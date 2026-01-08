#!/bin/bash

# Keep processes running even when laptop sleeps
# This script monitors and restarts processes if they stop
# Run this in the background: nohup bash keep_alive.sh > keep_alive.log 2>&1 &

cd "$(dirname "$0")"
LOG_FILE="keep_alive.log"
MAIN_SCRIPT="main.py"
AERO_SCRIPT="aero_tracker_basescan.py"
DASHBOARD_UPDATER="update_dashboard.py"
BACKFILL_SCRIPT="robust_backfill_v2.py"
BLOCK_SYNC_SCRIPT="update_block_sync.py"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to check if process is actually running (not just zombie)
is_process_running() {
    local script_name=$1
    if pgrep -f "$script_name" > /dev/null; then
        # Check if it's actually running (not zombie)
        local pid=$(pgrep -f "$script_name" | head -1)
        if [ -n "$pid" ]; then
            # Check if process state is not 'Z' (zombie)
            local state=$(ps -o state= -p "$pid" 2>/dev/null)
            if [ "$state" != "Z" ] && [ -n "$state" ]; then
                return 0
            fi
        fi
    fi
    return 1
}

# Function to check and restart process
check_and_restart() {
    local script_name=$1
    local script_file=$2
    local log_file=$3
    
    if ! is_process_running "$script_name"; then
        log "⚠️  $script_name not running, restarting..."
        cd "$(dirname "$0")"  # Ensure we're in the right directory
        
        # Start the process
        nohup python3 "$script_file" > "$log_file" 2>&1 &
        local pid=$!
        
        # Wait and check multiple times (process may take time to fully start)
        sleep 5
        local attempts=0
        local started=false
        while [ $attempts -lt 3 ]; do
            if is_process_running "$script_name"; then
                log "✅ $script_name restarted (PID: $pid)"
                started=true
                break
            fi
            sleep 2
            attempts=$((attempts + 1))
        done
        
        # If still not running, check for errors
        if [ "$started" = false ]; then
            log "❌ Failed to start $script_name (PID was: $pid)"
            if [ -f "$log_file" ]; then
                local last_lines=$(tail -5 "$log_file" 2>/dev/null)
                if [ -n "$last_lines" ]; then
                    log "   Checking log for errors..."
                    echo "$last_lines" | while IFS= read -r line; do
                        if echo "$line" | grep -qi "error\|exception\|traceback\|failed"; then
                            log "   Error found: $line"
                        fi
                    done
                fi
            fi
        fi
    fi
}

log "=========================================="
log "Keep-Alive Monitor Started"
log "=========================================="
log "Monitoring: robust_backfill, main.py, block_sync, aero_tracker"
log "Check interval: 60 seconds"
log "=========================================="

# Main monitoring loop
while true; do
    # PRIORITY 1: Robust backfill (most important - gets missing transactions)
    check_and_restart "python3 robust_backfill.py" "$BACKFILL_SCRIPT" "backfill.log"
    
    # PRIORITY 2: Main analysis (fetches new transactions from current block)
    check_and_restart "python3 main.py" "$MAIN_SCRIPT" "analysis.log"
    
    # PRIORITY 3: Block sync updater (updates dashboard with current progress)
    if ! is_process_running "update_block_sync.py --loop"; then
        log "⚠️  Block sync updater not running, restarting..."
        nohup python3 "$BLOCK_SYNC_SCRIPT" --loop > block_sync_updater.log 2>&1 &
        pid=$!
        sleep 2
        if is_process_running "update_block_sync.py --loop"; then
            log "✅ Block sync updater restarted (PID: $pid)"
        else
            log "❌ Failed to start block sync updater"
        fi
    fi
    
    # PRIORITY 4: AERO tracking (secondary analysis)
    # check_and_restart "python3 aero_tracker_basescan.py" "$AERO_SCRIPT" "aero_tracker.log"
    
    # Log current status every check
    TX_COUNT=$(python3 -c "import json; print(len(json.load(open('transactions.json'))))" 2>/dev/null || echo "?")
    log "📊 Current transaction count: $TX_COUNT"
    
    # Wait 60 seconds before next check
    sleep 60
done


