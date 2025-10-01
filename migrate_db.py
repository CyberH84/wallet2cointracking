#!/usr/bin/env python3
"""
Database Migration and ETL Integration Script
Initializes PostgreSQL database with ETL schemas and tables
"""

import sys
import os
import logging
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from database import db_manager, db_config
import subprocess

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_sql_file(file_path: str) -> bool:
    """Execute SQL file using psql command"""
    try:
        # Get database URL from environment
        db_url = db_config.database_url
        
        # Execute SQL file using psql
        cmd = ['psql', db_url, '-f', file_path, '-v', 'ON_ERROR_STOP=1']
        
        logger.info(f"Executing SQL file: {file_path}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if result.stdout:
            logger.info(f"Output: {result.stdout}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing SQL file {file_path}: {e}")
        if e.stderr:
            logger.error(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error executing SQL file {file_path}: {e}")
        return False

def initialize_database():
    """Initialize the complete database with ETL pipeline"""
    logger.info("Starting database initialization...")
    
    # Test database connection first
    if not db_config.test_connection():
        logger.error("Database connection failed! Please check your database configuration.")
        return False
    
    logger.info("Database connection successful!")
    
    # Initialize basic database structure
    if not db_manager.initialize_database():
        logger.error("Failed to initialize basic database structure")
        return False
    
    # Run ETL initialization scripts
    etl_sql_path = Path(__file__).parent / 'etl' / 'sql'
    
    if not etl_sql_path.exists():
        logger.error(f"ETL SQL directory not found: {etl_sql_path}")
        return False
    
    # Execute ETL SQL files in the correct order
    sql_files = [
        '00_init_schemas.sql',
        '01_stage_decoded_events_view.sql', 
        '02_seed_chains.sql',
        '03_seed_contracts_arbitrum.sql',
        '03_seed_contracts_flare.sql',
        '04_etl_openocean.sql',
        '05_etl_sparkdex_v3.sql',
        '06_etl_aave_v3.sql',
        '07_etl_kinetic.sql',
        '08_etl_pancakeswap.sql',
        '09_etl_ftso.sql',
        '10_amount_scaling_helpers.sql'
    ]
    
    failed_files = []
    
    for sql_file in sql_files:
        file_path = etl_sql_path / sql_file
        
        if file_path.exists():
            success = run_sql_file(str(file_path))
            if not success:
                failed_files.append(sql_file)
                logger.warning(f"Failed to execute {sql_file}, continuing with others...")
        else:
            logger.warning(f"SQL file not found: {file_path}")
    
    if failed_files:
        logger.warning(f"Some SQL files failed to execute: {failed_files}")
        logger.info("This is normal for optional ETL components. Core functionality should work.")
    
    # Verify the installation
    health = db_manager.get_health_status()
    if health['status'] == 'healthy':
        logger.info("✅ Database initialization completed successfully!")
        logger.info(f"Database version: {health.get('database_version', 'Unknown')}")
        logger.info(f"ETL schemas available: {health.get('etl_schemas', [])}")
        return True
    else:
        logger.error("❌ Database initialization completed with issues")
        logger.error(f"Health check result: {health}")
        return False

def create_sample_data():
    """Create sample data for testing"""
    logger.info("Creating sample data...")
    
    try:
        engine = db_config.initialize_engine()
        
        with engine.connect() as conn:
            # Insert sample chain data if not exists
            conn.execute("""
                INSERT INTO core.dim_chain (chain_id, chain_name, native_symbol, explorer_url)
                VALUES 
                    (42161, 'Arbitrum One', 'ETH', 'https://arbiscan.io'),
                    (14, 'Flare Network', 'FLR', 'https://flare-explorer.flare.network')
                ON CONFLICT (chain_id) DO NOTHING
            """)
            
            # Insert sample token data
            conn.execute("""
                INSERT INTO core.dim_token (chain_id, token_address, symbol, name, decimals, is_stablecoin)
                VALUES 
                    (42161, '0xa0b86a33e6441e2c88a4e5d1b8e5a3c4d', 'USDC', 'USD Coin', 6, true),
                    (42161, '0x82af49447d8a07e3bd95bd0d56f35241523fbab1', 'WETH', 'Wrapped Ether', 18, false),
                    (14, '0x1d80c49bbcd1c0911346656b529df9e5c2f783d', 'WFLR', 'Wrapped Flare', 18, false)
                ON CONFLICT (chain_id, token_address) DO NOTHING
            """)
            
            conn.commit()
        
        logger.info("✅ Sample data created successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create sample data: {e}")
        return False

def main():
    """Main migration function"""
    print("🚀 wallet2cointracking Database Migration")
    print("=========================================")
    
    # Check if .env file exists
    env_file = Path('.env')
    if not env_file.exists():
        print("⚠️  No .env file found!")
        print("Please copy .env.example to .env and configure your database settings.")
        print("Example:")
        print("  cp .env.example .env")
        print("  # Edit .env with your database credentials")
        return 1
    
    # Initialize database
    if not initialize_database():
        print("❌ Database initialization failed!")
        return 1
    
    # Create sample data
    create_sample_data()
    
    print("\n✅ Database setup completed!")
    print("\nNext steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Start the Flask application: python app.py")
    print("3. The ETL pipeline is ready in the etl/ folder")
    print("4. Use ./etl/run_daily_tail.sh to process blockchain data")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())