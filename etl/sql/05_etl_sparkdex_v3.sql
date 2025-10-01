\set ON_ERROR_STOP on
BEGIN;

-- Swaps
DELETE FROM core.sparkdex_v3_swaps
 WHERE chain_id = :CHAIN_ID AND block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK;

INSERT INTO core.sparkdex_v3_swaps (
  chain_id, block_number, block_time, tx_hash, log_index,
  pool_address, sender, recipient,
  amount0, amount1, sqrt_price_x96, liquidity, tick_after
)
SELECT
  :CHAIN_ID, e.block_number, e.block_time, e.tx_hash, e.log_index,
  lower(e.contract_address),
  lower(args->>'sender'),
  lower(args->>'recipient'),
  (args->>'amount0')::numeric,
  (args->>'amount1')::numeric,
  (args->>'sqrtPriceX96')::numeric,
  (args->>'liquidity')::numeric,
  (args->>'tick')::int
FROM stage.decoded_events e
WHERE e.chain_id      = :CHAIN_ID
  AND e.block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK
  AND e.event_name    = 'Swap'
  AND e.removed IS NOT TRUE
ON CONFLICT (chain_id, block_number, tx_hash, log_index) DO UPDATE
SET block_time = EXCLUDED.block_time,
    amount0    = EXCLUDED.amount0,
    amount1    = EXCLUDED.amount1,
    sqrt_price_x96 = EXCLUDED.sqrt_price_x96,
    liquidity  = EXCLUDED.liquidity,
    tick_after = EXCLUDED.tick_after;

-- Liquidity (Mint/Burn/Collect)
DELETE FROM core.sparkdex_v3_liquidity
 WHERE chain_id = :CHAIN_ID AND block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK;

WITH liq AS (
  SELECT e.*, e.event_name AS ev
  FROM stage.decoded_events e
  WHERE e.chain_id = :CHAIN_ID
    AND e.block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK
    AND e.event_name IN ('Mint','Burn','Collect')
    AND e.removed IS NOT TRUE
)
INSERT INTO core.sparkdex_v3_liquidity (
  chain_id, block_number, block_time, tx_hash, log_index,
  pool_address, owner, event_type, tick_lower, tick_upper,
  liquidity_delta, amount0, amount1, fees0, fees1
)
SELECT
  :CHAIN_ID, block_number, block_time, tx_hash, log_index,
  lower(contract_address),
  lower(COALESCE(args->>'owner', args->>'sender')),
  CASE ev WHEN 'Mint' THEN 'MINT' WHEN 'Burn' THEN 'BURN' ELSE 'COLLECT' END,
  (args->>'tickLower')::int,
  (args->>'tickUpper')::int,
  CASE WHEN ev='Mint' THEN (args->>'amount')::numeric
       WHEN ev='Burn' THEN -1 * (args->>'amount')::numeric
       ELSE NULL END,
  (args->>'amount0')::numeric,
  (args->>'amount1')::numeric,
  (args->>'amount0')::numeric FILTER (WHERE ev='Collect'),
  (args->>'amount1')::numeric FILTER (WHERE ev='Collect')
FROM liq
ON CONFLICT (chain_id, block_number, tx_hash, log_index) DO UPDATE
SET block_time = EXCLUDED.block_time,
    event_type = EXCLUDED.event_type,
    liquidity_delta = EXCLUDED.liquidity_delta,
    amount0 = EXCLUDED.amount0,
    amount1 = EXCLUDED.amount1,
    fees0   = EXCLUDED.fees0,
    fees1   = EXCLUDED.fees1;

COMMIT;