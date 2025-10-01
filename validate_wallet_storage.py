#!/usr/bin/env python3
"""
Complete validation script for wallet database storage
"""
import requests
import time
import json
from database import db_config
from sqlalchemy import text

def validate_wallet_database_storage():
    """Complete validation of wallet database storage"""
    
    wallet_address = "0xb3a2f25d7956f96703c9ed3ce6ea25e4d47295d3"
    print(f"🔍 Validating database storage for wallet: {wallet_address}")
    
    # Step 1: Check initial database state
    print("\n📊 Step 1: Initial Database State")
    try:
        engine = db_config.initialize_engine()
        with engine.connect() as conn:
            initial_tx_count = conn.execute(text("SELECT COUNT(*) FROM ethereum_transactions")).fetchone()[0]
            initial_transfer_count = conn.execute(text("SELECT COUNT(*) FROM token_transfers")).fetchone()[0]
            initial_analysis_count = conn.execute(text("SELECT COUNT(*) FROM wallet_analysis")).fetchone()[0]
            
            print(f"   Initial Transactions: {initial_tx_count}")
            print(f"   Initial Token Transfers: {initial_transfer_count}")
            print(f"   Initial Wallet Analysis: {initial_analysis_count}")
    except Exception as e:
        print(f"   ❌ Error checking initial state: {e}")
        return False
    
    # Step 2: Start wallet analysis job
    print(f"\n🚀 Step 2: Starting Wallet Analysis")
    try:
        response = requests.post("http://127.0.0.1:5000/start_job", 
                               json={
                                   "wallet_address": wallet_address,
                                   "networks": ["flare"]
                               })
        
        if response.status_code != 200:
            print(f"   ❌ Failed to start job: {response.status_code} - {response.text}")
            return False
            
        job_data = response.json()
        job_id = job_data.get("job_id")
        print(f"   ✅ Job started successfully: {job_id}")
        
    except Exception as e:
        print(f"   ❌ Error starting job: {e}")
        return False
    
    # Step 3: Monitor job progress
    print(f"\n⏳ Step 3: Monitoring Job Progress")
    max_wait = 300  # 5 minutes
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            status_response = requests.get(f"http://127.0.0.1:5000/job_status/{job_id}")
            if status_response.status_code != 200:
                print(f"   ❌ Failed to get job status: {status_response.status_code}")
                return False
                
            status_data = status_response.json()
            status = status_data.get("status")
            progress = status_data.get("progress", {})
            
            print(f"   Status: {status} | Progress: {progress}")
            
            if status == "completed":
                print("   ✅ Job completed successfully!")
                break
            elif status == "failed":
                error = status_data.get("error", "Unknown error")
                print(f"   ❌ Job failed: {error}")
                return False
            
            time.sleep(5)
        except Exception as e:
            print(f"   ❌ Error monitoring job: {e}")
            return False
    else:
        print("   ⏰ Job timed out")
        return False
    
    # Step 4: Verify CSV generation
    print(f"\n📄 Step 4: Verifying CSV Generation")
    try:
        csv_response = requests.get(f"http://127.0.0.1:5000/download/{job_id}")
        if csv_response.status_code == 200:
            csv_lines = len(csv_response.text.split('\n'))
            print(f"   ✅ CSV generated with {csv_lines} lines")
            transactions_count = csv_lines - 1  # Subtract header
            print(f"   📊 Transactions processed: {transactions_count}")
        else:
            print(f"   ❌ Failed to download CSV: {csv_response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error checking CSV: {e}")
        return False
    
    # Step 5: Validate database storage
    print(f"\n🗄️  Step 5: Validating Database Storage")
    try:
        with engine.connect() as conn:
            # Check final counts
            final_tx_count = conn.execute(text("SELECT COUNT(*) FROM ethereum_transactions")).fetchone()[0]
            final_transfer_count = conn.execute(text("SELECT COUNT(*) FROM token_transfers")).fetchone()[0]
            final_analysis_count = conn.execute(text("SELECT COUNT(*) FROM wallet_analysis")).fetchone()[0]
            
            print(f"   Final Transactions: {final_tx_count} (was {initial_tx_count})")
            print(f"   Final Token Transfers: {final_transfer_count} (was {initial_transfer_count})")
            print(f"   Final Wallet Analysis: {final_analysis_count} (was {initial_analysis_count})")
            
            # Check wallet-specific data
            wallet_txs = conn.execute(text("""
                SELECT COUNT(*) FROM ethereum_transactions 
                WHERE from_address = :wallet OR to_address = :wallet
            """), {"wallet": wallet_address.lower()}).fetchone()[0]
            
            wallet_transfers = conn.execute(text("""
                SELECT COUNT(*) FROM token_transfers 
                WHERE from_address = :wallet OR to_address = :wallet
            """), {"wallet": wallet_address.lower()}).fetchone()[0]
            
            wallet_analysis_records = conn.execute(text("""
                SELECT COUNT(*) FROM wallet_analysis 
                WHERE wallet_address = :wallet
            """), {"wallet": wallet_address.lower()}).fetchone()[0]
            
            print(f"   Wallet Transactions: {wallet_txs}")
            print(f"   Wallet Token Transfers: {wallet_transfers}")
            print(f"   Wallet Analysis Records: {wallet_analysis_records}")
            
            # Show sample data if available
            if wallet_txs > 0:
                print(f"\n   📝 Sample Transaction Data:")
                sample_txs = conn.execute(text("""
                    SELECT tx_hash, protocol, action_type, block_time, chain_id
                    FROM ethereum_transactions 
                    WHERE from_address = :wallet OR to_address = :wallet
                    ORDER BY block_time DESC LIMIT 3
                """), {"wallet": wallet_address.lower()}).fetchall()
                
                for tx in sample_txs:
                    print(f"     Hash: {tx[0][:10]}... | Protocol: {tx[1]} | Action: {tx[2]} | Chain: {tx[4]}")
            
            if wallet_analysis_records > 0:
                print(f"\n   📈 Wallet Analysis Data:")
                analysis = conn.execute(text("""
                    SELECT total_transactions, defi_transactions, protocols_used, total_volume_usd
                    FROM wallet_analysis 
                    WHERE wallet_address = :wallet
                    ORDER BY analysis_date DESC LIMIT 1
                """), {"wallet": wallet_address.lower()}).fetchone()
                
                if analysis:
                    print(f"     Total Transactions: {analysis[0]}")
                    print(f"     DeFi Transactions: {analysis[1]}")
                    print(f"     Protocols Used: {analysis[2]}")
                    print(f"     Total Volume USD: {analysis[3]}")
            
            # Determine validation result
            data_stored = (
                (final_tx_count > initial_tx_count) or 
                (final_transfer_count > initial_transfer_count) or
                (wallet_analysis_records > 0)
            )
            
            if data_stored:
                print(f"\n✅ VALIDATION SUCCESSFUL: Wallet data was stored in database!")
                return True
            else:
                print(f"\n❌ VALIDATION FAILED: No wallet data found in database")
                return False
                
    except Exception as e:
        print(f"   ❌ Error validating database: {e}")
        return False

if __name__ == "__main__":
    success = validate_wallet_database_storage()
    print(f"\n{'='*60}")
    if success:
        print("🎉 DATABASE INTEGRATION VALIDATION: PASSED")
    else:
        print("💥 DATABASE INTEGRATION VALIDATION: FAILED")
    print(f"{'='*60}")