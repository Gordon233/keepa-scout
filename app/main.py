from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.core.database import init_db
from app.api import health, upc, eligibility, ask, chat
from app.core.keepa_client import KeepaError
from app.core.llm_client import LLMError


@asynccontextmanager
async def lifespan(app):
    await init_db()
    yield


app = FastAPI(title="Keepa Scout", lifespan=lifespan)
app.include_router(health.router)
app.include_router(upc.router)
app.include_router(eligibility.router)
app.include_router(ask.router)
app.include_router(chat.router)


@app.exception_handler(KeepaError)
async def keepa_error_handler(request: Request, exc: KeepaError):
    return JSONResponse(status_code=503, content={"error": "Keepa API unavailable", "detail": str(exc)})


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    return JSONResponse(status_code=503, content={"error": "LLM service unavailable", "detail": str(exc)})
