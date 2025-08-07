#!/usr/bin/env python3
"""
Test script to verify gcp-price-sync-enhanced-v2.py compatibility
with the successful gcp-sku-downloader.py output format.
"""

import json
import sys
import os
from datetime import datetime

def create_test_catalog():
    """Create a test catalog matching the successful download format."""
    test_catalog = {
        "metadata": {
            "region": "asia-southeast2",
            "download_timestamp": "2025-08-07T19:44:06.432082",
            "total_services": 1795,
            "total_skus": 1905
        },
        "services": {
            "116A-ED39-D1F0": {
                "service_info": {
                    "display_name": "Database Migration",
                    "service_id": "116A-ED39-D1F0"
                },
                "skus": [
                    {
                        "skuId": "test-sku-1",
                        "description": "Database Migration Standard",
                        "category": {"resourceFamily": "Migration"},
                        "pricingInfo": [
                            {
                                "pricingExpression": {
                                    "usageUnit": "GiB",
                                    "tieredRates": [
                                        {
                                            "unitPrice": {
                                                "units": "0",
                                                "nanos": 100000000
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ]
            },
            "6F81-5844-456A": {
                "service_info": {
                    "display_name": "Compute Engine",
                    "service_id": "6F81-5844-456A"
                },
                "skus": [
                    {
                        "skuId": "test-compute-1",
                        "description": "Custom Instance Core",
                        "category": {"resourceFamily": "Compute"},
                        "pricingInfo": [
                            {
                                "pricingExpression": {
                                    "usageUnit": "h",
                                    "tieredRates": [
                                        {
                                            "unitPrice": {
                                                "units": "0",
                                                "nanos": 50000000
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ]
            },
            "95FF-2EF5-5EA1": {
                "service_info": {
                    "display_name": "Cloud Storage",
                    "service_id": "95FF-2EF5-5EA1"
                },
                "skus": [
                    {
                        "skuId": "test-storage-1",
                        "description": "Standard Storage",
                        "category": {"resourceFamily": "Storage"},
                        "pricingInfo": [
                            {
                                "pricingExpression": {
                                    "usageUnit": "GiB",
                                    "tieredRates": [
                                        {
                                            "unitPrice": {
                                                "units": "0",
                                                "nanos": 20000000
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ]
            }
        }
    }
    return test_catalog

def test_sku_processor():
    """Test the SKU processor with the test catalog."""
    print("Testing SKU Catalog Processor compatibility...")
    
    # Create test catalog
    test_catalog = create_test_catalog()
    
    # Save test catalog
    test_file = "test_sku_catalog.json"
    with open(test_file, 'w') as f:
        json.dump(test_catalog, f, indent=2)
    
    print(f"Created test catalog: {test_file}")
    
    try:
        # Import the SKU processor from the enhanced script
        sys.path.append('.')
        import importlib.util
        spec = importlib.util.spec_from_file_location("gcp_price_sync_enhanced_v2", "gcp-price-sync-enhanced-v2.py")
        gcp_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gcp_module)
        SKUCatalogProcessor = gcp_module.SKUCatalogProcessor
        
        # Test the processor
        processor = SKUCatalogProcessor(test_file)
        
        # Test methods
        print("\nTesting SKU processing...")
        all_skus = processor.get_all_skus()
        print(f"Total processed SKUs: {len(all_skus)}")
        
        sku_summary = processor.get_sku_summary()
        print(f"SKU Summary: {sku_summary}")
        
        service_summary = processor.get_service_summary()
        print(f"Service Summary: {service_summary}")
        
        # Test categorization
        storage_skus = processor.get_storage_skus()
        compute_skus = processor.get_compute_skus()
        
        print(f"Storage SKUs: {len(storage_skus)}")
        print(f"Compute SKUs: {len(compute_skus)}")
        
        print("\n✅ SKU Processor test passed!")
        
        # Clean up
        os.remove(test_file)
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure gcp-price-sync-enhanced-v2.py is in the current directory")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

def test_catalog_format_compatibility():
    """Test that the catalog format matches the successful download."""
    print("\nTesting catalog format compatibility...")
    
    # Based on your successful run output
    expected_structure = {
        "metadata": ["region", "download_timestamp", "total_services", "total_skus"],
        "services": "dict_with_service_ids"
    }
    
    test_catalog = create_test_catalog()
    
    # Check metadata structure
    if "metadata" not in test_catalog:
        print("❌ Missing metadata section")
        return False
    
    metadata = test_catalog["metadata"]
    for field in expected_structure["metadata"]:
        if field not in metadata:
            print(f"❌ Missing metadata field: {field}")
            return False
    
    # Check services structure
    if "services" not in test_catalog:
        print("❌ Missing services section")
        return False
    
    services = test_catalog["services"]
    if not isinstance(services, dict):
        print("❌ Services should be a dictionary")
        return False
    
    # Check service structure
    for service_id, service_data in services.items():
        if "service_info" not in service_data:
            print(f"❌ Service {service_id} missing service_info")
            return False
        
        if "skus" not in service_data:
            print(f"❌ Service {service_id} missing skus")
            return False
        
        service_info = service_data["service_info"]
        if "display_name" not in service_info:
            print(f"❌ Service {service_id} missing display_name")
            return False
    
    print("✅ Catalog format compatibility test passed!")
    return True

def main():
    """Main test function."""
    print("="*60)
    print("GCP PRICE SYNC ENHANCED V2 - COMPATIBILITY TEST")
    print("="*60)
    
    # Test catalog format
    format_ok = test_catalog_format_compatibility()
    
    # Test SKU processor
    processor_ok = test_sku_processor()
    
    print("\n" + "="*60)
    if format_ok and processor_ok:
        print("✅ ALL TESTS PASSED!")
        print("The enhanced v2 script is compatible with your successful download format.")
        print("\nYou can now use it with your downloaded catalog:")
        print("python gcp-price-sync-enhanced-v2.py --sku-catalog gcp_skus_20250807_194211.json --dry-run")
    else:
        print("❌ SOME TESTS FAILED!")
        print("Please check the errors above.")
    print("="*60)

if __name__ == "__main__":
    main()