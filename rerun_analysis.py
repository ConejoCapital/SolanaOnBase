#!/usr/bin/env python3
"""
Re-run analysis on existing transactions with updated classification logic
This uses the saved transactions.json and applies the new stricter rules
"""
import os
import json
import sys

# Add parent directory to import analyzer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

from routescan_fetcher import RoutescanFetcher
from analyzer import VolumeAnalyzer

def main():
    print("=" * 80)
    print("RE-RUNNING ANALYSIS WITH UPDATED CLASSIFICATION LOGIC")
    print("=" * 80)
    print()
    
    fetcher = RoutescanFetcher()
    analyzer = VolumeAnalyzer()
    
    # Load existing transactions
    transactions_file = 'transactions.json'
    
    if not os.path.exists(transactions_file):
        print(f"❌ {transactions_file} not found!")
        print("   Please run main.py first to fetch transactions.")
        return
    
    print(f"Loading existing transactions from {transactions_file}...")
    try:
        transactions = fetcher.load_transactions(transactions_file)
        print(f"✅ Loaded {len(transactions):,} transactions")
    except Exception as e:
        print(f"❌ Error loading transactions: {e}")
        return
    
    if not transactions:
        print("❌ No transactions loaded!")
        return
    
    print(f"\nAnalyzing {len(transactions):,} transactions with updated classification logic...")
    print("   (Using stricter multi-signal classification to avoid router misclassification)")
    print()
    
    analyzer.load_transactions(transactions)
    
    # Identify farming patterns (with updated logic)
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
        if isinstance(stats.get('unique_counterparties'), (set, list)):
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
        'is_preliminary': len(transactions) < 1800000
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
    print()
    print("📊 Key Changes:")
    print("  ✅ Infrastructure addresses excluded (routers, aggregators)")
    print("  ✅ Stricter multi-signal classification (2+ signals required)")
    print("  ✅ Better counterparty diversity weighting")
    print()
    print("🔄 Dashboard will auto-update with new results")
    print("=" * 80)

if __name__ == "__main__":
    main()


