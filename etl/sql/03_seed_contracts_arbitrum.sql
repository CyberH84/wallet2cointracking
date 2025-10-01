-- OPENOCEAN routers/aggregator (add current router addresses)
-- INSERT INTO core.contracts (chain_id, address, protocol, component, version, start_block)
-- VALUES (42161, '0x...', 'OPENOCEAN', 'ROUTER', 'vX', 0)
-- ON CONFLICT DO NOTHING;

-- AAVE V3 Pool / L2Pool on Arbitrum (verify from official Aave v3 addresses before enabling)
-- Docs: https://aave.com/docs  (see deployed markets / addresses). [5](https://support.ledger.com/article/7326303122589-zd)
-- INSERT INTO core.contracts (chain_id, address, protocol, component, version, start_block)
-- VALUES (42161, '0x...', 'AAVE_V3', 'POOL', 'v3', 0)
-- ON CONFLICT DO NOTHING;

-- PANCAKESWAP (v2-style) on Arbitrum
-- RouterV2 address frequently referenced as 0x8cFe327CEc66d1C090Dd72bd0FF11d690C33a2Eb — verify on Pancake docs before use. [6](https://dev.flare.network/ftso/guides/build-first-app/)
INSERT INTO core.contracts (chain_id, address, protocol, component, version, start_block)
VALUES
  (42161, lower('0x8cFe327CEc66d1C090Dd72bd0FF11d690C33a2Eb'), 'PANCAKESWAP', 'ROUTER', 'v2', NULL)
ON CONFLICT DO NOTHING;

-- Factory address if you want PairCreated ingestion (add the correct one when confirmed)
-- INSERT INTO core.contracts (chain_id, address, protocol, component) VALUES
-- (42161, '0x...', 'PANCAKESWAP', 'FACTORY')
-- ON CONFLICT DO NOTHING;
