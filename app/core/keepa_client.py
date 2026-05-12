import asyncio
import random

import httpx

from app.config import settings

_BASE_URL = "https://api.keepa.com/product"
_TIMEOUT = 30.0

_key_index = 0


class KeepaError(Exception):
    """Raised when all Keepa API keys/retries are exhausted."""


def _next_key() -> str:
    global _key_index
    keys = settings.keepa_keys
    if not keys:
        raise KeepaError("No Keepa API keys configured")
    key = keys[_key_index % len(keys)]
    _key_index = (_key_index + 1) % len(keys)
    return key


async def _request_with_retry(params: dict, max_retries: int | None = None) -> dict:
    keys = settings.keepa_keys
    if not keys:
        raise KeepaError("No Keepa API keys configured")

    effective_max = max_retries if max_retries is not None else 3 * len(keys)

    last_exc: Exception | None = None
    for attempt in range(effective_max):
        key = _next_key()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(_BASE_URL, params={"key": key, **params})

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code in (402, 429):
                backoff = min(2**attempt + random.random(), 30)
                await asyncio.sleep(backoff)
                last_exc = KeepaError(
                    f"HTTP {resp.status_code} from Keepa (attempt {attempt + 1})"
                )
                continue

            # Any other non-200 is unexpected — raise immediately
            raise KeepaError(f"Unexpected HTTP {resp.status_code} from Keepa")

        except KeepaError:
            raise
        except Exception as exc:
            backoff = min(2**attempt + random.random(), 30)
            await asyncio.sleep(backoff)
            last_exc = exc
            continue

    raise KeepaError(
        f"All {effective_max} Keepa retries exhausted"
    ) from last_exc


async def fetch_products(asins: list[str]) -> list[dict]:
    """Fetch Keepa product data for a list of ASINs, batched in groups of 100."""
    results: list[dict] = []
    for i in range(0, len(asins), 100):
        batch = asins[i : i + 100]
        params = {
            "domain": 1,
            "asin": ",".join(batch),
            "stats": 90,
            "buybox": 1,
            "fbafees": 1,
        }
        data = await _request_with_retry(params)
        products = data.get("products") or []
        results.extend(products)
    return results


async def fetch_by_codes(codes: list[str]) -> list[dict]:
    """Fetch Keepa product data by barcode/EAN/UPC codes, one at a time."""
    results: list[dict] = []
    for code in codes:
        params = {
            "domain": 1,
            "code": code,
        }
        try:
            data = await _request_with_retry(params)
            products = data.get("products") or []
            results.extend(products)
        except KeepaError:
            continue
    return results
