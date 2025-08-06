# Testing Guide for GCP Price Sync Script

## ✅ **YES, the script is ready to test!**

The script has been:
- ✅ Syntax validated (compiles without errors)
- ✅ Dependencies installed
- ✅ Help functionality tested
- ✅ All fixes implemented based on Morpheus API documentation

## Pre-Testing Checklist

### 1. Environment Setup
Make sure you have the following configured:

```bash
# Required environment variables
export MORPHEUS_URL="https://your-morpheus-instance"
export MORPHEUS_TOKEN="your-api-token"
export GCP_REGION="asia-southeast2"  # or your desired region
export PRICE_PREFIX="IOH-CP"  # or your desired prefix
```

### 2. Prerequisites
- ✅ Python 3.7+ (you have 3.13.3)
- ✅ Dependencies installed (`requests`, `urllib3`)
- ✅ Valid Morpheus API token with pricing permissions
- ✅ GCP CLI (`gcloud`) installed and authenticated (for sync-gcp-data step)
- ✅ Network access to both Morpheus instance and GCP APIs

## Testing Approach

### **Safe Testing Strategy (Recommended)**

Start with read-only operations first:

```bash
# 1. Test API connectivity and discover existing plans
python3 gcp-price-sync-fixed.py discover-morpheus-plans

# 2. Test validation (read-only)
python3 gcp-price-sync-fixed.py validate
```

### **Gradual Testing (if read-only tests pass)**

```bash
# 3. Test GCP data sync (creates local file only)
python3 gcp-price-sync-fixed.py sync-gcp-data

# 4. Test price creation (creates individual prices)
python3 gcp-price-sync-fixed.py create-prices

# 5. Test price set creation (groups prices)
python3 gcp-price-sync-fixed.py create-price-sets

# 6. Test plan mapping (links price sets to plans)
python3 gcp-price-sync-fixed.py map-plans-to-price-sets

# 7. Final validation
python3 gcp-price-sync-fixed.py validate
```

## What to Expect

### Success Indicators:
- ✅ No HTTP 4xx/5xx errors
- ✅ Progressive status messages with counts
- ✅ Validation shows plans with pricing
- ✅ Log messages indicate successful operations

### Common Issues to Watch For:
- ❌ **Authentication errors**: Check `MORPHEUS_TOKEN`
- ❌ **Network errors**: Check `MORPHEUS_URL` and connectivity
- ❌ **GCP auth errors**: Run `gcloud auth login` first
- ❌ **Permission errors**: Ensure API token has pricing permissions

## Output Files Created:
- `gcp_plan_skus.json` - Local cache of GCP pricing data

## Safety Features:
- ✅ **Idempotent**: Can run multiple times safely
- ✅ **Preserves existing data**: Won't delete existing price sets
- ✅ **Comprehensive logging**: Full error details for debugging
- ✅ **Progress indicators**: Shows what's happening

## Troubleshooting:

### If step 1 (discover-morpheus-plans) fails:
- Check `MORPHEUS_URL` and `MORPHEUS_TOKEN`
- Verify network connectivity to Morpheus instance
- Confirm API token has read permissions

### If step 2 (sync-gcp-data) fails:
- Run `gcloud auth login` to authenticate with GCP
- Check `GCP_REGION` is a valid GCP region
- Verify GCP APIs are enabled for your project

### If steps 3-6 fail:
- Check the detailed error logs in the output
- Verify API token has create/update permissions for pricing
- Review the `FIXES_EXPLAINED.md` for API structure details

## Next Steps After Testing:

Once testing is successful:
1. Schedule the script to run periodically for price updates
2. Monitor logs for any API changes or issues
3. Adjust `PRICE_PREFIX` and `GCP_REGION` as needed

## **Ready to Test? Start with:**

```bash
python3 gcp-price-sync-fixed.py discover-morpheus-plans
```

This will validate your Morpheus API connectivity and show you existing GCP service plans without making any changes.