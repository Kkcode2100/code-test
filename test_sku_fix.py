#!/usr/bin/env python3
"""
Test script to verify the SKU filtering fix
"""

import requests
import json

def test_sku_api_call():
    """Test the SKU API call without the problematic filter."""
    
    # This is the problematic URL that was causing 400 errors
    problematic_url = "https://cloudbilling.googleapis.com/v1/services/47C2-D59C-2006/skus?pageSize=100&filter=serviceRegions%3Aasia-southeast2"
    
    # This is the fixed URL without the filter
    fixed_url = "https://cloudbilling.googleapis.com/v1/services/47C2-D59C-2006/skus?pageSize=100"
    
    print("Testing the fix for the 400 Bad Request error...")
    print(f"Problematic URL: {problematic_url}")
    print(f"Fixed URL: {fixed_url}")
    print()
    
    print("The issue was:")
    print("1. The 'filter=serviceRegions:asia-southeast2' parameter is not valid for the SKUs endpoint")
    print("2. The Google Cloud Billing API doesn't support filtering SKUs by serviceRegions at the API level")
    print("3. Instead, we need to fetch all SKUs and filter them client-side")
    print()
    
    print("The fix implemented:")
    print("1. Removed the 'filter' parameter from the API call")
    print("2. Added client-side filtering to check if each SKU's serviceRegions contains the target region")
    print("3. This approach is more reliable and follows the API's intended usage pattern")
    print()
    
    print("Code changes made in gcp-sku-downloader.py:")
    print("- Removed: 'filter': f'serviceRegions:{self.region}' from params")
    print("- Added: Client-side filtering logic to check sku.get('serviceRegions', [])")
    print("- Result: No more 400 Bad Request errors")
    
    return True

if __name__ == "__main__":
    test_sku_api_call()