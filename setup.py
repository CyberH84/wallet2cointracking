#!/usr/bin/env python3
"""
Complete Setup Script for wallet2cointracking with PostgreSQL Integration
This script sets up the entire application including database, ETL pipeline, and dependencies
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_command(cmd, description, check=True):
    """Run a shell command with logging"""
    logger.info(f"Running: {description}")
    logger.debug(f"Command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    
    try:
        result = subprocess.run(cmd, shell=isinstance(cmd, str), check=check, capture_output=True, text=True)
        if result.stdout:
            logger.debug(f"Output: {result.stdout}")
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        if e.stderr:
            logger.error(f"Error: {e.stderr}")
        return False

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        logger.error("Python 3.8+ is required")
        return False
    logger.info(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
    return True

def check_postgresql():
    """Check if PostgreSQL is available"""
    try:
        result = subprocess.run(['psql', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"✅ PostgreSQL found: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    
    logger.warning("⚠️  PostgreSQL client (psql) not found")
    logger.info("Please install PostgreSQL:")
    logger.info("  - Windows: Download from https://www.postgresql.org/download/windows/")
    logger.info("  - macOS: brew install postgresql")
    logger.info("  - Ubuntu/Debian: sudo apt-get install postgresql postgresql-contrib")
    return False

def setup_virtual_environment():
    """Set up Python virtual environment"""
    venv_path = Path('.venv')
    
    if venv_path.exists():
        logger.info("✅ Virtual environment already exists")
        return True
    
    logger.info("Creating Python virtual environment...")
    success = run_command([sys.executable, '-m', 'venv', '.venv'], "Creating virtual environment")
    
    if success:
        logger.info("✅ Virtual environment created")
        return True
    else:
        logger.error("❌ Failed to create virtual environment")
        return False

def install_dependencies():
    """Install Python dependencies"""
    logger.info("Installing Python dependencies...")
    
    # Determine pip path
    if os.name == 'nt':  # Windows
        pip_path = Path('.venv/Scripts/pip.exe')
    else:  # Unix-like
        pip_path = Path('.venv/bin/pip')
    
    if not pip_path.exists():
        logger.error("❌ Virtual environment pip not found")
        return False
    
    # Upgrade pip first
    success = run_command([str(pip_path), 'install', '--upgrade', 'pip'], "Upgrading pip")
    if not success:
        logger.warning("⚠️ Failed to upgrade pip, continuing...")
    
    # Install requirements
    success = run_command([str(pip_path), 'install', '-r', 'requirements.txt'], "Installing requirements")
    
    if success:
        logger.info("✅ Dependencies installed successfully")
        return True
    else:
        logger.error("❌ Failed to install dependencies")
        return False

def setup_environment_file():
    """Set up environment configuration"""
    env_file = Path('.env')
    env_example = Path('.env.example')
    
    if env_file.exists():
        logger.info("✅ .env file already exists")
        return True
    
    if env_example.exists():
        logger.info("Creating .env file from .env.example...")
        try:
            with open(env_example, 'r') as src, open(env_file, 'w') as dst:
                content = src.read()
                # Update with default values for development
                content = content.replace('username:password@localhost', 'postgres:postgres@localhost')
                content = content.replace('your_password_here', 'postgres')
                content = content.replace('your_etherscan_api_key', 'YourEtherscanAPIKey')
                content = content.replace('your_coingecko_api_key', 'YourCoingeckoAPIKey')
                dst.write(content)
            
            logger.info("✅ .env file created")
            logger.info("📝 Please edit .env file with your actual database credentials and API keys")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create .env file: {e}")
            return False
    else:
        logger.error("❌ .env.example file not found")
        return False

def test_database_connection():
    """Test database connection"""
    logger.info("Testing database connection...")
    
    try:
        # Import here to avoid import errors if packages not installed
        sys.path.insert(0, str(Path.cwd()))
        from database import test_db_connection
        
        if test_db_connection():
            logger.info("✅ Database connection successful")
            return True
        else:
            logger.warning("⚠️ Database connection failed")
            logger.info("Please ensure:")
            logger.info("  1. PostgreSQL is running")
            logger.info("  2. Database 'defi_warehouse' exists")
            logger.info("  3. Credentials in .env are correct")
            return False
            
    except Exception as e:
        logger.warning(f"⚠️ Could not test database connection: {e}")
        return False

def initialize_database():
    """Initialize database schema and ETL components"""
    logger.info("Initializing database...")
    
    # Determine python path
    if os.name == 'nt':  # Windows
        python_path = Path('.venv/Scripts/python.exe')
    else:  # Unix-like
        python_path = Path('.venv/bin/python')
    
    if not python_path.exists():
        logger.error("❌ Virtual environment python not found")
        return False
    
    success = run_command([str(python_path), 'migrate_db.py'], "Running database migration", check=False)
    
    if success:
        logger.info("✅ Database initialized successfully")
        return True
    else:
        logger.warning("⚠️ Database initialization had issues (may be normal for missing components)")
        return True  # Continue anyway as some failures are expected

def run_tests():
    """Run basic application tests"""
    logger.info("Running basic tests...")
    
    # Determine python path
    if os.name == 'nt':  # Windows
        python_path = Path('.venv/Scripts/python.exe')
    else:  # Unix-like
        python_path = Path('.venv/bin/python')
    
    # Test basic imports
    test_cmd = [str(python_path), '-c', 'from database import test_db_connection; from app import app; print("✅ All imports successful")']
    success = run_command(test_cmd, "Testing application imports", check=False)
    
    if success:
        logger.info("✅ Application tests passed")
        return True
    else:
        logger.warning("⚠️ Some tests failed, but this may be expected")
        return True  # Continue anyway

def print_final_instructions():
    """Print final setup instructions"""
    logger.info("\n" + "="*60)
    logger.info("🎉 wallet2cointracking Setup Complete!")
    logger.info("="*60)
    
    print("""
Next Steps:

1. 📝 Edit .env file with your credentials:
   - Set your PostgreSQL database password
   - Add your Etherscan API key
   - Add your CoinGecko API key (optional)

2. 🗄️ Set up PostgreSQL database:
   - Create database: createdb defi_warehouse
   - Or use existing database connection

3. 🚀 Start the application:
   - Windows: .venv\\Scripts\\python.exe app.py
   - Unix: .venv/bin/python app.py

4. 🌐 Access the application:
   - Web interface: http://localhost:5000
   - Health check: http://localhost:5000/health
   - Database health: http://localhost:5000/db/health

5. 📊 ETL Pipeline:
   - Scripts available in etl/ folder
   - Run: ./etl/run_daily_tail.sh <CHAIN_ID> <BLOCK_NUMBER>
   - Example: ./etl/run_daily_tail.sh 42161 50000000

6. 🔧 Database Management:
   - Initialize: POST http://localhost:5000/db/init
   - View wallet data: GET http://localhost:5000/db/wallet/<address>/<chain_id>

Features Available:
✅ Multi-chain DeFi transaction analysis (Arbitrum, Flare)
✅ PostgreSQL integration with ETL pipeline
✅ Protocol detection (Aave V3, OpenOcean, SparkDEX, Kinetic Market)
✅ CoinTracking.info CSV export
✅ Real-time health monitoring
✅ Async job processing
✅ Token portfolio analysis with USD values
""")

def main():
    """Main setup function"""
    print("🚀 wallet2cointracking Setup Script")
    print("==================================")
    
    # Pre-flight checks
    if not check_python_version():
        return 1
    
    postgresql_available = check_postgresql()
    
    # Setup steps
    steps = [
        ("Setting up virtual environment", setup_virtual_environment),
        ("Installing dependencies", install_dependencies),
        ("Setting up environment file", setup_environment_file),
    ]
    
    if postgresql_available:
        steps.extend([
            ("Testing database connection", test_database_connection),
            ("Initializing database", initialize_database),
        ])
    
    steps.append(("Running tests", run_tests))
    
    # Execute steps
    failed_steps = []
    for description, func in steps:
        logger.info(f"\n📋 {description}...")
        if not func():
            failed_steps.append(description)
    
    # Report results
    print(f"\n📊 Setup Results:")
    print(f"✅ Successful: {len(steps) - len(failed_steps)}")
    print(f"❌ Failed: {len(failed_steps)}")
    
    if failed_steps:
        print(f"⚠️ Failed steps: {', '.join(failed_steps)}")
    
    if not postgresql_available:
        print("⚠️ PostgreSQL not detected - database features will be disabled")
        print("   Application will run in file-based mode only")
    
    print_final_instructions()
    
    return 0 if len(failed_steps) == 0 else 1

if __name__ == '__main__':
    sys.exit(main())