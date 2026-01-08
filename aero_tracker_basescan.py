"""
AERO Rewards Tracker using Basescan API
Tracks AERO token transfers for farming addresses
"""
import json
import os
import sys
import time
import requests
from collections import defaultdict
from typing import Dict, List

# Import from current directory first
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Add parent directory to import analyzer
sys.path.insert(1, os.path.join(current_dir, '..'))

import config

# AERO token contract address on Base
# Verified: This is the actual AERO token (not router)
# If this doesn't work, we may need to find the correct address
AERO_TOKEN_ADDRESS = "0x940181a94A35A4569E4529A3CDfB74e38FD98631"
START_BLOCK = 38699339

class BasescanAEROTracker:
    def __init__(self):
        # Use dedicated AERO API key for parallel processing
        self.api_key = config.ROUTESCAN_API_KEY_AERO
        self.api_url = config.ROUTESCAN_API_URL
        # Rate limiting: Routescan free tier = 2 requests per second
        self.min_request_interval = 0.6  # 0.6 seconds = ~1.67 req/sec (safe margin under 2 req/sec)
        self.last_request_time = 0
    
    def _rate_limit_wait(self):
        """Ensure we respect 2 requests per second limit"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def _get_current_block(self) -> int:
        """Get the current block number of the Base network."""
        # Rate limit: ensure we wait before this request too
        self._rate_limit_wait()
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
        except Exception as e:
            print(f"Could not get current block: {e}")
        # Fallback: use a large number if API fails
        return 50000000  # More reasonable fallback
        
    def _make_request(self, params: Dict):
        """Make request to Routescan API
        Respects 2 requests per second rate limit
        """
        # Rate limit: ensure we wait at least 0.6 seconds between requests
        self._rate_limit_wait()
        
        request_params = {
            'module': 'account',
            'action': 'tokentx',
            'apikey': self.api_key,
            'sort': 'asc'
        }
        request_params.update(params)
        
        try:
            response = requests.get(self.api_url, params=request_params, timeout=60)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1' and data.get('message') == 'OK':
                    return data
                elif data.get('status') == '0':
                    error_msg = data.get('message', '')
                    if 'rate limit' in error_msg.lower():
                        return {'rate_limited': True}
                    return None
            return None
        except Exception as e:
            print(f"Request error: {e}")
            return None
    
    def fetch_aero_transfers_for_address(self, address: str) -> List[Dict]:
        """Fetch AERO transfers for a single address using Routescan API"""
        addr_lower = address.lower()
        all_transfers = []
        max_retries = 3
        block_range = 50000  # Query in block ranges like main fetcher
        offset = 10000
        from_block = START_BLOCK
        
        # Get current block
        current_block = self._get_current_block()
        print(f"   Current block: {current_block:,}, querying from {from_block:,}")
        
            # Query by block ranges to avoid pagination limits
        query_count = 0
        consecutive_empty = 0
        max_consecutive_empty = 100  # Stop after 100 empty ranges
        
        while from_block < current_block:
            query_count += 1
            to_block = min(from_block + block_range - 1, current_block)
            
            if query_count % 10 == 0:
                print(f"   Query {query_count}: Blocks {from_block:,} to {to_block:,}...", end=' ', flush=True)
            
            # Query AERO token transfers for this address in this block range
            params = {
                'module': 'account',
                'action': 'tokentx',
                'contractaddress': AERO_TOKEN_ADDRESS,
                'address': address,
                'page': 1,
                'offset': offset,
                'startblock': from_block,
                'endblock': to_block,
                'sort': 'asc'
            }
            
            data = None
            for attempt in range(max_retries):
                data = self._make_request(params)
                if data:
                    break
                elif attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
            
            if not data:
                if query_count % 10 == 0:
                    print("Failed")
                from_block = to_block + 1
                consecutive_empty += 1
                if consecutive_empty >= max_consecutive_empty:
                    print(f"\n     {max_consecutive_empty} consecutive empty ranges, stopping")
                    break
                continue
            
            if data.get('rate_limited'):
                import time
                print("Rate limited, waiting...")
                time.sleep(10)
                continue
            
            transactions = data.get('result', [])
            if not transactions:
                if query_count % 10 == 0:
                    print("No transfers")
                from_block = to_block + 1
                consecutive_empty += 1
                if consecutive_empty >= max_consecutive_empty:
                    print(f"\n     {max_consecutive_empty} consecutive empty ranges, stopping")
                    break
                continue
            
            # Found transactions - reset empty counter
            consecutive_empty = 0
            if query_count % 10 == 0:
                print(f"Found {len(transactions)} transfers")
            
            # Process transactions
            for tx in transactions:
                tx_from = tx.get('from', '').lower()
                tx_to = tx.get('to', '').lower()
                
                if tx_to == addr_lower:
                    # Incoming AERO
                    value = int(tx.get('value', 0)) / (10 ** int(tx.get('tokenDecimal', 18)))
                    all_transfers.append({
                        'address': address,
                        'direction': 'incoming',
                        'value': value,
                        'block': int(tx.get('blockNumber', 0)),
                        'tx_hash': tx.get('hash', ''),
                        'from': tx_from,
                        'to': tx_to
                    })
                elif tx_from == addr_lower:
                    # Outgoing AERO
                    value = int(tx.get('value', 0)) / (10 ** int(tx.get('tokenDecimal', 18)))
                    all_transfers.append({
                        'address': address,
                        'direction': 'outgoing',
                        'value': value,
                        'block': int(tx.get('blockNumber', 0)),
                        'tx_hash': tx.get('hash', ''),
                        'from': tx_from,
                        'to': tx_to
                    })
            
            from_block = to_block + 1
            import time
            # Rate limit is handled in _make_request() - no additional sleep needed
        
        return all_transfers
    
    def analyze_aero_rewards(self, transfers: List[Dict], farming_addresses: List[str]) -> Dict:
        """Analyze AERO rewards and selling patterns"""
        if not transfers:
            return {}
        
        address_stats = defaultdict(lambda: {
            'total_received': 0,
            'total_sold': 0,
            'net_position': 0,
            'receive_count': 0,
            'sell_count': 0
        })
        
        for tx in transfers:
            addr = tx['address'].lower()
            if addr not in [a.lower() for a in farming_addresses]:
                continue
            
            value = tx['value']
            direction = tx['direction']
            
            if direction == 'incoming':
                address_stats[addr]['total_received'] += value
                address_stats[addr]['net_position'] += value
                address_stats[addr]['receive_count'] += 1
            elif direction == 'outgoing':
                address_stats[addr]['total_sold'] += value
                address_stats[addr]['net_position'] -= value
                address_stats[addr]['sell_count'] += 1
        
        # Calculate sell ratios
        for addr, stats in address_stats.items():
            if stats['total_received'] > 0:
                stats['sell_ratio'] = stats['total_sold'] / stats['total_received']
                stats['hold_ratio'] = 1 - stats['sell_ratio']
            else:
                stats['sell_ratio'] = 0
                stats['hold_ratio'] = 1
        
        return dict(address_stats)
    
    def generate_report(self, address_stats: Dict) -> str:
        """Generate AERO rewards report"""
        report = []
        report.append("=" * 80)
        report.append("AERO REWARDS TRACKING REPORT")
        report.append("=" * 80)
        report.append("")
        
        if not address_stats:
            report.append("No AERO transfers found for farming addresses.")
            return "\n".join(report)
        
        sorted_addresses = sorted(
            address_stats.items(),
            key=lambda x: x[1]['total_received'],
            reverse=True
        )
        
        total_received = sum(s['total_received'] for s in address_stats.values())
        total_sold = sum(s['total_sold'] for s in address_stats.values())
        total_held = total_received - total_sold
        
        report.append("SUMMARY")
        report.append("-" * 80)
        report.append(f"Total AERO Received: {total_received:,.2f} AERO")
        report.append(f"Total AERO Sold:     {total_sold:,.2f} AERO ({total_sold/total_received*100:.2f}%)")
        report.append(f"Total AERO Held:     {total_held:,.2f} AERO ({total_held/total_received*100:.2f}%)")
        report.append("")
        
        report.append("TOP ADDRESSES")
        report.append("-" * 80)
        for addr, stats in sorted_addresses[:20]:
            report.append(f"\n{addr}")
            report.append(f"  Received: {stats['total_received']:,.2f} AERO")
            report.append(f"  Sold:     {stats['total_sold']:,.2f} AERO")
            report.append(f"  Net:      {stats['net_position']:,.2f} AERO")
            report.append(f"  Sell %:   {stats['sell_ratio']*100:.2f}%")
        
        return "\n".join(report)

def main():
    """Main function to track AERO rewards"""
    print("=" * 80)
    print("AERO REWARDS TRACKER - BASESCAN API")
    print("=" * 80)
    print()
    
    # Load farming addresses
    if not os.path.exists('analysis_results.json'):
        print("No analysis results found. Run main.py first:")
        print("  python3 main.py")
        return
    
    with open('analysis_results.json', 'r') as f:
        results = json.load(f)
        farming_addresses = results.get('patterns', {}).get('farming_addresses', [])
    
    if not farming_addresses:
        print("No farming addresses found.")
        return
    
    print(f"Tracking AERO rewards for {len(farming_addresses)} farming addresses...")
    print(f"AERO Token: {AERO_TOKEN_ADDRESS}")
    print(f"Start block: {START_BLOCK:,}")
    print()
    
    tracker = BasescanAEROTracker()
    
    # Check cache
    cache_file = 'aero_transfers_cache.json'
    if os.path.exists(cache_file):
        print(f"Loading cached AERO transfers...")
        with open(cache_file, 'r') as f:
            transfers = json.load(f)
        print(f"Loaded {len(transfers)} cached transfers")
    else:
        # Fetch AERO transfers
        print("Fetching AERO token transfers via Basescan API...")
        print("This will query each address individually...")
        print()
        
        transfers = []
        for i, address in enumerate(farming_addresses, 1):
            print(f"[{i}/{len(farming_addresses)}] {address[:10]}...{address[-8:]}", end=' ... ', flush=True)
            
            addr_transfers = tracker.fetch_aero_transfers_for_address(address)
            transfers.extend(addr_transfers)
            
            print(f"{len(addr_transfers)} transfers")
            
            # Save progress
            progress = {
                'current_address': i,
                'total_addresses': len(farming_addresses),
                'transfers_found': len(transfers)
            }
            with open('aero_analysis_progress.json', 'w') as f:
                json.dump(progress, f, indent=2)
            
            import time
            # Rate limit is handled in _make_request() - no additional sleep needed
        
        # Cache results
        with open(cache_file, 'w') as f:
            json.dump(transfers, f, indent=2)
        print(f"\nCached {len(transfers)} transfers")
    
    if not transfers:
        print("No AERO transfers found.")
        return
    
    # Analyze
    print("\nAnalyzing AERO rewards...")
    address_stats = tracker.analyze_aero_rewards(transfers, farming_addresses)
    
    # Generate report
    report = tracker.generate_report(address_stats)
    print("\n" + report)
    
    # Save results
    with open('aero_rewards_results.json', 'w') as f:
        json.dump({
            'address_stats': {k: {
                'total_received': v['total_received'],
                'total_sold': v['total_sold'],
                'net_position': v['net_position'],
                'sell_ratio': v['sell_ratio'],
                'hold_ratio': v['hold_ratio']
            } for k, v in address_stats.items()},
            'total_transfers': len(transfers)
        }, f, indent=2)
    
    with open('aero_rewards_report.txt', 'w') as f:
        f.write(report)
    
    print("\nResults saved to:")
    print("  - aero_rewards_results.json")
    print("  - aero_rewards_report.txt")

if __name__ == "__main__":
    main()

