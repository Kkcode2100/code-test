# Universal API Discovery and Testing Framework

## 🎯 For Solution Architects in Hybrid Cloud Environments

This framework provides **industry-standard tools** to discover, analyze, and test APIs in hybrid cloud environments. It's specifically designed for solution architects who need to:

- **Validate POCs** with HPE Morpheus and external APIs
- **Assess integration capabilities** of third-party services
- **Compare API features** across multiple cloud platforms
- **Generate comprehensive documentation** for stakeholders

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Check Your Setup
```bash
python api_discovery_cli.py health
```

### 3. Discover HPE Morpheus API
```bash
python api_discovery_cli.py morpheus \
  --url https://your-morpheus-instance.com \
  --token YOUR_MORPHEUS_TOKEN
```

### 4. Test External API
```bash
python api_discovery_cli.py external \
  --url https://api.external-service.com \
  --auth-type bearer \
  --token YOUR_API_TOKEN
```

## 🛠️ Tools Overview

### 1. **Universal API Discovery** (`universal_api_discovery.py`)
**Industry-standard API discovery following OpenAPI, REST, and GraphQL patterns:**

- ✅ **OpenAPI/Swagger** specification discovery
- ✅ **REST API** pattern recognition  
- ✅ **Authentication** method detection
- ✅ **Rate limiting** analysis
- ✅ **Performance** testing
- ✅ **Concurrent** request handling

### 2. **Morpheus API Explorer** (`morpheus_api_explorer.py`)
**Specialized for HPE Morpheus integration:**

- ✅ **Morpheus-specific** endpoint discovery
- ✅ **Service plan** and pricing analysis
- ✅ **Infrastructure** resource mapping
- ✅ **Custom payload** generation

### 3. **Payload Analyzer** (`morpheus_payload_analyzer.py`)
**Deep payload structure analysis:**

- ✅ **Required vs optional** field detection
- ✅ **Data type** analysis
- ✅ **Validation rule** discovery
- ✅ **Example payload** generation

### 4. **Unified CLI** (`api_discovery_cli.py`)
**Easy-to-use interface for all tools:**

- ✅ **One-command** discovery workflows
- ✅ **Multi-API** comparison
- ✅ **Comprehensive** analysis options
- ✅ **Health checks** and validation

## 📊 What You Get

### Generated Reports
```
api_discovery/
├── api_discovery_report.json      # Raw discovery data
├── api_discovery_report.yaml      # YAML for automation
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

## 🏗️ Solution Architecture Workflows

### Workflow 1: New Integration Assessment
```bash
# 1. Discover API capabilities
python api_discovery_cli.py external \
  --url https://new-api.com \
  --auth-type bearer \
  --token TOKEN

# 2. Review generated reports
# 3. Create integration plan
```

### Workflow 2: Morpheus Feature Validation
```bash
# 1. Comprehensive Morpheus analysis
python api_discovery_cli.py morpheus-full \
  --url https://morpheus.company.com \
  --token YOUR_TOKEN

# 2. Validate specific features
# 3. Generate integration specs
```

### Workflow 3: Multi-Cloud API Comparison
```bash
# 1. Compare multiple APIs
python api_discovery_cli.py compare \
  --urls https://api1.com,https://api2.com \
  --tokens TOKEN1,TOKEN2

# 2. Analyze capabilities
# 3. Make architecture decisions
```

## 🔧 Industry Standard Features

### OpenAPI/Swagger Discovery
- Automatically finds `/swagger.json`, `/openapi.json`
- Extracts endpoint definitions and schemas
- Generates OpenAPI 3.0 specifications

### REST API Pattern Recognition
- Tests common REST patterns (`/api/v1/resources`)
- Discovers CRUD operations automatically
- Identifies pagination, filtering, and sorting capabilities

### Authentication Detection
- Bearer token authentication
- Basic authentication
- API key authentication
- OAuth2 support (framework ready)

### Rate Limiting Analysis
- Detects rate limiting headers
- Tests rate limit boundaries
- Provides rate limit recommendations

### Performance Testing
- Response time measurement
- Concurrent request testing
- Performance baseline establishment

## 📋 Use Cases for Solution Architects

### 1. **HPE Morpheus Integration POCs**
```bash
# Quick discovery
python api_discovery_cli.py morpheus \
  --url https://morpheus.company.com \
  --token YOUR_TOKEN

# Comprehensive analysis
python api_discovery_cli.py morpheus-full \
  --url https://morpheus.company.com \
  --token YOUR_TOKEN
```

### 2. **External API Assessment**
```bash
# Basic auth
python api_discovery_cli.py external \
  --url https://api.external-service.com \
  --auth-type basic \
  --username user \
  --password pass

# API key
python api_discovery_cli.py external \
  --url https://api.external-service.com \
  --auth-type api_key \
  --token YOUR_API_KEY
```

### 3. **Multi-API Comparison**
```bash
python api_discovery_cli.py compare \
  --urls https://aws-api.com,https://azure-api.com \
  --tokens AWS_TOKEN,AZURE_TOKEN \
  --auth-types bearer,bearer
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

## 🔍 Advanced Usage

### Direct Tool Usage
```bash
# Universal discovery
python universal_api_discovery.py \
  --url https://api.example.com \
  --auth-type bearer \
  --token TOKEN \
  --test-endpoints

# Morpheus exploration
python morpheus_api_explorer.py \
  --url https://morpheus.company.com \
  --token TOKEN

# Payload analysis
python morpheus_payload_analyzer.py \
  --url https://api.example.com \
  --token TOKEN \
  --endpoints users instances
```

### Custom Extensions
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
    python api_discovery_cli.py external \
      --url ${{ secrets.API_URL }} \
      --auth-type bearer \
      --token ${{ secrets.API_TOKEN }}
```

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

## 📄 License

This framework is designed for solution architects and follows industry standards for API discovery and testing.

---

**Note**: This framework follows industry standards and best practices for API discovery and testing. It's designed to help solution architects quickly assess and validate API capabilities in hybrid cloud environments.