#!/usr/bin/env python3
"""
Test Comprehensive GCP Workflow

This script demonstrates the complete workflow:
1. Download SKU catalog (if not exists)
2. Validate the catalog
3. Run enhanced price sync
4. Validate results

Usage:
    python test_comprehensive_workflow.py --region asia-southeast2
    python test_comprehensive_workflow.py --region us-central1 --dry-run
"""

import os
import sys
import json
import argparse
import subprocess
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_command(cmd, description, check=True):
    """Run a command and handle errors."""
    logger.info(f"Running: {description}")
    logger.debug(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check)
        if result.stdout:
            logger.info(f"Output: {result.stdout.strip()}")
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        logger.error(f"stderr: {e.stderr}")
        if check:
            raise
        return e

def check_file_exists(filepath):
    """Check if a file exists and is readable."""
    if os.path.exists(filepath) and os.path.isfile(filepath):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            return True, data
        except Exception as e:
            logger.warning(f"File {filepath} exists but is not valid JSON: {e}")
            return False, None
    return False, None

def validate_sku_catalog(catalog_file):
    """Validate the SKU catalog file."""
    logger.info(f"Validating SKU catalog: {catalog_file}")
    
    exists, data = check_file_exists(catalog_file)
    if not exists:
        return False, "Catalog file does not exist or is invalid"
    
    # Check required fields
    required_fields = ['metadata', 'services', 'sku_summary']
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    # Check metadata
    metadata = data['metadata']
    if not all(key in metadata for key in ['region', 'total_services', 'total_skus']):
        return False, "Invalid metadata structure"
    
    # Check services
    if not isinstance(data['services'], dict):
        return False, "Services should be a dictionary"
    
    # Check SKU summary
    if not isinstance(data['sku_summary'], dict):
        return False, "SKU summary should be a dictionary"
    
    logger.info(f"Catalog validation passed: {metadata['total_services']} services, {metadata['total_skus']} SKUs")
    return True, "Valid catalog"

def download_sku_catalog(region, output_file=None):
    """Download SKU catalog if it doesn't exist."""
    if not output_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"gcp_skus_{region}_{timestamp}.json"
    
    # Check if catalog already exists
    exists, data = check_file_exists(output_file)
    if exists:
        logger.info(f"SKU catalog already exists: {output_file}")
        return output_file
    
    # Download catalog
    cmd = [
        sys.executable, "gcp-sku-downloader.py",
        "--region", region,
        "--output", output_file,
        "--verbose"
    ]
    
    result = run_command(cmd, f"Downloading SKU catalog for region {region}")
    
    if result.returncode == 0:
        logger.info(f"Successfully downloaded SKU catalog: {output_file}")
        return output_file
    else:
        raise RuntimeError(f"Failed to download SKU catalog: {result.stderr}")

def run_enhanced_sync(catalog_file, dry_run=False):
    """Run the enhanced price sync."""
    cmd = [
        sys.executable, "gcp-price-sync-enhanced-v2.py",
        "--sku-catalog", catalog_file
    ]
    
    if dry_run:
        cmd.append("--dry-run")
        description = "Running enhanced price sync (DRY RUN)"
    else:
        description = "Running enhanced price sync"
    
    result = run_command(cmd, description)
    
    if result.returncode == 0:
        logger.info("Enhanced price sync completed successfully")
        return True
    else:
        logger.error("Enhanced price sync failed")
        return False

def validate_sync_results(catalog_file):
    """Validate the sync results."""
    cmd = [
        sys.executable, "gcp-price-sync-enhanced-v2.py",
        "--sku-catalog", catalog_file,
        "--validate-only"
    ]
    
    result = run_command(cmd, "Validating sync results")
    
    if result.returncode == 0:
        logger.info("Sync validation completed")
        return True
    else:
        logger.error("Sync validation failed")
        return False

def print_workflow_summary(region, catalog_file, dry_run=False):
    """Print a summary of the workflow."""
    print("\n" + "="*60)
    print("COMPREHENSIVE GCP WORKFLOW SUMMARY")
    print("="*60)
    print(f"Region: {region}")
    print(f"Catalog File: {catalog_file}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Load and display catalog info
    exists, data = check_file_exists(catalog_file)
    if exists:
        metadata = data['metadata']
        print(f"\nCatalog Information:")
        print(f"  Total Services: {metadata['total_services']}")
        print(f"  Total SKUs: {metadata['total_skus']}")
        print(f"  Download Time: {metadata['download_timestamp']}")
        
        print(f"\nSKU Categories:")
        for category, count in data['sku_summary'].items():
            print(f"  {category}: {count} SKUs")
    
    print("="*60)

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Test comprehensive GCP workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_comprehensive_workflow.py --region asia-southeast2
  python test_comprehensive_workflow.py --region us-central1 --dry-run
  python test_comprehensive_workflow.py --region europe-west1 --catalog existing_catalog.json
        """
    )
    
    parser.add_argument(
        '--region',
        required=True,
        help='GCP region (e.g., asia-southeast2, us-central1)'
    )
    
    parser.add_argument(
        '--catalog',
        help='Use existing catalog file (skip download)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run in dry-run mode (no changes made)'
    )
    
    parser.add_argument(
        '--skip-download',
        action='store_true',
        help='Skip SKU catalog download (use existing)'
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
        catalog_file = args.catalog
        
        # Step 1: Download or validate SKU catalog
        if catalog_file:
            # Use provided catalog file
            logger.info(f"Using provided catalog file: {catalog_file}")
            valid, message = validate_sku_catalog(catalog_file)
            if not valid:
                raise ValueError(f"Invalid catalog file: {message}")
        elif args.skip_download:
            # Look for existing catalog
            timestamp = datetime.now().strftime("%Y%m%d")
            possible_files = [
                f"gcp_skus_{args.region}_{timestamp}_*.json",
                f"gcp_skus_{args.region}.json",
                f"gcp_skus_*.json"
            ]
            
            catalog_file = None
            for pattern in possible_files:
                import glob
                files = glob.glob(pattern)
                if files:
                    catalog_file = files[0]
                    break
            
            if not catalog_file:
                raise FileNotFoundError("No existing catalog file found. Use --catalog or remove --skip-download")
            
            valid, message = validate_sku_catalog(catalog_file)
            if not valid:
                raise ValueError(f"Invalid catalog file: {message}")
        else:
            # Download new catalog
            catalog_file = download_sku_catalog(args.region)
        
        # Step 2: Print workflow summary
        print_workflow_summary(args.region, catalog_file, args.dry_run)
        
        # Step 3: Run enhanced sync
        if not run_enhanced_sync(catalog_file, args.dry_run):
            raise RuntimeError("Enhanced sync failed")
        
        # Step 4: Validate results (only if not dry run)
        if not args.dry_run:
            if not validate_sync_results(catalog_file):
                logger.warning("Sync validation failed - check results manually")
        
        logger.info("Comprehensive workflow completed successfully!")
        
        # Print next steps
        print("\nNext Steps:")
        print("1. Check the Morpheus UI to verify pricing data")
        print("2. Review log files for any warnings or errors")
        print("3. Run validation again if needed:")
        print(f"   python gcp-price-sync-enhanced-v2.py --sku-catalog {catalog_file} --validate-only")
        
    except KeyboardInterrupt:
        logger.info("Workflow interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()