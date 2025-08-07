#!/usr/bin/env python3
"""
API Discovery CLI - Unified Interface for Solution Architects
Provides easy access to all API discovery and testing tools.
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n🔧 {description}")
    print(f"Running: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Command completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="API Discovery CLI - Unified Interface for Solution Architects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick Morpheus discovery
  python api_discovery_cli.py morpheus --url https://morpheus.company.com --token YOUR_TOKEN

  # External API assessment
  python api_discovery_cli.py external --url https://api.external.com --auth-type basic --username user --password pass

  # Comprehensive Morpheus analysis
  python api_discovery_cli.py morpheus-full --url https://morpheus.company.com --token YOUR_TOKEN

  # Multi-API comparison
  python api_discovery_cli.py compare --urls https://api1.com,https://api2.com --tokens TOKEN1,TOKEN2
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Morpheus quick discovery
    morpheus_parser = subparsers.add_parser('morpheus', help='Quick HPE Morpheus API discovery')
    morpheus_parser.add_argument('--url', required=True, help='Morpheus base URL')
    morpheus_parser.add_argument('--token', required=True, help='Morpheus API token')
    morpheus_parser.add_argument('--output-dir', default='morpheus_discovery', help='Output directory')
    
    # External API discovery
    external_parser = subparsers.add_parser('external', help='External API discovery and testing')
    external_parser.add_argument('--url', required=True, help='API base URL')
    external_parser.add_argument('--auth-type', choices=['bearer', 'basic', 'api_key'], required=True, help='Authentication type')
    external_parser.add_argument('--token', help='Bearer token or API key')
    external_parser.add_argument('--username', help='Username for basic auth')
    external_parser.add_argument('--password', help='Password for basic auth')
    external_parser.add_argument('--key-name', default='X-API-Key', help='API key header name')
    external_parser.add_argument('--output-dir', default='external_api_discovery', help='Output directory')
    
    # Comprehensive Morpheus analysis
    morpheus_full_parser = subparsers.add_parser('morpheus-full', help='Comprehensive HPE Morpheus analysis')
    morpheus_full_parser.add_argument('--url', required=True, help='Morpheus base URL')
    morpheus_full_parser.add_argument('--token', required=True, help='Morpheus API token')
    morpheus_full_parser.add_argument('--output-dir', default='morpheus_full_analysis', help='Output directory')
    
    # Multi-API comparison
    compare_parser = subparsers.add_parser('compare', help='Compare multiple APIs')
    compare_parser.add_argument('--urls', required=True, help='Comma-separated list of API URLs')
    compare_parser.add_argument('--tokens', required=True, help='Comma-separated list of API tokens')
    compare_parser.add_argument('--auth-types', default='bearer', help='Comma-separated list of auth types')
    compare_parser.add_argument('--output-dir', default='api_comparison', help='Output directory')
    
    # Health check
    health_parser = subparsers.add_parser('health', help='Check tool dependencies and setup')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'health':
        print("🔍 Checking API Discovery Tools Health")
        print("=" * 50)
        
        # Check Python dependencies
        try:
            import requests
            import yaml
            import urllib3
            print("✅ Python dependencies: OK")
        except ImportError as e:
            print(f"❌ Missing dependency: {e}")
            print("Run: pip install -r requirements.txt")
            return
        
        # Check if tools exist
        tools = ['universal_api_discovery.py', 'morpheus_api_explorer.py', 'morpheus_payload_analyzer.py']
        for tool in tools:
            if Path(tool).exists():
                print(f"✅ {tool}: Found")
            else:
                print(f"❌ {tool}: Missing")
        
        print("\n🎯 Ready for API discovery!")
        return
    
    elif args.command == 'morpheus':
        print("🚀 Starting HPE Morpheus API Discovery")
        print(f"URL: {args.url}")
        print(f"Output: {args.output_dir}")
        
        # Run universal discovery
        cmd = [
            'python', 'universal_api_discovery.py',
            '--url', args.url,
            '--auth-type', 'bearer',
            '--token', args.token,
            '--output-dir', args.output_dir,
            '--test-endpoints'
        ]
        
        success = run_command(cmd, "Discovering Morpheus API endpoints and capabilities")
        
        if success:
            print(f"\n📊 Discovery complete! Check {args.output_dir}/ for reports.")
            print("Generated files:")
            print(f"  - {args.output_dir}/api_discovery_report.md (Human-readable)")
            print(f"  - {args.output_dir}/api_discovery_report.json (Raw data)")
            print(f"  - {args.output_dir}/test_discovered_apis.py (Test script)")
    
    elif args.command == 'external':
        print("🚀 Starting External API Discovery")
        print(f"URL: {args.url}")
        print(f"Auth: {args.auth_type}")
        print(f"Output: {args.output_dir}")
        
        cmd = ['python', 'universal_api_discovery.py', '--url', args.url, '--auth-type', args.auth_type]
        
        if args.auth_type == 'bearer' and args.token:
            cmd.extend(['--token', args.token])
        elif args.auth_type == 'basic' and args.username and args.password:
            cmd.extend(['--username', args.username, '--password', args.password])
        elif args.auth_type == 'api_key' and args.token:
            cmd.extend(['--token', args.token, '--key-name', args.key_name])
        
        cmd.extend(['--output-dir', args.output_dir, '--test-endpoints'])
        
        success = run_command(cmd, "Discovering external API endpoints and capabilities")
        
        if success:
            print(f"\n📊 Discovery complete! Check {args.output_dir}/ for reports.")
    
    elif args.command == 'morpheus-full':
        print("🚀 Starting Comprehensive HPE Morpheus Analysis")
        print(f"URL: {args.url}")
        print(f"Output: {args.output_dir}")
        
        # Step 1: Universal discovery
        cmd1 = [
            'python', 'universal_api_discovery.py',
            '--url', args.url,
            '--auth-type', 'bearer',
            '--token', args.token,
            '--output-dir', f"{args.output_dir}/universal",
            '--test-endpoints'
        ]
        
        success1 = run_command(cmd1, "Step 1: Universal API discovery")
        
        # Step 2: Morpheus-specific exploration
        cmd2 = [
            'python', 'morpheus_api_explorer.py',
            '--url', args.url,
            '--token', args.token,
            '--output-dir', f"{args.output_dir}/morpheus_specific"
        ]
        
        success2 = run_command(cmd2, "Step 2: Morpheus-specific endpoint exploration")
        
        # Step 3: Payload analysis
        cmd3 = [
            'python', 'morpheus_payload_analyzer.py',
            '--url', args.url,
            '--token', args.token,
            '--output-dir', f"{args.output_dir}/payload_analysis",
            '--endpoints', 'instances', 'apps', 'service-plans', 'price-sets', 'prices', 'clouds', 'groups'
        ]
        
        success3 = run_command(cmd3, "Step 3: Payload structure analysis")
        
        if success1 and success2 and success3:
            print(f"\n📊 Comprehensive analysis complete! Check {args.output_dir}/ for all reports.")
            print("Generated directories:")
            print(f"  - {args.output_dir}/universal/ (General API discovery)")
            print(f"  - {args.output_dir}/morpheus_specific/ (Morpheus-specific analysis)")
            print(f"  - {args.output_dir}/payload_analysis/ (Payload structure analysis)")
    
    elif args.command == 'compare':
        print("🚀 Starting Multi-API Comparison")
        
        urls = [url.strip() for url in args.urls.split(',')]
        tokens = [token.strip() for token in args.tokens.split(',')]
        auth_types = [auth.strip() for auth in args.auth_types.split(',')]
        
        if len(urls) != len(tokens) or len(urls) != len(auth_types):
            print("❌ Error: Number of URLs, tokens, and auth types must match")
            return
        
        print(f"Comparing {len(urls)} APIs:")
        for i, url in enumerate(urls):
            print(f"  {i+1}. {url} ({auth_types[i]})")
        
        print(f"Output: {args.output_dir}")
        
        # Create comparison directory
        os.makedirs(args.output_dir, exist_ok=True)
        
        all_success = True
        
        for i, (url, token, auth_type) in enumerate(zip(urls, tokens, auth_types)):
            print(f"\n🔍 Analyzing API {i+1}: {url}")
            
            api_output_dir = f"{args.output_dir}/api_{i+1}"
            
            cmd = ['python', 'universal_api_discovery.py', '--url', url, '--auth-type', auth_type]
            
            if auth_type == 'bearer':
                cmd.extend(['--token', token])
            elif auth_type == 'basic':
                # Split token as username:password
                if ':' in token:
                    username, password = token.split(':', 1)
                    cmd.extend(['--username', username, '--password', password])
                else:
                    print(f"❌ Error: Basic auth token should be in format 'username:password'")
                    all_success = False
                    continue
            elif auth_type == 'api_key':
                cmd.extend(['--token', token])
            
            cmd.extend(['--output-dir', api_output_dir, '--test-endpoints'])
            
            success = run_command(cmd, f"Discovering API {i+1} endpoints")
            if not success:
                all_success = False
        
        if all_success:
            print(f"\n📊 Comparison complete! Check {args.output_dir}/ for all API reports.")
            print("Generated directories:")
            for i in range(len(urls)):
                print(f"  - {args.output_dir}/api_{i+1}/ (API {i+1} analysis)")
            
            # Generate comparison summary
            print("\n📋 Next steps:")
            print("1. Review individual API reports")
            print("2. Compare endpoint capabilities")
            print("3. Analyze authentication methods")
            print("4. Evaluate performance characteristics")
    
    print("\n🎯 API Discovery CLI completed!")
    print("💡 Tip: Use 'python api_discovery_cli.py health' to check your setup")

if __name__ == "__main__":
    main()