import requests
import json
import logging
import time
import urllib3
import argparse
import os
import re
import uuid
import subprocess
import sys
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Configuration ---
MORPHEUS_URL = os.getenv("MORPHEUS_URL", "https://localhost")  # Change this to your actual Morpheus server URL
MORPHEUS_TOKEN = os.getenv("MORPHEUS_TOKEN", "9fcc4426-c89a-4430-b6d7-99d5950fc1cc")
GCP_REGION = os.getenv("GCP_REGION", "asia-southeast2")
PRICE_PREFIX = os.getenv("PRICE_PREFIX", "IOH-CP")
LOCAL_SKU_CACHE_FILE = "gcp_plan_skus.json"

# --- Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Morpheus API Client ---
class MorpheusApiClient:
    """Client for interacting with the Morpheus API."""
    def __init__(self, base_url, api_token, max_retries=5, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504)):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Authorization": f"BEARER {api_token}",
            "Content-Type": "application/json"
        }
        self.session = requests.Session()
        retry_strategy = Retry(total=max_retries, backoff_factor=backoff_factor, status_forcelist=list(status_forcelist))
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _request(self, method, endpoint, payload=None, params=None):
        url = f"{self.base_url}/api/{endpoint}"
        try:
            response = self.session.request(method, url, json=payload, headers=self.headers, params=params, verify=False)
            response.raise_for_status()
            return response.json() if response.content else None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection Error: Cannot connect to Morpheus server at {self.base_url}")
            logger.error(f"Please verify:")
            logger.error(f"  1. Morpheus server is running and accessible")
            logger.error(f"  2. MORPHEUS_URL is correct (current: {self.base_url})")
            logger.error(f"  3. Network connectivity to the server")
            logger.error(f"  4. Firewall allows connections on port 443")
            raise
        except requests.exceptions.HTTPError as e:
            if response.status_code != 404:
                logger.error(f"HTTP Error for {method.upper()} {endpoint}: {e.response.status_code} - {e.response.text}")
                # Log response details for debugging
                try:
                    error_detail = e.response.json()
                    logger.error(f"Error details: {json.dumps(error_detail, indent=2)}")
                except:
                    logger.error(f"Raw error response: {e.response.text}")
                raise
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"An unexpected error occurred: {e}")
            raise

    def get(self, endpoint, params=None):
        return self._request('get', endpoint, params=params)

    def post(self, endpoint, payload):
        return self._request('post', endpoint, payload=payload)
        
    def put(self, endpoint, payload):
        return self._request('put', endpoint, payload=payload)

# --- Cloud Pricing Client ---
class GCPPricingClient:
    """Client for fetching SKU data from the GCP Billing Catalog API using gcloud for auth."""
    API_HOST = "https://cloudbilling.googleapis.com"
    
    def __init__(self, region):
        self.region = region
        self.session = requests.Session()
        self.access_token = self._get_access_token_from_gcloud()
        self.all_services = self._get_all_services()
        logger.info(f"Initialized GCP Pricing Client for region: {self.region} with {len(self.all_services)} services cached.")

    def _get_access_token_from_gcloud(self):
        try:
            logger.info("Fetching GCP access token from gcloud CLI...")
            env = os.environ.copy()
            if "GOOGLE_APPLICATION_CREDENTIALS" in env and os.path.exists(env["GOOGLE_APPLICATION_CREDENTIALS"]):
                logger.info(f"Using service account from GOOGLE_APPLICATION_CREDENTIALS.")
                env["CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"] = env["GOOGLE_APPLICATION_CREDENTIALS"]
            
            result = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True, env=env)
            token = result.stdout.strip()
            if not token: raise ValueError("gcloud did not return an access token.")
            logger.info("Successfully obtained GCP access token.")
            return token
        except (FileNotFoundError, subprocess.CalledProcessError, ValueError) as e:
            logger.critical(f"Failed to get gcloud token: {e}")
            raise

    def _make_api_request(self, url, params=None):
        headers = {'Authorization': f'Bearer {self.access_token}'}
        response = self.session.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def _get_all_services(self):
        services_url = f"{self.API_HOST}/v1/services"
        return self._make_api_request(services_url).get('services', [])

    def get_skus_from_filters(self, filters):
        normalized_skus = []
        compute_service = next((s for s in self.all_services if s['serviceId'] == '6F81-5844-456A'), None)
        if not compute_service:
            logger.error("Compute Engine service not found.")
            return []

        logger.info(f"Querying SKUs for {len(filters)} filter sets...")
        for i, f in enumerate(filters):
            progress_message = f"Processing filter {i + 1}/{len(filters)}: {' & '.join(f):<50}"
            sys.stdout.write(f"\r{progress_message}")
            sys.stdout.flush()

            skus_url = f"{self.API_HOST}/v1/{compute_service['name']}/skus"
            next_page_token = None
            while True:
                params = {'currencyCode': 'USD', 'pageToken': next_page_token} if next_page_token else {'currencyCode': 'USD'}
                data = self._make_api_request(skus_url, params=params)
                for sku in data.get('skus', []):
                    if self.region in sku.get('serviceRegions', []) and all(term.lower() in sku.get('description', '').lower() for term in f):
                        normalized_sku = self._normalize_gcp_sku(sku)
                        if normalized_sku and not any(d['sku_id'] == normalized_sku['sku_id'] for d in normalized_skus):
                            normalized_skus.append(normalized_sku)
                next_page_token = data.get('nextPageToken')
                if not next_page_token: break
        sys.stdout.write("\n")
        logger.info(f"Found {len(normalized_skus)} matching SKUs.")
        return normalized_skus

    def _normalize_gcp_sku(self, sku_dict):
        pricing_info = sku_dict.get('pricingInfo', [{}])[0]
        tiered_rates = pricing_info.get('pricingExpression', {}).get('tieredRates', [{}])[0]
        unit_price = tiered_rates.get('unitPrice', {})
        base_price = float(unit_price.get('units', 0)) + float(unit_price.get('nanos', 0)) / 1e9
        if base_price == 0.0: return None

        category = sku_dict.get('category', {})
        resource_family = category.get('resourceFamily', '').upper()
        resource_group = category.get('resourceGroup', '').upper()
        
        price_type_code = 'software'
        machine_family_heuristic = 'software'
        description = sku_dict.get('description', '').lower()
        
        if resource_family == "COMPUTE":
            if resource_group == "CPU": 
                price_type_code = 'cores'
                # Extract family from description, e.g., "N2 CPU..." -> "n2"
                family_match = re.search(r'^([A-Z0-9]+[A-Z]?)', sku_dict.get('description', ''))
                if family_match: machine_family_heuristic = family_match.group(1).lower()
            elif resource_group == "RAM": 
                price_type_code = 'memory'
                family_match = re.search(r'^([A-Z0-9]+[A-Z]?)', sku_dict.get('description', ''))
                if family_match: machine_family_heuristic = family_match.group(1).lower()
        elif resource_family == "STORAGE":
            if resource_group == "DISK": 
                price_type_code = 'storage'
                # ENHANCED: Comprehensive disk type detection
                if 'local ssd' in description or 'local-ssd' in description:
                    machine_family_heuristic = 'local-ssd'
                elif 'hyperdisk' in description and 'balanced' in description:
                    machine_family_heuristic = 'hyperdisk-balanced'
                elif 'hyperdisk' in description and 'extreme' in description:
                    machine_family_heuristic = 'hyperdisk-extreme'
                elif 'pd-extreme' in description or ('extreme' in description and 'persistent' in description):
                    machine_family_heuristic = 'pd-extreme'
                elif 'pd-balanced' in description or ('balanced' in description and 'persistent' in description):
                    machine_family_heuristic = 'pd-balanced'
                elif 'pd-ssd' in description or ('ssd' in description and 'persistent' in description and 'standard' not in description):
                    machine_family_heuristic = 'pd-ssd'
                elif 'regional' in description and 'ssd' in description:
                    machine_family_heuristic = 'regional-pd-ssd'
                elif 'regional' in description and 'standard' in description:
                    machine_family_heuristic = 'regional-pd-standard'
                elif 'standard' in description and 'persistent' in description:
                    machine_family_heuristic = 'pd-standard'
                else:
                    # Default to standard if unclear
                    machine_family_heuristic = 'pd-standard'
        
        usage_unit_desc = pricing_info.get('pricingExpression', {}).get('usageUnitDescription', '').lower()
        price_unit = 'month' if 'month' in usage_unit_desc else 'hour'
        incur_charges = 'running' if resource_family == "COMPUTE" else 'always'
        morpheus_price_code = f"{PRICE_PREFIX.lower()}.gcp.{sku_dict.get('skuId')}.{self.region.replace('-', '_').lower()}"

        return {
            "sku_id": sku_dict.get('skuId'), "morpheus_code": morpheus_price_code,
            "description": sku_dict.get('description', 'N/A'), "region": self.region,
            "priceTypeCode": price_type_code, "priceUnit": price_unit,
            "incurCharges": incur_charges, "currency": unit_price.get('currencyCode', 'USD'),
            "price_per_unit": base_price, "machine_family": machine_family_heuristic
        }

# --- Modular Functions ---

def discover_morpheus_plans(morpheus_api: MorpheusApiClient):
    """Step 1: Discover GCP service plans in Morpheus."""
    logger.info("--- Step 1: Discovering GCP Service Plans in Morpheus ---")
    plans_resp = morpheus_api.get("service-plans?max=2000")
    if not plans_resp or not plans_resp.get('servicePlans'):
        logger.error("No service plans found in Morpheus.")
        return []

    gcp_plans = []
    for plan in plans_resp['servicePlans']:
        if plan.get('provisionType', {}).get('code') == 'gcp':
            gcp_plans.append(plan)

    logger.info(f"Found {len(gcp_plans)} GCP service plans in Morpheus.")
    for plan in sorted(gcp_plans, key=lambda p: p['name']):
        logger.info(f"  - {plan['name']}")
    
    return gcp_plans

def sync_gcp_data(morpheus_api: MorpheusApiClient, gcp_client: GCPPricingClient):
    """Step 2: Sync relevant GCP data based on Morpheus plans and save to a local file."""
    logger.info("--- Step 2: Syncing relevant GCP pricing data ---")
    plans = discover_morpheus_plans(morpheus_api)
    if not plans:
        logger.warning("No GCP service plans found in Morpheus. Nothing to sync.")
        return

    # ENHANCED: Extract machine families from actual GCP plan names and include comprehensive disk types
    filters = set()
    detected_families = set()
    
    for plan in plans:
        name = plan.get('name', '').lower()
        family = None
        
        # More comprehensive pattern matching for GCP machine families
        patterns = [
            r'^([a-z]\d+[a-z]?)-',  # e2-, n2-, c2-, n2d-, c2d-, etc.
            r'^(f1|g1)-',           # Legacy types
        ]
        
        for pattern in patterns:
            match = re.match(pattern, name)
            if match:
                family = match.group(1)
                break
        
        if family:
            detected_families.add(family)
            filters.add(tuple(sorted((family,))))
    
    # ENHANCED: Comprehensive disk/storage filters for all GCP disk types
    disk_types = [
        'pd-standard',    # Standard persistent disk
        'pd-ssd',         # SSD persistent disk  
        'pd-balanced',    # Balanced persistent disk
        'pd-extreme',     # Extreme persistent disk
        'local-ssd',      # Local SSD
        'hyperdisk-balanced',  # Hyperdisk balanced
        'hyperdisk-extreme',   # Hyperdisk extreme
        'regional-pd-standard', # Regional standard
        'regional-pd-ssd',      # Regional SSD
        'standard persistent disk',  # Alternative naming
        'ssd persistent disk',       # Alternative naming
        'balanced persistent disk',  # Alternative naming
        'extreme persistent disk',   # Alternative naming
    ]
    
    for disk_type in disk_types:
        filters.add(tuple(sorted((disk_type,))))
    
    logger.info(f"Detected machine families: {sorted(detected_families)}")
    logger.info(f"Generated {len(filters)} unique SKU search filters (including {len(disk_types)} disk types)")
    
    pricing_data = gcp_client.get_skus_from_filters([list(f) for f in filters])
    
    # ENHANCED: Validate that we have comprehensive storage coverage
    storage_skus = [sku for sku in pricing_data if sku.get('priceTypeCode') == 'storage']
    storage_types = set(sku.get('machine_family') for sku in storage_skus)
    
    logger.info(f"Found {len(storage_skus)} storage SKUs with types: {sorted(storage_types)}")
    
    # Check for required storage types
    required_storage_types = {'pd-standard', 'pd-ssd', 'pd-balanced'}
    missing_storage_types = required_storage_types - storage_types
    
    if missing_storage_types:
        logger.warning(f"Missing required storage types: {missing_storage_types}")
        logger.warning("This may cause issues with component price set creation")
    
    with open(LOCAL_SKU_CACHE_FILE, 'w') as f:
        json.dump(pricing_data, f, indent=2)
    logger.info(f"Targeted pricing data saved to {LOCAL_SKU_CACHE_FILE}")

def create_prices(morpheus_api: MorpheusApiClient):
    """Step 3: Create prices in Morpheus from the local SKU cache."""
    logger.info(f"--- Step 3: Creating Prices in Morpheus from local file ---")
    if not os.path.exists(LOCAL_SKU_CACHE_FILE):
        logger.error(f"Local cache file '{LOCAL_SKU_CACHE_FILE}' not found. Please run 'sync-gcp-data' first.")
        return

    with open(LOCAL_SKU_CACHE_FILE, 'r') as f:
        pricing_data = json.load(f)
    
    logger.info(f"Processing {len(pricing_data)} prices from local cache...")
    for i, price_info in enumerate(pricing_data):
        sys.stdout.write(f"\rProcessing price {i + 1}/{len(pricing_data)}")
        sys.stdout.flush()
        
        payload = { "price": {
            "name": f"{PRICE_PREFIX} - {price_info['description']}", "code": price_info['morpheus_code'],
            "priceType": price_info['priceTypeCode'], "priceUnit": price_info['priceUnit'], 
            "price": price_info['price_per_unit'], "cost": price_info['price_per_unit'], 
            "incurCharges": price_info['incurCharges'], "currency": price_info['currency'], "active": True
        }}
        
        if price_info['priceTypeCode'] == 'software':
            payload['price']['software'] = price_info['description']

        try:
            existing = morpheus_api.get(f"prices?code={price_info['morpheus_code']}")
            if not (existing and existing.get('prices')):
                response = morpheus_api.post("prices", payload)
                if not response or not (response.get('success') or response.get('price')):
                    logger.error(f"\nFailed to create price '{price_info['description']}'. Invalid response: {response}")
        except Exception as e:
            logger.error(f"\nException creating price '{price_info['description']}': {e}")
    sys.stdout.write("\n")
    logger.info("--- Price creation complete. ---")

def create_price_sets(morpheus_api: MorpheusApiClient):
    """Step 4: Create comprehensive price sets from prices in Morpheus - ENHANCED VERSION FOR COMPONENT PRICE SETS."""
    logger.info(f"--- Step 4: Creating Component Price Sets in Morpheus ---")
    if not os.path.exists(LOCAL_SKU_CACHE_FILE):
        logger.error(f"Local cache file '{LOCAL_SKU_CACHE_FILE}' not found. Please run 'sync-gcp-data' and 'create-prices' first.")
        return
    
    with open(LOCAL_SKU_CACHE_FILE, 'r') as f:
        pricing_data = json.load(f)
    
    # Get all prices with the required prefix
    all_prices_resp = morpheus_api.get(f"prices?max=2000&phrase={PRICE_PREFIX}")
    if not all_prices_resp or not all_prices_resp.get('prices'):
        logger.error("No prices found with the required prefix. Please run 'create-prices' first.")
        return

    price_id_map = {p['code']: p['id'] for p in all_prices_resp['prices']}
    
    # ENHANCED: Separate machine family prices from storage prices
    machine_family_prices = {}
    storage_prices = {}
    
    # Storage types that should be included in every machine family price set
    storage_types = ['pd-standard', 'pd-ssd', 'pd-balanced', 'pd-extreme', 'local-ssd', 
                     'hyperdisk-balanced', 'hyperdisk-extreme', 'regional-pd-standard', 'regional-pd-ssd']
    
    # ENHANCED: Separate machine family pricing from storage pricing
    for price_info in pricing_data:
        family = price_info.get('machine_family', 'unknown')
        price_type = price_info.get('priceTypeCode', 'unknown')
        region = price_info['region'].replace('-', '_')
        
        if family == 'software': 
            continue  # Don't create price sets for generic software
        
        price_id = price_id_map.get(price_info['morpheus_code'])
        if not price_id:
            continue
            
        # Check if this is storage pricing
        if family in storage_types or price_type == 'storage':
            # Storage prices - collect by region to add to all machine families
            if region not in storage_prices:
                storage_prices[region] = set()
            storage_prices[region].add(price_id)
        else:
            # Machine family prices (cores, memory)
            group_key = f"gcp-{family}-{region}"
            
            if group_key not in machine_family_prices:
                machine_family_prices[group_key] = {
                    "name": f"{PRICE_PREFIX} - GCP - {family.upper()} ({price_info['region']})",
                    "code": f"{PRICE_PREFIX.lower()}.{group_key}",
                    "prices": set(),
                    "price_types": set(),
                    "region": price_info['region'],
                    "region_key": region
                }
            
            machine_family_prices[group_key]["prices"].add(price_id)
            machine_family_prices[group_key]["price_types"].add(price_type)

    # ENHANCED: Now add storage prices to each machine family price set
    for group_key, data in machine_family_prices.items():
        region_key = data["region_key"]
        if region_key in storage_prices:
            # Add all storage prices for this region to the machine family price set
            data["prices"].update(storage_prices[region_key])
            data["price_types"].add("storage")
    
    # Check if we have any storage prices at all
    total_storage_prices = sum(len(prices) for prices in storage_prices.values())
    logger.info(f"Found {total_storage_prices} storage prices across {len(storage_prices)} regions")
    
    if total_storage_prices == 0:
        logger.error("No storage prices found! Component price sets require storage pricing.")
        logger.error("Please ensure the following storage types are available:")
        logger.error("- pd-standard (Standard Persistent Disk)")
        logger.error("- pd-ssd (SSD Persistent Disk)")
        logger.error("- pd-balanced (Balanced Persistent Disk)")
        logger.error("- pd-extreme (Extreme Persistent Disk)")
        logger.error("- local-ssd (Local SSD)")
        logger.error("Run 'sync-gcp-data' again to ensure storage SKUs are fetched")
        return

    logger.info(f"Processing {len(machine_family_prices)} component price sets")
    logger.info("Each price set includes cores, memory, and storage pricing for complete VM provisioning")
    
    successful_count = 0
    failed_count = 0
    
    for i, (key, data) in enumerate(machine_family_prices.items()):
        sys.stdout.write(f"\rProcessing price set {i + 1}/{len(machine_family_prices)}: {data['name']}")
        sys.stdout.flush()
        
        if not data["prices"]: 
            logger.warning(f"\nSkipping price set '{data['name']}' - no prices found")
            continue
        
        logger.info(f"\nCreating component price set '{data['name']}' with {len(data['prices'])} prices")
        logger.info(f"  Price types: {sorted(data['price_types'])}")
        
        # ENHANCED: Verify we have required components for component price sets
        required_types = {'cores', 'memory', 'storage'}
        if not required_types.issubset(data['price_types']):
            missing_types = required_types - data['price_types']
            logger.error(f"  Error: Missing required price types {missing_types} for Component pricing")
            logger.error(f"  Skipping price set '{data['name']}' - Component type requires cores, memory, and storage")
            failed_count += 1
            continue
        
        # ENHANCED: Create component price set payload with correct structure
        payload = {
            "priceSet": {
                "name": data["name"], 
                "code": data["code"], 
                "type": "component",  # FIXED: Use 'component' type as required
                "priceUnit": "hour",
                "regionCode": PRICE_PREFIX.lower(),
                "prices": [{"id": price_id} for price_id in data["prices"]]
            }
        }
        
        try:
            # Check if price set already exists
            existing = morpheus_api.get(f"price-sets?code={data['code']}")
            if existing and existing.get('priceSets') and len(existing['priceSets']) > 0:
                # Update existing price set
                price_set_id = existing['priceSets'][0]['id']
                logger.info(f"Updating existing price set: {data['name']} (ID: {price_set_id})")
                response = morpheus_api.put(f"price-sets/{price_set_id}", payload)
            else:
                # Create new price set
                logger.info(f"Creating new component price set: {data['name']}")
                response = morpheus_api.post("price-sets", payload)
            
            if response and (response.get('success') or response.get('priceSet')):
                logger.info(f"  ✅ Successfully created/updated component price set")
                successful_count += 1
            else:
                logger.error(f"  ❌ Failed to create price set. Response: {response}")
                failed_count += 1
                
        except Exception as e:
            logger.error(f"  ❌ Exception creating price set: {e}")
            failed_count += 1
    
    sys.stdout.write("\n")
    logger.info(f"--- Price set creation complete. Success: {successful_count}, Failed: {failed_count} ---")

def map_plans_to_price_sets(morpheus_api: MorpheusApiClient):
    """Step 5: Map price sets to service plans based on machine family matching."""
    logger.info("--- Step 5: Mapping Price Sets to Service Plans ---")
    
    # Get all price sets
    price_sets_resp = morpheus_api.get("price-sets?max=2000")
    if not price_sets_resp or not price_sets_resp.get('priceSets'):
        logger.error("No price sets found. Please run 'create-price-sets' first.")
        return

    price_set_map = {ps['code']: ps for ps in price_sets_resp['priceSets']}
    
    # Get all GCP service plans
    plans = discover_morpheus_plans(morpheus_api)
    if not plans:
        logger.error("No GCP service plans found.")
        return

    successful_mappings = 0
    failed_mappings = 0
    
    for plan in plans:
        plan_name = plan.get('name', '').lower()
        plan_id = plan.get('id')
        
        # Extract machine family from plan name
        family = None
        patterns = [
            r'^([a-z]\d+[a-z]?)-',  # e2-, n2-, c2-, n2d-, c2d-, etc.
            r'^(f1|g1)-',           # Legacy types
        ]
        
        for pattern in patterns:
            match = re.match(pattern, plan_name)
            if match:
                family = match.group(1)
                break
        
        if not family:
            logger.warning(f"Skipping plan '{plan.get('name')}' - could not extract machine family")
            continue
        
        # Find matching price set
        region_key = GCP_REGION.replace('-', '_')
        expected_price_set_code = f"{PRICE_PREFIX.lower()}.gcp-{family}-{region_key}"
        
        if expected_price_set_code not in price_set_map:
            logger.warning(f"No price set found for plan '{plan.get('name')}' (expected: {expected_price_set_code})")
            failed_mappings += 1
            continue
        
        price_set = price_set_map[expected_price_set_code]
        current_price_sets = plan.get('priceSets', []) or []
        current_ps_ids = {ps['id'] for ps in current_price_sets if ps}
        
        if price_set['id'] in current_ps_ids:
            logger.info(f"Plan '{plan.get('name')}' already has price set '{price_set['name']}'")
            successful_mappings += 1
            continue
        
        # Add price set to plan
        final_ps_ids = list(current_ps_ids) + [price_set['id']]
        payload = {
            "servicePlan": {
                "priceSets": [{"id": ps_id} for ps_id in final_ps_ids]
            }
        }
        
        try:
            response = morpheus_api.put(f"service-plans/{plan_id}", payload)
            if response and (response.get('success') or response.get('servicePlan')):
                logger.info(f"✅ Mapped price set '{price_set['name']}' to plan '{plan.get('name')}'")
                successful_mappings += 1
            else:
                logger.error(f"❌ Failed to map price set to plan '{plan.get('name')}'. Response: {response}")
                failed_mappings += 1
        except Exception as e:
            logger.error(f"❌ Exception mapping price set to plan '{plan.get('name')}': {e}")
            failed_mappings += 1
    
    logger.info(f"--- Mapping complete. Success: {successful_mappings}, Failed: {failed_mappings} ---")

def validate(morpheus_api: MorpheusApiClient):
    """Step 6: Validate that service plans have proper pricing configured."""
    logger.info("--- Step 6: Validating Service Plan Pricing ---")
    plans = discover_morpheus_plans(morpheus_api)
    if not plans:
        logger.error("No GCP service plans found.")
        return

    priced_count = 0
    total_plans = len(plans)
    
    for plan in sorted(plans, key=lambda p: p['name']):
        price_sets = plan.get('priceSets', [])
        has_pricing = len(price_sets) > 0
        if has_pricing:
            priced_count += 1
            status = f"✅ PRICED with {len(price_sets)} component price sets"
            logger.info(f"{plan['name']}: {status}")
            if plan.get('priceSets'):
                for ps in sorted(plan['priceSets'], key=lambda x: x['name']):
                    logger.info(f"  - {ps['name']} (Type: {ps.get('type', 'unknown')})")
        else:
            logger.warning(f"{plan['name']}: ❌ NOT PRICED")
    
    logger.info(f"\n--- Validation Summary ---")
    logger.info(f"Total GCP plans: {total_plans}")
    logger.info(f"Priced plans: {priced_count}")
    logger.info(f"Unpriced plans: {total_plans - priced_count}")
    logger.info(f"Pricing coverage: {(priced_count/total_plans)*100:.1f}%")

def evaluate_apis():
    """Evaluate both GCP and Morpheus APIs for comprehensive understanding."""
    logger.info("--- API Evaluation Report ---")
    
    # GCP API Evaluation
    logger.info("\n🔍 GCP Billing Catalog API Evaluation:")
    logger.info("✅ Strengths:")
    logger.info("  - Comprehensive SKU coverage for all GCP services")
    logger.info("  - Real-time pricing data with currency support")
    logger.info("  - Detailed resource categorization (CPU, RAM, Storage)")
    logger.info("  - Regional pricing support")
    logger.info("  - Multiple storage types: Standard, SSD, Balanced, Extreme")
    logger.info("  - Local SSD and Hyperdisk support")
    logger.info("  - Well-documented REST API with authentication")
    
    logger.info("⚠️  Limitations:")
    logger.info("  - Requires gcloud CLI or service account authentication")
    logger.info("  - Rate limiting on API requests")
    logger.info("  - Complex SKU structure requires parsing")
    logger.info("  - Some storage types may not be available in all regions")
    
    # Morpheus API Evaluation
    logger.info("\n🔍 Morpheus API Evaluation:")
    logger.info("✅ Strengths:")
    logger.info("  - Component price sets support complete VM provisioning")
    logger.info("  - Flexible price set types (fixed, component)")
    logger.info("  - Service plan integration for automated provisioning")
    logger.info("  - Regional pricing support")
    logger.info("  - Comprehensive validation of price set requirements")
    
    logger.info("⚠️  Requirements:")
    logger.info("  - Component price sets MUST include cores, memory, AND storage")
    logger.info("  - Price sets must have proper type classification")
    logger.info("  - Service plans require valid price set mappings")
    logger.info("  - API token must have pricing permissions")
    
    logger.info("\n📋 Integration Requirements:")
    logger.info("1. GCP SKU data must be normalized to Morpheus price format")
    logger.info("2. Storage pricing is mandatory for component price sets")
    logger.info("3. Machine family detection must be accurate")
    logger.info("4. Price set grouping must include all required components")
    logger.info("5. Service plan mapping requires exact family matching")

def main():
    parser = argparse.ArgumentParser(description="Enhanced GCP Price Sync Tool")
    parser.add_argument("command", choices=[
        "discover-morpheus-plans", "sync-gcp-data", "create-prices", 
        "create-price-sets", "map-plans-to-price-sets", "validate", "evaluate-apis"
    ], help="Command to execute")
    
    args = parser.parse_args()
    
    try:
        morpheus_api = MorpheusApiClient(MORPHEUS_URL, MORPHEUS_TOKEN)
        
        if args.command == "discover-morpheus-plans":
            discover_morpheus_plans(morpheus_api)
        elif args.command == "sync-gcp-data":
            gcp_client = GCPPricingClient(GCP_REGION)
            sync_gcp_data(morpheus_api, gcp_client)
        elif args.command == "create-prices":
            create_prices(morpheus_api)
        elif args.command == "create-price-sets":
            create_price_sets(morpheus_api)
        elif args.command == "map-plans-to-price-sets":
            map_plans_to_price_sets(morpheus_api)
        elif args.command == "validate":
            validate(morpheus_api)
        elif args.command == "evaluate-apis":
            evaluate_apis()
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()