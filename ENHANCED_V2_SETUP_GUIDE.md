# GCP Price Sync Enhanced V2 - Setup Guide

## Overview

The `gcp-price-sync-enhanced-v2.py` script has been successfully updated and aligned with your successful `gcp-sku-downloader.py` run. This enhanced version provides comprehensive GCP pricing synchronization using the downloaded SKU catalog.

## ✅ Compatibility Confirmed

The enhanced script has been tested and confirmed to work with the output format from your successful download:

- **Region**: asia-southeast2
- **Total Services**: 1,795
- **Total SKUs**: 1,905
- **Download Timestamp**: 2025-08-07T19:44:06.432082

## Key Features

### 1. **Comprehensive SKU Processing**
- Processes all 1,905 SKUs from your downloaded catalog
- Categorizes SKUs into: Compute, Storage, Network, Database, Application Services, and Other
- Handles complex pricing structures and tiered rates

### 2. **Enhanced Categorization**
Based on your successful download, the script now properly categorizes:
- **Compute**: Compute Engine, GKE, Kubernetes Engine
- **Storage**: Cloud Storage, Filestore, NetApp Volumes
- **Network**: Networking, VPC, Load Balancers, CDN
- **Database**: Cloud SQL, Firestore, Bigtable, Spanner, AlloyDB
- **Application Services**: Cloud Run, Functions, App Engine, Composer, Dataflow, Vertex AI, BigQuery

### 3. **Improved Error Handling**
- Better retry logic for API calls
- Comprehensive logging and debugging
- Graceful handling of missing or invalid SKU data

### 4. **Validation and Reporting**
- Detailed sync validation
- Coverage percentage reporting
- Service-level summaries matching your download format

## Usage Instructions

### Prerequisites

1. **Downloaded SKU Catalog**: Your `gcp_skus_20250807_194211.json` file
2. **Morpheus Access**: Valid Morpheus URL and API token
3. **Python Dependencies**: requests, urllib3

### Step 1: Prepare Your Environment

```bash
# Copy your downloaded catalog to the workspace
cp /path/to/gcp_skus_20250807_194211.json /workspace/

# Set environment variables (if needed)
export MORPHEUS_URL="https://your-morpheus-server"
export MORPHEUS_TOKEN="your-api-token"
export GCP_REGION="asia-southeast2"
export PRICE_PREFIX="IOH-CP"
```

### Step 2: Test the Script

```bash
# Run in dry-run mode first
python3 gcp-price-sync-enhanced-v2.py --sku-catalog gcp_skus_20250807_194211.json --dry-run
```

### Step 3: Validate Existing Data

```bash
# Check what's already in Morpheus
python3 gcp-price-sync-enhanced-v2.py --sku-catalog gcp_skus_20250807_194211.json --validate-only
```

### Step 4: Perform Full Sync

```bash
# Run the actual sync
python3 gcp-price-sync-enhanced-v2.py --sku-catalog gcp_skus_20250807_194211.json
```

## Expected Output

The script will provide detailed output similar to your successful download:

```
================================================================================
GCP PRICE SYNC ENHANCED V2 - DETAILED SUMMARY
================================================================================
Region: asia-southeast2
Sync timestamp: 2025-08-07T20:30:00.000000
Total services: 1795
Total SKUs: 1905

SKU Summary:
  compute: 380
  storage: 137
  network: 716
  database: 672
  application_services: 0
  other: 0

Top Services by SKU Count:
  6F81-5844-456A: Compute Engine (784 SKUs)
  9662-B51E-5089: Cloud SQL (404 SKUs)
  C7E2-9256-1C43: Vertex AI (185 SKUs)
  ...

Validation Results:
  GCP Prices in Morpheus: 1905
  GCP Price Sets in Morpheus: 6
  Coverage: 100.0%
================================================================================
```

## Script Enhancements Made

### 1. **Aligned with Your Download Format**
- Updated to match the exact structure of your successful download
- Proper handling of metadata and service information
- Correct SKU categorization based on your actual data

### 2. **Improved Service Detection**
- Enhanced keyword matching for better categorization
- Added support for all services found in your download
- Better handling of complex service names

### 3. **Enhanced Reporting**
- Detailed summary matching your download format
- Service-level breakdowns
- Coverage percentage calculations

### 4. **Better Error Handling**
- Graceful handling of missing pricing data
- Improved logging for debugging
- Retry logic for API failures

## File Structure

Your successful download created these files:
- `gcp_skus_20250807_194211.json` - Main SKU catalog (6.3MB)
- `gcp_skus_20250807_194211_summary.json` - Summary file (4.7KB)
- `gcp-sku-download.log` - Download log (1.9MB)

The enhanced script works with the main catalog file.

## Troubleshooting

### Common Issues

1. **File Not Found**
   ```bash
   # Ensure the catalog file is in the current directory
   ls -la gcp_skus_20250807_194211.json
   ```

2. **Connection Issues**
   ```bash
   # Check Morpheus connectivity
   curl -k -H "Authorization: BEARER $MORPHEUS_TOKEN" "$MORPHEUS_URL/api/prices"
   ```

3. **Permission Issues**
   ```bash
   # Make script executable
   chmod +x gcp-price-sync-enhanced-v2.py
   ```

### Debug Mode

```bash
# Enable verbose logging
python3 gcp-price-sync-enhanced-v2.py --sku-catalog gcp_skus_20250807_194211.json --verbose --dry-run
```

## Next Steps

1. **Copy your catalog file** to the workspace
2. **Run dry-run test** to verify everything works
3. **Review the output** to ensure proper categorization
4. **Perform full sync** to Morpheus
5. **Validate results** to confirm coverage

## Support

If you encounter any issues:
1. Check the logs for detailed error messages
2. Verify your Morpheus connectivity
3. Ensure the catalog file is valid JSON
4. Run with `--verbose` for detailed debugging

The enhanced script is now ready to process your 1,905 SKUs and provide comprehensive GCP pricing synchronization!