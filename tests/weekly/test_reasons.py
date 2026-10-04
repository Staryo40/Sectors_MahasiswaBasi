import pytest
from radar.signals.investor_reasons import build

@pytest.mark.parametrize("key,pillar,raw,percentile,code", [
    ("roe_ttm", "quality", 0.2, 1, "QUALITY_HIGH"),
    ("pe_relative", "valuation", 0.7, 1, "VALUATION_BELOW_PEERS"),
    ("yield_ttm", "valuation", 0.03, 1, "DIVIDEND_YIELD"),
    ("foreign_90d", "slow_flow", 0.01, 1, "FOREIGN_INFLOW_LONG"),
    ("holder_shift", "slow_flow", 0.03, 1, "HOLDER_SHIFT_INSTITUTIONAL"),
    ("holder_shift", "slow_flow", -0.02, 0, "HOLDER_SHIFT_RETAIL"),
    ("insider", "slow_flow", -1, 0, "INSIDER_ACTIVITY"),
])
def test_each_reason_code(key, pillar, raw, percentile, code):
    entry = {"pillars": {"quality": 90 if key == "roe_ttm" else 50},
             "components": [{"key": key, "pillar": pillar, "raw": raw, "percentile": percentile}]}
    reasons = build(entry)
    reason = next(r for r in reasons if r["code"] == code)
    assert set(reason) == {"code", "params", "text_en"}
    assert reason["params"]
    assert "buy" not in reason["text_en"].lower()
    assert "sell" not in reason["text_en"].lower()
    if key == "holder_shift":
        assert reason["params"]["pp"] == raw * 100

def test_top_three_by_influence():
    entry = {"pillars": {"quality": 100}, "components": [
        {"key": "pe_relative", "pillar": "valuation", "raw": 0.5, "percentile": 1},
        {"key": "yield_ttm", "pillar": "valuation", "raw": 0.04, "percentile": 0.5},
        {"key": "insider", "pillar": "slow_flow", "raw": 1, "percentile": 1},
        {"key": "holder_shift", "pillar": "slow_flow", "raw": 0.01, "percentile": 0.6}]}
    codes = [r["code"] for r in build(entry)]
    assert codes == ["QUALITY_HIGH", "INSIDER_ACTIVITY", "VALUATION_BELOW_PEERS"]
    assert build(entry, top=0) == []

def test_missing_and_negative_pe_no_positive_valuation_claim():
    assert build({"pillars": {"quality": None}, "components": []}) == []
    assert build({"components": [{"key": "pe_relative", "pillar": "valuation", "raw": -1, "percentile": 0}]}) == []
