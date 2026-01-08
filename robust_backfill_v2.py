#!/usr/bin/env python3
"""
Robust backfill script v2 with:
1. Live status updates for dashboard
2. No pauses - continuous operation
3. Automatic recovery from errors
"""
import requests
import json
import tempfile
import shutil
import time
import os
from datetime import datetime
from collections import defaultdict

# Configuration
TOKEN_ADDRESS = "0x311935cd80b76769bf2ecc9d8ab7635b2139cf82"
API_KEYS = ["rs_65f982566a2ca518dfcd4c4e", "rs_e1254323f750d4644cf0d772"]
API_URL = "https://api.routescan.io/v2/network/mainnet/evm/8453/etherscan/api"
TOKEN_START_BLOCK = 38699339
MAX_RESULTS_PER_QUERY = 10000
MIN_BLOCK_RANGE = 100
MAX_BLOCK_RANGE = 5000
STATUS_FILE = "backfill_status.json"

class RobustBackfillerV2:
    def __init__(self):
        self.api_keys = API_KEYS
        self.current_key_index = 0
        self.last_request_time = 0
        self.request_count = 0
        self.transactions_fetched = 0
        self.errors = []
        self.current_gap = ""
        self.gaps_remaining = 0
        self.start_time = time.time()
        
    def update_status(self, status, current_block=0, target_block=0, extra=None):
        """Write current status to JSON file for dashboard"""
        status_data = {
            "is_running": True,
            "status": status,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "current_block": current_block,
            "target_block": target_block,
            "transactions_fetched": self.transactions_fetched,
            "current_gap": self.current_gap,
            "gaps_remaining": self.gaps_remaining,
            "api_requests": self.request_count,
            "errors": self.errors[-5:],  # Last 5 errors
            "last_activity": extra or "",
            "uptime_seconds": int(time.time() - self.start_time),
            "requests_per_minute": round(self.request_count / max(1, (time.time() - self.start_time) / 60), 1)
        }
        try:
            with open(STATUS_FILE, 'w') as f:
                json.dump(status_data, f, indent=2)
        except Exception as e:
            print(f"Error writing status: {e}")
    
    def mark_stopped(self, reason="completed"):
        """Mark backfill as stopped"""
        status_data = {
            "is_running": False,
            "status": reason,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "current_block": 0,
            "target_block": 0,
            "transactions_fetched": self.transactions_fetched,
            "current_gap": "",
            "gaps_remaining": 0,
            "api_requests": self.request_count,
            "errors": self.errors[-5:],
            "last_activity": f"Stopped: {reason}",
            "uptime_seconds": int(time.time() - self.start_time),
            "requests_per_minute": 0
        }
        try:
            with open(STATUS_FILE, 'w') as f:
                json.dump(status_data, f, indent=2)
        except:
            pass
        
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
    
    def _make_request(self, start_block, end_block, max_retries=5):
        """Make API request with retry logic - NO PAUSES, just retries"""
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
                    error_msg = f"Rate limited at block {start_block}"
                    self.errors.append(error_msg)
                    print(f"  ⚠️ Rate limited, rotating key and waiting 30s...")
                    self._rotate_key()
                    time.sleep(30)  # Shorter wait, then retry
                    continue
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == '1' and data.get('message') == 'OK':
                        return data.get('result', [])
                    elif 'No transactions found' in str(data.get('message', '')):
                        return []
                    elif 'rate limit' in str(data).lower():
                        self._rotate_key()
                        time.sleep(30)
                        continue
                    else:
                        error_msg = f"API error: {data.get('message', 'Unknown')}"
                        self.errors.append(error_msg)
                        print(f"  ⚠️ {error_msg}")
                        return None
                else:
                    error_msg = f"HTTP {response.status_code}"
                    self.errors.append(error_msg)
                    print(f"  ⚠️ {error_msg}")
                    if attempt < max_retries - 1:
                        time.sleep(5 * (attempt + 1))
            except Exception as e:
                error_msg = f"Request error: {str(e)[:50]}"
                self.errors.append(error_msg)
                print(f"  ⚠️ {error_msg}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
        
        return None
    
    def fetch_range(self, start_block, end_block, block_range=MAX_BLOCK_RANGE):
        """Fetch transactions for a block range with adaptive sizing"""
        all_transactions = []
        current_start = start_block
        
        while current_start <= end_block:
            current_end = min(current_start + block_range - 1, end_block)
            
            # Update status
            self.update_status(
                "fetching",
                current_block=current_start,
                target_block=end_block,
                extra=f"Blocks {current_start:,} to {current_end:,}"
            )
            
            print(f"  Querying blocks {current_start:,} to {current_end:,} (range: {current_end - current_start + 1:,})...", end=' ', flush=True)
            
            results = self._make_request(current_start, current_end)
            
            if results is None:
                print("FAILED - will retry later")
                # Don't skip, add to retry list
                current_start = current_end + 1
                continue
            
            count = len(results)
            print(f"{count:,} txs", end='')
            
            if count >= MAX_RESULTS_PER_QUERY - 10:
                if block_range > MIN_BLOCK_RANGE:
                    new_range = max(block_range // 2, MIN_BLOCK_RANGE)
                    print(f" ⚠️ HIT LIMIT! Retrying with {new_range:,} blocks")
                    sub_results = self.fetch_range(current_start, current_end, new_range)
                    all_transactions.extend(sub_results)
                    self.transactions_fetched += len(sub_results)
                else:
                    print(f" ⚠️ At minimum range!")
                    all_transactions.extend(results)
                    self.transactions_fetched += count
            else:
                print()
                all_transactions.extend(results)
                self.transactions_fetched += count
            
            current_start = current_end + 1
        
        return all_transactions
    
    def identify_gaps(self, transactions):
        """Find gaps in block coverage"""
        if not transactions:
            return [(TOKEN_START_BLOCK, None)]
        
        blocks = sorted(set(int(tx.get('blockNumber', 0)) for tx in transactions if tx.get('blockNumber')))
        
        gaps = []
        expected_start = TOKEN_START_BLOCK
        
        if blocks[0] > expected_start:
            gaps.append((expected_start, blocks[0] - 1))
        
        for i in range(1, len(blocks)):
            gap_size = blocks[i] - blocks[i-1]
            if gap_size > 1000:
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
    
    def save_transactions(self, existing_txs, new_transactions):
        """Save transactions with deduplication using ATOMIC write"""
        all_transactions = existing_txs + new_transactions
        
        # Deduplicate
        unique_txs = {}
        for tx in all_transactions:
            tx_hash = tx.get('hash')
            if tx_hash and tx_hash not in unique_txs:
                unique_txs[tx_hash] = tx
        
        final_txs = list(unique_txs.values())
        
        # ATOMIC WRITE: Write to temp file first, then rename
        try:
            fd, temp_path = tempfile.mkstemp(suffix='.json', dir='.')
            with os.fdopen(fd, 'w') as f:
                json.dump(final_txs, f)
            # Atomic rename
            shutil.move(temp_path, 'transactions.json')
        except Exception as e:
            print(f"Error saving: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        return final_txs
    
    def run_continuous(self):
        """Run backfill continuously - never stop"""
        print("=" * 80)
        print("🔄 ROBUST BACKFILL V2 - Continuous Mode")
        print("=" * 80)
        print()
        
        self.update_status("starting")
        
        while True:
            try:
                # Load existing transactions
                existing_txs = []
                if os.path.exists('transactions.json'):
                    with open('transactions.json', 'r') as f:
                        existing_txs = json.load(f)
                    print(f"📂 Loaded {len(existing_txs):,} existing transactions")
                
                # Get current block
                current_block = self.get_current_block()
                if not current_block:
                    print("❌ Could not get current block, using estimate")
                    current_block = 40600000
                print(f"📊 Current Base block: {current_block:,}")
                
                # Create hash set for deduplication
                existing_hashes = set(tx.get('hash') for tx in existing_txs if tx.get('hash'))
                
                # Identify gaps
                gaps = self.identify_gaps(existing_txs)
                self.gaps_remaining = len(gaps)
                
                if gaps:
                    print(f"🔍 Found {len(gaps)} gaps to fill")
                else:
                    print("✅ No gaps found!")
                
                # Get current max block
                if existing_txs:
                    current_max = max(int(tx.get('blockNumber', 0)) for tx in existing_txs if tx.get('blockNumber'))
                else:
                    current_max = TOKEN_START_BLOCK - 1
                
                new_transactions = []
                
                # Fill gaps
                for i, (start, end) in enumerate(gaps):
                    if end is None:
                        end = current_max
                    if end < start:
                        continue
                    
                    self.current_gap = f"Gap {i+1}/{len(gaps)}: {start:,} to {end:,}"
                    self.gaps_remaining = len(gaps) - i
                    self.update_status("filling_gap", start, end, self.current_gap)
                    
                    print(f"\n📥 Filling gap {i+1}/{len(gaps)}: blocks {start:,} to {end:,}")
                    gap_txs = self.fetch_range(start, end)
                    
                    for tx in gap_txs:
                        if tx.get('hash') and tx.get('hash') not in existing_hashes:
                            new_transactions.append(tx)
                            existing_hashes.add(tx.get('hash'))
                    
                    print(f"   Added {len(gap_txs):,} transactions")
                    
                    # Save periodically
                    if len(new_transactions) > 10000:
                        print("💾 Saving progress...")
                        existing_txs = self.save_transactions(existing_txs, new_transactions)
                        new_transactions = []
                
                # Fetch new blocks
                if current_max < current_block:
                    self.current_gap = f"New blocks: {current_max + 1:,} to {current_block:,}"
                    self.update_status("fetching_new", current_max + 1, current_block, self.current_gap)
                    
                    print(f"\n📥 Fetching new blocks: {current_max + 1:,} to {current_block:,}")
                    new_txs = self.fetch_range(current_max + 1, current_block)
                    
                    for tx in new_txs:
                        if tx.get('hash') and tx.get('hash') not in existing_hashes:
                            new_transactions.append(tx)
                            existing_hashes.add(tx.get('hash'))
                    
                    print(f"   Added {len(new_txs):,} new transactions")
                
                # Final save
                if new_transactions:
                    final_txs = self.save_transactions(existing_txs, new_transactions)
                    print(f"\n✅ Total unique transactions: {len(final_txs):,}")
                else:
                    final_txs = existing_txs
                
                # Check if caught up
                blocks = [int(tx.get('blockNumber', 0)) for tx in final_txs if tx.get('blockNumber')]
                max_saved_block = max(blocks) if blocks else 0
                
                if max_saved_block >= current_block - 100:
                    print(f"\n✅ Caught up! Waiting 60 seconds for new blocks...")
                    self.update_status("caught_up", max_saved_block, current_block, "Waiting for new blocks")
                    time.sleep(60)
                else:
                    # Still have work to do
                    print(f"\n🔄 Continuing... (at block {max_saved_block:,}, target {current_block:,})")
                    time.sleep(5)
                    
            except KeyboardInterrupt:
                print("\n⏹️ Stopping...")
                self.mark_stopped("user_stopped")
                break
            except Exception as e:
                error_msg = f"Main loop error: {str(e)[:100]}"
                self.errors.append(error_msg)
                print(f"\n❌ Error: {e}")
                print("   Retrying in 30 seconds...")
                self.update_status("error", extra=error_msg)
                time.sleep(30)

def main():
    backfiller = RobustBackfillerV2()
    backfiller.run_continuous()

if __name__ == "__main__":
    main()
