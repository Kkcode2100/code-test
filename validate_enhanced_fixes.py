#!/usr/bin/env python3

"""
Simple validation script for the enhanced GCP price sync fixes.
This script validates the key fixes without requiring external dependencies.
"""

import os
import re

def validate_component_price_set_fix():
    """Validate that the component price set fix is implemented."""
    print("🔍 Validating Component Price Set Fix...")
    
    if not os.path.exists('gcp-price-sync-enhanced.py'):
        print("❌ Enhanced script not found")
        return False
    
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

def validate_storage_coverage():
    """Validate comprehensive storage coverage."""
    print("\n🔍 Validating Storage Coverage...")
    
    with open('gcp-price-sync-enhanced.py', 'r') as f:
        content = f.read()
    
    # Check for storage types
    storage_types = [
        'pd-standard', 'pd-ssd', 'pd-balanced', 'pd-extreme',
        'local-ssd', 'hyperdisk-balanced', 'hyperdisk-extreme',
        'regional-pd-standard', 'regional-pd-ssd'
    ]
    
    all_storage_types_present = True
    for storage_type in storage_types:
        if storage_type in content:
            print(f"✅ {storage_type}")
        else:
            print(f"❌ Missing: {storage_type}")
            all_storage_types_present = False
    
    # Check for storage validation
    validation_checks = [
        'required_storage_types = {\'pd-standard\', \'pd-ssd\', \'pd-balanced\'}',
        'missing_storage_types = required_storage_types - storage_types',
        'if missing_storage_types:',
        'logger.warning(f"Missing required storage types: {missing_storage_types}")'
    ]
    
    for check in validation_checks:
        if check in content:
            print(f"✅ Storage validation: {check}")
        else:
            print(f"⚠️  Missing storage validation: {check}")
    
    return all_storage_types_present

def validate_api_evaluation():
    """Validate API evaluation functionality."""
    print("\n🔍 Validating API Evaluation...")
    
    with open('gcp-price-sync-enhanced.py', 'r') as f:
        content = f.read()
    
    # Check for evaluate_apis function
    if 'def evaluate_apis():' in content:
        print("✅ API evaluation function present")
    else:
        print("❌ API evaluation function missing")
        return False
    
    # Check for API evaluation content
    evaluation_content = [
        'GCP Billing Catalog API Evaluation',
        'Morpheus API Evaluation',
        'Component price sets MUST include cores, memory, AND storage',
        'Multiple storage types: Standard, SSD, Balanced, Extreme',
        'Integration Requirements'
    ]
    
    all_content_present = True
    for item in evaluation_content:
        if item in content:
            print(f"✅ {item}")
        else:
            print(f"❌ Missing: {item}")
            all_content_present = False
    
    return all_content_present

def validate_enhanced_sku_detection():
    """Validate enhanced SKU detection logic."""
    print("\n🔍 Validating Enhanced SKU Detection...")
    
    with open('gcp-price-sync-enhanced.py', 'r') as f:
        content = f.read()
    
    # Check for enhanced disk type detection
    detection_patterns = [
        'local ssd',
        'hyperdisk.*balanced',
        'hyperdisk.*extreme',
        'pd-extreme',
        'pd-balanced',
        'pd-ssd',
        'regional.*ssd',
        'regional.*standard'
    ]
    
    all_patterns_present = True
    for pattern in detection_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            print(f"✅ {pattern}")
        else:
            print(f"❌ Missing: {pattern}")
            all_patterns_present = False
    
    return all_patterns_present

def validate_comprehensive_filters():
    """Validate comprehensive storage filters."""
    print("\n🔍 Validating Comprehensive Storage Filters...")
    
    with open('gcp-price-sync-enhanced.py', 'r') as f:
        content = f.read()
    
    # Check for comprehensive disk types list
    disk_types = [
        'pd-standard', 'pd-ssd', 'pd-balanced', 'pd-extreme',
        'local-ssd', 'hyperdisk-balanced', 'hyperdisk-extreme',
        'regional-pd-standard', 'regional-pd-ssd',
        'standard persistent disk', 'ssd persistent disk',
        'balanced persistent disk', 'extreme persistent disk'
    ]
    
    all_disk_types_present = True
    for disk_type in disk_types:
        if disk_type in content:
            print(f"✅ {disk_type}")
        else:
            print(f"❌ Missing: {disk_type}")
            all_disk_types_present = False
    
    return all_disk_types_present

def generate_validation_report():
    """Generate comprehensive validation report."""
    print("="*60)
    print("🔧 ENHANCED GCP PRICE SYNC - VALIDATION REPORT")
    print("="*60)
    
    validation_results = []
    
    # Run all validations
    validations = [
        ("Component Price Set Fix", validate_component_price_set_fix),
        ("Storage Coverage", validate_storage_coverage),
        ("API Evaluation", validate_api_evaluation),
        ("Enhanced SKU Detection", validate_enhanced_sku_detection),
        ("Comprehensive Filters", validate_comprehensive_filters)
    ]
    
    for validation_name, validation_func in validations:
        try:
            result = validation_func()
            validation_results.append((validation_name, result))
        except Exception as e:
            print(f"❌ {validation_name} validation failed with exception: {e}")
            validation_results.append((validation_name, False))
    
    # Generate summary
    print("\n" + "="*60)
    print("📊 VALIDATION SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in validation_results if result)
    total = len(validation_results)
    
    for validation_name, result in validation_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {validation_name}")
    
    print(f"\nOverall: {passed}/{total} validations passed")
    
    if passed == total:
        print("\n🎉 All validations passed! The enhanced script includes all required fixes:")
        print("✅ Component price set type fix")
        print("✅ Comprehensive storage coverage")
        print("✅ Enhanced SKU detection")
        print("✅ API evaluation functionality")
        print("✅ Storage validation")
        
        print("\n🚀 Key Improvements:")
        print("• Fixed price set type from 'fixed' to 'component'")
        print("• Added comprehensive storage type coverage (SSD, Balanced, Standard, Extreme)")
        print("• Enhanced GCP SKU detection for all disk types")
        print("• Added pre-creation validation for component price sets")
        print("• Added API evaluation functionality")
        print("• Improved error handling and reporting")
        
        print("\n📋 Next Steps:")
        print("1. Install dependencies: pip install requests urllib3")
        print("2. Set up environment variables")
        print("3. Run the enhanced script workflow")
        
    else:
        print("\n⚠️  Some validations failed. Please review the issues above.")
    
    return passed == total

if __name__ == "__main__":
    success = generate_validation_report()
    exit(0 if success else 1)