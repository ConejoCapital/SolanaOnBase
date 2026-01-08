#!/usr/bin/env python3
"""
Terminal Dashboard for Basescan Analysis
Shows progress of transaction fetching and analysis
"""
import os
import sys
import time
import json
from datetime import datetime

# Add parent directory to import analyzer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from basescan_fetcher import BasescanFetcher
    import config
except ImportError:
    print("Error: Could not import required modules")
    sys.exit(1)

class BasescanDashboard:
    def __init__(self):
        self.start_block = 38699339
        
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('clear' if os.name != 'nt' else 'cls')
    
    def get_transaction_count(self):
        """Get transaction count from file"""
        try:
            if os.path.exists('transactions.json'):
                with open('transactions.json', 'r') as f:
                    txs = json.load(f)
                    return len(txs)
        except:
            pass
        return 0
    
    def get_analysis_status(self):
        """Get analysis status"""
        status = {
            'has_results': False,
            'farming_addresses': 0,
            'organic_addresses': 0,
            'farmed_percentage': 0,
            'organic_percentage': 0,
            'total_transactions': 0
        }
        
        if os.path.exists('analysis_results.json'):
            try:
                with open('analysis_results.json', 'r') as f:
                    results = json.load(f)
                    status['has_results'] = True
                    status['farming_addresses'] = len(results.get('patterns', {}).get('farming_addresses', []))
                    status['organic_addresses'] = len(results.get('patterns', {}).get('organic_addresses', []))
                    status['total_transactions'] = results.get('total_transactions', 0)
                    
                    volume = results.get('volume_breakdown', {})
                    status['farmed_percentage'] = volume.get('farmed_percentage', 0)
                    status['organic_percentage'] = volume.get('organic_percentage', 0)
            except:
                pass
        
        return status
    
    def get_aero_status(self):
        """Get AERO rewards analysis status"""
        status = {
            'has_results': False,
            'addresses_with_aero': 0,
            'total_received': 0,
            'total_sold': 0
        }
        
        if os.path.exists('aero_rewards_results.json'):
            try:
                with open('aero_rewards_results.json', 'r') as f:
                    results = json.load(f)
                    status['has_results'] = True
                    stats = results.get('address_stats', {})
                    status['addresses_with_aero'] = len(stats)
                    status['total_received'] = sum(s.get('total_received', 0) for s in stats.values())
                    status['total_sold'] = sum(s.get('total_sold', 0) for s in stats.values())
            except:
                pass
        
        # Check progress
        if os.path.exists('aero_analysis_progress.json'):
            try:
                with open('aero_analysis_progress.json', 'r') as f:
                    progress = json.load(f)
                    status['current_address'] = progress.get('current_address', 0)
                    status['total_addresses'] = progress.get('total_addresses', 0)
                    status['transfers_found'] = progress.get('transfers_found', 0)
            except:
                pass
        
        return status
    
    def draw_progress_bar(self, current: int, total: int, width: int = 50) -> str:
        """Draw a progress bar"""
        if total == 0:
            return "[" + " " * width + "] 0%"
        
        filled = int((current / total) * width)
        bar = "█" * filled + "░" * (width - filled)
        pct = (current / total) * 100
        return f"[{bar}] {pct:.1f}%"
    
    def display(self):
        """Display the dashboard"""
        self.clear_screen()
        
        print("=" * 80)
        print(" " * 20 + "📊 BASESCAN ANALYSIS DASHBOARD")
        print("=" * 80)
        print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Transaction Fetching Status
        print("🔷 TRANSACTION FETCHING")
        print("-" * 80)
        tx_count = self.get_transaction_count()
        print(f"Transactions Fetched: {tx_count:,}")
        print(f"Start Block:          {self.start_block:,} (Solana token inception)")
        print()
        
        # Analysis Status
        print("🔷 VOLUME ANALYSIS")
        print("-" * 80)
        analysis = self.get_analysis_status()
        
        if analysis['has_results']:
            print(f"Status:               ✅ Complete")
            print(f"Total Transactions:   {analysis['total_transactions']:,}")
            print(f"Farming Addresses:    {analysis['farming_addresses']}")
            print(f"Organic Addresses:     {analysis['organic_addresses']}")
            print()
            print(f"Farmed Volume:        {analysis['farmed_percentage']:.2f}%")
            print(f"Organic Volume:        {analysis['organic_percentage']:.2f}%")
            print()
            print(f"Progress:             {self.draw_progress_bar(analysis['farmed_percentage'], 100)}")
        else:
            print(f"Status:               ⏸️  Not Started")
            print("Run: python3 main.py")
        
        print()
        print()
        
        # AERO Rewards Status
        print("🔷 AERO REWARDS ANALYSIS")
        print("-" * 80)
        aero = self.get_aero_status()
        
        if aero['has_results']:
            print(f"Status:               ✅ Complete")
            print(f"Addresses with AERO:   {aero['addresses_with_aero']}")
            print(f"Total AERO Received:   {aero['total_received']:,.2f} AERO")
            print(f"Total AERO Sold:       {aero['total_sold']:,.2f} AERO")
            if aero['total_received'] > 0:
                sell_pct = (aero['total_sold'] / aero['total_received']) * 100
                print(f"Sell Ratio:           {sell_pct:.2f}%")
        elif 'current_address' in aero:
            print(f"Status:               🟢 Running")
            print(f"Addresses Processed:   {aero.get('current_address', 0)}/{aero.get('total_addresses', 0)}")
            if aero.get('total_addresses', 0) > 0:
                pct = (aero.get('current_address', 0) / aero.get('total_addresses', 0)) * 100
                print(f"Progress:             {self.draw_progress_bar(aero.get('current_address', 0), aero.get('total_addresses', 0))}")
                print(f"Completion:           {pct:.1f}%")
            print(f"Transfers Found:       {aero.get('transfers_found', 0):,}")
        else:
            print(f"Status:               ⏸️  Not Started")
            print("Run: python3 aero_tracker_basescan.py")
        
        print()
        print("=" * 80)
        print("Press Ctrl+C to exit | Auto-refresh every 5 seconds")
        print("=" * 80)

def main():
    """Main dashboard loop"""
    dashboard = BasescanDashboard()
    
    try:
        while True:
            dashboard.display()
            time.sleep(5)  # Refresh every 5 seconds
    except KeyboardInterrupt:
        print("\n\nDashboard stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main()


