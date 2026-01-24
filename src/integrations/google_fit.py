from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import boto3
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from integrations.base import BaseIntegration
from utils.logger import setup_logger

logger = setup_logger(__name__)


class GoogleFitStepsIntegration(BaseIntegration):
    """Google Fit steps metric integration."""

    def __init__(self, user_id: str):
        super().__init__(user_id)
        self.ssm = boto3.client('ssm')
        self.credentials = self._get_credentials()

    def _get_credentials(self) -> Credentials:
        """Retrieve Google API credentials from SSM Parameter Store."""
        try:
            # Get OAuth token for this user
            token_param = f"/life-stats/google-fit/{self.user_id}/token"
            response = self.ssm.get_parameter(Name=token_param, WithDecryption=True)
            token_data = response['Parameter']['Value']

            # Parse JSON credentials
            import json
            creds = json.loads(token_data)

            logger.info(f"Retrieved credentials for user {self.user_id}")

            return Credentials(
                token=creds.get('token'),
                refresh_token=creds.get('refresh_token'),
                token_uri=creds.get('token_uri'),
                client_id=creds.get('client_id'),
                client_secret=creds.get('client_secret'),
                scopes=creds.get('scopes')
            )
        except Exception as e:
            logger.error(f"Failed to retrieve credentials: {e}")
            raise

    def fetch_data(self, since: Optional[str] = None, until: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch steps data from Google Fit API."""
        start_date, end_date = self._get_date_range(since, until)

        logger.info(f"Fetching Google Fit steps for {self.user_id} from {start_date} to {end_date}")

        try:
            service = build('fitness', 'v1', credentials=self.credentials)

            # Convert to milliseconds for Google Fit API
            start_time_millis = int(start_date.timestamp() * 1000)
            end_time_millis = int(end_date.timestamp() * 1000)

            # Request daily step counts
            body = {
                "aggregateBy": [{
                    "dataTypeName": "com.google.step_count.delta",
                    "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
                }],
                "bucketByTime": {"durationMillis": 86400000},  # 1 day
                "startTimeMillis": start_time_millis,
                "endTimeMillis": end_time_millis
            }

            response = service.users().dataset().aggregate(userId='me', body=body).execute()

            data_points = []
            for bucket in response.get('bucket', []):
                for dataset in bucket.get('dataset', []):
                    for point in dataset.get('point', []):
                        if point.get('value'):
                            steps = sum(v.get('intVal', 0) for v in point['value'])
                            date_str = datetime.fromtimestamp(
                                int(point['startTimeNanos']) / 1e9,
                                tz=timezone.utc
                            ).strftime('%Y-%m-%d')

                            data_points.append({
                                'date': date_str,
                                'value': steps,
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            })
                            logger.debug(f"Fetched steps for {date_str}: {steps}")

            logger.info(f"Successfully fetched {len(data_points)} data points")
            return data_points

        except Exception as e:
            logger.error(f"Error fetching Google Fit data: {e}", exc_info=True)
            raise
