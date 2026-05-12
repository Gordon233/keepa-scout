"""ETL pipeline: CSV → Keepa API → eligibility/ROI → SQLite."""

from __future__ import annotations

import asyncio
import csv
import time
from datetime import datetime, timezone

from app.core.database import engine, init_db
from app.core.keepa_client import fetch_products
from app.services.eligibility import check_eligibility, compute_payout, compute_roi

AMAZON_SELLER_ID = "ATVPDKIKX0DER"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _keepa_minutes_to_unix_ms(keepa_min: int) -> int:
    return (21564000 + keepa_min) * 60000


def _safe_price(val) -> float | None:
    if val is None or val == -1:
        return None
    return val / 100.0


def _safe_int(val) -> int | None:
    if val is None or val == -1:
        return None
    return int(val)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def load_csv(path: str) -> dict[str, float]:
    """Read sample_asins.csv, return {asin: supplier_cost} dict."""
    result: dict[str, float] = {}
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            asin = row["asin"].strip()
            cost = float(row["supplier_cost"])
            result[asin] = cost
    return result


def compute_buybox_pct(history: list | None) -> float:
    """Time-weighted calculation of Amazon's BuyBox share.

    *history* is the Keepa buyBoxSellerIdHistory array:
        [keepaMinutes, sellerId, keepaMinutes, sellerId, ...]
    """
    if not history or len(history) < 2:
        return 0.0

    now_ms = time.time() * 1000
    amazon_duration = 0.0
    total_duration = 0.0

    # Walk pairs: (keepaMinutes, sellerId)
    for i in range(0, len(history) - 1, 2):
        ts_start = _keepa_minutes_to_unix_ms(int(history[i]))

        # Determine end timestamp
        if i + 2 < len(history):
            ts_end = _keepa_minutes_to_unix_ms(int(history[i + 2]))
        else:
            ts_end = now_ms

        duration = ts_end - ts_start
        if duration <= 0:
            continue

        total_duration += duration
        seller_id = str(history[i + 1])
        if seller_id == AMAZON_SELLER_ID:
            amazon_duration += duration

    if total_duration == 0:
        return 0.0

    return amazon_duration / total_duration * 100


def extract_snapshot(product: dict, supplier_cost: float) -> dict:
    """Extract fields from a Keepa product response into a flat dict."""
    stats = product.get("stats") or {}
    current = stats.get("current") if stats else None
    fba_fees = product.get("fbaFees")

    # Basic fields
    snapshot: dict = {
        "asin": product.get("asin"),
        "title": product.get("title"),
        "brand": product.get("brand"),
        "product_group": product.get("productGroup"),
        "number_of_items": product.get("numberOfItems") or 1,
        "package_quantity": product.get("packageQuantity"),
        "supplier_cost": supplier_cost,
    }

    # Stats-derived fields
    if current and isinstance(current, list):
        snapshot["amazon_own_price"] = _safe_price(
            current[0] if len(current) > 0 else None
        )
        snapshot["new_price"] = _safe_price(
            current[1] if len(current) > 1 else None
        )
        snapshot["sales_rank"] = _safe_int(
            current[3] if len(current) > 3 else None
        )
        snapshot["new_offer_count"] = _safe_int(
            current[11] if len(current) > 11 else None
        )
        snapshot["buybox_price"] = _safe_price(
            current[18] if len(current) > 18 else None
        )
    else:
        snapshot["amazon_own_price"] = None
        snapshot["new_price"] = None
        snapshot["sales_rank"] = None
        snapshot["new_offer_count"] = None
        snapshot["buybox_price"] = None

    # Monthly sold
    monthly_sold = product.get("monthlySold")
    snapshot["monthly_sold"] = monthly_sold if monthly_sold else None

    # Referral fee — use referralFeePercentage (Double), NOT deprecated referralFeePercent
    snapshot["referral_fee_pct"] = product.get("referralFeePercentage")

    # FBA fees — fbaFees object itself can be null
    if fba_fees:
        snapshot["fba_pick_pack_cents"] = fba_fees.get("pickAndPackFee")
    else:
        snapshot["fba_pick_pack_cents"] = None

    # BuyBox ownership percentage
    snapshot["amazon_buybox_pct"] = compute_buybox_pct(
        product.get("buyBoxSellerIdHistory")
    )

    # Computed fields
    n_items = snapshot["number_of_items"]
    buybox = snapshot["buybox_price"]
    ref_pct = snapshot["referral_fee_pct"]
    fba_cents = snapshot["fba_pick_pack_cents"]

    snapshot["payout"] = compute_payout(buybox, ref_pct, fba_cents)

    roi = compute_roi(buybox, ref_pct, fba_cents, supplier_cost, n_items)
    snapshot["computed_roi_pct"] = round(roi, 2) if roi is not None else None

    eligible, filter_failed, _ = check_eligibility(snapshot)
    snapshot["eligible"] = eligible
    snapshot["filter_failed"] = filter_failed

    snapshot["last_updated"] = datetime.now(timezone.utc).isoformat()

    return snapshot


# ---------------------------------------------------------------------------
# Async ETL runner
# ---------------------------------------------------------------------------

# Columns in the asins table (must match models.py)
_COLUMNS = [
    "asin",
    "title",
    "brand",
    "product_group",
    "number_of_items",
    "package_quantity",
    "amazon_own_price",
    "new_price",
    "buybox_price",
    "sales_rank",
    "monthly_sold",
    "referral_fee_pct",
    "fba_pick_pack_cents",
    "amazon_buybox_pct",
    "supplier_cost",
    "payout",
    "computed_roi_pct",
    "eligible",
    "filter_failed",
    "new_offer_count",
    "last_updated",
]


async def run_etl() -> None:
    """Main ETL entry point."""
    print("Initialising database...")
    await init_db()

    print("Loading CSV...")
    asin_costs = load_csv("data/sample_asins.csv")
    asins = list(asin_costs.keys())
    print(f"  {len(asins)} ASINs loaded from CSV.")

    print("Fetching Keepa data...")
    products = await fetch_products(asins)
    print(f"  {len(products)} products returned from Keepa.")

    # Index products by ASIN for lookup
    product_map: dict[str, dict] = {}
    for p in products:
        a = p.get("asin")
        if a:
            product_map[a] = p

    snapshots: list[dict] = []
    for asin in asins:
        if asin not in product_map:
            print(f"  SKIP {asin}: no Keepa data")
            continue
        snap = extract_snapshot(product_map[asin], asin_costs[asin])
        snapshots.append(snap)

    print(f"Upserting {len(snapshots)} rows into database...")

    # Build INSERT OR REPLACE statement
    placeholders = ", ".join(f":{c}" for c in _COLUMNS)
    col_names = ", ".join(_COLUMNS)
    sql = f"INSERT OR REPLACE INTO asins ({col_names}) VALUES ({placeholders})"

    async with engine.begin() as conn:
        from sqlalchemy import text

        for snap in snapshots:
            await conn.execute(text(sql), snap)

    print("ETL complete.")


if __name__ == "__main__":
    asyncio.run(run_etl())
