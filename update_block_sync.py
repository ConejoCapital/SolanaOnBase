#!/usr/bin/env python3
"""
Quick script to update block sync information in dashboard_export.json
Runs every 30 seconds to keep the dashboard current
"""
import json
import requests
import time
import sys

def update_block_sync():
    # Load existing dashboard data
    try:
        with open('dashboard_export.json', 'r') as f:
            dashboard_export = json.load(f)
    except:
        print("Error: dashboard_export.json not found")
        return
    
    # Load transactions to get current max block
    try:
        with open('transactions.json', 'r') as f:
            transactions = json.load(f)
    except:
        print("Error: transactions.json not found")
        return
    
    # Get block range
    blocks = [int(tx.get('blockNumber', 0)) for tx in transactions if tx.get('blockNumber')]
    hashes = set(tx.get('hash') for tx in transactions if tx.get('hash'))
    
    min_block = min(blocks) if blocks else 0
    max_block = max(blocks) if blocks else 0
    
    # Get current Base block
    api_key = "rs_65f982566a2ca518dfcd4c4e"
    api_url = "https://api.routescan.io/v2/network/mainnet/evm/8453/etherscan/api"
    
    params = {
        'module': 'proxy',
        'action': 'eth_blockNumber',
        'apikey': api_key
    }
    
    try:
        response = requests.get(api_url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'result' in data:
                current_base_block = int(data['result'], 16)
            else:
                current_base_block = 40550947  # Fallback
        else:
            current_base_block = 40550947  # Fallback
    except:
        current_base_block = 40550947  # Fallback
    
    # Calculate block sync progress
    token_start_block = 38699339
    blocks_synced = max_block - token_start_block
    total_blocks = current_base_block - token_start_block
    block_sync_percentage = (blocks_synced / total_blocks * 100) if total_blocks > 0 else 0
    
    # Update dashboard data
    dashboard_export['summary']['transactions_analyzed'] = len(hashes)
    dashboard_export['summary']['progress_percentage'] = round(len(hashes) / 1847723 * 100, 1)
    dashboard_export['summary']['block_sync'] = {
        'synced_block': max_block,
        'latest_base_block': current_base_block,
        'blocks_behind': current_base_block - max_block,
        'block_sync_percentage': round(block_sync_percentage, 1),
        'min_block': min_block,
        'token_start_block': token_start_block
    }
    
    # Save
    with open('dashboard_export.json', 'w') as f:
        json.dump(dashboard_export, f, indent=2)
    
    print(f"✅ Updated: {len(hashes):,} txs | Block {max_block:,} | Behind {current_base_block - max_block:,} | {block_sync_percentage:.1f}% synced")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--loop':
        print("Starting block sync updater (every 30 seconds)...")
        print("Press Ctrl+C to stop")
        while True:
            try:
                update_block_sync()
                time.sleep(30)
            except KeyboardInterrupt:
                print("\nStopping...")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(30)
    else:
        update_block_sync()
