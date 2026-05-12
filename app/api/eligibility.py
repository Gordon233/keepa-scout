from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.schemas import BatchItem, BatchRequest, BatchResponse, EligibilityResponse
from app.core.database import get_db
from app.core.models import Asin
from app.services.eligibility import check_eligibility

router = APIRouter()

def _format_response(row: Asin) -> EligibilityResponse:
    snapshot = {
        "referral_fee_pct": row.referral_fee_pct,
        "sales_rank": row.sales_rank,
        "monthly_sold": row.monthly_sold,
        "buybox_price": row.buybox_price,
        "amazon_buybox_pct": row.amazon_buybox_pct,
    }
    _, _, checks = check_eligibility(snapshot)
    return EligibilityResponse(
        asin=row.asin, title=row.title, eligible=row.eligible,
        filter_failed=row.filter_failed, checks=checks,
        computed_roi_pct=row.computed_roi_pct, supplier_cost=row.supplier_cost,
        buybox_price=row.buybox_price, amazon_buybox_pct=row.amazon_buybox_pct,
    )

@router.get("/eligibility/{asin}", response_model=EligibilityResponse)
async def get_eligibility(asin: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Asin).where(Asin.asin == asin))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, f"ASIN {asin} not found")
    return _format_response(row)

@router.post("/eligibility/batch", response_model=BatchResponse)
async def batch_eligibility(body: BatchRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Asin).where(Asin.asin.in_(body.asins)))
    row_map = {r.asin: r for r in result.scalars().all()}
    items = []
    for asin in body.asins:
        row = row_map.get(asin)
        if row:
            items.append(BatchItem(asin=asin, found=True, data=_format_response(row)))
        else:
            items.append(BatchItem(asin=asin, found=False))
    return BatchResponse(results=items)
