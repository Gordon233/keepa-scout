"""Eligibility and ROI computations — pure functions, no I/O."""

from __future__ import annotations


def compute_payout(
    buybox: float | None,
    referral_fee_pct: float | None,
    fba_pick_pack_cents: int | None,
) -> float | None:
    """Net payout after Amazon fees.

    Returns None when any input is missing.
    """
    if buybox is None or referral_fee_pct is None or fba_pick_pack_cents is None:
        return None
    referral = buybox * (referral_fee_pct / 100)
    fba = fba_pick_pack_cents / 100
    storage = 0.50
    return buybox - referral - fba - storage


def compute_roi(
    buybox: float | None,
    referral_pct: float | None,
    fba_pick_pack_cents: int | None,
    supplier_cost: float,
    n_items: int | None,
) -> float | None:
    """Return-on-investment percentage.

    *n_items* defaults to 1 when None or < 1.
    Returns None when payout cannot be calculated or cost <= 0.
    """
    payout = compute_payout(buybox, referral_pct, fba_pick_pack_cents)
    if payout is None:
        return None
    cost = supplier_cost * max(n_items or 1, 1)
    if cost <= 0:
        return None
    return 100 * (payout - cost) / cost


def check_eligibility(snapshot: dict) -> tuple[bool, str | None, dict]:
    """Run five eligibility rules against a product snapshot.

    Returns (eligible, first_failed_rule_name_or_None, checks_dict).
    """
    referral_fee_pct = snapshot.get("referral_fee_pct")
    sales_rank = snapshot.get("sales_rank")
    monthly_sold = snapshot.get("monthly_sold")
    buybox_price = snapshot.get("buybox_price")
    amazon_buybox_pct = snapshot.get("amazon_buybox_pct")

    checks: dict[str, dict] = {}
    first_failed: str | None = None

    # Rule 1: referral_fee_pct is not None and > 0
    rule1_pass = referral_fee_pct is not None and referral_fee_pct > 0
    checks["referral_fee_pct"] = {
        "pass": rule1_pass,
        "value": referral_fee_pct,
        "threshold": "> 0",
    }
    if not rule1_pass and first_failed is None:
        first_failed = "referral_fee_pct"

    # Rule 2: sales_rank <= 100_000 OR monthly_sold >= 100
    rank_ok = sales_rank is not None and sales_rank <= 100_000
    sold_ok = monthly_sold is not None and monthly_sold >= 100
    rule2_pass = rank_ok or sold_ok
    checks["rank_or_sales"] = {
        "pass": rule2_pass,
        "value": {"sales_rank": sales_rank, "monthly_sold": monthly_sold},
        "threshold": "rank <= 100000 OR monthly_sold >= 100",
    }
    if not rule2_pass and first_failed is None:
        first_failed = "rank_or_sales"

    # Rule 3: buybox_price >= 10
    rule3_pass = buybox_price is not None and buybox_price >= 10
    checks["buybox_price"] = {
        "pass": rule3_pass,
        "value": buybox_price,
        "threshold": ">= 10",
    }
    if not rule3_pass and first_failed is None:
        first_failed = "buybox_price"

    # Rule 4: amazon_buybox_pct <= 80 (None treated as 0)
    abp = amazon_buybox_pct if amazon_buybox_pct is not None else 0
    rule4_pass = abp <= 80
    checks["amazon_buybox_pct"] = {
        "pass": rule4_pass,
        "value": abp,
        "threshold": "<= 80",
    }
    if not rule4_pass and first_failed is None:
        first_failed = "amazon_buybox_pct"

    # Rule 5: monthly_sold is None OR >= 100
    rule5_pass = monthly_sold is None or monthly_sold >= 100
    checks["monthly_sold"] = {
        "pass": rule5_pass,
        "value": monthly_sold,
        "threshold": "None OR >= 100",
    }
    if not rule5_pass and first_failed is None:
        first_failed = "monthly_sold"

    eligible = first_failed is None
    return eligible, first_failed, checks
