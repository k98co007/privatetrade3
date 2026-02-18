SCHEMA_VERSION = 1

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_events (
  event_id TEXT PRIMARY KEY,
  trading_date TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  symbol TEXT NOT NULL,
  event_type TEXT NOT NULL,
  base_price NUMERIC NULL,
  local_low NUMERIC NULL,
  current_price NUMERIC NULL,
  payload_json TEXT NULL
);
CREATE INDEX IF NOT EXISTS idx_strategy_events_date_symbol
ON strategy_events(trading_date, symbol, occurred_at);

CREATE TABLE IF NOT EXISTS order_events (
  event_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  trading_date TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  order_type TEXT NOT NULL,
  order_price NUMERIC NOT NULL,
  quantity INTEGER NOT NULL,
  status TEXT NOT NULL,
  client_order_key TEXT NOT NULL,
  reason_code TEXT NULL,
  reason_message TEXT NULL,
  UNIQUE(order_id, status, occurred_at)
);

CREATE TABLE IF NOT EXISTS execution_events (
  event_id TEXT PRIMARY KEY,
  execution_id TEXT NOT NULL UNIQUE,
  order_id TEXT NOT NULL,
  trading_date TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  execution_price NUMERIC NOT NULL,
  execution_qty INTEGER NOT NULL,
  cum_qty INTEGER NOT NULL,
  remaining_qty INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS position_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  saved_at TEXT NOT NULL,
  trading_date TEXT NOT NULL,
  symbol TEXT NOT NULL,
  avg_buy_price NUMERIC NOT NULL,
  quantity INTEGER NOT NULL,
  current_profit_rate NUMERIC NOT NULL,
  max_profit_rate NUMERIC NOT NULL,
  min_profit_locked INTEGER NOT NULL,
  last_order_id TEXT NULL,
  state_version INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_position_snapshots_date_savedat
ON position_snapshots(trading_date, saved_at DESC);

CREATE TABLE IF NOT EXISTS daily_reports (
  trading_date TEXT PRIMARY KEY,
  total_buy_amount NUMERIC NOT NULL,
  total_sell_amount NUMERIC NOT NULL,
  total_sell_tax NUMERIC NOT NULL,
  total_sell_fee NUMERIC NOT NULL,
  total_net_pnl NUMERIC NOT NULL,
  total_return_rate NUMERIC NOT NULL,
  generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trade_details (
  id TEXT PRIMARY KEY,
  trading_date TEXT NOT NULL,
  symbol TEXT NOT NULL,
  buy_executed_at TEXT NOT NULL,
  sell_executed_at TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  buy_price NUMERIC NOT NULL,
  sell_price NUMERIC NOT NULL,
  buy_amount NUMERIC NOT NULL,
  sell_amount NUMERIC NOT NULL,
  sell_tax NUMERIC NOT NULL,
  sell_fee NUMERIC NOT NULL,
  net_pnl NUMERIC NOT NULL,
  return_rate NUMERIC NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trade_details_date_symbol
ON trade_details(trading_date, symbol);
"""
