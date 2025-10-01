#!/usr/bin/env python3
"""
Debug script to check Flask app variables and job data
"""
import requests
import sys

def check_flask_debug_info():
    """Check Flask app debug information"""
    try:
        # Add a simple endpoint to check variables
        response = requests.get("http://127.0.0.1:5000/debug_status")
        if response.status_code == 200:
            print("Flask debug info:", response.json())
        else:
            print(f"Debug endpoint not available: {response.status_code}")
    except Exception as e:
        print(f"Error checking Flask debug: {e}")

def check_latest_job():
    """Check the internal job data"""
    print("Checking latest job data...")
    
    # We know the job ID from previous test
    job_id = "99c2efa3-662f-4828-a5e9-b0d30ef9367a"
    
    # Try to access internal job data through a custom endpoint
    try:
        response = requests.get(f"http://127.0.0.1:5000/debug_job/{job_id}")
        if response.status_code == 200:
            debug_data = response.json()
            print(f"Job keys: {list(debug_data.keys())}")
            print(f"Has all_transactions: {debug_data.get('has_all_transactions', False)}")
            print(f"All transactions count: {debug_data.get('all_transactions_count', 0)}")
            print(f"DATABASE_ENABLED: {debug_data.get('database_enabled', False)}")
        else:
            print(f"Debug job endpoint not available: {response.status_code}")
    except Exception as e:
        print(f"Error checking job debug: {e}")

if __name__ == "__main__":
    check_flask_debug_info()
    check_latest_job()