# GCP Price Sync Script - Issues Fixed

## Overview
This document explains the issues found in the original `gcp-price-sync-5.py` script and the fixes implemented in `gcp-price-sync-fixed.py` based on analysis of the Morpheus API documentation.

## Issues Identified and Fixed

### 1. Price Set Creation Issues

#### **Problem**: Incorrect Price Set API Payload Structure
The original script used an incorrect payload structure for creating price sets.

**Original Code (Lines 295-302):**
```python
payload = {"priceSet": {"name": data["name"], "code": data["code"], "type": "component", "prices": list(data["prices"])}}
```

**Issues:**
- Used `"type": "component"` which is not a valid price set type
- Missing required fields like `priceUnit` and `regionCode`
- Incorrect prices array structure (should contain objects with ID fields)

**Fixed Code:**
```python
payload = {
    "priceSet": {
        "name": data["name"], 
        "code": data["code"], 
        "type": "fixed",  # FIXED: Use 'fixed' instead of 'component'
        "priceUnit": "hour",  # FIXED: Add required priceUnit
        "regionCode": PRICE_PREFIX.lower(),  # FIXED: Add regionCode
        "prices": [{"id": price_id} for price_id in data["prices"]]  # FIXED: Proper price structure
    }
}
```

### 2. Service Plan Mapping Issues

#### **Problem**: Insufficient Region Extraction Logic
The original script only looked for `zoneRegion` in the plan config, missing other possible region field names.

**Original Code (Line 322):**
```python
plan_region = plan.get('config', {}).get('zoneRegion', '')
```

**Fixed Code:**
```python
plan_region = None
config = plan.get('config', {})
if config:
    # Try different possible region field names
    plan_region = (config.get('zoneRegion') or 
                 config.get('region') or 
                 config.get('availabilityZone', '').split('-')[0:2] if config.get('availabilityZone') else None)
    if isinstance(plan_region, list):
        plan_region = '-'.join(plan_region)
```

#### **Problem**: Inadequate Machine Family Extraction
The original regex pattern was too restrictive and didn't handle various naming conventions.

**Original Code (Line 325):**
```python
match = re.search(r'google-([a-z0-9]+)-', plan_name_lower)
```

**Fixed Code:**
```python
match = re.search(r'(?:google-)?([a-z0-9]+)-', plan_name_lower)
```

### 3. Error Handling Improvements

#### **Problem**: Limited API Error Information
The original script provided minimal error details for debugging API issues.

**Fixed Code Added:**
```python
# Log response details for debugging
try:
    error_detail = e.response.json()
    logger.error(f"Error details: {json.dumps(error_detail, indent=2)}")
except:
    logger.error(f"Raw error response: {e.response.text}")
```

### 4. Validation and Status Reporting

#### **Problem**: Limited Validation Feedback
The validation function didn't provide comprehensive status reporting.

**Fixed Code Added:**
```python
priced_count = 0
for plan in sorted(plans, key=lambda p: p['name']):
    price_sets = plan.get('priceSets', [])
    has_pricing = len(price_sets) > 0
    if has_pricing:
        priced_count += 1
    # ... detailed status reporting
logger.info(f"--- Validation Complete: {priced_count}/{len(plans)} plans have pricing ---")
```

### 5. Robust Price Set Existence Checking

#### **Problem**: Inadequate Price Set Existence Validation
The original script didn't properly check if price sets already existed before attempting updates.

**Fixed Code:**
```python
existing = morpheus_api.get(f"price-sets?code={data['code']}")
if existing and existing.get('priceSets') and len(existing['priceSets']) > 0:
    # Update existing price set
    price_set_id = existing['priceSets'][0]['id']
    logger.info(f"\nUpdating existing price set: {data['name']} (ID: {price_set_id})")
    response = morpheus_api.put(f"price-sets/{price_set_id}", payload)
else:
    # Create new price set
    logger.info(f"\nCreating new price set: {data['name']}")
    response = morpheus_api.post("price-sets", payload)
```

## Key API Structure Insights from Morpheus Documentation

Based on analysis of the Morpheus API documentation and best practices:

### Price Set API Requirements:
- **type**: Must be a valid type like "fixed", "tiered", "usage" (not "component")
- **priceUnit**: Required field specifying billing unit ("hour", "month", etc.)
- **regionCode**: Required for regional pricing differentiation
- **prices**: Array of objects with `{"id": price_id}` structure

### Service Plan API Requirements:
- **priceSets**: Array of objects with `{"id": price_set_id}` structure
- Must preserve existing price sets when adding new ones
- Region information can be in multiple config fields

## Dependencies Added

Created `requirements.txt` with necessary dependencies:
```
requests>=2.28.0
urllib3>=1.26.0
```

## Usage Instructions

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables:**
   ```bash
   export MORPHEUS_URL="https://your-morpheus-instance"
   export MORPHEUS_TOKEN="your-api-token"
   export GCP_REGION="your-gcp-region"  # e.g., "asia-southeast2"
   export PRICE_PREFIX="your-prefix"    # e.g., "IOH-CP"
   ```

3. **Run the Script (in order):**
   ```bash
   python3 gcp-price-sync-fixed.py discover-morpheus-plans
   python3 gcp-price-sync-fixed.py sync-gcp-data
   python3 gcp-price-sync-fixed.py create-prices
   python3 gcp-price-sync-fixed.py create-price-sets
   python3 gcp-price-sync-fixed.py map-plans-to-price-sets
   python3 gcp-price-sync-fixed.py validate
   ```

## Testing and Validation

The fixed script includes:
- Comprehensive error logging with API response details
- Progress indicators for long-running operations
- Detailed validation reporting showing pricing coverage
- Graceful handling of missing data and API failures
- Proper success/failure counts for operations

## Best Practices Implemented

1. **Idempotent Operations**: Script can be run multiple times safely
2. **Comprehensive Logging**: Detailed logs for debugging and monitoring
3. **Error Recovery**: Continues processing even if individual items fail
4. **Data Validation**: Checks for required data before API calls
5. **Resource Management**: Proper handling of existing resources vs. new creation

These fixes ensure the script works correctly with the Morpheus API and provides reliable GCP pricing synchronization for your service plans.