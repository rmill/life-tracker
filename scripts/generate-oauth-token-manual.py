#!/usr/bin/env python3
"""
Generate Google Fit OAuth token using manual authorization code.
"""
import sys
import json
import boto3
from urllib.parse import urlparse, parse_qs
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

def get_credentials_from_ssm():
    """Get client ID and secret from SSM."""
    ssm = boto3.client('ssm', region_name='us-west-2')
    
    client_id = ssm.get_parameter(
        Name='/life-stats/google-fit/client-id',
        WithDecryption=True
    )['Parameter']['Value']
    
    client_secret = ssm.get_parameter(
        Name='/life-stats/google-fit/client-secret',
        WithDecryption=True
    )['Parameter']['Value']
    
    return client_id, client_secret

def exchange_code_for_token(client_id, client_secret, code):
    """Exchange authorization code for access token."""
    import requests
    
    token_url = 'https://oauth2.googleapis.com/token'
    data = {
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': 'http://localhost:8080/',
        'grant_type': 'authorization_code'
    }
    
    response = requests.post(token_url, data=data)
    response.raise_for_status()
    return response.json()

def main():
    if len(sys.argv) < 2:
        print("Usage: python generate-oauth-token-manual.py <authorization_url>")
        print("Example: python generate-oauth-token-manual.py 'http://localhost:8080/?code=...'")
        sys.exit(1)
    
    auth_url = sys.argv[1]
    
    print("Google Fit OAuth Token Generator (Manual)")
    print("=" * 50)
    
    user_id = input("Enter user ID (default: zerocool): ").strip()
    if not user_id:
        user_id = "zerocool"
        print(f"Using default user ID: {user_id}")
    
    # Parse authorization code from URL
    parsed = urlparse(auth_url)
    params = parse_qs(parsed.query)
    code = params.get('code', [None])[0]
    
    if not code:
        print("Error: No authorization code found in URL")
        sys.exit(1)
    
    print(f"\n✓ Authorization code extracted")
    print(f"Fetching client credentials from SSM...")
    
    try:
        client_id, client_secret = get_credentials_from_ssm()
    except Exception as e:
        print(f"Error: Could not fetch credentials from SSM: {e}")
        sys.exit(1)
    
    print("Exchanging code for access token...")
    
    try:
        token_data = exchange_code_for_token(client_id, client_secret, code)
    except Exception as e:
        print(f"Error: Could not exchange code for token: {e}")
        sys.exit(1)
    
    print(f"✓ Token received!")
    
    # Store token in SSM
    print(f"Storing credentials in SSM for user '{user_id}'...")
    
    ssm = boto3.client('ssm', region_name='us-west-2')
    
    creds_data = {
        'token': token_data['access_token'],
        'refresh_token': token_data.get('refresh_token'),
        'token_uri': 'https://oauth2.googleapis.com/token',
        'client_id': client_id,
        'client_secret': client_secret,
        'scopes': [
            'https://www.googleapis.com/auth/fitness.activity.read',
            'https://www.googleapis.com/auth/fitness.body.read'
        ]
    }
    
    ssm.put_parameter(
        Name=f'/life-stats/google-fit/{user_id}/token',
        Value=json.dumps(creds_data),
        Type='SecureString',
        Overwrite=True
    )
    
    print(f"✓ Token stored successfully!")
    print(f"\nYou can now run tests with: TEST_USER_ID={user_id} pytest tests/test_external_api.py -v")

if __name__ == '__main__':
    main()
