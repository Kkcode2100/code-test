#!/usr/bin/env python3
"""
Test script for gcp-price-sync-enhanced-v2.py
Tests the script with the downloaded SKU data structure.
"""

import json
import sys
import os

# Add the current directory to the path to import the module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the SKUCatalogProcessor class
try:
    # Import the module with the correct filename
    import importlib.util
    spec = importlib.util.spec_from_file_location("gcp_price_sync_enhanced_v2", "gcp-price-sync-enhanced-v2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    SKUCatalogProcessor = module.SKUCatalogProcessor
except ImportError as e:
    print(f"Error: Could not import SKUCatalogProcessor from gcp-price-sync-enhanced-v2.py: {e}")
    print("Make sure the file exists and is in the same directory.")
    sys.exit(1)

def test_summary_file():
    """Test with the summary file structure."""
    print("Testing with summary file structure...")
    
    # Create a mock summary file based on your actual output
    mock_summary = {
        "metadata": {
            "region": "asia-southeast2",
            "download_timestamp": "2025-08-07T19:44:06.432082",
            "total_services": 1795,
            "total_skus": 1905
        },
        "sku_summary": {
            "Storage": 137,
            "Network": 716,
            "ApplicationServices": 672,
            "Compute": 380
        },
        "category_summary": {
            "Storage": 137,
            "Network": 716,
            "ApplicationServices": 672,
            "Compute": 380
        },
        "services_summary": {
            "116A-ED39-D1F0": {
                "display_name": "Database Migration",
                "sku_count": 2
            },
            "149C-F9EC-3994": {
                "display_name": "Artifact Registry",
                "sku_count": 3
            },
            "152E-C115-5142": {
                "display_name": "Cloud Run",
                "sku_count": 17
            },
            "6F81-5844-456A": {
                "display_name": "Compute Engine",
                "sku_count": 784
            },
            "95FF-2EF5-5EA1": {
                "display_name": "Cloud Storage",
                "sku_count": 21
            },
            "9662-B51E-5089": {
                "display_name": "Cloud SQL",
                "sku_count": 404
            },
            "C7E2-9256-1C43": {
                "display_name": "Vertex AI",
                "sku_count": 185
            }
        }
    }
    
    # Write mock file
    with open('test_summary.json', 'w') as f:
        json.dump(mock_summary, f, indent=2)
    
    try:
        # Test the processor
        processor = SKUCatalogProcessor('test_summary.json')
        
        print("✓ Successfully loaded summary file")
        print(f"  Total services: {processor.catalog['metadata']['total_services']}")
        print(f"  Total SKUs: {processor.catalog['metadata']['total_skus']}")
        
        # Test categorization
        summary = processor.get_sku_summary()
        print("\nCategorization results:")
        for category, data in summary.items():
            print(f"  {category}: {data['count']} SKUs")
        
        # Test original summary retrieval
        original = processor.get_original_summary()
        if original:
            print("\nOriginal summary retrieved:")
            for category, count in original.items():
                print(f"  {category}: {count}")
        
        print("\n✓ All tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False
    finally:
        # Cleanup
        if os.path.exists('test_summary.json'):
            os.remove('test_summary.json')

def test_full_catalog_file():
    """Test with a full catalog file structure."""
    print("\nTesting with full catalog file structure...")
    
    # Create a mock full catalog
    mock_catalog = {
        "metadata": {
            "region": "asia-southeast2",
            "download_timestamp": "2025-08-07T19:44:06.432082",
            "total_services": 2,
            "total_skus": 3
        },
        "services": {
            "95FF-2EF5-5EA1": {
                "service_info": {
                    "display_name": "Cloud Storage",
                    "service_id": "95FF-2EF5-5EA1"
                },
                "skus": [
                    {
                        "skuId": "95FF-2EF5-5EA1-sku-1",
                        "description": "Cloud Storage Standard",
                        "category": {
                            "resourceFamily": "Storage",
                            "resourceGroup": "Cloud Storage",
                            "usageType": "OnDemand"
                        },
                        "pricingInfo": [{
                            "pricingExpression": {
                                "usageUnit": "GiBy.mo",
                                "tieredRates": [{
                                    "unitPrice": {
                                        "units": "0",
                                        "nanos": 20000000  # $0.02
                                    }
                                }]
                            }
                        }]
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
                        "skuId": "6F81-5844-456A-sku-1",
                        "description": "Compute Engine n1-standard-1",
                        "category": {
                            "resourceFamily": "Compute",
                            "resourceGroup": "Compute Engine",
                            "usageType": "OnDemand"
                        },
                        "pricingInfo": [{
                            "pricingExpression": {
                                "usageUnit": "hour",
                                "tieredRates": [{
                                    "unitPrice": {
                                        "units": "0",
                                        "nanos": 50000000  # $0.05
                                    }
                                }]
                            }
                        }]
                    }
                ]
            }
        }
    }
    
    # Write mock file
    with open('test_full_catalog.json', 'w') as f:
        json.dump(mock_catalog, f, indent=2)
    
    try:
        # Test the processor
        processor = SKUCatalogProcessor('test_full_catalog.json')
        
        print("✓ Successfully loaded full catalog file")
        print(f"  Total services: {processor.catalog['metadata']['total_services']}")
        print(f"  Total SKUs: {processor.catalog['metadata']['total_skus']}")
        
        # Test categorization
        summary = processor.get_sku_summary()
        print("\nCategorization results:")
        for category, data in summary.items():
            print(f"  {category}: {data['count']} SKUs")
        
        # Test specific category methods
        storage_skus = processor.get_storage_skus()
        compute_skus = processor.get_compute_skus()
        
        print(f"\nStorage SKUs: {len(storage_skus)}")
        print(f"Compute SKUs: {len(compute_skus)}")
        
        print("\n✓ All tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False
    finally:
        # Cleanup
        if os.path.exists('test_full_catalog.json'):
            os.remove('test_full_catalog.json')

def main():
    """Run all tests."""
    print("Testing gcp-price-sync-enhanced-v2.py functionality...")
    
    success = True
    
    # Test summary file processing
    if not test_summary_file():
        success = False
    
    # Test full catalog processing
    if not test_full_catalog_file():
        success = False
    
    if success:
        print("\n🎉 All tests passed! The enhanced script is ready to use.")
        print("\nUsage examples:")
        print("  python gcp-price-sync-enhanced-v2.py --sku-catalog gcp_skus_20250807_194211_summary.json --dry-run")
        print("  python gcp-price-sync-enhanced-v2.py --sku-catalog gcp_skus_20250807_194211.json --validate-only")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        sys.exit(1)

if __name__ == "__main__":
    main()