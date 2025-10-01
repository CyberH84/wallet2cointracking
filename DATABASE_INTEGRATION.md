# PostgreSQL Database Integration Guide

## Overview

The wallet2cointracking application now includes comprehensive PostgreSQL database integration that works alongside the existing ETL pipeline in the `etl/` folder. This provides persistent storage, advanced analytics, and scalable data processing capabilities.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Flask App     │    │   Database       │    │   ETL Pipeline  │
│   (app.py)      │◄──►│   (PostgreSQL)   │◄──►│   (etl/ folder) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
  ┌──────────────┐    ┌──────────────────┐    ┌─────────────────┐
  │ Transaction  │    │ Database Schemas │    │ Blockchain Data │
  │ Analysis     │    │ • raw            │    │ Processing      │
  │ & Export     │    │ • stage          │    │ • OpenOcean     │
  │              │    │ • core           │    │ • SparkDEX V3   │
  │              │    │ • marts          │    │ • Aave V3       │
  └──────────────┘    └──────────────────┘    └─────────────────┘
```

## Database Schema

The integration uses a layered data warehouse approach:

### Core Schemas

1. **`raw`** - Raw blockchain data
2. **`stage`** - Processed and cleaned data
3. **`core`** - Business logic and dimensional models
4. **`marts`** - Analytics and reporting tables

### Key Tables

#### Application Tables (public schema)
- `ethereum_transactions` - Main transaction records
- `token_transfers` - ERC-20 token transfer events
- `wallet_analysis` - Wallet summaries and analytics

#### ETL Tables (core schema)
- `dim_chain` - Supported blockchain networks
- `dim_token` - Token metadata
- `contracts` - Protocol contract addresses
- `openocean_swaps` - OpenOcean DEX transactions
- `sparkdex_v3_pools` - SparkDEX V3 liquidity pools
- `aave_v3_*` - Aave V3 lending protocol data

## Setup Instructions

### 1. Prerequisites

- PostgreSQL 12+ installed and running
- Python 3.8+
- Git

### 2. Quick Setup

Run the automated setup script:

```bash
python setup.py
```

This will:
- Create Python virtual environment
- Install all dependencies
- Set up environment configuration
- Initialize database schemas
- Run basic tests

### 3. Manual Setup

#### 3.1 Install Dependencies

```bash
pip install -r requirements.txt
```

#### 3.2 Configure Database

Create `.env` file from template:

```bash
cp .env.example .env
```

Edit `.env` with your database settings:

```env
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/defi_warehouse
DB_HOST=localhost
DB_PORT=5432
DB_NAME=defi_warehouse
DB_USER=postgres
DB_PASSWORD=your_password
```

#### 3.3 Create Database

```bash
createdb defi_warehouse
```

#### 3.4 Initialize Database

```bash
python migrate_db.py
```

## Usage

### 1. Start the Application

```bash
python app.py
```

### 2. Database Health Check

Visit `http://localhost:5000/health` to see overall system health including database status.

For detailed database health:
```bash
curl http://localhost:5000/db/health
```

### 3. Initialize Database via API

```bash
curl -X POST http://localhost:5000/db/init
```

### 4. Query Wallet Data

```bash
curl http://localhost:5000/db/wallet/0x742d35Cc6634C0532925a3b8D42b8E3C277e95/42161
```

## ETL Pipeline Integration

The database integrates seamlessly with the existing ETL pipeline in the `etl/` folder.

### Running ETL Jobs

#### Daily Processing
```bash
cd etl
./run_daily_tail.sh 42161 50000000  # Arbitrum
./run_daily_tail.sh 14 10000000     # Flare
```

#### Custom Window
```bash
cd etl
./run_window.sh 42161 49000000 50000000  # Process blocks 49M-50M on Arbitrum
```

### ETL Configuration

The ETL pipeline uses environment variables from `.env`:

```env
# ETL Settings
REORG_WINDOW=200
DEFAULT_FROM_BLOCK=0
DEFAULT_TO_BLOCK=9223372036854775807

# Chain IDs
ARBITRUM_CHAIN_ID=42161
FLARE_CHAIN_ID=14
```

## Database Models

### Transaction Storage

When transactions are processed through the web interface, they are automatically stored in the database:

```python
# Automatic storage in _finalize_job()
if DATABASE_ENABLED and job.get('all_transactions'):
    success = db_manager.store_transactions(job['all_transactions'])
```

### Data Models

#### EthereumTransaction
- Transaction hash, block info, gas details
- Protocol detection results
- Status and processing metadata

#### TokenTransfer
- ERC-20 transfer events
- Token metadata (symbol, decimals)
- USD values and price sources

#### WalletAnalysis
- Aggregated wallet statistics
- Protocol usage patterns
- Risk scoring and portfolio summaries

## API Endpoints

### Database Management

- `GET /db/health` - Database health status
- `POST /db/init` - Initialize database schemas
- `GET /db/wallet/<address>/<chain_id>` - Get wallet summary

### Enhanced Health Monitoring

The `/health` endpoint now includes database status:

```json
{
  "status": "ok",
  "checks": {
    "arbitrum": {"explorer": {...}, "rpc": {...}},
    "flare": {"explorer": {...}, "rpc": {...}},
    "database": {
      "ok": true,
      "latency_ms": 45,
      "version": "PostgreSQL 14.2",
      "connection_pool_size": 10
    }
  }
}
```

## Performance Optimization

### Connection Pooling

The database uses SQLAlchemy connection pooling:

```python
engine = create_engine(
    database_url,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

### Indexing Strategy

Key indexes are automatically created:

- Transaction hash indexes for fast lookups
- Block number indexes for time-based queries
- Wallet address indexes for portfolio analysis
- Protocol-specific indexes for DeFi analytics

### Bulk Operations

Token metadata is prefetched in bulk to minimize database calls:

```python
prefetch_token_meta_bulk(contract_addresses, network, max_workers=10)
```

## Monitoring and Logging

### Application Logs

Database operations are logged with appropriate levels:

```python
logger.info("✅ Transactions stored in database successfully")
logger.warning("⚠️ Failed to store transactions in database")
logger.error("❌ Database storage error: {error}")
```

### Database Statistics

The health endpoint provides operational metrics:

- Connection pool utilization
- Table operation counts
- Schema information
- Performance statistics

## Development

### Running Tests

```bash
python -m pytest tests/
```

### Database Migrations

For schema changes, modify the SQL files in `etl/sql/` and re-run:

```bash
python migrate_db.py
```

### Adding New Protocols

1. Update `defi_config.py` with protocol addresses and methods
2. Add ETL SQL in `etl/sql/` for protocol-specific tables
3. Update transaction analysis logic in `app.py`
4. Add database models in `database.py` if needed

## Troubleshooting

### Common Issues

#### Connection Errors
```
Error: could not connect to server
```
- Check PostgreSQL is running: `pg_ctl status`
- Verify connection settings in `.env`
- Test manually: `psql -h localhost -U postgres -d defi_warehouse`

#### Import Errors
```
ImportError: No module named 'psycopg2'
```
- Install binary package: `pip install psycopg2-binary`
- Or compile from source: `pip install psycopg2`

#### Permission Errors
```
ERROR: permission denied for schema core
```
- Grant permissions: `GRANT ALL ON SCHEMA core TO username;`
- Or run as database superuser

### Debug Mode

Enable SQL debugging in `.env`:

```env
SQL_DEBUG=true
```

This will log all SQL queries for troubleshooting.

## Production Deployment

### Database Configuration

- Use connection pooling (already configured)
- Set up read replicas for analytics queries
- Configure backup and recovery procedures
- Monitor connection limits and performance

### Security

- Use environment variables for credentials (never hardcode)
- Set up SSL/TLS for database connections
- Implement proper user permissions and access controls
- Regular security updates for PostgreSQL

### Scaling

- Partition large tables by date/chain_id
- Use async processing for heavy ETL workloads
- Consider separate databases for hot vs cold data
- Implement caching for frequently accessed data

## Support

For issues and questions:

1. Check the application logs: `logs/app.log`
2. Verify database connection: `python -c "from database import test_db_connection; print(test_db_connection())"`
3. Test ETL components: `cd etl && ./run_window.sh 42161 0 100`
4. Review this documentation and README.md

The integration is designed to be robust and will gracefully degrade if database features are unavailable, allowing the application to continue functioning in file-based mode.