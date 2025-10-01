\set ON_ERROR_STOP on
BEGIN;

DELETE FROM core.kinetic_events
 WHERE chain_id = :CHAIN_ID AND block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK;

WITH kin AS (
  SELECT address
  FROM core.contracts
  WHERE chain_id = :CHAIN_ID AND protocol = 'KINETIC' AND component IN ('MARKET','POOL','CORE')
),
src AS (
  SELECT e.*
  FROM stage.decoded_events e
  JOIN kin k ON k.address = e.contract_address
  WHERE e.chain_id = :CHAIN_ID
    AND e.block_number BETWEEN :FROM_BLOCK AND :TO_BLOCK
    AND e.event_name IN ('Deposit','Withdraw','Borrow','Repay','Liquidate')
    AND e.removed IS NOT TRUE
)
INSERT INTO core.kinetic_events (
  chain_id, block_number, block_time, tx_hash, log_index,
  event_type, user_address, reserve_address,
  amount_raw, amount, liquidator, collateral_asset
)
SELECT
  :CHAIN_ID, block_number, block_time, tx_hash, log_index,
  upper(event_name),
  lower(COALESCE(args->>'user', args->>'onBehalfOf', args->>'borrower')),
  lower(args->>'asset'),
  (args->>'amount')::numeric,
  NULL,
  lower(args->>'liquidator'),
  lower(args->>'collateralAsset')
FROM src
ON CONFLICT (chain_id, block_number, tx_hash, log_index) DO UPDATE
SET block_time     = EXCLUDED.block_time,
    event_type     = EXCLUDED.event_type,
    user_address   = EXCLUDED.user_address,
    reserve_address= EXCLUDED.reserve_address,
    amount_raw     = EXCLUDED.amount_raw,
    liquidator     = EXCLUDED.liquidator,
    collateral_asset = EXCLUDED.collateral_asset;

