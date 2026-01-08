# Methodology Improvements for Farming Address Classification

## Problem Identified

The initial analysis classified 14 addresses as "farming" with 98.5% farmed volume and only 1.5% organic volume. However, several issues were identified:

1. **Infrastructure Misclassification**: Many addresses had very high transaction counts (10k-100k+) with few counterparties, suggesting they were infrastructure (LPs, AMMs, bridges) rather than farming addresses.

2. **Too Few Farming Addresses**: 14 addresses farming 98.5% of volume seemed suspicious.

3. **Too Low Organic Volume**: 1.5% organic volume seemed unrealistically low.

## Root Cause Analysis

### Address Pattern Analysis

Analysis of the 14 "farming" addresses revealed:

| Address | Tx Count | Counterparties | Volume | Likely Type |
|---------|----------|----------------|--------|-------------|
| 0xecbe25d69f0bc85c8eb42ae9a3b9a212dced96e6 | 102,111 | 1 | $3.6M | **Infrastructure** |
| 0x7c460d504c1600fb8c030ff0d3b7e02bab268309 | 31,048 | 2 | $11.4M | **Infrastructure** |
| 0x88fec94eb9f11376e0dcb31ea7babc278d6035c3 | 38,487 | 3 | $434K | **Infrastructure** |
| 0xdb0253708c484ac5b6710b3b6ee7ac896f643d33 | 23,385 | 1 | $228K | **Infrastructure** |
| 0xcbcfdaaae40d3466f0c68dc73f8fc6cf29e6c988 | 10,732 | 4 | $532K | **Infrastructure** |
| 0xab7ae77b7df5f10caaaca6049abe1d05416b680d | 16,086 | 5 | $172K | **Infrastructure** |

**Pattern**: Very high transaction counts (10k-100k+) with very few counterparties (1-5) is characteristic of:
- Liquidity pools
- Automated market makers (AMMs)
- Bridge contracts
- Other infrastructure contracts

These should **NOT** be classified as farming addresses.

## Improvements Implemented

### 1. Infrastructure Exclusion Criteria

Added explicit checks to exclude infrastructure addresses:

```python
# Infrastructure indicators:
# 1. Very high transaction count (>5000) with very few counterparties (<5) = likely LP/AMM
# 2. Extremely high transaction count (>10000) even with more counterparties = likely infrastructure
# 3. High volume (>1M) with very few counterparties (<3) = likely infrastructure

is_likely_infrastructure = False

if stats['tx_count'] > 5000 and unique_counterparties < 5:
    is_likely_infrastructure = True
elif stats['tx_count'] > 10000:
    is_likely_infrastructure = True
elif total_volume > 1000000 and unique_counterparties < 3:
    is_likely_infrastructure = True

# Skip infrastructure addresses
if is_likely_infrastructure:
    continue
```

### 2. Stricter Farming Criteria

Updated farming classification to require moderate transaction counts:

```python
# Signal 1: High round-trip ratio AND low net position
if volume_ratio > 0.9 and net_ratio < 0.1 and total_volume > 1000:
    # Only count if ALSO has low counterparty diversity AND moderate tx count
    if unique_counterparties < 10 and stats['tx_count'] < 5000:
        farming_signals += 1

# Signal 2: Moderate volume but very few counterparties
if total_volume > 10000 and unique_counterparties < 5 and stats['tx_count'] < 5000:
    farming_signals += 1
```

### 3. Enhanced Infrastructure Whitelist

Expanded the whitelist of known infrastructure addresses (though many are now caught by the pattern-based exclusion):

- WETH
- AERO token
- SushiSwap Router
- Aerodrome Router V2
- Aerodrome Router
- Uniswap V3 Router
- 1inch Aggregator
- CoW Protocol
- 0x Exchange Proxy
- And more...

## Expected Results

### Before Improvements
- **Farming Addresses**: 14
- **Farmed Volume**: 98.5%
- **Organic Volume**: 1.5%

### After Improvements
- **Farming Addresses**: ~4-5 (addresses with moderate tx counts)
- **Farmed Volume**: Lower percentage (infrastructure excluded)
- **Organic Volume**: Higher percentage (more realistic)

## Classification Logic

### Infrastructure (Excluded)
- High tx count (>5000) + low counterparties (<5)
- Very high tx count (>10000)
- High volume (>1M) + very few counterparties (<3)

### Farming (Wash Trading)
- Moderate tx count (<5000)
- Very few counterparties (<5-10)
- High round-trip ratio (>90%)
- Low net position (<10% of volume)
- Multiple signals required (2+)

### Organic (Real Trading)
- Low round-trip ratio (<50%) OR
- Many counterparties (>10) OR
- High net position (>30% of volume)

## Verification

To verify addresses are not infrastructure:

1. **Check Transaction Count**: Infrastructure typically has 5k+ transactions
2. **Check Counterparties**: Infrastructure may have few counterparties but very high tx count
3. **Check on Basedscan**: Look for contract labels or known infrastructure tags
4. **Check Contract Type**: Infrastructure addresses are often contracts, not EOAs

## References

- Based on analysis of 14 addresses with suspicious patterns
- Pattern recognition: High tx count + low counterparties = Infrastructure
- Improved classification prevents infrastructure misclassification

