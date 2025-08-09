# Universal API Discovery and Testing Framework
## Industry-Standard Approach for Hybrid Cloud Integration

This framework provides solution architects with industry-standard tools to discover, analyze, and test APIs in hybrid cloud environments. It follows established patterns for OpenAPI, REST API, and GraphQL discovery.

## 🎯 Use Cases for Solution Architects

### 1. **HPE Morpheus Integration POCs**
- Discover all available Morpheus API endpoints
- Understand payload structures and requirements
- Test integration scenarios before implementation
- Generate comprehensive documentation for stakeholders

### 2. **External API Integration**
- Rapidly assess third-party API capabilities
- Understand authentication methods and rate limits
- Test API compatibility with your infrastructure
- Generate integration specifications

### 3. **Hybrid Cloud Platform Assessment**
- Evaluate multiple cloud provider APIs
- Compare API capabilities across platforms
- Identify integration patterns and best practices
- Document API landscapes for architecture decisions

## 🛠️ Tools Overview

### 1. **Universal API Discovery** (`universal_api_discovery.py`)
**Industry Standard Features:**
- OpenAPI/Swagger specification discovery
- REST API pattern recognition
- GraphQL introspection support
- Rate limiting detection
- Authentication method detection
- Concurrent request handling

### 2. **Morpheus API Explorer** (`morpheus_api_explorer.py`)
**Specialized for HPE Morpheus:**
- Morpheus-specific endpoint discovery
- Service plan and pricing analysis
- Infrastructure resource mapping
- Custom payload generation

### 3. **Payload Analyzer** (`morpheus_payload_analyzer.py`)
**Deep Payload Analysis:**
- Required vs optional field detection
- Data type analysis
- Validation rule discovery
- Example payload generation

## 🚀 Quick Start Guide

### Prerequisites
```bash
pip install -r requirements.txt
```

### 1. Discover HPE Morpheus API
```bash
# Basic discovery
python universal_api_discovery.py \
  --url https://your-morpheus-instance.com \
  --auth-type bearer \
  --token YOUR_MORPHEUS_TOKEN

# Comprehensive discovery with testing
python universal_api_discovery.py \
  --url https://your-morpheus-instance.com \
  --auth-type bearer \
  --token YOUR_MORPHEUS_TOKEN \
  --test-endpoints \
  --output-dir morpheus_discovery
```

### 2. Discover External API
```bash
# Basic auth
python universal_api_discovery.py \
  --url https://api.external-service.com \
  --auth-type basic \
  --username your_username \
  --password your_password

# API key authentication
python universal_api_discovery.py \
  --url https://api.external-service.com \
  --auth-type api_key \
  --token YOUR_API_KEY \
  --key-name X-API-Key
```

### 3. Specialized Morpheus Analysis
```bash
# Discover Morpheus endpoints
python morpheus_api_explorer.py \
  --url https://your-morpheus-instance.com \
  --token YOUR_MORPHEUS_TOKEN

# Analyze payloads
python morpheus_payload_analyzer.py \
  --url https://your-morpheus-instance.com \
  --token YOUR_MORPHEUS_TOKEN \
  --endpoints instances apps service-plans
```

## 📊 Output and Reports

### Generated Files
```
api_discovery/
├── api_discovery_report.json      # Raw discovery data
├── api_discovery_report.yaml      # YAML format for automation
├── api_discovery_report.md        # Human-readable report
├── test_discovered_apis.py        # Generated test scripts
└── discovery.log                  # Detailed logs
```

### Report Contents
- **API Specifications**: OpenAPI/Swagger docs found
- **Endpoint Discovery**: All discovered endpoints with methods
- **Authentication**: Required auth methods detected
- **Rate Limiting**: Rate limit detection and analysis
- **Performance**: Response times and performance metrics
- **Testing Results**: Success/failure rates for endpoint testing

## 🔧 Industry Standard Features

### 1. **OpenAPI/Swagger Discovery**
- Automatically finds `/swagger.json`, `/openapi.json`
- Extracts endpoint definitions and schemas
- Generates OpenAPI 3.0 specifications

### 2. **REST API Pattern Recognition**
- Tests common REST patterns (`/api/v1/resources`)
- Discovers CRUD operations automatically
- Identifies pagination, filtering, and sorting capabilities

### 3. **Authentication Detection**
- Bearer token authentication
- Basic authentication
- API key authentication
- OAuth2 support (framework ready)

### 4. **Rate Limiting Analysis**
- Detects rate limiting headers
- Tests rate limit boundaries
- Provides rate limit recommendations

### 5. **Performance Testing**
- Response time measurement
- Concurrent request testing
- Performance baseline establishment

## 🏗️ Solution Architecture Workflows

### Workflow 1: New Integration Assessment
```bash
# 1. Discover API capabilities
python universal_api_discovery.py --url https://new-api.com --auth-type bearer --token TOKEN

# 2. Analyze specific endpoints
python morpheus_payload_analyzer.py --url https://new-api.com --token TOKEN --endpoints users instances

# 3. Generate integration specs
# Review generated reports and create integration plan
```

### Workflow 2: Morpheus Feature Validation
```bash
# 1. Discover Morpheus capabilities
python morpheus_api_explorer.py --url https://morpheus.company.com --token TOKEN

# 2. Test specific features
python universal_api_discovery.py --url https://morpheus.company.com --token TOKEN --test-endpoints

# 3. Validate integration requirements
# Use generated test scripts to validate POC requirements
```

### Workflow 3: Multi-Cloud API Comparison
```bash
# 1. Discover AWS APIs
python universal_api_discovery.py --url https://ec2.amazonaws.com --auth-type api_key --token AWS_KEY

# 2. Discover Azure APIs
python universal_api_discovery.py --url https://management.azure.com --auth-type bearer --token AZURE_TOKEN

# 3. Compare capabilities
# Analyze generated reports for feature comparison
```

## 📋 Best Practices for Solution Architects

### 1. **Discovery Strategy**
- Start with specification discovery (OpenAPI/Swagger)
- Use pattern-based discovery for undocumented APIs
- Test authentication methods early
- Document rate limits and quotas

### 2. **Testing Approach**
- Test with minimal payloads first
- Validate error handling and edge cases
- Measure performance under load
- Document integration patterns

### 3. **Documentation Standards**
- Generate OpenAPI specifications
- Create integration guides
- Document authentication flows
- Provide example implementations

### 4. **Security Considerations**
- Validate authentication methods
- Test authorization boundaries
- Document security requirements
- Follow least privilege principles

## 🔍 Advanced Usage

### Custom Endpoint Discovery
```python
# Add custom patterns to discovery
custom_patterns = [
    "api/v1/custom-resource",
    "rest/v2/special-endpoint"
]

# Extend the discovery framework
```

### Integration with CI/CD
```yaml
# GitHub Actions example
- name: API Discovery
  run: |
    python universal_api_discovery.py \
      --url ${{ secrets.API_URL }} \
      --auth-type bearer \
      --token ${{ secrets.API_TOKEN }} \
      --test-endpoints
```

### Automated Testing
```bash
# Run generated test scripts
python test_discovered_apis.py

# Integrate with testing frameworks
pytest test_discovered_apis.py
```

## 🎯 POC Validation Checklist

### Before Integration
- [ ] API endpoints discovered and documented
- [ ] Authentication methods validated
- [ ] Rate limits understood and planned for
- [ ] Error handling patterns documented
- [ ] Performance baselines established

### During Integration
- [ ] Use generated test scripts for validation
- [ ] Monitor rate limiting and performance
- [ ] Validate error scenarios
- [ ] Test authentication flows

### After Integration
- [ ] Update documentation with learnings
- [ ] Share integration patterns with team
- [ ] Plan for production scaling
- [ ] Document operational procedures

## 📞 Support and Extensions

### Custom Extensions
The framework is designed for extensibility:
- Add custom authentication methods
- Extend endpoint discovery patterns
- Customize payload generation
- Integrate with monitoring tools

### Integration Examples
- **Ansible**: Use generated YAML for automation
- **Terraform**: Reference API specs for provider development
- **Kubernetes**: Generate CRDs from API specifications
- **Monitoring**: Use performance data for alerting

## 🔗 Related Resources

- [OpenAPI Specification](https://swagger.io/specification/)
- [REST API Design Guidelines](https://restfulapi.net/)
- [HPE Morpheus API Documentation](https://docs.morpheusdata.com/)
- [API Testing Best Practices](https://www.postman.com/api-testing/)

---

**Note**: This framework follows industry standards and best practices for API discovery and testing. It's designed to help solution architects quickly assess and validate API capabilities in hybrid cloud environments.