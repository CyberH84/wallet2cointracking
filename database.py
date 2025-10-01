"""
Database Configuration and Connection Management
Integrates with existing ETL pipeline in the etl/ folder
"""

import os
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Text, BigInteger, DateTime, Boolean, Numeric, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from datetime import datetime
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
    block_time = Column(DateTime, nullable=False)
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
    processed_at = Column(DateTime, default=datetime.utcnow)
    
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
    block_time = Column(DateTime, nullable=False)
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
    processed_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<TokenTransfer(tx_hash='{self.tx_hash}', token='{self.token_symbol}')>"

class WalletAnalysis(Base):
    """Wallet analysis and summary model"""
    __tablename__ = 'wallet_analysis'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_address = Column(String(42), nullable=False)
    chain_id = Column(Integer, nullable=False)
    analysis_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    total_transactions = Column(Integer, nullable=False)
    defi_transactions = Column(Integer, nullable=False)
    total_volume_usd = Column(Numeric(20, 8))
    protocols_used = Column(JSON)
    token_portfolio = Column(JSON)
    risk_score = Column(Numeric(5, 2))
    last_activity = Column(DateTime)
    
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
            with self.db_config.get_session() as session:
                for tx_data in transactions:
                    # Store main transaction
                    tx = EthereumTransaction(
                        chain_id=tx_data.get('chain_id'),
                        tx_hash=tx_data.get('hash'),
                        block_number=tx_data.get('blockNumber'),
                        block_time=datetime.fromtimestamp(int(tx_data.get('timeStamp', 0))),
                        from_address=tx_data.get('from', '').lower(),
                        to_address=tx_data.get('to', '').lower(),
                        value=int(tx_data.get('value', 0)),
                        gas_used=int(tx_data.get('gasUsed', 0)),
                        gas_price=int(tx_data.get('gasPrice', 0)),
                        status=int(tx_data.get('txreceipt_status', 1)),
                        input_data=tx_data.get('input'),
                        logs=tx_data.get('logs'),
                        protocol=tx_data.get('protocol'),
                        action_type=tx_data.get('action_type')
                    )
                    
                    # Use merge to handle duplicates
                    session.merge(tx)
                    
                    # Store token transfers if available
                    if 'token_transfers' in tx_data:
                        for transfer in tx_data['token_transfers']:
                            token_transfer = TokenTransfer(
                                chain_id=tx_data.get('chain_id'),
                                tx_hash=tx_data.get('hash'),
                                log_index=transfer.get('log_index', 0),
                                block_number=tx_data.get('blockNumber'),
                                block_time=datetime.fromtimestamp(int(tx_data.get('timeStamp', 0))),
                                token_address=transfer.get('contractAddress', '').lower(),
                                from_address=transfer.get('from', '').lower(),
                                to_address=transfer.get('to', '').lower(),
                                value_raw=int(transfer.get('value', 0)),
                                value_scaled=transfer.get('value_scaled'),
                                token_symbol=transfer.get('tokenSymbol'),
                                token_name=transfer.get('tokenName'),
                                token_decimals=int(transfer.get('tokenDecimal', 0)),
                                usd_value=transfer.get('usd_value'),
                                protocol=tx_data.get('protocol')
                            )
                            session.merge(token_transfer)
                
                # Store wallet analysis if provided
                if wallet_analysis:
                    analysis = WalletAnalysis(
                        wallet_address=wallet_analysis.get('wallet_address', '').lower(),
                        chain_id=wallet_analysis.get('chain_id'),
                        total_transactions=wallet_analysis.get('total_transactions', 0),
                        defi_transactions=wallet_analysis.get('defi_transactions', 0),
                        total_volume_usd=wallet_analysis.get('total_volume_usd'),
                        protocols_used=wallet_analysis.get('protocols_used', {}),
                        token_portfolio=wallet_analysis.get('token_portfolio', {}),
                        risk_score=wallet_analysis.get('risk_score'),
                        last_activity=wallet_analysis.get('last_activity')
                    )
                    session.merge(analysis)
                
                session.commit()
                
            logger.info(f"Stored {len(transactions)} transactions in database")
            if wallet_analysis:
                logger.info(f"Stored wallet analysis for {wallet_analysis.get('wallet_address')}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing transactions: {e}")
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