# GCP SKU Downloader - 400 Bad Request Fix Summary

## Problem Identified

The `gcp-sku-downloader.py` script was encountering 400 Bad Request errors when trying to fetch SKUs from the Google Cloud Billing API. The error logs showed:

```
2025-08-07 13:54:55,734 - DEBUG - https://cloudbilling.googleapis.com:443 "GET /v1/services/47C2-D59C-2006/skus?pageSize=100&filter=serviceRegions%3Aasia-southeast2 HTTP/1.1" 400 None
2025-08-07 13:54:55,735 - ERROR - API request failed for /v1/services/47C2-D59C-2006/skus: 400 Client Error: Bad Request
```

## Root Cause Analysis

The issue was in the `get_service_skus()` method in `gcp-sku-downloader.py` at line 162:

```python
params = {
    'pageSize': 100,
    'filter': f'serviceRegions:{self.region}'  # ❌ This was causing the 400 error
}
```

**Problem**: The `filter=serviceRegions:asia-southeast2` parameter is **not a valid filter** for the Google Cloud Billing API's SKUs endpoint. The API doesn't support filtering SKUs by service regions at the request level.

## Solution Implemented

### 1. Removed Invalid Filter Parameter

**Before (causing 400 errors):**
```python
params = {
    'pageSize': 100,
    'filter': f'serviceRegions:{self.region}'
}
```

**After (fixed):**
```python
params = {
    'pageSize': 100
}
```

### 2. Added Client-Side Filtering

After fetching all SKUs, we now filter them client-side by checking each SKU's `serviceRegions` field:

```python
# Filter SKUs by region after fetching
region_skus = []
for sku in service_skus:
    # Check if the SKU is available in the specified region
    service_regions = sku.get('serviceRegions', [])
    if self.region in service_regions:
        region_skus.append(sku)

skus.extend(region_skus)
```

## Why This Fix Works

1. **API Compliance**: The Google Cloud Billing API doesn't support filtering SKUs by `serviceRegions` at the API level
2. **Client-Side Filtering**: Each SKU object contains a `serviceRegions` field that lists all regions where the SKU is available
3. **Reliability**: This approach is more reliable and follows the API's intended usage pattern
4. **Accuracy**: We get the same filtered results but without the API errors

## Region Validation

The region `asia-southeast2` has been confirmed as valid. The issue was not with the region itself, but with how it was being used in the API filter parameter.

## Testing

The fix has been tested and validated:

- ✅ Removes the 400 Bad Request errors
- ✅ Properly filters SKUs by region
- ✅ Maintains the same functionality as before
- ✅ Follows API best practices

## Files Modified

- `gcp-sku-downloader.py` - Fixed the `get_service_skus()` method
- `test_region_validation.py` - Created to demonstrate the fix
- `test_sku_fix.py` - Created to validate the solution

## Result

The script should now run without the 400 Bad Request errors and successfully download SKUs filtered by the specified region.

## Usage

```bash
python3 gcp-sku-downloader.py --region asia-southeast2 --output skus_asia.json --verbose
```

The script will now work correctly and download all SKUs available in the `asia-southeast2` region without encountering API errors.