"""Chat service: multi-turn stateful conversations with session persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ChatResult
from app.core.llm_client import chat_completion, chat_completion_json
from app.core.models import ChatSession
from app.services.nl2sql import TABLE_SCHEMA
from app.services.sql_guard import UnsafeSqlError, ensure_safe


CHAT_RESPONSE_SCHEMA = {
    "title": "chat_response",
    "type": "object",
    "properties": {
        "sql": {"type": "string", "description": "SQLite SELECT query"},
        "active_filters_json": {"type": "string", "description": 'JSON string of all active filters, e.g. \'{"eligible_only":true,"min_roi":25}\''},
        "sort": {"type": ["string", "null"], "description": "Current sort label or null"},
        "limit": {"type": ["integer", "null"], "description": "Result limit or null"},
        "topic_reset": {"type": "boolean", "description": "True only if user explicitly resets"},
        "focused_asin": {"type": ["string", "null"], "description": "Specific ASIN or null"},
        "preference_json": {"type": ["string", "null"], "description": 'JSON string of preference or null, e.g. \'{"budget_per_unit":20}\''},
        "is_out_of_scope": {"type": "boolean", "description": "True if question is NOT about Amazon ASIN arbitrage (weather, recipes, general knowledge, etc). Domain concepts like 'What is ROI' are IN scope."},
    },
    "required": ["sql", "active_filters_json", "sort", "limit", "topic_reset", "focused_asin", "preference_json", "is_out_of_scope"],
    "additionalProperties": False,
}


@dataclass
class SessionState:
    active_filters: dict = field(default_factory=dict)
    last_result_asins: list[str] = field(default_factory=list)
    focused_asin: str | None = None
    user_constraints: dict = field(default_factory=dict)
    sort: str | None = None
    limit: int | None = None

    def to_dict(self) -> dict:
        return {
            "active_filters": self.active_filters,
            "last_result_asins": self.last_result_asins,
            "focused_asin": self.focused_asin,
            "user_constraints": self.user_constraints,
            "sort": self.sort,
            "limit": self.limit,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SessionState":
        return cls(
            active_filters=d.get("active_filters", {}),
            last_result_asins=d.get("last_result_asins", []),
            focused_asin=d.get("focused_asin"),
            user_constraints=d.get("user_constraints", {}),
            sort=d.get("sort"),
            limit=d.get("limit"),
        )


async def _load_session(
    db: AsyncSession, session_id: str
) -> tuple[list[dict], SessionState]:
    """Load messages and state from ChatSession table. Return defaults if not found."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.session_id == session_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return [], SessionState()

    messages = json.loads(row.messages) if row.messages else []
    state = SessionState.from_dict(json.loads(row.session_state) if row.session_state else {})
    return messages, state


async def _save_session(
    db: AsyncSession,
    session_id: str,
    messages: list[dict],
    state: SessionState,
) -> None:
    """Upsert session into ChatSession table."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.session_id == session_id)
    )
    row = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if row is None:
        row = ChatSession(
            session_id=session_id,
            messages=json.dumps(messages),
            session_state=json.dumps(state.to_dict()),
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.messages = json.dumps(messages)
        row.session_state = json.dumps(state.to_dict())
        row.updated_at = now

    await db.commit()


def _build_context_prompt(state: SessionState, messages: list[dict]) -> str:
    """Build the LLM system prompt with full session context."""
    parts: list[str] = [
        "You are an Amazon arbitrage analyst with multi-turn conversation capability.",
        "",
        "DATABASE SCHEMA:",
        TABLE_SCHEMA,
        "",
    ]

    if state.active_filters:
        parts.append(f"ACTIVE FILTERS (apply ALL of these plus any new ones from the user message):")
        parts.append(json.dumps(state.active_filters))
        parts.append("")

    if state.user_constraints:
        parts.append(f"USER CONSTRAINTS (persistent preferences):")
        parts.append(json.dumps(state.user_constraints))
        parts.append("")

    if state.last_result_asins:
        parts.append("LAST RESULT ASINs (numbered list for ordinal resolution):")
        for i, asin in enumerate(state.last_result_asins, 1):
            parts.append(f"  {i}. {asin}")
        parts.append("")

    if state.focused_asin:
        parts.append(f"CURRENTLY FOCUSED ASIN: {state.focused_asin}")
        parts.append("")

    parts.extend([
        "INSTRUCTIONS:",
        "- Generate a single SQLite SELECT query that answers the user's question.",
        "- Apply ALL active filters AND any new ones from the current message.",
        '- Resolve ordinal references like "the second one" or "it" using the numbered LAST RESULT ASINs list.',
        '- If user says "forget that", "actually", or "never mind", set topic_reset to true and clear all filters.',
        "- If the message is about a specific ASIN, focus the query on that ASIN.",
        "",
        "RESPONSE FORMAT — return ONLY a JSON object, no markdown, no explanation:",
        '{',
        '  "sql": "SELECT ...",',
        '  "active_filters": {"eligible_only": true, "min_roi": 25},',
        '  "sort": "roi_desc",',
        '  "limit": 5,',
        '  "topic_reset": false,',
        '  "focused_asin": null,',
        '  "preference": null',
        '}',
        "",
        "Rules for the JSON fields:",
        '- "sql": the SQLite SELECT query',
        '- "active_filters": ALL filters currently in effect (merged: previous + new from this message)',
        '- "sort": current sort order as a short label, or null',
        '- "limit": result limit if user asked for top N, or null',
        '- "topic_reset": true ONLY if user explicitly resets ("forget that", "actually", "never mind")',
        '- "focused_asin": set to a specific ASIN if the user asks about one, or null',
        '- "preference": set to {"key": "value"} if user sets a preference like "my budget is $20", or null',
        '- "is_out_of_scope": true if question is NOT about Amazon ASIN arbitrage (weather, cooking, general knowledge). Domain concepts like "What is ROI?" are IN scope (false).',
    ])

    return "\n".join(parts)


async def handle_chat(
    session_id: str, message: str, db: AsyncSession
) -> ChatResult:
    """Orchestrate a single chat turn with full session state management."""

    # 1. Load session
    messages, state = await _load_session(db, session_id)

    # 2. Build context prompt (scope detection is now handled by LLM via structured output)
    system_prompt = _build_context_prompt(state, messages)

    # 4. Prepare recent history (last 10 turns) + current message for LLM
    recent = messages[-20:]
    llm_messages: list[dict] = [{"role": "system", "content": system_prompt}]
    llm_messages.extend(recent)
    llm_messages.append({"role": "user", "content": message})

    # 5. Call LLM with structured output — guaranteed JSON schema
    llm_resp = await chat_completion_json(llm_messages, CHAT_RESPONSE_SCHEMA)

    # 5a. Out-of-scope — LLM decided this is not about arbitrage. Preserve state, reject.
    if llm_resp.get("is_out_of_scope"):
        _OOS = "I can only help with Amazon ASIN arbitrage analysis."
        messages.append({"role": "user", "content": message})
        messages.append({"role": "assistant", "content": _OOS})
        await _save_session(db, session_id, messages, state)
        return ChatResult(
            answer=_OOS,
            session_state=state.to_dict(),
            intent={"intent": "out_of_scope"},
            out_of_scope=True,
        )

    # 6. Parse and apply state updates
    intent: dict = {}
    active_filters = json.loads(llm_resp.get("active_filters_json") or "{}")
    preference_raw = llm_resp.get("preference_json")
    preference = json.loads(preference_raw) if preference_raw else None

    if llm_resp.get("topic_reset"):
        state.active_filters = {}
        state.sort = None
        state.limit = None
        state.focused_asin = None
        intent["topic_reset"] = True
    else:
        state.active_filters = active_filters
        state.sort = llm_resp.get("sort")
        state.limit = llm_resp.get("limit")

    if llm_resp.get("focused_asin"):
        state.focused_asin = llm_resp["focused_asin"]
        intent["resolved_asin"] = llm_resp["focused_asin"]

    if preference:
        state.user_constraints.update(preference)
        pref_desc = ", ".join(f"{k}={v}" for k, v in preference.items())
        answer = f"Got it. I'll apply {pref_desc} to subsequent queries."
        messages.append({"role": "user", "content": message})
        messages.append({"role": "assistant", "content": answer})
        await _save_session(db, session_id, messages, state)
        return ChatResult(
            answer=answer,
            session_state=state.to_dict(),
            intent={"preference_set": list(preference.keys())},
        )

    sql = llm_resp.get("sql", "").strip()

    # 7. Safety check
    try:
        ensure_safe(sql)
    except UnsafeSqlError:
        messages.append({"role": "user", "content": message})
        messages.append({"role": "assistant", "content": "I couldn't translate that question safely."})
        await _save_session(db, session_id, messages, state)
        return ChatResult(
            answer="I couldn't translate that question safely.",
            sql=sql,
            session_state=state.to_dict(),
        )

    # 8. Execute SQL
    try:
        result = await db.execute(text(sql))
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
    except Exception:
        messages.append({"role": "user", "content": message})
        messages.append({"role": "assistant", "content": "I couldn't process that query."})
        await _save_session(db, session_id, messages, state)
        return ChatResult(
            answer="I couldn't process that query.",
            sql=sql,
            session_state=state.to_dict(),
        )

    # 9. Update result tracking in state
    result_asins = [str(r["asin"]) for r in rows if "asin" in r and r["asin"]]
    if result_asins:
        state.last_result_asins = result_asins
    if len(result_asins) == 1:
        state.focused_asin = result_asins[0]
        intent["resolved_asin"] = result_asins[0]

    # 10. Summarize results via LLM
    preview = rows[:20]
    summary_messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant that summarizes SQL query results "
                "for Amazon arbitrage analysis. Reference specific ASINs and "
                "numbers in your summary."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question: {message}\n\n"
                f"SQL: {sql}\n\n"
                f"Results ({len(rows)} rows, showing first {len(preview)}):\n"
                f"{json.dumps(preview, default=str)}"
            ),
        },
    ]
    answer = await chat_completion(summary_messages)

    # 11. Append messages and save session
    messages.append({"role": "user", "content": message})
    messages.append({"role": "assistant", "content": answer})
    await _save_session(db, session_id, messages, state)

    return ChatResult(
        answer=answer,
        sql=sql,
        results=rows,
        session_state=state.to_dict(),
        intent=intent if intent else None,
    )
