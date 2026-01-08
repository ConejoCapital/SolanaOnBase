# SOL Token Wash Trading Analysis - Base Network

Analysis of wash trading vs organic volume for the SOL token on Base network.

## 🔗 Links
- **Token Contract**: [0x311935cd80b76769bf2ecc9d8ab7635b2139cf82](https://basescan.org/token/0x311935cd80b76769bf2ecc9d8ab7635b2139cf82)
- **Aerodrome Pool**: [0xb30540172f1b37d1ee1d109e49f883e935e69219](https://basescan.org/address/0xb30540172f1b37d1ee1d109e49f883e935e69219)

## 📊 Key Findings

Based on analysis of ~256,000 ERC-20 transfer transactions:

| Classification | Volume | Percentage | Addresses |
|----------------|--------|------------|-----------|
| 🚜 **Wash Trading** | 5,805,197 SOL | **95.6%** | 77 |
| 🌱 **Organic** | 266,966 SOL | **4.4%** | 1,431 |

### Top Wash Trader
The top wash trader (`0x7c460d...`) accounts for **68%** of all wash trading volume with:
- Only **1 counterparty** (the Aerodrome pool)
- **100% balance ratio** (buys and sells equal amounts)
- Near-zero net position despite millions in volume

## 🔍 Wash Trading Mechanism (Proven)

Wash traders execute buy and sell transactions for the **exact same amount** within seconds:

```
Block 39,109,843: SELL 84.7211 SOL → Pool
Block 39,109,844: BUY  84.7211 SOL ← Pool
Time difference: ~2 seconds
Amount difference: 0.0000 SOL (0.00%)
```

This pattern repeats thousands of times, generating volume for AERO incentives without actual trading.

## 📋 Methodology

An address is classified as **Wash Trading** if ALL criteria are met:
1. **Balance Ratio > 85%** - Buys and sells nearly equal amounts
2. **Net Position < 15%** - Minimal net accumulation/distribution
3. **Counterparties < 10** - Trades with very few addresses (usually just 1-3 DEX pools)
4. **Volume > 100 SOL** - Significant activity threshold

**Pool volume is excluded** from the wash/organic split as it represents infrastructure, not trading activity.

## 🌐 Dashboard

Open `dashboard_modern.html` in a browser or deploy to Vercel:
- Multi-page dashboard with methodology explanation
- Interactive toggle to exclude top trader for research
- Paginated address lists with labels
- Real transaction evidence with Basescan links

## 📁 Files

| File | Description |
|------|-------------|
| `dashboard_modern.html` | Interactive analysis dashboard |
| `dashboard_export.json` | Pre-computed analysis data |
| `analyzer.py` | Volume classification logic |
| `routescan_fetcher.py` | Transaction fetching from Routescan API |
| `robust_backfill_v2.py` | Historical data backfill with gap detection |

## 🚀 Deployment

This dashboard can be deployed to Vercel as a static site:

1. Push to GitHub
2. Connect repository to Vercel
3. Deploy as static site (no build required)

## 📈 Data Source

Transaction data fetched from [Routescan API](https://routescan.io/documentation/api) (Etherscan-compatible endpoint for Base network), starting from block **38,699,339** (first SOL token transaction).

---

*Analysis by [@ConejoCapital](https://github.com/ConejoCapital)*
