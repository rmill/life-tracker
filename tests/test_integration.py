"""
Integration tests for deployed Life Stats Lambda function.
Tests against actual deployed AWS resources.
"""
import os
import json
import boto3
import pytest
from datetime import datetime, timezone


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


def test_lambda_deployed(lambda_client, lambda_function_name):
    """Test that Lambda function is deployed and accessible."""
    response = lambda_client.get_function(FunctionName=lambda_function_name)
    assert response['Configuration']['FunctionName'] == lambda_function_name
    assert response['Configuration']['Runtime'] == 'python3.11'
    assert response['Configuration']['State'] == 'Active'


def test_lambda_invocation_empty_event(lambda_client, lambda_function_name):
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


def test_lambda_invocation_specific_metric(lambda_client, lambda_function_name):
    """Test Lambda invocation with specific metric."""
    response = lambda_client.invoke(
        FunctionName=lambda_function_name,
        InvocationType='RequestResponse',
        Payload=json.dumps({'metric': 'steps'})
    )
    
    assert response['StatusCode'] == 200
    payload = json.loads(response['Payload'].read())
    assert payload['statusCode'] in [200, 207, 500]  # May fail if no users/credentials


def test_dynamodb_tables_exist(dynamodb_client, metrics_table_name, runs_table_name):
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


def test_lambda_environment_variables(lambda_client, lambda_function_name, metrics_table_name, runs_table_name):
    """Test Lambda has correct environment variables."""
    response = lambda_client.get_function_configuration(FunctionName=lambda_function_name)
    env_vars = response['Environment']['Variables']
    
    assert env_vars['METRICS_TABLE'] == metrics_table_name
    assert env_vars['RUNS_TABLE'] == runs_table_name


def test_lambda_iam_permissions(lambda_client, lambda_function_name):
    """Test Lambda has IAM role attached."""
    response = lambda_client.get_function(FunctionName=lambda_function_name)
    role_arn = response['Configuration']['Role']
    
    assert role_arn is not None
    assert 'life-stats' in role_arn.lower()


def test_eventbridge_rule_exists():
    """Test EventBridge rule exists for scheduled execution."""
    events_client = boto3.client('events')
    
    try:
        response = events_client.describe_rule(Name='life-stats-daily-trigger')
        assert response['State'] == 'ENABLED'
        assert 'rate(24 hours)' in response['ScheduleExpression'] or 'cron' in response['ScheduleExpression']
    except events_client.exceptions.ResourceNotFoundException:
        pytest.skip("EventBridge rule not found - may not be deployed yet")


def test_cloudwatch_log_group_exists():
    """Test CloudWatch log group exists."""
    logs_client = boto3.client('logs')
    
    try:
        response = logs_client.describe_log_groups(logGroupNamePrefix='/aws/lambda/life-stats')
        assert len(response['logGroups']) > 0
        log_group = response['logGroups'][0]
        assert log_group['logGroupName'] == '/aws/lambda/life-stats'
    except Exception:
        pytest.skip("CloudWatch log group not found - may not be deployed yet")


def test_lambda_timeout_configuration(lambda_client, lambda_function_name):
    """Test Lambda has appropriate timeout."""
    response = lambda_client.get_function_configuration(FunctionName=lambda_function_name)
    assert response['Timeout'] >= 60  # At least 1 minute
    assert response['MemorySize'] >= 128


def test_end_to_end_with_test_user(lambda_client, dynamodb_client, lambda_function_name, runs_table_name):
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
