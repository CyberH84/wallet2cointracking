\set ON_ERROR_STOP on
BEGIN;

DELETE FROM core.aave_v3_events
 WHERE chain_id = :CHAIN_ID AND block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK;

WITH aave_pool AS (
  SELECT address
  FROM core.contracts
  WHERE chain_id = :CHAIN_ID AND protocol = 'AAVE_V3' AND component IN ('POOL','L2POOL')
),
src AS (
  SELECT e.*
  FROM stage.decoded_events e
  JOIN aave_pool p ON p.address = e.contract_address
  WHERE e.chain_id = :CHAIN_ID
    AND e.block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK
    AND e.event_name IN ('Supply','Withdraw','Borrow','Repay','LiquidationCall','FlashLoan')
    AND e.removed IS NOT TRUE
)
INSERT INTO core.aave_v3_events (
  chain_id, block_number, block_time, tx_hash, log_index,
  event_type, user_address, reserve_address, amount_raw, amount,
  interest_rate_mode, debt_to_cover_raw, collateral_asset, liquidator
)
SELECT
  :CHAIN_ID, block_number, block_time, tx_hash, log_index,
  upper(event_name),
  lower(COALESCE(args->>'user', args->>'onBehalfOf', args->>'recipient')),
  lower(args->>'reserve'),
  CASE
    WHEN event_name IN ('Supply','Withdraw','Borrow','Repay') THEN (args->>'amount')::numeric
    WHEN event_name = 'LiquidationCall' THEN (args->>'debtToCover')::numeric
    ELSE NULL
  END,
  NULL,
  CASE WHEN event_name IN ('Borrow','Repay') THEN
       (CASE (args->>'interestRateMode') WHEN '1' THEN 'STABLE' WHEN '2' THEN 'VARIABLE' ELSE NULL END)
       END,
  (args->>'debtToCover')::numeric,
  lower(args->>'collateralAsset'),
  lower(args->>'liquidator')
FROM src
ON CONFLICT (chain_id, block_number, tx_hash, log_index) DO UPDATE
SET block_time = EXCLUDED.block_time,
    event_type = EXCLUDED.event_type,
    user_address = EXCLUDED.user_address,
    reserve_address = EXCLUDED.reserve_address,
    amount_raw = EXCLUDED.amount_raw,
    interest_rate_mode = EXCLUDED.interest_rate_mode,
    debt_to_cover_raw = EXCLUDED.debt_to_cover_raw,
    collateral_asset = EXCLUDED.collateral_asset,
    liquidator = EXCLUDED.liquidator;

-- Reserve indices
DELETE FROM core.aave_v3_reserve_indices
 WHERE chain_id = :CHAIN_ID AND block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK;

WITH idx_ev AS (
  SELECT e.*
  FROM stage.decoded_events e
  JOIN core.contracts c ON c.chain_id = e.chain_id
                       AND c.address   = e.contract_address
                       AND c.protocol  = 'AAVE_V3'
  WHERE e.chain_id = :CHAIN_ID
    AND e.block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK
    AND e.event_name = 'ReserveDataUpdated'
    AND e.removed IS NOT TRUE
)
INSERT INTO core.aave_v3_reserve_indices (
  chain_id, block_number, block_time, reserve_address,
  liquidity_index_ray, variable_borrow_index_ray,
  liquidity_rate_ray,   variable_borrow_rate_ray
)
SELECT
  :CHAIN_ID, block_number, block_time,
  lower(args->>'reserve'),
  (args->>'liquidityIndex')::numeric,
  (args->>'variableBorrowIndex')::numeric,
  (args->>'liquidityRate')::numeric,
  (args->>'variableBorrowRate')::numeric
FROM idx_ev
ON CONFLICT (chain_id, block_number, reserve_address) DO UPDATE
SET block_time = EXCLUDED.block_time,
    liquidity_index_ray = EXCLUDED.liquidity_index_ray,
    variable_borrow_index_ray = EXCLUDED.variable_borrow_index_ray,
    liquidity_rate_ray = EXCLUDED.liquidity_rate_ray,
    variable_borrow_rate_ray = EXCLUDED.variable_borrow_rate_ray;

