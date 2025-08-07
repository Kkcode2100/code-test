#!/usr/bin/env python3

import requests
import subprocess
import json
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_access_token():
    """Get GCP access token using gcloud CLI."""
    try:
        logger.info("Fetching GCP access token from gcloud CLI...")
        env = os.environ.copy()
        if "GOOGLE_APPLICATION_CREDENTIALS" in env and os.path.exists(env["GOOGLE_APPLICATION_CREDENTIALS"]):
            logger.info(f"Using service account from GOOGLE_APPLICATION_CREDENTIALS.")
            env["CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"] = env["GOOGLE_APPLICATION_CREDENTIALS"]
        
        result = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True, env=env)
        token = result.stdout.strip()
        logger.info("Successfully obtained GCP access token.")
        return token
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get access token: {e}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        raise

def get_services(access_token):
    """Get all available GCP services."""
    url = "https://cloudbilling.googleapis.com/v1/services"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get('services', [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get services: {e}")
        raise

def main():
    """Main function to debug GCP services."""
    try:
        # Get access token
        access_token = get_access_token()
        
        # Get all services
        services = get_services(access_token)
        
        logger.info(f"Found {len(services)} total services")
        
        # Look for Compute Engine service
        compute_services = []
        for service in services:
            service_id = service.get('serviceId', '')
            display_name = service.get('displayName', '')
            name = service.get('name', '')
            
            # Check if this looks like Compute Engine
            if ('compute' in display_name.lower() or 
                'compute' in name.lower() or
                service_id == '6F81-5844-456A'):
                compute_services.append({
                    'serviceId': service_id,
                    'displayName': display_name,
                    'name': name
                })
        
        logger.info(f"Found {len(compute_services)} potential Compute Engine services:")
        for service in compute_services:
            logger.info(f"  Service ID: {service['serviceId']}")
            logger.info(f"  Display Name: {service['displayName']}")
            logger.info(f"  Name: {service['name']}")
            logger.info("  ---")
        
        # Also show first 10 services for reference
        logger.info("First 10 services for reference:")
        for i, service in enumerate(services[:10]):
            logger.info(f"  {i+1}. {service.get('displayName', 'N/A')} (ID: {service.get('serviceId', 'N/A')})")
        
        # Save all services to file for inspection
        with open('gcp_services_debug.json', 'w') as f:
            json.dump(services, f, indent=2)
        logger.info("All services saved to gcp_services_debug.json")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())