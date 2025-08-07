#!/usr/bin/env python3
"""
GCP SKU Downloader - Comprehensive SKU Catalog Fetcher

This script downloads the complete GCP SKU catalog for a specified region
and organizes it by service, making it easy to analyze and use for pricing sync.

Features:
- Downloads all available services and their SKUs
- Organizes data by service category and SKU type
- Handles authentication via gcloud CLI
- Provides detailed logging and progress tracking
- Saves data in structured JSON format
- Includes metadata for analysis

Usage:
    python gcp-sku-downloader.py --region us-central1
    python gcp-sku-downloader.py --region asia-southeast2 --output skus_asia.json
"""

import requests
import json
import logging
import time
import urllib3
import argparse
import os
import subprocess
import sys
from datetime import datetime
from collections import defaultdict
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Global logger variable
logger = None

class GCPBillingCatalogClient:
    """Client for fetching complete SKU data from GCP Billing Catalog API."""
    
    API_BASE = "https://cloudbilling.googleapis.com"
    
    def __init__(self, region, max_retries=5, backoff_factor=2):
        self.region = region
        self.session = requests.Session()
        
        # Setup retry strategy
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Get access token
        self.access_token = self._get_access_token()
        self.session.headers.update({
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        })
        
        if logger:
            logger.info(f"Initialized GCP Billing Catalog client for region: {self.region}")

    def _get_access_token(self):
        """Get access token from gcloud CLI."""
        try:
            if logger:
                logger.info("Fetching GCP access token from gcloud CLI...")
            env = os.environ.copy()
            
            # Handle service account credentials if present
            if "GOOGLE_APPLICATION_CREDENTIALS" in env and os.path.exists(env["GOOGLE_APPLICATION_CREDENTIALS"]):
                if logger:
                    logger.info(f"Using service account from GOOGLE_APPLICATION_CREDENTIALS")
                env["CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"] = env["GOOGLE_APPLICATION_CREDENTIALS"]
            
            result = subprocess.run(
                ["gcloud", "auth", "print-access-token"],
                capture_output=True,
                text=True,
                check=True,
                env=env
            )
            
            token = result.stdout.strip()
            if not token:
                raise ValueError("Empty access token received from gcloud")
            
            if logger:
                logger.info("Successfully obtained GCP access token")
            return token
            
        except subprocess.CalledProcessError as e:
            if logger:
                logger.error(f"Failed to get access token from gcloud: {e}")
                logger.error(f"stderr: {e.stderr}")
            raise
        except Exception as e:
            if logger:
                logger.error(f"Unexpected error getting access token: {e}")
            raise

    def _make_request(self, endpoint, params=None):
        """Make authenticated request to GCP API."""
        url = f"{self.API_BASE}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if logger:
                logger.error(f"API request failed for {endpoint}: {e}")
            raise

    def get_all_services(self):
        """Get all available billing services."""
        if logger:
            logger.info("Fetching all available billing services...")
        services = []
        page_token = None
        
        while True:
            params = {'pageSize': 100}
            if page_token:
                params['pageToken'] = page_token
            
            try:
                data = self._make_request('/v1/services', params)
                services.extend(data.get('services', []))
                
                page_token = data.get('nextPageToken')
                if not page_token:
                    break
                    
                if logger:
                    logger.info(f"Fetched {len(services)} services so far...")
                time.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                if logger:
                    logger.error(f"Error fetching services: {e}")
                break
        
        if logger:
            logger.info(f"Total services found: {len(services)}")
        return services

    def get_service_skus(self, service_id):
        """Get all SKUs for a specific service."""
        if logger:
            logger.info(f"Fetching SKUs for service: {service_id}")
        skus = []
        page_token = None
        
        while True:
            params = {
                'pageSize': 100,
                'filter': f'serviceRegions:{self.region}'
            }
            if page_token:
                params['pageToken'] = page_token
            
            try:
                data = self._make_request(f'/v1/services/{service_id}/skus', params)
                service_skus = data.get('skus', [])
                skus.extend(service_skus)
                
                page_token = data.get('nextPageToken')
                if not page_token:
                    break
                    
                if logger:
                    logger.info(f"Fetched {len(skus)} SKUs for {service_id} so far...")
                time.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                if logger:
                    logger.error(f"Error fetching SKUs for {service_id}: {e}")
                break
        
        if logger:
            logger.info(f"Total SKUs for {service_id}: {len(skus)}")
        return skus

    def download_complete_catalog(self):
        """Download the complete SKU catalog for the region."""
        if logger:
            logger.info(f"Starting complete SKU catalog download for region: {self.region}")
        
        # Get all services
        services = self.get_all_services()
        
        # Organize data
        catalog = {
            'metadata': {
                'region': self.region,
                'download_timestamp': datetime.now().isoformat(),
                'total_services': len(services),
                'total_skus': 0
            },
            'services': {},
            'sku_summary': defaultdict(int),
            'category_summary': defaultdict(int)
        }
        
        # Process each service
        for i, service in enumerate(services, 1):
            service_id = service['serviceId']
            service_name = service.get('displayName', service_id)
            
            if logger:
                logger.info(f"Processing service {i}/{len(services)}: {service_name} ({service_id})")
            
            try:
                skus = self.get_service_skus(service_id)
                
                if skus:
                    # Organize SKUs by category
                    service_data = {
                        'service_info': {
                            'service_id': service_id,
                            'display_name': service_name,
                            'business_entity_name': service.get('businessEntityName', ''),
                            'sku_count': len(skus)
                        },
                        'skus': skus,
                        'categories': defaultdict(list)
                    }
                    
                    # Categorize SKUs
                    for sku in skus:
                        category = sku.get('category', {}).get('resourceFamily', 'Unknown')
                        service_data['categories'][category].append(sku)
                        catalog['sku_summary'][category] += 1
                        catalog['category_summary'][category] += 1
                    
                    catalog['services'][service_id] = service_data
                    catalog['metadata']['total_skus'] += len(skus)
                    
                    if logger:
                        logger.info(f"  Added {len(skus)} SKUs for {service_name}")
                else:
                    if logger:
                        logger.info(f"  No SKUs found for {service_name}")
                
            except Exception as e:
                if logger:
                    logger.error(f"Error processing service {service_id}: {e}")
                continue
            
            # Rate limiting between services
            time.sleep(0.2)
        
        # Convert defaultdict to regular dict for JSON serialization
        catalog['sku_summary'] = dict(catalog['sku_summary'])
        catalog['category_summary'] = dict(catalog['category_summary'])
        
        for service_id in catalog['services']:
            catalog['services'][service_id]['categories'] = dict(
                catalog['services'][service_id]['categories']
            )
        
        if logger:
            logger.info(f"Download complete! Total SKUs: {catalog['metadata']['total_skus']}")
        return catalog

def setup_logging(verbose=False):
    """Setup logging configuration."""
    global logger
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('gcp-sku-download.log')
        ]
    )
    logger = logging.getLogger(__name__)

def save_catalog(catalog, output_file):
    """Save catalog to JSON file."""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
        if logger:
            logger.info(f"Catalog saved to: {output_file}")
        
        # Also save a summary
        summary_file = output_file.replace('.json', '_summary.json')
        summary = {
            'metadata': catalog['metadata'],
            'sku_summary': catalog['sku_summary'],
            'category_summary': catalog['category_summary'],
            'services_summary': {
                service_id: {
                    'display_name': data['service_info']['display_name'],
                    'sku_count': data['service_info']['sku_count']
                }
                for service_id, data in catalog['services'].items()
            }
        }
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        if logger:
            logger.info(f"Summary saved to: {summary_file}")
        
    except Exception as e:
        if logger:
            logger.error(f"Error saving catalog: {e}")
        raise

def print_summary(catalog):
    """Print a summary of the downloaded catalog."""
    print("\n" + "="*60)
    print("GCP SKU CATALOG DOWNLOAD SUMMARY")
    print("="*60)
    print(f"Region: {catalog['metadata']['region']}")
    print(f"Download Time: {catalog['metadata']['download_timestamp']}")
    print(f"Total Services: {catalog['metadata']['total_services']}")
    print(f"Total SKUs: {catalog['metadata']['total_skus']}")
    
    print("\nTop SKU Categories:")
    sorted_categories = sorted(
        catalog['sku_summary'].items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]
    
    for category, count in sorted_categories:
        print(f"  {category}: {count} SKUs")
    
    print("\nServices with most SKUs:")
    service_counts = [
        (data['service_info']['display_name'], data['service_info']['sku_count'])
        for data in catalog['services'].values()
    ]
    service_counts.sort(key=lambda x: x[1], reverse=True)
    
    for service_name, count in service_counts[:10]:
        print(f"  {service_name}: {count} SKUs")
    
    print("="*60)

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Download complete GCP SKU catalog for a region",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python gcp-sku-downloader.py --region us-central1
  python gcp-sku-downloader.py --region asia-southeast2 --output skus_asia.json
  python gcp-sku-downloader.py --region europe-west1 --verbose
        """
    )
    
    parser.add_argument(
        '--region',
        required=True,
        help='GCP region (e.g., us-central1, asia-southeast2)'
    )
    
    parser.add_argument(
        '--output',
        default=f'gcp_skus_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
        help='Output JSON file path (default: auto-generated)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    try:
        # Initialize client
        client = GCPBillingCatalogClient(args.region)
        
        # Download catalog
        catalog = client.download_complete_catalog()
        
        # Save catalog
        save_catalog(catalog, args.output)
        
        # Print summary
        print_summary(catalog)
        
        if logger:
            logger.info("SKU catalog download completed successfully!")
        
    except KeyboardInterrupt:
        if logger:
            logger.info("Download interrupted by user")
        sys.exit(1)
    except Exception as e:
        if logger:
            logger.error(f"Download failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()