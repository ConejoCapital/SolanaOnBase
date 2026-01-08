#!/usr/bin/env python3
"""
Check if AERO token address is correct and find the actual AERO token
"""
import requests
import json
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import config

# Possible AERO token addresses to check
POSSIBLE_ADDRESSES = [
    "0x940181a94A35A4569E4529A3CDfB74e38FD98631",  # Current (might be router)
    "0x940181a94A35A4569E4529A3CDfB74e38FD98631",  # Need to find actual token
]

def check_token_info(address):
    """Check if address is a valid token"""
    params = {
        'module': 'token',
        'action': 'tokeninfo',
        'contractaddress': address,
        'apikey': config.ROUTESCAN_API_KEY_AERO
    }
    
    try:
        response = requests.get(config.ROUTESCAN_API_URL, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == '1' and data.get('result'):
                result = data['result'][0] if isinstance(data['result'], list) else data['result']
                return {
                    'valid': True,
                    'name': result.get('tokenName', ''),
                    'symbol': result.get('symbol', ''),
                    'decimals': result.get('divisor', ''),
                    'supply': result.get('totalSupply', '')
                }
        return {'valid': False, 'error': data.get('message', 'Unknown')}
    except Exception as e:
        return {'valid': False, 'error': str(e)}

def main():
    print("=" * 80)
    print("AERO TOKEN ADDRESS VERIFICATION")
    print("=" * 80)
    print()
    
    current_address = "0x940181a94A35A4569E4529A3CDfB74e38FD98631"
    
    print(f"Checking current address: {current_address}")
    print()
    
    result = check_token_info(current_address)
    
    if result.get('valid'):
        print(" Token Found:")
        print(f"   Name: {result.get('name')}")
        print(f"   Symbol: {result.get('symbol')}")
        print(f"   Decimals: {result.get('decimals')}")
        print(f"   Supply: {result.get('supply')}")
        print()
        
        if result.get('symbol', '').upper() == 'AERO':
            print(" This appears to be the correct AERO token!")
        else:
            print("  Symbol doesn't match 'AERO' - might be wrong address")
    else:
        print(f" Token not found: {result.get('error', 'Unknown error')}")
        print()
        print(" To find the correct AERO token address:")
        print("   1. Go to https://basedscan.io")
        print("   2. Search for 'AERO' or 'Aerodrome'")
        print("   3. Find the token contract (not router)")
        print("   4. Update AERO_TOKEN_ADDRESS in aero_tracker_basescan.py")

if __name__ == "__main__":
    main()

