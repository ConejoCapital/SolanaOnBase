#!/bin/bash
# Auto-restart script for analysis processes
# Checks if processes are running and restarts if needed

cd "$(dirname "$0")"

MAIN_LOG="analysis.log"
AERO_LOG="aero_tracker.log"
MAIN_SCRIPT="main.py"
AERO_SCRIPT="aero_tracker_basescan.py"

# Function to check if process is running
is_running() {
    pgrep -f "$1" > /dev/null
}

# Function to start main analysis
start_main() {
    if ! is_running "$MAIN_SCRIPT"; then
        echo "$(date): Starting main analysis..." >> restart.log
        nohup python3 "$MAIN_SCRIPT" >> "$MAIN_LOG" 2>&1 &
        echo "$(date): Main analysis started (PID: $!)" >> restart.log
    fi
}

# Function to start AERO tracking
start_aero() {
    if ! is_running "$AERO_SCRIPT"; then
        echo "$(date): Starting AERO tracking..." >> restart.log
        nohup python3 "$AERO_SCRIPT" >> "$AERO_LOG" 2>&1 &
        echo "$(date): AERO tracking started (PID: $!)" >> restart.log
    fi
}

# Check and restart if needed
echo "$(date): Checking processes..."

if is_running "$MAIN_SCRIPT"; then
    echo "✅ Main analysis is running"
else
    echo "⚠️  Main analysis not running, restarting..."
    start_main
fi

if is_running "$AERO_SCRIPT"; then
    echo "✅ AERO tracking is running"
else
    echo "⚠️  AERO tracking not running, restarting..."
    start_aero
fi

echo "$(date): Check complete"


