#!/usr/bin/env python3
"""
Verify AERO tracking implementation and check if farming addresses have AERO activity
"""
import json
import os
import sys
import requests
import time
from typing import Dict, List

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import config

# AERO token address - need to verify this is correct
AERO_TOKEN_ADDRESS = "0x940181a94A35A4569E4529A3CDfB74e38FD98631"

def verify_aero_token_address():
    """Verify the AERO token address is correct"""
    print("=" * 80)
    print("VERIFYING AERO TOKEN ADDRESS")
    print("=" * 80)
    print()
    
    # Try to get token info
    params = {
        'module': 'token',
        'action': 'tokeninfo',
        'contractaddress': AERO_TOKEN_ADDRESS,
        'apikey': config.ROUTESCAN_API_KEY_AERO
    }
    
    try:
        response = requests.get(config.ROUTESCAN_API_URL, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == '1' and data.get('result'):
                result = data['result'][0] if isinstance(data['result'], list) else data['result']
                print(f"✅ Token Found:")
                print(f"   Name: {result.get('tokenName', 'N/A')}")
                print(f"   Symbol: {result.get('symbol', 'N/A')}")
                print(f"   Decimals: {result.get('divisor', 'N/A')}")
                print(f"   Total Supply: {result.get('totalSupply', 'N/A')}")
                return True
            else:
                print(f"❌ Token not found or error: {data.get('message', 'Unknown')}")
                return False
        else:
            print(f"❌ API Error: {response.status_code}")
            if response.status_code == 429:
                print("   Rate limited - waiting 10 seconds...")
                time.sleep(10)
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_aero_transfer_query(address: str):
    """Test querying AERO transfers for one address"""
    print()
    print("=" * 80)
    print(f"TESTING AERO TRANSFER QUERY FOR: {address}")
    print("=" * 80)
    print()
    
    # Query with a small block range first
    start_block = 38699339
    end_block = min(start_block + 100000, 40000000)  # 100k blocks
    
    params = {
        'module': 'account',
        'action': 'tokentx',
        'contractaddress': AERO_TOKEN_ADDRESS,
        'address': address,
        'startblock': start_block,
        'endblock': end_block,
        'page': 1,
        'offset': 10000,
        'sort': 'asc',
        'apikey': config.ROUTESCAN_API_KEY_AERO
    }
    
    try:
        print(f"Querying blocks {start_block:,} to {end_block:,}...")
        response = requests.get(config.ROUTESCAN_API_URL, params=params, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == '1' and data.get('message') == 'OK':
                transfers = data.get('result', [])
                print(f"✅ Found {len(transfers)} AERO transfers")
                
                if transfers:
                    print("\nSample transfers:")
                    for tx in transfers[:5]:
                        tx_from = tx.get('from', '')
                        tx_to = tx.get('to', '')
                        value = int(tx.get('value', 0)) / (10 ** int(tx.get('tokenDecimal', 18)))
                        direction = "INCOMING" if tx_to.lower() == address.lower() else "OUTGOING"
                        print(f"   {direction}: {value:.4f} AERO (Block: {tx.get('blockNumber', 'N/A')})")
                        print(f"      From: {tx_from[:10]}...{tx_from[-8:]}")
                        print(f"      To: {tx_to[:10]}...{tx_to[-8:]}")
                        print()
                else:
                    print("   No transfers found in this range")
                
                return len(transfers)
            elif data.get('status') == '0':
                error_msg = data.get('message', '')
                print(f"❌ API Error: {error_msg}")
                if 'rate limit' in error_msg.lower():
                    print("   Rate limited - need to wait")
                return 0
            else:
                print(f"❌ Unexpected response: {json.dumps(data, indent=2)}")
                return 0
        elif response.status_code == 429:
            print("❌ Rate limited (429)")
            return -1
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(response.text[:500])
            return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 0

def main():
    """Main verification function"""
    print("\n" + "=" * 80)
    print("AERO TRACKING VERIFICATION")
    print("=" * 80)
    print()
    
    # Step 1: Verify AERO token address
    if not verify_aero_token_address():
        print("\n⚠️  Could not verify AERO token address")
        print("   This might be the issue - address may be incorrect")
        return
    
    # Step 2: Load farming addresses
    if not os.path.exists('analysis_results.json'):
        print("\n❌ No analysis_results.json found")
        print("   Run main.py first to identify farming addresses")
        return
    
    with open('analysis_results.json', 'r') as f:
        results = json.load(f)
    
    farming_addresses = results.get('patterns', {}).get('farming_addresses', [])
    
    if not farming_addresses:
        print("\n❌ No farming addresses found")
        return
    
    print(f"\n✅ Found {len(farming_addresses)} farming addresses")
    
    # Step 3: Test query on first address
    test_address = farming_addresses[0]
    print(f"\nTesting with first farming address: {test_address}")
    
    transfer_count = test_aero_transfer_query(test_address)
    
    if transfer_count > 0:
        print(f"\n✅ SUCCESS: Found {transfer_count} AERO transfers")
        print("   The tracking implementation should work!")
    elif transfer_count == 0:
        print(f"\n⚠️  No transfers found for this address")
        print("   Possible reasons:")
        print("   1. Address hasn't received AERO rewards yet")
        print("   2. AERO token address is incorrect")
        print("   3. Query parameters need adjustment")
    else:
        print(f"\n⚠️  Rate limited - need to wait before testing")
    
    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()

