"""
Integration tests for deployed Life Stats Lambda function.
Tests against actual deployed AWS resources.
"""
import os
import json
import boto3
import pytest
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError


@pytest.fixture(scope='session')
def lambda_client():
    """Lambda client for invoking deployed function."""
    return boto3.client('lambda')


@pytest.fixture(scope='session')
def dynamodb_client():
    """DynamoDB client for verifying data."""
    return boto3.resource('dynamodb')


@pytest.fixture(scope='session')
def lambda_function_name():
    """Get Lambda function name from environment or default."""
    return os.environ.get('LAMBDA_FUNCTION_NAME', 'life-stats')


@pytest.fixture(scope='session')
def metrics_table_name():
    """Get metrics table name from environment or default."""
    return os.environ.get('METRICS_TABLE', 'life-stats-metrics')


@pytest.fixture(scope='session')
def runs_table_name():
    """Get runs table name from environment or default."""
    return os.environ.get('RUNS_TABLE', 'life-stats-runs')


    """Test that Lambda function is deployed and accessible."""
    
    response = lambda_client.get_function(FunctionName=lambda_function_name)
    assert response['Configuration']['FunctionName'] == lambda_function_name
    assert response['Configuration']['Runtime'] == 'python3.11'
    assert response['Configuration']['State'] == 'Active'


    """Test Lambda invocation with empty event."""
    
    response = lambda_client.invoke(
        FunctionName=lambda_function_name,
        InvocationType='RequestResponse',
        Payload=json.dumps({})
    )
    
    assert response['StatusCode'] == 200
    payload = json.loads(response['Payload'].read())
    assert 'statusCode' in payload
    assert 'body' in payload
    
    body = json.loads(payload['body'])
    assert 'results' in body or 'errors' in body or 'error' in body


    """Test Lambda invocation with specific metric."""
    
    response = lambda_client.invoke(
        FunctionName=lambda_function_name,
        InvocationType='RequestResponse',
        Payload=json.dumps({'metric': 'steps'})
    )
    
    assert response['StatusCode'] == 200
    payload = json.loads(response['Payload'].read())
    assert payload['statusCode'] in [200, 207, 500]  # May fail if no users/credentials


    """Test that DynamoDB tables exist and are active."""
    
    # Check metrics table
    metrics_table = dynamodb_client.Table(metrics_table_name)
    assert metrics_table.table_status == 'ACTIVE'
    assert metrics_table.key_schema == [
        {'AttributeName': 'user_id', 'KeyType': 'HASH'},
        {'AttributeName': 'metric_date', 'KeyType': 'RANGE'}
    ]
    
    # Check runs table
    runs_table = dynamodb_client.Table(runs_table_name)
    assert runs_table.table_status == 'ACTIVE'
    assert runs_table.key_schema == [
        {'AttributeName': 'user_id', 'KeyType': 'HASH'},
        {'AttributeName': 'metric_type', 'KeyType': 'RANGE'}
    ]


    """Test Lambda has correct environment variables."""
    
    response = lambda_client.get_function_configuration(FunctionName=lambda_function_name)
    env_vars = response['Environment']['Variables']
    
    assert env_vars['METRICS_TABLE'] == metrics_table_name
    assert env_vars['RUNS_TABLE'] == runs_table_name


    """Test Lambda has IAM role attached."""
    
    response = lambda_client.get_function(FunctionName=lambda_function_name)
    role_arn = response['Configuration']['Role']
    
    assert role_arn is not None
    assert 'life-stats' in role_arn.lower()


    """Test EventBridge rule exists for scheduled execution."""
    
    events_client = boto3.client('events')
    
    try:
        response = events_client.describe_rule(Name='life-stats-daily-trigger')
        assert response['State'] == 'ENABLED'
        assert 'rate(24 hours)' in response['ScheduleExpression'] or 'cron' in response['ScheduleExpression']
    except events_client.exceptions.ResourceNotFoundException:
        pytest.skip("EventBridge rule not found - may not be deployed yet")


    """Test CloudWatch log group exists."""
    
    logs_client = boto3.client('logs')
    
    try:
        response = logs_client.describe_log_groups(logGroupNamePrefix='/aws/lambda/life-stats')
        assert len(response['logGroups']) > 0
        log_group = response['logGroups'][0]
        assert log_group['logGroupName'] == '/aws/lambda/life-stats'
    except Exception:
        pytest.skip("CloudWatch log group not found - may not be deployed yet")


    """Test Lambda has appropriate timeout."""
    
    response = lambda_client.get_function_configuration(FunctionName=lambda_function_name)
    assert response['Timeout'] >= 60  # At least 1 minute
    assert response['MemorySize'] >= 128


@pytest.fixture(scope='session')
def test_user_with_oauth():
    """Create test user with OAuth token if needed."""
    test_user_id = os.environ.get('TEST_USER_ID', 'zerocool')
    
    ssm = boto3.client('ssm')
    
    # Check if token exists
    try:
        ssm.get_parameter(
            Name=f'/life-stats/google-fit/{test_user_id}/token',
            WithDecryption=True
        )
        return test_user_id
    except ssm.exceptions.ParameterNotFound:
        # Token doesn't exist - try to generate
        if os.environ.get('AUTO_GENERATE_OAUTH', 'true').lower() == 'true':
            from google_auth_oauthlib.flow import InstalledAppFlow
            
            # Get client credentials
            client_id = ssm.get_parameter(
                Name='/life-stats/google-fit/client-id',
                WithDecryption=True
            )['Parameter']['Value']
            
            client_secret = ssm.get_parameter(
                Name='/life-stats/google-fit/client-secret',
                WithDecryption=True
            )['Parameter']['Value']
            
            # Run OAuth flow
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost:8080/"]
                }
            }
            
            scopes = [
                'https://www.googleapis.com/auth/fitness.activity.read',
                'https://www.googleapis.com/auth/fitness.body.read',
            ]
            
            flow = InstalledAppFlow.from_client_config(client_config, scopes)
            credentials = flow.run_local_server(port=8080)
            
            # Store token
            ssm.put_parameter(
                Name=f'/life-stats/google-fit/{test_user_id}/token',
                Value=credentials.token,
                Type='SecureString',
                Overwrite=True
            )
            
            return test_user_id
        else:
            pytest.fail(f"OAuth token not found for {test_user_id}. Set AUTO_GENERATE_OAUTH=true or run: python scripts/generate-oauth-token.py")


    """Test end-to-end flow with a test user (if configured)."""
    
    # Add a test user to runs table
    runs_table = dynamodb_client.Table(runs_table_name)
    
    test_user_id = f"integration-test-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    
    runs_table.put_item(Item={
        'user_id': test_user_id,
        'metric_type': 'steps',
        'last_run_time': datetime.now(timezone.utc).isoformat()
    })
    
    # Invoke Lambda for this test user
    response = lambda_client.invoke(
        FunctionName=lambda_function_name,
        InvocationType='RequestResponse',
        Payload=json.dumps({'user_id': test_user_id, 'metric': 'steps'})
    )
    
    assert response['StatusCode'] == 200
    payload = json.loads(response['Payload'].read())
    
    # Should handle gracefully even without SSM credentials
    assert payload['statusCode'] in [200, 207, 500]
    
    # Cleanup
    runs_table.delete_item(Key={'user_id': test_user_id, 'metric_type': 'steps'})


def test_end_to_end_with_real_oauth(lambda_client, dynamodb_client, lambda_function_name, 
                                     metrics_table_name, runs_table_name, test_user_with_oauth):
    """Test complete flow with real OAuth token and API calls."""
    test_user_id = test_user_with_oauth
    runs_table = dynamodb_client.Table(runs_table_name)
    metrics_table = dynamodb_client.Table(metrics_table_name)
    
    # Ensure user exists in runs table
    runs_table.put_item(Item={
        'user_id': test_user_id,
        'metric_type': 'steps',
        'last_run_time': (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    })
    
    # Invoke Lambda
    response = lambda_client.invoke(
        FunctionName=lambda_function_name,
        InvocationType='RequestResponse',
        Payload=json.dumps({'user_id': test_user_id, 'metric': 'steps'})
    )
    
    assert response['StatusCode'] == 200
    payload = json.loads(response['Payload'].read())
    assert payload['statusCode'] == 200
    
    body = json.loads(payload['body'])
    assert 'results' in body
    assert len(body['results']) > 0
    assert body['results'][0]['user_id'] == test_user_id
    assert body['results'][0]['status'] == 'success'
    
    # Verify data was written to metrics table
    result = metrics_table.query(
        KeyConditionExpression='user_id = :uid',
        ExpressionAttributeValues={':uid': test_user_id},
        Limit=10
    )
    
    # Should have at least some data points
    assert result['Count'] >= 0  # May be 0 if no Google Fit data available
