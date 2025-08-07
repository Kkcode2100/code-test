# Comprehensive GCP Price Sync Guide

This guide explains how to use the new comprehensive GCP SKU downloader and enhanced price sync scripts to ensure complete coverage of GCP pricing data.

## Overview

The new approach consists of two main components:

1. **`gcp-sku-downloader.py`** - Downloads the complete GCP SKU catalog for a region
2. **`gcp-price-sync-enhanced-v2.py`** - Uses the downloaded catalog to create comprehensive pricing data

## Prerequisites

1. **GCP Authentication**: Ensure you have gcloud CLI configured with appropriate permissions
2. **Morpheus Access**: Valid Morpheus API token and server URL
3. **Python Dependencies**: Install required packages

```bash
pip install requests urllib3
```

## Step 1: Download Complete SKU Catalog

### Basic Usage

```bash
# Download SKUs for a specific region
python gcp-sku-downloader.py --region asia-southeast2

# Download with custom output file
python gcp-sku-downloader.py --region us-central1 --output gcp_skus_us.json

# Enable verbose logging
python gcp-sku-downloader.py --region europe-west1 --verbose
```

### What the Downloader Does

1. **Fetches All Services**: Gets all available GCP billing services
2. **Downloads SKUs**: For each service, downloads all SKUs available in the specified region
3. **Organizes Data**: Categorizes SKUs by service and resource family
4. **Saves Results**: Creates structured JSON files with comprehensive metadata

### Output Files

- **Main Catalog**: `gcp_skus_YYYYMMDD_HHMMSS.json` (complete SKU data)
- **Summary**: `gcp_skus_YYYYMMDD_HHMMSS_summary.json` (high-level overview)
- **Log File**: `gcp-sku-download.log` (detailed execution log)

### Example Output Structure

```json
{
  "metadata": {
    "region": "asia-southeast2",
    "download_timestamp": "2024-01-15T10:30:00",
    "total_services": 150,
    "total_skus": 2500
  },
  "services": {
    "6F81-5844-456A": {
      "service_info": {
        "service_id": "6F81-5844-456A",
        "display_name": "Compute Engine",
        "business_entity_name": "Google Cloud Platform",
        "sku_count": 45
      },
      "skus": [...],
      "categories": {
        "Compute": [...],
        "Storage": [...]
      }
    }
  },
  "sku_summary": {
    "Compute": 1200,
    "Storage": 800,
    "Network": 300,
    "Database": 200
  }
}
```

## Step 2: Enhanced Price Sync

### Basic Usage

```bash
# Sync using downloaded catalog
python gcp-price-sync-enhanced-v2.py --sku-catalog gcp_skus_20240115_103000.json

# Dry run to see what would be created
python gcp-price-sync-enhanced-v2.py --sku-catalog gcp_skus_20240115_103000.json --dry-run

# Validate existing sync results
python gcp-price-sync-enhanced-v2.py --sku-catalog gcp_skus_20240115_103000.json --validate-only
```

### What the Enhanced Sync Does

1. **Loads SKU Catalog**: Reads the comprehensive SKU data
2. **Processes SKUs**: Normalizes and categorizes SKU information
3. **Creates Pricing Data**: Generates Morpheus-compatible pricing entries
4. **Creates Price Sets**: Organizes prices into logical groups
5. **Validates Results**: Checks coverage and completeness

### Enhanced Features

- **Comprehensive Coverage**: Uses all available SKUs, not just filtered subsets
- **Better Categorization**: Intelligent categorization of SKUs by service type
- **Storage Pricing**: Enhanced detection and handling of storage-related SKUs
- **Validation**: Built-in validation and coverage reporting
- **Dry Run Mode**: Safe testing without making changes

## Complete Workflow Example

### 1. Download SKU Catalog

```bash
# Download complete catalog for Asia Southeast 2
python gcp-sku-downloader.py --region asia-southeast2 --output gcp_skus_asia.json --verbose
```

Expected output:
```
GCP SKU CATALOG DOWNLOAD SUMMARY
============================================================
Region: asia-southeast2
Download Time: 2024-01-15T10:30:00
Total Services: 150
Total SKUs: 2500

Top SKU Categories:
  Compute: 1200 SKUs
  Storage: 800 SKUs
  Network: 300 SKUs
  Database: 200 SKUs
```

### 2. Validate and Sync

```bash
# First, do a dry run to see what would be created
python gcp-price-sync-enhanced-v2.py --sku-catalog gcp_skus_asia.json --dry-run

# If satisfied, run the actual sync
python gcp-price-sync-enhanced-v2.py --sku-catalog gcp_skus_asia.json

# Validate the results
python gcp-price-sync-enhanced-v2.py --sku-catalog gcp_skus_asia.json --validate-only
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   ```bash
   # Ensure gcloud is authenticated
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

2. **Permission Errors**
   - Ensure your GCP account has billing catalog access
   - Check that the service account has appropriate roles

3. **Network Issues**
   - Verify internet connectivity
   - Check firewall settings
   - Ensure DNS resolution works

4. **Rate Limiting**
   - The scripts include built-in rate limiting
   - If you encounter 429 errors, increase delays in the code

### Debug Mode

```bash
# Enable verbose logging for both scripts
python gcp-sku-downloader.py --region asia-southeast2 --verbose
python gcp-price-sync-enhanced-v2.py --sku-catalog skus.json --verbose
```

## Advanced Usage

### Custom Categories

You can modify the categorization logic in `gcp-price-sync-enhanced-v2.py`:

```python
def _categorize_sku(self, sku):
    # Add custom categorization logic here
    service_name = sku['service_name'].lower()
    
    if 'ai' in service_name or 'ml' in service_name:
        return 'ai_ml'
    # ... existing logic
```

### Filtering SKUs

To sync only specific categories:

```python
# In the sync script, modify the get_all_skus method
def get_filtered_skus(self, categories=['compute', 'storage']):
    filtered_skus = []
    for category in categories:
        if category in self.processed_skus:
            filtered_skus.extend(self.processed_skus[category])
    return filtered_skus
```

### Custom Price Sets

Modify the price set creation logic:

```python
def create_custom_price_sets(self, sku_processor):
    # Create custom price set logic
    custom_sets = []
    
    # Example: Create price sets by service
    for service_name in sku_processor.get_unique_services():
        custom_sets.append({
            'name': f"{PRICE_PREFIX}-{service_name.upper()}-PRICES",
            'code': f"gcp-{service_name.lower()}-prices",
            # ... other fields
        })
    
    return custom_sets
```

## Monitoring and Maintenance

### Regular Updates

1. **Download Fresh Catalogs**: Run the downloader periodically to get updated pricing
2. **Validate Coverage**: Use the validation mode to check sync status
3. **Monitor Logs**: Check log files for errors or warnings

### Performance Considerations

- **Large Catalogs**: For regions with many SKUs, the download may take 10-30 minutes
- **API Limits**: The scripts include rate limiting to respect GCP API limits
- **Memory Usage**: Large catalogs may require significant memory

### Backup and Recovery

```bash
# Backup existing pricing data before sync
python gcp-price-sync-enhanced-v2.py --sku-catalog skus.json --validate-only > backup_report.txt

# If issues occur, you can restore from backup or re-run the sync
```

## Comparison with Previous Approach

| Feature | Previous Script | Enhanced v2 |
|---------|----------------|-------------|
| SKU Coverage | Limited by filters | Complete catalog |
| Storage Pricing | Basic detection | Enhanced categorization |
| Error Handling | Basic | Comprehensive |
| Validation | Manual | Built-in |
| Dry Run | No | Yes |
| Logging | Basic | Detailed |
| Categorization | Simple | Intelligent |

## Best Practices

1. **Always Use Dry Run First**: Test with `--dry-run` before actual sync
2. **Download Fresh Catalogs**: Use recent SKU data for accurate pricing
3. **Monitor Coverage**: Regularly validate sync results
4. **Backup Before Changes**: Keep backups of existing pricing data
5. **Use Verbose Logging**: Enable `--verbose` for troubleshooting

## Support

For issues or questions:

1. Check the log files for detailed error information
2. Verify GCP authentication and permissions
3. Ensure Morpheus server is accessible
4. Review the troubleshooting section above

The enhanced approach provides much better coverage and reliability for GCP pricing synchronization.