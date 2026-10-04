import copy
import pytest
from radar.signals.changes_weekly import diff

@pytest.fixture
def history(db, trading_days):
    for date in ("2026-09-25", "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02"):
        db.execute("INSERT INTO prices(symbol,date,close) VALUES ('A',?,100)", (date,))
    return db

def test_new_top5(history):
    now = [{"symbol": "A", "rank": 3}]
    prev = [{"symbol": "A", "rank": 6}]
    saved = copy.deepcopy((now, prev))
    result = diff(now, prev, history, "2026-10-02")
    assert [i["kind"] for i in result["items"]] == ["new_top5"]
    assert result["items"][0]["code"] == "NEW_TOP5"
    assert (now, prev) == saved

def test_rank_mover_both_directions(history):
    result = diff([{"symbol": "A", "rank": 1}, {"symbol": "B", "rank": 12}],
                  [{"symbol": "A", "rank": 6}, {"symbol": "B", "rank": 2}], history, "2026-10-02")
    changes = [i["params"]["change"] for i in result["items"] if i["kind"] == "rank_mover"]
    assert changes == [5, -10]

def test_holder_shift_new_snapshot(history):
    for date, individuals in [("2026-08-31", 40), ("2026-09-30", 38), ("2026-10-03", 1)]:
        history.execute("INSERT INTO holder_mix(symbol,date,shares_number,individual_l,individual_f) VALUES ('A',?,100,?,0)", (date, individuals))
    rows = [{"symbol": "A", "rank": 7}]
    result = diff(rows, rows, history, "2026-10-02")
    item = result["items"][0]
    assert item["kind"] == "holder_shift"
    assert item["params"]["pp"] == pytest.approx(2)
    assert item["params"]["from_date"] == "2026-08-31"
    assert item["params"]["to_date"] == "2026-09-30"
    # Once that snapshot is the comparison baseline, it is no longer new.
    for date in ("2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09"):
        history.execute("INSERT INTO prices(symbol,date,close) VALUES ('A',?,100)", (date,))
    # Remove the future snapshot used above to isolate repeat detection.
    history.execute("DELETE FROM holder_mix WHERE date='2026-10-03'")
    assert diff(rows, rows, history, "2026-10-09")["items"] == []

def test_upcoming_filtered_to_universe_and_window(history):
    for symbol, key_date in [("A", "2026-10-08"), ("Z", "2026-10-08"), ("A", "2026-12-01"), ("A", "2026-10-01")]:
        history.execute("INSERT INTO corporate_actions(symbol,type,key_date) VALUES (?, 'dividend', ?)", (symbol, key_date))
    rows = [{"symbol": "A", "rank": 7}]
    result = diff(rows, rows, history, "2026-10-02")
    assert result["upcoming"] == [{"date": "2026-10-08", "symbol": "A", "type": "dividend_ex_date"}]

def test_no_prior_history_no_false_rank_or_holder_movers(db, trading_days):
    result = diff([{"symbol": "A", "rank": 1}], [], db, "2026-10-02")
    assert [i["kind"] for i in result["items"]] == ["new_top5"]
