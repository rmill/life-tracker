#!/usr/bin/env python3
"""
Local testing script for Life Stats Lambda function.
Allows testing without deploying to AWS.
"""
import sys
import os
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Mock environment variables
os.environ.setdefault('METRICS_TABLE', 'life-stats-metrics')
os.environ.setdefault('RUNS_TABLE', 'life-stats-runs')
os.environ.setdefault('AWS_DEFAULT_REGION', 'us-west-2')


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Life Stats Lambda locally')
    parser.add_argument('--metric', help='Specific metric to run (e.g., steps)')
    parser.add_argument('--user-id', help='Specific user ID to process')
    parser.add_argument('--event', help='Path to JSON event file')
    
    args = parser.parse_args()
    
    # Build event
    if args.event:
        with open(args.event) as f:
            event = json.load(f)
    else:
        event = {}
        if args.metric:
            event['metric'] = args.metric
        if args.user_id:
            event['user_id'] = args.user_id
    
    print(f"Testing with event: {json.dumps(event, indent=2)}\n")
    
    # Import and run handler
    from lambda_function import handler
    
    class MockContext:
        function_name = 'life-stats-local'
        memory_limit_in_mb = 256
        invoked_function_arn = 'arn:aws:lambda:us-west-2:123456789012:function:life-stats-local'
        aws_request_id = 'local-test-request-id'
    
    try:
        response = handler(event, MockContext())
        print("\n" + "="*50)
        print("RESPONSE:")
        print("="*50)
        print(json.dumps(response, indent=2))
        
        # Parse and display results
        body = json.loads(response['body'])
        print("\n" + "="*50)
        print("SUMMARY:")
        print("="*50)
        print(f"Status Code: {response['statusCode']}")
        print(f"Successful: {body.get('total_processed', 0)}")
        print(f"Errors: {body.get('total_errors', 0)}")
        
        if body.get('results'):
            print("\nResults:")
            for result in body['results']:
                print(f"  - {result['user_id']}/{result['metric']}: {result['count']} points ({result['status']})")
        
        if body.get('errors'):
            print("\nErrors:")
            for error in body['errors']:
                print(f"  - {error['user_id']}/{error['metric']}: {error['error']}")
        
        sys.exit(0 if response['statusCode'] == 200 else 1)
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
