# Flare Wallet Transaction Exporter

A comprehensive Python Flask web application that analyzes DeFi transactions from multiple blockchain networks and exports them in CoinTracking.info compatible CSV format with enhanced protocol detection, PostgreSQL database integration, ETL pipeline capabilities, and advanced wallet analytics.

## Features

- **Multi-Network Support**: Flare Network and Arbitrum with comprehensive RPC connectivity
- **PostgreSQL Database Integration**: 
  - Persistent transaction storage and analytics with dual-format processing
  - ETL pipeline with layered data warehouse (raw/stage/core/ma### Enhanced Database Integration

The PostgreSQL integration has been significantly enhanced with advanced transaction processing capabilities:

### Enhanced Processing Pipeline
- **Dual-Format Processing**: Every transaction analysis now generates both CSV export AND database storage simultaneously
- **Real-Time Analytics**: Wallet analysis data is automatically generated and stored during processing
- **Transaction Normalization**: Raw transaction data is transformed to match database schema requirements
- **Comprehensive Storage**: Transactions, token transfers, and wallet analytics are all persisted

### Performance & Scalability
- **Persistent Storage**: Transaction data survives application restarts with comprehensive historical tracking
- **Connection Pooling**: Efficient database connection management with automatic retry logic
- **Indexed Queries**: Fast wallet lookups and portfolio analysis with optimized database schemas
- **Bulk Operations**: Efficient processing of large transaction sets with batch storage capabilities
- **Health Monitoring**: Real-time database performance metrics and connectivity validation

### Advanced Analytics & Wallet Intelligence
- **Historical Analysis**: Track wallet performance over time with stored transaction patterns
- **Cross-Chain Analytics**: Compare activity across networks with unified data model
- **Protocol Usage Patterns**: Identify DeFi strategy trends with comprehensive protocol interaction tracking
- **Risk Assessment**: Portfolio diversification and exposure analysis with automated risk scoring
- **Transaction Classification**: Automatic categorization of DeFi operations (lending, trading, staking, etc.)
- **Volume Analysis**: Track transaction volumes and USD values over timeed wallet analysis and portfolio tracking with comprehensive analytics
  - Real-time health monitoring and connection pooling
  - Enhanced transaction processing pipeline with database storage
  - Wallet analysis generation with protocol usage and risk assessment
- **Enhanced DeFi Protocol Detection**: 
  - **Aave V3** (lending/borrowing operations)
  - **OpenOcean** (DEX aggregator trading)
  - **SparkDEX V3** (Uniswap V3 fork with advanced trading)
  - **Kinetic Market** (decentralized lending platform)
  - **Flare Network** native staking and FTSO operations
- **Advanced Contract Analysis**: Real contract addresses and method signature detection
- **CoinTracking.info Export**: Enhanced CSV format with detailed contract information
- **Modern Web Interface**: Responsive design with real-time job progress tracking
- **Token Icon Caching**: Automated token logo fetching and local caching system
- **Health Monitoring**: Built-in network connectivity, API, and database health checks
- **ETL Pipeline**: Comprehensive blockchain data processing with SQL-based transformations

## Supported Networks & Protocols

### Flare Network (Chain ID: 14)
- **Native Staking**: Delegation to FTSO providers with reward claiming
- **WFLR Operations**: Wrapping/unwrapping of native FLR tokens
- **FTSO Rewards**: Automatic detection of Time Series Oracle rewards
- **DeFi Protocols**: Enhanced detection for Flare-based DeFi platforms
- **RPC Endpoint**: `https://flare-api.flare.network/ext/C/rpc`

### Arbitrum (Chain ID: 42161)
- **Aave V3**: Complete lending protocol support
  - Supply/withdraw operations
  - Borrow/repay transactions
  - Liquidation events
  - Contract addresses: Pool, PoolAddressesProvider, AToken contracts
- **OpenOcean**: DEX aggregator with multi-source routing
  - Token swaps across multiple DEXs
  - Optimal routing detection
- **SparkDEX V3**: Uniswap V3 fork with advanced features
  - Liquidity provision and removal
  - Concentrated liquidity positions
  - Fee collection operations
- **Kinetic Market**: Decentralized lending platform
  - Lending and borrowing operations
  - Interest rate optimization
- **RPC Endpoint**: `https://arb1.arbitrum.io/rpc`

## Installation & Setup

### Prerequisites
- Python 3.8+ (tested with Python 3.13)
- PostgreSQL 12+ (optional but recommended for full features)
- Internet connection for blockchain API access

### Quick Start

#### Automated Setup (Recommended)

Run the setup script that handles everything automatically:

```bash
python setup.py
```

This will:
- Create Python virtual environment
- Install all dependencies including PostgreSQL drivers
- Set up database configuration
- Initialize database schemas and ETL pipeline
- Run basic tests and validation

#### Manual Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd wallet2cointracking
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv .venv
   .venv\Scripts\Activate.ps1  # Windows PowerShell
   # or: source .venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure database** (optional):
   ```bash
   # Copy environment template
   cp .env.example .env
   
   # Edit .env with your PostgreSQL credentials
   # DATABASE_URL=postgresql://username:password@localhost:5432/defi_warehouse
   
   # Create database
   createdb defi_warehouse
   
   # Initialize database and ETL schemas
   python migrate_db.py
   ```

5. **Run the application**:
   python app.py
   ```

5. **Access the web interface**:
   Open your browser and navigate to:
   - Local: `http://localhost:5000`
   - Network: `http://127.0.0.1:5000`
   - External: `http://<your-ip>:5000` (if accessible on network)

## Usage

1. **Enter Wallet Address**: Input your EVM-compatible wallet address
2. **Select Network**: Choose between Flare Network or Arbitrum
3. **Generate CSV**: Click "Generate & Download CSV" to analyze transactions
4. **Import to CoinTracking**: Use the downloaded CSV file in CoinTracking.info

## API Configuration & Data Sources

### Blockchain Data Sources
The application fetches real transaction data from multiple blockchain explorers:

#### Primary APIs
- **Arbiscan API**: `https://api.arbiscan.io/api` (Arbitrum transactions)
- **Flare Explorer**: `https://flare-explorer.flare.network/api` (Flare network primary)
- **Etherscan V2 Multi-chain**: `https://api.etherscan.io/v2/api` (Fallback with chain ID)

#### API Authentication
- **API Key**: `5GNG5ZQRP3TEF7EJ7RTMW96N68JJQZFD9D` (Etherscan-compatible)
- **Rate Limiting**: Automatic handling with fallback mechanisms
- **Health Monitoring**: Built-in API endpoint health checks

#### Token Price Data
- **CoinGecko API**: `https://api.coingecko.com/api/v3/`
  - Contract-based price lookups
  - Multi-chain token support
  - USD price conversion
  - Rate limit handling with 429 error management

#### RPC Endpoints
- **Arbitrum**: `https://arb1.arbitrum.io/rpc`
- **Flare**: `https://flare-api.flare.network/ext/C/rpc`
- **Fallback**: Etherscan proxy endpoints for block number queries

## Project Structure

```
cursor-app-v2/
├── app.py                      # Main Flask application with enhanced protocol detection
├── defi_config.py             # DeFi protocol configurations and contract addresses
├── requirements.txt           # Python dependencies
├── README.md                  # Project documentation (this file)
├── test_address_info.py       # Address information testing utilities
├── static/                    # Static web assets
│   ├── network_logos/         # Cached network logos (SVG/PNG)
│   │   ├── arbitrum.svg
│   │   └── flare.svg
│   └── token_icons/           # Cached token icons by network
│       ├── arbitrum/          # Arbitrum token icons
│       │   └── <contract>.png
│       └── flare/             # Flare token icons
│           └── <contract>.png
├── templates/
│   └── index.html            # Modern responsive web interface
├── data/                     # Application data and cache
│   ├── address_info_cache.json    # Contract information cache
│   └── token_meta_cache.json      # Token metadata cache
├── logs/                     # Application logs
│   ├── app.log              # Main application log
│   └── app.err              # Error logs
├── tests/                    # Test suite
│   ├── test_arbitrum_summary.py
│   ├── test_coingecko_helper.py
│   ├── test_flare_tokens.py
│   └── test_token_icon_endpoint.py
└── __pycache__/             # Python bytecode cache
```

## Enhanced CSV Export Format

The exported CSV follows CoinTracking.info "Custom" import format with extensive enhancements:

### Core Transaction Fields
- **Type**: Transaction type (Trade, Deposit, Withdrawal, etc.)
- **Buy/Sell**: Token amounts and symbols
- **Fee**: Transaction fees with proper currency detection
- **Exchange**: Platform identification (enhanced protocol detection)
- **Date**: ISO 8601 timestamp formatting

### Enhanced Protocol Detection
- **dAppPlatform**: Automatically detected DeFi platform names
- **FunctionName**: Smart contract function signatures
- **Platform Group**: Categorized protocol types (DEX, Lending, Staking)

### Advanced Contract Information
The CSV now includes comprehensive contract and token information:
# Flare Wallet Transaction Exporter

Lightweight Flask app that analyzes on-chain activity for EVM-compatible wallets (Arbitrum & Flare), enriches token holdings with USD valuations, caches token icons locally, and exports transaction rows in a CoinTracking.info-compatible CSV.

This README summarizes how to run the app, the important endpoints, and the notable implementation details added in recent updates.

## Application Architecture & Features

### Core Functionality
- **Multi-Chain Transaction Analysis**: Fetches and analyzes transactions from Arbitrum and Flare networks
- **Enhanced Protocol Detection**: Identifies DeFi protocols using real contract addresses and method signatures
- **Token Balance Aggregation**: Combines transaction history with real-time on-chain balance queries
- **USD Price Enrichment**: Integrates CoinGecko API for comprehensive token valuations
- **Intelligent Caching**: Local storage for token icons, contract metadata, and price data

### Advanced Features
- **Asynchronous Job Processing**: Background CSV generation with progress tracking
- **Health Monitoring**: Real-time API and RPC endpoint status checks
- **Asset Prefetching**: Automatic download of token logos from TrustWallet repository
- **Contract Information**: Enhanced contract name resolution using blockchain explorer APIs
- **Rate Limit Handling**: Intelligent API request management with fallback mechanisms

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

## API Endpoints

### Core Endpoints
- **`GET /`** — Main web interface for transaction analysis
- **`GET /health`** — Comprehensive health check for all external APIs, RPC endpoints, and database
- **`POST /start_job`** — Initialize asynchronous CSV generation job (returns job_id)
- **`GET /job_status/<job_id>`** — Real-time job progress and status monitoring
- **`GET /download/<job_id>`** — Download completed CSV export file

### Database Management
- **`GET /db/health`** — Dedicated database health check and statistics
- **`POST /db/init`** — Initialize database schemas and ETL pipeline
- **`GET /db/wallet/<address>/<chain_id>`** — Get stored wallet analysis from database

### Enhanced Database Features
- **Dual-Format Processing**: Simultaneous CSV export and database storage during transaction analysis
- **Wallet Analytics Storage**: Comprehensive wallet analysis with protocol usage, transaction patterns, and risk metrics
- **Transaction Storage**: Complete transaction data with token transfers, protocol detection, and metadata
- **Database Health Monitoring**: Real-time monitoring of database connectivity, table counts, and performance metrics

### Network Analysis
- **`GET /network_summary/<network>/<wallet>`** — Detailed wallet analysis with:
  - Token holdings and USD valuations
  - Transaction counts and metadata
  - Network-specific statistics
  - Protocol interaction summary
- **`GET /flare_tokens/<wallet>`** — Specialized Flare token aggregation from transaction history

### Asset Management
- **`GET /token_icon/<network>/<contract_address>`** — Cached token icons with automatic fallback
- **`GET /assets_status`** — Asset prefetch status and cache statistics
- **`GET /trustwallet/assets/master/blockchains/<network>/assets/<contract>/logo.png`** — Direct TrustWallet asset proxy

### Utility Endpoints
- **`GET /arbitrum_summary/<wallet>`** — Arbitrum-specific transaction analysis
- **`GET /address_info/<network>/<address>`** — Contract verification and metadata lookup

### API Usage Examples

**Fetch Network Summary:**
```powershell
# Get comprehensive wallet analysis for Arbitrum
Invoke-RestMethod -Uri 'http://127.0.0.1:5000/network_summary/arbitrum/0x...' -Method GET | ConvertTo-Json -Depth 5

# Check Flare network token holdings
Invoke-RestMethod -Uri 'http://127.0.0.1:5000/flare_tokens/0x...' -Method GET
```

**Start CSV Export Job:**
```powershell
# Initialize CSV generation job
$jobResponse = Invoke-RestMethod -Uri 'http://127.0.0.1:5000/start_job' -Method POST -ContentType 'application/json' -Body '{"wallet":"0x...","networks":["arbitrum","flare"]}'

# Monitor job progress
Invoke-RestMethod -Uri "http://127.0.0.1:5000/job_status/$($jobResponse.job_id)" -Method GET

# Download completed CSV
Invoke-WebRequest -Uri "http://127.0.0.1:5000/download/$($jobResponse.job_id)" -OutFile "wallet_export.csv"
```

**Health Check:**
```bash
# Monitor system health (includes database status)
curl http://127.0.0.1:5000/health

# Database-specific health check
curl http://127.0.0.1:5000/db/health

# Initialize database
curl -X POST http://127.0.0.1:5000/db/init
```

## ETL Pipeline

The application includes a comprehensive ETL (Extract, Transform, Load) pipeline for processing blockchain data at scale.

### ETL Architecture

The pipeline uses a layered data warehouse approach with PostgreSQL:

```
Raw Data → Stage → Core → Marts
    ↓        ↓      ↓      ↓
Blockchain  Clean  Business Analytics
  Events    Data   Logic   & Reports
```

### ETL Components

Located in the `etl/` folder:

- **`00_init_schemas.sql`** - Database schema initialization
- **`02_seed_chains.sql`** - Supported blockchain networks
- **`03_seed_contracts_*.sql`** - Protocol contract addresses
- **`04_etl_openocean.sql`** - OpenOcean DEX data processing
- **`05_etl_sparkdex_v3.sql`** - SparkDEX V3 liquidity data
- **`06_etl_aave_v3.sql`** - Aave V3 lending protocol
- **`07_etl_kinetic.sql`** - Kinetic Market data
- **`09_etl_ftso.sql`** - Flare FTSO oracle data
- **`10_amount_scaling_helpers.sql`** - Token amount utilities

### Running ETL Jobs

#### Daily Processing (Recommended)
```bash
cd etl

# Process latest blocks for Arbitrum (handles reorgs)
./run_daily_tail.sh 42161 50000000

# Process latest blocks for Flare
./run_daily_tail.sh 14 10000000
```

#### Custom Block Range
```bash
cd etl

# Process specific block range
./run_window.sh 42161 49000000 50000000  # Arbitrum blocks 49M-50M
./run_window.sh 14 9000000 10000000      # Flare blocks 9M-10M
```

#### Configuration

Set up ETL environment in `.env`:

```env
# ETL Configuration
PGURL=postgresql://username:password@localhost:5432/defi_warehouse
REORG_WINDOW=200
DEFAULT_FROM_BLOCK=0
DEFAULT_TO_BLOCK=9223372036854775807

# Chain Configuration
ARBITRUM_CHAIN_ID=42161
FLARE_CHAIN_ID=14
```

### Data Models

The ETL pipeline creates comprehensive data models:

#### Core Tables
- **`core.dim_chain`** - Blockchain network metadata
- **`core.dim_token`** - Token information and pricing
- **`core.contracts`** - DeFi protocol contract registry
- **`core.blocks`** - Block metadata and timestamps

#### Protocol Tables
- **`core.openocean_swaps`** - DEX swap transactions
- **`core.sparkdex_v3_pools`** - Liquidity pool data
- **`core.aave_v3_*`** - Lending protocol events
- **`core.ftso_*`** - Flare oracle data

### Integration with Web App

The ETL pipeline integrates seamlessly with the Flask application:

- Transactions processed via web interface are automatically stored
- Database health monitoring includes ETL schema status
- Portfolio analysis uses both real-time API data and historical ETL data
- Advanced analytics queries leverage the data warehouse structure

## Technical Implementation Details

### Blockchain Data Integration
- **Multi-Explorer Architecture**: Prioritizes native explorer APIs (Arbiscan, Flare Explorer) with intelligent fallback to Etherscan v2 multi-chain endpoints
- **Parallel Balance Queries**: After aggregating token quantities from transaction history, executes concurrent on-chain balance calls for authoritative holdings data
- **Method Signature Detection**: Enhanced protocol identification using real smart contract function signatures and ABI analysis

### Advanced Protocol Detection System
- **Real Contract Addresses**: Uses actual deployed contract addresses for accurate protocol identification
- **Method Fallback Mapping**: Comprehensive mapping of function signatures to protocol operations
- **Group Classification**: Automatic categorization into protocol types (DEX, Lending, Staking, Bridge)

### Price and Asset Management
- **CoinGecko Integration**: Contract-address based price lookups with intelligent heuristics for common tokens:
  - WETH → Ethereum price
  - WBTC → Bitcoin price  
  - USDC/USDT → $1.00 stable value
  - FLR/WFLR → Flare network price
- **Multi-Layer Caching**:
  - In-memory price caching for session performance
  - Persistent disk caching for token icons under `static/token_icons/<network>/`
  - Contract metadata caching in `data/address_info_cache.json`

### Performance Optimizations
- **Background Asset Prefetching**: Startup threads download network and token logos from TrustWallet repository
- **Asynchronous Job Processing**: CSV generation runs in background threads with progress tracking
- **Rate Limit Intelligence**: Automatic handling of API rate limits with exponential backoff
- **Connection Pooling**: Efficient HTTP connection management for external API calls

### Enhanced Contract Analysis
- **Comprehensive Contract Information**: Utilizes blockchain explorer APIs to fetch:
  - Verified contract names and source code information
  - Token metadata (name, symbol, decimals)
  - Contract verification status and creation details
- **Multi-Address Analysis**: Enriches CSV exports with contract information for all transaction participants:
  - `FromContractName`/`FromTokenName` - Source address details
  - `ContractName`/`ContractTokenName` - Contract interaction details  
  - `dAppPlatform`/`ToTokenName` - Destination address details

## Development and Testing

### Adding New Protocol Support
1. **Update Protocol Configuration** (`defi_config.py`):
   ```python
   NEW_PROTOCOL_CONFIG = {
       'addresses': ['0x...'],  # Real deployed contract addresses
       'methods': ['methodSignature(...)'],  # Function signatures
       'name': 'Protocol Name'
   }
   ```

2. **Extend Detection Logic** (`app.py`):
   ```python
   def analyze_defi_interaction(tx, network):
       # Add protocol-specific detection logic
       if tx['to'].lower() in NEW_PROTOCOL_ADDRESSES:
           return detect_new_protocol_operation(tx)
   ```

3. **Add Method Mappings**:
   ```python
   method_fallback_map = {
       'methodHash': 'Protocol Operation Name'
   }
   ```

### Testing Suite
```powershell
# Run complete test suite
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/test_arbitrum_summary.py -v
python -m pytest tests/test_coingecko_helper.py -v
python -m pytest tests/test_flare_tokens.py -v
```

### Current Test Coverage
- **Network Summary Aggregation**: Validates wallet analysis and token aggregation
- **Token Icon Management**: Tests icon caching and TrustWallet integration  
- **CoinGecko Integration**: Price fetching and contract resolution
- **Protocol Detection**: DeFi platform identification accuracy

### Configuration Management
- **Environment Variables**: Support for API keys and endpoint configuration
- **Logging Configuration**: Comprehensive logging to `logs/app.log` and `logs/app.err`
- **Cache Management**: Configurable cache sizes and retention policies
- **Network Timeouts**: Adjustable timeout settings for external API calls

## Troubleshooting Guide

### Common Issues and Solutions

#### Low Token Valuations
**Symptoms**: Network totals show unexpectedly low USD values
**Diagnosis**: Check `/assets_status` and `/network_summary/<network>/<wallet>`
**Solutions**: 
- Verify CoinGecko API connectivity and rate limits
- Review contract-to-coin ID mappings
- Check for missing price data in logs

#### Missing Transactions
**Symptoms**: UI shows fewer transactions than blockchain explorers
**Diagnosis**: Check `tokentx_pages` and `tokentx_used_fallback` in network summary
**Solutions**:
- Verify explorer API key validity
- Check rate limiting and API quotas
- Review fallback mechanism logs

#### Protocol Detection Issues
**Symptoms**: Transactions show as "Unknown" platform
**Diagnosis**: Review transaction logs and method signatures
**Solutions**:
- Update `defi_config.py` with missing contract addresses
- Add method signature mappings
- Verify contract verification status

#### Performance Issues
**Symptoms**: Slow CSV generation or API responses
**Solutions**:
- Monitor network connectivity in health endpoint
- Check cache hit rates in logs
- Review concurrent request limits

### Health Monitoring
```powershell
# Check system health
curl http://localhost:5000/health

# Monitor asset cache status  
curl http://localhost:5000/assets_status

# Review application logs
Get-Content logs/app.log -Tail 50
```

### CSV Export Column Reference

#### Standard CoinTracking.info Fields
| Column | Description | Example |
|--------|-------------|---------|
| `Type` | Transaction classification | `Trade`, `Deposit`, `Withdrawal` |
| `Buy` | Received token amount | `100.5` |
| `Cur.` | Received token symbol | `USDC` |
| `Sell` | Sent token amount | `0.05` |
| `Cur..1` | Sent token symbol | `ETH` |
| `Fee` | Transaction fee amount | `0.002` |
| `Cur..2` | Fee currency | `ETH` |
| `Exchange` | Platform identifier | `Aave V3` |
| `Trade-Group` | Protocol category | `DeFi Lending` |
| `Comment` | Transaction details | `Supply USDC to Aave V3` |
| `Date` | ISO 8601 timestamp | `2025-09-30T14:05:42` |

#### Enhanced Contract Information Fields
| Column | Description | Data Source |
|--------|-------------|-------------|
| `FromContractName` | Source address contract name | Explorer `getsourcecode` API |
| `FromTokenName` | Source address token name | On-chain `name()` call |
| `ContractName` | Interaction contract name | Explorer verification data |
| `ContractTokenName` | Contract token metadata | On-chain token calls |
| `dAppPlatform` | Destination platform name | Enhanced protocol detection |
| `ToTokenName` | Destination token name | Multi-source token metadata |
| `FunctionName` | Smart contract method | ABI signature analysis |
| `TokenId` | NFT or token identifier | Transaction input parsing |

#### Technical Metadata Fields  
| Column | Description | Purpose |
|--------|-------------|---------|
| `TxHash` | Transaction hash | Blockchain verification |
| `BlockNumber` | Block number | Transaction ordering |
| `LogIndex` | Event log index | Event identification |
| `Network` | Blockchain network | Multi-chain support |

## Security Considerations

### API Key Management
- API keys are embedded for demonstration purposes
- For production use, implement environment variable configuration
- Consider API key rotation and rate limit monitoring

### Data Privacy
- No wallet private keys are required or stored
- Only public blockchain data is accessed
- Local caching may store transaction metadata

### Network Security
- All API communications use HTTPS
- Rate limiting prevents excessive API usage
- Health checks monitor external service availability

## Performance Characteristics

### Supported Scale
- **Wallets**: Handles wallets with thousands of transactions
- **Networks**: Currently supports 2 networks (expandable)
- **Concurrent Users**: Single-instance design for personal use
- **CSV Size**: Exports can handle 10,000+ transaction rows

### Resource Requirements
- **Memory**: 100-500MB depending on wallet size and cache
- **Disk**: Minimal (logs + cached icons + token metadata)
- **Network**: Dependent on blockchain API response times
- **CPU**: Low usage except during CSV generation

## Database Benefits

The PostgreSQL integration provides significant advantages:

### Performance & Scalability
- **Persistent Storage**: Transaction data survives application restarts
- **Connection Pooling**: Efficient database connection management
- **Indexed Queries**: Fast wallet lookups and portfolio analysis
- **Bulk Operations**: Efficient processing of large transaction sets

### Advanced Analytics
- **Historical Analysis**: Track wallet performance over time
- **Cross-Chain Analytics**: Compare activity across networks
- **Protocol Usage Patterns**: Identify DeFi strategy trends
- **Risk Assessment**: Portfolio diversification and exposure analysis

### Enhanced Data Warehouse Features
- **ETL Pipeline**: Process blockchain data at scale with automated transaction ingestion
- **Layered Architecture**: Clean separation of raw, processed, and analytical data with enhanced schema design
- **SQL Analytics**: Direct database queries for custom analysis with comprehensive wallet analytics tables
- **Backup & Recovery**: Enterprise-grade data protection with automated migration capabilities
- **Schema Evolution**: Database migration scripts for seamless updates and enhancements

### Enhanced Operational Benefits
- **Advanced Health Monitoring**: Real-time database performance metrics, table counts, and transaction statistics
- **Graceful Degradation**: Application continues with CSV-only mode if database unavailable
- **Enhanced Development Tools**: Migration scripts, validation utilities, and comprehensive testing framework
- **Production Ready**: Connection pooling, error handling, comprehensive logging, and automatic retry logic
- **Data Validation**: Built-in validation for transaction data integrity and wallet analysis accuracy

### Database Schema & Models
The enhanced integration includes comprehensive database models:

#### Core Transaction Tables
- **`ethereum_transactions`**: Complete transaction data with protocol detection and metadata
- **`token_transfers`**: Detailed token transfer information with USD valuations
- **`wallet_analysis`**: Comprehensive wallet analytics with protocol usage patterns and risk assessment

#### Enhanced Features
- **Automatic Data Transformation**: Raw API data is automatically converted to database-compatible format
- **Duplicate Handling**: Intelligent merge operations prevent duplicate transaction storage
- **Real-Time Updates**: Transaction processing updates both CSV generation and database storage
- **Comprehensive Logging**: Detailed logging of all database operations with error tracking

For detailed information, see [DATABASE_INTEGRATION.md](DATABASE_INTEGRATION.md).

## License and Legal

### License
This project is provided for educational and personal use under MIT-style licensing.

### Disclaimer
- **Tax Compliance**: Users are responsible for tax reporting accuracy
- **Data Accuracy**: Blockchain data quality depends on external APIs
- **Financial Advice**: This tool provides data analysis, not financial advice

### Third-Party Services
- **CoinGecko**: Price data subject to their terms of service
- **Blockchain Explorers**: Transaction data from Arbiscan, Flare Explorer
- **TrustWallet**: Token icons from their open-source assets repository

## Contributing

### Contribution Guidelines
1. **Fork the repository** and create a feature branch
2. **Add comprehensive tests** for new functionality  
3. **Update documentation** including this README
4. **Follow existing code style** and conventions
5. **Submit a pull request** with detailed description

### Development Priorities
- Additional blockchain network support (Polygon, BSC, etc.)
- Enhanced DeFi protocol coverage
- Performance optimizations for large wallets
- Advanced tax reporting features
- Mobile-responsive UI improvements

### Community
- **Issues**: Report bugs and feature requests via GitHub Issues
- **Discussions**: Technical discussions and protocol requests welcome
- **Documentation**: Help improve user guides and API documentation
