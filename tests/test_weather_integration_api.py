"""Integration tests for Open-Meteo weather API (real API calls).

These tests make actual API calls and should be run separately from unit tests.
Skip in CI by default to avoid network dependencies.
"""
import sys
from pathlib import Path
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pytest
from datetime import datetime, timezone, timedelta
from integrations.open_meteo import OpenMeteoWeatherIntegration


@pytest.mark.skipif(
    os.environ.get('SKIP_INTEGRATION_TESTS', 'true').lower() == 'true',
    reason="Integration tests disabled (set SKIP_INTEGRATION_TESTS=false to enable)"
)
def test_weather_real_api_call():
    """Test actual API call to Open-Meteo (integration test)."""
    integration = OpenMeteoWeatherIntegration('test-user')

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')

    try:
        data_points = integration.fetch_data(since=yesterday, until=yesterday)
    except Exception as e:
        pytest.skip(f"API unavailable: {e}")

    assert len(data_points) == 1
    value = data_points[0]['value']

    # Verify all expected fields are present
    assert 'temp_max' in value
    assert 'temp_min' in value
    assert 'humidity_mean' in value
    assert 'pressure_mean' in value
    assert 'precipitation' in value
    assert 'wind_max' in value
    assert 'sunshine_duration' in value


@pytest.mark.skipif(
    os.environ.get('SKIP_INTEGRATION_TESTS', 'true').lower() == 'true',
    reason="Integration tests disabled"
)
def test_weather_data_sanity_checks():
    """Test real weather data is within reasonable ranges."""
    integration = OpenMeteoWeatherIntegration('test-user')

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')

    try:
        data_points = integration.fetch_data(since=yesterday, until=yesterday)
    except Exception as e:
        pytest.skip(f"API unavailable: {e}")

    assert len(data_points) == 1
    value = data_points[0]['value']

    # Calgary temperature ranges - convert Decimal to float
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

    assert 0 <= humidity <= 100  # %
    assert 850 <= pressure <= 1100  # hPa
    assert precipitation >= 0  # mm
    assert wind >= 0  # km/h
    assert sunshine >= 0  # seconds


@pytest.mark.skipif(
    os.environ.get('SKIP_INTEGRATION_TESTS', 'true').lower() == 'true',
    reason="Integration tests disabled"
)
def test_weather_date_range():
    """Test weather data fetch respects date range."""
    integration = OpenMeteoWeatherIntegration('test-user')

    start = '2026-01-20'
    end = '2026-01-22'

    try:
        data_points = integration.fetch_data(since=start, until=end)
    except Exception as e:
        pytest.skip(f"API unavailable: {e}")

    assert len(data_points) == 3

    dates = [point['date'] for point in data_points]
    assert '2026-01-20' in dates
    assert '2026-01-21' in dates
    assert '2026-01-22' in dates
