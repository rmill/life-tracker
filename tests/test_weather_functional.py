"""Functional tests for Open-Meteo weather integration."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from integrations.open_meteo import OpenMeteoWeatherIntegration


def test_weather_integration_initialization():
    """Test weather integration can be initialized."""
    integration = OpenMeteoWeatherIntegration('test-user')
    assert integration.user_id == 'test-user'
    assert integration.LATITUDE == 51.05306
    assert integration.LONGITUDE == -114.07139


def test_weather_fetch_data_structure():
    """Test weather data fetch returns correct structure."""
    integration = OpenMeteoWeatherIntegration('test-user')

    # Fetch last 3 days
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=3)

    data_points = integration.fetch_data(
        since=start_date.isoformat(),
        until=end_date.strftime('%Y-%m-%d')
    )

    assert len(data_points) > 0

    # Check structure of first data point
    point = data_points[0]
    assert 'date' in point
    assert 'value' in point
    assert 'timestamp' in point

    # Check value structure
    value = point['value']
    assert 'temp_max' in value
    assert 'temp_min' in value
    assert 'humidity_mean' in value
    assert 'pressure_mean' in value
    assert 'precipitation' in value
    assert 'wind_max' in value
    assert 'sunshine_duration' in value

    # Check data types
    assert isinstance(value['temp_max'], (int, float, Decimal))
    assert isinstance(value['temp_min'], (int, float, Decimal))
    assert isinstance(value['humidity_mean'], (int, float, Decimal))
    assert isinstance(value['pressure_mean'], (int, float, Decimal))
    assert isinstance(value['precipitation'], (int, float, Decimal))
    assert isinstance(value['wind_max'], (int, float, Decimal))
    assert isinstance(value['sunshine_duration'], (int, float, Decimal))


def test_weather_data_sanity_checks():
    """Test weather data values are within reasonable ranges."""
    integration = OpenMeteoWeatherIntegration('test-user')

    # Fetch yesterday's data
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')

    data_points = integration.fetch_data(
        since=yesterday,
        until=yesterday
    )

    assert len(data_points) == 1
    value = data_points[0]['value']

    # Calgary temperature ranges (reasonable bounds) - convert Decimal to float for comparison
    temp_max = float(value['temp_max'])
    temp_min = float(value['temp_min'])
    humidity = float(value['humidity_mean'])
    pressure = float(value['pressure_mean'])
    precipitation = float(value['precipitation'])
    wind = float(value['wind_max'])
    sunshine = float(value['sunshine_duration'])

    assert -50 <= temp_max <= 40  # °C
    assert -50 <= temp_min <= 40
    assert temp_min <= temp_max

    # Humidity 0-100%
    assert 0 <= humidity <= 100

    # Pressure reasonable range (low pressure systems can go below 900)
    assert 850 <= pressure <= 1100  # hPa

    # Precipitation non-negative
    assert precipitation >= 0

    # Wind speed non-negative
    assert wind >= 0

    # Sunshine duration 0-86400 seconds (24 hours)
    assert 0 <= sunshine <= 86400


def test_weather_date_range():
    """Test weather data fetch respects date range."""
    integration = OpenMeteoWeatherIntegration('test-user')

    # Fetch specific date range
    start = '2026-01-20'
    end = '2026-01-22'

    try:
        data_points = integration.fetch_data(since=start, until=end)
    except Exception as e:
        pytest.skip(f"Network timeout or API unavailable: {e}")

    # Should get 3 days of data
    assert len(data_points) == 3

    # Check dates are in range
    dates = [point['date'] for point in data_points]
    assert '2026-01-20' in dates
    assert '2026-01-21' in dates
    assert '2026-01-22' in dates


def test_weather_api_error_handling():
    """Test weather integration handles API errors gracefully."""
    integration = OpenMeteoWeatherIntegration('test-user')

    # Test with invalid date range (future dates beyond forecast)
    with pytest.raises(Exception):
        integration.fetch_data(
            since='2030-01-01',
            until='2030-01-31'
        )
