"""NL-to-SQL service: domain detection -> SQL generation -> safety check -> execution -> summarization."""

from __future__ import annotations

import json
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AskResult
from app.core.llm_client import chat_completion
from app.services.sql_guard import UnsafeSqlError, ensure_safe

TABLE_SCHEMA = """\
Table: asins
Columns:
  asin TEXT PRIMARY KEY
  title TEXT
  brand TEXT
  product_group TEXT
  number_of_items INTEGER
  buybox_price REAL              -- BuyBox price in USD
  sales_rank INTEGER
  monthly_sold INTEGER           -- monthly units sold, NULL = unknown
  referral_fee_pct REAL          -- e.g. 15.0 means 15%
  amazon_buybox_pct REAL         -- Amazon's Buy Box share %, 0-100
  supplier_cost REAL             -- wholesale cost per unit in USD
  payout REAL                    -- revenue after fees in USD
  computed_roi_pct REAL          -- ROI percentage, NULL if not computable
  eligible BOOLEAN               -- passes all 5 eligibility rules
  filter_failed TEXT             -- name of first failed rule, NULL if eligible
  new_offer_count INTEGER        -- number of competing new offers
  amazon_own_price REAL          -- Amazon's own listing price in USD
Notes:
  - Use COALESCE or IS NOT NULL when querying nullable columns
  - ORDER BY computed_roi_pct DESC NULLS LAST for ROI ranking
  - eligible = 1 for eligible, eligible = 0 for not eligible"""

_OOS_MESSAGE = "I can only help with Amazon ASIN arbitrage analysis."


async def check_out_of_scope(question: str) -> bool:
    """LLM-based domain check. Returns True if question is out of scope."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a scope classifier for an Amazon ASIN arbitrage analysis tool.\n"
                "Answer ONLY 'yes' or 'no'.\n"
                "- 'yes' = question is about Amazon arbitrage, ASINs, products, pricing, "
                "ROI, eligibility, BuyBox, suppliers, fees, sales rank, or related concepts.\n"
                "- 'no' = question is about weather, cooking, sports, general knowledge, or anything unrelated.\n"
                "Domain concepts like 'What is ROI?' or 'How does BuyBox work?' are IN scope (yes)."
            ),
        },
        {"role": "user", "content": question},
    ]
    resp = await chat_completion(messages, temperature=0)
    return "no" in resp.strip().lower()


async def handle_ask(question: str, db: AsyncSession) -> AskResult:
    """Orchestrate the /ask flow: domain check -> SQL generation -> safety -> execute -> summarize."""

    # 1. LLM-based domain check
    if await check_out_of_scope(question):
        return AskResult(answer=_OOS_MESSAGE, out_of_scope=True)

    # 2-3. Build SQL generation prompt and call LLM
    sql_messages = [
        {
            "role": "system",
            "content": (
                f"You are a SQL assistant. Given the following table schema, "
                f"generate a single SQLite SELECT query that answers the user's question.\n\n"
                f"{TABLE_SCHEMA}\n\n"
                f"Return ONLY the raw SQL. No markdown, no explanation, no code fences."
            ),
        },
        {"role": "user", "content": question},
    ]
    sql = await chat_completion(sql_messages)

    # 4. Strip markdown fences if present
    sql = re.sub(r"^```(?:sql)?\s*", "", sql.strip())
    sql = re.sub(r"\s*```$", "", sql.strip())
    sql = sql.strip()

    # 5. Safety check
    try:
        ensure_safe(sql)
    except UnsafeSqlError:
        return AskResult(
            answer="I couldn't translate that question safely.",
            sql=sql,
        )

    # 6. Execute SQL
    try:
        result = await db.execute(text(sql))
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
    except Exception:
        return AskResult(
            answer="I couldn't process that query.",
            sql=sql,
        )

    # 7-8. Summarize results
    preview = rows[:20]
    summary_messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant that summarizes SQL query results. "
                "Reference specific ASINs and numbers in your summary."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"SQL: {sql}\n\n"
                f"Results ({len(rows)} rows, showing first {len(preview)}):\n"
                f"{json.dumps(preview, default=str)}"
            ),
        },
    ]
    answer = await chat_completion(summary_messages)

    # 9. Return result
    return AskResult(answer=answer, sql=sql, rows=rows)
