from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ChatRequest, ChatResponse
from app.core.database import get_db
from app.services.chat import handle_chat

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, db: AsyncSession = Depends(get_db)):
    result = await handle_chat(body.session_id, body.message, db)
    return ChatResponse(
        answer=result.answer,
        sql=result.sql,
        results=result.results,
        row_count=len(result.results),
        session_state=result.session_state,
        intent=result.intent,
        out_of_scope=result.out_of_scope,
    )
