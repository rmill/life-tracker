#!/usr/bin/env python3
"""Debug script to check Google Fit API responses."""

import json
import sys
from datetime import datetime, timezone, timedelta
import boto3
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def get_credentials(user_id: str) -> Credentials:
    """Retrieve Google API credentials from SSM Parameter Store."""
    ssm = boto3.client('ssm')
    token_param = f"/life-stats/google-fit/{user_id}/token"
    response = ssm.get_parameter(Name=token_param, WithDecryption=True)
    creds = json.loads(response['Parameter']['Value'])
    
    return Credentials(
        token=creds.get('token'),
        refresh_token=creds.get('refresh_token'),
        token_uri=creds.get('token_uri'),
        client_id=creds.get('client_id'),
        client_secret=creds.get('client_secret'),
        scopes=creds.get('scopes')
    )

def fetch_steps(user_id: str, start_date: str, end_date: str):
    """Fetch steps data from Google Fit API."""
    credentials = get_credentials(user_id)
    service = build('fitness', 'v1', credentials=credentials)
    
    # Parse dates
    start = datetime.strptime(start_date, '%Y-%m-%d').replace(hour=0, minute=0, second=0, tzinfo=timezone.utc)
    end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    
    start_millis = int(start.timestamp() * 1000)
    end_millis = int(end.timestamp() * 1000)
    
    print(f"Fetching steps from {start} to {end}")
    print(f"Start millis: {start_millis}")
    print(f"End millis: {end_millis}")
    print()
    
    body = {
        "aggregateBy": [{
            "dataTypeName": "com.google.step_count.delta",
            "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
        }],
        "bucketByTime": {"durationMillis": 86400000},  # 1 day
        "startTimeMillis": start_millis,
        "endTimeMillis": end_millis
    }
    
    response = service.users().dataset().aggregate(userId='me', body=body).execute()
    
    print("Raw API Response:")
    print(json.dumps(response, indent=2))
    print()
    
    print("Parsed Data:")
    for bucket in response.get('bucket', []):
        start_time = datetime.fromtimestamp(int(bucket['startTimeMillis']) / 1000, tz=timezone.utc)
        end_time = datetime.fromtimestamp(int(bucket['endTimeMillis']) / 1000, tz=timezone.utc)
        
        print(f"\nBucket: {start_time} to {end_time}")
        
        for dataset in bucket.get('dataset', []):
            for point in dataset.get('point', []):
                point_start = datetime.fromtimestamp(int(point['startTimeNanos']) / 1e9, tz=timezone.utc)
                point_end = datetime.fromtimestamp(int(point['endTimeNanos']) / 1e9, tz=timezone.utc)
                
                if point.get('value'):
                    steps = sum(v.get('intVal', 0) for v in point['value'])
                    date_str = point_start.strftime('%Y-%m-%d')
                    
                    print(f"  Date: {date_str}")
                    print(f"  Point start: {point_start}")
                    print(f"  Point end: {point_end}")
                    print(f"  Steps: {steps}")

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: ./debug_google_fit.py <user_id> <start_date> <end_date>")
        print("Example: ./debug_google_fit.py zerocool 2026-01-17 2026-01-19")
        sys.exit(1)
    
    user_id = sys.argv[1]
    start_date = sys.argv[2]
    end_date = sys.argv[3]
    
    fetch_steps(user_id, start_date, end_date)
