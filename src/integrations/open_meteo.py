from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from integrations.base import BaseIntegration
from utils.logger import setup_logger

logger = setup_logger(__name__)


class OpenMeteoWeatherIntegration(BaseIntegration):
    """Open-Meteo weather data integration for Eau Claire, Calgary."""

    # Eau Claire, Calgary coordinates
    LATITUDE = 51.05306
    LONGITUDE = -114.07139

    def __init__(self, user_id: str):
        super().__init__(user_id)
        # Configure session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _to_decimal(self, value):
        """Convert float/int to Decimal for DynamoDB, handle None."""
        if value is None:
            return Decimal('0')
        return Decimal(str(value))

    def fetch_data(self, since: Optional[str] = None, until: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch daily weather data from Open-Meteo API."""
        start_date, end_date = self._get_date_range(since, until)

        # Format dates as YYYY-MM-DD
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        logger.info(f"Fetching weather data for {self.user_id} from {start_str} to {end_str}")

        try:
            url = "https://archive-api.open-meteo.com/v1/archive"
            params = {
                'latitude': self.LATITUDE,
                'longitude': self.LONGITUDE,
                'start_date': start_str,
                'end_date': end_str,
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

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            data_points = []
            daily = data.get('daily', {})
            times = daily.get('time', [])

            for i, date_str in enumerate(times):
                data_points.append({
                    'date': date_str,
                    'value': {
                        'temp_max': self._to_decimal(daily['temperature_2m_max'][i]),
                        'temp_min': self._to_decimal(daily['temperature_2m_min'][i]),
                        'humidity_mean': self._to_decimal(daily['relative_humidity_2m_mean'][i]),
                        'pressure_mean': self._to_decimal(daily['surface_pressure_mean'][i]),
                        'precipitation': self._to_decimal(daily['precipitation_sum'][i]),
                        'wind_max': self._to_decimal(daily['wind_speed_10m_max'][i]),
                        'sunshine_duration': self._to_decimal(daily['sunshine_duration'][i])
                    },
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                logger.debug(f"Fetched weather for {date_str}")

            logger.info(f"Successfully fetched {len(data_points)} weather data points")
            return data_points

        except Exception as e:
            logger.error(f"Error fetching Open-Meteo data: {e}", exc_info=True)
            raise
