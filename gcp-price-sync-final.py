#!/usr/bin/env python3
"""
GCP Price Sync - Final Unified Script

This consolidated script uses the comprehensive SKU catalog produced by gcp-sku-downloader.py
to discover existing GCP service plans and create comprehensive prices and price sets in Morpheus.
Optionally, it can also create service plans based on Compute Engine SKUs.

Features:
- Uses downloaded SKU catalog (full catalog JSON from gcp-sku-downloader.py)
- Discovers existing GCP service plans in Morpheus
- Creates comprehensive Prices from SKUs (with units and costs)
- Creates Price Sets by category and a comprehensive set
- Optionally creates Service Plans based on compute instance families/types
- Dry-run and validation modes with concise summaries

Usage:
  python gcp-price-sync-final.py --sku-catalog gcp_skus_YYYYMMDD_HHMMSS.json --dry-run
  python gcp-price-sync-final.py --sku-catalog gcp_skus_YYYYMMDD_HHMMSS.json --create-service-plans
  python gcp-price-sync-final.py --sku-catalog gcp_skus_YYYYMMDD_HHMMSS.json --validate-only
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime

import requests
import urllib3
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

    def __init__(self, base_url: str, api_token: str, max_retries: int = 5, backoff_factor: float = 2,
                 status_forcelist=(429, 500, 502, 503, 504)):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Authorization": f"BEARER {api_token}",
            "Content-Type": "application/json",
        }
        self.session = requests.Session()
        retry_strategy = Retry(total=max_retries, backoff_factor=backoff_factor,
                               status_forcelist=list(status_forcelist))
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _request(self, method: str, endpoint: str, payload=None, params=None):
        url = f"{self.base_url}/api/{endpoint}"
        try:
            response = self.session.request(method, url, json=payload, headers=self.headers,
                                             params=params, verify=False)
            response.raise_for_status()
            return response.json() if response.content else None
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection Error: Cannot connect to Morpheus server at {self.base_url}")
            logger.error("Please verify Morpheus availability, URL correctness, and network connectivity.")
            raise
        except requests.exceptions.HTTPError as e:
            if response.status_code != 404:
                logger.error(f"HTTP Error for {method.upper()} {endpoint}: "
                             f"{e.response.status_code} - {e.response.text}")
                try:
                    error_detail = e.response.json()
                    logger.error(f"Error details: {json.dumps(error_detail, indent=2)}")
                except Exception:
                    logger.error(f"Raw error response: {e.response.text}")
                raise
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"An unexpected request error occurred: {e}")
            raise

    def get(self, endpoint: str, params=None):
        return self._request('get', endpoint, params=params)

    def post(self, endpoint: str, payload):
        return self._request('post', endpoint, payload=payload)

    def put(self, endpoint: str, payload):
        return self._request('put', endpoint, payload=payload)


class SKUCatalogProcessor:
    """Process and analyze the comprehensive SKU catalog (full catalog from downloader)."""

    def __init__(self, catalog_file: str):
        self.catalog_file = catalog_file
        self.catalog = self._load_catalog()
        self.processed_skus = self._process_skus()
        self.compute_skus = self._extract_compute_skus()

    def _load_catalog(self):
        """Load the SKU catalog from file. Requires full catalog with 'services'."""
        try:
            with open(self.catalog_file, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
            if 'services' not in catalog:
                raise ValueError("SKU catalog must be the full output from gcp-sku-downloader.py (missing 'services').")
            meta = catalog.get('metadata', {})
            logger.info(f"Loaded SKU catalog: {meta.get('total_services', '?')} services, "
                        f"{meta.get('total_skus', '?')} SKUs")
            return catalog
        except Exception as e:
            logger.error(f"Error loading SKU catalog: {e}")
            raise

    def _process_skus(self):
        """Process and normalize SKUs for pricing sync grouped by broad categories."""
        processed = {
            'compute': [],
            'storage': [],
            'network': [],
            'database': [],
            'ai_ml': [],
            'other': [],
        }
        for service_id, service_data in self.catalog['services'].items():
            service_name = service_data['service_info']['display_name']
            for sku in service_data.get('skus', []):
                normalized_sku = self._normalize_sku(sku, service_name, service_id)
                if normalized_sku:
                    category_key = self._categorize_sku(normalized_sku)
                    processed[category_key].append(normalized_sku)
        for category, skus in processed.items():
            logger.info(f"Processed {len(skus)} {category} SKUs")
        return processed

    def _normalize_sku(self, sku: dict, service_name: str, service_id: str):
        """Normalize SKU data for pricing sync."""
        try:
            pricing_info = sku.get('pricingInfo', [])
            if not pricing_info:
                return None
            tiered_rates = pricing_info[0].get('pricingExpression', {}).get('tieredRates', [])
            if not tiered_rates:
                return None
            rate = tiered_rates[0].get('unitPrice', {})
            if not rate:
                return None
            pricing_unit = pricing_info[0].get('pricingExpression', {}).get('usageUnit', 'hour')
            normalized = {
                'sku_id': sku.get('skuId', ''),
                'description': sku.get('description', ''),
                'service_name': service_name,
                'service_id': service_id,
                'category': sku.get('category', {}),
                'pricing_unit': pricing_unit,
                'rate': rate,
                'tiered_rates': tiered_rates,
                'pricing_info': pricing_info,
                'original_sku': sku,
            }
            return normalized
        except Exception as e:
            logger.warning(f"Error normalizing SKU {sku.get('skuId', 'unknown')}: {e}")
            return None

    def _categorize_sku(self, sku: dict) -> str:
        service_name = sku['service_name'].lower()
        description = sku['description'].lower()
        category = sku['category']
        resource_family = category.get('resourceFamily', '').lower()
        if resource_family == 'storage':
            return 'storage'
        if resource_family == 'compute':
            return 'compute'
        if resource_family == 'network':
            return 'network'
        if resource_family == 'database':
            return 'database'
        if resource_family in ['ai/ml', 'ai', 'ml']:
            return 'ai_ml'
        if any(k in service_name for k in ['storage', 'cloud storage', 'filestore', 'memorystore']):
            return 'storage'
        if any(k in service_name for k in ['compute', 'vm', 'instance', 'gke', 'kubernetes', 'run', 'functions']):
            return 'compute'
        if any(k in service_name for k in ['network', 'vpc', 'load balancer', 'cdn', 'gateway']):
            return 'network'
        if any(k in service_name for k in ['sql', 'database', 'firestore', 'bigtable', 'spanner', 'alloydb']):
            return 'database'
        if any(k in service_name for k in ['ai', 'ml', 'vertex', 'notebooks', 'composer', 'dataflow']):
            return 'ai_ml'
        if any(k in description for k in ['storage', 'gb', 'tb']):
            return 'storage'
        if any(k in description for k in ['cpu', 'ram', 'memory', 'core']):
            return 'compute'
        if any(k in description for k in ['network', 'bandwidth', 'transfer']):
            return 'network'
        if any(k in description for k in ['database', 'sql', 'query']):
            return 'database'
        if any(k in description for k in ['ai', 'ml', 'machine learning', 'tensorflow']):
            return 'ai_ml'
        return 'other'

    def _extract_compute_skus(self):
        """Extract compute SKUs for service plan creation (instance families/types)."""
        compute_skus: list[dict] = []
        for service_id, service_data in self.catalog['services'].items():
            if service_data['service_info']['display_name'] == 'Compute Engine':
                for sku in service_data.get('skus', []):
                    description = sku.get('description', '').lower()
                    sku_id = sku.get('skuId', '')
                    instance_patterns = [
                        r'(\w+\d+[a-z]?-\w+-\d+)',  # e2-standard-2, n2-standard-4
                        r'(\w+\d+[a-z]?-\w+)',      # e2-standard, n2-standard
                        r'(\w+\d+[a-z]?-\d+)',      # e2-2, n2-4
                    ]
                    matched = False
                    for pattern in instance_patterns:
                        matches = re.findall(pattern, description)
                        if matches:
                            for match in matches:
                                compute_skus.append({
                                    'instance_type': match,
                                    'sku_id': sku_id,
                                    'description': sku.get('description', ''),
                                    'pricing_info': sku.get('pricingInfo', []),
                                    'original_sku': sku,
                                })
                                matched = True
                                break
                        if matched:
                            break
                    if not matched:
                        compute_skus.append({
                            'instance_type': 'general',
                            'sku_id': sku_id,
                            'description': sku.get('description', ''),
                            'pricing_info': sku.get('pricingInfo', []),
                            'original_sku': sku,
                        })
        logger.info(f"Extracted {len(compute_skus)} compute SKUs for service plan creation")
        return compute_skus

    def get_sku_summary(self):
        summary = {}
        for category, skus in self.processed_skus.items():
            summary[category] = {
                'count': len(skus),
                'services': list(set(sku['service_name'] for sku in skus)),
            }
        return summary

    def get_all_skus(self):
        all_skus = []
        for category_skus in self.processed_skus.values():
            all_skus.extend(category_skus)
        return all_skus


def discover_morpheus_plans(morpheus_api: MorpheusApiClient):
    """Discover existing plans in Morpheus (filters for GCP)."""
    logger.info("Discovering existing Morpheus plans...")
    try:
        plans_response = morpheus_api.get("plans")
        if not plans_response:
            logger.warning("No plans found or unable to fetch plans")
            return []
        plans = plans_response.get("plans", [])
        gcp_plans = []
        for plan in plans:
            if plan.get("zone", {}).get("cloud", {}).get("type") == "gcp":
                gcp_plans.append(plan)
        logger.info(f"Found {len(gcp_plans)} GCP plans (of {len(plans)} total)")
        return gcp_plans
    except Exception as e:
        logger.error(f"Error discovering plans: {e}")
        return []


def create_comprehensive_pricing_data(sku_processor: SKUCatalogProcessor):
    """Create comprehensive pricing entries from SKU catalog."""
    logger.info("Creating comprehensive pricing data from SKU catalog...")
    all_skus = sku_processor.get_all_skus()
    logger.info(f"Processing {len(all_skus)} SKUs for pricing data creation")
    pricing_data = []
    for sku in all_skus:
        try:
            pricing_entry = {
                'name': f"{PRICE_PREFIX}-{sku['sku_id']}",
                'code': f"gcp-{sku['sku_id']}",
                'priceType': 'fixed',
                'priceUnit': sku['pricing_unit'],
                'price': 0.0,
                'markupType': 'fixed',
                'markup': 0,
                'markupPercent': 0,
                'cost': 0.0,
                'currency': 'USD',
                'refType': 'ComputeZone',
                'refId': None,
                'volumeType': None,
                'datastore': None,
                'crossCloudApply': False,
                'sku': sku['sku_id'],
                'sku_description': sku['description'],
                'service_name': sku['service_name'],
                'service_id': sku['service_id'],
                'category': sku['category'],
            }
            rate = sku['rate']
            if 'units' in rate and 'nanos' in rate:
                units_val = int(rate.get('units') or 0)
                nanos_val = int(rate.get('nanos') or 0)
                price = units_val + nanos_val / 1_000_000_000
                pricing_entry['price'] = price
                pricing_entry['cost'] = price
            pricing_data.append(pricing_entry)
        except Exception as e:
            logger.warning(f"Error processing SKU {sku.get('sku_id', 'unknown')} for pricing: {e}")
            continue
    logger.info(f"Created {len(pricing_data)} pricing entries")
    return pricing_data


def create_enhanced_price_sets(sku_processor: SKUCatalogProcessor):
    """Create enhanced price sets grouped by category plus a comprehensive set."""
    logger.info("Creating enhanced price sets...")
    sku_summary = sku_processor.get_sku_summary()
    price_sets = []
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
                'services': summary['services'],
            }
            price_sets.append(price_set)
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
        'services': list(set(service for summary in sku_summary.values() for service in summary['services'])),
    }
    price_sets.append(comprehensive_set)
    logger.info(f"Created {len(price_sets)} price sets")
    return price_sets


def create_service_plans_from_skus(sku_processor: SKUCatalogProcessor):
    """Create service plans based on compute instance families/types (optional)."""
    logger.info("Creating service plans from compute SKUs...")
    compute_skus = sku_processor.compute_skus
    if not compute_skus:
        logger.warning("No compute SKUs found for service plan creation")
        return []
    instance_families: dict[str, list] = defaultdict(list)
    for sku in compute_skus:
        instance_type = sku['instance_type']
        if instance_type != 'general':
            family_match = re.match(r'(\w+\d+[a-z]?)', instance_type)
            if family_match:
                family = family_match.group(1)
                instance_families[family].append(sku)
    service_plans = []
    for family, skus in instance_families.items():
        instance_types = list(set(sku['instance_type'] for sku in skus))
        for instance_type in instance_types[:10]:  # Limit to first 10 per family
            service_plan = {
                'name': f"GCP {instance_type.upper()}",
                'code': f"gcp-{instance_type.lower()}",
                'description': f"Google Cloud Platform {instance_type.upper()} instance",
                'editable': True,
                'provisionType': {'id': 1},
                'zone': {'id': 1},  # Adjust to your Morpheus zone
                'priceSets': [],
                'config': {
                    'instanceType': instance_type,
                    'family': family,
                    'region': GCP_REGION,
                },
            }
            service_plans.append(service_plan)
    logger.info(f"Created {len(service_plans)} service plans from {len(compute_skus)} compute SKUs")
    return service_plans


def sync_data(morpheus_api: MorpheusApiClient, sku_processor: SKUCatalogProcessor,
              dry_run: bool = False, create_service_plans: bool = False):
    """Sync prices and price sets (and optionally service plans) into Morpheus."""
    logger.info("Starting sync from SKU catalog...")
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    pricing_data = create_comprehensive_pricing_data(sku_processor)
    price_sets = create_enhanced_price_sets(sku_processor)
    service_plans = create_service_plans_from_skus(sku_processor) if create_service_plans else []
    if not dry_run:
        created_prices = []
        for pricing_entry in pricing_data:
            try:
                response = morpheus_api.post("prices", pricing_entry)
                if response:
                    created_prices.append(response)
                    logger.info(f"Created price: {pricing_entry['name']}")
                time.sleep(0.05)
            except Exception as e:
                logger.error(f"Error creating price {pricing_entry['name']}: {e}")
        created_price_sets = []
        for price_set in price_sets:
            try:
                response = morpheus_api.post("price-sets", price_set)
                if response:
                    created_price_sets.append(response)
                    logger.info(f"Created price set: {price_set['name']}")
                time.sleep(0.05)
            except Exception as e:
                logger.error(f"Error creating price set {price_set['name']}: {e}")
        created_service_plans = []
        if create_service_plans:
            for service_plan in service_plans:
                try:
                    response = morpheus_api.post("service-plans", service_plan)
                    if response:
                        created_service_plans.append(response)
                        logger.info(f"Created service plan: {service_plan['name']}")
                    time.sleep(0.05)
                except Exception as e:
                    logger.error(f"Error creating service plan {service_plan['name']}: {e}")
        logger.info(
            f"Sync completed: {len(created_prices)} prices, {len(created_price_sets)} price sets, "
            f"{len(created_service_plans)} service plans created"
        )
    else:
        logger.info(
            f"DRY RUN: Would create {len(pricing_data)} prices, {len(price_sets)} price sets, "
            f"{len(service_plans)} service plans"
        )
    return {
        'pricing_data': pricing_data,
        'price_sets': price_sets,
        'service_plans': service_plans,
        'sku_summary': sku_processor.get_sku_summary(),
    }


def validate_sync(morpheus_api: MorpheusApiClient, sku_processor: SKUCatalogProcessor):
    """Validate existing prices/price sets against catalog size and provide coverage."""
    logger.info("Validating sync results in Morpheus...")
    try:
        prices_response = morpheus_api.get("prices")
        price_sets_response = morpheus_api.get("price-sets")
        service_plans_response = morpheus_api.get("service-plans")
        existing_prices = prices_response.get("prices", []) if prices_response else []
        existing_price_sets = price_sets_response.get("priceSets", []) if price_sets_response else []
        existing_service_plans = service_plans_response.get("servicePlans", []) if service_plans_response else []
        gcp_prices = [p for p in existing_prices if p.get("code", "").startswith("gcp-")]
        gcp_price_sets = [ps for ps in existing_price_sets if ps.get("code", "").startswith("gcp-")]
        gcp_service_plans = [sp for sp in existing_service_plans if sp.get("code", "").startswith("gcp-")]
        sku_summary = sku_processor.get_sku_summary()
        total_skus = sum(summary['count'] for summary in sku_summary.values())
        coverage = (len(gcp_prices) / total_skus * 100) if total_skus > 0 else 0
        logger.info("Validation Results:")
        logger.info(f"  Total prices in Morpheus: {len(existing_prices)} (GCP: {len(gcp_prices)})")
        logger.info(f"  Total price sets in Morpheus: {len(existing_price_sets)} (GCP: {len(gcp_price_sets)})")
        logger.info(f"  Total service plans in Morpheus: {len(existing_service_plans)} (GCP: {len(gcp_service_plans)})")
        logger.info(f"  Total SKUs in catalog: {total_skus}")
        logger.info(f"  Price coverage: {len(gcp_prices)}/{total_skus} ({coverage:.1f}%)")
        return {
            'total_prices': len(existing_prices),
            'gcp_prices': len(gcp_prices),
            'total_price_sets': len(existing_price_sets),
            'gcp_price_sets': len(gcp_price_sets),
            'total_service_plans': len(existing_service_plans),
            'gcp_service_plans': len(gcp_service_plans),
            'catalog_skus': total_skus,
            'coverage_percentage': coverage,
        }
    except Exception as e:
        logger.error(f"Error during validation: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Final unified GCP price sync using downloaded SKU catalog",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python gcp-price-sync-final.py --sku-catalog gcp_skus_YYYYMMDD_HHMMSS.json --dry-run\n"
            "  python gcp-price-sync-final.py --sku-catalog gcp_skus_YYYYMMDD_HHMMSS.json --create-service-plans\n"
            "  python gcp-price-sync-final.py --sku-catalog gcp_skus_YYYYMMDD_HHMMSS.json --validate-only\n"
        ),
    )
    parser.add_argument('--sku-catalog', required=True,
                        help='Path to the full SKU catalog JSON (output of gcp-sku-downloader.py)')
    parser.add_argument('--dry-run', action='store_true', help='Run in dry-run mode (no changes made)')
    parser.add_argument('--create-service-plans', action='store_true', help='Create service plans from compute SKUs')
    parser.add_argument('--validate-only', action='store_true', help='Only validate existing sync results')
    parser.add_argument('--create-prices', action='store_true', help='Create prices from SKU catalog')
    parser.add_argument('--create-price-sets', action='store_true', help='Create price sets from SKU catalog summary')
    parser.add_argument('--map-to-plans', action='store_true', help='Map created price sets to discovered GCP service plans')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        morpheus_api = MorpheusApiClient(MORPHEUS_URL, MORPHEUS_TOKEN)
        sku_processor = SKUCatalogProcessor(args.sku_catalog)

        # Discover existing GCP service plans up front (to scope actions)
        discovered_plans = discover_morpheus_plans(morpheus_api)
        if not discovered_plans:
            logger.warning("No GCP service plans discovered in Morpheus. Creation steps will be skipped.")
            if args.validate_only:
                pass
            else:
                print("\nNo GCP service plans found. Use Morpheus to create or import plans, then re-run.")
                # Still allow dry-run preview of counts

        print("\n=== GCP SKU Catalog Information ===")
        metadata = sku_processor.catalog.get('metadata', {})
        print(f"Region: {metadata.get('region')}")
        print(f"Download Time: {metadata.get('download_timestamp')}")
        print(f"Total Services: {metadata.get('total_services')}")
        print(f"Total SKUs: {metadata.get('total_skus')}")

        processed_summary = sku_processor.get_sku_summary()
        print("\nProcessed SKU Summary:")
        for category, summary in processed_summary.items():
            services_display = ', '.join(summary['services'][:3])
            ellipsis = '...' if len(summary['services']) > 3 else ''
            print(f"  {category}: {summary['count']} SKUs")
            if summary['services']:
                print(f"    Services: {services_display}{ellipsis}")

        if args.validate_only:
            results = validate_sync(morpheus_api, sku_processor)
            if results:
                print("\n=== Validation Summary ===")
                print(f"GCP Prices in Morpheus: {results['gcp_prices']}")
                print(f"GCP Price Sets in Morpheus: {results['gcp_price_sets']}")
                print(f"GCP Service Plans in Morpheus: {results['gcp_service_plans']}")
                print(f"Catalog SKUs: {results['catalog_skus']}")
                print(f"Coverage: {results['coverage_percentage']:.1f}%")
        else:
            print("\n=== Starting Sync ===")

            # Decide what to create based on flags; default is to create both if neither is specified
            create_prices_flag = args.create_prices or (not args.create_prices and not args.create_price_sets)
            create_price_sets_flag = args.create_price_sets or (not args.create_prices and not args.create_price_sets)

            pricing_data = []
            price_sets = []
            service_plans_payloads = []

            if create_prices_flag:
                pricing_data = create_comprehensive_pricing_data(sku_processor)
                if not args.dry_run and discovered_plans:
                    for pricing_entry in pricing_data:
                        try:
                            morpheus_api.post("prices", pricing_entry)
                            logger.info(f"Created price: {pricing_entry['name']}")
                            time.sleep(0.05)
                        except Exception as e:
                            logger.error(f"Error creating price {pricing_entry['name']}: {e}")
                elif args.dry_run:
                    logger.info(f"DRY RUN: Would create {len(pricing_data)} prices")
                else:
                    logger.warning("Skipping price creation as no GCP plans were discovered")

            if create_price_sets_flag:
                price_sets = create_enhanced_price_sets(sku_processor)
                if not args.dry_run and discovered_plans:
                    for price_set in price_sets:
                        try:
                            morpheus_api.post("price-sets", price_set)
                            logger.info(f"Created price set: {price_set['name']}")
                            time.sleep(0.05)
                        except Exception as e:
                            logger.error(f"Error creating price set {price_set['name']}: {e}")
                elif args.dry_run:
                    logger.info(f"DRY RUN: Would create {len(price_sets)} price sets")
                else:
                    logger.warning("Skipping price set creation as no GCP plans were discovered")

            if args.create_service_plans:
                service_plans_payloads = create_service_plans_from_skus(sku_processor)
                if not args.dry_run:
                    for service_plan in service_plans_payloads:
                        try:
                            morpheus_api.post("service-plans", service_plan)
                            logger.info(f"Created service plan: {service_plan['name']}")
                            time.sleep(0.05)
                        except Exception as e:
                            logger.error(f"Error creating service plan {service_plan['name']}: {e}")
                else:
                    logger.info(f"DRY RUN: Would create {len(service_plans_payloads)} service plans")

            # Optionally map created price sets to discovered plans
            if args.map_to_plans and not args.dry_run and discovered_plans:
                try:
                    # Refresh to get IDs
                    ps_resp = morpheus_api.get(f"price-sets?max=1000&phrase={PRICE_PREFIX}")
                    price_sets_list = ps_resp.get('priceSets', []) if ps_resp else []
                    price_set_ids = [ps['id'] for ps in price_sets_list]
                    updated = 0
                    for plan in discovered_plans:
                        current_ids = {ps['id'] for ps in (plan.get('priceSets') or []) if ps and 'id' in ps}
                        final_ids = current_ids.union(price_set_ids)
                        payload = {"servicePlan": {"priceSets": [{"id": pid} for pid in final_ids]}}
                        resp = morpheus_api.put(f"service-plans/{plan['id']}", payload)
                        if resp and (resp.get('success') or resp.get('servicePlan')):
                            updated += 1
                    logger.info(f"Mapped price sets to {updated}/{len(discovered_plans)} plans")
                except Exception as e:
                    logger.error(f"Failed to map price sets to plans: {e}")

            validation_results = validate_sync(morpheus_api, sku_processor)

            print("\n=== Final Sync Summary ===")
            print(f"SKU Categories Processed: {list(processed_summary.keys())}")
            for category, summary in processed_summary.items():
                print(f"  {category}: {summary['count']} SKUs")
            if validation_results:
                print(f"\nCoverage Achieved: {validation_results['coverage_percentage']:.1f}%")
                print(f"Total GCP Prices in Morpheus: {validation_results['gcp_prices']}")
                print(f"Total GCP Price Sets in Morpheus: {validation_results['gcp_price_sets']}")
                print(f"Total GCP Service Plans in Morpheus: {validation_results['gcp_service_plans']}")

        logger.info("Final unified price sync completed successfully!")
    except KeyboardInterrupt:
        logger.info("Sync interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()