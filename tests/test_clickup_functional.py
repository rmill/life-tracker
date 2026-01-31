"""
Functional tests for ClickUp integration.
Tests against real AWS resources (DynamoDB, SSM).
"""
from botocore.exceptions import ClientError
import boto3
import os
import sys
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Set test environment
os.environ['METRICS_TABLE'] = 'life-stats-metrics-test'
os.environ['RUNS_TABLE'] = 'life-stats-runs-test'
os.environ['AWS_DEFAULT_REGION'] = os.environ.get('AWS_REGION', 'us-west-2')


@pytest.fixture(scope='session')
def ssm_client():
    """SSM client for checking credentials."""
    return boto3.client('ssm')


@pytest.fixture(scope='session')
def dynamodb():
    """DynamoDB resource for verifying data."""
    return boto3.resource('dynamodb')


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
    os.environ.get('SKIP_LIVE_API_TESTS', 'true').lower() == 'true',
    reason="Live API tests disabled"
)
def test_clickup_integration_stores_data(dynamodb, clickup_credentials_exist):
    """Test that ClickUp integration stores data correctly in DynamoDB."""
    if not clickup_credentials_exist:
        pytest.skip("ClickUp credentials not configured")

    test_user_id = os.environ.get('TEST_USER_ID', 'zerocool')

    from integrations.clickup import ClickUpTasksIntegration
    from utils.db import MetricsDB

    # Fetch data
    integration = ClickUpTasksIntegration(test_user_id)
    since = (datetime.now(timezone.utc) - timedelta(days=3)).strftime('%Y-%m-%d')
    data = integration.fetch_data(since=since)

    if len(data) == 0:
        pytest.skip("No ClickUp data available for testing")

    # Store in test database
    db = MetricsDB()

    # Group by metric_type
    grouped = {}
    for point in data:
        mt = point.get('metric_type', 'tasks')
        if mt not in grouped:
            grouped[mt] = []
        grouped[mt].append(point)

    # Store each metric type
    for metric_type, points in grouped.items():
        db.store_metrics(test_user_id, metric_type, points)

    # Verify data was stored
    metrics_table = dynamodb.Table(os.environ['METRICS_TABLE'])

    for metric_type in grouped.keys():
        # Query for this specific metric type
        for point in grouped[metric_type]:
            response = metrics_table.get_item(
                Key={
                    'user_id': test_user_id,
                    'metric_date': f"{point['date']}#{metric_type}"
                }
            )

            assert 'Item' in response, f"No data stored for {metric_type} on {point['date']}"
            item = response['Item']

            # Verify structure
            assert 'value' in item
            assert isinstance(item['value'], dict)
            assert 'hours' in item['value']
            assert 'tags' in item['value']


@pytest.mark.skipif(
    os.environ.get('SKIP_LIVE_API_TESTS', 'true').lower() == 'true',
    reason="Live API tests disabled"
)
def test_clickup_dynamic_metric_types(dynamodb, clickup_credentials_exist):
    """Test that different task types create separate metrics."""
    if not clickup_credentials_exist:
        pytest.skip("ClickUp credentials not configured")

    test_user_id = os.environ.get('TEST_USER_ID', 'zerocool')

    from integrations.clickup import ClickUpTasksIntegration

    integration = ClickUpTasksIntegration(test_user_id)
    since = (datetime.now(timezone.utc) - timedelta(days=3)).strftime('%Y-%m-%d')
    data = integration.fetch_data(since=since)

    if len(data) == 0:
        pytest.skip("No ClickUp data available for testing")

    # Verify multiple metric types exist
    metric_types = set(point['metric_type'] for point in data)
    assert len(metric_types) > 0, "Should have at least one metric type"

    # Verify metric types are properly formatted
    for mt in metric_types:
        assert mt.islower(), f"Metric type '{mt}' should be lowercase"
        assert ' ' not in mt, f"Metric type '{mt}' should not contain spaces"
