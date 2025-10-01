-- Layered namespaces
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS stage;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS marts;

-- Common dimensions
CREATE TABLE IF NOT EXISTS core.dim_chain (
  chain_id      INTEGER PRIMARY KEY,
  chain_name    TEXT NOT NULL,
  native_symbol TEXT NOT NULL,
  explorer_url  TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.dim_token (
  chain_id      INTEGER NOT NULL REFERENCES core.dim_chain(chain_id),
  token_address TEXT    NOT NULL,
  symbol        TEXT    NOT NULL,
  name          TEXT,
  decimals      INTEGER NOT NULL,
  is_stablecoin BOOLEAN DEFAULT FALSE,
  PRIMARY KEY (chain_id, token_address)
);

CREATE TABLE IF NOT EXISTS core.contracts (
  chain_id      INTEGER NOT NULL REFERENCES core.dim_chain(chain_id),
  address       TEXT    NOT NULL,
  protocol      TEXT    NOT NULL,
  component     TEXT    NOT NULL,
  version       TEXT,
  start_block   BIGINT,
  end_block     BIGINT,
  meta          JSONB,
  PRIMARY KEY (chain_id, address)
);

CREATE TABLE IF NOT EXISTS core.blocks (
  chain_id     INTEGER NOT NULL REFERENCES core.dim_chain(chain_id),
  block_number BIGINT  NOT NULL,
  block_hash   TEXT    NOT NULL,
  block_time   TIMESTAMPTZ NOT NULL,
  parent_hash  TEXT,
  PRIMARY KEY (chain_id, block_number)
);

-- Protocol tables (subset shown; the rest created as part of ETLs if not exists)
-- OpenOcean swaps + route legs
CREATE TABLE IF NOT EXISTS core.openocean_swaps (
  chain_id INTEGER NOT NULL REFERENCES core.dim_chain(chain_id),
  block_number BIGINT NOT NULL,
  block_time   TIMESTAMPTZ NOT NULL,
  tx_hash TEXT NOT NULL,
  log_index INTEGER NOT NULL,
  aggregator_addr TEXT NOT NULL,
  user_addr TEXT,
  src_token TEXT NOT NULL,
  dst_token TEXT NOT NULL,
  amount_in_raw  NUMERIC(78,0),
  amount_out_raw NUMERIC(78,0),
  amount_in  NUMERIC(38,18),
  amount_out NUMERIC(38,18),
  slippage_bps INTEGER,
  fee_amount_raw NUMERIC(78,0),
  fee_token TEXT,
  recipient TEXT,
  route_id TEXT,
  PRIMARY KEY (chain_id, block_number, tx_hash, log_index)
);
CREATE INDEX IF NOT EXISTS idx_oosw_time ON core.openocean_swaps (chain_id, block_time);

CREATE TABLE IF NOT EXISTS core.openocean_route_legs (
  chain_id INTEGER NOT NULL REFERENCES core.dim_chain(chain_id),
  block_number BIGINT NOT NULL,
  tx_hash TEXT NOT NULL,
  parent_log_index INTEGER NOT NULL,
  seq INTEGER NOT NULL,
  dex_name TEXT,
  pool_address TEXT,
  token_in TEXT NOT NULL,
  token_out TEXT NOT NULL,
  amount_in_raw  NUMERIC(78,0),
  amount_out_raw NUMERIC(78,0),
  amount_in  NUMERIC(38,18),
  amount_out NUMERIC(38,18),
  fee_bps INTEGER,
  PRIMARY KEY (chain_id, block_number, tx_hash, parent_log_index, seq),
  FOREIGN KEY (chain_id, block_number, tx_hash, parent_log_index)
    REFERENCES core.openocean_swaps(chain_id, block_number, tx_hash, log_index)
);

-- SparkDEX v3
CREATE TABLE IF NOT EXISTS core.sparkdex_v3_pools (
  chain_id INTEGER NOT NULL REFERENCES core.dim_chain(chain_id),
  pool_address TEXT NOT NULL,
  token0 TEXT NOT NULL,
  token1 TEXT NOT NULL,
  fee_tier INTEGER NOT NULL,
  tick_spacing INTEGER NOT NULL,
  created_block BIGINT,
  PRIMARY KEY (chain_id, pool_address)
);

CREATE TABLE IF NOT EXISTS core.sparkdex_v3_swaps (
  chain_id INTEGER NOT NULL REFERENCES core.dim_chain(chain_id),
  block_number BIGINT NOT NULL,
  block_time TIMESTAMPTZ NOT NULL,
  tx_hash TEXT NOT NULL,
  log_index INTEGER NOT NULL,
  pool_address TEXT NOT NULL,
  sender TEXT,
  recipient TEXT,
  amount0 NUMERIC(78,0) NOT NULL,
  amount1 NUMERIC(78,0) NOT NULL,
  sqrt_price_x96 NUMERIC(78,0) NOT NULL,
  liquidity NUMERIC(78,0) NOT NULL,
  tick_after INTEGER NOT NULL,
  PRIMARY KEY (chain_id, block_number, tx_hash, log_index)
);

CREATE TABLE IF NOT EXISTS core.sparkdex_v3_liquidity (
  chain_id INTEGER NOT NULL REFERENCES core.dim_chain(chain_id),
  block_number BIGINT NOT NULL,
  block_time TIMESTAMPTZ NOT NULL,
  tx_hash TEXT NOT NULL,
  log_index INTEGER NOT NULL,
  pool_address TEXT NOT NULL,
  owner TEXT,
  event_type TEXT NOT NULL CHECK (event_type IN ('MINT','BURN','COLLECT')),
  tick_lower INTEGER,
  tick_upper INTEGER,
  liquidity_delta NUMERIC(78,0),
  amount0 NUMERIC(78,0),
  amount1 NUMERIC(78,0),
  fees0 NUMERIC(78,0),
  fees1 NUMERIC(78,0),
  PRIMARY KEY (chain_id, block_number, tx_hash, log_index)
);

-- Aave v3
CREATE TABLE IF NOT EXISTS core.aave_v3_reserve_indices (
  chain_id INTEGER NOT NULL,
  block_number BIGINT NOT NULL,
  block_time TIMESTAMPTZ NOT NULL,
  reserve_address TEXT NOT NULL,
  liquidity_index_ray NUMERIC(78,0),
  variable_borrow_index_ray NUMERIC(78,0),
  liquidity_rate_ray NUMERIC(78,0),
  variable_borrow_rate_ray NUMERIC(78,0),
  PRIMARY KEY (chain_id, block_number, reserve_address)
);

CREATE TABLE IF NOT EXISTS core.aave_v3_events (
  chain_id INTEGER NOT NULL,
  block_number BIGINT NOT NULL,
  block_time TIMESTAMPTZ NOT NULL,
  tx_hash TEXT NOT NULL,
  log_index INTEGER NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('SUPPLY','WITHDRAW','BORROW','REPAY','LIQUIDATION_CALL','FLASHLOAN')),
  user_address TEXT NOT NULL,
  reserve_address TEXT NOT NULL,
  amount_raw NUMERIC(78,0),
  amount NUMERIC(38,18),
  interest_rate_mode TEXT,
  debt_to_cover_raw NUMERIC(78,0),
  collateral_asset TEXT,
  liquidator TEXT,
  PRIMARY KEY (chain_id, block_number, tx_hash, log_index)
);

-- Kinetic (Flare lending)
CREATE TABLE IF NOT EXISTS core.kinetic_events (
  chain_id INTEGER NOT NULL,
  block_number BIGINT NOT NULL,
  block_time TIMESTAMPTZ NOT NULL,
  tx_hash TEXT NOT NULL,
  log_index INTEGER NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('DEPOSIT','WITHDRAW','BORROW','REPAY','LIQUIDATE')),
  user_address TEXT NOT NULL,
  reserve_address TEXT NOT NULL,
  amount_raw NUMERIC(78,0),
  amount NUMERIC(38,18),
  liquidator TEXT,
  collateral_asset TEXT,
  PRIMARY KEY (chain_id, block_number, tx_hash, log_index)
);

-- PancakeSwap v2-style
CREATE TABLE IF NOT EXISTS core.pancakeswap_pairs (
  chain_id INTEGER NOT NULL REFERENCES core.dim_chain(chain_id),
  pair_address TEXT NOT NULL,
  token0 TEXT NOT NULL,
  token1 TEXT NOT NULL,
  created_block BIGINT,
  PRIMARY KEY (chain_id, pair_address)
);

CREATE TABLE IF NOT EXISTS core.pancakeswap_swaps (
  chain_id INTEGER NOT NULL,
  block_number BIGINT NOT NULL,
  block_time TIMESTAMPTZ NOT NULL,
  tx_hash TEXT NOT NULL,
  log_index INTEGER NOT NULL,
  pair_address TEXT NOT NULL,
  sender TEXT,
  to_address TEXT,
  amount0_in NUMERIC(78,0) NOT NULL,
  amount1_in NUMERIC(78,0) NOT NULL,
  amount0_out NUMERIC(78,0) NOT NULL,
  amount1_out NUMERIC(78,0) NOT NULL,
  PRIMARY KEY (chain_id, block_number, tx_hash, log_index)
);

CREATE TABLE IF NOT EXISTS core.pancakeswap_liquidity (
  chain_id INTEGER NOT NULL,
  block_number BIGINT NOT NULL,
  block_time TIMESTAMPTZ NOT NULL,
  tx_hash TEXT NOT NULL,
  log_index INTEGER NOT NULL,
  pair_address TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('MINT','BURN')),
  amount0 NUMERIC(78,0) NOT NULL,
  amount1 NUMERIC(78,0) NOT NULL,
  to_from TEXT,
  PRIMARY KEY (chain_id, block_number, tx_hash, log_index)
);

CREATE TABLE IF NOT EXISTS core.pancakeswap_syncs (
  chain_id INTEGER NOT NULL,
  block_number BIGINT NOT NULL,
  block_time TIMESTAMPTZ NOT NULL,
  tx_hash TEXT NOT NULL,
  log_index INTEGER NOT NULL,
  pair_address TEXT NOT NULL,
  reserve0 NUMERIC(78,0) NOT NULL,
  reserve1 NUMERIC(78,0) NOT NULL,
  PRIMARY KEY (chain_id, block_number, tx_hash, log_index)
);

-- Flare FTSOv2
CREATE TABLE IF NOT EXISTS core.flare_ftso_feeds (
  feed_id_hex TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  category    TEXT NOT NULL,
  risk_level  TEXT,
  decimals_hint INTEGER
);

CREATE TABLE IF NOT EXISTS core.flare_ftso_feed_values (
  chain_id INTEGER NOT NULL REFERENCES core.dim_chain(chain_id),
  block_number BIGINT NOT NULL,
  block_time   TIMESTAMPTZ NOT NULL,
  feed_id_hex  TEXT NOT NULL REFERENCES core.flare_ftso_feeds(feed_id_hex),
  value        NUMERIC(38,18) NOT NULL,
  raw_value_wei NUMERIC(78,0),
  PRIMARY KEY (chain_id, block_number, feed_id_hex)
);
CREATE INDEX IF NOT EXISTS idx_ftso_feed_time ON core.flare_ftso_feed_values (chain_id, feed_id_hex, block_time);