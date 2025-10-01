\set ON_ERROR_STOP on
BEGIN;

-- Purge window
DELETE FROM core.openocean_route_legs
 WHERE chain_id = :CHAIN_ID AND block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK;
DELETE FROM core.openocean_swaps
 WHERE chain_id = :CHAIN_ID AND block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK;

WITH oo_contracts AS (
  SELECT address
  FROM core.contracts
  WHERE chain_id = :CHAIN_ID
    AND protocol = 'OPENOCEAN'
    AND component IN ('ROUTER','AGGREGATOR')
),
src AS (
  SELECT e.*
  FROM stage.decoded_events e
  JOIN oo_contracts c ON c.address = e.contract_address
  WHERE e.chain_id = :CHAIN_ID
    AND e.block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK
    AND e.removed IS NOT TRUE
    AND e.event_name IN ('Swap','Swapped','OrderExecuted','RouteExecuted')
)
INSERT INTO core.openocean_swaps (
  chain_id, block_number, block_time, tx_hash, log_index,
  aggregator_addr, user_addr,
  src_token, dst_token,
  amount_in_raw, amount_out_raw,
  amount_in, amount_out,
  slippage_bps, fee_amount_raw, fee_token, recipient, route_id
)
SELECT
  :CHAIN_ID, block_number, block_time, tx_hash, log_index,
  contract_address,
  lower(COALESCE(NULLIF(args->>'sender',''), NULLIF(args->>'trader',''), NULLIF(args->>'user',''))),
  lower(COALESCE(args->>'fromToken', args->>'srcToken', args->>'tokenIn')),
  lower(COALESCE(args->>'toToken',   args->>'dstToken', args->>'tokenOut')),
  COALESCE( (args->>'amountIn')::numeric,  (args->>'amount')::numeric, 0 ),
  COALESCE( (args->>'amountOut')::numeric, (args->>'returnAmount')::numeric, 0 ),
  NULL, NULL,
  (args->>'slippageBps')::int,
  (args->>'feeAmount')::numeric,
  lower(args->>'feeToken'),
  lower(COALESCE(args->>'recipient', args->>'to')),
  args->>'routeId'
FROM src
ON CONFLICT (chain_id, block_number, tx_hash, log_index) DO UPDATE
SET block_time = EXCLUDED.block_time,
    aggregator_addr = EXCLUDED.aggregator_addr,
    user_addr       = EXCLUDED.user_addr,
    src_token       = EXCLUDED.src_token,
    dst_token       = EXCLUDED.dst_token,
    amount_in_raw   = EXCLUDED.amount_in_raw,
    amount_out_raw  = EXCLUDED.amount_out_raw,
    slippage_bps    = EXCLUDED.slippage_bps,
    fee_amount_raw  = EXCLUDED.fee_amount_raw,
    fee_token       = EXCLUDED.fee_token,
    recipient       = EXCLUDED.recipient,
    route_id        = EXCLUDED.route_id;

-- Optional: per-hop legs when available as array args
WITH legs AS (
  SELECT e.*, COALESCE(args->'routes', args->'hops', args->'path') AS route_arr
  FROM stage.decoded_events e
  JOIN oo_contracts c ON c.address = e.contract_address
  WHERE e.chain_id = :CHAIN_ID
    AND e.block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK
    AND e.removed IS NOT TRUE
    AND route_arr IS NOT NULL
)
INSERT INTO core.openocean_route_legs (
  chain_id, block_number, tx_hash, parent_log_index, seq,
  dex_name, pool_address, token_in, token_out,
  amount_in_raw, amount_out_raw, amount_in, amount_out, fee_bps
)
SELECT
  :CHAIN_ID, l.block_number, l.tx_hash, l.log_index,
  COALESCE((elem->>'index')::int, ord.seq) AS seq,
  elem->>'dex',
  lower(elem->>'pool'),
  lower(COALESCE(elem->>'tokenIn',  elem->>'srcToken')),
  lower(COALESCE(elem->>'tokenOut', elem->>'dstToken')),
  (elem->>'amountIn')::numeric,
  (elem->>'amountOut')::numeric,
  NULL, NULL,
  (elem->>'feeBps')::int
FROM legs l
CROSS JOIN LATERAL (
  SELECT elem, row_number() over ()::int AS seq
  FROM jsonb_array_elements(l.route_arr) elem
) ord
ON CONFLICT (chain_id, block_number, tx_hash, parent_log_index, seq) DO UPDATE
SET dex_name       = EXCLUDED.dex_name,
    pool_address   = EXCLUDED.pool_address,
    token_in       = EXCLUDED.token_in,
    token_out      = EXCLUDED.token_out,
    amount_in_raw  = EXCLUDED.amount_in_raw,
    amount_out_raw = EXCLUDED.amount_out_raw,
    fee_bps        = EXCLUDED.fee_bps;

COMMIT;