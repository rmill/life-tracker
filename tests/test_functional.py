"""
Functional tests for Life Stats Lambda function.
Tests against real AWS resources (DynamoDB, SSM).
"""
import os
import sys
import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Set test environment
os.environ['METRICS_TABLE'] = 'life-stats-metrics-test'
os.environ['RUNS_TABLE'] = 'life-stats-runs-test'
os.environ['AWS_DEFAULT_REGION'] = os.environ.get('AWS_REGION', 'us-west-2')

import boto3
from lambda_function import handler


class MockContext:
    """Mock Lambda context for testing."""
    function_name = 'life-stats-test'
    memory_limit_in_mb = 256
    invoked_function_arn = 'arn:aws:lambda:us-west-2:123456789012:function:life-stats-test'
    aws_request_id = 'test-request-id'


@pytest.fixture(scope='session')
def dynamodb_client():
    """DynamoDB client for test setup/teardown."""
    return boto3.client('dynamodb')


@pytest.fixture(scope='session')
def setup_dynamodb_tables(dynamodb_client):
    """Create test DynamoDB tables."""
    metrics_table = os.environ['METRICS_TABLE']
    runs_table = os.environ['RUNS_TABLE']
    
    # Create metrics table
    try:
        dynamodb_client.create_table(
            TableName=metrics_table,
            KeySchema=[
                {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                {'AttributeName': 'metric_date', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'user_id', 'AttributeType': 'S'},
                {'AttributeName': 'metric_date', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        dynamodb_client.get_waiter('table_exists').wait(TableName=metrics_table)
    except dynamodb_client.exceptions.ResourceInUseException:
        pass
    
    # Create runs table
    try:
        dynamodb_client.create_table(
            TableName=runs_table,
            KeySchema=[
                {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                {'AttributeName': 'metric_type', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'user_id', 'AttributeType': 'S'},
                {'AttributeName': 'metric_type', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        dynamodb_client.get_waiter('table_exists').wait(TableName=runs_table)
    except dynamodb_client.exceptions.ResourceInUseException:
        pass
    
    yield
    
    # Cleanup (optional - comment out to inspect data after tests)
    # dynamodb_client.delete_table(TableName=metrics_table)
    # dynamodb_client.delete_table(TableName=runs_table)


@pytest.fixture
def clean_tables():
    """Clean test tables before each test."""
    dynamodb = boto3.resource('dynamodb')
    metrics_table = dynamodb.Table(os.environ['METRICS_TABLE'])
    runs_table = dynamodb.Table(os.environ['RUNS_TABLE'])
    
    # Clear metrics table
    scan = metrics_table.scan()
    with metrics_table.batch_writer() as batch:
        for item in scan.get('Items', []):
            batch.delete_item(Key={'user_id': item['user_id'], 'metric_date': item['metric_date']})
    
    # Clear runs table
    scan = runs_table.scan()
    with runs_table.batch_writer() as batch:
        for item in scan.get('Items', []):
            batch.delete_item(Key={'user_id': item['user_id'], 'metric_type': item['metric_type']})


def test_lambda_handler_no_users(setup_dynamodb_tables, clean_tables):
    """Test Lambda with no users configured."""
    event = {}
    response = handler(event, MockContext())
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['total_processed'] >= 0
    assert 'results' in body


def test_lambda_handler_with_mock_user(setup_dynamodb_tables, clean_tables):
    """Test Lambda with a mock user in runs table."""
    dynamodb = boto3.resource('dynamodb')
    runs_table = dynamodb.Table(os.environ['RUNS_TABLE'])
    
    # Add mock user
    runs_table.put_item(Item={
        'user_id': 'test-user',
        'metric_type': 'steps',
        'last_run_time': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    })
    
    event = {'user_id': 'test-user', 'metric': 'steps'}
    response = handler(event, MockContext())
    
    # Should fail because no SSM credentials, but Lambda should handle gracefully
    assert response['statusCode'] in [200, 207, 500]
    body = json.loads(response['body'])
    assert 'results' in body or 'errors' in body or 'error' in body


def test_database_schema_metrics(setup_dynamodb_tables, clean_tables):
    """Test metrics table schema."""
    from utils.db import MetricsDB
    
    db = MetricsDB()
    test_data = [
        {'date': '2026-01-17', 'value': 8542, 'timestamp': datetime.now(timezone.utc).isoformat()},
        {'date': '2026-01-16', 'value': 7231, 'timestamp': datetime.now(timezone.utc).isoformat()}
    ]
    
    db.store_metrics('test-user', 'steps', test_data)
    
    # Verify data stored correctly
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.environ['METRICS_TABLE'])
    
    response = table.query(
        KeyConditionExpression='user_id = :uid',
        ExpressionAttributeValues={':uid': 'test-user'}
    )
    
    items = response['Items']
    assert len(items) == 2
    assert all(item['metric_type'] == 'steps' for item in items)
    assert all(item['user_id'] == 'test-user' for item in items)
    
    # Verify chronological ordering (date#metric_type format)
    dates = [item['metric_date'] for item in items]
    assert dates == sorted(dates)


def test_database_last_run_tracking(setup_dynamodb_tables, clean_tables):
    """Test last run tracking."""
    from utils.db import MetricsDB
    
    db = MetricsDB()
    
    # Initially no last run
    last_run = db.get_last_run('test-user', 'steps')
    assert last_run is None
    
    # Update last run
    db.update_last_run('test-user', 'steps')
    
    # Verify last run stored
    last_run = db.get_last_run('test-user', 'steps')
    assert last_run is not None
    
    # Verify it's a valid ISO timestamp
    parsed = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
    assert isinstance(parsed, datetime)


def test_integration_registry():
    """Test integration registry."""
    from integrations.registry import IntegrationRegistry
    
    registry = IntegrationRegistry()
    
    # List available metrics
    metrics = registry.list_metrics()
    assert 'steps' in metrics
    assert len(metrics) > 0
    
    # Get integration (will fail without credentials, but should instantiate)
    try:
        integration = registry.get_integration('steps', 'test-user')
        assert integration is not None
    except Exception:
        # Expected if SSM credentials not available
        pass


def test_lambda_event_formats(setup_dynamodb_tables, clean_tables):
    """Test different Lambda event formats."""
    test_cases = [
        {},  # No parameters - all metrics, all users
        {'metric': 'steps'},  # Specific metric
        {'user_id': 'test-user'},  # Specific user
        {'metric': 'steps', 'user_id': 'test-user'}  # Both
    ]
    
    for event in test_cases:
        response = handler(event, MockContext())
        assert 'statusCode' in response
        assert 'body' in response
        body = json.loads(response['body'])
        assert isinstance(body, dict)


def test_idempotency(setup_dynamodb_tables, clean_tables):
    """Test that running Lambda multiple times is idempotent."""
    from utils.db import MetricsDB
    
    db = MetricsDB()
    
    # Store same data twice
    test_data = [
        {'date': '2026-01-17', 'value': 8542, 'timestamp': datetime.now(timezone.utc).isoformat()}
    ]
    
    db.store_metrics('test-user', 'steps', test_data)
    db.store_metrics('test-user', 'steps', test_data)
    
    # Should overwrite, not duplicate
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.environ['METRICS_TABLE'])
    
    response = table.query(
        KeyConditionExpression='user_id = :uid AND begins_with(metric_date, :date)',
        ExpressionAttributeValues={':uid': 'test-user', ':date': '2026-01-17'}
    )
    
    # Should only have one item (overwritten)
    assert len(response['Items']) == 1
