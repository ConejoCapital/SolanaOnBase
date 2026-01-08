#!/usr/bin/env python3
"""
List addresses with high volume and few counterparties
This helps identify potential farming addresses vs infrastructure
"""
import json
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def main():
    if not os.path.exists('analysis_results.json'):
        print("Error: analysis_results.json not found. Run main.py first.")
        return
    
    with open('analysis_results.json', 'r') as f:
        results = json.load(f)
    
    address_stats = results.get('patterns', {}).get('address_stats', {})
    farming_addresses = set(addr.lower() for addr in results.get('patterns', {}).get('farming_addresses', []))
    
    # Filter addresses with high volume and few counterparties
    candidates = []
    
    for addr, stats in address_stats.items():
        total_volume = stats.get('total_volume', 0)
        counterparties = stats.get('unique_counterparties', 0)
        tx_count = stats.get('tx_count', 0)
        volume_ratio = stats.get('volume_ratio', 0)
        net_ratio = stats.get('net_ratio', 0)
        incoming = stats.get('incoming_volume', 0)
        outgoing = stats.get('outgoing_volume', 0)
        
        # High volume with few counterparties
        if total_volume > 10000 and counterparties < 20:
            is_farming = addr.lower() in farming_addresses
            candidates.append({
                'address': addr,
                'volume': total_volume,
                'counterparties': counterparties,
                'tx_count': tx_count,
                'volume_ratio': volume_ratio,
                'net_ratio': net_ratio,
                'incoming': incoming,
                'outgoing': outgoing,
                'is_farming': is_farming
            })
    
    # Sort by volume descending
    candidates.sort(key=lambda x: x['volume'], reverse=True)
    
    print("=" * 120)
    print("ADDRESSES WITH HIGH VOLUME AND FEW COUNTERPARTIES")
    print("=" * 120)
    print()
    print(f"{'#':<4} {'Address':<45} {'Volume':<18} {'CPs':<5} {'Tx':<10} {'Vol%':<7} {'Net%':<7} {'Status':<12}")
    print("-" * 120)
    
    for i, candidate in enumerate(candidates, 1):
        addr = candidate['address']
        volume = candidate['volume']
        counterparties = candidate['counterparties']
        tx_count = candidate['tx_count']
        vol_ratio = candidate['volume_ratio'] * 100
        net_ratio = candidate['net_ratio'] * 100
        is_farming = candidate['is_farming']
        
        status = "FARMING" if is_farming else "ORGANIC"
        
        # Additional flags
        flags = []
        if tx_count > 10000:
            flags.append("INFRA?")
        elif tx_count > 5000:
            flags.append("POSS-INFRA")
        if counterparties == 1:
            flags.append("1-CP")
        if flags:
            status += f" [{', '.join(flags)}]"
        
        print(f"{i:<4} {addr:<45} ${volume:>15,.2f} {counterparties:>4} {tx_count:>9,} {vol_ratio:>6.1f}% {net_ratio:>6.1f}% {status:<12}")
    
    print()
    print("=" * 120)
    print(f"Total: {len(candidates)} addresses")
    print()
    
    # Summary statistics
    farming_count = sum(1 for c in candidates if c['is_farming'])
    organic_count = len(candidates) - farming_count
    
    print("Summary:")
    print(f"  Currently classified as FARMING: {farming_count}")
    print(f"  Currently classified as ORGANIC: {organic_count}")
    print()
    
    # Group by counterparty count
    print("By Counterparty Count:")
    print("-" * 120)
    for cp_count in range(1, 11):
        matching = [c for c in candidates if c['counterparties'] == cp_count]
        if matching:
            total_vol = sum(c['volume'] for c in matching)
            farming_vol = sum(c['volume'] for c in matching if c['is_farming'])
            print(f"  {cp_count:2} counterparty(ies): {len(matching):3} addresses, ${total_vol:>15,.2f} total (${farming_vol:>15,.2f} farming)")
    
    # Group by transaction count ranges
    print()
    print("By Transaction Count:")
    print("-" * 120)
    ranges = [
        (0, 100, "0-100"),
        (100, 1000, "100-1k"),
        (1000, 5000, "1k-5k"),
        (5000, 10000, "5k-10k"),
        (10000, 50000, "10k-50k"),
        (50000, float('inf'), "50k+")
    ]
    for min_tx, max_tx, label in ranges:
        matching = [c for c in candidates if min_tx <= c['tx_count'] < max_tx]
        if matching:
            total_vol = sum(c['volume'] for c in matching)
            farming_vol = sum(c['volume'] for c in matching if c['is_farming'])
            print(f"  {label:10} tx: {len(matching):3} addresses, ${total_vol:>15,.2f} total (${farming_vol:>15,.2f} farming)")

if __name__ == "__main__":
    main()

