#!/usr/bin/env python3
"""
Fetch earlier transactions that were missed.
Goes backwards from our earliest block to the token start block.
"""
import json
import time
from routescan_fetcher import RoutescanFetcher

def main():
    # Load existing transactions
    with open('transactions.json', 'r') as f:
        transactions = json.load(f)
    
    # Find our earliest block
    blocks = [int(tx.get('blockNumber', 0)) for tx in transactions if tx.get('blockNumber')]
    our_min_block = min(blocks)
    
    # Token started at this block
    token_start_block = 38699339
    
    print("=" * 80)
    print("FETCHING EARLIER TRANSACTIONS (BACKWARDS)")
    print("=" * 80)
    print(f"Token start block: {token_start_block:,}")
    print(f"Our earliest block: {our_min_block:,}")
    print(f"Gap: {our_min_block - token_start_block:,} blocks")
    print()
    
    if our_min_block <= token_start_block:
        print("✅ Already have all earlier transactions!")
        return
    
    # Fetch transactions from token start to our earliest
    fetcher = RoutescanFetcher()
    
    print(f"Fetching from block {token_start_block:,} to {our_min_block:,}...")
    print()
    
    new_transactions = fetcher.fetch_all_transactions(
        start_block=token_start_block,
        end_block=our_min_block - 1
    )
    
    if new_transactions:
        # Merge with existing (deduplicate by hash)
        existing_hashes = {tx.get('hash') for tx in transactions}
        unique_new = [tx for tx in new_transactions if tx.get('hash') not in existing_hashes]
        
        if unique_new:
            transactions.extend(unique_new)
            print(f"\n✅ Added {len(unique_new):,} new transactions")
            print(f"✅ Total now: {len(transactions):,} transactions")
            
            # Save with deduplication
            unique_txs = {}
            for tx in transactions:
                tx_hash = tx.get('hash')
                if tx_hash and tx_hash not in unique_txs:
                    unique_txs[tx_hash] = tx
            
            with open('transactions.json', 'w') as f:
                json.dump(list(unique_txs.values()), f)
            
            print(f"Saved {len(unique_txs):,} unique transactions")
    else:
        print("No new transactions found")

if __name__ == "__main__":
    main()
