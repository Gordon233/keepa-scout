from fastapi import APIRouter, Query
from app.api.schemas import UpcResponse
from app.core.keepa_client import fetch_by_codes
from app.services.upc import normalize

router = APIRouter()

@router.get("/upc", response_model=UpcResponse)
async def upc_lookup(upc: str = Query(...)):
    variants = normalize(upc)
    if not variants:
        return UpcResponse(input=upc, normalized=[], asins=[])
    products = await fetch_by_codes(variants)
    asins = sorted(set(p["asin"] for p in products if "asin" in p))
    return UpcResponse(input=upc, normalized=variants, asins=asins)
