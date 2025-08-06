#!/usr/bin/env python3

import requests
import json
import os
import sys
from collections import defaultdict

# Configuration
MORPHEUS_URL = os.getenv("MORPHEUS_URL", "https://xdjmorpheapp01")
MORPHEUS_TOKEN = os.getenv("MORPHEUS_TOKEN", "9fcc4426-c89a-4430-b6d7-99d5950fc1cc")
PRICE_PREFIX = os.getenv("PRICE_PREFIX", "IOH-CP")

class MorpheusApiClient:
    def __init__(self, base_url, api_token):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Authorization": f"BEARER {api_token}",
            "Content-Type": "application/json"
        }
        self.session = requests.Session()

    def _request(self, method, endpoint, payload=None, params=None):
        url = f"{self.base_url}/api/{endpoint}"
        try:
            response = self.session.request(method, url, json=payload, headers=self.headers, params=params, verify=False)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json() if response.content else None
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error for {method.upper()} {endpoint}: {e.response.status_code}")
            try:
                error_detail = e.response.json()
                print(f"Error details: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"Raw error response: {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            raise

    def get(self, endpoint, params=None):
        return self._request('get', endpoint, params=params)

    def post(self, endpoint, payload):
        return self._request('post', endpoint, payload=payload)

def analyze_existing_prices(api_client):
    """Analyze existing prices to understand the structure needed for price sets"""
    print("🔍 Analyzing existing prices...")
    
    # Get all prices with our prefix
    prices_resp = api_client.get(f"prices?max=2000&phrase={PRICE_PREFIX}")
    if not prices_resp or not prices_resp.get('prices'):
        print("❌ No prices found with prefix")
        return None
    
    prices = prices_resp['prices']
    print(f"✅ Found {len(prices)} prices with prefix {PRICE_PREFIX}")
    
    # Group by machine family and analyze price types
    price_analysis = defaultdict(lambda: defaultdict(list))
    
    for price in prices:
        code = price.get('code', '')
        price_type = price.get('priceType', '')
        name = price.get('name', '')
        
        # Extract machine family from code
        # Code format: ioh-cp.gcp.SKU_ID.region
        if '.gcp.' in code:
            parts = code.split('.')
            if len(parts) >= 3:
                # Try to extract family from the name or code
                family = extract_family_from_name(name)
                if family:
                    price_analysis[family][price_type].append({
                        'id': price['id'],
                        'code': code,
                        'name': name,
                        'priceType': price_type
                    })
    
    print("\n📊 Price Analysis by Family:")
    for family, types in price_analysis.items():
        print(f"\n🏷️  {family.upper()}:")
        for price_type, items in types.items():
            print(f"   • {price_type}: {len(items)} prices")
            if len(items) <= 3:  # Show details for small sets
                for item in items:
                    print(f"     - {item['name']}")
    
    return price_analysis

def extract_family_from_name(name):
    """Extract machine family from price name"""
    import re
    
    # Look for patterns like "IOH-CP - N2 CPU", "IOH-CP - E2 RAM", etc.
    match = re.search(r'IOH-CP\s*-\s*([A-Z0-9]+(?:D|U)?)', name.upper())
    if match:
        return match.group(1).lower()
    
    # Alternative patterns
    match = re.search(r'GCP\s*-\s*([A-Z0-9]+)', name.upper())
    if match:
        return match.group(1).lower()
    
    return None

def check_existing_price_sets(api_client):
    """Check what price sets already exist"""
    print("\n🔍 Checking existing price sets...")
    
    price_sets_resp = api_client.get(f"price-sets?max=1000&phrase={PRICE_PREFIX}")
    if price_sets_resp and price_sets_resp.get('priceSets'):
        price_sets = price_sets_resp['priceSets']
        print(f"✅ Found {len(price_sets)} existing price sets")
        
        for ps in price_sets:
            print(f"\n📦 {ps['name']} (ID: {ps['id']})")
            print(f"   Code: {ps['code']}")
            print(f"   Type: {ps.get('type', 'unknown')}")
            print(f"   Prices: {len(ps.get('prices', []))}")
            
            # Show price types in this set
            if ps.get('prices'):
                price_types = set()
                for price in ps['prices']:
                    price_types.add(price.get('priceType', 'unknown'))
                print(f"   Price Types: {', '.join(sorted(price_types))}")
    else:
        print("❌ No existing price sets found")

def suggest_price_set_strategy(price_analysis):
    """Suggest how to create valid price sets based on the analysis"""
    print("\n💡 Price Set Strategy Suggestions:")
    
    for family, types in price_analysis.items():
        print(f"\n🏷️  {family.upper()} Family:")
        
        available_types = list(types.keys())
        print(f"   Available price types: {', '.join(available_types)}")
        
        # Check what's missing for a complete "Everything" price set
        expected_types = ['cores', 'memory', 'storage']
        missing_types = [t for t in expected_types if t not in available_types]
        
        if missing_types:
            print(f"   ⚠️  Missing price types: {', '.join(missing_types)}")
            print(f"   💡 Consider creating separate price sets per type instead of 'Everything'")
        else:
            print(f"   ✅ Has all basic types - can create 'Everything' price set")
        
        # Suggest price set configurations
        if 'cores' in available_types and 'memory' in available_types:
            cores_count = len(types['cores'])
            memory_count = len(types['memory'])
            print(f"   💡 Option 1: Combined Compute price set ({cores_count} cores + {memory_count} memory)")
        
        for price_type, items in types.items():
            if len(items) > 0:
                print(f"   💡 Option 2: Separate {price_type.title()} price set ({len(items)} prices)")

def create_corrected_price_sets(api_client, price_analysis):
    """Create price sets with the correct configuration"""
    print("\n🔧 Creating corrected price sets...")
    
    success_count = 0
    
    for family, types in price_analysis.items():
        if not types:
            continue
            
        # Strategy 1: Try to create separate price sets by type
        for price_type, items in types.items():
            if not items:
                continue
                
            price_set_name = f"{PRICE_PREFIX} - GCP - {family.upper()} - {price_type.title()} (asia-southeast2)"
            price_set_code = f"{PRICE_PREFIX.lower()}.gcp-{family}-{price_type}-asia_southeast2"
            
            print(f"\n🔄 Creating: {price_set_name}")
            
            # Create payload with correct structure for single price type
            payload = {
                "priceSet": {
                    "name": price_set_name,
                    "code": price_set_code,
                    "type": "fixed",  # Use 'fixed' type
                    "priceUnit": "hour",
                    "regionCode": PRICE_PREFIX.lower(),
                    "prices": [{"id": item['id']} for item in items]
                }
            }
            
            try:
                # Check if exists first
                existing = api_client.get(f"price-sets?code={price_set_code}")
                if existing and existing.get('priceSets'):
                    print(f"   ⏭️  Already exists, skipping")
                    continue
                
                response = api_client.post("price-sets", payload)
                if response and (response.get('success') or response.get('priceSet')):
                    print(f"   ✅ Created successfully")
                    success_count += 1
                else:
                    print(f"   ❌ Failed: {response}")
                    
            except Exception as e:
                print(f"   ❌ Exception: {e}")
    
    print(f"\n📊 Summary: Created {success_count} price sets successfully")

def main():
    print("🔧 GCP Price Set Fix Tool")
    print("=" * 50)
    
    # Disable SSL warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        api_client = MorpheusApiClient(MORPHEUS_URL, MORPHEUS_TOKEN)
        
        # Step 1: Analyze existing prices
        price_analysis = analyze_existing_prices(api_client)
        if not price_analysis:
            print("❌ Cannot proceed without price data")
            return
        
        # Step 2: Check existing price sets
        check_existing_price_sets(api_client)
        
        # Step 3: Suggest strategy
        suggest_price_set_strategy(price_analysis)
        
        # Step 4: Ask user if they want to proceed
        print("\n" + "=" * 50)
        proceed = input("Do you want to create the corrected price sets? (y/N): ").lower().strip()
        
        if proceed == 'y':
            create_corrected_price_sets(api_client, price_analysis)
        else:
            print("👋 Exiting without making changes")
            
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()