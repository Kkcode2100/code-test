#!/usr/bin/env python3
"""
HPE Morpheus API Explorer Tool
A comprehensive tool to discover, document, and explore all available Morpheus API endpoints.
"""

import requests
import json
import logging
import argparse
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class MorpheusApiExplorer:
    """Comprehensive Morpheus API exploration and documentation tool."""
    
    def __init__(self, base_url: str, api_token: str, output_dir: str = "morpheus_api_docs"):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.output_dir = output_dir
        self.session = self._setup_session()
        self.discovered_endpoints = {}
        self.api_specs = {}
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f"{output_dir}/explorer.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _setup_session(self) -> requests.Session:
        """Setup requests session with retry logic and authentication."""
        session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Authentication headers
        session.headers.update({
            "Authorization": f"BEARER {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        
        return session

    def _make_request(self, method: str, endpoint: str, payload: Optional[Dict] = None, 
                     params: Optional[Dict] = None) -> Optional[Dict]:
        """Make HTTP request to Morpheus API with error handling."""
        url = f"{self.base_url}/api/{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=payload,
                params=params,
                verify=False,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json() if response.content else None
            elif response.status_code == 404:
                self.logger.debug(f"Endpoint not found: {method} {endpoint}")
                return None
            else:
                self.logger.warning(f"HTTP {response.status_code} for {method} {endpoint}: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error making request to {method} {endpoint}: {e}")
            return None

    def discover_api_endpoints(self) -> Dict[str, Any]:
        """Discover all available API endpoints by exploring common patterns."""
        self.logger.info("Starting API endpoint discovery...")
        
        # Common endpoint patterns in Morpheus
        endpoint_patterns = [
            # Core resources
            "instances", "apps", "servers", "hosts", "clusters", "datastores",
            "networks", "security-groups", "load-balancers", "backups",
            
            # Infrastructure
            "clouds", "groups", "zones", "pools", "folders", "resource-pools",
            
            # Provisioning
            "service-plans", "price-sets", "prices", "provision-types",
            
            # Users and Access
            "users", "roles", "permissions", "tenants", "accounts",
            
            # Monitoring and Operations
            "monitoring", "alerts", "logs", "tasks", "jobs", "executions",
            
            # Configuration
            "options", "settings", "config", "integrations", "credentials",
            
            # Advanced features
            "workflows", "automations", "scripts", "templates", "blueprints",
            "catalog", "orders", "approvals", "budgets", "costs",
            
            # Storage and Compute
            "volumes", "snapshots", "images", "floating-ips", "ssh-keys",
            
            # API and Development
            "api", "webhooks", "events", "notifications"
        ]
        
        discovered = {}
        
        for pattern in endpoint_patterns:
            self.logger.info(f"Exploring pattern: {pattern}")
            
            # Test GET request
            response = self._make_request("GET", pattern, params={"max": 1})
            if response:
                discovered[pattern] = {
                    "methods": ["GET"],
                    "sample_response": response,
                    "endpoint": pattern
                }
                
                # Test if POST is supported (create operation)
                test_payload = self._generate_test_payload(pattern)
                if test_payload:
                    post_response = self._make_request("POST", pattern, payload=test_payload)
                    if post_response and "error" not in str(post_response).lower():
                        discovered[pattern]["methods"].append("POST")
                        discovered[pattern]["create_payload"] = test_payload
                
                # Test if PUT is supported (update operation)
                put_response = self._make_request("PUT", pattern, payload={"id": 1})
                if put_response and "error" not in str(put_response).lower():
                    discovered[pattern]["methods"].append("PUT")
                
                # Test if DELETE is supported
                delete_response = self._make_request("DELETE", pattern)
                if delete_response and "error" not in str(delete_response).lower():
                    discovered[pattern]["methods"].append("DELETE")
        
        self.discovered_endpoints = discovered
        self.logger.info(f"Discovered {len(discovered)} endpoints")
        return discovered

    def _generate_test_payload(self, endpoint: str) -> Optional[Dict]:
        """Generate test payloads for different endpoint types."""
        payloads = {
            "instances": {
                "name": "test-instance",
                "description": "Test instance for API exploration"
            },
            "apps": {
                "name": "test-app",
                "description": "Test application"
            },
            "service-plans": {
                "name": "test-plan",
                "description": "Test service plan"
            },
            "price-sets": {
                "name": "test-price-set",
                "description": "Test price set"
            },
            "prices": {
                "name": "test-price",
                "code": "test.price.code",
                "priceType": "fixed"
            }
        }
        
        return payloads.get(endpoint, {"name": "test"})

    def analyze_endpoint_structure(self, endpoint: str) -> Dict[str, Any]:
        """Analyze the structure and capabilities of a specific endpoint."""
        self.logger.info(f"Analyzing endpoint structure: {endpoint}")
        
        analysis = {
            "endpoint": endpoint,
            "methods": [],
            "query_parameters": {},
            "response_structure": {},
            "pagination": False,
            "filtering": False,
            "sorting": False
        }
        
        # Test different HTTP methods
        methods = ["GET", "POST", "PUT", "DELETE"]
        for method in methods:
            response = self._make_request(method, endpoint)
            if response:
                analysis["methods"].append(method)
                
                if method == "GET":
                    # Analyze GET response structure
                    analysis["response_structure"] = self._analyze_response_structure(response)
                    
                    # Test pagination
                    paginated = self._make_request("GET", endpoint, params={"max": 5, "offset": 0})
                    if paginated and len(str(paginated)) > len(str(response)):
                        analysis["pagination"] = True
                    
                    # Test filtering
                    filtered = self._make_request("GET", endpoint, params={"phrase": "test"})
                    if filtered:
                        analysis["filtering"] = True
                    
                    # Test sorting
                    sorted_response = self._make_request("GET", endpoint, params={"sort": "name"})
                    if sorted_response:
                        analysis["sorting"] = True
        
        return analysis

    def _analyze_response_structure(self, response: Any) -> Dict[str, Any]:
        """Analyze the structure of an API response."""
        if isinstance(response, dict):
            structure = {}
            for key, value in response.items():
                if isinstance(value, list):
                    structure[key] = f"array[{len(value)} items]"
                    if value and isinstance(value[0], dict):
                        structure[f"{key}_sample"] = value[0]
                elif isinstance(value, dict):
                    structure[key] = "object"
                    structure[f"{key}_keys"] = list(value.keys())
                else:
                    structure[key] = type(value).__name__
            return structure
        elif isinstance(response, list):
            return {"type": "array", "count": len(response), "sample": response[0] if response else None}
        else:
            return {"type": type(response).__name__}

    def generate_api_documentation(self) -> None:
        """Generate comprehensive API documentation."""
        self.logger.info("Generating API documentation...")
        
        # Generate main documentation
        docs = {
            "generated_at": datetime.now().isoformat(),
            "base_url": self.base_url,
            "total_endpoints": len(self.discovered_endpoints),
            "endpoints": {}
        }
        
        for endpoint, info in self.discovered_endpoints.items():
            self.logger.info(f"Documenting endpoint: {endpoint}")
            analysis = self.analyze_endpoint_structure(endpoint)
            docs["endpoints"][endpoint] = analysis
        
        # Save comprehensive documentation
        with open(f"{self.output_dir}/api_documentation.json", "w") as f:
            json.dump(docs, f, indent=2, default=str)
        
        # Generate markdown documentation
        self._generate_markdown_docs(docs)
        
        # Generate OpenAPI/Swagger spec
        self._generate_openapi_spec(docs)
        
        self.logger.info(f"Documentation saved to {self.output_dir}/")

    def _generate_markdown_docs(self, docs: Dict[str, Any]) -> None:
        """Generate markdown documentation."""
        md_content = f"""# HPE Morpheus API Documentation

Generated on: {docs['generated_at']}
Base URL: {docs['base_url']}
Total Endpoints: {docs['total_endpoints']}

## Endpoints

"""
        
        for endpoint, info in docs["endpoints"].items():
            md_content += f"""### {endpoint}

**Methods:** {', '.join(info['methods'])}

**Endpoint:** `{info['endpoint']}`

**Capabilities:**
- Pagination: {'Yes' if info['pagination'] else 'No'}
- Filtering: {'Yes' if info['filtering'] else 'No'}
- Sorting: {'Yes' if info['sorting'] else 'No'}

**Response Structure:**
```json
{json.dumps(info['response_structure'], indent=2)}
```

**Example Usage:**
```bash
# GET request
curl -H "Authorization: BEARER {self.api_token}" \\
     -H "Content-Type: application/json" \\
     "{self.base_url}/api/{endpoint}"

# POST request (if supported)
curl -X POST \\
     -H "Authorization: BEARER {self.api_token}" \\
     -H "Content-Type: application/json" \\
     -d '{{"name": "test"}}' \\
     "{self.base_url}/api/{endpoint}"
```

---

"""
        
        with open(f"{self.output_dir}/api_documentation.md", "w") as f:
            f.write(md_content)

    def _generate_openapi_spec(self, docs: Dict[str, Any]) -> None:
        """Generate OpenAPI/Swagger specification."""
        openapi_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "HPE Morpheus API",
                "description": "Auto-generated API specification for HPE Morpheus",
                "version": "1.0.0"
            },
            "servers": [
                {"url": f"{self.base_url}/api"}
            ],
            "paths": {},
            "components": {
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer"
                    }
                }
            },
            "security": [{"bearerAuth": []}]
        }
        
        for endpoint, info in docs["endpoints"].items():
            path_item = {}
            
            if "GET" in info["methods"]:
                path_item["get"] = {
                    "summary": f"Get {endpoint}",
                    "parameters": [
                        {"name": "max", "in": "query", "schema": {"type": "integer"}},
                        {"name": "offset", "in": "query", "schema": {"type": "integer"}},
                        {"name": "phrase", "in": "query", "schema": {"type": "string"}}
                    ],
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            }
                        }
                    }
                }
            
            if "POST" in info["methods"]:
                path_item["post"] = {
                    "summary": f"Create {endpoint}",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Created successfully"
                        }
                    }
                }
            
            openapi_spec["paths"][f"/{endpoint}"] = path_item
        
        with open(f"{self.output_dir}/openapi_spec.json", "w") as f:
            json.dump(openapi_spec, f, indent=2)

    def generate_test_scripts(self) -> None:
        """Generate test scripts for all discovered endpoints."""
        self.logger.info("Generating test scripts...")
        
        # Python test script
        python_script = f"""#!/usr/bin/env python3
\"\"\"
Auto-generated Morpheus API test script
Generated on: {datetime.now().isoformat()}
\"\"\"

import requests
import json
import sys

BASE_URL = "{self.base_url}"
API_TOKEN = "{self.api_token}"

headers = {{
    "Authorization": f"BEARER {{API_TOKEN}}",
    "Content-Type": "application/json"
}}

def test_endpoint(endpoint, method="GET", payload=None):
    \"\"\"Test an API endpoint.\"\"\"
    url = f"{{BASE_URL}}/api/{{endpoint}}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, verify=False)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=payload, verify=False)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=payload, verify=False)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, verify=False)
        
        print(f"{{method}} {{endpoint}}: {{response.status_code}}")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error testing {{method}} {{endpoint}}: {{e}}")
        return None

# Test all discovered endpoints
"""
        
        for endpoint, info in self.discovered_endpoints.items():
            python_script += f"""
# Testing {endpoint}
print("\\n--- Testing {endpoint} ---")
result = test_endpoint("{endpoint}")
if result:
    print(f"Response keys: {{list(result.keys()) if isinstance(result, dict) else 'Not a dict'}}")
"""
        
        with open(f"{self.output_dir}/test_api.py", "w") as f:
            f.write(python_script)
        
        # Bash test script
        bash_script = f"""#!/bin/bash
# Auto-generated Morpheus API test script
# Generated on: {datetime.now().isoformat()}

BASE_URL="{self.base_url}"
API_TOKEN="{self.api_token}"

echo "Testing Morpheus API endpoints..."

"""
        
        for endpoint, info in self.discovered_endpoints.items():
            bash_script += f"""
echo "Testing {endpoint}..."
curl -s -w "\\nHTTP Status: %{{http_code}}\\n" \\
     -H "Authorization: BEARER $API_TOKEN" \\
     -H "Content-Type: application/json" \\
     "$BASE_URL/api/{endpoint}" | jq '.' 2>/dev/null || echo "Response not JSON"
echo "---"
"""
        
        with open(f"{self.output_dir}/test_api.sh", "w") as f:
            f.write(bash_script)
        
        # Make bash script executable
        os.chmod(f"{self.output_dir}/test_api.sh", 0o755)

def main():
    parser = argparse.ArgumentParser(description="HPE Morpheus API Explorer")
    parser.add_argument("--url", required=True, help="Morpheus base URL")
    parser.add_argument("--token", required=True, help="Morpheus API token")
    parser.add_argument("--output-dir", default="morpheus_api_docs", help="Output directory for documentation")
    parser.add_argument("--discover-only", action="store_true", help="Only discover endpoints, don't generate docs")
    
    args = parser.parse_args()
    
    explorer = MorpheusApiExplorer(args.url, args.token, args.output_dir)
    
    # Discover endpoints
    endpoints = explorer.discover_api_endpoints()
    
    if not args.discover_only:
        # Generate documentation
        explorer.generate_api_documentation()
        explorer.generate_test_scripts()
    
    print(f"\nDiscovery complete! Found {len(endpoints)} endpoints.")
    print(f"Documentation saved to: {args.output_dir}/")

if __name__ == "__main__":
    main()