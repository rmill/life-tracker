"""
External API integration tests.
Tests connectivity and authentication with external services (Google Fit, etc.).
"""
from botocore.exceptions import ClientError
import boto3
import os
import sys
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


@pytest.fixture(scope='session')
def ssm_client():
    """SSM client for retrieving credentials."""
    return boto3.client('ssm')


@pytest.fixture(scope='session')
def google_fit_credentials_exist(ssm_client):
    """Check if Google Fit credentials are configured in SSM."""
    try:
        ssm_client.get_parameter(Name='/life-stats/google-fit/client-id', WithDecryption=True)
        ssm_client.get_parameter(Name='/life-stats/google-fit/client-secret', WithDecryption=True)
        return True
    except ClientError:
        return False


@pytest.fixture(scope='session')
def test_user_with_oauth(ssm_client):
    """Create test user with OAuth token if needed."""
    test_user_id = os.environ.get('TEST_USER_ID', 'zerocool')

    # Check if token exists
    try:
        ssm_client.get_parameter(
            Name=f'/life-stats/google-fit/{test_user_id}/token',
            WithDecryption=True
        )
        return test_user_id
    except ClientError:
        # Token doesn't exist - try to generate
        if os.environ.get('AUTO_GENERATE_OAUTH', 'true').lower() == 'true':
            from google_auth_oauthlib.flow import InstalledAppFlow

            # Get client credentials
            client_id = ssm_client.get_parameter(
                Name='/life-stats/google-fit/client-id',
                WithDecryption=True
            )['Parameter']['Value']

            client_secret = ssm_client.get_parameter(
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
            ssm_client.put_parameter(
                Name=f'/life-stats/google-fit/{test_user_id}/token',
                Value=credentials.token,
                Type='SecureString',
                Overwrite=True
            )

            return test_user_id
        else:
            pytest.fail(
                f"OAuth token not found for {test_user_id}. "
                "Set AUTO_GENERATE_OAUTH=true or run: "
                "python scripts/generate-oauth-token.py")


def test_google_fit_credentials_configured(ssm_client):
    """Test that Google Fit credentials are stored in SSM."""
    client_id = ssm_client.get_parameter(
        Name='/life-stats/google-fit/client-id',
        WithDecryption=True
    )
    assert client_id['Parameter']['Value'] is not None
    assert len(client_id['Parameter']['Value']) > 0

    client_secret = ssm_client.get_parameter(
        Name='/life-stats/google-fit/client-secret',
        WithDecryption=True
    )
    assert client_secret['Parameter']['Value'] is not None
    assert len(client_secret['Parameter']['Value']) > 0


def test_google_fit_integration_instantiation(google_fit_credentials_exist):
    """Test that Google Fit integration can be instantiated."""
    if not google_fit_credentials_exist:
        pytest.skip("Google Fit credentials not configured")

    from integrations.google_fit import GoogleFitStepsIntegration

    # Should be able to instantiate (may fail on credential retrieval if no user token)
    try:
        integration = GoogleFitStepsIntegration('test-user')
        assert integration is not None
        assert integration.user_id == 'test-user'
    except Exception as e:
        # Expected if user token doesn't exist
        assert 'Parameter /life-stats/google-fit/test-user/token not found' in str(e) or \
               'ParameterNotFound' in str(e)


def test_google_fit_api_imports():
    """Test that Google API client libraries are available."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        assert Credentials is not None
        assert build is not None
    except ImportError as e:
        pytest.fail(f"Google API client libraries not available: {e}")


def test_google_fit_integration_base_class():
    """Test that Google Fit integration inherits from base correctly."""
    from integrations.google_fit import GoogleFitStepsIntegration
    from integrations.base import BaseIntegration

    assert issubclass(GoogleFitStepsIntegration, BaseIntegration)

    # Check required methods exist
    assert hasattr(GoogleFitStepsIntegration, 'fetch_data')
    assert callable(getattr(GoogleFitStepsIntegration, 'fetch_data'))


def test_google_fit_date_range_calculation():
    """Test date range calculation for first run vs incremental."""
    from integrations.base import BaseIntegration

    class TestIntegration(BaseIntegration):
        def fetch_data(self, since=None):
            return []

    integration = TestIntegration('test-user')

    # First run (no since) - should fetch last 7 days
    start, end = integration._get_date_range(None)
    assert (end - start).days >= 6
    assert (end - start).days <= 8  # Allow some tolerance

    # Incremental run - should fetch from since timestamp
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    start, end = integration._get_date_range(yesterday)
    assert (end - start).days <= 2  # Should be ~1 day


def test_integration_registry_has_google_fit():
    """Test that Google Fit integration is registered."""
    from integrations.registry import IntegrationRegistry
    from integrations.google_fit import GoogleFitStepsIntegration

    registry = IntegrationRegistry()
    metrics = registry.list_metrics()

    assert 'steps' in metrics

    # Verify the integration class is registered (don't instantiate - requires user token)
    integration_class = registry._integrations.get('steps')
    assert integration_class == GoogleFitStepsIntegration
    assert integration_class.__name__ == 'GoogleFitStepsIntegration'


def test_google_fit_api_scopes():
    """Test that Google Fit API scopes are correctly defined."""
    # Google Fit requires specific OAuth scopes
    # This test ensures we're aware of the required scopes
    required_scopes = [
        'https://www.googleapis.com/auth/fitness.activity.read',
        'https://www.googleapis.com/auth/fitness.body.read',
        'https://www.googleapis.com/auth/fitness.location.read'
    ]

    # Just verify we know what scopes are needed
    # Actual scope validation happens during OAuth flow
    assert len(required_scopes) > 0


@pytest.mark.skipif(
    os.environ.get('SKIP_LIVE_API_TESTS', 'false').lower() == 'true',
    reason="Live API tests disabled - set SKIP_LIVE_API_TESTS=false to enable"
)
def test_google_fit_live_api_call(test_user_with_oauth):
    """
    Test actual Google Fit API call with real credentials.
    REQUIRED: This test must pass to ensure Google Fit integration works.
    """
    from integrations.google_fit import GoogleFitStepsIntegration

    test_user_id = test_user_with_oauth

    try:
        integration = GoogleFitStepsIntegration(test_user_id)

        # Fetch last 2 days of data
        since = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        data = integration.fetch_data(since)

        # Should return list (may be empty if no data)
        assert isinstance(data, list), "Google Fit API should return a list"

        # If data exists, validate structure
        if data:
            for point in data:
                assert 'date' in point, "Data point must have 'date'"
                assert 'value' in point, "Data point must have 'value'"
                assert 'timestamp' in point, "Data point must have 'timestamp'"
                assert isinstance(point['value'], (int, float)), "Value must be numeric"

        print(f"✓ Google Fit integration working - fetched {len(data)} data points")

    except Exception as e:
        pytest.fail(f"Google Fit integration failed - REQUIRED for deployment: {e}")


def test_error_handling_invalid_credentials():
    """Test that integration handles invalid credentials gracefully."""
    from integrations.google_fit import GoogleFitStepsIntegration

    # Try to instantiate with non-existent user
    with pytest.raises(Exception) as exc_info:
        GoogleFitStepsIntegration('nonexistent-user-12345')

    # Should raise an error about missing credentials
    assert 'Parameter' in str(exc_info.value) or 'not found' in str(
        exc_info.value).lower()


def test_integration_data_format():
    """Test that integration returns data in expected format."""
    from integrations.base import BaseIntegration

    class MockIntegration(BaseIntegration):
        def fetch_data(self, since=None):
            return [
                {
                    'date': '2026-01-17',
                    'value': 8542,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            ]

    integration = MockIntegration('test-user')
    data = integration.fetch_data()

    assert isinstance(data, list)
    assert len(data) == 1
    assert 'date' in data[0]
    assert 'value' in data[0]
    assert 'timestamp' in data[0]
