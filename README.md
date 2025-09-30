# Flare Wallet Transaction Exporter

A Python Flask web application that analyzes DeFi transactions from Flare and Arbitrum networks and exports them in CoinTracking.info compatible CSV format.

## Features

- **Multi-Network Support**: Flare Network and Arbitrum
- **DeFi Protocol Detection**: 
  - Aave V3 (lending/borrowing)
  - OpenOcean (DEX trading)
  - SparkDEX V3 (Uniswap V3 fork)
  - Kinetic Market (lending)
  - Flare Network native staking
- **CoinTracking.info Export**: Compatible CSV format for tax reporting
- **Modern Web Interface**: Clean, responsive design

## Supported Networks & Protocols

### Flare Network
- Native staking and delegation to FTSO providers
- WFLR wrapping/unwrapping
- FTSO reward claiming

### Arbitrum
- Aave V3: Supply, withdraw, borrow, repay
- OpenOcean: Token swaps and trading
- SparkDEX V3: Liquidity provision and trading
- Kinetic Market: Lending and borrowing

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd cursor-app
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Access the web interface**:
   Open your browser and go to `http://localhost:5000`

## Usage

1. **Enter Wallet Address**: Input your EVM-compatible wallet address
2. **Select Network**: Choose between Flare Network or Arbitrum
3. **Generate CSV**: Click "Generate & Download CSV" to analyze transactions
4. **Import to CoinTracking**: Use the downloaded CSV file in CoinTracking.info

## API Configuration

**Real Data Mode**: This application fetches real transaction data from blockchain explorers.
- **Arbitrum**: Uses Arbiscan API with provided API key
- **Flare**: Uses Flare Explorer API with fallback to Songbird Explorer
- **API Key**: `5GNG5ZQRP3TEF7EJ7RTMW96N68JJQZFD9D` (Etherscan-compatible)

**Supported APIs:**
- **Arbiscan**: For Arbitrum network transactions
- **Flare Explorer**: Primary API for Flare network
- **Songbird Explorer**: Fallback for Flare network transactions

## File Structure

```
cursor-app/
├── app.py                 # Main Flask application
├── defi_config.py         # DeFi protocol configurations
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html        # Web interface
└── README.md             # This file
```

## CSV Export Format

The exported CSV follows CoinTracking.info "Custom" import format:
# Flare Wallet Transaction Exporter

Lightweight Flask app that analyzes on-chain activity for EVM-compatible wallets (Arbitrum & Flare), enriches token holdings with USD valuations, caches token icons locally, and exports transaction rows in a CoinTracking.info-compatible CSV.

This README summarizes how to run the app, the important endpoints, and the notable implementation details added in recent updates.

## What this app does (high level)
- Fetches transactions and token transfers for a wallet on supported networks (Arbitrum, Flare).
- Aggregates per-token quantities and, when available, queries on-chain token balances to prefer authoritative balances.
- Enriches tokens with USD prices (CoinGecko contract lookup + heuristics for common tokens) and computes network and portfolio totals.
- Caches token logos under `static/token_icons/<network>/` and serves them via `/token_icon/<network>/<contract>`.
- Prefetches many common network and token logos (best-effort) from TrustWallet's assets repo.
- Provides a small web UI to generate CSV exports and quick API endpoints for programmatic use.

## Quick start

1. Install dependencies:

```powershell
pip install -r requirements.txt
```

2. Start the app:

```powershell
python app.py
```

3. Open the UI in your browser:

http://localhost:5000

The web UI offers a simple form to enter a wallet address, select networks, and generate/download a CSV.

## Important API endpoints
- `GET /health` — simple healthcheck for external APIs and RPC endpoints.
- `GET /network_summary/<network>/<wallet>` — small JSON summary for the wallet on the given network (tokens, network_total_usd, tokentx pages/metadata, transaction_count).
- `GET /flare_tokens/<wallet>` — aggregated Flare token holdings derived from `tokentx`.
- `GET /token_icon/<network>/<contract_address>` — serves cached token icon (tries TrustWallet raw assets when missing and caches locally).
- `GET /assets_status` — reports which network and token logos were downloaded and their sizes (useful for debugging asset prefetched state).
- `POST /start_job` — start an asynchronous CSV generation job for a wallet/networks; returns `job_id`.
- `GET /job_status/<job_id>` — poll job progress/status.
- `GET /download/<job_id>` — download the generated CSV when a job completes.

Example: fetch a network summary

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:5000/network_summary/arbitrum/<wallet>' -Method GET | ConvertTo-Json -Depth 5
```

## Notable implementation details

- Explorer fallbacks: the app prefers per-network explorer APIs but falls back to the Etherscan v2 multi-chain endpoint (`chainid` param) when needed.
- Balance fetching: after aggregating token quantities from `tokentx`, the app tries to query on-chain balances (`tokenbalance` or `eth_call balanceOf`) for more accurate holdings. These balance queries run in parallel for speed.
- Pricing: token prices are fetched from CoinGecko using contract-address endpoints where possible. When CoinGecko lacks a contract mapping we apply a small set of heuristics (WETH → ethereum, WBTC → bitcoin, USDC/USDT → 1.0, FLR/WFLR → flare) to provide reasonable defaults.
- Caching: prices are cached in-memory for the running process (simple PRICE_CACHE). Token images are cached on disk under `static/token_icons/<network>/`.
- Asset prefetch: at startup the app spawns background threads that attempt to download network logos and a seeded set of token logos from TrustWallet's assets repository (best-effort; failures are non-fatal).
- CSV export: the generator writes CSV rows in CoinTracking-compatible columns and includes additional fields such as `FunctionName` and `TokenId` to aid CSV consumers.
- **Enhanced Contract Information**: The CSV now includes contract and token name information for all addresses:
  - `FromContractName` and `FromTokenName` - Contract and token information for the 'from' address
  - `ContractName` and `ContractTokenName` - Contract and token information for the contract address
  - `dAppPlatform` and `ToTokenName` - Contract and token information for the 'to' address (existing columns)
  - Uses Flare Explorer's `getsourcecode` API to fetch verified contract names and token metadata

## File layout (high level)

```
cursor-app/
├── app.py                 # Main Flask application — endpoints, fetchers, logic
├── defi_config.py         # DeFi protocol addresses and method signatures
├── requirements.txt       # Python dependencies
├── static/
│   ├── network_logos/     # Prefetched network logos (svg/png wrappers)
│   └── token_icons/       # Cached token icons by network
├── templates/
│   └── index.html         # Web UI
└── tests/                 # pytest suite
```

## Development notes

- To add support for new protocols, update `defi_config.py` and extend `analyze_defi_interaction()` to detect the protocol and map transactions to export rows.
- The module contains multiple helper functions that are safe to run offline (they swallow network errors), which keeps tests fast and deterministic.

## Testing

Run the test suite locally:

```powershell
& "C:/Program Files/Python313/python.exe" -m pytest -q
```

Current test coverage includes a small set of unit tests for network summary aggregation, icon endpoint, and CoinGecko helper (4 tests in the current suite).

## Troubleshooting & tips

- If network totals show unexpectedly low values, check `/assets_status` and `/network_summary/<network>/<wallet>` to see which tokens were priced and whether CoinGecko returned values. Missing contract-to-coin mappings are a common reason for 0-valued tokens.
- To improve price coverage, maintain a local mapping of contract → CoinGecko coin id and extend heuristics in `get_token_price_coingecko()`.
- If the UI reports fewer transactions than an explorer, check `tokentx_pages` and `tokentx_used_fallback` in the network summary — we include metadata to show whether the explorer or Etherscan v2 fallback was used.

## CSV Export Columns

The exported CSV includes the following additional contract and token information columns:

| Column | Description |
|--------|-------------|
| `FromContractName` | Contract name for the 'from' address (if it's a verified contract) |
| `FromTokenName` | Token name for the 'from' address (if it's a token contract) |
| `ContractName` | Contract name for the contract address (if different from to/from addresses) |
| `ContractTokenName` | Token name for the contract address (if it's a token contract) |
| `dAppPlatform` | Contract name for the 'to' address (existing column) |
| `ToTokenName` | Token name for the 'to' address (existing column) |

These columns are populated using the Flare Explorer API's `getsourcecode` endpoint and on-chain token metadata calls, providing enhanced visibility into the contracts and tokens involved in each transaction.

## License

This project is provided for educational and personal use. Use the exported CSVs in accordance with your local tax regulations.

## Contributing

Contributions are welcome — please fork, make changes on a feature branch, and open a PR.
