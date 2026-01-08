"""
Analyzer to distinguish organic vs farmed volume
"""
import pandas as pd
import numpy as np
from collections import defaultdict
from typing import Dict, List, Tuple
import json

class VolumeAnalyzer:
    def __init__(self):
        self.transactions = []
        self.df = None
        
    def load_transactions(self, transactions: List[Dict]):
        """Load and prepare transaction data"""
        self.transactions = transactions
        self._prepare_dataframe()
        
    def _prepare_dataframe(self):
        """Convert transactions to pandas DataFrame"""
        if not self.transactions:
            raise ValueError("No transactions loaded")
            
        data = []
        for tx in self.transactions:
            try:
                # Get token decimals (default 18, but check if available)
                decimals = int(tx.get('tokenDecimal', 18))
                # Convert wei to tokens
                value = int(tx.get('value', 0)) / (10 ** decimals)
                timestamp = int(tx.get('timeStamp', 0))
                
                # Determine if this is a buy or sell
                # For token transfers: 'from' sends tokens, 'to' receives tokens
                # If 'to' is a DEX/router, it's likely a sell
                # If 'from' is a DEX/router, it's likely a buy
                # We'll track both addresses and analyze patterns
                
                data.append({
                    'hash': tx.get('hash', ''),
                    'from': tx.get('from', '').lower(),
                    'to': tx.get('to', '').lower(),
                    'value': value,
                    'timestamp': timestamp,
                    'block': int(tx.get('blockNumber', 0)),
                    'token_name': tx.get('tokenName', ''),
                    'token_symbol': tx.get('tokenSymbol', ''),
                })
            except Exception as e:
                print(f"Error processing transaction: {e}")
                continue
                
        self.df = pd.DataFrame(data)
        if len(self.df) > 0:
            self.df = self.df.sort_values('timestamp')
        print(f"Prepared DataFrame with {len(self.df)} transactions")
        
    def identify_farming_patterns(self) -> Dict:
        """
        Identify farming patterns:
        1. Addresses that buy and sell similar amounts (round-trip trades)
        2. Addresses with AERO-CL-POS tokens (liquidity providers)
        3. High volume from few addresses
        4. Minimal net position changes
        """
        if self.df is None or self.df.empty:
            raise ValueError("No data to analyze")
            
        # Group by address to analyze trading patterns
        # Track both incoming (receives tokens = buy) and outgoing (sends tokens = sell)
        address_stats = defaultdict(lambda: {
            'incoming_txs': [],  # Receives tokens
            'outgoing_txs': [],  # Sends tokens
            'total_incoming_volume': 0,
            'total_outgoing_volume': 0,
            'net_position': 0,
            'tx_count': 0,
            'unique_counterparties': set()
        })
        
        # Common DEX/router/aggregator/bridge addresses on Base (whitelist - these are infrastructure, not farming)
        infrastructure_addresses = {
            '0x4200000000000000000000000000000000000006',  # WETH
            '0x940181a94a35a4569e4529a3cdfb74e38fd98631',  # AERO token
            '0xc35dadb65012ec5796536bd9864ed8773abc74c4',  # SushiSwap Router
            '0x2626664c2603336e57b271c5c0b26f421741e481',  # Aerodrome Router V2
            '0xcf77a3ba9a5ca399b7c97c74d54e5b1beb874e43',  # Aerodrome Router
            '0x888ef71766ca594ded1f0fa3ae0edcc778529304',  # Uniswap V3 Router
            '0x1b02da8cb0d097eb8d57a175b88c7d8b47997506',  # SushiSwap Router V2
            '0x4752ba5dbc23f44d87826276bf6fd6b1c372ad24',  # BaseSwap Router
            '0x6bded42c6da8fbf0d2ba55b2fa120c5e0c8d7891',  # DODO Router
            '0x1111111254eeb25477b68fb85ed929f73a960582',  # 1inch Aggregator
            '0x111111125421ca6dc452d289314280a0f8842a65',  # 1inch V5 Router
            '0x9008d19f58aabd9ed0d60971565aa8510560ab41',  # CoW Protocol Settlement Contract
            '0xdef1c0ded9bec7f1a1670819833240f027b25eff',  # 0x Exchange Proxy
            # Base Bridge addresses
            '0x3154cf16c4c5c6e5b6b6b0b6b0b6b0b6b0b6b0b6',  # Base Bridge (placeholder - need actual address)
            # Known liquidity pool patterns (will be filtered by high tx count + low counterparties)
        }
        
        # Analyze each transaction
        for _, row in self.df.iterrows():
            from_addr = row['from'].lower()
            to_addr = row['to'].lower()
            value = abs(row['value'])
            
            # Track outgoing (sender loses tokens)
            address_stats[from_addr]['outgoing_txs'].append(value)
            address_stats[from_addr]['total_outgoing_volume'] += value
            address_stats[from_addr]['net_position'] -= value
            address_stats[from_addr]['tx_count'] += 1
            address_stats[from_addr]['unique_counterparties'].add(to_addr)
            
            # Track incoming (receiver gains tokens)
            address_stats[to_addr]['incoming_txs'].append(value)
            address_stats[to_addr]['total_incoming_volume'] += value
            address_stats[to_addr]['net_position'] += value
            address_stats[to_addr]['tx_count'] += 1
            address_stats[to_addr]['unique_counterparties'].add(from_addr)
        
        # Calculate farming indicators
        farming_addresses = set()
        organic_addresses = set()
        address_details = {}
        
        for addr, stats in address_stats.items():
            # Skip infrastructure addresses (routers, aggregators, etc.)
            if addr in infrastructure_addresses:
                continue
                
            total_volume = stats['total_incoming_volume'] + stats['total_outgoing_volume']
            
            if total_volume == 0:
                continue
            
            # Convert set to count for JSON serialization
            unique_counterparties = len(stats['unique_counterparties'])
            
            # Round-trip ratio: if incoming and outgoing volumes are very similar, likely farming
            if stats['total_incoming_volume'] > 0 and stats['total_outgoing_volume'] > 0:
                volume_ratio = min(stats['total_incoming_volume'], stats['total_outgoing_volume']) / max(
                    stats['total_incoming_volume'], stats['total_outgoing_volume']
                )
            else:
                volume_ratio = 0
            
            # Net position relative to total volume
            net_ratio = abs(stats['net_position']) / total_volume if total_volume > 0 else 1
            
            # Transaction frequency (high frequency = likely bot)
            # Calculate average time between transactions if we have timestamps
            avg_time_between = 0
            if len(stats['incoming_txs']) + len(stats['outgoing_txs']) > 1:
                # Get timestamps for this address
                addr_txs = self.df[(self.df['from'] == addr) | (self.df['to'] == addr)].sort_values('timestamp')
                if len(addr_txs) > 1:
                    time_diffs = addr_txs['timestamp'].diff().dropna()
                    avg_time_between = time_diffs.mean() if len(time_diffs) > 0 else 0
            
            address_details[addr] = {
                'total_volume': total_volume,
                'incoming_volume': stats['total_incoming_volume'],
                'outgoing_volume': stats['total_outgoing_volume'],
                'net_position': stats['net_position'],
                'volume_ratio': volume_ratio,
                'net_ratio': net_ratio,
                'tx_count': stats['tx_count'],
                'unique_counterparties': unique_counterparties,
                'avg_time_between_txs': avg_time_between
            }
            
            # EXCLUDE INFRASTRUCTURE FIRST
            # High transaction count with very few counterparties is likely infrastructure (LP, AMM, bridge)
            # These should NOT be classified as farming addresses
            is_likely_infrastructure = False
            
            # Infrastructure indicators:
            # The key question: Can farmers generate 10k+ transactions?
            # Or are addresses with 10k+ tx definitely infrastructure?
            #
            # More nuanced approach:
            # 1. Extremely high transaction count (>50000) = definitely infrastructure
            # 2. Very high transaction count (>20000) with very few counterparties (<3) = likely infrastructure
            # 3. High transaction count (>10000) with single counterparty = likely infrastructure (LP)
            # 4. High volume (>1M) with very few counterparties (<3) AND high tx count (>10000) = infrastructure
            #
            # BUT: Addresses with 10k-50k tx and 2-5 counterparties might be sophisticated farmers
            # We need to evaluate them based on farming signals, not just exclude them
            
            if stats['tx_count'] > 50000:
                # Extremely high tx count - definitely infrastructure
                is_likely_infrastructure = True
            elif stats['tx_count'] > 20000 and unique_counterparties < 3:
                # Very high tx count with very few CPs - likely infrastructure
                is_likely_infrastructure = True
            elif stats['tx_count'] > 10000 and unique_counterparties == 1:
                # High tx count with single counterparty - likely LP/infrastructure
                is_likely_infrastructure = True
            elif total_volume > 1000000 and unique_counterparties < 3 and stats['tx_count'] > 10000:
                # Very high volume with very few CPs and high tx count - infrastructure
                is_likely_infrastructure = True
            
            # Skip infrastructure addresses
            if is_likely_infrastructure:
                continue
            
            # Farming indicators:
            # 1. High round-trip ratio (>0.9) AND low net position (<10% of volume)
            # 2. Moderate transaction count with low counterparty diversity (but not infrastructure-level)
            # 3. Very regular transaction timing (bot-like)
            # 
            # IMPORTANT: 
            # - Routers/aggregators have high round-trip ratios but interact with MANY addresses
            # - Infrastructure (LPs, AMMs) have very high tx counts with few counterparties
            # - Real farming addresses have moderate tx counts with very few counterparties
            
            is_farming = False
            farming_signals = 0
            
            # Signal 1: High round-trip ratio AND low net position (classic wash trading pattern)
            # Farmers typically have high round-trip (buying and selling similar amounts)
            # AND low net position (not accumulating, just generating volume)
            if volume_ratio > 0.9 and net_ratio < 0.1 and total_volume > 1000:
                # Only count as signal if ALSO has low counterparty diversity (not a router)
                # Farmers can have 1-5 counterparties
                # Allow higher tx counts (up to 50k) but weight them differently
                if unique_counterparties <= 5:
                    if stats['tx_count'] <= 50000:  # Allow up to 50k tx
                        farming_signals += 1
                        # If tx count is very high (20k+), it's less likely to be farming
                        # But if it has all other signals, it might still be sophisticated farming
            
            # Signal 2: High volume with very few counterparties (trading with self via DEX)
            # This is a STRONG indicator of farming
            # Routers have many counterparties, infrastructure has extremely high tx counts (>50k)
            # Farmers can have high tx counts (10k-50k) if they're sophisticated bots
            if total_volume > 10000 and unique_counterparties <= 5:
                # Allow up to 50k tx, but very high tx counts reduce the signal strength
                if stats['tx_count'] <= 50000:
                    farming_signals += 1
                    # If tx count is 20k+, require additional confirmation (lower threshold)
                    if stats['tx_count'] > 20000:
                        # Still count as signal, but we'll require 3 signals instead of 2
                        pass
            
            # Signal 3: Very regular timing suggests bot
            # Routers also have regular timing, so combine with other signals
            if avg_time_between > 0 and avg_time_between < 300 and 50 < stats['tx_count'] <= 10000:
                # Only count if also has low counterparty diversity
                if unique_counterparties <= 10:
                    farming_signals += 1
            
            # Require signals to classify as farming
            # If tx count is very high (20k+), require more signals (3 instead of 2)
            # This accounts for the possibility that high tx count might indicate infrastructure
            required_signals = 3 if stats['tx_count'] > 20000 else 2
            
            if farming_signals >= required_signals:
                is_farming = True
            # Also allow strong single signal if it's very specific (high volume + very few CPs + moderate tx)
            elif total_volume > 50000 and unique_counterparties <= 3 and stats['tx_count'] <= 20000:
                # Extremely high volume with very few counterparties and moderate tx count is likely farming
                is_farming = True
            
            if is_farming:
                farming_addresses.add(addr)
            elif net_ratio > 0.3 or volume_ratio < 0.5 or unique_counterparties > 10:
                organic_addresses.add(addr)
        
        return {
            'farming_addresses': list(farming_addresses),
            'organic_addresses': list(organic_addresses),
            'address_stats': address_details
        }
    
    def calculate_volume_breakdown(self, farming_addresses: List[str]) -> Dict:
        """Calculate organic vs farmed volume"""
        if self.df is None or self.df.empty:
            raise ValueError("No data to analyze")
            
        farming_set = set(addr.lower() for addr in farming_addresses)
        
        farmed_volume = 0
        organic_volume = 0
        
        for _, row in self.df.iterrows():
            value = abs(row['value'])
            
            # Check if transaction involves farming address
            from_addr = row['from'].lower()
            to_addr = row['to'].lower()
            
            is_farmed = (from_addr in farming_set) or (to_addr in farming_set)
            
            if is_farmed:
                farmed_volume += value
            else:
                organic_volume += value
        
        total_volume = farmed_volume + organic_volume
        
        return {
            'total_volume': total_volume,
            'farmed_volume': farmed_volume,
            'organic_volume': organic_volume,
            'farmed_percentage': (farmed_volume / total_volume * 100) if total_volume > 0 else 0,
            'organic_percentage': (organic_volume / total_volume * 100) if total_volume > 0 else 0
        }
    
    def analyze_top_addresses(self, n: int = 10) -> pd.DataFrame:
        """Analyze top N addresses by volume"""
        if self.df is None or self.df.empty:
            raise ValueError("No data to analyze")
            
        address_volume = defaultdict(float)
        
        for _, row in self.df.iterrows():
            value = abs(row['value'])
            # Count volume for both from and to addresses
            address_volume[row['from'].lower()] += value
            address_volume[row['to'].lower()] += value
        
        # Convert to DataFrame and sort
        top_addresses = pd.DataFrame([
            {'address': addr, 'volume': vol}
            for addr, vol in address_volume.items()
        ]).sort_values('volume', ascending=False).head(n)
        
        return top_addresses
    
    def generate_report(self, patterns: Dict, volume_breakdown: Dict) -> str:
        """Generate comprehensive analysis report"""
        report = []
        report.append("=" * 80)
        report.append("VOLUME ANALYSIS REPORT")
        report.append("Token: 0x311935cd80b76769bf2ecc9d8ab7635b2139cf82")
        report.append("=" * 80)
        report.append("")
        
        report.append("EXECUTIVE SUMMARY")
        report.append("-" * 80)
        report.append(f"Total Transactions Analyzed: {len(self.df):,}")
        if len(self.df) < 100000:
            report.append("  NOTE: This is a partial dataset. Subgraph is still syncing.")
            report.append("   Expected total: ~1,800,000 transactions")
            report.append("")
        report.append(f"Farmed Volume: {volume_breakdown['farmed_percentage']:.2f}%")
        report.append(f"Organic Volume: {volume_breakdown['organic_percentage']:.2f}%")
        report.append("")
        
        report.append("VOLUME BREAKDOWN")
        report.append("-" * 80)
        # Use scientific notation or more decimals for very small values
        total_vol = volume_breakdown['total_volume']
        farmed_vol = volume_breakdown['farmed_volume']
        organic_vol = volume_breakdown['organic_volume']
        
        def format_volume(vol):
            if vol < 0.01:
                return f"{vol:.6f}"
            elif vol < 1000:
                return f"{vol:,.2f}"
            else:
                return f"{vol:,.0f}"
        
        report.append(f"Total Volume: {format_volume(total_vol)} tokens")
        report.append(f"Farmed Volume: {format_volume(farmed_vol)} tokens ({volume_breakdown['farmed_percentage']:.2f}%)")
        report.append(f"Organic Volume: {format_volume(organic_vol)} tokens ({volume_breakdown['organic_percentage']:.2f}%)")
        report.append("")
        
        report.append("FARMING ANALYSIS")
        report.append("-" * 80)
        report.append(f"Farming Addresses Identified: {len(patterns['farming_addresses'])}")
        report.append(f"Organic Addresses Identified: {len(patterns['organic_addresses'])}")
        report.append("")
        
        # Top farming addresses
        if patterns['farming_addresses']:
            report.append("TOP FARMING ADDRESSES")
            report.append("-" * 80)
            farming_volumes = []
            for addr in patterns['farming_addresses']:
                if addr in patterns['address_stats']:
                    stats = patterns['address_stats'][addr]
                    farming_volumes.append((addr, stats['total_volume'], stats))
            
            farming_volumes.sort(key=lambda x: x[1], reverse=True)
            for addr, vol, stats in farming_volumes[:10]:
                report.append(f"{addr}")
                vol_str = f"{vol:.6f}" if vol < 0.01 else f"{vol:,.2f}"
                net_str = f"{stats['net_position']:.6f}" if abs(stats['net_position']) < 0.01 else f"{stats['net_position']:,.2f}"
                report.append(f"  Volume: {vol_str} tokens")
                report.append(f"  Transactions: {stats['tx_count']:,}")
                report.append(f"  Net Position: {net_str} tokens ({stats['net_ratio']*100:.2f}% of volume)")
                report.append(f"  Round-trip Ratio: {stats['volume_ratio']*100:.2f}%")
                report.append("")
        
        # Top addresses analysis
        top_addresses = self.analyze_top_addresses(20)
        report.append("TOP 20 ADDRESSES BY VOLUME")
        report.append("-" * 80)
        for idx, row in top_addresses.iterrows():
            is_farming = row['address'].lower() in [a.lower() for a in patterns['farming_addresses']]
            label = "[FARMING]" if is_farming else "[ORGANIC]"
            addr_stats = patterns['address_stats'].get(row['address'].lower(), {})
            net_pos = addr_stats.get('net_position', 0)
            vol_str = f"{row['volume']:.6f}" if row['volume'] < 0.01 else f"{row['volume']:,.2f}"
            net_str = f"{net_pos:.6f}" if abs(net_pos) < 0.01 else f"{net_pos:,.2f}"
            report.append(f"{label} {row['address']}: {vol_str} tokens (Net: {net_str})")
        report.append("")
        
        report.append("METHODOLOGY")
        report.append("-" * 80)
        report.append("Farming addresses identified by:")
        report.append("  1. High round-trip ratio (>90%) with low net position (<10% of volume)")
        report.append("  2. High volume with very few unique counterparties (<5)")
        report.append("  3. Very regular transaction timing (bot-like patterns)")
        report.append("")
        
        report.append("=" * 80)
        
        return "\n".join(report)

