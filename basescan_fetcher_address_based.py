"""
Alternative Basescan Fetcher - Query by address instead of contract
This might work better on free tier
"""
import requests
import time
import json
from typing import List, Dict, Optional
import config

class BasescanAddressBasedFetcher:
    def __init__(self):
        self.api_key = config.BASESCAN_API_KEY
        self.api_v2_url = config.BASESCAN_API_V2_URL
        self.chain_id = config.BASE_CHAIN_ID
        self.token_address = config.TOKEN_ADDRESS.lower()
        
    def _make_request(self, params: Dict) -> Optional[Dict]:
        """Make request to Basescan API V2"""
        request_params = {
            'chainid': self.chain_id,
            'module': 'account',
            'action': 'tokentx',
            'apikey': self.api_key,
            'sort': 'asc'
        }
        request_params.update(params)
        
        try:
            response = requests.get(self.api_v2_url, params=request_params, timeout=60)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1' and data.get('message') == 'OK':
                    return data
                elif data.get('status') == '0':
                    error_msg = data.get('message', '')
                    result_msg = data.get('result', '')
                    if 'rate limit' in error_msg.lower():
                        return {'rate_limited': True}
                    # Don't print every error to avoid spam
                    return None
            return None
        except Exception as e:
            return None
    
    def fetch_transactions_by_addresses(self, addresses: List[str], start_block: int = 0) -> List[Dict]:
        """
        Fetch transactions by querying each address individually
        Then filter for our token
        This approach might work on free tier
        """
        all_transactions = []
        seen_hashes = set()  # Avoid duplicates
        
        print(f"Fetching transactions for token {self.token_address}")
        print(f"Querying {len(addresses)} addresses individually...")
        print(f"Start block: {start_block:,}" if start_block > 0 else "From beginning")
        print()
        
        for i, address in enumerate(addresses, 1):
            print(f"[{i}/{len(addresses)}] {address[:10]}...{address[-8:]}", end=' ... ', flush=True)
            
            page = 1
            offset = 1000
            address_txs = 0
            
            while True:
                params = {
                    'address': address,
                    'page': page,
                    'offset': offset
                }
                
                if start_block > 0:
                    params['startblock'] = start_block
                    params['endblock'] = 99999999
                
                data = self._make_request(params)
                
                if not data or data.get('rate_limited'):
                    if data and data.get('rate_limited'):
                        time.sleep(5)
                        continue
                    break
                
                transactions = data.get('result', [])
                if not transactions:
                    break
                
                # Filter for our token and avoid duplicates
                for tx in transactions:
                    tx_hash = tx.get('hash', '')
                    contract = tx.get('contractAddress', '').lower()
                    
                    if contract == self.token_address and tx_hash not in seen_hashes:
                        converted = self._convert_to_standard_format(tx)
                        if converted:
                            all_transactions.append(converted)
                            seen_hashes.add(tx_hash)
                            address_txs += 1
                
                if len(transactions) < offset:
                    break
                
                page += 1
                time.sleep(0.25)  # Rate limit protection
            
            print(f"{address_txs} transactions")
            
            # Save progress
            progress = {
                'current_address': i,
                'total_addresses': len(addresses),
                'transactions_found': len(all_transactions)
            }
            with open('fetch_progress.json', 'w') as f:
                json.dump(progress, f, indent=2)
        
        print(f"\nTotal unique transactions: {len(all_transactions):,}")
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
        except:
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


