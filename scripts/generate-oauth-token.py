#!/usr/bin/env python3
"""
Generate Google Fit OAuth token for testing.
This script will open a browser for you to authorize access.
"""
import os
import sys
from google_auth_oauthlib.flow import InstalledAppFlow
import boto3

SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.body.read',
]

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

def main():
    print("Google Fit OAuth Token Generator")
    print("=" * 50)
    
    user_id = input("Enter user ID (e.g., 'test-user'): ").strip()
    if not user_id:
        print("Error: User ID is required")
        sys.exit(1)
    
    print("\nFetching client credentials from SSM...")
    try:
        client_id, client_secret = get_credentials_from_ssm()
    except Exception as e:
        print(f"Error: Could not fetch credentials from SSM: {e}")
        sys.exit(1)
    
    # Create OAuth flow
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8080/"]
        }
    }
    
    print("\nStarting OAuth flow...")
    print("A browser window will open for you to authorize access.")
    print("After authorizing, you'll be redirected to localhost (this is normal).")
    
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    credentials = flow.run_local_server(port=8080)
    
    # Store token in SSM
    print(f"\n✓ Authorization successful!")
    print(f"Storing token in SSM for user '{user_id}'...")
    
    ssm = boto3.client('ssm', region_name='us-west-2')
    ssm.put_parameter(
        Name=f'/life-stats/google-fit/{user_id}/token',
        Value=credentials.token,
        Type='SecureString',
        Overwrite=True
    )
    
    print(f"✓ Token stored successfully!")
    print(f"\nYou can now run tests with: TEST_USER_ID={user_id} pytest tests/test_external_api.py -v")

if __name__ == '__main__':
    main()
