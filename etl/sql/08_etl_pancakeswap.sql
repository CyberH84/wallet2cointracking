\set ON_ERROR_STOP on
BEGIN;

-- Pairs (if you seed FACTORY)
WITH factory AS (
  SELECT address
  FROM core.contracts
  WHERE chain_id = :CHAIN_ID AND protocol = 'PANCAKESWAP' AND component = 'FACTORY'
),
pairs AS (
  SELECT e.*
  FROM stage.decoded_events e
  JOIN factory f ON f.address = e.contract_address
  WHERE e.chain_id = :CHAIN_ID
    AND e.block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK
    AND e.event_name = 'PairCreated'
    AND e.removed IS NOT TRUE
)
INSERT INTO core.pancakeswap_pairs (chain_id, pair_address, token0, token1, created_block)
SELECT :CHAIN_ID, lower(args->>'pair'), lower(args->>'token0'), lower(args->>'token1'), block_number
FROM pairs
ON CONFLICT (chain_id, pair_address) DO UPDATE
SET token0 = EXCLUDED.token0, token1 = EXCLUDED.token1;

-- Swaps
DELETE FROM core.pancakeswap_swaps
 WHERE chain_id = :CHAIN_ID AND block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK;

INSERT INTO core.pancakeswap_swaps (
  chain_id, block_number, block_time, tx_hash, log_index,
  pair_address, sender, to_address,
  amount0_in, amount1_in, amount0_out, amount1_out
)
SELECT
  :CHAIN_ID, e.block_number, e.block_time, e.tx_hash, e.log_index,
  lower(e.contract_address),
  lower(args->>'sender'),
  lower(args->>'to'),
  (args->>'amount0In')::numeric,  (args->>'amount1In')::numeric,
  (args->>'amount0Out')::numeric, (args->>'amount1Out')::numeric
FROM stage.decoded_events e
WHERE e.chain_id = :CHAIN_ID
  AND e.block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK
  AND e.event_name = 'Swap'
  AND e.removed IS NOT TRUE
ON CONFLICT (chain_id, block_number, tx_hash, log_index) DO UPDATE
SET block_time = EXCLUDED.block_time,
    amount0_in  = EXCLUDED.amount0_in,
    amount1_in  = EXCLUDED.amount1_in,
    amount0_out = EXCLUDED.amount0_out,
    amount1_out = EXCLUDED.amount1_out;

-- Liquidity: Mint/Burn
DELETE FROM core.pancakeswap_liquidity
 WHERE chain_id = :CHAIN_ID AND block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK;

WITH liq AS (
  SELECT e.*, e.event_name ev
  FROM stage.decoded_events e
  WHERE e.chain_id = :CHAIN_ID
    AND e.block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK
    AND e.event_name IN ('Mint','Burn')
    AND e.removed IS NOT TRUE
)
INSERT INTO core.pancakeswap_liquidity (
  chain_id, block_number, block_time, tx_hash, log_index,
  pair_address, event_type, amount0, amount1, to_from
)
SELECT
  :CHAIN_ID, block_number, block_time, tx_hash, log_index,
  lower(contract_address),
  CASE ev WHEN 'Mint' THEN 'MINT' ELSE 'BURN' END,
  (args->>'amount0')::numeric, (args->>'amount1')::numeric,
  lower(COALESCE(args->>'to', args->>'sender'))
FROM liq
ON CONFLICT (chain_id, block_number, tx_hash, log_index) DO UPDATE
SET block_time = EXCLUDED.block_time,
    event_type = EXCLUDED.event_type,
    amount0    = EXCLUDED.amount0,
    amount1    = EXCLUDED.amount1;

-- Sync
DELETE FROM core.pancakeswap_syncs
 WHERE chain_id = :CHAIN_ID AND block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK;

INSERT INTO core.pancakeswap_syncs (
  chain_id, block_number, block_time, tx_hash, log_index,
  pair_address, reserve0, reserve1
)
SELECT
  :CHAIN_ID, block_number, block_time, tx_hash, log_index,
  lower(contract_address),
  (args->>'reserve0')::numeric, (args->>'reserve1')::numeric
FROM stage.decoded_events
WHERE chain_id = :CHAIN_ID
  AND block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK
  AND event_name = 'Sync'
  AND removed IS NOT TRUE
ON CONFLICT (chain_id, block_number, tx_hash, log_index) DO UPDATE
SET block_time = EXCLUDED.block_time,
    reserve0   = EXCLUDED.reserve0,
    reserve1   = EXCLUDED.reserve1;

COMMIT;
