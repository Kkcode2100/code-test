#!/usr/bin/env python3
"""
Universal API Discovery and Testing Framework
Industry-standard approach for discovering and testing APIs in hybrid cloud environments.
Follows OpenAPI, REST API, and GraphQL discovery patterns.

Usage:
    python universal_api_discovery.py --url https://api.example.com --auth-type bearer --token YOUR_TOKEN
    python universal_api_discovery.py --url https://morpheus.company.com --auth-type bearer --token MORPHEUS_TOKEN --discover-only
    python universal_api_discovery.py --url https://external-api.com --auth-type basic --username user --password pass --test-endpoints
"""

import requests
import json
import logging
import argparse
import os
import sys
import time
import yaml
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urljoin, urlparse, urlunparse
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import concurrent.futures
from dataclasses import dataclass, asdict
import re

# Disable SSL warnings for development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@dataclass
class ApiEndpoint:
    """Standardized API endpoint information."""
    path: str
    method: str
    status_code: int
    response_time: float
    content_type: str
    response_size: int
    requires_auth: bool
    rate_limited: bool
    pagination: bool
    filtering: bool
    sorting: bool
    sample_response: Optional[Dict] = None
    error_responses: List[Dict] = None
    query_params: List[str] = None
    path_params: List[str] = None
    request_schema: Optional[Dict] = None
    response_schema: Optional[Dict] = None

class UniversalApiDiscovery:
    """
    Universal API Discovery Framework following industry standards:
    - OpenAPI/Swagger specification discovery
    - REST API pattern recognition
    - GraphQL introspection
    - Standard HTTP method testing
    - Rate limiting detection
    - Authentication method detection
    """
    
    def __init__(self, base_url: str, auth_config: Dict[str, Any], output_dir: str = "api_discovery"):
        self.base_url = base_url.rstrip('/')
        self.auth_config = auth_config
        self.output_dir = output_dir
        self.session = self._setup_session()
        self.discovered_endpoints = []
        self.api_specs = {}
        self.rate_limits = {}
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Setup logging
        self._setup_logging()
        
        # Common API patterns
        self.common_paths = [
            # REST API patterns
            "api", "api/v1", "api/v2", "rest", "rest/v1", "rest/v2",
            # OpenAPI/Swagger
            "swagger", "swagger.json", "openapi", "openapi.json",
            # GraphQL
            "graphql", "graphiql",
            # Documentation
            "docs", "documentation", "api-docs",
            # Health checks
            "health", "status", "ping", "ready",
            # Common resources
            "users", "instances", "servers", "apps", "projects",
            "clouds", "groups", "tenants", "organizations"
        ]

    def _setup_logging(self):
        """Setup comprehensive logging."""
        log_file = f"{self.output_dir}/discovery.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _setup_session(self) -> requests.Session:
        """Setup requests session with industry-standard configurations."""
        session = requests.Session()
        
        # Industry-standard retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set authentication
        self._apply_authentication(session)
        
        # Standard headers
        session.headers.update({
            "User-Agent": "Universal-API-Discovery/1.0",
            "Accept": "application/json, application/xml, text/plain, */*",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        })
        
        return session

    def _apply_authentication(self, session: requests.Session):
        """Apply authentication based on configuration."""
        auth_type = self.auth_config.get("type", "none")
        
        if auth_type == "bearer":
            token = self.auth_config.get("token")
            if token:
                session.headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "basic":
            username = self.auth_config.get("username")
            password = self.auth_config.get("password")
            if username and password:
                session.auth = (username, password)
        elif auth_type == "api_key":
            key_name = self.auth_config.get("key_name", "X-API-Key")
            key_value = self.auth_config.get("key_value")
            if key_value:
                session.headers[key_name] = key_value
        elif auth_type == "oauth2":
            # OAuth2 implementation
            pass

    def discover_api_specifications(self) -> Dict[str, Any]:
        """Discover OpenAPI/Swagger specifications and other API docs."""
        self.logger.info("Discovering API specifications...")
        
        spec_endpoints = [
            "/swagger.json", "/swagger/v1/swagger.json", "/api/swagger.json",
            "/openapi.json", "/openapi/v1/openapi.json", "/api/openapi.json",
            "/docs/swagger.json", "/docs/openapi.json",
            "/api-docs", "/api/docs", "/documentation"
        ]
        
        discovered_specs = {}
        
        for spec_path in spec_endpoints:
            try:
                url = urljoin(self.base_url, spec_path)
                response = self.session.get(url, verify=False, timeout=10)
                
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', '')
                    
                    if 'application/json' in content_type:
                        try:
                            spec_data = response.json()
                            discovered_specs[spec_path] = {
                                "type": "openapi" if "openapi" in spec_data else "swagger",
                                "version": spec_data.get("openapi") or spec_data.get("swagger"),
                                "title": spec_data.get("info", {}).get("title"),
                                "description": spec_data.get("info", {}).get("description"),
                                "endpoints": self._extract_endpoints_from_spec(spec_data)
                            }
                            self.logger.info(f"Found API spec at {spec_path}")
                        except json.JSONDecodeError:
                            self.logger.warning(f"Invalid JSON at {spec_path}")
                    
                    elif 'text/html' in content_type:
                        # Check for Swagger UI
                        if 'swagger' in response.text.lower():
                            discovered_specs[spec_path] = {
                                "type": "swagger_ui",
                                "description": "Swagger UI documentation"
                            }
                            
            except Exception as e:
                self.logger.debug(f"Error checking {spec_path}: {e}")
        
        self.api_specs = discovered_specs
        return discovered_specs

    def _extract_endpoints_from_spec(self, spec_data: Dict) -> List[Dict]:
        """Extract endpoints from OpenAPI/Swagger specification."""
        endpoints = []
        
        paths = spec_data.get("paths", {})
        for path, methods in paths.items():
            for method, details in methods.items():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    endpoints.append({
                        "path": path,
                        "method": method.upper(),
                        "summary": details.get("summary"),
                        "description": details.get("description"),
                        "parameters": details.get("parameters", []),
                        "responses": details.get("responses", {})
                    })
        
        return endpoints

    def discover_common_patterns(self) -> List[ApiEndpoint]:
        """Discover API endpoints using common REST patterns."""
        self.logger.info("Discovering common API patterns...")
        
        discovered = []
        
        # Test common base paths
        for base_path in self.common_paths:
            endpoints = self._test_base_path(base_path)
            discovered.extend(endpoints)
        
        # Test resource patterns
        resource_patterns = self._generate_resource_patterns()
        for pattern in resource_patterns:
            endpoints = self._test_resource_pattern(pattern)
            discovered.extend(endpoints)
        
        self.discovered_endpoints = discovered
        return discovered

    def _test_base_path(self, base_path: str) -> List[ApiEndpoint]:
        """Test a base path for API endpoints."""
        endpoints = []
        url = urljoin(self.base_url, base_path)
        
        # Test different HTTP methods
        methods = ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]
        
        for method in methods:
            try:
                start_time = time.time()
                response = self.session.request(
                    method=method,
                    url=url,
                    verify=False,
                    timeout=10
                )
                response_time = time.time() - start_time
                
                if response.status_code in [200, 201, 204, 400, 401, 403, 404]:
                    endpoint = self._create_endpoint_object(
                        path=base_path,
                        method=method,
                        response=response,
                        response_time=response_time
                    )
                    endpoints.append(endpoint)
                    
            except Exception as e:
                self.logger.debug(f"Error testing {method} {base_path}: {e}")
        
        return endpoints

    def _generate_resource_patterns(self) -> List[str]:
        """Generate common REST resource patterns."""
        resources = [
            "users", "instances", "servers", "apps", "projects", "clouds",
            "groups", "tenants", "organizations", "networks", "volumes",
            "snapshots", "backups", "monitoring", "alerts", "logs",
            "tasks", "jobs", "workflows", "templates", "blueprints"
        ]
        
        patterns = []
        for resource in resources:
            patterns.extend([
                f"api/{resource}",
                f"api/v1/{resource}",
                f"api/v2/{resource}",
                f"rest/{resource}",
                f"rest/v1/{resource}",
                f"rest/v2/{resource}"
            ])
        
        return patterns

    def _test_resource_pattern(self, pattern: str) -> List[ApiEndpoint]:
        """Test a resource pattern for CRUD operations."""
        endpoints = []
        base_url = urljoin(self.base_url, pattern)
        
        # Test collection endpoints
        collection_methods = ["GET", "POST"]
        for method in collection_methods:
            try:
                start_time = time.time()
                response = self.session.request(
                    method=method,
                    url=base_url,
                    verify=False,
                    timeout=10
                )
                response_time = time.time() - start_time
                
                if response.status_code in [200, 201, 400, 401, 403, 404]:
                    endpoint = self._create_endpoint_object(
                        path=pattern,
                        method=method,
                        response=response,
                        response_time=response_time
                    )
                    endpoints.append(endpoint)
                    
            except Exception as e:
                self.logger.debug(f"Error testing {method} {pattern}: {e}")
        
        # Test individual resource endpoints (with ID)
        individual_methods = ["GET", "PUT", "DELETE"]
        for method in individual_methods:
            try:
                test_id = "test-id-123"
                resource_url = f"{base_url}/{test_id}"
                
                start_time = time.time()
                response = self.session.request(
                    method=method,
                    url=resource_url,
                    verify=False,
                    timeout=10
                )
                response_time = time.time() - start_time
                
                if response.status_code in [200, 201, 204, 400, 401, 403, 404]:
                    endpoint = self._create_endpoint_object(
                        path=f"{pattern}/{{id}}",
                        method=method,
                        response=response,
                        response_time=response_time
                    )
                    endpoints.append(endpoint)
                    
            except Exception as e:
                self.logger.debug(f"Error testing {method} {pattern}/{{id}}: {e}")
        
        return endpoints

    def _create_endpoint_object(self, path: str, method: str, response: requests.Response, 
                               response_time: float) -> ApiEndpoint:
        """Create a standardized endpoint object."""
        content_type = response.headers.get('content-type', '')
        response_size = len(response.content)
        
        # Parse response
        sample_response = None
        try:
            if 'application/json' in content_type:
                sample_response = response.json()
        except:
            pass
        
        # Detect features
        requires_auth = response.status_code == 401
        rate_limited = response.status_code == 429
        pagination = self._detect_pagination(response)
        filtering = self._detect_filtering(response)
        sorting = self._detect_sorting(response)
        
        # Extract query parameters from response headers or content
        query_params = self._extract_query_params(response)
        path_params = self._extract_path_params(path)
        
        return ApiEndpoint(
            path=path,
            method=method,
            status_code=response.status_code,
            response_time=response_time,
            content_type=content_type,
            response_size=response_size,
            requires_auth=requires_auth,
            rate_limited=rate_limited,
            pagination=pagination,
            filtering=filtering,
            sorting=sorting,
            sample_response=sample_response,
            error_responses=[],
            query_params=query_params,
            path_params=path_params
        )

    def _detect_pagination(self, response: requests.Response) -> bool:
        """Detect if response supports pagination."""
        # Check headers
        pagination_headers = ['x-pagination', 'link', 'x-total-count', 'x-page-count']
        for header in pagination_headers:
            if header in response.headers:
                return True
        
        # Check response content
        try:
            content = response.json()
            if isinstance(content, dict):
                pagination_keys = ['page', 'offset', 'limit', 'next', 'previous', 'total']
                return any(key in content for key in pagination_keys)
        except:
            pass
        
        return False

    def _detect_filtering(self, response: requests.Response) -> bool:
        """Detect if endpoint supports filtering."""
        # This would require testing with query parameters
        return False

    def _detect_sorting(self, response: requests.Response) -> bool:
        """Detect if endpoint supports sorting."""
        # This would require testing with sort parameters
        return False

    def _extract_query_params(self, response: requests.Response) -> List[str]:
        """Extract common query parameters from response."""
        # Common query parameters
        return ["limit", "offset", "page", "sort", "filter", "search", "q"]

    def _extract_path_params(self, path: str) -> List[str]:
        """Extract path parameters from URL pattern."""
        params = re.findall(r'\{(\w+)\}', path)
        return params

    def test_endpoints(self, endpoints: List[ApiEndpoint]) -> Dict[str, Any]:
        """Comprehensive testing of discovered endpoints."""
        self.logger.info("Testing discovered endpoints...")
        
        test_results = {
            "total_tested": 0,
            "successful": 0,
            "failed": 0,
            "rate_limited": 0,
            "auth_required": 0,
            "endpoint_tests": {}
        }
        
        for endpoint in endpoints:
            if endpoint.status_code in [200, 201, 204]:
                test_result = self._test_endpoint_functionality(endpoint)
                test_results["endpoint_tests"][f"{endpoint.method} {endpoint.path}"] = test_result
                test_results["total_tested"] += 1
                
                if test_result["success"]:
                    test_results["successful"] += 1
                else:
                    test_results["failed"] += 1
                
                if test_result.get("rate_limited"):
                    test_results["rate_limited"] += 1
                
                if test_result.get("auth_required"):
                    test_results["auth_required"] += 1
        
        return test_results

    def _test_endpoint_functionality(self, endpoint: ApiEndpoint) -> Dict[str, Any]:
        """Test specific functionality of an endpoint."""
        result = {
            "success": False,
            "response_time": 0,
            "rate_limited": False,
            "auth_required": False,
            "error": None,
            "test_details": {}
        }
        
        try:
            url = urljoin(self.base_url, endpoint.path)
            
            # Test with different payloads
            test_payloads = self._generate_test_payloads(endpoint)
            
            for payload_name, payload in test_payloads.items():
                start_time = time.time()
                response = self.session.request(
                    method=endpoint.method,
                    url=url,
                    json=payload if payload else None,
                    verify=False,
                    timeout=30
                )
                response_time = time.time() - start_time
                
                result["test_details"][payload_name] = {
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "success": response.status_code in [200, 201, 204]
                }
                
                if response.status_code == 429:
                    result["rate_limited"] = True
                elif response.status_code == 401:
                    result["auth_required"] = True
                
                # Update overall result
                if response.status_code in [200, 201, 204]:
                    result["success"] = True
                    result["response_time"] = response_time
                
        except Exception as e:
            result["error"] = str(e)
        
        return result

    def _generate_test_payloads(self, endpoint: ApiEndpoint) -> Dict[str, Any]:
        """Generate test payloads based on endpoint type."""
        payloads = {
            "empty": None,
            "minimal": {"name": "test"},
            "standard": {"name": "test", "description": "Test description"}
        }
        
        # Add specific payloads based on endpoint path
        if "users" in endpoint.path:
            payloads["user_specific"] = {
                "name": "test_user",
                "email": "test@example.com",
                "enabled": True
            }
        elif "instances" in endpoint.path:
            payloads["instance_specific"] = {
                "name": "test_instance",
                "type": "vm",
                "size": "small"
            }
        
        return payloads

    def generate_reports(self, test_results: Dict[str, Any]):
        """Generate comprehensive reports in multiple formats."""
        self.logger.info("Generating reports...")
        
        # Generate JSON report
        report_data = {
            "discovery_info": {
                "base_url": self.base_url,
                "discovered_at": datetime.now().isoformat(),
                "total_endpoints": len(self.discovered_endpoints),
                "api_specs": self.api_specs
            },
            "endpoints": [asdict(endpoint) for endpoint in self.discovered_endpoints],
            "test_results": test_results
        }
        
        with open(f"{self.output_dir}/api_discovery_report.json", "w") as f:
            json.dump(report_data, f, indent=2, default=str)
        
        # Generate YAML report
        with open(f"{self.output_dir}/api_discovery_report.yaml", "w") as f:
            yaml.dump(report_data, f, default_flow_style=False)
        
        # Generate markdown report
        self._generate_markdown_report(report_data)
        
        # Generate test scripts
        self._generate_test_scripts(report_data)

    def _generate_markdown_report(self, report_data: Dict[str, Any]):
        """Generate markdown report."""
        md_content = f"""# API Discovery Report

**Base URL:** {report_data['discovery_info']['base_url']}
**Discovered:** {report_data['discovery_info']['discovered_at']}
**Total Endpoints:** {report_data['discovery_info']['total_endpoints']}

## API Specifications Found

"""
        
        for spec_path, spec_info in report_data['discovery_info']['api_specs'].items():
            md_content += f"""### {spec_path}
- **Type:** {spec_info.get('type', 'Unknown')}
- **Version:** {spec_info.get('version', 'Unknown')}
- **Title:** {spec_info.get('title', 'Unknown')}

"""
        
        md_content += """## Discovered Endpoints

| Method | Path | Status | Auth Required | Rate Limited | Response Time |
|--------|------|--------|---------------|--------------|---------------|
"""
        
        for endpoint in report_data['endpoints']:
            md_content += f"| {endpoint['method']} | {endpoint['path']} | {endpoint['status_code']} | {endpoint['requires_auth']} | {endpoint['rate_limited']} | {endpoint['response_time']:.3f}s |\n"
        
        md_content += f"""

## Test Results

- **Total Tested:** {report_data['test_results']['total_tested']}
- **Successful:** {report_data['test_results']['successful']}
- **Failed:** {report_data['test_results']['failed']}
- **Rate Limited:** {report_data['test_results']['rate_limited']}
- **Auth Required:** {report_data['test_results']['auth_required']}

"""
        
        with open(f"{self.output_dir}/api_discovery_report.md", "w") as f:
            f.write(md_content)

    def _generate_test_scripts(self, report_data: Dict[str, Any]):
        """Generate test scripts for discovered endpoints."""
        # Python test script
        python_script = f"""#!/usr/bin/env python3
\"\"\"
Auto-generated API test script
Generated from discovery report
\"\"\"

import requests
import json
import time

BASE_URL = "{self.base_url}"
AUTH_CONFIG = {json.dumps(self.auth_config, indent=4)}

def setup_session():
    \"\"\"Setup authenticated session.\"\"\"
    session = requests.Session()
    
    # Apply authentication
    auth_type = AUTH_CONFIG.get("type")
    if auth_type == "bearer":
        session.headers["Authorization"] = f"Bearer {{AUTH_CONFIG['token']}}"
    elif auth_type == "basic":
        session.auth = (AUTH_CONFIG['username'], AUTH_CONFIG['password'])
    
    session.headers.update({{
        "Content-Type": "application/json",
        "Accept": "application/json"
    }})
    
    return session

def test_endpoint(session, method, path, payload=None):
    \"\"\"Test an API endpoint.\"\"\"
    url = f"{{BASE_URL}}{{path}}"
    
    try:
        start_time = time.time()
        response = session.request(
            method=method,
            url=url,
            json=payload,
            verify=False,
            timeout=30
        )
        response_time = time.time() - start_time
        
        print(f"{{method}} {{path}}: {{response.status_code}} ({{response_time:.3f}}s)")
        
        if response.status_code in [200, 201, 204]:
            return True, response.json() if response.content else None
        else:
            return False, response.text
            
    except Exception as e:
        print(f"Error testing {{method}} {{path}}: {{e}}")
        return False, str(e)

# Test discovered endpoints
session = setup_session()

print("Testing discovered endpoints...\\n")

"""
        
        for endpoint in report_data['endpoints']:
            if endpoint['status_code'] in [200, 201, 204]:
                python_script += f"""
# Test {endpoint['method']} {endpoint['path']}
success, result = test_endpoint(session, "{endpoint['method']}", "{endpoint['path']}")
if success:
    print(f"✅ {endpoint['method']} {endpoint['path']} - SUCCESS")
else:
    print(f"❌ {endpoint['method']} {endpoint['path']} - FAILED: {{result}}")
"""
        
        with open(f"{self.output_dir}/test_discovered_apis.py", "w") as f:
            f.write(python_script)

def main():
    parser = argparse.ArgumentParser(
        description="Universal API Discovery and Testing Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Discover HPE Morpheus API
  python universal_api_discovery.py --url https://morpheus.company.com --auth-type bearer --token YOUR_TOKEN

  # Test external API with basic auth
  python universal_api_discovery.py --url https://api.external.com --auth-type basic --username user --password pass --test-endpoints

  # Discover only (no testing)
  python universal_api_discovery.py --url https://api.example.com --auth-type bearer --token TOKEN --discover-only

  # Comprehensive discovery and testing
  python universal_api_discovery.py --url https://api.example.com --auth-type bearer --token TOKEN --test-endpoints --output-dir my_discovery
        """
    )
    
    parser.add_argument("--url", required=True, help="Base URL of the API")
    parser.add_argument("--auth-type", choices=["none", "bearer", "basic", "api_key", "oauth2"], 
                       default="none", help="Authentication type")
    parser.add_argument("--token", help="Bearer token or API key value")
    parser.add_argument("--username", help="Username for basic auth")
    parser.add_argument("--password", help="Password for basic auth")
    parser.add_argument("--key-name", default="X-API-Key", help="API key header name")
    parser.add_argument("--output-dir", default="api_discovery", help="Output directory for reports")
    parser.add_argument("--discover-only", action="store_true", help="Only discover endpoints, don't test")
    parser.add_argument("--test-endpoints", action="store_true", help="Test discovered endpoints")
    parser.add_argument("--concurrent", type=int, default=5, help="Number of concurrent requests")
    
    args = parser.parse_args()
    
    # Build auth configuration
    auth_config = {"type": args.auth_type}
    if args.auth_type == "bearer" and args.token:
        auth_config["token"] = args.token
    elif args.auth_type == "basic" and args.username and args.password:
        auth_config["username"] = args.username
        auth_config["password"] = args.password
    elif args.auth_type == "api_key" and args.token:
        auth_config["key_name"] = args.key_name
        auth_config["key_value"] = args.token
    
    # Initialize discovery framework
    discovery = UniversalApiDiscovery(args.url, auth_config, args.output_dir)
    
    print(f"🔍 Starting API discovery for: {args.url}")
    print(f"📁 Output directory: {args.output_dir}")
    print(f"🔐 Authentication: {args.auth_type}")
    print()
    
    # Discover API specifications
    specs = discovery.discover_api_specifications()
    if specs:
        print(f"📋 Found {len(specs)} API specification(s)")
    
    # Discover endpoints
    endpoints = discovery.discover_common_patterns()
    print(f"🔗 Discovered {len(endpoints)} endpoints")
    
    # Test endpoints if requested
    test_results = {}
    if args.test_endpoints and endpoints:
        print("🧪 Testing discovered endpoints...")
        test_results = discovery.test_endpoints(endpoints)
        print(f"✅ Testing complete: {test_results['successful']} successful, {test_results['failed']} failed")
    
    # Generate reports
    discovery.generate_reports(test_results)
    
    print(f"\n📊 Reports generated in: {args.output_dir}/")
    print("   - api_discovery_report.json (Raw data)")
    print("   - api_discovery_report.yaml (YAML format)")
    print("   - api_discovery_report.md (Markdown report)")
    print("   - test_discovered_apis.py (Test script)")

if __name__ == "__main__":
    main()