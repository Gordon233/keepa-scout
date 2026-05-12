"""Tests for eligibility module — written before implementation (TDD)."""

import pytest
from app.services.eligibility import compute_payout, compute_roi, check_eligibility


# ---------------------------------------------------------------------------
# compute_payout
# ---------------------------------------------------------------------------

class TestComputePayout:
    def test_normal_case(self):
        # buybox=$30, referral=15%, fba=354 cents
        # referral = 30 * 0.15 = 4.50
        # fba = 354 / 100 = 3.54
        # storage = 0.50
        # payout = 30 - 4.50 - 3.54 - 0.50 = 21.46
        result = compute_payout(30.0, 15.0, 354)
        assert result == pytest.approx(21.46)

    def test_buybox_none(self):
        assert compute_payout(None, 15.0, 354) is None

    def test_referral_none(self):
        assert compute_payout(30.0, None, 354) is None

    def test_fba_none(self):
        assert compute_payout(30.0, 15.0, None) is None

    def test_all_none(self):
        assert compute_payout(None, None, None) is None


# ---------------------------------------------------------------------------
# compute_roi
# ---------------------------------------------------------------------------

class TestComputeRoi:
    def test_normal(self):
        # payout = 21.46 (from above), supplier_cost=5, n_items=1
        # roi = 100 * (21.46 - 5) / 5 = 100 * 16.46 / 5 = 329.2
        result = compute_roi(30.0, 15.0, 354, 5.0, 1)
        assert result == pytest.approx(329.2)

    def test_multi_pack(self):
        # n_items=3, cost = 5 * 3 = 15
        # roi = 100 * (21.46 - 15) / 15 = 100 * 6.46 / 15 ≈ 43.0667
        result = compute_roi(30.0, 15.0, 354, 5.0, 3)
        assert result == pytest.approx(100 * 6.46 / 15, rel=1e-6)

    def test_n_items_none_defaults_to_1(self):
        # n_items=None → treated as 1
        result = compute_roi(30.0, 15.0, 354, 5.0, None)
        expected = compute_roi(30.0, 15.0, 354, 5.0, 1)
        assert result == pytest.approx(expected)

    def test_cost_zero_returns_none(self):
        assert compute_roi(30.0, 15.0, 354, 0, 1) is None

    def test_cost_negative_returns_none(self):
        assert compute_roi(30.0, 15.0, 354, -5, 1) is None

    def test_fba_none_returns_none(self):
        # fba None → payout is None → roi is None
        assert compute_roi(30.0, 15.0, None, 5.0, 1) is None


# ---------------------------------------------------------------------------
# check_eligibility
# ---------------------------------------------------------------------------

def _base_snapshot(**overrides):
    """Return a snapshot dict that passes all rules, with optional overrides."""
    base = {
        "referral_fee_pct": 15.0,
        "sales_rank": 5000,
        "monthly_sold": 200,
        "buybox_price": 30.0,
        "amazon_buybox_pct": 50.0,
    }
    base.update(overrides)
    return base


class TestCheckEligibility:
    # --- all pass ---
    def test_all_pass(self):
        eligible, failed, checks = check_eligibility(_base_snapshot())
        assert eligible is True
        assert failed is None
        assert all(v["pass"] for v in checks.values())

    # --- each rule fails individually ---
    def test_rule1_referral_fee_none(self):
        eligible, failed, checks = check_eligibility(
            _base_snapshot(referral_fee_pct=None)
        )
        assert eligible is False
        assert failed == "referral_fee_pct"
        assert checks["referral_fee_pct"]["pass"] is False

    def test_rule1_referral_fee_zero(self):
        eligible, failed, checks = check_eligibility(
            _base_snapshot(referral_fee_pct=0)
        )
        assert eligible is False
        assert failed == "referral_fee_pct"

    def test_rule2_rank_and_sales_both_fail(self):
        eligible, failed, checks = check_eligibility(
            _base_snapshot(sales_rank=200_000, monthly_sold=50)
        )
        assert eligible is False
        assert failed == "rank_or_sales"
        assert checks["rank_or_sales"]["pass"] is False

    def test_rule2_rank_passes_with_low_monthly_sold(self):
        # rank <= 100000 is enough even if monthly_sold < 100
        eligible, failed, checks = check_eligibility(
            _base_snapshot(sales_rank=50_000, monthly_sold=10)
        )
        assert checks["rank_or_sales"]["pass"] is True

    def test_rule3_buybox_too_low(self):
        eligible, failed, checks = check_eligibility(
            _base_snapshot(buybox_price=9.99)
        )
        assert eligible is False
        assert failed == "buybox_price"
        assert checks["buybox_price"]["pass"] is False

    def test_rule4_amazon_buybox_too_high(self):
        eligible, failed, checks = check_eligibility(
            _base_snapshot(amazon_buybox_pct=85)
        )
        assert eligible is False
        assert failed == "amazon_buybox_pct"
        assert checks["amazon_buybox_pct"]["pass"] is False

    def test_rule4_none_treated_as_zero(self):
        # None → 0, which is <= 80 → pass
        eligible, failed, checks = check_eligibility(
            _base_snapshot(amazon_buybox_pct=None)
        )
        assert checks["amazon_buybox_pct"]["pass"] is True

    def test_rule5_monthly_sold_none_passes(self):
        # None → pass (we don't know, so we allow it)
        snap = _base_snapshot(monthly_sold=None, sales_rank=5000)
        eligible, failed, checks = check_eligibility(snap)
        assert checks["monthly_sold"]["pass"] is True

    def test_rule5_monthly_sold_too_low(self):
        # monthly_sold < 100 AND it's not None → fail rule 5
        # BUT we also need rule 2 to pass (rank must be <= 100000)
        snap = _base_snapshot(monthly_sold=50, sales_rank=5000)
        eligible, failed, checks = check_eligibility(snap)
        assert checks["monthly_sold"]["pass"] is False

    def test_first_failed_rule_returned(self):
        # Fail rules 1 and 3 → should report rule 1 as first
        snap = _base_snapshot(referral_fee_pct=None, buybox_price=5)
        eligible, failed, checks = check_eligibility(snap)
        assert failed == "referral_fee_pct"

    def test_checks_dict_structure(self):
        _, _, checks = check_eligibility(_base_snapshot())
        expected_keys = {
            "referral_fee_pct",
            "rank_or_sales",
            "buybox_price",
            "amazon_buybox_pct",
            "monthly_sold",
        }
        assert set(checks.keys()) == expected_keys
        for key, entry in checks.items():
            assert "pass" in entry, f"missing 'pass' in {key}"
            assert "value" in entry, f"missing 'value' in {key}"
            assert "threshold" in entry, f"missing 'threshold' in {key}"
