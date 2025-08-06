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
import traceback
import threading
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from functools import wraps
import inspect

# --- Enhanced Configuration ---
MORPHEUS_URL = os.getenv("MORPHEUS_URL", "https://xdjmorpheapp01")
MORPHEUS_TOKEN = os.getenv("MORPHEUS_TOKEN", "9fcc4426-c89a-4430-b6d7-99d5950fc1cc")
GCP_REGION = os.getenv("GCP_REGION", "asia-southeast2")
PRICE_PREFIX = os.getenv("PRICE_PREFIX", "IOH-CP")
LOCAL_SKU_CACHE_FILE = "gcp_plan_skus.json"

# Debug and logging configuration
DEBUG_MODE = os.getenv("DEBUG_MODE", "true").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if DEBUG_MODE else "INFO")
LOG_FILE = os.getenv("LOG_FILE", f"gcp_price_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
CAPTURE_HTTP_TRAFFIC = os.getenv("CAPTURE_HTTP_TRAFFIC", "true").lower() == "true"
PERFORMANCE_MONITORING = os.getenv("PERFORMANCE_MONITORING", "true").lower() == "true"

# --- Enhanced Logging Setup ---
class ColoredFormatter(logging.Formatter):
    """Colored console formatter for better readability"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{log_color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)

class DebugLogger:
    """Enhanced logger with debug capabilities"""
    
    def __init__(self, name=__name__):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, LOG_LEVEL.upper()))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler with colors
        console_handler = logging.StreamHandler()
        console_formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler for detailed logs
        file_handler = logging.FileHandler(LOG_FILE, mode='a')
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s | PID:%(process)d',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Session start marker
        self.logger.info("="*80)
        self.logger.info(f"NEW SESSION STARTED - Log Level: {LOG_LEVEL}")
        self.logger.info(f"Configuration: DEBUG={DEBUG_MODE}, HTTP_CAPTURE={CAPTURE_HTTP_TRAFFIC}, PERF_MON={PERFORMANCE_MONITORING}")
        self.logger.info("="*80)
    
    def debug(self, msg, **kwargs):
        self.logger.debug(msg, **kwargs)
    
    def info(self, msg, **kwargs):
        self.logger.info(msg, **kwargs)
    
    def warning(self, msg, **kwargs):
        self.logger.warning(msg, **kwargs)
    
    def error(self, msg, **kwargs):
        self.logger.error(msg, **kwargs)
    
    def critical(self, msg, **kwargs):
        self.logger.critical(msg, **kwargs)
    
    def exception(self, msg, **kwargs):
        self.logger.exception(msg, **kwargs)

# Global logger instance
logger = DebugLogger()

# --- Performance Monitoring Decorator ---
def monitor_performance(func):
    """Decorator to monitor function performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not PERFORMANCE_MONITORING:
            return func(*args, **kwargs)
        
        start_time = time.time()
        func_name = f"{func.__module__}.{func.__name__}"
        
        # Log function entry
        logger.debug(f"🚀 ENTER {func_name} with args={len(args)}, kwargs={list(kwargs.keys())}")
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(f"✅ EXIT {func_name} | Duration: {execution_time:.3f}s | Success")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ EXIT {func_name} | Duration: {execution_time:.3f}s | Error: {str(e)}")
            raise
    return wrapper

# --- HTTP Traffic Capture ---
class HTTPTrafficLogger:
    """Captures and logs all HTTP traffic for debugging"""
    
    def __init__(self):
        self.session_id = str(uuid.uuid4())[:8]
        self.request_count = 0
    
    def log_request(self, method, url, headers=None, payload=None, params=None):
        self.request_count += 1
        req_id = f"{self.session_id}-{self.request_count:03d}"
        
        logger.debug(f"🌐 HTTP REQUEST [{req_id}] {method.upper()} {url}")
        if params:
            logger.debug(f"   📋 Params: {json.dumps(params, indent=2)}")
        if headers and CAPTURE_HTTP_TRAFFIC:
            # Mask sensitive headers
            safe_headers = {k: "***MASKED***" if "authorization" in k.lower() or "token" in k.lower() else v 
                          for k, v in headers.items()}
            logger.debug(f"   📝 Headers: {json.dumps(safe_headers, indent=2)}")
        if payload and CAPTURE_HTTP_TRAFFIC:
            logger.debug(f"   📦 Payload: {json.dumps(payload, indent=2)}")
        
        return req_id
    
    def log_response(self, req_id, response, execution_time):
        logger.debug(f"🌐 HTTP RESPONSE [{req_id}] Status: {response.status_code} | Time: {execution_time:.3f}s")
        
        if response.status_code >= 400:
            logger.error(f"   ❌ Error Response: {response.text}")
        elif CAPTURE_HTTP_TRAFFIC and response.content:
            try:
                resp_json = response.json()
                logger.debug(f"   📄 Response: {json.dumps(resp_json, indent=2)[:500]}...")
            except:
                logger.debug(f"   📄 Response: {response.text[:500]}...")

# --- Enhanced API Client ---
class MorpheusApiClient:
    """Enhanced Morpheus API client with comprehensive debugging"""
    
    def __init__(self, base_url, api_token, max_retries=5, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504)):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Authorization": f"BEARER {api_token}",
            "Content-Type": "application/json"
        }
        self.session = requests.Session()
        self.http_logger = HTTPTrafficLogger()
        
        # Setup retry strategy
        retry_strategy = Retry(
            total=max_retries, 
            backoff_factor=backoff_factor, 
            status_forcelist=list(status_forcelist),
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        logger.info(f"🔗 Morpheus API Client initialized | Base URL: {self.base_url} | Retries: {max_retries}")

    @monitor_performance
    def _request(self, method, endpoint, payload=None, params=None):
        url = f"{self.base_url}/api/{endpoint}"
        req_id = self.http_logger.log_request(method, url, self.headers, payload, params)
        
        start_time = time.time()
        try:
            response = self.session.request(
                method, url, 
                json=payload, 
                headers=self.headers, 
                params=params, 
                verify=False
            )
            execution_time = time.time() - start_time
            
            self.http_logger.log_response(req_id, response, execution_time)
            
            if response.status_code == 404:
                logger.debug(f"📭 Resource not found (404) for {method.upper()} {endpoint}")
                return None
            
            response.raise_for_status()
            return response.json() if response.content else None
            
        except requests.exceptions.HTTPError as e:
            execution_time = time.time() - start_time
            logger.error(f"🚨 HTTP Error [{req_id}] {method.upper()} {endpoint}: {e.response.status_code}")
            
            # Enhanced error logging
            try:
                error_detail = e.response.json()
                logger.error(f"   📋 Error Details: {json.dumps(error_detail, indent=2)}")
            except:
                logger.error(f"   📋 Raw Error: {e.response.text}")
            
            # Log request details for debugging
            logger.error(f"   🔍 Request URL: {url}")
            logger.error(f"   🔍 Request Method: {method.upper()}")
            if payload:
                logger.error(f"   🔍 Request Payload: {json.dumps(payload, indent=2)}")
            
            raise
            
        except requests.exceptions.RequestException as e:
            execution_time = time.time() - start_time
            logger.error(f"🚨 Request Error [{req_id}]: {str(e)} | Time: {execution_time:.3f}s")
            raise

    def get(self, endpoint, params=None):
        return self._request('get', endpoint, params=params)

    def post(self, endpoint, payload):
        return self._request('post', endpoint, payload=payload)
        
    def put(self, endpoint, payload):
        return self._request('put', endpoint, payload=payload)

# --- Enhanced GCP Client ---
class GCPPricingClient:
    """Enhanced GCP client with detailed debugging"""
    API_HOST = "https://cloudbilling.googleapis.com"
    
    def __init__(self, region):
        self.region = region
        self.session = requests.Session()
        self.http_logger = HTTPTrafficLogger()
        
        logger.info(f"🌤️  Initializing GCP Pricing Client for region: {self.region}")
        
        try:
            self.access_token = self._get_access_token_from_gcloud()
            self.all_services = self._get_all_services()
            logger.info(f"✅ GCP Client ready | Services cached: {len(self.all_services)}")
        except Exception as e:
            logger.critical(f"❌ Failed to initialize GCP client: {str(e)}")
            raise

    @monitor_performance
    def _get_access_token_from_gcloud(self):
        logger.debug("🔑 Fetching GCP access token from gcloud CLI...")
        
        try:
            env = os.environ.copy()
            if "GOOGLE_APPLICATION_CREDENTIALS" in env and os.path.exists(env["GOOGLE_APPLICATION_CREDENTIALS"]):
                logger.info(f"🔐 Using service account from GOOGLE_APPLICATION_CREDENTIALS: {env['GOOGLE_APPLICATION_CREDENTIALS']}")
                env["CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"] = env["GOOGLE_APPLICATION_CREDENTIALS"]
            
            cmd = ["gcloud", "auth", "print-access-token"]
            logger.debug(f"🔧 Executing command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
            token = result.stdout.strip()
            
            if not token:
                raise ValueError("gcloud returned empty access token")
            
            logger.info(f"✅ GCP access token obtained | Length: {len(token)}")
            logger.debug(f"🔍 Token preview: {token[:20]}...")
            
            return token
            
        except (FileNotFoundError, subprocess.CalledProcessError, ValueError) as e:
            logger.error(f"❌ Failed to get gcloud token")
            logger.error(f"   🔍 Error type: {type(e).__name__}")
            logger.error(f"   🔍 Error message: {str(e)}")
            
            if hasattr(e, 'stderr') and e.stderr:
                logger.error(f"   🔍 Command stderr: {e.stderr}")
            if hasattr(e, 'stdout') and e.stdout:
                logger.error(f"   🔍 Command stdout: {e.stdout}")
            
            raise

    @monitor_performance
    def _make_api_request(self, url, params=None):
        headers = {'Authorization': f'Bearer {self.access_token}'}
        req_id = self.http_logger.log_request('GET', url, headers, None, params)
        
        start_time = time.time()
        try:
            response = self.session.get(url, headers=headers, params=params)
            execution_time = time.time() - start_time
            
            self.http_logger.log_response(req_id, response, execution_time)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"🚨 GCP API request failed [{req_id}]: {str(e)}")
            raise

    @monitor_performance
    def _get_all_services(self):
        logger.debug("📋 Fetching all GCP services...")
        all_services = []
        next_page_token = None
        page_count = 0
        
        while True:
            page_count += 1
            params = {'pageToken': next_page_token} if next_page_token else {}
            
            logger.debug(f"   📄 Fetching services page {page_count}")
            data = self._make_api_request(f"{self.API_HOST}/v1/services", params)
            
            services = data.get('services', [])
            all_services.extend(services)
            logger.debug(f"   ➕ Added {len(services)} services (total: {len(all_services)})")
            
            next_page_token = data.get('nextPageToken')
            if not next_page_token:
                break
        
        logger.info(f"✅ Retrieved {len(all_services)} GCP services in {page_count} pages")
        return all_services

    @monitor_performance
    def get_skus_from_filters(self, filters):
        logger.info(f"🔍 Starting SKU discovery with {len(filters)} filter sets")
        
        normalized_skus = []
        compute_service = next((s for s in self.all_services if s['serviceId'] == '6F81-5844-456A'), None)
        
        if not compute_service:
            logger.error("❌ Compute Engine service not found in services list")
            logger.debug(f"   🔍 Available services: {[s.get('serviceId') for s in self.all_services[:5]]}...")
            return []

        logger.info(f"✅ Found Compute Engine service: {compute_service['name']}")
        
        for i, filter_terms in enumerate(filters):
            filter_desc = ' & '.join(filter_terms)
            logger.info(f"🔍 Processing filter {i + 1}/{len(filters)}: {filter_desc}")
            
            skus_url = f"{self.API_HOST}/v1/{compute_service['name']}/skus"
            next_page_token = None
            page_count = 0
            filter_matches = 0
            
            while True:
                page_count += 1
                params = {'currencyCode': 'USD', 'pageToken': next_page_token} if next_page_token else {'currencyCode': 'USD'}
                
                logger.debug(f"   📄 Fetching SKUs page {page_count} for filter: {filter_desc}")
                data = self._make_api_request(skus_url, params=params)
                
                skus = data.get('skus', [])
                logger.debug(f"   📋 Processing {len(skus)} SKUs from page {page_count}")
                
                for sku in skus:
                    if self._sku_matches_filter(sku, filter_terms):
                        normalized_sku = self._normalize_gcp_sku(sku)
                        if normalized_sku and not any(d['sku_id'] == normalized_sku['sku_id'] for d in normalized_skus):
                            normalized_skus.append(normalized_sku)
                            filter_matches += 1
                            logger.debug(f"   ✅ Match: {sku.get('description', 'N/A')}")
                
                next_page_token = data.get('nextPageToken')
                if not next_page_token:
                    break
            
            logger.info(f"   📊 Filter '{filter_desc}': {filter_matches} matches from {page_count} pages")
        
        logger.info(f"🎯 SKU discovery complete: {len(normalized_skus)} unique SKUs found")
        return normalized_skus

    def _sku_matches_filter(self, sku, filter_terms):
        """Check if SKU matches filter terms"""
        region_match = self.region in sku.get('serviceRegions', [])
        description = sku.get('description', '').lower()
        term_matches = all(term.lower() in description for term in filter_terms)
        
        match_result = region_match and term_matches
        
        if DEBUG_MODE and match_result:
            logger.debug(f"   🎯 SKU Match: {sku.get('description', 'N/A')} | Regions: {sku.get('serviceRegions', [])}")
        
        return match_result

    @monitor_performance
    def _normalize_gcp_sku(self, sku_dict):
        """Enhanced SKU normalization with detailed logging"""
        try:
            sku_id = sku_dict.get('skuId')
            description = sku_dict.get('description', 'N/A')
            
            logger.debug(f"🔧 Normalizing SKU: {sku_id} - {description}")
            
            # Extract pricing information
            pricing_info = sku_dict.get('pricingInfo', [{}])[0]
            tiered_rates = pricing_info.get('pricingExpression', {}).get('tieredRates', [{}])[0]
            unit_price = tiered_rates.get('unitPrice', {})
            base_price = float(unit_price.get('units', 0)) + float(unit_price.get('nanos', 0)) / 1e9
            
            if base_price == 0.0:
                logger.debug(f"   ⏭️  Skipping {sku_id} - zero price")
                return None

            # Extract category information
            category = sku_dict.get('category', {})
            resource_family = category.get('resourceFamily', '').upper()
            resource_group = category.get('resourceGroup', '').upper()
            
            logger.debug(f"   📂 Category: {resource_family}/{resource_group}")
            
            # Determine price type and machine family
            price_type_code, machine_family_heuristic = self._determine_price_type(
                resource_family, resource_group, description
            )
            
            # Extract additional details
            usage_unit_desc = pricing_info.get('pricingExpression', {}).get('usageUnitDescription', '').lower()
            price_unit = 'month' if 'month' in usage_unit_desc else 'hour'
            incur_charges = 'running' if resource_family == "COMPUTE" else 'always'
            morpheus_price_code = f"{PRICE_PREFIX.lower()}.gcp.{sku_id}.{self.region.replace('-', '_').lower()}"

            normalized_sku = {
                "sku_id": sku_id,
                "morpheus_code": morpheus_price_code,
                "description": description,
                "region": self.region,
                "priceTypeCode": price_type_code,
                "priceUnit": price_unit,
                "incurCharges": incur_charges,
                "currency": unit_price.get('currencyCode', 'USD'),
                "price_per_unit": base_price,
                "machine_family": machine_family_heuristic
            }
            
            logger.debug(f"   ✅ Normalized: {price_type_code}/{machine_family_heuristic} @ ${base_price}")
            return normalized_sku
            
        except Exception as e:
            logger.error(f"❌ Failed to normalize SKU {sku_dict.get('skuId', 'unknown')}: {str(e)}")
            logger.debug(f"   🔍 SKU data: {json.dumps(sku_dict, indent=2)}")
            return None

    def _determine_price_type(self, resource_family, resource_group, description):
        """Determine price type and machine family with logging"""
        logger.debug(f"   🔍 Determining price type for {resource_family}/{resource_group}")
        
        price_type_code = 'software'
        machine_family_heuristic = 'software'
        
        if resource_family == "COMPUTE":
            if resource_group == "CPU":
                price_type_code = 'cores'
                family_match = re.search(r'^([A-Z0-9]+)', description)
                if family_match:
                    machine_family_heuristic = family_match.group(1).lower()
            elif resource_group == "RAM":
                price_type_code = 'memory'
                family_match = re.search(r'^([A-Z0-9]+)', description)
                if family_match:
                    machine_family_heuristic = family_match.group(1).lower()
        elif resource_family == "STORAGE":
            if resource_group == "DISK":
                price_type_code = 'storage'
                machine_family_heuristic = 'pd-standard'
        
        logger.debug(f"   ➡️  Result: {price_type_code}/{machine_family_heuristic}")
        return price_type_code, machine_family_heuristic

# --- Enhanced Functions with Debug Capabilities ---

@monitor_performance
def discover_morpheus_plans(morpheus_api: MorpheusApiClient):
    """Step 1: Discover Google service plans from Morpheus with enhanced logging"""
    logger.info("🔍 Step 1: Discovering Morpheus Service Plans")
    
    try:
        plans_response = morpheus_api.get("service-plans?provisionTypeCode=google&max=1000")
        service_plans = plans_response.get('servicePlans', []) if plans_response else []
        
        logger.info(f"✅ Found {len(service_plans)} GCP Service Plans in Morpheus")
        
        if service_plans:
            logger.info("📋 Service Plans List:")
            for i, plan in enumerate(sorted(service_plans, key=lambda x: x['name'])):
                logger.info(f"   {i+1:3d}. {plan['name']} (ID: {plan['id']})")
                if DEBUG_MODE:
                    config = plan.get('config', {})
                    region = config.get('zoneRegion', config.get('region', 'Unknown'))
                    logger.debug(f"        🌍 Region: {region}")
                    logger.debug(f"        ⚙️  Config keys: {list(config.keys())}")
        else:
            logger.warning("⚠️  No GCP service plans found")
        
        return service_plans
        
    except Exception as e:
        logger.exception(f"❌ Failed to discover Morpheus plans: {str(e)}")
        raise

@monitor_performance
def sync_gcp_data(morpheus_api: MorpheusApiClient, gcp_client: GCPPricingClient):
    """Step 2: Sync relevant GCP data with enhanced monitoring"""
    logger.info("🔄 Step 2: Syncing relevant GCP pricing data")
    
    try:
        # Discover plans
        plans = discover_morpheus_plans(morpheus_api)
        if not plans:
            logger.warning("⚠️  No GCP service plans found in Morpheus. Nothing to sync.")
            return

        # Generate filters
        logger.info("🔍 Generating SKU search filters from service plans")
        filters = set()
        plan_analysis = {}
        
        for plan in plans:
            name = plan.get('name', '').lower()
            match = re.search(r'(e2|n1|n2|c2|m1|m2)-[a-z]+-[0-9]+', name)
            if match:
                family = match.group(1)
                filters.add(tuple(sorted((family,))))
                
                if family not in plan_analysis:
                    plan_analysis[family] = []
                plan_analysis[family].append(plan['name'])
        
        # Always add storage
        filters.add(tuple(sorted(('pd-standard',))))
        
        logger.info(f"📊 Filter Analysis:")
        for family, plans_list in plan_analysis.items():
            logger.info(f"   🏷️  {family}: {len(plans_list)} plans")
            if DEBUG_MODE:
                for plan_name in plans_list[:3]:  # Show first 3
                    logger.debug(f"      • {plan_name}")
                if len(plans_list) > 3:
                    logger.debug(f"      • ... and {len(plans_list) - 3} more")
        
        logger.info(f"✅ Generated {len(filters)} unique SKU search filters")
        
        # Fetch pricing data
        pricing_data = gcp_client.get_skus_from_filters([list(f) for f in filters])
        
        # Save to file
        logger.info(f"💾 Saving pricing data to {LOCAL_SKU_CACHE_FILE}")
        with open(LOCAL_SKU_CACHE_FILE, 'w') as f:
            json.dump(pricing_data, f, indent=2)
        
        # Analysis
        logger.info("📊 Pricing Data Analysis:")
        by_family = {}
        by_type = {}
        
        for item in pricing_data:
            family = item.get('machine_family', 'unknown')
            price_type = item.get('priceTypeCode', 'unknown')
            
            by_family[family] = by_family.get(family, 0) + 1
            by_type[price_type] = by_type.get(price_type, 0) + 1
        
        logger.info(f"   📈 By Machine Family:")
        for family, count in sorted(by_family.items()):
            logger.info(f"      • {family}: {count} SKUs")
        
        logger.info(f"   📈 By Price Type:")
        for ptype, count in sorted(by_type.items()):
            logger.info(f"      • {ptype}: {count} SKUs")
        
        logger.info(f"✅ Pricing data saved successfully | Total SKUs: {len(pricing_data)}")
        
    except Exception as e:
        logger.exception(f"❌ Failed to sync GCP data: {str(e)}")
        raise

@monitor_performance
def create_prices(morpheus_api: MorpheusApiClient):
    """Step 3: Create prices in Morpheus with detailed tracking"""
    logger.info("💰 Step 3: Creating Prices in Morpheus")
    
    if not os.path.exists(LOCAL_SKU_CACHE_FILE):
        logger.error(f"❌ Local cache file '{LOCAL_SKU_CACHE_FILE}' not found. Please run 'sync-gcp-data' first.")
        return

    try:
        with open(LOCAL_SKU_CACHE_FILE, 'r') as f:
            pricing_data = json.load(f)
        
        logger.info(f"📂 Loaded {len(pricing_data)} prices from local cache")
        
        # Statistics tracking
        stats = {
            'processed': 0,
            'created': 0,
            'skipped_existing': 0,
            'errors': 0,
            'by_type': {}
        }
        
        logger.info("🔄 Processing prices...")
        
        for i, price_info in enumerate(pricing_data):
            stats['processed'] += 1
            price_type = price_info.get('priceTypeCode', 'unknown')
            stats['by_type'][price_type] = stats['by_type'].get(price_type, 0) + 1
            
            # Progress indicator
            if i % 10 == 0 or i == len(pricing_data) - 1:
                progress = (i + 1) / len(pricing_data) * 100
                logger.info(f"   📊 Progress: {i+1}/{len(pricing_data)} ({progress:.1f}%)")
            
            try:
                # Check if price already exists
                existing = morpheus_api.get(f"prices?code={price_info['morpheus_code']}")
                if existing and existing.get('prices'):
                    stats['skipped_existing'] += 1
                    logger.debug(f"   ⏭️  Skipping existing price: {price_info['morpheus_code']}")
                    continue
                
                # Create price payload
                payload = { "price": {
                    "name": f"{PRICE_PREFIX} - {price_info['description']}", 
                    "code": price_info['morpheus_code'],
                    "priceType": price_info['priceTypeCode'], 
                    "priceUnit": price_info['priceUnit'], 
                    "price": price_info['price_per_unit'], 
                    "cost": price_info['price_per_unit'], 
                    "incurCharges": price_info['incurCharges'], 
                    "currency": price_info['currency'], 
                    "active": True
                }}
                
                if price_info['priceTypeCode'] == 'software':
                    payload['price']['software'] = price_info['description']

                logger.debug(f"   ➕ Creating price: {price_info['morpheus_code']}")
                response = morpheus_api.post("prices", payload)
                
                if response and (response.get('success') or response.get('price')):
                    stats['created'] += 1
                    logger.debug(f"   ✅ Created: {price_info['description']}")
                else:
                    stats['errors'] += 1
                    logger.error(f"   ❌ Failed to create price: {price_info['description']} | Response: {response}")
                    
            except Exception as e:
                stats['errors'] += 1
                logger.error(f"   ❌ Exception creating price '{price_info['description']}': {str(e)}")
        
        # Final statistics
        logger.info("📊 Price Creation Summary:")
        logger.info(f"   📋 Total Processed: {stats['processed']}")
        logger.info(f"   ✅ Created: {stats['created']}")
        logger.info(f"   ⏭️  Skipped (existing): {stats['skipped_existing']}")
        logger.info(f"   ❌ Errors: {stats['errors']}")
        logger.info(f"   📈 By Type:")
        for ptype, count in sorted(stats['by_type'].items()):
            logger.info(f"      • {ptype}: {count}")
        
        logger.info("✅ Price creation complete")
        
    except Exception as e:
        logger.exception(f"❌ Failed to create prices: {str(e)}")
        raise

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Enhanced Price Sets Function ---
@monitor_performance
def create_price_sets(morpheus_api: MorpheusApiClient):
    """Step 4: Create price sets with comprehensive tracking"""
    logger.info("📦 Step 4: Creating Price Sets in Morpheus")
    
    if not os.path.exists(LOCAL_SKU_CACHE_FILE):
        logger.error(f"❌ Local cache file '{LOCAL_SKU_CACHE_FILE}' not found")
        return

    try:
        with open(LOCAL_SKU_CACHE_FILE, 'r') as f:
            pricing_data = json.load(f)
        
        # Get all prices with our prefix
        logger.info(f"🔍 Fetching existing prices with prefix: {PRICE_PREFIX}")
        all_prices_resp = morpheus_api.get(f"prices?max=2000&phrase={PRICE_PREFIX}")
        
        if not all_prices_resp or not all_prices_resp.get('prices'):
            logger.error("❌ No prices found with the required prefix. Please run 'create-prices' first.")
            return

        price_id_map = {p['code']: p['id'] for p in all_prices_resp['prices']}
        logger.info(f"✅ Found {len(price_id_map)} existing prices")
        
        # Group prices by machine family and region
        price_set_groups = {}
        
        for price_info in pricing_data:
            family = price_info.get('machine_family', 'unknown')
            if family == 'software': 
                logger.debug(f"   ⏭️  Skipping software price: {price_info['morpheus_code']}")
                continue
            
            region = price_info['region'].replace('-', '_')
            group_key = f"gcp-{family}-{region}"
            
            if group_key not in price_set_groups:
                price_set_groups[group_key] = {
                    "name": f"{PRICE_PREFIX} - GCP - {family.upper()} ({price_info['region']})",
                    "code": f"{PRICE_PREFIX.lower()}.{group_key}",
                    "prices": set(),
                    "region": price_info['region'],
                    "family": family
                }
            
            price_id = price_id_map.get(price_info['morpheus_code'])
            if price_id:
                price_set_groups[group_key]["prices"].add(price_id)
            else:
                logger.warning(f"   ⚠️  Price not found in Morpheus: {price_info['morpheus_code']}")

        logger.info(f"📊 Price Set Groups Analysis:")
        for group_key, data in price_set_groups.items():
            logger.info(f"   📦 {group_key}: {len(data['prices'])} prices")
        
        # Create/update price sets
        stats = {'processed': 0, 'created': 0, 'updated': 0, 'errors': 0, 'skipped': 0}
        
        for i, (key, data) in enumerate(price_set_groups.items()):
            stats['processed'] += 1
            logger.info(f"🔄 Processing price set {i + 1}/{len(price_set_groups)}: {data['name']}")
            
            if not data["prices"]:
                stats['skipped'] += 1
                logger.warning(f"   ⏭️  Skipping - no prices found")
                continue
            
            # Create payload
            payload = {
                "priceSet": {
                    "name": data["name"], 
                    "code": data["code"], 
                    "type": "fixed",
                    "priceUnit": "hour",
                    "regionCode": PRICE_PREFIX.lower(),
                    "prices": [{"id": price_id} for price_id in data["prices"]]
                }
            }
            
            try:
                # Check if exists
                existing = morpheus_api.get(f"price-sets?code={data['code']}")
                
                if existing and existing.get('priceSets') and len(existing['priceSets']) > 0:
                    # Update existing
                    price_set_id = existing['priceSets'][0]['id']
                    logger.info(f"   🔄 Updating existing price set (ID: {price_set_id})")
                    response = morpheus_api.put(f"price-sets/{price_set_id}", payload)
                    if response and (response.get('success') or response.get('priceSet')):
                        stats['updated'] += 1
                        logger.info(f"   ✅ Updated successfully")
                    else:
                        stats['errors'] += 1
                        logger.error(f"   ❌ Update failed: {response}")
                else:
                    # Create new
                    logger.info(f"   ➕ Creating new price set")
                    response = morpheus_api.post("price-sets", payload)
                    if response and (response.get('success') or response.get('priceSet')):
                        stats['created'] += 1
                        logger.info(f"   ✅ Created successfully")
                    else:
                        stats['errors'] += 1
                        logger.error(f"   ❌ Creation failed: {response}")
                        
            except Exception as e:
                stats['errors'] += 1
                logger.error(f"   ❌ Exception processing price set: {str(e)}")
        
        # Summary
        logger.info("📊 Price Set Creation Summary:")
        logger.info(f"   📋 Total Processed: {stats['processed']}")
        logger.info(f"   ➕ Created: {stats['created']}")
        logger.info(f"   🔄 Updated: {stats['updated']}")
        logger.info(f"   ⏭️  Skipped: {stats['skipped']}")
        logger.info(f"   ❌ Errors: {stats['errors']}")
        
        logger.info("✅ Price Set creation complete")
        
    except Exception as e:
        logger.exception(f"❌ Failed to create price sets: {str(e)}")
        raise

@monitor_performance
def map_plans_to_price_sets(morpheus_api: MorpheusApiClient):
    """Step 5: Map price sets to service plans with detailed tracking"""
    logger.info("🔗 Step 5: Mapping Price Sets to Service Plans")
    
    try:
        # Get all GCP service plans
        logger.info("🔍 Fetching GCP service plans...")
        plans_resp = morpheus_api.get("service-plans?provisionTypeCode=google&max=1000")
        if not plans_resp or not plans_resp.get('servicePlans'):
            logger.error("❌ No GCP service plans found")
            return
        
        plans = plans_resp['servicePlans']
        logger.info(f"✅ Found {len(plans)} GCP service plans")
        
        # Get all our price sets
        logger.info(f"🔍 Fetching price sets with prefix: {PRICE_PREFIX}")
        price_sets_resp = morpheus_api.get(f"price-sets?max=1000&phrase={PRICE_PREFIX}")
        if not price_sets_resp or not price_sets_resp.get('priceSets'):
            logger.error("❌ No price sets found. Please run 'create-price-sets' first.")
            return
        
        price_set_map = {ps['code']: ps for ps in price_sets_resp['priceSets']}
        logger.info(f"✅ Found {len(price_set_map)} price sets")
        
        # Statistics
        stats = {
            'processed': 0, 'updated': 0, 'skipped_no_region': 0, 
            'skipped_no_family': 0, 'skipped_no_price_sets': 0, 
            'skipped_already_mapped': 0, 'errors': 0
        }
        
        logger.info("🔄 Processing service plan mappings...")
        
        for i, plan in enumerate(plans):
            stats['processed'] += 1
            plan_name = plan.get('name', 'Unknown')
            
            if i % 10 == 0 or i == len(plans) - 1:
                progress = (i + 1) / len(plans) * 100
                logger.info(f"   📊 Progress: {i+1}/{len(plans)} ({progress:.1f}%)")
            
            logger.debug(f"🔍 Processing: {plan_name}")
            
            try:
                # Extract region
                plan_region = self._extract_plan_region(plan)
                if not plan_region:
                    stats['skipped_no_region'] += 1
                    logger.debug(f"   ⏭️  No region found for: {plan_name}")
                    continue
                
                # Extract machine family
                machine_family = self._extract_machine_family(plan_name)
                if not machine_family:
                    stats['skipped_no_family'] += 1
                    logger.debug(f"   ⏭️  No machine family found for: {plan_name}")
                    continue
                
                # Find matching price sets
                expected_ps_code = f"{PRICE_PREFIX.lower()}.gcp-{machine_family}-{plan_region.replace('-', '_')}"
                disk_ps_code = f"{PRICE_PREFIX.lower()}.gcp-pd-standard-{plan_region.replace('-', '_')}"
                
                price_sets_to_link = []
                if expected_ps_code in price_set_map:
                    price_sets_to_link.append(price_set_map[expected_ps_code])
                if disk_ps_code in price_set_map:
                    price_sets_to_link.append(price_set_map[disk_ps_code])
                
                if not price_sets_to_link:
                    stats['skipped_no_price_sets'] += 1
                    logger.debug(f"   ⏭️  No matching price sets for: {plan_name} (family: {machine_family}, region: {plan_region})")
                    continue
                
                # Check if already mapped
                current_price_sets = plan.get('priceSets', []) or []
                current_ps_ids = {ps['id'] for ps in current_price_sets if ps and 'id' in ps}
                new_ps_ids = {ps['id'] for ps in price_sets_to_link}
                
                if new_ps_ids.issubset(current_ps_ids):
                    stats['skipped_already_mapped'] += 1
                    logger.debug(f"   ⏭️  Already mapped: {plan_name}")
                    continue
                
                # Update plan
                final_ps_ids = current_ps_ids.union(new_ps_ids)
                payload = {
                    "servicePlan": {
                        "priceSets": [{"id": ps_id} for ps_id in final_ps_ids]
                    }
                }
                
                logger.debug(f"   🔄 Updating plan with {len(price_sets_to_link)} price sets")
                response = morpheus_api.put(f"service-plans/{plan['id']}", payload)
                
                if response and (response.get('success') or response.get('servicePlan')):
                    stats['updated'] += 1
                    logger.debug(f"   ✅ Updated: {plan_name}")
                else:
                    stats['errors'] += 1
                    logger.error(f"   ❌ Failed to update: {plan_name} | Response: {response}")
                    
            except Exception as e:
                stats['errors'] += 1
                logger.error(f"   ❌ Exception processing: {plan_name} | Error: {str(e)}")
        
        # Summary
        logger.info("📊 Service Plan Mapping Summary:")
        logger.info(f"   📋 Total Processed: {stats['processed']}")
        logger.info(f"   ✅ Updated: {stats['updated']}")
        logger.info(f"   ⏭️  Skipped (no region): {stats['skipped_no_region']}")
        logger.info(f"   ⏭️  Skipped (no family): {stats['skipped_no_family']}")
        logger.info(f"   ⏭️  Skipped (no price sets): {stats['skipped_no_price_sets']}")
        logger.info(f"   ⏭️  Skipped (already mapped): {stats['skipped_already_mapped']}")
        logger.info(f"   ❌ Errors: {stats['errors']}")
        
        logger.info("✅ Service Plan mapping complete")
        
    except Exception as e:
        logger.exception(f"❌ Failed to map plans to price sets: {str(e)}")
        raise

def _extract_plan_region(plan):
    """Extract region from service plan configuration"""
    config = plan.get('config', {})
    if not config:
        return None
    
    # Try different possible region field names
    region = (config.get('zoneRegion') or 
              config.get('region') or 
              config.get('availabilityZone', '').split('-')[0:2] if config.get('availabilityZone') else None)
    
    if isinstance(region, list):
        region = '-'.join(region)
    
    return region

def _extract_machine_family(plan_name):
    """Extract machine family from plan name"""
    plan_name_lower = plan_name.lower()
    match = re.search(r'(?:google-)?([a-z0-9]+)-', plan_name_lower)
    return match.group(1) if match else None

@monitor_performance
def validate(morpheus_api: MorpheusApiClient):
    """Enhanced validation with detailed analysis"""
    logger.info("✅ Validating Service Plan Pricing")
    
    try:
        plans_resp = morpheus_api.get("service-plans?provisionTypeCode=google&max=1000")
        if not plans_resp:
            logger.error("❌ Failed to retrieve service plans")
            return
            
        plans = plans_resp.get('servicePlans', [])
        logger.info(f"📋 Analyzing {len(plans)} GCP service plans")
        
        # Statistics
        stats = {
            'total': len(plans),
            'priced': 0,
            'unpriced': 0,
            'by_family': {},
            'by_region': {},
            'price_set_distribution': {}
        }
        
        logger.info("📊 Detailed Analysis:")
        
        for plan in sorted(plans, key=lambda p: p['name']):
            price_sets = plan.get('priceSets', [])
            has_pricing = len(price_sets) > 0
            
            if has_pricing:
                stats['priced'] += 1
            else:
                stats['unpriced'] += 1
            
            # Extract family and region for statistics
            family = _extract_machine_family(plan['name']) or 'unknown'
            region = _extract_plan_region(plan) or 'unknown'
            
            stats['by_family'][family] = stats['by_family'].get(family, {'priced': 0, 'total': 0})
            stats['by_family'][family]['total'] += 1
            if has_pricing:
                stats['by_family'][family]['priced'] += 1
            
            stats['by_region'][region] = stats['by_region'].get(region, {'priced': 0, 'total': 0})
            stats['by_region'][region]['total'] += 1
            if has_pricing:
                stats['by_region'][region]['priced'] += 1
            
            # Price set count distribution
            ps_count = len(price_sets)
            stats['price_set_distribution'][ps_count] = stats['price_set_distribution'].get(ps_count, 0) + 1
            
            # Individual plan status
            status = f"✅ PRICED ({len(price_sets)} sets)" if has_pricing else "❌ NOT PRICED"
            logger.info(f"   📋 {plan['name']} (ID: {plan['id']}) - {status}")
            
            if price_sets and DEBUG_MODE:
                for ps in sorted(price_sets, key=lambda x: x.get('name', '')):
                    logger.debug(f"      └── {ps.get('name', 'Unknown')} (ID: {ps.get('id', 'Unknown')})")
        
        # Summary statistics
        logger.info("📈 Summary Statistics:")
        logger.info(f"   📊 Overall: {stats['priced']}/{stats['total']} plans priced ({stats['priced']/stats['total']*100:.1f}%)")
        
        logger.info(f"   📊 By Machine Family:")
        for family, data in sorted(stats['by_family'].items()):
            percentage = data['priced']/data['total']*100 if data['total'] > 0 else 0
            logger.info(f"      • {family}: {data['priced']}/{data['total']} ({percentage:.1f}%)")
        
        logger.info(f"   📊 By Region:")
        for region, data in sorted(stats['by_region'].items()):
            percentage = data['priced']/data['total']*100 if data['total'] > 0 else 0
            logger.info(f"      • {region}: {data['priced']}/{data['total']} ({percentage:.1f}%)")
        
        logger.info(f"   📊 Price Set Distribution:")
        for count, plans_count in sorted(stats['price_set_distribution'].items()):
            logger.info(f"      • {count} price sets: {plans_count} plans")
        
        logger.info("✅ Validation complete")
        
    except Exception as e:
        logger.exception(f"❌ Validation failed: {str(e)}")
        raise

# --- Enhanced Main Function ---
def main():
    """Enhanced main function with comprehensive error handling"""
    parser = argparse.ArgumentParser(
        description="Morpheus GCP Pricing Tool (Enhanced Debug Version)", 
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument('command', choices=[
        'discover-morpheus-plans', 'sync-gcp-data', 'create-prices', 
        'create-price-sets', 'map-plans-to-price-sets', 'validate'
    ], help="""Action to perform (run in order):
    
    1. discover-morpheus-plans   : List all GCP service plans currently in Morpheus.
    2. sync-gcp-data             : Fetch GCP SKUs for your plans and save to a local file.
    3. create-prices             : Create/update prices in Morpheus from the local file.
    4. create-price-sets         : Group Morpheus prices into price sets.
    5. map-plans-to-price-sets   : Link price sets to the corresponding service plans.
    
    validate                     : Check which Morpheus GCP plans have pricing.
    """)
    
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--log-file', help='Custom log file path')
    parser.add_argument('--no-http-capture', action='store_true', help='Disable HTTP traffic capture')
    parser.add_argument('--no-performance', action='store_true', help='Disable performance monitoring')
    
    args = parser.parse_args()
    
    # Update configuration based on arguments
    global DEBUG_MODE, LOG_FILE, CAPTURE_HTTP_TRAFFIC, PERFORMANCE_MONITORING
    if args.debug:
        DEBUG_MODE = True
    if args.log_file:
        LOG_FILE = args.log_file
    if args.no_http_capture:
        CAPTURE_HTTP_TRAFFIC = False
    if args.no_performance:
        PERFORMANCE_MONITORING = False
    
    # Reinitialize logger with updated settings
    global logger
    logger = DebugLogger()
    
    try:
        logger.info("🚀 Starting Morpheus GCP Pricing Tool")
        logger.info(f"   📋 Command: {args.command}")
        logger.info(f"   🔧 Debug Mode: {DEBUG_MODE}")
        logger.info(f"   📄 Log File: {LOG_FILE}")
        logger.info(f"   🌐 HTTP Capture: {CAPTURE_HTTP_TRAFFIC}")
        logger.info(f"   ⏱️  Performance Monitoring: {PERFORMANCE_MONITORING}")
        
        start_time = time.time()
        
        # Initialize API client
        logger.info("🔗 Initializing Morpheus API client...")
        morpheus_api = MorpheusApiClient(MORPHEUS_URL, MORPHEUS_TOKEN)
        
        # Initialize GCP client if needed
        gcp_client = None
        if args.command == 'sync-gcp-data':
            logger.info("🌤️  Initializing GCP Pricing client...")
            gcp_client = GCPPricingClient(GCP_REGION)
        
        # Execute command
        logger.info(f"▶️  Executing command: {args.command}")
        
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
        
        total_time = time.time() - start_time
        logger.info(f"🎉 Command completed successfully in {total_time:.2f} seconds")
        logger.info(f"📄 Detailed logs saved to: {LOG_FILE}")
        
    except KeyboardInterrupt:
        logger.warning("⚠️  Operation interrupted by user")
        sys.exit(1)
    except Exception as e:
        total_time = time.time() - start_time if 'start_time' in locals() else 0
        logger.critical(f"💥 Fatal error after {total_time:.2f} seconds: {str(e)}")
        logger.critical(f"📄 Full error details in log file: {LOG_FILE}")
        
        if DEBUG_MODE:
            logger.critical("🔍 Full stack trace:")
            logger.critical(traceback.format_exc())
        
        sys.exit(1)

if __name__ == "__main__":
    main()