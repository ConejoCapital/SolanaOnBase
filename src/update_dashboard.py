#!/usr/bin/env python3
"""
Auto-update dashboard data from latest analysis results
Runs periodically to refresh dashboard with new data
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from collections import defaultdict

def load_latest_results():
    """Load the latest analysis results"""
    results_file = 'analysis_results.json'
    preliminary_file = 'analysis_results_preliminary.json'
    
    # Try to load final results first, fall back to preliminary
    if os.path.exists(results_file):
        try:
            with open(results_file, 'r') as f:
                return json.load(f), False  # False = not preliminary
        except:
            pass
    
    if os.path.exists(preliminary_file):
        try:
            with open(preliminary_file, 'r') as f:
                return json.load(f), True  # True = preliminary
        except:
            pass
    
    return None, None

def load_aero_results():
    """Load AERO rewards results if available"""
    aero_file = 'aero_rewards_results.json'
    if os.path.exists(aero_file):
        try:
            with open(aero_file, 'r') as f:
                return json.load(f)
        except:
            pass
    return None

def get_transaction_count():
    """Get current transaction count from file"""
    tx_file = 'transactions.json'
    if os.path.exists(tx_file):
        try:
            with open(tx_file, 'r') as f:
                txs = json.load(f)
                return len(txs)
        except:
            # File might be incomplete, try to get size estimate
            size = os.path.getsize(tx_file)
            # Rough estimate: ~500 bytes per transaction
            return int(size / 500)
    return 0

def get_progress():
    """Get progress from progress files"""
    progress = {
        'main': {},
        'aero': {}
    }
    
    # Main analysis progress
    if os.path.exists('fetch_progress.json'):
        try:
            with open('fetch_progress.json', 'r') as f:
                progress['main'] = json.load(f)
        except:
            pass
    
    # AERO progress
    if os.path.exists('aero_analysis_progress.json'):
        try:
            with open('aero_analysis_progress.json', 'r') as f:
                progress['aero'] = json.load(f)
        except:
            pass
    
    return progress

def generate_chart_data():
    """Generate time-series chart data from transactions"""
    chart_file = 'chart_data.json'
    
    if not os.path.exists('transactions.json'):
        # Create empty chart data
        with open(chart_file, 'w') as f:
            json.dump({
                'labels': [],
                'farmed': [],
                'organic': [],
                'total': []
            }, f, indent=2)
        return
    
    try:
        with open('transactions.json', 'r') as f:
            txs = json.load(f)
    except:
        return
    
    # Load farming addresses
    farming_addresses = set()
    if os.path.exists('analysis_results.json'):
        try:
            with open('analysis_results.json', 'r') as f:
                results = json.load(f)
                farming_addresses = set(results.get('patterns', {}).get('farming_addresses', []))
        except:
            pass
    
    # Group by date
    daily_data = defaultdict(lambda: {'farmed': 0, 'organic': 0, 'total': 0})
    
    for tx in txs:
        try:
            timestamp = int(tx.get('timeStamp', 0))
            if timestamp == 0:
                continue
            date = datetime.fromtimestamp(timestamp).date()
            date_str = date.strftime('%Y-%m-%d')
            
            value = float(tx.get('value', 0)) / (10 ** int(tx.get('tokenDecimal', 18)))
            from_addr = tx.get('from', '').lower()
            to_addr = tx.get('to', '').lower()
            
            # Check if either address is farming
            is_farmed = from_addr in farming_addresses or to_addr in farming_addresses
            
            daily_data[date_str]['total'] += value
            if is_farmed:
                daily_data[date_str]['farmed'] += value
            else:
                daily_data[date_str]['organic'] += value
        except:
            continue
    
    # Sort by date and get last 30 days
    sorted_dates = sorted(daily_data.keys())
    recent_dates = sorted_dates[-30:] if len(sorted_dates) > 30 else sorted_dates
    
    chart_data = {
        'labels': [d[-5:] for d in recent_dates],  # MM-DD format
        'farmed': [daily_data[d]['farmed'] for d in recent_dates],
        'organic': [daily_data[d]['organic'] for d in recent_dates],
        'total': [daily_data[d]['total'] for d in recent_dates]
    }
    
    with open(chart_file, 'w') as f:
        json.dump(chart_data, f, indent=2)

def update_dashboard_data():
    """Update dashboard_data.json with latest information"""
    results, is_preliminary = load_latest_results()
    aero_results = load_aero_results()
    tx_count = get_transaction_count()
    progress = get_progress()
    
    if not results:
        print("No results found yet")
        return
    
    # Prepare dashboard data
    dashboard_data = {
        'total_transactions': tx_count or results.get('total_transactions', 0),
        'organic_percentage': results['volume_breakdown']['organic_percentage'],
        'farmed_percentage': results['volume_breakdown']['farmed_percentage'],
        'organic_volume': results['volume_breakdown']['organic_volume'],
        'farmed_volume': results['volume_breakdown']['farmed_volume'],
        'total_volume': results['volume_breakdown']['total_volume'],
        'farming_addresses_count': len(results['patterns']['farming_addresses']),
        'organic_addresses_count': len(results['patterns']['organic_addresses']),
        'is_preliminary': is_preliminary,
        'last_updated': datetime.now().isoformat(),
        'progress': progress,
        'top_farming_addresses': []
    }
    
    # Get top farming addresses
    address_stats = results['patterns']['address_stats']
    farming_addresses = results['patterns']['farming_addresses']
    
    farming_stats = [(addr, stats) for addr, stats in address_stats.items() 
                     if addr in farming_addresses]
    farming_stats.sort(key=lambda x: x[1]['total_volume'], reverse=True)
    
    for addr, stats in farming_stats[:20]:
        dashboard_data['top_farming_addresses'].append({
            'address': addr,
            'volume': stats['total_volume'],
            'transactions': stats['tx_count'],
            'net_position': stats['net_position'],
            'round_trip_ratio': stats.get('volume_ratio', 0) * 100,
            'net_ratio': stats.get('net_ratio', 0) * 100
        })
    
    # Add AERO data if available
    if aero_results:
        dashboard_data['aero_results'] = aero_results
        dashboard_data['aero_available'] = True
    else:
        dashboard_data['aero_available'] = False
        # Check if AERO tracking is in progress
        if progress.get('aero'):
            dashboard_data['aero_in_progress'] = True
            dashboard_data['aero_progress'] = progress['aero']
        else:
            dashboard_data['aero_in_progress'] = False
    
    # Save updated dashboard data
    with open('dashboard_data.json', 'w') as f:
        json.dump(dashboard_data, f, indent=2)
    
    # Generate chart data for time-series visualization
    generate_chart_data()
    
    print(f" Dashboard data updated: {tx_count:,} transactions, AERO: {'Yes' if aero_results else 'No'}")

def main():
    """Main update loop"""
    print("Starting dashboard auto-updater...")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            update_dashboard_data()
            time.sleep(30)  # Update every 30 seconds
    except KeyboardInterrupt:
        print("\nStopping dashboard updater...")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        # Run once and exit
        update_dashboard_data()
    else:
        # Run continuously
        main()

