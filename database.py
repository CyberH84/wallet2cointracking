"""
Database Configuration and Connection Management
Integrates with existing ETL pipeline in the etl/ folder
"""

import os
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Text, BigInteger, DateTime, Boolean, Numeric, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from dotenv import load_dotenv
from decimal import Decimal, getcontext

# Load environment variables from .env file
load_dotenv()

# Use high precision for Decimal arithmetic to avoid precision loss across conversions
getcontext().prec = 78


def parse_value_to_raw_and_scaled(value, decimals: int):
    """Parse a value that may be:
    - an integer/raw string (wei or raw token units)
    - a decimal/scientific string representing scaled token (e.g. '0.1156' or '2.08e-06')
    - a hex string (0x...)
    Returns (raw_int, Decimal(scaled_value)).
    This is safe to call from other modules/tests.
    """
    try:
        if value is None:
            return 0, Decimal(0)

        # Already an int
        if isinstance(value, int):
            raw = int(value)
            scaled = Decimal(raw) / (Decimal(10) ** decimals) if decimals is not None else Decimal(raw)
            return raw, scaled

        s = str(value).strip()
        if s == '':
            return 0, Decimal(0)

        # Hex encoded integer
        if s.startswith('0x') or s.startswith('0X'):
            try:
                raw = int(s, 16)
                scaled = Decimal(raw) / (Decimal(10) ** decimals) if decimals is not None else Decimal(raw)
                return raw, scaled
            except Exception:
                pass

        # If it looks like a decimal/scientific notation -> treat as scaled amount
        if ('.' in s) or ('e' in s) or ('E' in s):
            try:
                dec = Decimal(s)
                raw = int((dec * (Decimal(10) ** int(decimals or 0))).to_integral_value())
                return raw, dec
            except Exception:
                pass

        # Otherwise try integer parse
        try:
            raw = int(s)
            scaled = Decimal(raw) / (Decimal(10) ** int(decimals or 0)) if decimals is not None else Decimal(raw)
            return raw, scaled
        except Exception:
            # Fallback to Decimal parsing
            dec = Decimal(s)
            raw = int((dec * (Decimal(10) ** int(decimals or 0))).to_integral_value())
            return raw, dec

    except Exception as e:
        logger.warning(f"Failed to parse value '{value}' with decimals={decimals}: {e}")
        return 0, Decimal(0)

# Configure logging
logger = logging.getLogger(__name__)

# Database Models Base
Base = declarative_base()

class DatabaseConfig:
    """Database configuration management"""
    
    def __init__(self):
        self.database_url = self._get_database_url()
        self.engine = None
        self.SessionLocal = None
        self.metadata = MetaData()
        
    def _get_database_url(self) -> str:
        """Get database URL from environment variables"""
        # Try different environment variable names for flexibility
        db_url = (
            os.getenv('DATABASE_URL') or 
            os.getenv('PGURL') or 
            os.getenv('POSTGRES_URL')
        )
        
        if not db_url:
            # Build from individual components if not found
            host = os.getenv('DB_HOST', 'localhost')
            port = os.getenv('DB_PORT', '5432')
            database = os.getenv('DB_NAME', 'defi_warehouse')
            username = os.getenv('DB_USER', 'postgres')
            password = os.getenv('DB_PASSWORD', '')
            
            if password:
                db_url = f"postgresql://{username}:{password}@{host}:{port}/{database}"
            else:
                db_url = f"postgresql://{username}@{host}:{port}/{database}"
        
        logger.info(f"Database URL configured: {db_url.replace(':' + db_url.split(':')[2].split('@')[0], ':***')}")
        return db_url
    
    def initialize_engine(self):
        """Initialize SQLAlchemy engine with connection pooling"""
        if self.engine is None:
            self.engine = create_engine(
                self.database_url,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=os.getenv('SQL_DEBUG', 'false').lower() == 'true'
            )
            
            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            logger.info("Database engine initialized successfully")
        
        return self.engine
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            engine = self.initialize_engine()
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                return result.fetchone()[0] == 1
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    @contextmanager
    def get_session(self):
        """Get database session with automatic cleanup"""
        if self.SessionLocal is None:
            self.initialize_engine()
        
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

# Global database configuration instance
db_config = DatabaseConfig()

class EthereumTransaction(Base):
    """Ethereum transaction model"""
    __tablename__ = 'ethereum_transactions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_id = Column(Integer, nullable=False)
    tx_hash = Column(String(66), nullable=False, unique=True)
    block_number = Column(BigInteger, nullable=False)
    block_time = Column(DateTime(timezone=True), nullable=False)
    from_address = Column(String(42), nullable=False)
    to_address = Column(String(42))
    value = Column(Numeric(78, 0), nullable=False)
    gas_used = Column(BigInteger)
    gas_price = Column(BigInteger)
    status = Column(Integer, nullable=False)
    input_data = Column(Text)
    logs = Column(JSON)
    protocol = Column(String(50))
    action_type = Column(String(50))
    processed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<EthereumTransaction(tx_hash='{self.tx_hash}', chain_id={self.chain_id})>"

class TokenTransfer(Base):
    """Token transfer model"""
    __tablename__ = 'token_transfers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_id = Column(Integer, nullable=False)
    tx_hash = Column(String(66), nullable=False)
    log_index = Column(Integer, nullable=False)
    block_number = Column(BigInteger, nullable=False)
    block_time = Column(DateTime(timezone=True), nullable=False)
    token_address = Column(String(42), nullable=False)
    from_address = Column(String(42), nullable=False)
    to_address = Column(String(42), nullable=False)
    value_raw = Column(Numeric(78, 0), nullable=False)
    value_scaled = Column(Numeric(38, 18))
    token_symbol = Column(String(20))
    token_name = Column(String(100))
    token_decimals = Column(Integer)
    usd_value = Column(Numeric(20, 8))
    protocol = Column(String(50))
    processed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<TokenTransfer(tx_hash='{self.tx_hash}', token='{self.token_symbol}')>"

class WalletAnalysis(Base):
    """Wallet analysis and summary model"""
    __tablename__ = 'wallet_analysis'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_address = Column(String(42), nullable=False)
    chain_id = Column(Integer, nullable=False)
    analysis_date = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    total_transactions = Column(Integer, nullable=False)
    defi_transactions = Column(Integer, nullable=False)
    total_volume_usd = Column(Numeric(20, 8))
    protocols_used = Column(JSON)
    token_portfolio = Column(JSON)
    risk_score = Column(Numeric(5, 2))
    last_activity = Column(DateTime(timezone=True))
    
    def __repr__(self):
        return f"<WalletAnalysis(wallet='{self.wallet_address}', chain_id={self.chain_id})>"

class DatabaseManager:
    """High-level database operations manager"""
    
    def __init__(self):
        self.db_config = db_config
    
    def initialize_database(self) -> bool:
        """Initialize database with schemas and tables"""
        try:
            engine = self.db_config.initialize_engine()
            # Create all tables
            # NOTE: Unique indexes required for ON CONFLICT upserts are managed via Alembic migrations
            # and should NOT be created at runtime. Use the migration: alembic upgrade head
            Base.metadata.create_all(bind=engine)
            
            # Initialize ETL schemas if they don't exist
            with engine.connect() as conn:
                conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))
                conn.execute(text("CREATE SCHEMA IF NOT EXISTS stage"))
                conn.execute(text("CREATE SCHEMA IF NOT EXISTS core"))
                conn.execute(text("CREATE SCHEMA IF NOT EXISTS marts"))
                conn.commit()
            
            logger.info("Database initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return False
    
    def run_etl_initialization(self) -> bool:
        """Run ETL SQL initialization scripts"""
        try:
            engine = self.db_config.initialize_engine()
            etl_sql_path = os.path.join(os.path.dirname(__file__), 'etl', 'sql')
            
            # List of SQL files to execute in order
            sql_files = [
                '00_init_schemas.sql',
                '02_seed_chains.sql',
                '03_seed_contracts_arbitrum.sql',
                '03_seed_contracts_flare.sql',
                '10_amount_scaling_helpers.sql'
            ]
            
            with engine.connect() as conn:
                for sql_file in sql_files:
                    file_path = os.path.join(etl_sql_path, sql_file)
                    if os.path.exists(file_path):
                        logger.info(f"Executing ETL script: {sql_file}")
                        with open(file_path, 'r') as f:
                            sql_content = f.read()
                            # Split by statements and execute each
                            statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
                            for statement in statements:
                                try:
                                    conn.execute(text(statement))
                                except Exception as e:
                                    logger.warning(f"Warning executing statement in {sql_file}: {e}")
                conn.commit()
            
            logger.info("ETL initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"ETL initialization failed: {e}")
            return False
    
    def get_wallet_summary(self, wallet_address: str, chain_id: int) -> Optional[Dict[str, Any]]:
        """Get wallet summary from database"""
        try:
            with self.db_config.get_session() as session:
                # Get latest analysis
                analysis = session.query(WalletAnalysis).filter(
                    WalletAnalysis.wallet_address == wallet_address.lower(),
                    WalletAnalysis.chain_id == chain_id
                ).order_by(WalletAnalysis.analysis_date.desc()).first()
                
                if analysis:
                    return {
                        'wallet_address': analysis.wallet_address,
                        'chain_id': analysis.chain_id,
                        'total_transactions': analysis.total_transactions,
                        'defi_transactions': analysis.defi_transactions,
                        'total_volume_usd': float(analysis.total_volume_usd) if analysis.total_volume_usd else 0,
                        'protocols_used': analysis.protocols_used,
                        'token_portfolio': analysis.token_portfolio,
                        'risk_score': float(analysis.risk_score) if analysis.risk_score else 0,
                        'last_activity': analysis.last_activity.isoformat() if analysis.last_activity else None,
                        'analysis_date': analysis.analysis_date.isoformat()
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting wallet summary: {e}")
            return None
    
    def store_transactions(self, transactions: List[Dict[str, Any]], wallet_analysis: Dict[str, Any] = None) -> bool:
        """Store processed transactions and wallet analysis in database"""
        try:
            engine = self.db_config.initialize_engine()
            # Prepare batch insert for ethereum_transactions using ON CONFLICT upsert
            if transactions:
                tx_params = []
                tt_params = []
                # Use module-level Decimal parser
                # getcontext().prec is already configured at module import
                for tx_data in transactions:
                    try:
                        # Parse timestamp as UTC-aware datetime
                        block_time = datetime.fromtimestamp(int(tx_data.get('timeStamp', 0)), tz=timezone.utc)
                    except Exception:
                        block_time = datetime.now(timezone.utc)

                    processed_at = datetime.now(timezone.utc)

                    # Convert transaction value to raw integer (wei) and scaled Decimal (ETH)
                    try:
                        tx_value_raw, tx_value_scaled = parse_value_to_raw_and_scaled(tx_data.get('value'), 18)
                    except Exception:
                        tx_value_raw, tx_value_scaled = 0, Decimal(0)

                    tx_params.append({
                        'chain_id': tx_data.get('chain_id'),
                        'tx_hash': tx_data.get('hash'),
                        'block_number': tx_data.get('blockNumber'),
                        'block_time': block_time,
                        'from_address': (tx_data.get('from') or '').lower(),
                        'to_address': (tx_data.get('to') or '').lower(),
                        'value': tx_value_raw,
                        'gas_used': int(tx_data.get('gasUsed') or 0),
                        'gas_price': int(tx_data.get('gasPrice') or 0),
                        'status': int(tx_data.get('txreceipt_status') or 1),
                        'input_data': tx_data.get('input'),
                        'logs': json.dumps(tx_data.get('logs') or []),
                        'protocol': tx_data.get('protocol'),
                        'action_type': tx_data.get('action_type'),
                        'processed_at': processed_at
                    })

                    # Flatten token transfers
                    for transfer in tx_data.get('token_transfers', []):
                        try:
                            # Determine token decimals (fallback to 18)

                            token_decimals = int(transfer.get('tokenDecimal') or transfer.get('token_decimals') or 18)

                            # Parse transfer value which may be scaled decimal (e.g. '0.1156'), scientific, hex, or raw integer string
                            raw_val, scaled_val = parse_value_to_raw_and_scaled(transfer.get('value'), token_decimals)

                            tt_params.append({
                                'chain_id': tx_data.get('chain_id'),
                                'tx_hash': tx_data.get('hash'),
                                'log_index': int(transfer.get('log_index', 0)),
                                'block_number': tx_data.get('blockNumber'),
                                'block_time': block_time,
                                'token_address': (transfer.get('contractAddress') or transfer.get('tokenAddress') or '').lower(),
                                'from_address': (transfer.get('from') or '').lower(),
                                'to_address': (transfer.get('to') or '').lower(),
                                'value_raw': raw_val,
                                'value_scaled': scaled_val,
                                'token_symbol': transfer.get('tokenSymbol'),
                                'token_name': transfer.get('tokenName'),
                                'token_decimals': token_decimals,
                                'usd_value': transfer.get('usd_value'),
                                'protocol': tx_data.get('protocol'),
                                'processed_at': processed_at
                            })
                        except Exception:
                            logger.exception("Skipping malformed token transfer during DB store")
                            continue

                # Build SQL for ethereum_transactions upsert
                eth_sql = text("""
                INSERT INTO ethereum_transactions (
                    chain_id, tx_hash, block_number, block_time, from_address, to_address, value,
                    gas_used, gas_price, status, input_data, logs, protocol, action_type, processed_at
                ) VALUES (
                    :chain_id, :tx_hash, :block_number, :block_time, :from_address, :to_address, :value,
                    :gas_used, :gas_price, :status, :input_data, :logs, :protocol, :action_type, :processed_at
                )
                ON CONFLICT (tx_hash) DO UPDATE SET
                    block_number = EXCLUDED.block_number,
                    block_time = EXCLUDED.block_time,
                    from_address = EXCLUDED.from_address,
                    to_address = EXCLUDED.to_address,
                    value = EXCLUDED.value,
                    gas_used = EXCLUDED.gas_used,
                    gas_price = EXCLUDED.gas_price,
                    status = EXCLUDED.status,
                    input_data = EXCLUDED.input_data,
                    logs = EXCLUDED.logs,
                    protocol = EXCLUDED.protocol,
                    action_type = EXCLUDED.action_type,
                    processed_at = EXCLUDED.processed_at;
                """)

                # Build SQL for token_transfers upsert (requires unique index on tx_hash, log_index)
                tt_sql = text("""
                INSERT INTO token_transfers (
                    chain_id, tx_hash, log_index, block_number, block_time, token_address,
                    from_address, to_address, value_raw, value_scaled, token_symbol, token_name,
                    token_decimals, usd_value, protocol, processed_at
                ) VALUES (
                    :chain_id, :tx_hash, :log_index, :block_number, :block_time, :token_address,
                    :from_address, :to_address, :value_raw, :value_scaled, :token_symbol, :token_name,
                    :token_decimals, :usd_value, :protocol, :processed_at
                )
                ON CONFLICT (tx_hash, log_index) DO UPDATE SET
                    block_number = EXCLUDED.block_number,
                    block_time = EXCLUDED.block_time,
                    token_address = EXCLUDED.token_address,
                    from_address = EXCLUDED.from_address,
                    to_address = EXCLUDED.to_address,
                    value_raw = EXCLUDED.value_raw,
                    value_scaled = EXCLUDED.value_scaled,
                    token_symbol = EXCLUDED.token_symbol,
                    token_name = EXCLUDED.token_name,
                    token_decimals = EXCLUDED.token_decimals,
                    usd_value = EXCLUDED.usd_value,
                    protocol = EXCLUDED.protocol,
                    processed_at = EXCLUDED.processed_at;
                """)

                # Execute batch inserts
                with engine.begin() as conn:
                    # Unique indexes for ON CONFLICT upserts are managed by Alembic migrations
                    # (alembic/versions/20251001_create_upsert_indexes.py). Do not create them at
                    # runtime in production; they were previously created defensively for local
                    # development runs only.

                    if tx_params:
                        conn.execute(eth_sql, tx_params)
                    if tt_params:
                        conn.execute(tt_sql, tt_params)

            # Upsert wallet analysis if provided
            if wallet_analysis:
                try:
                    engine = self.db_config.initialize_engine()
                    wa = wallet_analysis
                    # Ensure chain_id is set (use 0 for cross-network aggregate) because wallet_analysis.chain_id is NOT NULL in schema
                    wa_chain_id = wa.get('chain_id') if wa.get('chain_id') is not None else 0
                    wa_stmt = text("""
                    INSERT INTO wallet_analysis (
                        wallet_address, chain_id, analysis_date, total_transactions,
                        defi_transactions, total_volume_usd, protocols_used, token_portfolio, risk_score, last_activity
                    ) VALUES (
                        :wallet_address, :chain_id, :analysis_date, :total_transactions,
                        :defi_transactions, :total_volume_usd, :protocols_used, :token_portfolio, :risk_score, :last_activity
                    )
                    ON CONFLICT (wallet_address, chain_id) DO UPDATE SET
                        analysis_date = EXCLUDED.analysis_date,
                        total_transactions = EXCLUDED.total_transactions,
                        defi_transactions = EXCLUDED.defi_transactions,
                        total_volume_usd = EXCLUDED.total_volume_usd,
                        protocols_used = EXCLUDED.protocols_used,
                        token_portfolio = EXCLUDED.token_portfolio,
                        risk_score = EXCLUDED.risk_score,
                        last_activity = EXCLUDED.last_activity;
                    """)

                    # Ensure analysis_date is timezone-aware UTC
                    analysis_date = wa.get('analysis_date')
                    if isinstance(analysis_date, datetime) and analysis_date.tzinfo is None:
                        analysis_date = analysis_date.replace(tzinfo=timezone.utc)
                    if analysis_date is None:
                        analysis_date = datetime.now(timezone.utc)

                    last_activity = wa.get('last_activity')
                    if isinstance(last_activity, datetime) and last_activity.tzinfo is None:
                        last_activity = last_activity.replace(tzinfo=timezone.utc)

                    wa_params = {
                        'wallet_address': wa.get('wallet_address', '').lower(),
                        'chain_id': wa_chain_id,
                        'analysis_date': analysis_date,
                        'total_transactions': wa.get('total_transactions', 0),
                        'defi_transactions': wa.get('defi_transactions', 0),
                        'total_volume_usd': wa.get('total_volume_usd'),
                        'protocols_used': json.dumps(wa.get('protocols_used') or {}),
                        'token_portfolio': json.dumps(wa.get('token_portfolio') or {}),
                        'risk_score': wa.get('risk_score'),
                        'last_activity': last_activity
                    }

                    with engine.begin() as conn:
                        conn.execute(wa_stmt, wa_params)
                except Exception as e_wa:
                    logger.error(f"Error upserting wallet analysis: {e_wa}")

            logger.info(f"Stored {len(transactions)} transactions in database")
            if wallet_analysis:
                logger.info(f"Stored wallet analysis for {wallet_analysis.get('wallet_address')}")
            return True

        except Exception as e:
            logger.error(f"Error storing transactions (upsert path): {e}")
            return False
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get database health status"""
        try:
            engine = self.db_config.initialize_engine()
            
            with engine.connect() as conn:
                # Test basic connectivity
                conn.execute(text("SELECT 1"))
                
                # Get database info
                db_info = conn.execute(text("SELECT version()")).fetchone()
                
                # Get table counts from core schema
                table_counts = {}
                try:
                    counts_query = """
                    SELECT 
                        schemaname,
                        tablename,
                        n_tup_ins + n_tup_upd + n_tup_del as total_operations
                    FROM pg_stat_user_tables 
                    WHERE schemaname IN ('core', 'public')
                    ORDER BY total_operations DESC
                    LIMIT 10
                    """
                    result = conn.execute(text(counts_query))
                    table_counts = {f"{row[0]}.{row[1]}": row[2] for row in result}
                except Exception:
                    table_counts = {"info": "Statistics not available"}
                
                return {
                    'status': 'healthy',
                    'database_version': db_info[0] if db_info else 'Unknown',
                    'connection_pool_size': self.db_config.engine.pool.size() if self.db_config.engine else 0,
                    'table_operations': table_counts,
                    'etl_schemas': ['raw', 'stage', 'core', 'marts']
                }
        
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

# Global database manager instance
db_manager = DatabaseManager()

# Utility functions for easy access
def get_db_session():
    """Get database session - convenience function"""
    return db_config.get_session()

def test_db_connection() -> bool:
    """Test database connection - convenience function"""
    return db_config.test_connection()

def initialize_db() -> bool:
    """Initialize database - convenience function"""
    return db_manager.initialize_database()

def get_db_health() -> Dict[str, Any]:
    """Get database health status - convenience function"""
    return db_manager.get_health_status()