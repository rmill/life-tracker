"""Functional tests for Open-Meteo weather integration (mocked)."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pytest
from unittest.mock import Mock, patch
from decimal import Decimal
from integrations.open_meteo import OpenMeteoWeatherIntegration


def test_weather_integration_initialization():
    """Test weather integration can be initialized."""
    integration = OpenMeteoWeatherIntegration('test-user')
    assert integration.user_id == 'test-user'
    assert integration.LATITUDE == 51.05306
    assert integration.LONGITUDE == -114.07139


@patch('integrations.open_meteo.requests.Session.get')
def test_weather_fetch_data_structure(mock_get):
    """Test weather data fetch returns correct structure with mocked API."""
    # Mock API response
    mock_response = Mock()
    mock_response.json.return_value = {
        'daily': {
            'time': ['2026-01-30'],
            'temperature_2m_max': [5.0],
            'temperature_2m_min': [-2.0],
            'relative_humidity_2m_mean': [70.0],
            'surface_pressure_mean': [1013.0],
            'precipitation_sum': [0.0],
            'wind_speed_10m_max': [15.0],
            'sunshine_duration': [3600.0]
        }
    }
    mock_get.return_value = mock_response

    integration = OpenMeteoWeatherIntegration('test-user')
    data_points = integration.fetch_data(since='2026-01-30', until='2026-01-30')

    assert len(data_points) == 1

    # Check structure
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

    # Verify values are Decimal type
    assert isinstance(value['temp_max'], Decimal)
    assert isinstance(value['pressure_mean'], Decimal)


@patch('integrations.open_meteo.requests.Session.get')
def test_weather_api_error_handling(mock_get):
    """Test weather integration handles API errors gracefully."""
    # Mock API error
    mock_get.side_effect = Exception("API Error")

    integration = OpenMeteoWeatherIntegration('test-user')

    with pytest.raises(Exception) as exc_info:
        integration.fetch_data(since='2026-01-30')

    assert "API Error" in str(exc_info.value)


@patch('integrations.open_meteo.requests.Session.get')
def test_weather_date_range_parameters(mock_get):
    """Test that correct date parameters are sent to API."""
    mock_response = Mock()
    mock_response.json.return_value = {
        'daily': {
            'time': ['2026-01-20', '2026-01-21', '2026-01-22'],
            'temperature_2m_max': [5.0, 6.0, 7.0],
            'temperature_2m_min': [-2.0, -1.0, 0.0],
            'relative_humidity_2m_mean': [70.0, 71.0, 72.0],
            'surface_pressure_mean': [1013.0, 1014.0, 1015.0],
            'precipitation_sum': [0.0, 0.0, 0.0],
            'wind_speed_10m_max': [15.0, 16.0, 17.0],
            'sunshine_duration': [3600.0, 3700.0, 3800.0]
        }
    }
    mock_get.return_value = mock_response

    integration = OpenMeteoWeatherIntegration('test-user')
    data_points = integration.fetch_data(since='2026-01-20', until='2026-01-22')

    # Verify API was called with correct parameters
    mock_get.assert_called_once()
    call_args = mock_get.call_args
    params = call_args[1]['params']

    assert params['start_date'] == '2026-01-20'
    assert params['end_date'] == '2026-01-22'
    assert params['latitude'] == 51.05306
    assert params['longitude'] == -114.07139

    # Verify returned data
    assert len(data_points) == 3
    dates = [point['date'] for point in data_points]
    assert '2026-01-20' in dates
    assert '2026-01-21' in dates
    assert '2026-01-22' in dates
