#!/usr/bin/env python3
"""
Robust backfill script that properly handles:
1. API result limit (10,000 per query) by using adaptive block ranges
2. Gaps in data by systematically checking all blocks
3. Rate limiting with proper retry logic
"""
import requests
import json
import time
import os
from collections import defaultdict

# Configuration
TOKEN_ADDRESS = "0x311935cd80b76769bf2ecc9d8ab7635b2139cf82"
API_KEYS = ["rs_65f982566a2ca518dfcd4c4e", "rs_e1254323f750d4644cf0d772"]
API_URL = "https://api.routescan.io/v2/network/mainnet/evm/8453/etherscan/api"
TOKEN_START_BLOCK = 38699339
MAX_RESULTS_PER_QUERY = 10000
MIN_BLOCK_RANGE = 100  # Minimum block range to query
MAX_BLOCK_RANGE = 5000  # Start with 5k blocks, reduce if hitting limit (safer for dense blocks)

class RobustBackfiller:
    def __init__(self):
        self.api_keys = API_KEYS
        self.current_key_index = 0
        self.last_request_time = 0
        self.request_count = 0
        
    def _get_api_key(self):
        return self.api_keys[self.current_key_index]
    
    def _rotate_key(self):
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        print(f"  Rotated to API key {self.current_key_index + 1}/{len(self.api_keys)}")
    
    def _rate_limit_wait(self):
        """Ensure 1 second between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self.last_request_time = time.time()
    
    def _make_request(self, start_block, end_block, max_retries=3):
        """Make API request with retry logic"""
        self._rate_limit_wait()
        
        params = {
            'module': 'account',
            'action': 'tokentx',
            'contractaddress': TOKEN_ADDRESS,
            'startblock': start_block,
            'endblock': end_block,
            'page': 1,
            'offset': MAX_RESULTS_PER_QUERY,
            'sort': 'asc',
            'apikey': self._get_api_key()
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.get(API_URL, params=params, timeout=60)
                self.request_count += 1
                
                if response.status_code == 429:
                    print(f"   Rate limited, waiting 60s and rotating key...")
                    time.sleep(60)
                    self._rotate_key()
                    continue
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == '1' and data.get('message') == 'OK':
                        return data.get('result', [])
                    elif 'No transactions found' in str(data.get('message', '')):
                        return []
                    elif 'rate limit' in str(data).lower():
                        print(f"   Rate limit in response, waiting 60s...")
                        time.sleep(60)
                        self._rotate_key()
                        continue
                    else:
                        print(f"   API error: {data.get('message', 'Unknown')}")
                        return None
                else:
                    print(f"   HTTP {response.status_code}")
                    if attempt < max_retries - 1:
                        time.sleep(10 * (attempt + 1))
            except Exception as e:
                print(f"   Request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(10 * (attempt + 1))
        
        return None
    
    def fetch_range(self, start_block, end_block, block_range=MAX_BLOCK_RANGE):
        """
        Fetch transactions for a block range, automatically reducing range size
        if we hit the 10k result limit.
        """
        all_transactions = []
        current_start = start_block
        
        while current_start <= end_block:
            current_end = min(current_start + block_range - 1, end_block)
            
            print(f"  Querying blocks {current_start:,} to {current_end:,} (range: {current_end - current_start + 1:,})...", end=' ', flush=True)
            
            results = self._make_request(current_start, current_end)
            
            if results is None:
                print("FAILED")
                current_start = current_end + 1
                continue
            
            count = len(results)
            print(f"{count:,} txs", end='')
            
            if count >= MAX_RESULTS_PER_QUERY - 10:  # Close to or at limit
                # We likely hit the limit, need to use smaller range
                if block_range > MIN_BLOCK_RANGE:
                    new_range = max(block_range // 2, MIN_BLOCK_RANGE)
                    print(f"  HIT LIMIT! Retrying with smaller range ({new_range:,} blocks)")
                    # Don't add these results, re-fetch with smaller range
                    sub_results = self.fetch_range(current_start, current_end, new_range)
                    all_transactions.extend(sub_results)
                else:
                    # Already at minimum range, just add what we have
                    print(f"  At minimum range, some txs may be missing!")
                    all_transactions.extend(results)
            else:
                print()
                all_transactions.extend(results)
            
            current_start = current_end + 1
        
        return all_transactions
    
    def identify_gaps(self, transactions):
        """Find gaps in block coverage"""
        if not transactions:
            return [(TOKEN_START_BLOCK, None)]
        
        blocks = sorted(set(int(tx.get('blockNumber', 0)) for tx in transactions if tx.get('blockNumber')))
        
        gaps = []
        expected_start = TOKEN_START_BLOCK
        
        # Check gap at the beginning
        if blocks[0] > expected_start:
            gaps.append((expected_start, blocks[0] - 1))
        
        # Check gaps in the middle (only large gaps > 1000 blocks)
        for i in range(1, len(blocks)):
            gap_size = blocks[i] - blocks[i-1]
            if gap_size > 1000:  # Only report gaps > 1000 blocks
                gaps.append((blocks[i-1] + 1, blocks[i] - 1))
        
        return gaps
    
    def get_current_block(self):
        """Get current Base network block"""
        self._rate_limit_wait()
        try:
            params = {
                'module': 'proxy',
                'action': 'eth_blockNumber',
                'apikey': self._get_api_key()
            }
            response = requests.get(API_URL, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    return int(data['result'], 16)
        except Exception as e:
            print(f"Error getting block: {e}")
        return None
    
    def run_backfill(self, force_full=False):
        """Run the backfill process"""
        print("=" * 80)
        print(" ROBUST BACKFILL - SOL Token Transactions")
        print("=" * 80)
        print()
        
        # Load existing transactions
        existing_txs = []
        if os.path.exists('transactions.json') and not force_full:
            with open('transactions.json', 'r') as f:
                existing_txs = json.load(f)
            print(f"📂 Loaded {len(existing_txs):,} existing transactions")
        else:
            print("📂 Starting fresh (no existing data or force_full=True)")
        
        # Get current block
        current_block = self.get_current_block()
        if not current_block:
            print(" Could not get current block, using estimate")
            current_block = 40551000
        print(f" Current Base block: {current_block:,}")
        print(f" Token start block: {TOKEN_START_BLOCK:,}")
        print()
        
        # Create a set of existing hashes for deduplication
        existing_hashes = set(tx.get('hash') for tx in existing_txs if tx.get('hash'))
        
        # Identify gaps
        gaps = self.identify_gaps(existing_txs)
        
        if gaps:
            print(f" Found {len(gaps)} gaps to fill:")
            for start, end in gaps[:10]:  # Show first 10
                if end:
                    print(f"   Blocks {start:,} to {end:,} ({end - start + 1:,} blocks)")
                else:
                    print(f"   Blocks {start:,} to current")
            if len(gaps) > 10:
                print(f"   ... and {len(gaps) - 10} more gaps")
            print()
        
        # Get current max block in our data
        if existing_txs:
            current_max = max(int(tx.get('blockNumber', 0)) for tx in existing_txs if tx.get('blockNumber'))
        else:
            current_max = TOKEN_START_BLOCK - 1
        
        # Fetch missing data
        new_transactions = []
        
        # First, fill gaps
        for start, end in gaps:
            if end is None:
                end = current_max
            if end < start:
                continue
            
            print(f" Filling gap: blocks {start:,} to {end:,}")
            gap_txs = self.fetch_range(start, end)
            
            # Deduplicate
            for tx in gap_txs:
                if tx.get('hash') and tx.get('hash') not in existing_hashes:
                    new_transactions.append(tx)
                    existing_hashes.add(tx.get('hash'))
            
            print(f"   Added {len(gap_txs):,} transactions from this gap")
            print()
        
        # Then, fetch from current max to latest
        if current_max < current_block:
            print(f" Fetching new blocks: {current_max + 1:,} to {current_block:,}")
            new_txs = self.fetch_range(current_max + 1, current_block)
            
            for tx in new_txs:
                if tx.get('hash') and tx.get('hash') not in existing_hashes:
                    new_transactions.append(tx)
                    existing_hashes.add(tx.get('hash'))
            
            print(f"   Added {len(new_txs):,} new transactions")
            print()
        
        # Merge and save
        all_transactions = existing_txs + new_transactions
        
        # Final deduplication
        unique_txs = {}
        for tx in all_transactions:
            tx_hash = tx.get('hash')
            if tx_hash and tx_hash not in unique_txs:
                unique_txs[tx_hash] = tx
        
        final_txs = list(unique_txs.values())
        
        # Save
        with open('transactions.json', 'w') as f:
            json.dump(final_txs, f)
        
        print("=" * 80)
        print(" BACKFILL COMPLETE")
        print("=" * 80)
        print(f"   Previous count: {len(existing_txs):,}")
        print(f"   New transactions: {len(new_transactions):,}")
        print(f"   Total unique: {len(final_txs):,}")
        print(f"   API requests made: {self.request_count:,}")
        print()
        
        # Check coverage
        blocks = sorted(set(int(tx.get('blockNumber', 0)) for tx in final_txs if tx.get('blockNumber')))
        if blocks:
            print(f"   Block range: {min(blocks):,} to {max(blocks):,}")
            remaining_gaps = self.identify_gaps(final_txs)
            print(f"   Remaining gaps: {len(remaining_gaps)}")
        
        return final_txs

def main():
    backfiller = RobustBackfiller()
    backfiller.run_backfill()

if __name__ == "__main__":
    main()
