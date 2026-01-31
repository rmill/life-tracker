"""
Integration tests for ClickUp with deployed Lambda function.
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
def dynamodb():
    """DynamoDB resource for verifying data."""
    return boto3.resource('dynamodb')


@pytest.fixture(scope='session')
def ssm_client():
    """SSM client for checking credentials."""
    return boto3.client('ssm')


@pytest.fixture(scope='session')
def lambda_function_name():
    """Get Lambda function name from environment or default."""
    return os.environ.get('LAMBDA_FUNCTION_NAME', 'life-stats')


@pytest.fixture(scope='session')
def metrics_table_name():
    """Get metrics table name from environment or default."""
    return os.environ.get('METRICS_TABLE', 'life-stats-metrics')


@pytest.fixture(scope='session')
def clickup_credentials_exist(ssm_client):
    """Check if ClickUp credentials are configured."""
    test_user_id = os.environ.get('TEST_USER_ID', 'zerocool')
    try:
        ssm_client.get_parameter(Name=f'/life-stats/clickup/{test_user_id}/token', WithDecryption=True)
        ssm_client.get_parameter(Name=f'/life-stats/clickup/{test_user_id}/list-id', WithDecryption=False)
        ssm_client.get_parameter(Name=f'/life-stats/clickup/{test_user_id}/team-id', WithDecryption=False)
        return True
    except ClientError:
        return False


@pytest.mark.skipif(
    os.environ.get('SKIP_INTEGRATION_TESTS', 'true').lower() == 'true',
    reason="Integration tests disabled"
)
def test_lambda_clickup_tasks_metric(lambda_client, dynamodb, lambda_function_name, 
                                      metrics_table_name, clickup_credentials_exist):
    """Test Lambda function with ClickUp tasks metric."""
    if not clickup_credentials_exist:
        pytest.skip("ClickUp credentials not configured")
    
    test_user_id = os.environ.get('TEST_USER_ID', 'zerocool')
    
    # Invoke Lambda with tasks metric
    start_date = (datetime.now(timezone.utc) - timedelta(days=2)).strftime('%Y-%m-%d')
    
    payload = {
        'metric': 'tasks',
        'user_id': test_user_id,
        'start_date': start_date,
        'source': 'manual'
    }
    
    response = lambda_client.invoke(
        FunctionName=lambda_function_name,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )
    
    # Parse response
    response_payload = json.loads(response['Payload'].read())
    assert response_payload['statusCode'] in [200, 207], \
        f"Lambda returned error: {response_payload.get('body')}"
    
    body = json.loads(response_payload['body'])
    
    # Verify results
    if body['total_processed'] > 0:
        # Verify data was stored in DynamoDB
        metrics_table = dynamodb.Table(metrics_table_name)
        
        response = metrics_table.query(
            KeyConditionExpression='user_id = :uid AND begins_with(metric_date, :date)',
            ExpressionAttributeValues={
                ':uid': test_user_id,
                ':date': start_date
            }
        )
        
        # Should have multiple metric types (work, socialization, etc.)
        metric_types = set(item['metric_type'] for item in response['Items'])
        assert len(metric_types) > 0, "Should have stored at least one task type metric"
        
        # Verify value structure
        for item in response['Items']:
            if item['metric_type'] in ['work', 'socialization', 'exercise', 'adulting', 
                                        'project', 'chore', 'relax', 'meeting']:
                assert 'value' in item
                assert isinstance(item['value'], dict)
                assert 'hours' in item['value']
                assert 'tags' in item['value']
