#!/usr/bin/env python3
"""
Auto-sync script: Updates dashboard_export.json and pushes to GitHub every 5 minutes.
This keeps the Vercel deployment updated with the latest data.
"""
import json
import time
import subprocess
import os
from collections import defaultdict
from datetime import datetime

SOL_PRICE_USD = 137.86
POOL = "0xb30540172f1b37d1ee1d109e49f883e935e69219"
SYNC_INTERVAL = 300  # 5 minutes

def update_dashboard_export():
    """Regenerate dashboard_export.json from transactions.json"""
    try:
        with open('transactions.json', 'r') as f:
            transactions = json.load(f)
    except Exception as e:
        print(f"Error loading transactions: {e}")
        return None
    
    # Build stats
    address_stats = defaultdict(lambda: {'sent': 0, 'received': 0, 'count': 0, 'cp': set()})
    
    for tx in transactions:
        from_addr = tx.get('from', '').lower()
        to_addr = tx.get('to', '').lower()
        value = int(tx.get('value', 0)) / (10**9)
        
        address_stats[from_addr]['sent'] += value
        address_stats[from_addr]['count'] += 1
        address_stats[from_addr]['cp'].add(to_addr)
        address_stats[to_addr]['received'] += value
        address_stats[to_addr]['count'] += 1
        address_stats[to_addr]['cp'].add(from_addr)
    
    # Calculate volumes
    total_vol = sum(int(tx.get('value', 0)) / (10**9) for tx in transactions)
    pool_stats = address_stats.get(POOL, {})
    pool_vol = pool_stats.get('sent', 0)
    non_pool_vol = total_vol - pool_vol
    
    # Classify
    wash_list, organic_list = [], []
    
    for addr, s in address_stats.items():
        if not addr or addr == POOL: continue
        
        sent, received = s['sent'], s['received']
        total_activity = sent + received
        if total_activity <= 0 or sent <= 0: continue
        
        cp = len(s['cp'])
        balance_ratio = min(sent, received) / max(sent, received) if max(sent, received) > 0 else 0
        net_ratio = abs(received - sent) / (total_activity / 2) if total_activity > 0 else 0
        
        addr_info = {
            'address': addr,
            'total_volume_sol': round(sent, 2),
            'total_volume_usd': round(sent * SOL_PRICE_USD, 2),
            'balance_ratio': round(balance_ratio * 100, 1),
            'counterparties': cp,
            'tx_count': s['count'],
            'label': '',
            'label_type': '',
            'label_confidence': 0
        }
        
        if balance_ratio > 0.85 and net_ratio < 0.15 and cp < 10 and total_activity > 100:
            addr_info['label'] = "🚜 Wash Trader"
            addr_info['label_type'] = "wash_trader"
            addr_info['label_confidence'] = 95
            wash_list.append(addr_info)
        else:
            addr_info['label'] = "🌱 Organic" if cp > 5 else "👤 User"
            addr_info['label_type'] = "organic"
            addr_info['label_confidence'] = 70
            organic_list.append(addr_info)
    
    wash_list.sort(key=lambda x: x['total_volume_sol'], reverse=True)
    organic_list.sort(key=lambda x: x['total_volume_sol'], reverse=True)
    
    wash_vol = sum(a['total_volume_sol'] for a in wash_list)
    organic_vol = sum(a['total_volume_sol'] for a in organic_list)
    
    blocks = [int(tx.get('blockNumber', 0)) for tx in transactions if tx.get('blockNumber')]
    
    export = {
        'summary': {
            'transactions_analyzed': len(transactions),
            'unique_addresses': len(address_stats),
            'holders_on_basescan': 4238,
            'target_transactions': 2352771,
            'progress_percentage': round(len(transactions) / 2352771 * 100, 1),
            'total_volume_sol': round(total_vol, 2),
            'total_volume_usd': round(total_vol * SOL_PRICE_USD, 2),
            'sol_price_usd': SOL_PRICE_USD,
            'pool_volume_sol': round(pool_vol, 2),
            'pool_volume_pct': round(pool_vol / total_vol * 100, 1) if total_vol > 0 else 0,
            'non_pool_volume_sol': round(non_pool_vol, 2),
            'wash_volume_sol': round(wash_vol, 2),
            'wash_volume_usd': round(wash_vol * SOL_PRICE_USD, 2),
            'wash_percentage': round(wash_vol / non_pool_vol * 100, 1) if non_pool_vol > 0 else 0,
            'organic_volume_sol': round(organic_vol, 2),
            'organic_volume_usd': round(organic_vol * SOL_PRICE_USD, 2),
            'organic_percentage': round(organic_vol / non_pool_vol * 100, 1) if non_pool_vol > 0 else 0,
            'wash_address_count': len(wash_list),
            'organic_address_count': len(organic_list),
            'block_sync': {
                'synced_block': max(blocks) if blocks else 0,
                'min_block': min(blocks) if blocks else 0,
                'token_start_block': 38699339
            },
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        'wash_trading_addresses': wash_list,
        'organic_addresses': organic_list
    }
    
    # Try to preserve evidence from existing export
    try:
        with open('dashboard_export.json', 'r') as f:
            old = json.load(f)
            if 'wash_trading_evidence' in old:
                export['wash_trading_evidence'] = old['wash_trading_evidence']
            if 'methodology' in old:
                export['methodology'] = old['methodology']
    except:
        pass
    
    with open('dashboard_export.json', 'w') as f:
        json.dump(export, f, indent=2)
    
    return len(transactions)

def push_to_github():
    """Commit and push changes to GitHub"""
    try:
        # Copy to index.html
        subprocess.run(['cp', 'dashboard_modern.html', 'index.html'], check=True)
        
        # Git add
        subprocess.run(['git', 'add', 'dashboard_export.json', 'index.html'], check=True)
        
        # Check if there are changes
        result = subprocess.run(['git', 'diff', '--cached', '--quiet'], capture_output=True)
        if result.returncode == 0:
            return False  # No changes
        
        # Commit
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        subprocess.run(['git', 'commit', '-m', f'Auto-update: {timestamp}'], check=True)
        
        # Push
        subprocess.run(['git', 'push'], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}")
        return False

def main():
    print("=" * 60)
    print("🔄 Auto-Sync GitHub for Vercel")
    print("=" * 60)
    print(f"Syncing every {SYNC_INTERVAL} seconds ({SYNC_INTERVAL // 60} minutes)")
    print("Press Ctrl+C to stop")
    print()
    
    while True:
        try:
            now = datetime.now().strftime('%H:%M:%S')
            
            # Update dashboard export
            tx_count = update_dashboard_export()
            if tx_count:
                print(f"[{now}] Updated: {tx_count:,} transactions")
                
                # Push to GitHub
                if push_to_github():
                    print(f"[{now}] ✅ Pushed to GitHub")
                else:
                    print(f"[{now}] No changes to push")
            else:
                print(f"[{now}] ❌ Error updating")
            
            time.sleep(SYNC_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n👋 Stopping auto-sync")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)

if __name__ == '__main__':
    main()
