# GCP Price Sync Debug & Monitoring Guide

This guide explains how to effectively capture script output, errors, and troubleshoot issues using the enhanced debug features.

## 🚀 Quick Start

### 1. Make the monitor script executable
```bash
chmod +x monitor_script.sh
```

### 2. Run with monitoring
```bash
# Basic execution with full monitoring
./monitor_script.sh discover-morpheus-plans

# Enable extra debug features
./monitor_script.sh --debug sync-gcp-data
```

## 📊 Enhanced Logging Features

### Automatic Log Files
The enhanced script creates multiple log files automatically:

- **Main log**: `gcp_price_sync_YYYYMMDD_HHMMSS.log` - All script output
- **Monitor log**: `logs/monitor_YYYYMMDD_HHMMSS.log` - Monitoring wrapper output
- **Script output**: `logs/script_output_YYYYMMDD_HHMMSS.log` - Python script output
- **Error log**: `logs/errors_YYYYMMDD_HHMMSS.log` - Error messages only

### Debug Features Included

1. **🌈 Colored Console Output** - Different colors for different log levels
2. **🌐 HTTP Traffic Capture** - All API requests/responses logged
3. **⏱️ Performance Monitoring** - Function execution times tracked
4. **📋 Detailed Error Context** - Enhanced error messages with request details
5. **📊 Real-time Statistics** - Progress tracking and summaries
6. **🔍 Session Tracking** - Each run gets a unique session ID

## 🛠️ Configuration Options

### Environment Variables
```bash
# Enable debug mode
export DEBUG_MODE="true"

# Set log level (DEBUG, INFO, WARNING, ERROR)
export LOG_LEVEL="DEBUG"

# Capture HTTP requests/responses
export CAPTURE_HTTP_TRAFFIC="true"

# Enable performance monitoring
export PERFORMANCE_MONITORING="true"

# Custom log file location
export LOG_FILE="my_custom_log.log"
```

### Command Line Options
```bash
# Enable debug mode for single run
python3 gcp-price-sync-debug.py --debug discover-morpheus-plans

# Disable HTTP capture for privacy
python3 gcp-price-sync-debug.py --no-http-capture sync-gcp-data

# Disable performance monitoring
python3 gcp-price-sync-debug.py --no-performance create-prices

# Custom log file
python3 gcp-price-sync-debug.py --log-file /path/to/custom.log validate
```

## 📱 Monitoring Commands

### Real-time Monitoring
```bash
# Monitor logs in real-time
./monitor_script.sh --monitor-only

# Tail specific log files
./monitor_script.sh --tail-logs "*error*"
./monitor_script.sh --tail-logs "gcp_price_sync_*"
```

### Log Analysis
```bash
# Show available log files
./monitor_script.sh --show-logs

# Analyze a specific log file
./monitor_script.sh --analyze-logs logs/gcp_price_sync_20240101_120000.log

# Clean up old log files (7+ days)
./monitor_script.sh --cleanup
```

## 🔍 Troubleshooting Guide

### Common Issues & Solutions

#### 1. **Authentication Errors**
```bash
# Check if logged in
gcloud auth list

# Login if needed
gcloud auth login

# Check service account
echo $GOOGLE_APPLICATION_CREDENTIALS
```

**Debug Output to Look For:**
- `❌ Failed to get gcloud token`
- `🔐 Using service account from GOOGLE_APPLICATION_CREDENTIALS`
- `✅ GCP access token obtained`

#### 2. **API Connection Issues**
```bash
# Test Morpheus API connectivity
curl -k -H "Authorization: BEARER $MORPHEUS_TOKEN" \
  "$MORPHEUS_URL/api/whoami"
```

**Debug Output to Look For:**
- `🚨 HTTP Error [REQ-ID] GET endpoint: 401/403/500`
- `🔗 Morpheus API Client initialized`
- `🌐 HTTP REQUEST [REQ-ID] GET/POST url`

#### 3. **Performance Issues**
**Debug Output to Look For:**
- `⏱️ Performance Analysis: Average duration: X.XXXs`
- `✅ EXIT function | Duration: X.XXXs | Success`
- `📊 Progress: X/Y (XX.X%)`

#### 4. **Data Issues**
**Debug Output to Look For:**
- `📊 Filter Analysis: family: X plans`
- `🎯 SKU discovery complete: X unique SKUs found`
- `📈 By Machine Family: family: X SKUs`

## 📋 Example Troubleshooting Session

### Step 1: Run with full debugging
```bash
./monitor_script.sh --debug discover-morpheus-plans
```

### Step 2: Check for errors
```bash
# Quick error check
grep -i error logs/script_output_*.log

# Analyze the latest log
./monitor_script.sh --analyze-logs $(ls -t logs/script_output_*.log | head -1)
```

### Step 3: Share logs for help
```bash
# Get session summary
tail -20 logs/monitor_*.log

# Share relevant error context
grep -A5 -B5 "❌\|ERROR\|CRITICAL" logs/script_output_*.log
```

## 🎯 Providing Debug Information

When seeking help, share these details:

### 1. Session Information
```bash
# Session ID and timing
grep "NEW SESSION STARTED\|Command completed\|Fatal error" logs/script_output_*.log
```

### 2. Error Context
```bash
# Errors with context
grep -A10 -B5 "❌\|ERROR\|CRITICAL" logs/script_output_*.log
```

### 3. HTTP Issues
```bash
# API call failures
grep "🚨 HTTP Error\|HTTP.*[45][0-9][0-9]" logs/script_output_*.log
```

### 4. Configuration
```bash
# Environment and config
grep "Configuration:\|Base URL:\|Region:" logs/script_output_*.log
```

### 5. Performance Data
```bash
# Performance issues
grep "Duration:\|Performance Analysis" logs/script_output_*.log
```

## 🔧 Advanced Usage

### Real-time Monitoring in Terminal
```bash
# Terminal 1: Run the script
./monitor_script.sh sync-gcp-data

# Terminal 2: Monitor logs
tail -f logs/script_output_*.log | grep --color=always "ERROR\|WARNING\|✅\|❌"
```

### Log Filtering
```bash
# Show only HTTP requests
grep "🌐 HTTP" logs/script_output_*.log

# Show only errors and warnings
grep "❌\|⚠️\|ERROR\|WARNING" logs/script_output_*.log

# Show performance metrics
grep "Duration:\|📊 Progress" logs/script_output_*.log
```

### Custom Analysis
```bash
# Count API calls by endpoint
grep "HTTP REQUEST" logs/script_output_*.log | awk '{print $6}' | sort | uniq -c

# Average response times
grep "Duration:" logs/script_output_*.log | awk '{print $NF}' | sed 's/s//' | awk '{sum+=$1; n++} END {print "Average:", sum/n, "seconds"}'

# Error distribution
grep "❌\|ERROR" logs/script_output_*.log | awk -F'|' '{print $3}' | sort | uniq -c
```

## 💡 Tips for Effective Debugging

1. **Always use the monitor script** for comprehensive logging
2. **Check authentication first** before investigating other issues
3. **Look for patterns** in HTTP errors (429 = rate limit, 401 = auth, etc.)
4. **Monitor performance** for long-running operations
5. **Save successful runs** as baseline for comparison
6. **Use grep with context** (-A5 -B5) to see surrounding log entries
7. **Check timestamps** to correlate events
8. **Monitor disk space** when debug logging is enabled

## 🆘 Getting Help

When reporting issues, include:

1. **Command that failed**: `./monitor_script.sh sync-gcp-data`
2. **Session ID**: Found in log files
3. **Error messages**: With context (5 lines before/after)
4. **Environment**: GCP region, Morpheus URL, Python version
5. **Timing**: When the error occurred
6. **Log file**: The relevant `script_output_*.log` file

This enhanced debugging setup will help identify and resolve issues much faster!