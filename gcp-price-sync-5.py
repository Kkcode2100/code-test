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
MORPHEUS_URL = os.getenv("MORPHEUS_URL", "https://xdjmorpheapp01")
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
        except requests.exceptions.HTTPError as e:
            if response.status_code != 404:
                 logger.error(f"HTTP Error for {method.upper()} {endpoint}: {e.response.status_code} - {e.response.text}")
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
        all_services = []
        next_page_token = None
        while True:
            params = {'pageToken': next_page_token} if next_page_token else {}
            data = self._make_api_request(f"{self.API_HOST}/v1/services", params)
            all_services.extend(data.get('services', []))
            next_page_token = data.get('nextPageToken')
            if not next_page_token: break
        return all_services

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
        if resource_family == "COMPUTE":
            if resource_group == "CPU": 
                price_type_code = 'cores'
                # Extract family from description, e.g., "N2 CPU..." -> "n2"
                family_match = re.search(r'^([A-Z0-9]+)', sku_dict.get('description', ''))
                if family_match: machine_family_heuristic = family_match.group(1).lower()
            elif resource_group == "RAM": 
                price_type_code = 'memory'
                family_match = re.search(r'^([A-Z0-9]+)', sku_dict.get('description', ''))
                if family_match: machine_family_heuristic = family_match.group(1).lower()
        elif resource_family == "STORAGE":
            if resource_group == "DISK": 
                price_type_code = 'storage'
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
    """Step 1: Discover Google service plans from Morpheus."""
    logger.info("--- Step 1: Discovering Morpheus Service Plans ---")
    plans = morpheus_api.get("service-plans?provisionTypeCode=google&max=1000")
    service_plans = plans.get('servicePlans', []) if plans else []
    logger.info(f"Found {len(service_plans)} GCP Service Plans in Morpheus.")
    for p in sorted(service_plans, key=lambda x: x['name']):
        print(f" - {p['name']}")
    return service_plans

def sync_gcp_data(morpheus_api: MorpheusApiClient, gcp_client: GCPPricingClient):
    """Step 2: Sync relevant GCP data based on Morpheus plans and save to a local file."""
    logger.info("--- Step 2: Syncing relevant GCP pricing data ---")
    plans = discover_morpheus_plans(morpheus_api)
    if not plans:
        logger.warning("No GCP service plans found in Morpheus. Nothing to sync.")
        return

    filters = set()
    for plan in plans:
        name = plan.get('name', '').lower()
        match = re.search(r'(e2|n1|n2|c2|m1|m2)-[a-z]+-[0-9]+', name)
        if match:
            family = match.group(1)
            filters.add(tuple(sorted((family,))))
    filters.add(tuple(sorted(('pd-standard',))))
    logger.info(f"Generated {len(filters)} unique SKU search filters.")
    
    pricing_data = gcp_client.get_skus_from_filters([list(f) for f in filters])
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
    """Step 4: Create price sets from prices in Morpheus."""
    logger.info(f"--- Step 4: Creating Price Sets in Morpheus ---")
    if not os.path.exists(LOCAL_SKU_CACHE_FILE):
        logger.error(f"Local cache file '{LOCAL_SKU_CACHE_FILE}' not found. Please run 'sync-gcp-data' and 'create-prices' first.")
        return
    
    with open(LOCAL_SKU_CACHE_FILE, 'r') as f:
        pricing_data = json.load(f)
    
    all_prices_resp = morpheus_api.get(f"prices?max=2000&phrase={PRICE_PREFIX}")
    if not all_prices_resp or not all_prices_resp.get('prices'):
        logger.error("No prices found with the required prefix. Please run 'create-prices' first.")
        return

    price_id_map = {p['code']: p['id'] for p in all_prices_resp['prices']}
    price_set_groups = {}
    
    for price_info in pricing_data:
        family = price_info.get('machine_family', 'unknown')
        if family == 'software': continue # Don't create price sets for generic software
        
        region = price_info['region'].replace('-', '_')
        group_key = f"gcp-{family}-{region}"
        
        if group_key not in price_set_groups:
            price_set_groups[group_key] = {
                "name": f"{PRICE_PREFIX} - GCP - {family.upper()} ({price_info['region']})",
                "code": f"{PRICE_PREFIX.lower()}.{group_key}",
                "prices": set()
            }
        
        price_id = price_id_map.get(price_info['morpheus_code'])
        if price_id:
            price_set_groups[group_key]["prices"].add(price_id)

    logger.info(f"Processing {len(price_set_groups)} price sets...")
    for i, (key, data) in enumerate(price_set_groups.items()):
        sys.stdout.write(f"\rProcessing price set {i + 1}/{len(price_set_groups)}")
        sys.stdout.flush()
        if not data["prices"]: continue
        
        payload = {"priceSet": {"name": data["name"], "code": data["code"], "type": "component", "prices": list(data["prices"])}}
        
        existing = morpheus_api.get(f"price-sets?code={data['code']}")
        if existing and existing.get('priceSets'):
            price_set_id = existing['priceSets'][0]['id']
            morpheus_api.put(f"price-sets/{price_set_id}", payload)
        else:
            morpheus_api.post("price-sets", payload)
    sys.stdout.write("\n")
    logger.info("--- Price Set creation complete. ---")

def map_plans_to_price_sets(morpheus_api: MorpheusApiClient):
    """Step 5: Map price sets to service plans."""
    logger.info("--- Step 5: Mapping Price Sets to Service Plans ---")
    plans = morpheus_api.get("service-plans?provisionTypeCode=google&max=1000").get('servicePlans', [])
    price_sets_resp = morpheus_api.get(f"price-sets?max=1000&phrase={PRICE_PREFIX}")
    price_set_map = {ps['code']: ps['id'] for ps in price_sets_resp.get('priceSets', [])} if price_sets_resp else {}

    if not price_set_map:
        logger.error("No price sets found to map. Please run 'create-price-sets' first.")
        return

    for i, plan in enumerate(plans):
        sys.stdout.write(f"\rProcessing plan {i + 1}/{len(plans)}: {plan['name']}")
        sys.stdout.flush()
        
        plan_name_lower = plan.get('name', '').lower()
        plan_region = plan.get('config', {}).get('zoneRegion', '')
        if not plan_region: continue
        
        match = re.search(r'google-([a-z0-9]+)-', plan_name_lower)
        if not match: continue
        
        machine_family = match.group(1)
        expected_ps_code = f"{PRICE_PREFIX.lower()}.gcp-{machine_family}-{plan_region.replace('-', '_')}"
        disk_ps_code = f"{PRICE_PREFIX.lower()}.gcp-pd-standard-{plan_region.replace('-', '_')}"
        
        ids_to_link = set()
        if expected_ps_code in price_set_map:
            ids_to_link.add(price_set_map[expected_ps_code])
        if disk_ps_code in price_set_map:
            ids_to_link.add(price_set_map[disk_ps_code])

        if not ids_to_link: continue
            
        current_ps_ids = {ps['id'] for ps in plan.get('priceSets', []) if ps}
        
        if not ids_to_link.issubset(current_ps_ids):
            final_ids = current_ps_ids.union(ids_to_link)
            payload = {"servicePlan": {"priceSets": [{"id": ps_id} for ps_id in final_ids]}}
            morpheus_api.put(f"service-plans/{plan['id']}", payload)

    sys.stdout.write("\n")
    logger.info("--- Service Plan mapping complete. ---")

def validate(morpheus_api: MorpheusApiClient):
    """Utility: Validate pricing on service plans."""
    logger.info("--- Validating Service Plan Pricing ---")
    plans = morpheus_api.get("service-plans?provisionTypeCode=google&max=1000").get('servicePlans', [])
    for plan in sorted(plans, key=lambda p: p['name']):
        status = f"✅ PRICED with {len(plan.get('priceSets',[]))} sets" if plan.get('priceSets') else "❌ NOT PRICED"
        print(f"\nPLAN: {plan['name']} (ID: {plan['id']}) - Status: {status}")
        if plan.get('priceSets'):
            for ps in sorted(plan['priceSets'], key=lambda x: x['name']):
                print(f"    └── {ps['name']} (ID: {ps['id']})")
    logger.info("--- Validation Complete ---")

# --- Main Execution ---
def main():
    parser = argparse.ArgumentParser(description="Morpheus GCP Pricing Tool (Modular).", formatter_class=argparse.RawTextHelpFormatter)
    
    parser.add_argument('command', choices=[
        'discover-morpheus-plans', 'sync-gcp-data', 'create-prices', 'create-price-sets', 'map-plans-to-price-sets', 'validate'
    ], help="""Action to perform (run in order):
    
    1. discover-morpheus-plans   : List all GCP service plans currently in Morpheus.
    2. sync-gcp-data             : Fetch GCP SKUs for your plans and save to a local file.
    3. create-prices             : Create/update prices in Morpheus from the local file.
    4. create-price-sets         : Group Morpheus prices into price sets.
    5. map-plans-to-price-sets   : Link price sets to the corresponding service plans.
    
    validate                     : Check which Morpheus GCP plans have pricing.
    """)
    args = parser.parse_args()

    morpheus_api = MorpheusApiClient(MORPHEUS_URL, MORPHEUS_TOKEN)
    
    gcp_client = None
    if args.command == 'sync-gcp-data':
        gcp_client = GCPPricingClient(GCP_REGION)

    if args.command == 'discover-morpheus-plans':
        discover_morpheus_plans(morpheus_api)
    elif args.command == 'sync-gcp-data':
        sync_gcp_data(morpheus_api, gcp_client)
    elif args.command == 'create-prices':
        create_prices(morpheus_api)
    elif args.command == 'create-price-sets':
        create_price_sets(morpheus_api)
    elif args.command == 'map-plans-to-price-sets':
        map_plans_to_price_sets(morpheus_api)
    elif args.command == 'validate':
        validate(morpheus_api)

if __name__ == "__main__":
    main()

