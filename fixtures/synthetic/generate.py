"""Deterministic generator for synthetic test database fixtures/synthetic/synthetic.db.

Owned by agent B (task B0).
Produces a §4-shaped SQLite database for 45 fake-but-plausible stocks over 90 trading days,
including edge cases:
- A stock with no foreign flow (NOFF)
- Null f_* in broker_summary
- Missing fundamentals (MISF)
- A suspended stock (SUSP)
- A Financials-sector stock (FINA)
"""

from __future__ import annotations

import datetime
import json
import random
import sqlite3
from pathlib import Path

from radar import config, db

OUTPUT_PATH = config.FIXTURES_DIR / "synthetic" / "synthetic.db"
SEED = 42


def generate_trading_days(end_date: datetime.date, count: int) -> list[str]:
    """Generate `count` weekdays ending on `end_date`, sorted ascending."""
    days: list[str] = []
    curr = end_date
    while len(days) < count:
        if curr.weekday() < 5:  # Monday to Friday
            days.append(curr.isoformat())
        curr -= datetime.timedelta(days=1)
    days.reverse()
    return days


def generate(target_path: Path | str = OUTPUT_PATH) -> Path:
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    conn = db.connect(target)
    db.init_schema(conn)

    rng = random.Random(SEED)
    end_date = datetime.date(2026, 10, 2)
    trading_dates = generate_trading_days(end_date, 90)

    # 1. Brokers registry
    brokers_data = [
        ("CC", "Mandiri Sekuritas", 0, "institutional"),
        ("ZP", "Maybank Sekuritas", 1, "institutional"),
        ("RX", "Macquarie Sekuritas", 1, "institutional"),
        ("AK", "UBS Sekuritas", 1, "institutional"),
        ("CS", "Credit Suisse", 1, "institutional"),
        ("BK", "J.P. Morgan", 1, "institutional"),
        ("YP", "Mirae Asset", 0, "retail"),
        ("PD", "Indo Premier", 0, "retail"),
        ("XC", "Ajaib Sekuritas", 0, "retail"),
        ("NI", "BNI Sekuritas", 0, "mixed"),
        ("OD", "BRI Danareksa", 0, "mixed"),
        ("DR", "RHB Sekuritas", 1, "mixed"),
        ("LG", "Trimegah Sekuritas", 0, "mixed"),
        ("ZZ", "Unknown Broker", 0, "unknown"),
    ]
    conn.executemany(
        "INSERT INTO brokers (code, name, is_foreign, cohort) VALUES (?, ?, ?, ?)",
        brokers_data,
    )

    # 2. 45 Companies
    sectors = [
        "Financials",
        "Energy",
        "Basic Materials",
        "Consumer Non-Cyclicals",
        "Consumer Cyclicals",
        "Healthcare",
        "Industrials",
        "Infrastructures",
        "Technology",
    ]

    symbols = []
    # Dedicated edge cases
    symbols.append("FINA")  # Financials sector, null der_mrq
    symbols.append("NOFF")  # No foreign flow records
    symbols.append("SUSP")  # Suspended stock
    symbols.append("MISF")  # Missing fundamentals (None/nulls)

    # Fill remaining up to 45
    for i in range(5, 46):
        symbols.append(f"STK{i:02d}")

    companies_rows = []
    for sym in symbols:
        if sym == "FINA":
            sec = "Financials"
            sub = "Banks"
            der = None
            roe = 0.18
            npm = 0.25
            pe = 12.5
            pb = 2.1
            yield_ttm = 0.045
        elif sym == "MISF":
            sec = "Technology"
            sub = "Software"
            der = None
            roe = None
            npm = None
            pe = None
            pb = None
            yield_ttm = None
        elif sym == "SUSP":
            sec = "Industrials"
            sub = "Heavy Machinery"
            der = 1.2
            roe = -0.05
            npm = -0.02
            pe = -8.0
            pb = 0.8
            yield_ttm = None
        else:
            sec = rng.choice(sectors)
            sub = f"{sec} General"
            der = None if sec == "Financials" else round(rng.uniform(0.2, 2.5), 2)
            roe = round(rng.uniform(0.02, 0.35), 4)
            npm = round(rng.uniform(0.01, 0.30), 4)
            pe = round(rng.uniform(5.0, 35.0), 2)
            pb = round(rng.uniform(0.8, 5.0), 2)
            yield_ttm = round(rng.uniform(0.01, 0.08), 4) if rng.random() > 0.1 else None

        last_close = rng.choice([500, 1200, 2500, 4800, 9100, 15000])
        mcap = last_close * rng.randint(5_000_000_000, 50_000_000_000)
        earn_growth = round(rng.uniform(-0.3, 0.5), 4) if sym != "MISF" else None
        rev_growth = round(rng.uniform(-0.2, 0.4), 4) if sym != "MISF" else None
        pe_peer = round(rng.uniform(10.0, 25.0), 2) if pe else None
        pb_peer = round(rng.uniform(1.2, 3.5), 2) if pb else None

        companies_rows.append(
            (
                sym,
                f"Company {sym} Tbk",
                sec,
                sub,
                float(mcap),
                float(last_close),
                roe,
                npm,
                der,
                earn_growth,
                rev_growth,
                pe,
                pb,
                pe_peer,
                pb_peer,
                yield_ttm,
                json.dumps({"symbol": sym, "synthetic": True}),
            )
        )

    conn.executemany(
        """
        INSERT INTO companies (
            symbol, name, sector, sub_sector, market_cap, last_close,
            roe_ttm, net_profit_margin, der_mrq, yoy_quarter_earnings_growth,
            yoy_quarter_revenue_growth, pe_ttm, pb_mrq, pe_peer_avg, pb_peer_avg,
            yield_ttm, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        companies_rows,
    )

    # 3. Prices & Foreign Flow over 90 trading days
    prices_rows = []
    flow_rows = []

    for sym in symbols:
        price = rng.choice([500.0, 1500.0, 3000.0, 8500.0])
        shares = rng.randint(2_000_000_000, 20_000_000_000)

        for d in trading_dates:
            # Price walk
            ret = rng.gauss(0.0005, 0.02)
            price = max(50.0, round(price * (1 + ret), 2))
            vol = rng.randint(1_000_000, 80_000_000)
            mcap = price * shares
            prices_rows.append((sym, d, price, float(vol), float(mcap)))

            # Foreign flow: NOFF has no foreign flow rows
            if sym != "NOFF":
                f_buy = float(rng.randint(500_000_000, 50_000_000_000))
                f_sell = float(rng.randint(500_000_000, 50_000_000_000))
                net_f = f_buy - f_sell
                f_share = round(rng.uniform(0.1, 0.6), 4)
                flow_rows.append((sym, d, net_f, f_buy, f_sell, f_share))

    conn.executemany(
        "INSERT INTO prices (symbol, date, close, volume, market_cap) VALUES (?, ?, ?, ?, ?)",
        prices_rows,
    )
    conn.executemany(
        """
        INSERT INTO foreign_flow (
            symbol, date, net_foreign_inflow, foreign_buy_idr, foreign_sell_idr, foreign_share
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        flow_rows,
    )

    # 4. Broker Summary (last 10 trading days)
    broker_dates = trading_dates[-10:]
    broker_codes = [b[0] for b in brokers_data]
    bs_rows = []

    for sym in symbols:
        for d in broker_dates:
            # Active brokers for this day
            active = rng.sample(broker_codes, k=min(len(broker_codes), 8))
            for bcode in active:
                bval = float(rng.randint(100_000_000, 10_000_000_000))
                sval = float(rng.randint(100_000_000, 10_000_000_000))
                nval = bval - sval
                blot = float(rng.randint(1_000, 100_000))
                slot = float(rng.randint(1_000, 100_000))
                nlot = blot - slot
                bavg = round(bval / (blot * 100), 2) if blot > 0 else 0.0
                savg = round(sval / (slot * 100), 2) if slot > 0 else 0.0

                # Edge case: null f_bval / f_sval in 70% of rows
                if rng.random() < 0.70:
                    f_bval = None
                    f_sval = None
                else:
                    f_bval = round(bval * rng.uniform(0.1, 0.9), 2)
                    f_sval = round(sval * rng.uniform(0.1, 0.9), 2)

                bs_rows.append(
                    (
                        sym,
                        d,
                        bcode,
                        bval,
                        sval,
                        nval,
                        blot,
                        slot,
                        nlot,
                        bavg,
                        savg,
                        f_bval,
                        f_sval,
                    )
                )

    conn.executemany(
        """
        INSERT INTO broker_summary (
            symbol, date, broker_code, bval, sval, nval, blot, slot, nlot,
            bavg_per_share, savg_per_share, f_bval, f_sval
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        bs_rows,
    )

    # 5. Holder Mix (9 monthly snapshots in 2026)
    holder_rows = []
    holder_months = [
        "2026-01-31",
        "2026-02-28",
        "2026-03-31",
        "2026-04-30",
        "2026-05-31",
        "2026-06-30",
        "2026-07-31",
        "2026-08-31",
        "2026-09-30",
    ]
    for sym in symbols:
        tot_shares = float(rng.randint(5_000_000_000, 25_000_000_000))
        for m in holder_months:
            indiv_l = tot_shares * rng.uniform(0.08, 0.20)
            indiv_f = tot_shares * rng.uniform(0.01, 0.05)
            tot_l = tot_shares * rng.uniform(0.40, 0.65)
            tot_f = tot_shares - tot_l
            holder_rows.append(
                (
                    sym,
                    m,
                    tot_shares,
                    round(indiv_l),
                    round(indiv_f),
                    round(tot_l),
                    round(tot_f),
                    None,  # numbers_of_shareholders is null in real data
                    json.dumps({"symbol": sym, "snapshot": m}),
                )
            )

    conn.executemany(
        """
        INSERT INTO holder_mix (
            symbol, date, shares_number, individual_l, individual_f,
            total_l, total_f, numbers_of_shareholders, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        holder_rows,
    )

    # 6. Filings
    filing_rows = []
    filing_id = 1
    for sym in ["FINA", "STK05", "STK10", "STK15"]:
        for fdate in ["2026-09-10", "2026-09-22", "2026-09-29"]:
            ttype = rng.choice(["buy", "sell"])
            htype = "insider"
            ts = f"{fdate}T10:15:30"
            raw = {
                "holder_name": f"Director of {sym}",
                "amount_transaction": rng.randint(100_000, 5_000_000),
                "transaction_value": rng.randint(500_000_000, 10_000_000_000),
                "transaction_type": ttype,
                "holder_type": htype,
            }
            filing_rows.append((str(filing_id), sym, ts, ttype, htype, json.dumps(raw)))
            filing_id += 1

    conn.executemany(
        """
        INSERT INTO filings (
            id, symbol, timestamp, transaction_type, holder_type, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        filing_rows,
    )

    # 7. Corporate Actions & Suspensions
    conn.execute(
        """
        INSERT INTO corporate_actions (symbol, type, key_date, raw_json)
        VALUES (?, ?, ?, ?)
        """,
        ("FINA", "dividend", "2026-10-08", json.dumps({"amount": 150.0, "type": "dividend"})),
    )

    conn.execute(
        """
        INSERT INTO suspensions (symbol, date, reason, pdf_url)
        VALUES (?, ?, ?, ?)
        """,
        ("SUSP", "2026-09-15", "Unusual market activity spike", "https://example.com/susp.pdf"),
    )

    conn.commit()
    conn.close()
    return target


if __name__ == "__main__":
    out = generate()
    print(f"Generated synthetic database at {out}")
