-- Database contract between ingest (agent A) and the signal modules (agents B, C).
-- Dates are YYYY-MM-DD text, symbols have no .JK suffix, money is IDR.

CREATE TABLE IF NOT EXISTS companies (
    symbol                       TEXT PRIMARY KEY,
    name                         TEXT,
    sector                       TEXT,
    sub_sector                   TEXT,
    market_cap                   REAL,
    last_close                   REAL,
    roe_ttm                      REAL,
    net_profit_margin            REAL,
    der_mrq                      REAL,
    yoy_quarter_earnings_growth  REAL,
    yoy_quarter_revenue_growth   REAL,
    pe_ttm                       REAL,
    pb_mrq                       REAL,
    pe_peer_avg                  REAL,
    pb_peer_avg                  REAL,
    yield_ttm                    REAL,
    raw_json                     TEXT
);

CREATE TABLE IF NOT EXISTS prices (
    symbol      TEXT NOT NULL,
    date        TEXT NOT NULL,
    close       REAL,
    volume      REAL,
    market_cap  REAL,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS foreign_flow (
    symbol              TEXT NOT NULL,
    date                TEXT NOT NULL,
    net_foreign_inflow  REAL,
    foreign_buy_idr     REAL,
    foreign_sell_idr    REAL,
    foreign_share       REAL,
    PRIMARY KEY (symbol, date)
);

-- f_bval / f_sval are NULL when the broker had no foreign-investor trades that day.
CREATE TABLE IF NOT EXISTS broker_summary (
    symbol          TEXT NOT NULL,
    date            TEXT NOT NULL,
    broker_code     TEXT NOT NULL,
    bval            REAL,
    sval            REAL,
    nval            REAL,
    blot            REAL,
    slot            REAL,
    nlot            REAL,
    bavg_per_share  REAL,
    savg_per_share  REAL,
    f_bval          REAL,
    f_sval          REAL,
    PRIMARY KEY (symbol, date, broker_code)
);

-- cohort: retail / mixed / institutional / unknown
CREATE TABLE IF NOT EXISTS brokers (
    code        TEXT PRIMARY KEY,
    name        TEXT,
    is_foreign  INTEGER,
    cohort      TEXT
);

-- Monthly snapshots. *_l = local holders, *_f = foreign holders, in shares.
CREATE TABLE IF NOT EXISTS holder_mix (
    symbol                  TEXT NOT NULL,
    date                    TEXT NOT NULL,
    shares_number           REAL,
    individual_l            REAL,
    individual_f            REAL,
    total_l                 REAL,
    total_f                 REAL,
    numbers_of_shareholders REAL,
    raw_json                TEXT,
    PRIMARY KEY (symbol, date)
);

-- transaction_type: buy / sell / others. Other fields live in raw_json.
CREATE TABLE IF NOT EXISTS filings (
    id                TEXT PRIMARY KEY,
    symbol            TEXT,
    timestamp         TEXT,
    transaction_type  TEXT,
    holder_type       TEXT,
    raw_json          TEXT
);

-- type: dividend / upcoming_dividend / bonus / right_issue / stock_split / warrant / agm
CREATE TABLE IF NOT EXISTS corporate_actions (
    symbol    TEXT NOT NULL,
    type      TEXT NOT NULL,
    key_date  TEXT NOT NULL,
    raw_json  TEXT,
    PRIMARY KEY (symbol, type, key_date)
);

CREATE TABLE IF NOT EXISTS suspensions (
    symbol   TEXT NOT NULL,
    date     TEXT NOT NULL,
    reason   TEXT,
    pdf_url  TEXT,
    PRIMARY KEY (symbol, date)
);

-- Credit ledger: one row per request, including cache hits (credits = 0).
CREATE TABLE IF NOT EXISTS api_calls (
    ts          TEXT NOT NULL,
    url         TEXT NOT NULL,
    status      INTEGER,
    credits     INTEGER NOT NULL DEFAULT 0,
    from_cache  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_prices_date ON prices (date);
CREATE INDEX IF NOT EXISTS idx_foreign_flow_date ON foreign_flow (date);
CREATE INDEX IF NOT EXISTS idx_broker_summary_symbol_date ON broker_summary (symbol, date);
CREATE INDEX IF NOT EXISTS idx_filings_symbol_ts ON filings (symbol, timestamp);
