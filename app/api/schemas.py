from __future__ import annotations
from dataclasses import dataclass, field
from pydantic import BaseModel

# --- Request models ---
class AskRequest(BaseModel):
    question: str

class ChatRequest(BaseModel):
    session_id: str
    message: str

class BatchRequest(BaseModel):
    asins: list[str]

# --- Response models ---
class UpcResponse(BaseModel):
    input: str
    normalized: list[str]
    asins: list[str]

class EligibilityResponse(BaseModel):
    asin: str
    title: str | None
    eligible: bool
    filter_failed: str | None
    checks: dict
    computed_roi_pct: float | None
    supplier_cost: float
    buybox_price: float | None
    amazon_buybox_pct: float | None

class BatchItem(BaseModel):
    asin: str
    found: bool
    data: EligibilityResponse | None = None

class BatchResponse(BaseModel):
    results: list[BatchItem]

class AskResponse(BaseModel):
    answer: str
    sql: str | None = None
    rows: list[dict] = []
    row_count: int = 0
    out_of_scope: bool = False

class ChatResponse(BaseModel):
    answer: str
    sql: str | None = None
    results: list[dict] = []
    row_count: int = 0
    session_state: dict = {}
    intent: dict | None = None
    out_of_scope: bool = False

# --- Service-layer result dataclasses ---
@dataclass
class AskResult:
    answer: str
    sql: str | None = None
    rows: list[dict] = field(default_factory=list)
    out_of_scope: bool = False

@dataclass
class ChatResult:
    answer: str
    sql: str | None = None
    results: list[dict] = field(default_factory=list)
    session_state: dict = field(default_factory=dict)
    intent: dict | None = None
    out_of_scope: bool = False
