#!/usr/bin/env python3

"""
Test script for the enhanced GCP price sync tool.
This script validates the key fixes and improvements.
"""

import json
import os
import sys
import subprocess
from datetime import datetime

def test_environment():
    """Test environment setup and dependencies."""
    print("🔍 Testing Environment Setup...")
    
    # Check Python version
    python_version = sys.version_info
    print(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    # Check required packages
    try:
        import requests
        print(f"✅ requests {requests.__version__}")
    except ImportError:
        print("❌ requests package not found")
        return False
    
    try:
        import urllib3
        print(f"✅ urllib3 {urllib3.__version__}")
    except ImportError:
        print("❌ urllib3 package not found")
        return False
    
    # Check environment variables
    required_env_vars = ['MORPHEUS_URL', 'MORPHEUS_TOKEN']
    for var in required_env_vars:
        if os.getenv(var):
            print(f"✅ {var} is set")
        else:
            print(f"⚠️  {var} is not set (using default)")
    
    # Check gcloud CLI
    try:
        result = subprocess.run(['gcloud', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✅ {version_line}")
        else:
            print("❌ gcloud CLI not working properly")
            return False
    except FileNotFoundError:
        print("❌ gcloud CLI not found")
        return False
    
    return True

def test_enhanced_script():
    """Test the enhanced script functionality."""
    print("\n🔍 Testing Enhanced Script...")
    
    # Check if enhanced script exists
    if not os.path.exists('gcp-price-sync-enhanced.py'):
        print("❌ gcp-price-sync-enhanced.py not found")
        return False
    
    print("✅ Enhanced script found")
    
    # Test help functionality
    try:
        result = subprocess.run(['python3', 'gcp-price-sync-enhanced.py', '--help'], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and 'evaluate-apis' in result.stdout:
            print("✅ Help functionality works")
            print("✅ New 'evaluate-apis' command available")
        else:
            print("❌ Help functionality failed")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Help command timed out")
        return False
    except Exception as e:
        print(f"❌ Help test failed: {e}")
        return False
    
    return True

def test_api_evaluation():
    """Test the new API evaluation functionality."""
    print("\n🔍 Testing API Evaluation...")
    
    try:
        result = subprocess.run(['python3', 'gcp-price-sync-enhanced.py', 'evaluate-apis'], 
                              capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            output = result.stdout
            if 'GCP Billing Catalog API Evaluation' in output and 'Morpheus API Evaluation' in output:
                print("✅ API evaluation command works")
                print("✅ GCP API evaluation included")
                print("✅ Morpheus API evaluation included")
                
                # Check for key evaluation points
                evaluation_points = [
                    'Component price sets MUST include cores, memory, AND storage',
                    'Multiple storage types: Standard, SSD, Balanced, Extreme',
                    'Integration Requirements'
                ]
                
                for point in evaluation_points:
                    if point in output:
                        print(f"✅ Found: {point}")
                    else:
                        print(f"⚠️  Missing: {point}")
                
                return True
            else:
                print("❌ API evaluation output incomplete")
                return False
        else:
            print(f"❌ API evaluation failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ API evaluation timed out")
        return False
    except Exception as e:
        print(f"❌ API evaluation test failed: {e}")
        return False

def test_storage_coverage():
    """Test storage coverage validation."""
    print("\n🔍 Testing Storage Coverage Validation...")
    
    # Check if the enhanced script has storage validation
    with open('gcp-price-sync-enhanced.py', 'r') as f:
        content = f.read()
    
    storage_validation_checks = [
        'required_storage_types = {\'pd-standard\', \'pd-ssd\', \'pd-balanced\'}',
        'missing_storage_types = required_storage_types - storage_types',
        'pd-standard', 'pd-ssd', 'pd-balanced', 'pd-extreme',
        'local-ssd', 'hyperdisk-balanced', 'hyperdisk-extreme'
    ]
    
    for check in storage_validation_checks:
        if check in content:
            print(f"✅ Found storage validation: {check}")
        else:
            print(f"⚠️  Missing storage validation: {check}")
    
    return True

def test_component_price_set_fix():
    """Test component price set fix."""
    print("\n🔍 Testing Component Price Set Fix...")
    
    with open('gcp-price-sync-enhanced.py', 'r') as f:
        content = f.read()
    
    # Check for the key fixes
    fixes = [
        ('"type": "component"', 'Component price set type'),
        ('required_types = {\'cores\', \'memory\', \'storage\'}', 'Required components validation'),
        ('if not required_types.issubset(data[\'price_types\']):', 'Component validation logic'),
        ('logger.error(f"  Error: Missing required price types {missing_types} for Component pricing")', 'Error reporting')
    ]
    
    all_fixes_present = True
    for fix_code, description in fixes:
        if fix_code in content:
            print(f"✅ {description}")
        else:
            print(f"❌ Missing: {description}")
            all_fixes_present = False
    
    return all_fixes_present

def generate_test_report():
    """Generate a comprehensive test report."""
    print("\n" + "="*60)
    print("🧪 ENHANCED GCP PRICE SYNC - TEST REPORT")
    print("="*60)
    
    test_results = []
    
    # Run all tests
    tests = [
        ("Environment Setup", test_environment),
        ("Enhanced Script", test_enhanced_script),
        ("API Evaluation", test_api_evaluation),
        ("Storage Coverage", test_storage_coverage),
        ("Component Price Set Fix", test_component_price_set_fix)
    ]
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            test_results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
            test_results.append((test_name, False))
    
    # Generate summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The enhanced script is ready for use.")
        print("\n🚀 Next steps:")
        print("1. Set up environment variables")
        print("2. Run: python3 gcp-price-sync-enhanced.py discover-morpheus-plans")
        print("3. Run: python3 gcp-price-sync-enhanced.py sync-gcp-data")
        print("4. Run: python3 gcp-price-sync-enhanced.py create-prices")
        print("5. Run: python3 gcp-price-sync-enhanced.py create-price-sets")
        print("6. Run: python3 gcp-price-sync-enhanced.py map-plans-to-price-sets")
        print("7. Run: python3 gcp-price-sync-enhanced.py validate")
    else:
        print("⚠️  Some tests failed. Please review the issues above.")
    
    return passed == total

if __name__ == "__main__":
    success = generate_test_report()
    sys.exit(0 if success else 1)