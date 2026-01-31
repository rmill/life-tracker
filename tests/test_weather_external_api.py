"""External API tests for Open-Meteo weather integration."""
# -*- coding: utf-8 -*-
import requests
import time
from datetime import datetime, timedelta


def _make_request_with_retry(url, params, max_retries=3, timeout=30):
    """Make HTTP request with retry logic for flaky networks."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            return response
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
    return None


def test_open_meteo_api_connectivity():
    """Test Open-Meteo API is accessible."""
    url = "https://archive-api.open-meteo.com/v1/archive"

    # Simple ping with minimal parameters
    params = {
        'latitude': 51.05,
        'longitude': -114.07,
        'start_date': '2026-01-20',
        'end_date': '2026-01-20',
        'daily': 'temperature_2m_max'
    }

    response = _make_request_with_retry(url, params)
    assert response.status_code == 200

    data = response.json()
    assert 'latitude' in data
    assert 'longitude' in data
    assert 'daily' in data


def test_open_meteo_api_response_structure():
    """Test Open-Meteo API returns expected data structure."""
    url = "https://archive-api.open-meteo.com/v1/archive"

    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    params = {
        'latitude': 51.05306,
        'longitude': -114.07139,
        'start_date': yesterday,
        'end_date': yesterday,
        'daily': [
            'temperature_2m_max',
            'temperature_2m_min',
            'relative_humidity_2m_mean',
            'surface_pressure_mean',
            'precipitation_sum',
            'wind_speed_10m_max',
            'sunshine_duration'
        ],
        'timezone': 'America/Edmonton'
    }

    response = _make_request_with_retry(url, params)
    assert response.status_code == 200

    data = response.json()

    # Check top-level structure
    assert 'latitude' in data
    assert 'longitude' in data
    assert 'timezone' in data
    assert 'daily' in data
    assert 'daily_units' in data

    # Check daily data
    daily = data['daily']
    assert 'time' in daily
    assert 'temperature_2m_max' in daily
    assert 'temperature_2m_min' in daily
    assert 'relative_humidity_2m_mean' in daily
    assert 'surface_pressure_mean' in daily
    assert 'precipitation_sum' in daily
    assert 'wind_speed_10m_max' in daily
    assert 'sunshine_duration' in daily

    # Check units
    units = data['daily_units']
    assert 'temperature_2m_max' in units
    assert units['temperature_2m_max'] == '°C'


def test_open_meteo_calgary_coordinates():
    """Test Open-Meteo API with Eau Claire, Calgary coordinates."""
    url = "https://archive-api.open-meteo.com/v1/archive"

    params = {
        'latitude': 51.05306,
        'longitude': -114.07139,
        'start_date': '2026-01-20',
        'end_date': '2026-01-22',
        'daily': 'temperature_2m_max,temperature_2m_min',
        'timezone': 'America/Edmonton'
    }

    response = _make_request_with_retry(url, params)
    assert response.status_code == 200

    data = response.json()

    # Verify coordinates are close to requested
    assert abs(data['latitude'] - 51.05306) < 0.1
    assert abs(data['longitude'] - (-114.07139)) < 0.1

    # Verify timezone
    assert data['timezone'] == 'America/Edmonton'

    # Verify 3 days of data
    assert len(data['daily']['time']) == 3


def test_open_meteo_data_quality():
    """Test Open-Meteo returns reasonable weather data for Calgary."""
    url = "https://archive-api.open-meteo.com/v1/archive"

    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    params = {
        'latitude': 51.05306,
        'longitude': -114.07139,
        'start_date': yesterday,
        'end_date': yesterday,
        'daily': 'temperature_2m_max,temperature_2m_min,relative_humidity_2m_mean',
        'timezone': 'America/Edmonton'
    }

    response = requests.get(url, params=params, timeout=10)
    assert response.status_code == 200

    data = response.json()
    daily = data['daily']

    # Check data exists
    assert len(daily['temperature_2m_max']) == 1
    assert len(daily['temperature_2m_min']) == 1
    assert len(daily['relative_humidity_2m_mean']) == 1

    temp_max = daily['temperature_2m_max'][0]
    temp_min = daily['temperature_2m_min'][0]
    humidity = daily['relative_humidity_2m_mean'][0]

    # Sanity checks for Calgary weather
    assert -50 <= temp_max <= 40  # °C
    assert -50 <= temp_min <= 40
    assert temp_min <= temp_max
    assert 0 <= humidity <= 100


def test_open_meteo_error_handling():
    """Test Open-Meteo API error responses."""
    url = "https://archive-api.open-meteo.com/v1/archive"

    # Test with invalid coordinates
    params = {
        'latitude': 999,  # Invalid
        'longitude': 999,  # Invalid
        'start_date': '2026-01-20',
        'end_date': '2026-01-20',
        'daily': 'temperature_2m_max'
    }

    response = requests.get(url, params=params, timeout=10)
    assert response.status_code == 400

    data = response.json()
    assert 'error' in data or 'reason' in data


def test_open_meteo_no_api_key_required():
    """Test Open-Meteo API works without authentication."""
    url = "https://archive-api.open-meteo.com/v1/archive"

    params = {
        'latitude': 51.05,
        'longitude': -114.07,
        'start_date': '2026-01-20',
        'end_date': '2026-01-20',
        'daily': 'temperature_2m_max'
    }

    # No API key or authentication headers
    response = requests.get(url, params=params, timeout=10)
    assert response.status_code == 200
