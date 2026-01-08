"""
Fetcher for Base blockchain transactions using Routescan/Basedscan API
Free API alternative to Basescan - https://basedscan.io/documentation/api
"""
import requests
import time
import json
from typing import List, Dict, Optional
from tqdm import tqdm
import config

class RoutescanFetcher:
    def __init__(self):
        # Use both API keys for rotation (reduces rate limit impact)
        self.api_keys = [config.ROUTESCAN_API_KEY, config.ROUTESCAN_API_KEY_AERO]
        self.current_key_index = 0
        self.api_key = self.api_keys[0]
        self.api_url = config.ROUTESCAN_API_URL
        self.token_address = config.TOKEN_ADDRESS.lower()
        # Rate limiting: VERY CONSERVATIVE to avoid 429 errors
        # Routescan free tier = 2 requests per second, 10,000 per day
        # Use 1 request per second to be very safe (with rotation between keys)
        self.min_request_interval = 1.0  # 1 second = 1 req/sec (very conservative)
        self.last_request_time = 0
        self.consecutive_rate_limits = 0
        # Track daily requests to avoid hitting 10k limit
        self.daily_request_count = 0
        self.max_daily_requests = 8000  # Stay well under 10k limit
    
    def _rotate_api_key(self):
        """Rotate to next API key"""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.api_key = self.api_keys[self.current_key_index]
        print(f"  Rotated to API key {self.current_key_index + 1}/{len(self.api_keys)}")
        
    def _rate_limit_wait(self):
        """Ensure we respect 2 requests per second limit"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def _make_request(self, params: Dict) -> Optional[Dict]:
        """
        Make request to Routescan API
        Uses standard Etherscan-compatible API format
        Respects 2 requests per second rate limit
        """
        # Rate limit: ensure we wait at least 0.6 seconds between requests
        self._rate_limit_wait()
        
        # Build request parameters (standard Etherscan format)
        request_params = {
            'module': 'account',
            'action': 'tokentx',
            'contractaddress': self.token_address,
            'apikey': self.api_key,
            'sort': 'asc'
        }
        
        # Add optional parameters if provided
        if 'page' in params:
            request_params['page'] = params['page']
        if 'offset' in params:
            request_params['offset'] = params['offset']
        if 'startblock' in params:
            request_params['startblock'] = params['startblock']
        if 'endblock' in params:
            request_params['endblock'] = params['endblock']
        
        try:
            response = requests.get(self.api_url, params=request_params, timeout=60)
            if response.status_code == 200:
                data = response.json()
                
                status = data.get('status')
                message = data.get('message', '')
                
                if status == '1' and message == 'OK':
                    self.consecutive_rate_limits = 0  # Reset on success
                    return data
                elif message == 'No transactions found':
                    return {'result': [], 'status': '1', 'message': 'OK'}
                elif status == '0':
                    error_msg = data.get('message', 'Unknown error')
                    result_msg = data.get('result', '')
                    
                    # Check for rate limiting
                    if 'rate limit' in error_msg.lower() or 'max rate' in error_msg.lower():
                        print(f"  Rate limit reached: {error_msg}")
                        self._rotate_api_key()  # Try different key
                        self.consecutive_rate_limits += 1
                        wait_time = min(5 * self.consecutive_rate_limits, 60)
                        print(f"   Waiting {wait_time} seconds before retry...")
                        time.sleep(wait_time)
                        return None
                    
                    print(f"API Error: {error_msg}")
                    if result_msg:
                        print(f"   Details: {result_msg}")
                    return None
                else:
                    # Unknown status, but might have data
                    if 'result' in data:
                        return data
                    print(f"Unknown response: status={status}, message={message}")
                    return None
            else:
                print(f"HTTP Error: {response.status_code}")
                print(f"Response: {response.text[:200]}")
                # On 429, wait much longer and rotate API key
                if response.status_code == 429:
                    self.consecutive_rate_limits += 1
                    wait_time = min(30 * self.consecutive_rate_limits, 300)  # Up to 5 minutes
                    print(f"⏳ Rate limited. Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    self._rotate_api_key()
                return None
        except Exception as e:
            print(f"Request error: {e}")
            return None
    
    def _get_current_block(self) -> int:
        """Get current block number from API"""
        # Rate limit: ensure we wait before this request too
        self._rate_limit_wait()
        
        # Try multiple times with backoff
        for attempt in range(3):
            try:
                params = {
                    'module': 'proxy',
                    'action': 'eth_blockNumber',
                    'apikey': self.api_key
                }
                response = requests.get(self.api_url, params=params, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == '1':
                        block_hex = data.get('result', '0x0')
                        return int(block_hex, 16)
                    elif data.get('result'):
                        # Sometimes result is hex without status
                        try:
                            return int(data['result'], 16)
                        except:
                            pass
                elif response.status_code == 429:
                    print(f"Rate limited getting block number, waiting {30 * (attempt + 1)}s...")
                    time.sleep(30 * (attempt + 1))
                    continue
            except Exception as e:
                print(f"Error getting block number: {e}")
                time.sleep(5)
        
        # Fallback: Use reasonable Base block estimate
        # Base launched ~July 2023, ~2 blocks/second = ~63M blocks/year
        # As of Jan 2026 (~2.5 years), current block is approximately 41-42M
        # Use 42M as safe upper bound
        print("  Could not get current block from API. Using fallback: 42,000,000")
        return 42000000
    
    def fetch_all_transactions(self, start_block: int = 0, end_block: int = None, max_pages: Optional[int] = None) -> List[Dict]:
        """
        Fetch all ERC-20 transfer transactions for the token using Routescan API
        Uses block range queries to avoid "Result window too large" error
        Routescan limit: PageNo x Offset <= 10000
        Strategy: Query by block ranges, always use page=1
        
        Args:
            start_block: Block to start fetching from
            end_block: Block to stop fetching at (optional, defaults to current block)
            max_pages: Maximum pages to fetch (optional)
        """
        all_transactions = []
        max_retries = 3
        block_range = 50000  # Query 50k blocks at a time (larger for efficiency)
        offset = 10000  # Max offset per query
        
        print(f"Fetching transactions for token {self.token_address}")
        print(f"Using Routescan/Basedscan API (FREE!)")
        print(f"Start block: {start_block:,}" if start_block > 0 else "From beginning")
        if end_block:
            print(f"End block: {end_block:,}")
        print(f"Strategy: Block range queries ({block_range:,} blocks per query)")
        print()
        
        # Progress tracking
        progress_file = 'fetch_progress.json'
        
        current_block = self._get_current_block()
        # Use end_block if specified, otherwise use current network block
        target_block = end_block if end_block else current_block
        from_block = start_block if start_block > 0 else 0
        query_count = 0
        consecutive_empty = 0
        
        # Hard limit: never query beyond current known block + small buffer
        # Base chain as of Jan 2026 is ~41-42M blocks
        absolute_max_block = min(43000000, target_block + 1)  # Hard ceiling
        
        while from_block < target_block and from_block < absolute_max_block:
            # Safety check: if from_block is way past the known target block, stop
            if from_block > target_block + 100000:  # More than 100k blocks past "target"
                print(f"\n  Stopping: from_block ({from_block:,}) is way past target_block ({target_block:,})")
                print(f"   This suggests rate limiting prevented accurate block detection.")
                break
            
            query_count += 1
            to_block = min(from_block + block_range - 1, target_block, absolute_max_block)
            
            print(f"Query {query_count}: Blocks {from_block:,} to {to_block:,}...", end=' ', flush=True)
            
            # Always use page=1 with block range to avoid pagination limit
            params = {
                'page': 1,
                'offset': offset,
                'startblock': from_block,
                'endblock': to_block
            }
            
            # Retry logic for rate limits
            data = None
            for attempt in range(max_retries):
                data = self._make_request(params)
                
                if data:
                    break
                elif attempt < max_retries - 1:
                    # Exponential backoff with longer waits for rate limits
                    # Wait longer to respect rate limits (2 req/sec = 0.5 sec min between requests)
                    wait_time = min((attempt + 1) * 10, 120)  # Start with 10s, up to 120 seconds
                    print(f"\n  Retry {attempt + 1}/{max_retries} after {wait_time}s...", end=' ', flush=True)
                    time.sleep(wait_time)
                    # Reset last request time after long wait
                    self.last_request_time = 0
            
            if not data:
                print("Failed after retries")
                # If rate limited, wait MUCH longer before continuing
                # Routescan free tier: 2 req/sec, so wait significantly to avoid hammering the API
                wait_time = 120  # Wait 2 minutes for rate limit to reset
                print(f"  ⏳ Rate limit hit - waiting {wait_time} seconds before continuing...")
                time.sleep(wait_time)
                # Reset last request time after long wait
                self.last_request_time = 0
                # Rotate API key to try the other one
                self._rotate_api_key()
                # Move to next range
                from_block = to_block + 1
                consecutive_empty += 1
                # Only stop after MANY consecutive failures (rate limits are temporary)
                if consecutive_empty >= 20:  # Reduced from 50 to 20 to avoid wasted time
                    print("\n  Many consecutive failures. Pausing for 10 minutes...")
                    time.sleep(600)  # Wait 10 minutes
                    consecutive_empty = 0  # Reset counter and continue
                continue
            
            transactions = data.get('result', [])
            
            if not transactions:
                print("No transactions")
                consecutive_empty += 1
                
                # Check if we've gone too far past target block
                if target_block > 0 and to_block >= target_block:
                    print(f"\n Reached target block ({target_block:,})")
                    print(f"   Stopping fetch - no more blocks to query")
                    break
                
                # Check if we've gone way past where transactions likely exist
                if all_transactions and consecutive_empty > 50:  # After 50 empty ranges, check
                    last_tx_block = max(int(tx.get('blockNumber', 0)) for tx in all_transactions if tx.get('blockNumber'))
                    blocks_ahead = to_block - last_tx_block
                    if blocks_ahead > 200000:  # 200k blocks ahead of last transaction
                        print(f"\n Stopping: Querying {blocks_ahead:,} blocks ahead of last transaction")
                        print(f"   Last transaction was at block {last_tx_block:,}")
                        print(f"   Current query block: {to_block:,}")
                        print(f"   Token likely stopped trading. Collected {len(all_transactions):,} transactions.")
                        break
                
                # Only stop after MANY consecutive empty ranges
                # But also check if we're way past where transactions likely exist
                if consecutive_empty >= 500:  # Very high threshold - transactions might be sparse
                    print(f"\n  No transactions found in last {consecutive_empty} ranges.")
                    print(f"   Current block: {to_block:,}, Total collected: {len(all_transactions):,}")
                    # If we have transactions, check if we're way past the last one
                    if all_transactions:
                        last_tx_block = max(int(tx.get('blockNumber', 0)) for tx in all_transactions if tx.get('blockNumber'))
                        blocks_ahead = to_block - last_tx_block
                        if blocks_ahead > 200000:  # 200k blocks ahead of last transaction
                            print(f"     Querying {blocks_ahead:,} blocks ahead of last transaction")
                            print(f"   Token likely stopped trading. Stopping fetch.")
                            break
                    print(f"   Continuing to check more ranges...")
                    consecutive_empty = 0  # Reset and continue
                from_block = to_block + 1
                # Rate limit is handled in _make_request() - no additional sleep needed
                continue
            
            # Reset consecutive empty counter
            consecutive_empty = 0
            
            # Convert to standard format
            converted = []
            for tx in transactions:
                converted_tx = self._convert_to_standard_format(tx)
                if converted_tx:
                    converted.append(converted_tx)
            
            all_transactions.extend(converted)
            print(f" {len(converted)} transactions (Total: {len(all_transactions):,})")
            
            # Update progress
            if converted:
                last_block = int(converted[-1].get('blockNumber', 0))
                progress = {
                    'current_block_range': f"{from_block}-{to_block}",
                    'total_transactions': len(all_transactions),
                    'last_block': last_block,
                    'queries_completed': query_count
                }
                with open(progress_file, 'w') as f:
                    json.dump(progress, f, indent=2)
            
            # Move to next block range
            from_block = to_block + 1
            
            # Rate limit is handled in _make_request() - no additional sleep needed
            # But add small delay for empty results to avoid tight loops
            if not transactions:
                time.sleep(0.1)
        
        print(f"\nTotal transactions fetched: {len(all_transactions):,}")
        return all_transactions
    
    def _convert_to_standard_format(self, tx: Dict) -> Optional[Dict]:
        """Convert Routescan format to standard format"""
        try:
            return {
                'hash': tx.get('hash', ''),
                'from': tx.get('from', '').lower(),
                'to': tx.get('to', '').lower(),
                'value': tx.get('value', '0'),
                'timeStamp': tx.get('timeStamp', '0'),
                'blockNumber': tx.get('blockNumber', '0'),
                'tokenName': tx.get('tokenName', ''),
                'tokenSymbol': tx.get('tokenSymbol', ''),
                'tokenDecimal': tx.get('tokenDecimal', '18'),
                'contractAddress': tx.get('contractAddress', '')
            }
        except Exception as e:
            print(f"Error converting transaction: {e}")
            return None
    
    def save_transactions(self, transactions: List[Dict], filename: str = 'transactions.json'):
        """Save transactions to JSON file, deduplicating by hash"""
        # Deduplicate by transaction hash before saving
        seen_hashes = set()
        unique_transactions = []
        duplicates_removed = 0
        
        for tx in transactions:
            tx_hash = tx.get('hash', '')
            if tx_hash and tx_hash not in seen_hashes:
                seen_hashes.add(tx_hash)
                unique_transactions.append(tx)
            elif tx_hash:
                duplicates_removed += 1
        
        # Save deduplicated transactions
        with open(filename, 'w') as f:
            json.dump(unique_transactions, f, indent=2)
        
        if duplicates_removed > 0:
            print(f"Saved {len(unique_transactions):,} unique transactions to {filename} (removed {duplicates_removed:,} duplicates)")
        else:
            print(f"Saved {len(unique_transactions):,} transactions to {filename}")
    
    def load_transactions(self, filename: str = 'transactions.json') -> List[Dict]:
        """Load transactions from JSON file"""
        with open(filename, 'r') as f:
            return json.load(f)
