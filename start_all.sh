#!/bin/bash

# Startup script to launch all analysis processes
# Run this after system restart: bash start_all.sh

cd "$(dirname "$0")"

echo "=========================================="
echo "Starting All Analysis Processes"
echo "=========================================="
echo ""

# Kill any existing processes first
echo "🧹 Cleaning up old processes..."
pkill -f "python3 main.py" 2>/dev/null
pkill -f "update_dashboard.py" 2>/dev/null
pkill -f "aero_tracker_basescan.py" 2>/dev/null
pkill -f "keep_alive.sh" 2>/dev/null
sleep 2

# Start main analysis
echo "🚀 Starting main analysis..."
nohup python3 main.py > analysis.log 2>&1 &
MAIN_PID=$!
echo "   ✅ Main analysis started (PID: $MAIN_PID)"

# Start dashboard updater
echo "🚀 Starting dashboard updater..."
nohup python3 update_dashboard.py --auto-update > dashboard_updater.log 2>&1 &
DASHBOARD_PID=$!
echo "   ✅ Dashboard updater started (PID: $DASHBOARD_PID)"

# Start AERO tracker
echo "🚀 Starting AERO tracker..."
nohup python3 aero_tracker_basescan.py > aero_tracker.log 2>&1 &
AERO_PID=$!
echo "   ✅ AERO tracker started (PID: $AERO_PID)"

# Start keep-alive monitor
echo "🚀 Starting keep-alive monitor..."
nohup bash keep_alive.sh > keep_alive.log 2>&1 &
KEEPALIVE_PID=$!
echo "   ✅ Keep-alive monitor started (PID: $KEEPALIVE_PID)"

echo ""
echo "=========================================="
echo "✅ All Processes Started"
echo "=========================================="
echo ""
echo "📊 Process PIDs:"
echo "   Main analysis: $MAIN_PID"
echo "   Dashboard updater: $DASHBOARD_PID"
echo "   AERO tracker: $AERO_PID"
echo "   Keep-alive monitor: $KEEPALIVE_PID"
echo ""
echo "📈 Monitor logs:"
echo "   tail -f analysis.log"
echo "   tail -f dashboard_updater.log"
echo "   tail -f aero_tracker.log"
echo "   tail -f keep_alive.log"
echo ""
echo "🌐 Dashboard: http://localhost:8000/dashboard_modern.html"
echo ""

