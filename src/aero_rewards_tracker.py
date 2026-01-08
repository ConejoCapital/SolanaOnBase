"""
Track AERO rewards for farming addresses
Monitors how much AERO they receive and sell
"""
import json
import pandas as pd
from collections import defaultdict
from typing import Dict, List, Optional
from datetime import datetime
import requests

# AERO token contract
AERO_TOKEN_ADDRESS = "0x940181a94A35A4569E4529A3CDfB74e38FD98631"

class AERORewardsTracker:
    def __init__(self, api_key: str, project_id: str):
        self.api_key = api_key
        self.project_id = project_id
        self.api_url = "https://api.goldsky.com"
        self.base_url = self.api_url
        
    def _make_graphql_request(self, query: str, variables: Dict = None) -> Optional[Dict]:
        """Make GraphQL request to Goldsky"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'query': query,
            'variables': variables or {}
        }
        
        # Try AERO token subgraph endpoint
        # We'll need to check if there's a dataset or create a query
        endpoints = [
            f"{self.base_url}/api/public/{self.project_id}/subgraphs/solana-token-base-base-base-base/1.0.0/gn",
            # Try to query AERO transfers from the same subgraph if it indexes all ERC-20 transfers
        ]
        
        for endpoint in endpoints:
            try:
                response = requests.post(endpoint, json=payload, headers=headers, timeout=60)
                if response.status_code == 200:
                    data = response.json()
                    if 'errors' in data:
                        continue
                    return data
            except:
                continue
        
        return None
    
    def fetch_aero_transfers_for_addresses(self, addresses: List[str], start_block: int = 0) -> List[Dict]:
        """Fetch AERO token transfers for specific addresses"""
        all_transfers = []
        
        # Query transfers where AERO token is involved and addresses are sender or recipient
        # Note: We'll need to filter by token address in the query
        # Since our subgraph might only index the SOL token, we may need to query Base RPC directly
        
        print(f"Fetching AERO transfers for {len(addresses)} addresses...")
        print("Note: This may require querying Base RPC directly if subgraph doesn't index AERO")
        
        return all_transfers
    
    def fetch_aero_transfers_rpc(self, addresses: List[str], start_block: int = 38699339) -> List[Dict]:
        """Fetch AERO transfers using Base RPC - optimized batch query"""
        all_transfers = []
        
        # Try multiple Base RPC endpoints (public endpoints)
        rpc_endpoints = [
            "https://mainnet.base.org",
            "https://base.llamarpc.com",
            "https://base-rpc.publicnode.com",
            "https://1rpc.io/base",
        ]
        rpc_url = rpc_endpoints[0]  # Start with first
        
        print(f"Fetching AERO token transfers via RPC for {len(addresses)} addresses...")
        print("This may take a while for large address lists...")
        print()
        
        # More efficient: Query all AERO transfers and filter by addresses
        # This is faster than querying per-address
        print("Step 1: Fetching all AERO transfers (this may take a few minutes)...")
        
        # Get current block
        try:
            current_block_payload = {
                "jsonrpc": "2.0",
                "method": "eth_blockNumber",
                "params": [],
                "id": 1
            }
            current_response = requests.post(rpc_url, json=current_block_payload, timeout=30)
            if current_response.status_code == 200:
                current_block_hex = current_response.json().get('result', '0x0')
                current_block = int(current_block_hex, 16)
            else:
                current_block = start_block + 1000000  # Fallback
        except:
            current_block = start_block + 1000000
        
        # Query per-address (more reliable than batch queries)
        address_set = set(addr.lower() for addr in addresses)
        max_retries = 3
        
        # Create progress tracking file
        progress_file = 'aero_analysis_progress.json'
        
        for i, address in enumerate(addresses, 1):
            addr_lower = address.lower()
            print(f"  [{i}/{len(addresses)}] {address[:10]}...{address[-8:]}", end=' ... ', flush=True)
            
            # Save progress
            try:
                progress_data = {
                    'current_address': i,
                    'total_addresses': len(addresses),
                    'addresses_processed': i - 1,
                    'transfers_found': len(all_transfers),
                    'current_address_being_processed': address
                }
                with open(progress_file, 'w') as f:
                    json.dump(progress_data, f, indent=2)
            except:
                pass
            
            addr_transfers = 0
            
            # Query in 1000 block chunks (RPC limit)
            chunk_size = 1000
            from_block = start_block
            
            # Query incoming transfers (receiving AERO) in chunks
            while from_block < current_block:
                to_block = min(from_block + chunk_size - 1, current_block)
                
                payload_to = {
                    "jsonrpc": "2.0",
                    "method": "eth_getLogs",
                    "params": [{
                        "fromBlock": hex(from_block),
                        "toBlock": hex(to_block),
                        "address": AERO_TOKEN_ADDRESS,
                        "topics": [
                            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",  # Transfer event
                            None,  # from (any)
                            f"0x{'0'*24}{addr_lower[2:]}"  # to (this address)
                        ]
                    }],
                    "id": 1
                }
                
                success = False
                for attempt in range(max_retries):
                    rpc_url = rpc_endpoints[attempt % len(rpc_endpoints)]
                    try:
                        response = requests.post(rpc_url, json=payload_to, timeout=60)
                        if response.status_code == 200:
                            data = response.json()
                            if 'result' in data:
                                for log in data['result']:
                                    transfer = self._parse_transfer_log(log, address, 'incoming')
                                    if transfer:
                                        all_transfers.append(transfer)
                                        addr_transfers += 1
                                success = True
                                break
                            elif 'error' in data:
                                error_msg = data['error'].get('message', '')
                                if 'range is too large' in error_msg.lower():
                                    # Chunk too large, split it
                                    chunk_size = chunk_size // 2
                                    to_block = from_block + chunk_size - 1
                                    continue
                                elif attempt < max_retries - 1:
                                    import time
                                    time.sleep(1)
                                    continue
                        elif response.status_code == 503:
                            if attempt < max_retries - 1:
                                import time
                                time.sleep(2 ** attempt)
                                continue
                    except:
                        if attempt < max_retries - 1:
                            import time
                            time.sleep(1)
                            continue
                
                if not success:
                    # Skip this chunk if all retries failed
                    pass
                
                from_block = to_block + 1
                import time
                time.sleep(0.1)  # Small delay between chunks
            
            # Query outgoing transfers (sending AERO) in chunks
            from_block = start_block
            while from_block < current_block:
                to_block = min(from_block + chunk_size - 1, current_block)
                
                payload_from = {
                    "jsonrpc": "2.0",
                    "method": "eth_getLogs",
                    "params": [{
                        "fromBlock": hex(from_block),
                        "toBlock": hex(to_block),
                        "address": AERO_TOKEN_ADDRESS,
                        "topics": [
                            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",  # Transfer event
                            f"0x{'0'*24}{addr_lower[2:]}",  # from (this address)
                            None  # to (any)
                        ]
                    }],
                    "id": 2
                }
                
                success = False
                for attempt in range(max_retries):
                    rpc_url = rpc_endpoints[attempt % len(rpc_endpoints)]
                    try:
                        response = requests.post(rpc_url, json=payload_from, timeout=60)
                        if response.status_code == 200:
                            data = response.json()
                            if 'result' in data:
                                for log in data['result']:
                                    transfer = self._parse_transfer_log(log, address, 'outgoing')
                                    if transfer:
                                        all_transfers.append(transfer)
                                        addr_transfers += 1
                                success = True
                                break
                            elif 'error' in data:
                                error_msg = data['error'].get('message', '')
                                if 'range is too large' in error_msg.lower():
                                    chunk_size = chunk_size // 2
                                    to_block = from_block + chunk_size - 1
                                    continue
                                elif attempt < max_retries - 1:
                                    import time
                                    time.sleep(1)
                                    continue
                        elif response.status_code == 503:
                            if attempt < max_retries - 1:
                                import time
                                time.sleep(2 ** attempt)
                                continue
                    except:
                        if attempt < max_retries - 1:
                            import time
                            time.sleep(1)
                            continue
                
                from_block = to_block + 1
                import time
                time.sleep(0.1)
            
            print(f"{addr_transfers} transfers")
            
            # Update progress after each address
            try:
                progress_data = {
                    'current_address': i,
                    'total_addresses': len(addresses),
                    'addresses_processed': i,
                    'transfers_found': len(all_transfers),
                    'last_processed_address': address,
                    'last_address_transfers': addr_transfers
                }
                with open(progress_file, 'w') as f:
                    json.dump(progress_data, f, indent=2)
            except:
                pass
            
            # Small delay between addresses
            import time
            time.sleep(0.3)
        
        # Final progress update
        try:
            progress_data = {
                'current_address': len(addresses),
                'total_addresses': len(addresses),
                'addresses_processed': len(addresses),
                'transfers_found': len(all_transfers),
                'status': 'complete'
            }
            with open(progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
        except:
            pass
        
        print(f"\nTotal AERO transfers found: {len(all_transfers)}")
        return all_transfers
    
    def _parse_transfer_log_batch(self, log: Dict, address_set: set) -> Optional[Dict]:
        """Parse Transfer event log and check if it involves tracked addresses"""
        try:
            topics = log.get('topics', [])
            if len(topics) < 3:
                return None
            
            from_addr = '0x' + topics[1][-40:].lower()
            to_addr = '0x' + topics[2][-40:].lower()
            
            # Only include if it involves one of our tracked addresses
            if from_addr not in address_set and to_addr not in address_set:
                return None
            
            value_hex = log.get('data', '0x0')
            value = int(value_hex, 16)
            value_tokens = value / (10 ** 18)  # AERO has 18 decimals
            
            block_number = int(log.get('blockNumber', '0x0'), 16)
            tx_hash = log.get('transactionHash', '')
            
            # Determine direction
            if from_addr in address_set:
                direction = 'outgoing'
                address = from_addr
            else:
                direction = 'incoming'
                address = to_addr
            
            return {
                'address': address,
                'from': from_addr,
                'to': to_addr,
                'value': value,
                'value_tokens': value_tokens,
                'direction': direction,
                'block_number': block_number,
                'transaction_hash': tx_hash,
                'timestamp': 0  # Will fetch if needed
            }
        except Exception as e:
            return None
    
    def _parse_transfer_log(self, log: Dict, address: str, direction: str) -> Optional[Dict]:
        """Parse Transfer event log"""
        try:
            # Transfer event: Transfer(address indexed from, address indexed to, uint256 value)
            topics = log.get('topics', [])
            if len(topics) < 3:
                return None
            
            from_addr = '0x' + topics[1][-40:].lower()
            to_addr = '0x' + topics[2][-40:].lower()
            value_hex = log.get('data', '0x0')
            value = int(value_hex, 16)
            
            # AERO has 18 decimals
            value_tokens = value / (10 ** 18)
            
            block_number = int(log.get('blockNumber', '0x0'), 16)
            tx_hash = log.get('transactionHash', '')
            
            # Get timestamp from block (we'll need to fetch this separately)
            timestamp = 0  # Will fetch if needed
            
            return {
                'address': address.lower(),
                'from': from_addr,
                'to': to_addr,
                'value': value,
                'value_tokens': value_tokens,
                'direction': direction,
                'block_number': block_number,
                'transaction_hash': tx_hash,
                'timestamp': timestamp
            }
        except Exception as e:
            return None
    
    def analyze_aero_rewards(self, transfers: List[Dict], farming_addresses: List[str]) -> Dict:
        """Analyze AERO rewards and selling patterns"""
        if not transfers:
            return {}
        
        df = pd.DataFrame(transfers)
        
        # Group by address
        address_stats = defaultdict(lambda: {
            'total_received': 0,
            'total_sold': 0,
            'net_position': 0,
            'receive_count': 0,
            'sell_count': 0,
            'transactions': []
        })
        
        for _, row in df.iterrows():
            addr = row['address'].lower()
            if addr not in [a.lower() for a in farming_addresses]:
                continue
            
            value = row['value_tokens']
            direction = row['direction']
            
            if direction == 'incoming':
                address_stats[addr]['total_received'] += value
                address_stats[addr]['net_position'] += value
                address_stats[addr]['receive_count'] += 1
            elif direction == 'outgoing':
                address_stats[addr]['total_sold'] += value
                address_stats[addr]['net_position'] -= value
                address_stats[addr]['sell_count'] += 1
            
            address_stats[addr]['transactions'].append({
                'direction': direction,
                'value': value,
                'block': row['block_number'],
                'tx_hash': row['transaction_hash']
            })
        
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
        
        # Sort by total received
        sorted_addresses = sorted(
            address_stats.items(),
            key=lambda x: x[1]['total_received'],
            reverse=True
        )
        
        report.append("TOP FARMING ADDRESSES - AERO REWARDS")
        report.append("-" * 80)
        report.append("")
        
        total_received = sum(s['total_received'] for s in address_stats.values())
        total_sold = sum(s['total_sold'] for s in address_stats.values())
        total_held = total_received - total_sold
        
        report.append(f"SUMMARY")
        report.append(f"  Total AERO Received: {total_received:,.2f} AERO")
        report.append(f"  Total AERO Sold:     {total_sold:,.2f} AERO ({total_sold/total_received*100:.2f}%)")
        report.append(f"  Total AERO Held:     {total_held:,.2f} AERO ({total_held/total_received*100:.2f}%)")
        report.append("")
        
        report.append("ADDRESS BREAKDOWN")
        report.append("-" * 80)
        
        for addr, stats in sorted_addresses[:20]:  # Top 20
            report.append(f"\n{addr}")
            report.append(f"  Total Received:  {stats['total_received']:,.2f} AERO")
            report.append(f"  Total Sold:      {stats['total_sold']:,.2f} AERO")
            report.append(f"  Net Position:    {stats['net_position']:,.2f} AERO")
            report.append(f"  Sell Ratio:      {stats['sell_ratio']*100:.2f}%")
            report.append(f"  Hold Ratio:       {stats['hold_ratio']*100:.2f}%")
            report.append(f"  Transactions:    {stats['receive_count']} received, {stats['sell_count']} sold")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)

def main():
    """Main function to track AERO rewards"""
    import config
    import os
    
    print("=" * 80)
    print("AERO REWARDS TRACKER")
    print("=" * 80)
    print()
    
    # Load farming addresses from analysis results
    farming_addresses = []
    if os.path.exists('analysis_results.json'):
        with open('analysis_results.json', 'r') as f:
            results = json.load(f)
            farming_addresses = results.get('patterns', {}).get('farming_addresses', [])
    
    if not farming_addresses:
        print("No farming addresses found. Run analysis first:")
        print("  python3 main.py")
        return
    
    print(f"Tracking AERO rewards for {len(farming_addresses)} farming addresses...")
    print(f"AERO Token: {AERO_TOKEN_ADDRESS}")
    print()
    
    tracker = AERORewardsTracker(
        api_key=config.GOLDSKY_API_KEY,
        project_id=config.GOLDSKY_PROJECT_ID
    )
    
    # Check if we have cached data
    cache_file = 'aero_transfers_cache.json'
    if os.path.exists(cache_file):
        print(f"Loading cached AERO transfers from {cache_file}...")
        with open(cache_file, 'r') as f:
            transfers = json.load(f)
        print(f"Loaded {len(transfers)} cached transfers")
        use_cache = input("\nUse cached data? (y/n, default=y): ").strip().lower()
        if use_cache != 'n':
            print("Using cached data. Delete cache file to fetch fresh data.")
        else:
            transfers = None
    else:
        transfers = None
    
    if not transfers:
        # Fetch AERO transfers
        print("\nFetching AERO token transfers via Base RPC...")
        print("This will query all AERO transfers and filter for farming addresses.")
        print("This may take 10-30 minutes depending on block range...")
        print()
        
        transfers = tracker.fetch_aero_transfers_rpc(
            addresses=farming_addresses,
            start_block=38699339
        )
        
        if transfers:
            # Cache the results
            with open(cache_file, 'w') as f:
                json.dump(transfers, f, indent=2)
            print(f"\nCached {len(transfers)} transfers to {cache_file}")
    
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
                'hold_ratio': v['hold_ratio'],
                'receive_count': v['receive_count'],
                'sell_count': v['sell_count']
            } for k, v in address_stats.items()},
            'total_transfers': len(transfers),
            'aero_token_address': AERO_TOKEN_ADDRESS
        }, f, indent=2)
    
    with open('aero_rewards_report.txt', 'w') as f:
        f.write(report)
    
    print("\nResults saved to:")
    print("  - aero_rewards_results.json")
    print("  - aero_rewards_report.txt")
    print("  - aero_transfers_cache.json (cached transfers)")

if __name__ == "__main__":
    import os
    main()

