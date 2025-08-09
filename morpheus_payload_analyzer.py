#!/usr/bin/env python3
"""
HPE Morpheus API Payload Analyzer
A specialized tool to analyze API payloads, understand required fields, data types, and generate examples.
"""

import requests
import json
import logging
import argparse
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class MorpheusPayloadAnalyzer:
    """Analyze Morpheus API payloads and generate comprehensive documentation."""
    
    def __init__(self, base_url: str, api_token: str, output_dir: str = "payload_analysis"):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.output_dir = output_dir
        self.session = self._setup_session()
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f"{output_dir}/analyzer.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _setup_session(self) -> requests.Session:
        """Setup requests session with retry logic and authentication."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        session.headers.update({
            "Authorization": f"BEARER {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        
        return session

    def _make_request(self, method: str, endpoint: str, payload: Optional[Dict] = None, 
                     params: Optional[Dict] = None) -> Optional[Dict]:
        """Make HTTP request to Morpheus API."""
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
            
            if response.status_code in [200, 201]:
                return response.json() if response.content else None
            elif response.status_code == 400:
                # Bad request - might give us validation error details
                return {"error": response.text, "status_code": 400}
            else:
                self.logger.debug(f"HTTP {response.status_code} for {method} {endpoint}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error making request to {method} {endpoint}: {e}")
            return None

    def analyze_endpoint_payloads(self, endpoint: str) -> Dict[str, Any]:
        """Analyze payloads for a specific endpoint."""
        self.logger.info(f"Analyzing payloads for endpoint: {endpoint}")
        
        analysis = {
            "endpoint": endpoint,
            "get_response_structure": {},
            "post_payload_structure": {},
            "put_payload_structure": {},
            "required_fields": {},
            "optional_fields": {},
            "data_types": {},
            "validation_rules": {},
            "example_payloads": {}
        }
        
        # Analyze GET response structure
        get_response = self._make_request("GET", endpoint, params={"max": 1})
        if get_response:
            analysis["get_response_structure"] = self._analyze_data_structure(get_response)
        
        # Analyze POST payload requirements
        post_analysis = self._analyze_post_payloads(endpoint)
        analysis.update(post_analysis)
        
        # Analyze PUT payload requirements
        put_analysis = self._analyze_put_payloads(endpoint)
        analysis.update(put_analysis)
        
        return analysis

    def _analyze_data_structure(self, data: Any, path: str = "") -> Dict[str, Any]:
        """Recursively analyze data structure and types."""
        if isinstance(data, dict):
            structure = {}
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                structure[key] = {
                    "type": type(value).__name__,
                    "path": current_path,
                    "sample_value": value
                }
                
                if isinstance(value, dict):
                    structure[key]["nested_structure"] = self._analyze_data_structure(value, current_path)
                elif isinstance(value, list) and value:
                    structure[key]["array_item_type"] = type(value[0]).__name__
                    if isinstance(value[0], dict):
                        structure[key]["array_item_structure"] = self._analyze_data_structure(value[0], f"{current_path}[0]")
            
            return structure
        elif isinstance(data, list):
            if data:
                return {
                    "type": "array",
                    "count": len(data),
                    "item_type": type(data[0]).__name__,
                    "sample_item": self._analyze_data_structure(data[0], f"{path}[0]")
                }
            else:
                return {"type": "array", "count": 0}
        else:
            return {
                "type": type(data).__name__,
                "sample_value": data
            }

    def _analyze_post_payloads(self, endpoint: str) -> Dict[str, Any]:
        """Analyze POST payload requirements through trial and error."""
        analysis = {
            "post_payload_structure": {},
            "post_required_fields": set(),
            "post_optional_fields": set(),
            "post_data_types": {},
            "post_validation_rules": {},
            "post_example_payloads": {}
        }
        
        # Get sample data from GET request to understand structure
        sample_data = self._make_request("GET", endpoint, params={"max": 1})
        if not sample_data:
            return analysis
        
        # Extract sample item if it's a list
        if isinstance(sample_data, dict) and any(isinstance(v, list) for v in sample_data.values()):
            for key, value in sample_data.items():
                if isinstance(value, list) and value:
                    sample_item = value[0]
                    break
        else:
            sample_item = sample_data
        
        if not isinstance(sample_item, dict):
            return analysis
        
        # Analyze each field by testing with and without it
        for field_name, field_value in sample_item.items():
            if field_name in ['id', 'dateCreated', 'lastUpdated', 'createdBy', 'updatedBy']:
                # Skip system fields
                continue
            
            self.logger.info(f"Testing POST field: {field_name}")
            
            # Test payload without this field
            test_payload = {k: v for k, v in sample_item.items() 
                          if k != field_name and k not in ['id', 'dateCreated', 'lastUpdated', 'createdBy', 'updatedBy']}
            
            response_without = self._make_request("POST", endpoint, payload=test_payload)
            
            # Test payload with this field
            test_payload[field_name] = field_value
            response_with = self._make_request("POST", endpoint, payload=test_payload)
            
            # Determine if field is required
            if response_without and "error" in str(response_without).lower():
                if response_with and "error" not in str(response_with).lower():
                    analysis["post_required_fields"].add(field_name)
                else:
                    analysis["post_optional_fields"].add(field_name)
            else:
                analysis["post_optional_fields"].add(field_name)
            
            # Record data type
            analysis["post_data_types"][field_name] = type(field_value).__name__
        
        # Generate example payloads
        analysis["post_example_payloads"] = self._generate_example_payloads(endpoint, sample_item, "POST")
        
        return analysis

    def _analyze_put_payloads(self, endpoint: str) -> Dict[str, Any]:
        """Analyze PUT payload requirements."""
        analysis = {
            "put_payload_structure": {},
            "put_required_fields": set(),
            "put_optional_fields": set(),
            "put_data_types": {},
            "put_validation_rules": {},
            "put_example_payloads": {}
        }
        
        # Get existing items for PUT testing
        existing_items = self._make_request("GET", endpoint, params={"max": 1})
        if not existing_items:
            return analysis
        
        # Extract sample item
        if isinstance(existing_items, dict) and any(isinstance(v, list) for v in existing_items.values()):
            for key, value in existing_items.items():
                if isinstance(value, list) and value:
                    sample_item = value[0]
                    break
        else:
            sample_item = existing_items
        
        if not isinstance(sample_item, dict) or 'id' not in sample_item:
            return analysis
        
        item_id = sample_item['id']
        
        # Test PUT with minimal payload
        minimal_payload = {"id": item_id, "name": sample_item.get('name', 'test')}
        response = self._make_request("PUT", f"{endpoint}/{item_id}", payload=minimal_payload)
        
        if response and "error" not in str(response).lower():
            analysis["put_required_fields"].add("id")
            analysis["put_optional_fields"].add("name")
        
        # Generate example payloads
        analysis["put_example_payloads"] = self._generate_example_payloads(endpoint, sample_item, "PUT", item_id)
        
        return analysis

    def _generate_example_payloads(self, endpoint: str, sample_data: Dict, method: str, item_id: Optional[int] = None) -> Dict[str, Any]:
        """Generate example payloads for different scenarios."""
        examples = {}
        
        # Minimal payload
        minimal_fields = ["name"]
        minimal_payload = {k: v for k, v in sample_data.items() if k in minimal_fields}
        if method == "PUT" and item_id:
            minimal_payload["id"] = item_id
        examples["minimal"] = minimal_payload
        
        # Standard payload (common fields)
        standard_fields = ["name", "description", "enabled", "code"]
        standard_payload = {k: v for k, v in sample_data.items() if k in standard_fields}
        if method == "PUT" and item_id:
            standard_payload["id"] = item_id
        examples["standard"] = standard_payload
        
        # Full payload (all non-system fields)
        full_payload = {k: v for k, v in sample_data.items() 
                       if k not in ['id', 'dateCreated', 'lastUpdated', 'createdBy', 'updatedBy']}
        if method == "PUT" and item_id:
            full_payload["id"] = item_id
        examples["full"] = full_payload
        
        return examples

    def analyze_all_endpoints(self, endpoints: List[str]) -> Dict[str, Any]:
        """Analyze payloads for all specified endpoints."""
        self.logger.info(f"Starting payload analysis for {len(endpoints)} endpoints")
        
        all_analysis = {
            "generated_at": datetime.now().isoformat(),
            "base_url": self.base_url,
            "endpoints": {}
        }
        
        for endpoint in endpoints:
            try:
                analysis = self.analyze_endpoint_payloads(endpoint)
                all_analysis["endpoints"][endpoint] = analysis
                self.logger.info(f"Completed analysis for {endpoint}")
            except Exception as e:
                self.logger.error(f"Error analyzing {endpoint}: {e}")
                all_analysis["endpoints"][endpoint] = {"error": str(e)}
        
        return all_analysis

    def generate_payload_documentation(self, analysis: Dict[str, Any]) -> None:
        """Generate comprehensive payload documentation."""
        self.logger.info("Generating payload documentation...")
        
        # Save raw analysis
        with open(f"{self.output_dir}/payload_analysis.json", "w") as f:
            json.dump(analysis, f, indent=2, default=str)
        
        # Generate markdown documentation
        self._generate_payload_markdown(analysis)
        
        # Generate example scripts
        self._generate_example_scripts(analysis)
        
        self.logger.info(f"Payload documentation saved to {self.output_dir}/")

    def _generate_payload_markdown(self, analysis: Dict[str, Any]) -> None:
        """Generate markdown documentation for payloads."""
        md_content = f"""# HPE Morpheus API Payload Analysis

Generated on: {analysis['generated_at']}
Base URL: {analysis['base_url']}

## Endpoint Payload Analysis

"""
        
        for endpoint, endpoint_analysis in analysis["endpoints"].items():
            if "error" in endpoint_analysis:
                md_content += f"""### {endpoint}

**Error:** {endpoint_analysis['error']}

---
"""
                continue
            
            md_content += f"""### {endpoint}

#### GET Response Structure
```json
{json.dumps(endpoint_analysis.get('get_response_structure', {}), indent=2)}
```

#### POST Payload Analysis

**Required Fields:**
{chr(10).join(f"- `{field}` ({endpoint_analysis.get('post_data_types', {}).get(field, 'unknown')})" for field in endpoint_analysis.get('post_required_fields', []))}

**Optional Fields:**
{chr(10).join(f"- `{field}` ({endpoint_analysis.get('post_data_types', {}).get(field, 'unknown')})" for field in endpoint_analysis.get('post_optional_fields', []))}

**Example Payloads:**

**Minimal:**
```json
{json.dumps(endpoint_analysis.get('post_example_payloads', {}).get('minimal', {}), indent=2)}
```

**Standard:**
```json
{json.dumps(endpoint_analysis.get('post_example_payloads', {}).get('standard', {}), indent=2)}
```

**Full:**
```json
{json.dumps(endpoint_analysis.get('post_example_payloads', {}).get('full', {}), indent=2)}
```

#### PUT Payload Analysis

**Required Fields:**
{chr(10).join(f"- `{field}` ({endpoint_analysis.get('put_data_types', {}).get(field, 'unknown')})" for field in endpoint_analysis.get('put_required_fields', []))}

**Optional Fields:**
{chr(10).join(f"- `{field}` ({endpoint_analysis.get('put_data_types', {}).get(field, 'unknown')})" for field in endpoint_analysis.get('put_optional_fields', []))}

**Example Payloads:**

**Minimal:**
```json
{json.dumps(endpoint_analysis.get('put_example_payloads', {}).get('minimal', {}), indent=2)}
```

**Standard:**
```json
{json.dumps(endpoint_analysis.get('put_example_payloads', {}).get('standard', {}), indent=2)}
```

**Full:**
```json
{json.dumps(endpoint_analysis.get('put_example_payloads', {}).get('full', {}), indent=2)}
```

---

"""
        
        with open(f"{self.output_dir}/payload_documentation.md", "w") as f:
            f.write(md_content)

    def _generate_example_scripts(self, analysis: Dict[str, Any]) -> None:
        """Generate example scripts for all endpoints."""
        python_script = f"""#!/usr/bin/env python3
\"\"\"
Auto-generated Morpheus API payload examples
Generated on: {analysis['generated_at']}
\"\"\"

import requests
import json

BASE_URL = "{self.base_url}"
API_TOKEN = "{self.api_token}"

headers = {{
    "Authorization": f"BEARER {{API_TOKEN}}",
    "Content-Type": "application/json"
}}

def make_request(method, endpoint, payload=None):
    \"\"\"Make API request.\"\"\"
    url = f"{{BASE_URL}}/api/{{endpoint}}"
    
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=payload,
            verify=False
        )
        print(f"{{method}} {{endpoint}}: {{response.status_code}}")
        if response.status_code in [200, 201]:
            return response.json()
        else:
            print(f"Error: {{response.text}}")
            return None
    except Exception as e:
        print(f"Exception: {{e}}")
        return None

# Example API calls based on payload analysis
"""
        
        for endpoint, endpoint_analysis in analysis["endpoints"].items():
            if "error" in endpoint_analysis:
                continue
            
            python_script += f"""
# {endpoint} examples
print("\\n--- {endpoint} Examples ---")

# GET {endpoint}
{endpoint}_data = make_request("GET", "{endpoint}")

# POST {endpoint} - Minimal
{endpoint}_minimal_payload = {json.dumps(endpoint_analysis.get('post_example_payloads', {}).get('minimal', {}), indent=8)}
make_request("POST", "{endpoint}", {endpoint}_minimal_payload)

# POST {endpoint} - Standard
{endpoint}_standard_payload = {json.dumps(endpoint_analysis.get('post_example_payloads', {}).get('standard', {}), indent=8)}
make_request("POST", "{endpoint}", {endpoint}_standard_payload)
"""
        
        with open(f"{self.output_dir}/example_scripts.py", "w") as f:
            f.write(python_script)

def main():
    parser = argparse.ArgumentParser(description="HPE Morpheus API Payload Analyzer")
    parser.add_argument("--url", required=True, help="Morpheus base URL")
    parser.add_argument("--token", required=True, help="Morpheus API token")
    parser.add_argument("--output-dir", default="payload_analysis", help="Output directory")
    parser.add_argument("--endpoints", nargs="+", help="Specific endpoints to analyze")
    
    args = parser.parse_args()
    
    # Default endpoints if none specified
    if not args.endpoints:
        args.endpoints = [
            "instances", "apps", "servers", "service-plans", "price-sets", 
            "prices", "clouds", "groups", "users", "roles"
        ]
    
    analyzer = MorpheusPayloadAnalyzer(args.url, args.token, args.output_dir)
    
    # Analyze all endpoints
    analysis = analyzer.analyze_all_endpoints(args.endpoints)
    
    # Generate documentation
    analyzer.generate_payload_documentation(analysis)
    
    print(f"\nPayload analysis complete!")
    print(f"Documentation saved to: {args.output_dir}/")

if __name__ == "__main__":
    main()