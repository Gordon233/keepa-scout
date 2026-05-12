from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Asin(Base):
    __tablename__ = "asins"

    # ── Identity ──
    asin: Mapped[str] = mapped_column(String, primary_key=True)

    # ── Product info (from Keepa product object) ──
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    brand: Mapped[str | None] = mapped_column(String, nullable=True)
    product_group: Mapped[str | None] = mapped_column(String, nullable=True)
    number_of_items: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="numberOfItems, used as n_items in ROI")
    package_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Pricing (from stats.current[], converted to USD) ──
    amazon_own_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="stats.current[0] / 100")
    new_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="stats.current[1] / 100")
    buybox_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="stats.current[18] / 100, includes shipping")

    # ── Demand signals ──
    sales_rank: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="stats.current[3]")
    monthly_sold: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="top-level monthlySold, 0/missing → NULL")

    # ── Fee structure (from Keepa) ──
    referral_fee_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="referralFeePercentage, e.g. 15.0 = 15%")
    fba_pick_pack_cents: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="raw Keepa cents, NOT converted to USD")

    # ── Competition ──
    amazon_buybox_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="time-weighted Amazon BuyBox share 0-100")
    new_offer_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="stats.current[11]")

    # ── Sourcing ──
    supplier_cost: Mapped[float | None] = mapped_column(Float, nullable=True, comment="from sample_asins.csv, USD")

    # ── Computed (by ETL) ──
    payout: Mapped[float | None] = mapped_column(Float, nullable=True, comment="buybox - referral - fba - storage")
    computed_roi_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="100 * (payout - cost) / cost")
    eligible: Mapped[bool | None] = mapped_column(Boolean, nullable=True, comment="all 5 eligibility rules pass")
    filter_failed: Mapped[str | None] = mapped_column(String, nullable=True, comment="first failed rule name, NULL if eligible")

    # ── Metadata ──
    last_updated: Mapped[datetime | None] = mapped_column(nullable=True)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    messages: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
