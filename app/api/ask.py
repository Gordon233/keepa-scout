from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.schemas import AskRequest, AskResponse
from app.core.database import get_db
from app.services.nl2sql import handle_ask

router = APIRouter()


@router.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest, db: AsyncSession = Depends(get_db)):
    result = await handle_ask(body.question, db)
    return AskResponse(
        answer=result.answer,
        sql=result.sql,
        rows=result.rows,
        row_count=len(result.rows),
        out_of_scope=result.out_of_scope,
    )
