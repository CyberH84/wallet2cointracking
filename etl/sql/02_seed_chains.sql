-- Seed common chains
INSERT INTO core.dim_chain (chain_id, chain_name, native_symbol, explorer_url)
VALUES
  (1, 'Ethereum Mainnet', 'ETH', 'https://etherscan.io'),
  (42161, 'Arbitrum One', 'ETH', 'https://arbiscan.io'),
  (56, 'BNB Smart Chain', 'BNB', 'https://bscscan.com'),
  (14, 'Flare Mainnet', 'FLR', 'https://flare-explorer.flare.network')
ON CONFLICT (chain_id) DO NOTHING;
-- Flare chain id 14 and explorer ref per Chainlist/ChainID resources. [1](https://developer.pancakeswap.finance/contracts/v2/router-v2)[2](https://docs.openocean.finance/)
