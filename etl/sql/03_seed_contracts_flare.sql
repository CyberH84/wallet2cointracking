-- SPARKDEX v3 factory (add official address from SparkDEX docs/repo when confirmed)
-- Docs overview: https://docs.sparkdex.ai  (see V3 DEX). [8](https://aave.com/docs/developers/aave-v3/overview)
-- INSERT INTO core.contracts (chain_id, address, protocol, component, version)
-- VALUES (14, '0x...', 'SPARKDEX_V3', 'FACTORY', 'v3')
-- ON CONFLICT DO NOTHING;

-- KINETIC Market core/market addresses (verify from Kinetic docs)
-- https://docs.kinetic.market/  (Contracts and API section). [9](https://chainlist.org/chain/14)
-- INSERT INTO core.contracts (chain_id, address, protocol, component)
-- VALUES (14, '0x...', 'KINETIC', 'MARKET')
-- ON CONFLICT DO NOTHING;

-- FTSO feed catalog: seed a few common feeds (IDs per Flare developer hub).
INSERT INTO core.flare_ftso_feeds (feed_id_hex, name, category)
VALUES
  ('0x01464c522f55534400000000000000000000000000','FLR/USD','CRYPTO'), -- "FLR/USD"
  ('0x014254432f55534400000000000000000000000000','BTC/USD','CRYPTO'),
  ('0x014554482f55534400000000000000000000000000','ETH/USD','CRYPTO')
ON CONFLICT DO NOTHING;
-- FTSOv2 feeds update ~1.8s; feed IDs are bytes21 encodings—decimals can change. [4](https://www.reddit.com/r/Cointracker/comments/lbm2xj/cant_import_trade_history_while_using_their_csv/)[3](https://gist.github.com/kylemanna/4104c84a0d1293d5af8e53572b5674a4)
