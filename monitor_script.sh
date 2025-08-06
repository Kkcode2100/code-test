#!/bin/bash

# Enhanced Script Monitor for GCP Price Sync Tool
# This script provides comprehensive monitoring and logging capabilities

set -euo pipefail

# Configuration
SCRIPT_NAME="gcp-price-sync-debug.py"
LOG_DIR="./logs"
SESSION_ID=$(date +%Y%m%d_%H%M%S)
MONITOR_LOG="$LOG_DIR/monitor_${SESSION_ID}.log"
SCRIPT_OUTPUT="$LOG_DIR/script_output_${SESSION_ID}.log"
ERROR_LOG="$LOG_DIR/errors_${SESSION_ID}.log"
PERFORMANCE_LOG="$LOG_DIR/performance_${SESSION_ID}.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Create log directory
mkdir -p "$LOG_DIR"

# Function to log with timestamp
log_with_timestamp() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$MONITOR_LOG"
}

# Function to show usage
show_usage() {
    echo -e "${CYAN}Enhanced GCP Price Sync Monitor${NC}"
    echo ""
    echo "Usage: $0 [OPTIONS] COMMAND"
    echo ""
    echo "Commands:"
    echo "  discover-morpheus-plans    - List all GCP service plans"
    echo "  sync-gcp-data             - Fetch GCP SKUs and save locally"
    echo "  create-prices             - Create prices in Morpheus"
    echo "  create-price-sets         - Group prices into price sets"
    echo "  map-plans-to-price-sets   - Link price sets to service plans"
    echo "  validate                  - Validate pricing on service plans"
    echo ""
    echo "Options:"
    echo "  --debug                   - Enable debug mode"
    echo "  --monitor-only           - Monitor without executing (tail existing logs)"
    echo "  --cleanup                - Clean up old log files"
    echo "  --show-logs              - Show available log files"
    echo "  --tail-logs [pattern]    - Tail specific log files"
    echo "  --analyze-logs [file]    - Analyze log file for issues"
    echo "  --help                   - Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  DEBUG_MODE               - Enable debug logging (true/false)"
    echo "  LOG_LEVEL                - Set log level (DEBUG/INFO/WARNING/ERROR)"
    echo "  CAPTURE_HTTP_TRAFFIC     - Capture HTTP requests/responses (true/false)"
    echo "  PERFORMANCE_MONITORING   - Enable performance monitoring (true/false)"
    echo ""
    echo "Examples:"
    echo "  $0 discover-morpheus-plans"
    echo "  $0 --debug sync-gcp-data"
    echo "  $0 --monitor-only"
    echo "  $0 --analyze-logs logs/gcp_price_sync_20240101_120000.log"
}

# Function to clean up old logs
cleanup_logs() {
    echo -e "${YELLOW}Cleaning up old log files...${NC}"
    find "$LOG_DIR" -name "*.log" -mtime +7 -delete 2>/dev/null || true
    find "$LOG_DIR" -name "*.log" -type f -exec ls -lh {} \; | head -20
    echo -e "${GREEN}Cleanup complete${NC}"
}

# Function to show available logs
show_logs() {
    echo -e "${CYAN}Available log files:${NC}"
    if [ -d "$LOG_DIR" ]; then
        find "$LOG_DIR" -name "*.log" -type f -printf '%T@ %Tc %s %p\n' | sort -n | tail -20 | while read time size file; do
            size_mb=$(echo "scale=2; $size/1024/1024" | bc -l 2>/dev/null || echo "0")
            echo -e "${GREEN}$(echo $time | cut -d' ' -f2-)${NC} (${size_mb}MB) ${file}"
        done
    else
        echo "No log directory found"
    fi
}

# Function to tail specific logs
tail_logs() {
    local pattern=${1:-"*.log"}
    echo -e "${CYAN}Tailing logs matching: $pattern${NC}"
    
    if [ -d "$LOG_DIR" ]; then
        # Find matching files
        local files=($(find "$LOG_DIR" -name "$pattern" -type f 2>/dev/null | head -5))
        
        if [ ${#files[@]} -eq 0 ]; then
            echo -e "${RED}No log files found matching: $pattern${NC}"
            return 1
        fi
        
        echo -e "${GREEN}Following ${#files[@]} log file(s):${NC}"
        for file in "${files[@]}"; do
            echo "  - $file"
        done
        echo ""
        
        # Use multitail if available, otherwise fallback to tail
        if command -v multitail >/dev/null 2>&1; then
            multitail "${files[@]}"
        else
            tail -f "${files[@]}"
        fi
    else
        echo -e "${RED}Log directory not found${NC}"
        return 1
    fi
}

# Function to analyze logs for issues
analyze_logs() {
    local log_file="$1"
    
    if [ ! -f "$log_file" ]; then
        echo -e "${RED}Log file not found: $log_file${NC}"
        return 1
    fi
    
    echo -e "${CYAN}Analyzing log file: $log_file${NC}"
    echo ""
    
    # Summary statistics
    local total_lines=$(wc -l < "$log_file")
    local errors=$(grep -c "ERROR\|CRITICAL\|❌" "$log_file" 2>/dev/null || echo "0")
    local warnings=$(grep -c "WARNING\|⚠️" "$log_file" 2>/dev/null || echo "0")
    local http_requests=$(grep -c "HTTP REQUEST" "$log_file" 2>/dev/null || echo "0")
    local performance_entries=$(grep -c "Duration:" "$log_file" 2>/dev/null || echo "0")
    
    echo -e "${GREEN}📊 Log Analysis Summary:${NC}"
    echo "  Total lines: $total_lines"
    echo "  Errors: $errors"
    echo "  Warnings: $warnings"
    echo "  HTTP requests: $http_requests"
    echo "  Performance entries: $performance_entries"
    echo ""
    
    # Show recent errors
    if [ "$errors" -gt 0 ]; then
        echo -e "${RED}🚨 Recent Errors:${NC}"
        grep "ERROR\|CRITICAL\|❌" "$log_file" | tail -10
        echo ""
    fi
    
    # Show recent warnings
    if [ "$warnings" -gt 0 ]; then
        echo -e "${YELLOW}⚠️ Recent Warnings:${NC}"
        grep "WARNING\|⚠️" "$log_file" | tail -5
        echo ""
    fi
    
    # Performance analysis
    if [ "$performance_entries" -gt 0 ]; then
        echo -e "${BLUE}⏱️ Performance Analysis:${NC}"
        grep "Duration:" "$log_file" | awk '{
            for(i=1;i<=NF;i++) {
                if($i ~ /Duration:/) {
                    duration = $(i+1)
                    gsub(/s.*/, "", duration)
                    sum += duration
                    count++
                    if(duration > max) max = duration
                    if(min == 0 || duration < min) min = duration
                }
            }
        } END {
            if(count > 0) {
                printf "  Average duration: %.3fs\n", sum/count
                printf "  Max duration: %.3fs\n", max
                printf "  Min duration: %.3fs\n", min
                printf "  Total operations: %d\n", count
            }
        }'
        echo ""
    fi
    
    # HTTP error analysis
    local http_errors=$(grep -c "HTTP.*[45][0-9][0-9]" "$log_file" 2>/dev/null || echo "0")
    if [ "$http_errors" -gt 0 ]; then
        echo -e "${RED}🌐 HTTP Errors:${NC}"
        grep "HTTP.*[45][0-9][0-9]" "$log_file" | tail -5
        echo ""
    fi
    
    # Show session start/end times
    local session_start=$(grep "NEW SESSION STARTED" "$log_file" | head -1 | cut -d'|' -f1 | xargs)
    local session_end=$(grep "Command completed successfully\|Fatal error" "$log_file" | tail -1 | cut -d'|' -f1 | xargs)
    
    if [ -n "$session_start" ]; then
        echo -e "${GREEN}📅 Session Info:${NC}"
        echo "  Started: $session_start"
        if [ -n "$session_end" ]; then
            echo "  Ended: $session_end"
        else
            echo "  Status: Still running or incomplete"
        fi
        echo ""
    fi
}

# Function to monitor script execution in real-time
monitor_execution() {
    local cmd="$1"
    shift
    local args=("$@")
    
    log_with_timestamp "Starting monitoring session: $SESSION_ID"
    log_with_timestamp "Command: $cmd ${args[*]}"
    log_with_timestamp "Monitor log: $MONITOR_LOG"
    log_with_timestamp "Script output: $SCRIPT_OUTPUT"
    log_with_timestamp "Error log: $ERROR_LOG"
    
    # Set environment variables for enhanced logging
    export DEBUG_MODE="true"
    export LOG_LEVEL="DEBUG"
    export CAPTURE_HTTP_TRAFFIC="true"
    export PERFORMANCE_MONITORING="true"
    
    echo -e "${GREEN}🚀 Starting GCP Price Sync Tool with monitoring...${NC}"
    echo -e "${CYAN}Session ID: $SESSION_ID${NC}"
    echo -e "${BLUE}Logs will be saved to: $LOG_DIR${NC}"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to interrupt (logs will be preserved)${NC}"
    echo ""
    
    # Create named pipes for real-time output processing
    local stdout_pipe=$(mktemp -u)
    local stderr_pipe=$(mktemp -u)
    mkfifo "$stdout_pipe" "$stderr_pipe"
    
    # Background processes to handle output
    tee "$SCRIPT_OUTPUT" < "$stdout_pipe" &
    local stdout_pid=$!
    
    tee "$ERROR_LOG" < "$stderr_pipe" | while IFS= read -r line; do
        echo -e "${RED}[ERROR]${NC} $line"
    done &
    local stderr_pid=$!
    
    # Function to cleanup on exit
    cleanup_on_exit() {
        log_with_timestamp "Cleaning up monitoring processes..."
        kill $stdout_pid $stderr_pid 2>/dev/null || true
        rm -f "$stdout_pipe" "$stderr_pipe" 2>/dev/null || true
        log_with_timestamp "Monitoring session ended"
        
        echo ""
        echo -e "${CYAN}📋 Session Summary:${NC}"
        echo "  Session ID: $SESSION_ID"
        echo "  Monitor log: $MONITOR_LOG"
        echo "  Script output: $SCRIPT_OUTPUT"
        echo "  Error log: $ERROR_LOG"
        
        if [ -f "$SCRIPT_OUTPUT" ]; then
            local exit_code=$(grep "Command completed successfully" "$SCRIPT_OUTPUT" >/dev/null && echo "0" || echo "1")
            echo "  Exit status: $exit_code"
            echo "  Output size: $(wc -l < "$SCRIPT_OUTPUT") lines"
        fi
        
        echo ""
        echo -e "${GREEN}💡 To analyze this session later:${NC}"
        echo "  $0 --analyze-logs $SCRIPT_OUTPUT"
        echo ""
        echo -e "${GREEN}💡 To view logs in real-time:${NC}"
        echo "  $0 --tail-logs"
    }
    
    trap cleanup_on_exit EXIT
    
    # Start the actual script with monitoring
    log_with_timestamp "Executing: python3 $SCRIPT_NAME $cmd ${args[*]}"
    
    # Execute the Python script with proper output redirection
    if python3 "$SCRIPT_NAME" "$cmd" "${args[@]}" > "$stdout_pipe" 2> "$stderr_pipe"; then
        log_with_timestamp "Script execution completed successfully"
        echo -e "${GREEN}✅ Script completed successfully${NC}"
    else
        local exit_code=$?
        log_with_timestamp "Script execution failed with exit code: $exit_code"
        echo -e "${RED}❌ Script failed with exit code: $exit_code${NC}"
        return $exit_code
    fi
}

# Main execution
main() {
    # Check if Python script exists
    if [ ! -f "$SCRIPT_NAME" ]; then
        echo -e "${RED}Error: $SCRIPT_NAME not found in current directory${NC}"
        exit 1
    fi
    
    # Parse arguments
    case "${1:-}" in
        --help|-h)
            show_usage
            exit 0
            ;;
        --cleanup)
            cleanup_logs
            exit 0
            ;;
        --show-logs)
            show_logs
            exit 0
            ;;
        --tail-logs)
            tail_logs "${2:-*.log}"
            exit 0
            ;;
        --analyze-logs)
            if [ -z "${2:-}" ]; then
                echo -e "${RED}Error: Please specify a log file to analyze${NC}"
                exit 1
            fi
            analyze_logs "$2"
            exit 0
            ;;
        --monitor-only)
            echo -e "${CYAN}Monitoring mode - watching existing logs...${NC}"
            tail_logs "*.log"
            exit 0
            ;;
        discover-morpheus-plans|sync-gcp-data|create-prices|create-price-sets|map-plans-to-price-sets|validate)
            monitor_execution "$@"
            ;;
        *)
            echo -e "${RED}Error: Invalid command or option${NC}"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"