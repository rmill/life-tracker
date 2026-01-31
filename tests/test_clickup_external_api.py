"""
External API integration tests for ClickUp.
Tests connectivity and authentication with ClickUp API.
"""
import os
import sys
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import boto3
from botocore.exceptions import ClientError


@pytest.fixture(scope='session')
def ssm_client():
    """SSM client for retrieving credentials."""
    return boto3.client('ssm')


@pytest.fixture(scope='session')
def clickup_credentials_exist(ssm_client):
    """Check if ClickUp credentials are configured in SSM."""
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
    reason="Live API tests disabled (set SKIP_LIVE_API_TESTS=false to enable)"
)
def test_clickup_credentials_configured(ssm_client, clickup_credentials_exist):
    """Test that ClickUp credentials are configured in SSM."""
    assert clickup_credentials_exist, "ClickUp credentials not found in SSM"


@pytest.mark.skipif(
    os.environ.get('SKIP_LIVE_API_TESTS', 'true').lower() == 'true',
    reason="Live API tests disabled"
)
def test_clickup_api_connectivity(ssm_client, clickup_credentials_exist):
    """Test basic ClickUp API connectivity."""
    if not clickup_credentials_exist:
        pytest.skip("ClickUp credentials not configured")
    
    test_user_id = os.environ.get('TEST_USER_ID', 'zerocool')
    
    # Get credentials
    token = ssm_client.get_parameter(
        Name=f'/life-stats/clickup/{test_user_id}/token',
        WithDecryption=True
    )['Parameter']['Value']
    
    team_id = ssm_client.get_parameter(
        Name=f'/life-stats/clickup/{test_user_id}/team-id',
        WithDecryption=False
    )['Parameter']['Value']
    
    # Test API call
    import requests
    response = requests.get(
        f'https://api.clickup.com/api/v2/team/{team_id}',
        headers={'Authorization': token}
    )
    
    assert response.status_code == 200, f"ClickUp API returned {response.status_code}"
    data = response.json()
    assert 'team' in data


@pytest.mark.skipif(
    os.environ.get('SKIP_LIVE_API_TESTS', 'true').lower() == 'true',
    reason="Live API tests disabled"
)
def test_clickup_custom_task_types(ssm_client, clickup_credentials_exist):
    """Test fetching custom task types from ClickUp."""
    if not clickup_credentials_exist:
        pytest.skip("ClickUp credentials not configured")
    
    test_user_id = os.environ.get('TEST_USER_ID', 'zerocool')
    
    from integrations.clickup import ClickUpTasksIntegration
    
    integration = ClickUpTasksIntegration(test_user_id)
    
    # Verify custom types were loaded
    assert len(integration.custom_types) > 0, "No custom task types found"
    assert any('work' in name.lower() or 'socialization' in name.lower() 
               for name in integration.custom_types.values()), \
           "Expected task types not found"


@pytest.mark.skipif(
    os.environ.get('SKIP_LIVE_API_TESTS', 'true').lower() == 'true',
    reason="Live API tests disabled"
)
def test_clickup_fetch_tasks(ssm_client, clickup_credentials_exist):
    """Test fetching completed tasks from ClickUp."""
    if not clickup_credentials_exist:
        pytest.skip("ClickUp credentials not configured")
    
    test_user_id = os.environ.get('TEST_USER_ID', 'zerocool')
    
    from integrations.clickup import ClickUpTasksIntegration
    
    integration = ClickUpTasksIntegration(test_user_id)
    
    # Fetch last 7 days
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
    data = integration.fetch_data(since=since)
    
    # Verify data structure
    assert isinstance(data, list), "fetch_data should return a list"
    
    if len(data) > 0:
        point = data[0]
        assert 'date' in point
        assert 'metric_type' in point
        assert 'value' in point
        assert 'timestamp' in point
        
        # Verify value structure
        assert isinstance(point['value'], dict)
        assert 'hours' in point['value']
        assert 'tags' in point['value']
        assert isinstance(point['value']['hours'], (int, float))
        assert isinstance(point['value']['tags'], list)
        
        # Verify metric_type is valid
        assert point['metric_type'] != 'unknown', "Task type should not be unknown"
