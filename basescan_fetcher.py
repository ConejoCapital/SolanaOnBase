"""
Fetcher for Base blockchain transactions using Basescan API V2
According to https://docs.etherscan.io/v2-migration
"""
import requests
import time
import json
from typing import List, Dict, Optional
from tqdm import tqdm
import config

class BasescanFetcher:
    def __init__(self):
        self.api_key = config.BASESCAN_API_KEY
        self.api_v2_url = config.BASESCAN_API_V2_URL
        self.chain_id = config.BASE_CHAIN_ID
        self.token_address = config.TOKEN_ADDRESS.lower()
        
    def _make_request(self, params: Dict) -> Optional[Dict]:
        """
        Make request to Basescan API V2
        According to https://docs.etherscan.io/v2-migration
        Format: https://api.etherscan.io/v2/api?chainid=8453&action=tokentx&module=account&...
        """
        # Build request parameters for V2 API
        request_params = {
            'chainid': self.chain_id,  # Base chain ID: 8453
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
            response = requests.get(self.api_v2_url, params=request_params, timeout=60)
            if response.status_code == 200:
                data = response.json()
                
                status = data.get('status')
                message = data.get('message', '')
                
                if status == '1' and message == 'OK':
                    return data
                elif message == 'No transactions found':
                    return {'result': [], 'status': '1', 'message': 'OK'}
                elif status == '0':
                    error_msg = data.get('message', 'Unknown error')
                    result_msg = data.get('result', '')
                    
                    # Check for rate limiting
                    if 'rate limit' in error_msg.lower() or 'max rate' in error_msg.lower():
                        print(f"⚠️  Rate limit reached: {error_msg}")
                        print("   Waiting 5 seconds before retry...")
                        time.sleep(5)
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
                return None
        except Exception as e:
            print(f"Request error: {e}")
            return None
    
    def fetch_all_transactions(self, start_block: int = 0, max_pages: Optional[int] = None) -> List[Dict]:
        """
        Fetch all ERC-20 transfer transactions for the token using Basescan API V2
        Uses very small chunks (10-20 per page) to work around free tier limitations
        Free tier: Small queries work, larger ones fail
        """
        all_transactions = []
        page = 1
        offset = 10  # Very small offset - free tier allows small queries
        max_retries = 3
        
        print(f"Fetching transactions for token {self.token_address}")
        print(f"Using Basescan API V2 (chainid={self.chain_id})")
        print(f"Start block: {start_block:,}" if start_block > 0 else "From beginning")
        print(f"Rate limit: 5 requests/second (free tier)")
        print()
        
        while True:
            if max_pages and page > max_pages:
                print(f"Reached max pages limit ({max_pages})")
                break
            
            params = {
                'page': page,
                'offset': offset
            }
            
            if start_block > 0:
                params['startblock'] = start_block
                params['endblock'] = 99999999  # Latest
            
            print(f"Fetching page {page} (offset {offset})...", end=' ', flush=True)
            
            # Retry logic for rate limits
            data = None
            for attempt in range(max_retries):
                data = self._make_request(params)
                
                if data:
                    break
                elif attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # Exponential backoff
                    print(f"\n  Retry {attempt + 1}/{max_retries} after {wait_time}s...", end=' ', flush=True)
                    time.sleep(wait_time)
            
            if not data:
                print("Failed after retries")
                # If first page fails, might be API issue
                if page == 1:
                    print("⚠️  First page failed. Check API key and plan limitations.")
                    break
                else:
                    # Continue with next page
                    page += 1
                    time.sleep(1)
                    continue
            
            transactions = data.get('result', [])
            
            if not transactions:
                print("No more transactions")
                break
            
            # Convert to standard format
            converted = []
            for tx in transactions:
                converted_tx = self._convert_to_standard_format(tx)
                if converted_tx:
                    converted.append(converted_tx)
            
            all_transactions.extend(converted)
            print(f"✅ {len(converted)} transactions (Total: {len(all_transactions):,})")
            
            # Check if we got fewer than offset (last page)
            if len(transactions) < offset:
                print("Reached last page")
                break
            
            page += 1
            # Rate limit: 5 req/sec = 0.2s between requests (add buffer)
            time.sleep(0.25)  # Slightly slower to be safe
        
        print(f"\nTotal transactions fetched: {len(all_transactions):,}")
        return all_transactions
    
    def _convert_to_standard_format(self, tx: Dict) -> Optional[Dict]:
        """Convert Basescan format to standard format"""
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
        """Save transactions to JSON file"""
        with open(filename, 'w') as f:
            json.dump(transactions, f, indent=2)
        print(f"Saved {len(transactions)} transactions to {filename}")
    
    def load_transactions(self, filename: str = 'transactions.json') -> List[Dict]:
        """Load transactions from JSON file"""
        with open(filename, 'r') as f:
            return json.load(f)
