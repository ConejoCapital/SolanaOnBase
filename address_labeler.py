#!/usr/bin/env python3
"""
Address Labeling System
Identifies and classifies addresses with sources for each classification
"""
import requests
import json
import time
import os
from datetime import datetime
from collections import defaultdict

# Configuration
API_KEYS = ["rs_65f982566a2ca518dfcd4c4e", "rs_e1254323f750d4644cf0d772"]
API_URL = "https://api.routescan.io/v2/network/mainnet/evm/8453/etherscan/api"
LABELS_FILE = "address_labels.json"

# Known addresses (pre-researched)
KNOWN_ADDRESSES = {
    # Aerodrome pools
    "0xb30540172f1b37d1ee1d109e49f883e935e69219": {
        "label": "Aerodrome vAMM SOL/WETH Pool",
        "type": "dex_pool",
        "protocol": "Aerodrome",
        "source": "https://aerodrome.finance/pools",
        "verified": True
    },
    # Known routers/aggregators
    "0xcf77a3ba9a5ca399b7c97c74d54e5b1beb874e43": {
        "label": "Aerodrome Router",
        "type": "dex_router",
        "protocol": "Aerodrome",
        "source": "https://docs.aerodrome.finance/",
        "verified": True
    },
    # Universal Router (Uniswap)
    "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad": {
        "label": "Uniswap Universal Router",
        "type": "dex_router",
        "protocol": "Uniswap",
        "source": "https://docs.uniswap.org/contracts/v3/reference/deployments",
        "verified": True
    },
    # 1inch
    "0x1111111254eeb25477b68fb85ed929f73a960582": {
        "label": "1inch Aggregation Router V5",
        "type": "aggregator",
        "protocol": "1inch",
        "source": "https://docs.1inch.io/docs/aggregation-protocol/smart-contract-addresses",
        "verified": True
    },
}

class AddressLabeler:
    def __init__(self):
        self.current_key_index = 0
        self.last_request_time = 0
        self.labels = {}
        self.load_existing_labels()
        
    def load_existing_labels(self):
        """Load existing labels from file"""
        if os.path.exists(LABELS_FILE):
            try:
                with open(LABELS_FILE, 'r') as f:
                    self.labels = json.load(f)
                print(f"📂 Loaded {len(self.labels)} existing labels")
            except:
                self.labels = {}
        
        # Add known addresses
        for addr, info in KNOWN_ADDRESSES.items():
            if addr not in self.labels:
                self.labels[addr.lower()] = info
    
    def save_labels(self):
        """Save labels to file"""
        with open(LABELS_FILE, 'w') as f:
            json.dump(self.labels, f, indent=2)
    
    def _rate_limit_wait(self):
        """Ensure 1 second between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self.last_request_time = time.time()
    
    def _get_api_key(self):
        return API_KEYS[self.current_key_index % len(API_KEYS)]
    
    def get_contract_info(self, address):
        """Get contract source code/name from API"""
        self._rate_limit_wait()
        
        params = {
            'module': 'contract',
            'action': 'getsourcecode',
            'address': address,
            'apikey': self._get_api_key()
        }
        
        try:
            response = requests.get(API_URL, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1' and data.get('result'):
                    result = data['result'][0]
                    return {
                        'contract_name': result.get('ContractName', ''),
                        'is_contract': bool(result.get('ContractName')),
                        'is_verified': result.get('ContractName') != '',
                        'source': f"https://basescan.org/address/{address}"
                    }
        except Exception as e:
            print(f"  Error getting contract info: {e}")
        
        return None
    
    def get_address_transactions(self, address, limit=100):
        """Get recent transactions for an address"""
        self._rate_limit_wait()
        
        params = {
            'module': 'account',
            'action': 'txlist',
            'address': address,
            'page': 1,
            'offset': limit,
            'sort': 'desc',
            'apikey': self._get_api_key()
        }
        
        try:
            response = requests.get(API_URL, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1':
                    return data.get('result', [])
        except Exception as e:
            print(f"  Error getting transactions: {e}")
        
        return []
    
    def classify_by_behavior(self, address, stats):
        """Classify address based on transaction patterns"""
        classification = {
            "label": "Unknown",
            "type": "unknown",
            "confidence": 0,
            "reasons": [],
            "source": "Behavioral analysis"
        }
        
        tx_count = stats.get('tx_count', 0)
        counterparties = stats.get('counterparties', 0)
        balance_ratio = stats.get('balance_ratio', 0)
        net_ratio = stats.get('net_ratio', 0)
        total_volume = stats.get('total_volume', 0)
        
        # DEX Pool indicators
        if tx_count > 10000 and counterparties > 100:
            classification['label'] = "Likely DEX Pool/AMM"
            classification['type'] = "dex_pool"
            classification['confidence'] = 80
            classification['reasons'].append(f"Very high tx count ({tx_count:,}) with many counterparties ({counterparties})")
        
        # Wash trader indicators
        elif balance_ratio > 0.85 and net_ratio < 0.15 and counterparties < 10:
            classification['label'] = "Suspected Wash Trader"
            classification['type'] = "wash_trader"
            classification['confidence'] = 85
            classification['reasons'].append(f"High balance ratio ({balance_ratio:.1%}) = nearly equal buys/sells")
            classification['reasons'].append(f"Low net ratio ({net_ratio:.1%}) = minimal net position")
            classification['reasons'].append(f"Few counterparties ({counterparties}) = trading with limited addresses")
            if total_volume > 100000:
                classification['confidence'] = 95
                classification['reasons'].append(f"High volume ({total_volume:,.0f} SOL) amplifies wash trading impact")
        
        # Bot/automated trader
        elif tx_count > 1000 and stats.get('avg_time_between', 999999) < 60:
            classification['label'] = "Automated Trader/Bot"
            classification['type'] = "bot"
            classification['confidence'] = 70
            classification['reasons'].append(f"High frequency trading (avg {stats.get('avg_time_between', 0):.0f}s between txs)")
        
        # LP provider
        elif counterparties < 5 and tx_count > 100 and balance_ratio > 0.7:
            classification['label'] = "Liquidity Provider"
            classification['type'] = "lp_provider"
            classification['confidence'] = 60
            classification['reasons'].append(f"Trading primarily with pools (only {counterparties} counterparties)")
        
        # Regular trader
        elif counterparties > 10 and balance_ratio < 0.7:
            classification['label'] = "Organic Trader"
            classification['type'] = "organic"
            classification['confidence'] = 70
            classification['reasons'].append(f"Diverse counterparties ({counterparties})")
            classification['reasons'].append(f"Unbalanced trading ({balance_ratio:.1%} ratio)")
        
        return classification
    
    def label_address(self, address, stats=None):
        """Label an address with all available information"""
        address = address.lower()
        
        # Check if already labeled with high confidence
        if address in self.labels:
            existing = self.labels[address]
            if existing.get('verified') or existing.get('confidence', 0) > 80:
                return existing
        
        print(f"  Labeling {address[:10]}...", end=' ')
        
        label_info = {
            "address": address,
            "label": "Unknown",
            "type": "unknown",
            "confidence": 0,
            "reasons": [],
            "source": "",
            "basescan_url": f"https://basescan.org/address/{address}",
            "labeled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Check known addresses first
        if address in KNOWN_ADDRESSES:
            label_info.update(KNOWN_ADDRESSES[address])
            label_info['confidence'] = 100
            print(f"Known: {label_info['label']}")
            self.labels[address] = label_info
            return label_info
        
        # Try to get contract info
        contract_info = self.get_contract_info(address)
        if contract_info and contract_info.get('is_contract'):
            contract_name = contract_info.get('contract_name', '')
            label_info['is_contract'] = True
            label_info['contract_name'] = contract_name
            label_info['source'] = contract_info['source']
            
            # Try to identify based on contract name
            name_lower = contract_name.lower()
            if 'pool' in name_lower or 'pair' in name_lower:
                label_info['label'] = f"DEX Pool: {contract_name}"
                label_info['type'] = "dex_pool"
                label_info['confidence'] = 90
                label_info['reasons'].append(f"Verified contract name contains 'pool/pair'")
            elif 'router' in name_lower:
                label_info['label'] = f"DEX Router: {contract_name}"
                label_info['type'] = "dex_router"
                label_info['confidence'] = 90
                label_info['reasons'].append(f"Verified contract name contains 'router'")
            elif 'aggregator' in name_lower or 'swap' in name_lower:
                label_info['label'] = f"Swap Contract: {contract_name}"
                label_info['type'] = "aggregator"
                label_info['confidence'] = 85
                label_info['reasons'].append(f"Verified contract name indicates swap functionality")
            elif contract_name:
                label_info['label'] = f"Contract: {contract_name}"
                label_info['type'] = "contract"
                label_info['confidence'] = 70
                label_info['reasons'].append(f"Verified contract")
            
            print(f"Contract: {label_info['label']}")
        
        # If we have stats, classify by behavior
        elif stats:
            behavior_class = self.classify_by_behavior(address, stats)
            label_info.update(behavior_class)
            print(f"Behavior: {label_info['label']} ({label_info['confidence']}%)")
        else:
            # EOA (externally owned account)
            label_info['is_contract'] = False
            label_info['label'] = "EOA (Wallet)"
            label_info['type'] = "wallet"
            label_info['confidence'] = 50
            print("EOA")
        
        self.labels[address] = label_info
        return label_info
    
    def label_all_from_transactions(self, transactions_file='transactions.json'):
        """Label all addresses found in transactions"""
        print("=" * 80)
        print("🏷️ ADDRESS LABELING SYSTEM")
        print("=" * 80)
        print()
        
        # Load transactions
        with open(transactions_file, 'r') as f:
            transactions = json.load(f)
        
        print(f"📂 Loaded {len(transactions):,} transactions")
        
        # Build address stats
        address_stats = defaultdict(lambda: {
            'received_volume': 0, 'sent_volume': 0,
            'received_count': 0, 'sent_count': 0,
            'counterparties': set(),
            'timestamps': []
        })
        
        for tx in transactions:
            from_addr = tx.get('from', '').lower()
            to_addr = tx.get('to', '').lower()
            
            decimals = int(tx.get('tokenDecimal', 9))
            value = int(tx.get('value', 0)) / (10 ** decimals)
            timestamp = int(tx.get('timeStamp', 0))
            
            address_stats[from_addr]['sent_volume'] += value
            address_stats[from_addr]['sent_count'] += 1
            address_stats[from_addr]['counterparties'].add(to_addr)
            address_stats[from_addr]['timestamps'].append(timestamp)
            
            address_stats[to_addr]['received_volume'] += value
            address_stats[to_addr]['received_count'] += 1
            address_stats[to_addr]['counterparties'].add(from_addr)
            address_stats[to_addr]['timestamps'].append(timestamp)
        
        # Calculate derived stats
        for addr, stats in address_stats.items():
            total_vol = stats['sent_volume'] + stats['received_volume']
            sent = stats['sent_volume']
            received = stats['received_volume']
            
            stats['total_volume'] = total_vol
            stats['tx_count'] = stats['sent_count'] + stats['received_count']
            stats['counterparties'] = len(stats['counterparties'])
            stats['balance_ratio'] = min(sent, received) / max(sent, received) if max(sent, received) > 0 else 0
            stats['net_ratio'] = abs(received - sent) / (total_vol / 2) if total_vol > 0 else 0
            
            timestamps = sorted(stats['timestamps'])
            if len(timestamps) > 1:
                diffs = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
                stats['avg_time_between'] = sum(diffs) / len(diffs)
            else:
                stats['avg_time_between'] = 999999
        
        # Sort by volume
        sorted_addresses = sorted(
            address_stats.items(),
            key=lambda x: x[1]['total_volume'],
            reverse=True
        )
        
        print(f"📊 Found {len(sorted_addresses):,} unique addresses")
        print()
        
        # Label top addresses first (most impactful)
        labeled_count = 0
        total_to_label = min(500, len(sorted_addresses))  # Label top 500
        
        print(f"🏷️ Labeling top {total_to_label} addresses by volume...")
        print()
        
        for addr, stats in sorted_addresses[:total_to_label]:
            if not addr or addr == '0x0000000000000000000000000000000000000000':
                continue
            
            self.label_address(addr, dict(stats))
            labeled_count += 1
            
            # Save periodically
            if labeled_count % 50 == 0:
                self.save_labels()
                print(f"  💾 Saved {labeled_count} labels...")
        
        # Final save
        self.save_labels()
        
        print()
        print("=" * 80)
        print(f"✅ LABELING COMPLETE")
        print("=" * 80)
        print(f"   Total addresses labeled: {len(self.labels)}")
        print()
        
        # Summary by type
        type_counts = defaultdict(int)
        for label_info in self.labels.values():
            type_counts[label_info.get('type', 'unknown')] += 1
        
        print("📊 Labels by type:")
        for label_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"   {label_type}: {count}")
        
        return self.labels
    
    def export_for_dashboard(self):
        """Export labels in a format suitable for the dashboard"""
        export_data = {
            "labels": self.labels,
            "summary": {
                "total_labeled": len(self.labels),
                "by_type": defaultdict(int),
                "verified_count": 0,
                "high_confidence_count": 0
            },
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        for label_info in self.labels.values():
            export_data["summary"]["by_type"][label_info.get('type', 'unknown')] += 1
            if label_info.get('verified'):
                export_data["summary"]["verified_count"] += 1
            if label_info.get('confidence', 0) >= 80:
                export_data["summary"]["high_confidence_count"] += 1
        
        export_data["summary"]["by_type"] = dict(export_data["summary"]["by_type"])
        
        with open('address_labels_export.json', 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"📤 Exported labels to address_labels_export.json")
        return export_data

def main():
    labeler = AddressLabeler()
    labeler.label_all_from_transactions()
    labeler.export_for_dashboard()

if __name__ == "__main__":
    main()
