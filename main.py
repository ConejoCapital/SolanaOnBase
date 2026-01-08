"""
Main script for Basescan-based analysis
Fetches all transactions and analyzes farming vs organic volume
"""
import os
import json
import sys
import time

# Import from current directory first
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Add parent directory to import analyzer
sys.path.insert(1, os.path.join(current_dir, '..'))

from routescan_fetcher import RoutescanFetcher
from analyzer import VolumeAnalyzer
import config

def main():
    print("=" * 80)
    print("TOKEN VOLUME ANALYSIS - ROUTESCAN/BASEDSCAN API (FREE!)")
    print("=" * 80)
    print()
    
    fetcher = RoutescanFetcher()
    analyzer = VolumeAnalyzer()
    
    transactions_file = 'transactions.json'
    target_transactions = 1800000  # Target: 1.8M transactions
    
    # Load existing transactions if available
    transactions = []
    if os.path.exists(transactions_file):
        print(f"Loading existing transactions from {transactions_file}")
        try:
            transactions = fetcher.load_transactions(transactions_file)
            print(f"Loaded {len(transactions):,} transactions")
        except Exception as e:
            print(f"Error loading: {e}")
            transactions = []
    
    # Continuous fetch loop until target reached
    while len(transactions) < target_transactions:
        current_count = len(transactions)
        remaining = target_transactions - current_count
        
        print(f"\n{'='*80}")
        print(f"Current: {current_count:,} transactions")
        print(f"Target: {target_transactions:,} transactions")
        print(f"Remaining: {remaining:,} transactions")
        print(f"{'='*80}\n")
        
        # Determine start block
        if transactions:
            # Get last block from existing transactions
            last_block = max(int(tx.get('blockNumber', 0)) for tx in transactions if tx.get('blockNumber'))
            start_block = last_block + 1
            print(f"Continuing from block {start_block:,} (last block: {last_block:,})")
        else:
            start_block = 38699339
            print(f"Starting from block {start_block:,} (Solana token inception)")
        
        print("Fetching more transactions...")
        print("NOTE: This may take a while")
        print()
        
        # Fetch more transactions
        new_transactions = fetcher.fetch_all_transactions(start_block=start_block)
        
        if new_transactions:
            # Merge with existing (deduplicate by hash)
            existing_hashes = {tx.get('hash') for tx in transactions}
            unique_new = [tx for tx in new_transactions if tx.get('hash') not in existing_hashes]
            
            if unique_new:
                transactions.extend(unique_new)
                print(f"\n✅ Added {len(unique_new):,} new transactions")
                print(f"✅ Total now: {len(transactions):,} transactions")
                
                # Save progress
                fetcher.save_transactions(transactions, transactions_file)
            else:
                print("\n⚠️  No new unique transactions found")
                # Check if we should continue or stop
                if len(transactions) >= target_transactions * 0.9:  # If we have 90% of target
                    print("   Have 90%+ of target transactions. Stopping fetch.")
                    break
                else:
                    print("   Continuing to check more blocks...")
                    time.sleep(5)  # Wait before next attempt
        else:
            print("\n⚠️  No transactions returned")
            # If we have substantial data, analyze what we have
            if len(transactions) > 100000:
                print(f"   Have {len(transactions):,} transactions. Analyzing current data...")
                break
            else:
                print("   Waiting before retry...")
                time.sleep(10)
    
    if not transactions:
        print("No transactions to analyze")
        return
    
    print(f"\n{'='*80}")
    print(f"ANALYZING {len(transactions):,} TRANSACTIONS")
    print(f"{'='*80}\n")
    
    analyzer.load_transactions(transactions)
    
    # Identify farming patterns
    print("Identifying farming patterns...")
    patterns = analyzer.identify_farming_patterns()
    
    # Calculate volume breakdown
    print("Calculating volume breakdown...")
    volume_breakdown = analyzer.calculate_volume_breakdown(patterns['farming_addresses'])
    
    # Generate report
    print("\nGenerating report...")
    report = analyzer.generate_report(patterns, volume_breakdown)
    
    # Save results with address_stats
    address_stats_serializable = {}
    for addr, stats in patterns['address_stats'].items():
        if isinstance(stats.get('unique_counterparties'), set):
            unique_count = len(stats['unique_counterparties'])
        else:
            unique_count = stats.get('unique_counterparties', 0)
        
        address_stats_serializable[addr] = {
            'total_volume': stats.get('total_volume', 0),
            'net_position': stats.get('net_position', 0),
            'tx_count': stats.get('tx_count', 0),
            'volume_ratio': stats.get('volume_ratio', 0),
            'net_ratio': stats.get('net_ratio', 0),
            'unique_counterparties': unique_count
        }
    
    results = {
        'patterns': {
            'farming_addresses': patterns['farming_addresses'],
            'organic_addresses': patterns['organic_addresses'],
            'address_count': len(patterns['address_stats']),
            'address_stats': address_stats_serializable
        },
        'volume_breakdown': volume_breakdown,
        'total_transactions': len(transactions),
        'is_preliminary': len(transactions) < target_transactions
    }
    
    with open('analysis_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print report
    print("\n" + report)
    
    # Save report to file
    with open('analysis_report.txt', 'w') as f:
        f.write(report)
    
    print("\n" + "=" * 80)
    print("Analysis complete!")
    print("Results saved to:")
    print("  - analysis_results.json (structured data)")
    print("  - analysis_report.txt (human-readable report)")
    if results['is_preliminary']:
        print(f"\n⚠️  NOTE: This is preliminary analysis ({len(transactions):,}/{target_transactions:,} transactions)")
        print("   Analysis will continue fetching more transactions in background")
    print("=" * 80)

if __name__ == "__main__":
    main()
