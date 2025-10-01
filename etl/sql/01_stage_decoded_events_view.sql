-- Adjust this view to point at your decoded event source.
-- Expected columns: chain_id, block_number, block_time, tx_hash, log_index,
--                   contract_address, event_name, args JSONB, topic0, removed
DROP VIEW IF EXISTS stage.decoded_events;
CREATE VIEW stage.decoded_events AS
SELECT
  s.chain_id,
  s.block_number,
  s.block_time,
  s.tx_hash,
  s.log_index,
  lower(s.contract_address) AS contract_address,
  s.event_name,
  s.args,
  s.topic0,
  COALESCE(s.removed, FALSE) AS removed
FROM public.decoded_events_source s;  -- TODO: replace with your table/view