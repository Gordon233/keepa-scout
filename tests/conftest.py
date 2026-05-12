import asyncio
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

os.environ["DB_PATH"] = ":memory:"
os.environ["KEEPA_API_KEYS"] = "test-key"
os.environ["OPENROUTER_API_KEY"] = "test-key"

from app.core.database import engine, init_db
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def client():
    await init_db()
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT OR REPLACE INTO asins (
                asin, title, eligible, filter_failed, computed_roi_pct,
                supplier_cost, buybox_price, amazon_buybox_pct,
                referral_fee_pct, sales_rank, monthly_sold
            ) VALUES (
                'B00TEST001', 'Test Widget', 1, NULL, 50.0,
                10.0, 25.0, 12.0, 15.0, 5000, 200
            )
        """))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
