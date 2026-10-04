import json
from pathlib import Path
import pytest
from jsonschema import ValidationError
from radar.export.validation import validate

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "out"

@pytest.mark.parametrize("name", ["meta", "daily", "investor", "brief_daily", "brief_weekly"])
def test_output_sample(name):
    validate(name, json.loads((FIXTURES / f"{name}.json").read_text()))

def test_stock_samples():
    daily = json.loads((FIXTURES / "daily.json").read_text())
    investor = json.loads((FIXTURES / "investor.json").read_text())
    assert len(daily) == len(investor) == 5
    for d, i in zip(daily, investor):
        stock = json.loads((FIXTURES / "stocks" / f"{d['symbol']}.json").read_text())
        validate("stock", stock)
        assert stock["daily"] == d
        assert stock["investor"] == i

@pytest.mark.parametrize("name,key,value", [("meta", "as_of", "bad-date"), ("investor", "coverage", 1.1), ("daily", "flow_score", 101)])
def test_schema_rejects_invalid_data(name, key, value):
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    (data[0] if isinstance(data, list) else data)[key] = value
    with pytest.raises(ValidationError):
        validate(name, data)
