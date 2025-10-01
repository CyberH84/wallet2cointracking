\set ON_ERROR_STOP on
BEGIN;

-- Stage table that your FTSO reader fills (chain_id=14, feed_id_hex, block_number/time, value_wei, decimals)
CREATE TABLE IF NOT EXISTS stage.ftso_updates (
  chain_id     INTEGER,
  block_number BIGINT,
  block_time   TIMESTAMPTZ,
  feed_id_hex  TEXT,
  value_wei    NUMERIC,
  decimals     INT
);

-- Upsert to core (normalize to decimals)
INSERT INTO core.flare_ftso_feed_values (
  chain_id, block_number, block_time, feed_id_hex, value, raw_value_wei
)
SELECT
  u.chain_id, u.block_number, u.block_time, u.feed_id_hex,
  (u.value_wei / power(10::numeric, COALESCE(u.decimals, 18)))::numeric(38,18),
  u.value_wei
FROM stage.ftso_updates u
WHERE u.chain_id = :CHAIN_ID
  AND u.block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK
ON CONFLICT (chain_id, block_number, feed_id_hex) DO UPDATE
SET block_time   = EXCLUDED.block_time,
    value        = EXCLUDED.value,
    raw_value_wei= EXCLUDED.raw_value_wei;

