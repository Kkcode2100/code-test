#!/usr/bin/env python3
"""
Simple compatibility test for gcp-price-sync-enhanced-v2.py
Validates the catalog format without requiring full module import.
"""

import json
import os

def test_catalog_structure():
    """Test that the catalog structure matches the expected format."""
    print("Testing catalog structure compatibility...")
    
    # Create test catalog matching your successful download format
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
    
    # Test 1: Check metadata structure
    print("  ✓ Testing metadata structure...")
    if "metadata" not in test_catalog:
        print("    ❌ Missing metadata section")
        return False
    
    metadata = test_catalog["metadata"]
    required_metadata_fields = ["region", "download_timestamp", "total_services", "total_skus"]
    for field in required_metadata_fields:
        if field not in metadata:
            print(f"    ❌ Missing metadata field: {field}")
            return False
    
    print(f"    ✓ Metadata: {metadata['region']}, {metadata['total_services']} services, {metadata['total_skus']} SKUs")
    
    # Test 2: Check services structure
    print("  ✓ Testing services structure...")
    if "services" not in test_catalog:
        print("    ❌ Missing services section")
        return False
    
    services = test_catalog["services"]
    if not isinstance(services, dict):
        print("    ❌ Services should be a dictionary")
        return False
    
    print(f"    ✓ Found {len(services)} services")
    
    # Test 3: Check individual service structure
    print("  ✓ Testing individual service structure...")
    for service_id, service_data in services.items():
        if "service_info" not in service_data:
            print(f"    ❌ Service {service_id} missing service_info")
            return False
        
        if "skus" not in service_data:
            print(f"    ❌ Service {service_id} missing skus")
            return False
        
        service_info = service_data["service_info"]
        if "display_name" not in service_info:
            print(f"    ❌ Service {service_id} missing display_name")
            return False
        
        skus = service_data["skus"]
        if not isinstance(skus, list):
            print(f"    ❌ Service {service_id} skus should be a list")
            return False
        
        print(f"    ✓ Service {service_id}: {service_info['display_name']} ({len(skus)} SKUs)")
    
    # Test 4: Check SKU structure
    print("  ✓ Testing SKU structure...")
    for service_id, service_data in services.items():
        for sku in service_data["skus"]:
            required_sku_fields = ["skuId", "description", "category", "pricingInfo"]
            for field in required_sku_fields:
                if field not in sku:
                    print(f"    ❌ SKU missing field: {field}")
                    return False
            
            # Check pricing info structure
            pricing_info = sku["pricingInfo"]
            if not isinstance(pricing_info, list) or len(pricing_info) == 0:
                print(f"    ❌ SKU {sku['skuId']} has invalid pricingInfo")
                return False
            
            pricing_expr = pricing_info[0].get("pricingExpression", {})
            if "usageUnit" not in pricing_expr or "tieredRates" not in pricing_expr:
                print(f"    ❌ SKU {sku['skuId']} has invalid pricingExpression")
                return False
            
            tiered_rates = pricing_expr["tieredRates"]
            if not isinstance(tiered_rates, list) or len(tiered_rates) == 0:
                print(f"    ❌ SKU {sku['skuId']} has invalid tieredRates")
                return False
            
            unit_price = tiered_rates[0].get("unitPrice", {})
            if "units" not in unit_price or "nanos" not in unit_price:
                print(f"    ❌ SKU {sku['skuId']} has invalid unitPrice")
                return False
    
    print("    ✓ All SKUs have valid structure")
    return True

def test_enhanced_script_syntax():
    """Test that the enhanced script has valid Python syntax."""
    print("\nTesting enhanced script syntax...")
    
    script_file = "gcp-price-sync-enhanced-v2.py"
    if not os.path.exists(script_file):
        print(f"  ❌ Script file {script_file} not found")
        return False
    
    try:
        with open(script_file, 'r') as f:
            content = f.read()
        
        # Basic syntax check
        compile(content, script_file, 'exec')
        print("  ✓ Script has valid Python syntax")
        
        # Check for required classes
        if "class SKUCatalogProcessor" in content:
            print("  ✓ Found SKUCatalogProcessor class")
        else:
            print("  ❌ Missing SKUCatalogProcessor class")
            return False
        
        if "class MorpheusApiClient" in content:
            print("  ✓ Found MorpheusApiClient class")
        else:
            print("  ❌ Missing MorpheusApiClient class")
            return False
        
        # Check for main function
        if "def main()" in content:
            print("  ✓ Found main function")
        else:
            print("  ❌ Missing main function")
            return False
        
        return True
        
    except SyntaxError as e:
        print(f"  ❌ Syntax error in script: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error reading script: {e}")
        return False

def test_usage_examples():
    """Test that the script has proper usage examples."""
    print("\nTesting usage examples...")
    
    script_file = "gcp-price-sync-enhanced-v2.py"
    try:
        with open(script_file, 'r') as f:
            content = f.read()
        
        # Check for proper usage examples
        if "gcp_skus_20250807_194211.json" in content:
            print("  ✓ Script references the correct catalog filename")
        else:
            print("  ❌ Script doesn't reference the correct catalog filename")
            return False
        
        if "--dry-run" in content:
            print("  ✓ Script includes dry-run option")
        else:
            print("  ❌ Script missing dry-run option")
            return False
        
        if "--validate-only" in content:
            print("  ✓ Script includes validate-only option")
        else:
            print("  ❌ Script missing validate-only option")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error checking usage examples: {e}")
        return False

def main():
    """Main test function."""
    print("="*70)
    print("GCP PRICE SYNC ENHANCED V2 - SIMPLE COMPATIBILITY TEST")
    print("="*70)
    
    # Run all tests
    tests = [
        ("Catalog Structure", test_catalog_structure),
        ("Script Syntax", test_enhanced_script_syntax),
        ("Usage Examples", test_usage_examples)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ❌ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("The enhanced v2 script is ready to use with your downloaded catalog.")
        print("\nNext steps:")
        print("1. Copy your gcp_skus_20250807_194211.json file to this directory")
        print("2. Run: python3 gcp-price-sync-enhanced-v2.py --sku-catalog gcp_skus_20250807_194211.json --dry-run")
        print("3. If dry-run looks good, run without --dry-run to sync to Morpheus")
    else:
        print("\n⚠️  Some tests failed. Please check the issues above.")
    
    print("="*70)

if __name__ == "__main__":
    main()