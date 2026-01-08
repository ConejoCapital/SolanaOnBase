#!/usr/bin/env python3
"""
Quick test to verify Basescan API integration
"""
import sys
import os

# Import from current directory first
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from basescan_fetcher import BasescanFetcher
import config

def main():
    print("=" * 80)
    print("BASESCAN API INTEGRATION TEST")
    print("=" * 80)
    print()
    
    print(f"API Key: {config.BASESCAN_API_KEY[:10]}...{config.BASESCAN_API_KEY[-5:]}")
    print(f"Token Address: {config.TOKEN_ADDRESS}")
    print()
    
    fetcher = BasescanFetcher()
    
    # Test 1: Check API connection (V2)
    print("Test 1: API V2 Connection")
    print("-" * 80)
    print(f"Using V2 endpoint: {fetcher.api_v2_url}")
    print(f"Chain ID: {fetcher.chain_id} (Base)")
    print()
    
    params = {
        'page': 1,
        'offset': 10,  # Just get 10 transactions for test
        'startblock': 38699339,  # First transaction block
        'endblock': 99999999
    }
    
    data = fetcher._make_request(params)
    
    if data:
        print("✅ API V2 connection successful!")
        transactions = data.get('result', [])
        print(f"   Found {len(transactions)} transactions in test query")
        
        if transactions:
            print("\n   Sample transaction:")
            sample = transactions[0]
            print(f"     Hash: {sample.get('hash', 'N/A')[:20]}...")
            print(f"     From: {sample.get('from', 'N/A')}")
            print(f"     To: {sample.get('to', 'N/A')}")
            print(f"     Value: {sample.get('value', 'N/A')}")
            print(f"     Block: {sample.get('blockNumber', 'N/A')}")
            print(f"     Timestamp: {sample.get('timeStamp', 'N/A')}")
            print(f"     Token: {sample.get('tokenSymbol', 'N/A')} ({sample.get('tokenName', 'N/A')})")
            
            # Test conversion
            converted = fetcher._convert_to_standard_format(sample)
            if converted:
                print("\n   ✅ Conversion to standard format successful!")
                print(f"     Standard format keys: {list(converted.keys())}")
        else:
            print("   ⚠️  No transactions returned (might be rate limited or no data)")
    else:
        print("❌ API connection failed!")
        print("   Check your API key and network connection")
        return False
    
    print()
    
    # Test 2: Fetch a small batch
    print("Test 2: Fetch Small Batch (100 transactions)")
    print("-" * 80)
    
    params = {
        'page': 1,
        'offset': 100,
        'startblock': 38699339,
        'endblock': 99999999
    }
    
    data = fetcher._make_request(params)
    
    if data:
        transactions = data.get('result', [])
        print(f"✅ Successfully fetched {len(transactions)} transactions")
        
        if len(transactions) > 0:
            # Check data quality
            has_hash = sum(1 for tx in transactions if tx.get('hash'))
            has_from = sum(1 for tx in transactions if tx.get('from'))
            has_to = sum(1 for tx in transactions if tx.get('to'))
            has_value = sum(1 for tx in transactions if tx.get('value'))
            
            print(f"\n   Data quality check:")
            print(f"     Has hash: {has_hash}/{len(transactions)}")
            print(f"     Has from: {has_from}/{len(transactions)}")
            print(f"     Has to: {has_to}/{len(transactions)}")
            print(f"     Has value: {has_value}/{len(transactions)}")
            
            if has_hash == len(transactions) and has_from == len(transactions):
                print("\n   ✅ All transactions have required fields!")
            else:
                print("\n   ⚠️  Some transactions missing fields")
    else:
        print("❌ Failed to fetch batch")
        return False
    
    print()
    print("=" * 80)
    print("✅ BASESCAN API INTEGRATION TEST PASSED!")
    print("=" * 80)
    print()
    print("The Basescan API is working correctly.")
    print("You can now run the full analysis using Basescan.")
    print()
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

