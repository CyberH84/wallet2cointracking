#!/usr/bin/env python3
"""
Test script to verify enhanced database integration
"""
import requests
import time
import json
from database import get_db_health, db_config
from sqlalchemy import text

def test_database_integration():
    """Test the enhanced database integration by running a transaction analysis"""
    
    print("🔍 Testing enhanced database integration...")
    
    # Check database health before test
    print("\n1. Database Health Check:")
    health = get_db_health()
    print(json.dumps(health, indent=2, default=str))
    
    # Check current transaction count
    print("\n2. Pre-test Transaction Count:")
    try:
        engine = db_config.initialize_engine()
        with engine.connect() as conn:
            tx_count = conn.execute(text("SELECT COUNT(*) FROM ethereum_transactions")).fetchone()[0]
            transfer_count = conn.execute(text("SELECT COUNT(*) FROM token_transfers")).fetchone()[0]
            analysis_count = conn.execute(text("SELECT COUNT(*) FROM wallet_analysis")).fetchone()[0]
            
            print(f"   Ethereum Transactions: {tx_count}")
            print(f"   Token Transfers: {transfer_count}")  
            print(f"   Wallet Analysis: {analysis_count}")
    except Exception as e:
        print(f"   Error checking counts: {e}")
    
    # Test wallet (known to have some transactions)
    test_wallet = "0x8ba1f109551bD432803012645Hac136c6" + "0066"  # Sample with transactions
    
    print(f"\n3. Starting transaction analysis for {test_wallet}...")
    
    # Start the job
    try:
        response = requests.post("http://127.0.0.1:5000/start_job", 
                               json={
                                   "wallet_address": test_wallet,
                                   "networks": ["arbitrum"]
                               })
    except requests.exceptions.RequestException:
        # Local server not running; skip this integration test in local runs
        import pytest

        pytest.skip("Local web server not available on 127.0.0.1:5000 — skipping integration test")
    
    if response.status_code != 200:
        print(f"   ❌ Failed to start job: {response.text}")
        return False
    
    job_data = response.json()
    job_id = job_data.get("job_id")
    print(f"   ✅ Job started with ID: {job_id}")
    
    # Monitor job progress
    print("\n4. Monitoring job progress...")
    max_wait = 300  # 5 minutes max
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        status_response = requests.get(f"http://127.0.0.1:5000/job_status/{job_id}")
        if status_response.status_code != 200:
            print("   ❌ Failed to get job status")
            return False
            
        status_data = status_response.json()
        status = status_data.get("status")
        
        print(f"   Status: {status}")
        
        if status == "completed":
            print("   ✅ Job completed successfully!")
            break
        elif status == "failed":
            error = status_data.get("error", "Unknown error")
            print(f"   ❌ Job failed: {error}")
            return False
        
        time.sleep(5)  # Check every 5 seconds
    else:
        print("   ⏰ Job timed out")
        return False
    
    # Check database after test
    print("\n5. Post-test Database Verification:")
    try:
        with engine.connect() as conn:
            tx_count_after = conn.execute(text("SELECT COUNT(*) FROM ethereum_transactions")).fetchone()[0]
            transfer_count_after = conn.execute(text("SELECT COUNT(*) FROM token_transfers")).fetchone()[0]
            analysis_count_after = conn.execute(text("SELECT COUNT(*) FROM wallet_analysis")).fetchone()[0]
            
            print(f"   Ethereum Transactions: {tx_count_after} (was {tx_count})")
            print(f"   Token Transfers: {transfer_count_after} (was {transfer_count})")
            print(f"   Wallet Analysis: {analysis_count_after} (was {analysis_count})")
            
            # Show sample data
            if tx_count_after > tx_count:
                print("\n   📋 Sample transaction data:")
                sample_tx = conn.execute(text("SELECT tx_hash, protocol, action_type FROM ethereum_transactions ORDER BY id DESC LIMIT 3")).fetchall()
                for tx in sample_tx:
                    print(f"      Hash: {tx[0][:10]}... Protocol: {tx[1]} Action: {tx[2]}")
            
            if analysis_count_after > analysis_count:
                print("\n   📊 Sample wallet analysis:")
                sample_analysis = conn.execute(text("SELECT wallet_address, total_transactions, defi_transactions, protocols_used FROM wallet_analysis ORDER BY id DESC LIMIT 1")).fetchone()
                if sample_analysis:
                    print(f"      Wallet: {sample_analysis[0][:10]}...")
                    print(f"      Total TX: {sample_analysis[1]}")
                    print(f"      DeFi TX: {sample_analysis[2]}")
                    print(f"      Protocols: {sample_analysis[3]}")
            
            success = (tx_count_after > tx_count or transfer_count_after > transfer_count or analysis_count_after > analysis_count)
            
            if success:
                print("\n   ✅ Database integration working! Data was stored successfully.")
            else:
                print("\n   ⚠️ No new data found in database - this may be expected if wallet had no transactions")
                
            return success
            
    except Exception as e:
        print(f"   ❌ Error verifying database: {e}")
        return False

if __name__ == "__main__":
    test_database_integration()