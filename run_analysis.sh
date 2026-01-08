#!/bin/bash
# Script to run the full Basescan analysis
# Uses small chunks to work around free tier limitations

echo "=================================================================================="
echo "BASESCAN ANALYSIS - FREE TIER MODE"
echo "=================================================================================="
echo ""
echo "  Using very small chunks (10 transactions per page)"
echo "   This will take a LONG time for 1.8M transactions"
echo "   Estimated: ~180,000 pages × 0.25s = ~12.5 hours"
echo ""
echo "You can:"
echo "  1. Run in background: nohup python3 main.py > analysis.log 2>&1 &"
echo "  2. Monitor progress: python3 dashboard.py"
echo "  3. Check logs: tail -f analysis.log"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

echo ""
echo "Starting analysis..."
python3 main.py


