"""Integration tests for weather data collection."""
import pytest
import boto3
from datetime import datetime, timezone, timedelta
from integrations.open_meteo import OpenMeteoWeatherIntegration
from utils.db import MetricsDB


@pytest.fixture
def db():
    """Create test database instance."""
    return MetricsDB()


def test_weather_end_to_end(db):
    """Test complete weather data collection and storage."""
    user_id = 'test-weather-user'
    integration = OpenMeteoWeatherIntegration(user_id)
    
    # Fetch yesterday's weather
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    
    data_points = integration.fetch_data(since=yesterday, until=yesterday)
    assert len(data_points) == 1
    
    # Store in DynamoDB
    db.store_metrics(user_id, 'weather', data_points)
    
    # Verify storage
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('life-stats-metrics')
    
    response = table.get_item(
        Key={
            'user_id': user_id,
            'metric_date': f"{yesterday}#weather"
        }
    )
    
    assert 'Item' in response
    item = response['Item']
    
    assert item['user_id'] == user_id
    assert item['metric_type'] == 'weather'
    assert item['date'] == yesterday
    assert 'value' in item
    
    # Check value structure
    value = item['value']
    assert 'temp_max' in value
    assert 'temp_min' in value
    assert 'humidity_mean' in value
    assert 'pressure_mean' in value


def test_weather_last_run_tracking(db):
    """Test last run tracking for weather metric."""
    user_id = 'test-weather-user'
    
    # Update last run
    db.update_last_run(user_id, 'weather')
    
    # Retrieve last run
    last_run = db.get_last_run(user_id, 'weather')
    
    assert last_run is not None
    last_run_time = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
    
    # Should be recent (within last minute)
    now = datetime.now(timezone.utc)
    assert (now - last_run_time).total_seconds() < 60


def test_weather_data_overwrite(db):
    """Test that re-fetching weather data overwrites previous values."""
    user_id = 'test-weather-user'
    integration = OpenMeteoWeatherIntegration(user_id)
    
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Fetch and store once
    data_points = integration.fetch_data(since=yesterday, until=yesterday)
    db.store_metrics(user_id, 'weather', data_points)
    
    # Fetch and store again
    data_points_2 = integration.fetch_data(since=yesterday, until=yesterday)
    db.store_metrics(user_id, 'weather', data_points_2)
    
    # Verify only one record exists
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('life-stats-metrics')
    
    response = table.query(
        KeyConditionExpression='user_id = :uid AND begins_with(metric_date, :date)',
        ExpressionAttributeValues={
            ':uid': user_id,
            ':date': f"{yesterday}#weather"
        }
    )
    
    # Should have exactly one item
    assert response['Count'] == 1


def test_weather_multiple_days(db):
    """Test fetching and storing multiple days of weather data."""
    user_id = 'test-weather-user'
    integration = OpenMeteoWeatherIntegration(user_id)
    
    # Fetch last 5 days
    end_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    start_date = (datetime.now(timezone.utc) - timedelta(days=5)).strftime('%Y-%m-%d')
    
    data_points = integration.fetch_data(since=start_date, until=end_date)
    assert len(data_points) == 5
    
    # Store all
    db.store_metrics(user_id, 'weather', data_points)
    
    # Verify all stored
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('life-stats-metrics')
    
    for point in data_points:
        response = table.get_item(
            Key={
                'user_id': user_id,
                'metric_date': f"{point['date']}#weather"
            }
        )
        assert 'Item' in response
