#!/usr/bin/env python3
"""
Check if farming addresses are known infrastructure (bridges, routers, DEXs, LPs)
"""
import requests
import json
import sys
import os
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import config

# The 14 farming addresses
FARMING_ADDRESSES = [
    '0xa87a233e8a7d8951ff790a2e39738086cb5f71b7',
    '0xdb0253708c484ac5b6710b3b6ee7ac896f643d33',
    '0xcbcfdaaae40d3466f0c68dc73f8fc6cf29e6c988',
    '0xab7ae77b7df5f10caaaca6049abe1d05416b680d',
    '0x88fec94eb9f11376e0dcb31ea7babc278d6035c3',
    '0x416ec2ca21a38cbcfeacd6a14532b3f348356d23',
    '0x0ac583ce7fcd7d6de77d340abac18e7ff20e1f5f',
    '0x55606779f4c08fb988fbcd83539278b676d5bd9c',
    '0x802b65b5d9016621e66003aed0b16615093f328b',
    '0xecbe25d69f0bc85c8eb42ae9a3b9a212dced96e6',
    '0xa343e6d005cbe3adf1cb8325ac2b59ddf25b30ac',
    '0x3a32d2987b86a9c5552921289b8d4470075d360f',
    '0x7c460d504c1600fb8c030ff0d3b7e02bab268309',
    '0x1113a2bc6c237083183b9db29410d93f0077e501',
]

def check_address_on_basescan(address):
    """Check if address has a label on Basescan"""
    # We can't directly query Basescan API for labels, but we can check transaction patterns
    # For now, we'll use the API to get basic info
    params = {
        'module': 'account',
        'action': 'txlist',
        'address': address,
        'startblock': 0,
        'endblock': 99999999,
        'page': 1,
        'offset': 1,
        'sort': 'asc',
        'apikey': config.ROUTESCAN_API_KEY
    }
    
    try:
        response = requests.get(config.ROUTESCAN_API_URL, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == '1':
                return {
                    'has_txs': len(data.get('result', [])) > 0,
                    'tx_count': len(data.get('result', []))
                }
        return None
    except Exception as e:
        return {'error': str(e)}

def check_address_pattern(address, transactions_data):
    """Analyze address pattern to determine if it's infrastructure"""
    # This would require transaction data
    # For now, return basic info
    return {
        'address': address,
        'check_url': f'https://basedscan.io/address/{address}'
    }

def main():
    print("=" * 80)
    print("CHECKING FARMING ADDRESSES FOR INFRASTRUCTURE LABELS")
    print("=" * 80)
    print()
    
    print("Checking 14 addresses...")
    print("Note: Manual verification needed on Basedscan")
    print()
    
    for i, addr in enumerate(FARMING_ADDRESSES, 1):
        print(f"{i}. {addr}")
        print(f"   Check: https://basedscan.io/address/{addr}")
        
        # Basic check
        info = check_address_on_basescan(addr)
        if info:
            if info.get('has_txs'):
                print(f"    Has transactions")
            if info.get('error'):
                print(f"     Error: {info['error']}")
        
        time.sleep(0.5)  # Rate limit protection
        print()
    
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print()
    print("1. Manually check each address on Basedscan for labels")
    print("2. Look for patterns:")
    print("   - High transaction count with many unique counterparties = Router/DEX")
    print("   - Regular patterns with few counterparties = Possible farming")
    print("   - Contract addresses = Likely infrastructure")
    print("3. Check if addresses are:")
    print("   - Contract addresses (not EOA)")
    print("   - Known bridges (Base Bridge, Wormhole, etc.)")
    print("   - Known routers (Aerodrome, Uniswap, etc.)")
    print("   - Liquidity pools")
    print()

if __name__ == "__main__":
    main()

