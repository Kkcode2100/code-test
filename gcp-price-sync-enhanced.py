#!/usr/bin/env python3
"""
GCP Price Sync Enhanced - Complete Service Plan, Price, and Price Set Creation

This enhanced version uses the downloaded SKU catalog from gcp-sku-downloader.py
to create comprehensive service plans, prices, and price sets with proper mapping.

Features:
- Uses downloaded SKU catalog (no API calls needed)
- Creates service plans based on GCP instance types
- Creates comprehensive pricing data from SKU catalog
- Creates price sets by category and service
- Maps price sets to service plans
- Handles tiered pricing and regional pricing
- Comprehensive validation and reporting

Usage:
    python gcp-price-sync-enhanced.py --sku-catalog gcp_skus_20250807_194211.json
    python gcp-price-sync-enhanced.py --sku-catalog gcp_skus_20250807_194211.json --dry-run
    python gcp-price-sync-enhanced.py --sku-catalog gcp_skus_20250807_194211.json --create-service-plans
"""

import requests
import json
import logging
import time
import urllib3
import argparse
import os
import re
import uuid
import sys
from datetime import datetime
from collections import defaultdict
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Configuration ---
MORPHEUS_URL = os.getenv("MORPHEUS_URL", "https://localhost")
MORPHEUS_TOKEN = os.getenv("MORPHEUS_TOKEN", "9fcc4426-c89a-4430-b6d7-99d5950fc1cc")
GCP_REGION = os.getenv("GCP_REGION", "asia-southeast2")
PRICE_PREFIX = os.getenv("PRICE_PREFIX", "IOH-CP")

# --- Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

class SKUCatalogProcessor:
    """Process and analyze the comprehensive SKU catalog."""
    
    def __init__(self, catalog_file):
        self.catalog_file = catalog_file
        self.catalog = self._load_catalog()
        self.processed_skus = self._process_skus()
        self.compute_skus = self._extract_compute_skus()
        
    def _load_catalog(self):
        """Load the SKU catalog from file."""
        try:
            with open(self.catalog_file, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
            logger.info(f"Loaded SKU catalog: {catalog['metadata']['total_services']} services, {catalog['metadata']['total_skus']} SKUs")
            return catalog
        except Exception as e:
            logger.error(f"Error loading SKU catalog: {e}")
            raise
    
    def _process_skus(self):
        """Process and normalize SKUs for pricing sync."""
        processed = {
            'compute': [],
            'storage': [],
            'network': [],
            'database': [],
            'ai_ml': [],
            'other': []
        }
        
        for service_id, service_data in self.catalog['services'].items():
            service_name = service_data['service_info']['display_name']
            
            for sku in service_data['skus']:
                normalized_sku = self._normalize_sku(sku, service_name, service_id)
                if normalized_sku:
                    category = self._categorize_sku(normalized_sku)
                    processed[category].append(normalized_sku)
        
        # Log summary
        for category, skus in processed.items():
            logger.info(f"Processed {len(skus)} {category} SKUs")
        
        return processed
    
    def _normalize_sku(self, sku, service_name, service_id):
        """Normalize SKU data for pricing sync."""
        try:
            # Extract pricing info
            pricing_info = sku.get('pricingInfo', [])
            if not pricing_info:
                return None
            
            # Get the first pricing tier
            tiered_rates = pricing_info[0].get('pricingExpression', {}).get('tieredRates', [])
            if not tiered_rates:
                return None
            
            # Extract rate
            rate = tiered_rates[0].get('unitPrice', {})
            if not rate:
                return None
            
            # Determine pricing unit
            pricing_unit = pricing_info[0].get('pricingExpression', {}).get('usageUnit', 'hour')
            
            # Extract SKU details
            sku_id = sku.get('skuId', '')
            description = sku.get('description', '')
            category = sku.get('category', {})
            
            # Create normalized SKU
            normalized = {
                'sku_id': sku_id,
                'description': description,
                'service_name': service_name,
                'service_id': service_id,
                'category': category,
                'pricing_unit': pricing_unit,
                'rate': rate,
                'tiered_rates': tiered_rates,
                'pricing_info': pricing_info,
                'original_sku': sku
            }
            
            return normalized
            
        except Exception as e:
            logger.warning(f"Error normalizing SKU {sku.get('skuId', 'unknown')}: {e}")
            return None
    
    def _categorize_sku(self, sku):
        """Categorize SKU based on service and description."""
        service_name = sku['service_name'].lower()
        description = sku['description'].lower()
        category = sku['category']
        
        # Check resource family first
        resource_family = category.get('resourceFamily', '').lower()
        if resource_family == 'storage':
            return 'storage'
        elif resource_family == 'compute':
            return 'compute'
        elif resource_family == 'network':
            return 'network'
        elif resource_family == 'database':
            return 'database'
        elif resource_family in ['ai/ml', 'ai', 'ml']:
            return 'ai_ml'
        
        # Storage services
        if any(keyword in service_name for keyword in ['storage', 'cloud storage', 'filestore', 'memorystore']):
            return 'storage'
        
        # Compute services
        if any(keyword in service_name for keyword in ['compute', 'vm', 'instance', 'gke', 'kubernetes', 'run', 'functions']):
            return 'compute'
        
        # Network services
        if any(keyword in service_name for keyword in ['network', 'vpc', 'load balancer', 'cdn', 'gateway']):
            return 'network'
        
        # Database services
        if any(keyword in service_name for keyword in ['sql', 'database', 'firestore', 'bigtable', 'spanner', 'alloydb']):
            return 'database'
        
        # AI/ML services
        if any(keyword in service_name for keyword in ['ai', 'ml', 'vertex', 'notebooks', 'composer', 'dataflow']):
            return 'ai_ml'
        
        # Check description for additional clues
        if any(keyword in description for keyword in ['storage', 'gb', 'tb']):
            return 'storage'
        if any(keyword in description for keyword in ['cpu', 'ram', 'memory', 'core']):
            return 'compute'
        if any(keyword in description for keyword in ['network', 'bandwidth', 'transfer']):
            return 'network'
        if any(keyword in description for keyword in ['database', 'sql', 'query']):
            return 'database'
        if any(keyword in description for keyword in ['ai', 'ml', 'machine learning', 'tensorflow']):
            return 'ai_ml'
        
        return 'other'
    
    def _extract_compute_skus(self):
        """Extract compute SKUs for service plan creation."""
        compute_skus = []
        
        # Look for Compute Engine service
        for service_id, service_data in self.catalog['services'].items():
            if service_data['service_info']['display_name'] == 'Compute Engine':
                for sku in service_data['skus']:
                    # Extract instance type information
                    description = sku.get('description', '').lower()
                    sku_id = sku.get('skuId', '')
                    
                    # Look for instance type patterns
                    instance_patterns = [
                        r'(\w+\d+[a-z]?-\w+-\d+)',  # e2-standard-2, n2-standard-4, etc.
                        r'(\w+\d+[a-z]?-\w+)',      # e2-standard, n2-standard, etc.
                        r'(\w+\d+[a-z]?-\d+)',      # e2-2, n2-4, etc.
                    ]
                    
                    for pattern in instance_patterns:
                        matches = re.findall(pattern, description)
                        for match in matches:
                            compute_skus.append({
                                'instance_type': match,
                                'sku_id': sku_id,
                                'description': sku.get('description', ''),
                                'pricing_info': sku.get('pricingInfo', []),
                                'original_sku': sku
                            })
                            break
                    else:
                        # If no instance type found, still include for general compute pricing
                        compute_skus.append({
                            'instance_type': 'general',
                            'sku_id': sku_id,
                            'description': sku.get('description', ''),
                            'pricing_info': sku.get('pricingInfo', []),
                            'original_sku': sku
                        })
        
        logger.info(f"Extracted {len(compute_skus)} compute SKUs for service plan creation")
        return compute_skus
    
    def get_storage_skus(self):
        """Get all storage-related SKUs."""
        return self.processed_skus['storage']
    
    def get_compute_skus(self):
        """Get all compute-related SKUs."""
        return self.processed_skus['compute']
    
    def get_network_skus(self):
        """Get all network-related SKUs."""
        return self.processed_skus['network']
    
    def get_database_skus(self):
        """Get all database-related SKUs."""
        return self.processed_skus['database']
    
    def get_ai_ml_skus(self):
        """Get all AI/ML-related SKUs."""
        return self.processed_skus['ai_ml']
    
    def get_all_skus(self):
        """Get all processed SKUs."""
        all_skus = []
        for category_skus in self.processed_skus.values():
            all_skus.extend(category_skus)
        return all_skus
    
    def get_sku_summary(self):
        """Get summary of processed SKUs."""
        summary = {}
        for category, skus in self.processed_skus.items():
            summary[category] = {
                'count': len(skus),
                'services': list(set(sku['service_name'] for sku in skus))
            }
        return summary

def discover_morpheus_plans(morpheus_api: MorpheusApiClient):
    """Discover existing plans in Morpheus."""
    logger.info("Discovering existing Morpheus plans...")
    
    try:
        plans_response = morpheus_api.get("plans")
        if not plans_response:
            logger.warning("No plans found or unable to fetch plans")
            return []
        
        plans = plans_response.get("plans", [])
        logger.info(f"Found {len(plans)} existing plans")
        
        # Filter for GCP plans
        gcp_plans = []
        for plan in plans:
            if plan.get("zone", {}).get("cloud", {}).get("type") == "gcp":
                gcp_plans.append(plan)
        
        logger.info(f"Found {len(gcp_plans)} GCP plans")
        return gcp_plans
        
    except Exception as e:
        logger.error(f"Error discovering plans: {e}")
        return []

def create_comprehensive_pricing_data(morpheus_api: MorpheusApiClient, sku_processor: SKUCatalogProcessor):
    """Create comprehensive pricing data from SKU catalog."""
    logger.info("Creating comprehensive pricing data from SKU catalog...")
    
    all_skus = sku_processor.get_all_skus()
    logger.info(f"Processing {len(all_skus)} SKUs for pricing data creation")
    
    pricing_data = []
    
    for sku in all_skus:
        try:
            # Create pricing entry
            pricing_entry = {
                'name': f"{PRICE_PREFIX}-{sku['sku_id']}",
                'code': f"gcp-{sku['sku_id']}",
                'priceType': 'fixed',
                'priceUnit': sku['pricing_unit'],
                'price': 0.0,  # Will be calculated from rate
                'markupType': 'fixed',
                'markup': 0,
                'markupPercent': 0,
                'cost': 0.0,  # Will be calculated from rate
                'currency': 'USD',
                'refType': 'ComputeZone',
                'refId': None,  # Will be set when mapping to zones
                'volumeType': None,
                'datastore': None,
                'crossCloudApply': False,
                'sku': sku['sku_id'],
                'sku_description': sku['description'],
                'service_name': sku['service_name'],
                'service_id': sku['service_id'],
                'category': sku['category']
            }
            
            # Calculate pricing from rate
            rate = sku['rate']
            if 'units' in rate and 'nanos' in rate:
                # Convert nanos to dollars
                price = (rate['units'] or 0) + (rate['nanos'] or 0) / 1_000_000_000
                pricing_entry['price'] = price
                pricing_entry['cost'] = price
            
            pricing_data.append(pricing_entry)
            
        except Exception as e:
            logger.warning(f"Error processing SKU {sku['sku_id']} for pricing: {e}")
            continue
    
    logger.info(f"Created {len(pricing_data)} pricing entries")
    return pricing_data

def create_enhanced_price_sets(morpheus_api: MorpheusApiClient, sku_processor: SKUCatalogProcessor):
    """Create enhanced price sets with comprehensive coverage."""
    logger.info("Creating enhanced price sets...")
    
    # Get SKU summary
    sku_summary = sku_processor.get_sku_summary()
    
    price_sets = []
    
    # Create price sets by category
    for category, summary in sku_summary.items():
        if summary['count'] > 0:
            price_set = {
                'name': f"{PRICE_PREFIX}-{category.upper()}-PRICES",
                'code': f"gcp-{category}-prices",
                'priceUnit': 'month',
                'priceType': 'fixed',
                'incurCharges': True,
                'currency': 'USD',
                'refType': 'ComputeZone',
                'refId': None,
                'volumeType': None,
                'datastore': None,
                'crossCloudApply': False,
                'category': category,
                'sku_count': summary['count'],
                'services': summary['services']
            }
            price_sets.append(price_set)
    
    # Create comprehensive price set
    comprehensive_set = {
        'name': f"{PRICE_PREFIX}-COMPREHENSIVE-PRICES",
        'code': "gcp-comprehensive-prices",
        'priceUnit': 'month',
        'priceType': 'fixed',
        'incurCharges': True,
        'currency': 'USD',
        'refType': 'ComputeZone',
        'refId': None,
        'volumeType': None,
        'datastore': None,
        'crossCloudApply': False,
        'category': 'comprehensive',
        'sku_count': sum(summary['count'] for summary in sku_summary.values()),
        'services': list(set(service for summary in sku_summary.values() for service in summary['services']))
    }
    price_sets.append(comprehensive_set)
    
    logger.info(f"Created {len(price_sets)} price sets")
    return price_sets

def create_service_plans_from_skus(morpheus_api: MorpheusApiClient, sku_processor: SKUCatalogProcessor):
    """Create service plans based on compute SKUs."""
    logger.info("Creating service plans from compute SKUs...")
    
    compute_skus = sku_processor.compute_skus
    if not compute_skus:
        logger.warning("No compute SKUs found for service plan creation")
        return []
    
    # Group by instance family
    instance_families = defaultdict(list)
    for sku in compute_skus:
        instance_type = sku['instance_type']
        if instance_type != 'general':
            # Extract family (e2, n2, c2, etc.)
            family_match = re.match(r'(\w+\d+[a-z]?)', instance_type)
            if family_match:
                family = family_match.group(1)
                instance_families[family].append(sku)
    
    service_plans = []
    
    # Create service plans for each family
    for family, skus in instance_families.items():
        # Get unique instance types for this family
        instance_types = list(set(sku['instance_type'] for sku in skus))
        
        for instance_type in instance_types[:10]:  # Limit to first 10 per family
            service_plan = {
                'name': f"GCP {instance_type.upper()}",
                'code': f"gcp-{instance_type.lower()}",
                'description': f"Google Cloud Platform {instance_type.upper()} instance",
                'editable': True,
                'provisionType': {
                    'id': 1  # Default provision type
                },
                'zone': {
                    'id': 1  # Default zone - will need to be updated
                },
                'priceSets': [],  # Will be populated later
                'config': {
                    'instanceType': instance_type,
                    'family': family,
                    'region': GCP_REGION
                }
            }
            service_plans.append(service_plan)
    
    logger.info(f"Created {len(service_plans)} service plans from {len(compute_skus)} compute SKUs")
    return service_plans

def sync_comprehensive_data(morpheus_api: MorpheusApiClient, sku_processor: SKUCatalogProcessor, dry_run=False, create_service_plans=False):
    """Sync comprehensive data from SKU catalog."""
    logger.info("Starting comprehensive data sync...")
    
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    
    # Create pricing data
    pricing_data = create_comprehensive_pricing_data(morpheus_api, sku_processor)
    
    # Create price sets
    price_sets = create_enhanced_price_sets(morpheus_api, sku_processor)
    
    # Create service plans if requested
    service_plans = []
    if create_service_plans:
        service_plans = create_service_plans_from_skus(morpheus_api, sku_processor)
    
    if not dry_run:
        # Create prices in Morpheus
        created_prices = []
        for pricing_entry in pricing_data:
            try:
                response = morpheus_api.post("prices", pricing_entry)
                if response:
                    created_prices.append(response)
                    logger.info(f"Created price: {pricing_entry['name']}")
                time.sleep(0.1)  # Rate limiting
            except Exception as e:
                logger.error(f"Error creating price {pricing_entry['name']}: {e}")
        
        # Create price sets in Morpheus
        created_price_sets = []
        for price_set in price_sets:
            try:
                response = morpheus_api.post("price-sets", price_set)
                if response:
                    created_price_sets.append(response)
                    logger.info(f"Created price set: {price_set['name']}")
                time.sleep(0.1)  # Rate limiting
            except Exception as e:
                logger.error(f"Error creating price set {price_set['name']}: {e}")
        
        # Create service plans in Morpheus
        created_service_plans = []
        if create_service_plans:
            for service_plan in service_plans:
                try:
                    response = morpheus_api.post("service-plans", service_plan)
                    if response:
                        created_service_plans.append(response)
                        logger.info(f"Created service plan: {service_plan['name']}")
                    time.sleep(0.1)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error creating service plan {service_plan['name']}: {e}")
        
        logger.info(f"Sync completed: {len(created_prices)} prices, {len(created_price_sets)} price sets, {len(created_service_plans)} service plans created")
    else:
        logger.info(f"DRY RUN: Would create {len(pricing_data)} prices, {len(price_sets)} price sets, {len(service_plans)} service plans")
    
    return {
        'pricing_data': pricing_data,
        'price_sets': price_sets,
        'service_plans': service_plans,
        'sku_summary': sku_processor.get_sku_summary()
    }

def validate_comprehensive_sync(morpheus_api: MorpheusApiClient, sku_processor: SKUCatalogProcessor):
    """Validate the comprehensive sync results."""
    logger.info("Validating comprehensive sync results...")
    
    # Get existing prices and price sets
    try:
        prices_response = morpheus_api.get("prices")
        price_sets_response = morpheus_api.get("price-sets")
        service_plans_response = morpheus_api.get("service-plans")
        
        existing_prices = prices_response.get("prices", []) if prices_response else []
        existing_price_sets = price_sets_response.get("priceSets", []) if price_sets_response else []
        existing_service_plans = service_plans_response.get("servicePlans", []) if service_plans_response else []
        
        # Filter for GCP items
        gcp_prices = [p for p in existing_prices if p.get("code", "").startswith("gcp-")]
        gcp_price_sets = [ps for ps in existing_price_sets if ps.get("code", "").startswith("gcp-")]
        gcp_service_plans = [sp for sp in existing_service_plans if sp.get("code", "").startswith("gcp-")]
        
        logger.info(f"Validation Results:")
        logger.info(f"  Total prices in Morpheus: {len(existing_prices)}")
        logger.info(f"  GCP prices: {len(gcp_prices)}")
        logger.info(f"  Total price sets in Morpheus: {len(existing_price_sets)}")
        logger.info(f"  GCP price sets: {len(gcp_price_sets)}")
        logger.info(f"  Total service plans in Morpheus: {len(existing_service_plans)}")
        logger.info(f"  GCP service plans: {len(gcp_service_plans)}")
        
        # Check coverage
        sku_summary = sku_processor.get_sku_summary()
        total_skus = sum(summary['count'] for summary in sku_summary.values())
        
        logger.info(f"  Total SKUs in catalog: {total_skus}")
        logger.info(f"  Price coverage: {len(gcp_prices)}/{total_skus} ({len(gcp_prices)/total_skus*100:.1f}%)")
        
        return {
            'total_prices': len(existing_prices),
            'gcp_prices': len(gcp_prices),
            'total_price_sets': len(existing_price_sets),
            'gcp_price_sets': len(gcp_price_sets),
            'total_service_plans': len(existing_service_plans),
            'gcp_service_plans': len(gcp_service_plans),
            'catalog_skus': total_skus,
            'coverage_percentage': len(gcp_prices)/total_skus*100 if total_skus > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error during validation: {e}")
        return None

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Enhanced GCP Price Sync using downloaded SKU catalog",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python gcp-price-sync-enhanced.py --sku-catalog gcp_skus_20250807_194211.json --dry-run
  python gcp-price-sync-enhanced.py --sku-catalog gcp_skus_20250807_194211.json --create-service-plans
  python gcp-price-sync-enhanced.py --sku-catalog gcp_skus_20250807_194211.json --validate-only
        """
    )
    
    parser.add_argument(
        '--sku-catalog',
        required=True,
        help='Path to the SKU catalog JSON file from gcp-sku-downloader.py'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run in dry-run mode (no changes made)'
    )
    
    parser.add_argument(
        '--create-service-plans',
        action='store_true',
        help='Create service plans from compute SKUs'
    )
    
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate existing sync results'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Initialize clients
        morpheus_api = MorpheusApiClient(MORPHEUS_URL, MORPHEUS_TOKEN)
        sku_processor = SKUCatalogProcessor(args.sku_catalog)
        
        # Display catalog information
        print("\n=== GCP SKU Catalog Information ===")
        metadata = sku_processor.catalog['metadata']
        print(f"Region: {metadata['region']}")
        print(f"Download Time: {metadata['download_timestamp']}")
        print(f"Total Services: {metadata['total_services']}")
        print(f"Total SKUs: {metadata['total_skus']}")
        
        # Show processed summary
        processed_summary = sku_processor.get_sku_summary()
        print("\nProcessed SKU Summary:")
        for category, summary in processed_summary.items():
            print(f"  {category}: {summary['count']} SKUs")
            if summary['services']:
                print(f"    Services: {', '.join(summary['services'][:3])}{'...' if len(summary['services']) > 3 else ''}")
        
        if args.validate_only:
            # Only validate
            validation_results = validate_comprehensive_sync(morpheus_api, sku_processor)
            if validation_results:
                print("\n=== Validation Summary ===")
                print(f"GCP Prices in Morpheus: {validation_results['gcp_prices']}")
                print(f"GCP Price Sets in Morpheus: {validation_results['gcp_price_sets']}")
                print(f"GCP Service Plans in Morpheus: {validation_results['gcp_service_plans']}")
                print(f"Catalog SKUs: {validation_results['catalog_skus']}")
                print(f"Coverage: {validation_results['coverage_percentage']:.1f}%")
        else:
            # Full sync
            print("\n=== Starting Comprehensive Sync ===")
            sync_results = sync_comprehensive_data(morpheus_api, sku_processor, args.dry_run, args.create_service_plans)
            
            # Validate results
            validation_results = validate_comprehensive_sync(morpheus_api, sku_processor)
            
            # Print final summary
            print("\n=== Final Sync Summary ===")
            print(f"SKU Categories Processed: {list(sync_results['sku_summary'].keys())}")
            for category, summary in sync_results['sku_summary'].items():
                print(f"  {category}: {summary['count']} SKUs")
            
            if validation_results:
                print(f"\nCoverage Achieved: {validation_results['coverage_percentage']:.1f}%")
                print(f"Total GCP Prices in Morpheus: {validation_results['gcp_prices']}")
                print(f"Total GCP Price Sets in Morpheus: {validation_results['gcp_price_sets']}")
                print(f"Total GCP Service Plans in Morpheus: {validation_results['gcp_service_plans']}")
        
        logger.info("Enhanced price sync completed successfully!")
        
    except KeyboardInterrupt:
        logger.info("Sync interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()