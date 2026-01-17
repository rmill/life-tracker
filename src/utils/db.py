import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import boto3
from utils.logger import setup_logger

logger = setup_logger(__name__)


class MetricsDB:
    """DynamoDB interface for metrics storage."""

    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.metrics_table = self.dynamodb.Table(os.environ.get('METRICS_TABLE', 'life-stats-metrics'))
        self.runs_table = self.dynamodb.Table(os.environ.get('RUNS_TABLE', 'life-stats-runs'))

    def store_metrics(self, user_id: str, metric_type: str, data_points: List[Dict[str, Any]]) -> None:
        """Store metric data points in DynamoDB."""
        with self.metrics_table.batch_writer() as batch:
            for point in data_points:
                item = {
                    'user_id': user_id,
                    'metric_date': f"{point['date']}#{metric_type}",
                    'metric_type': metric_type,
                    'date': point['date'],
                    'value': point['value'],
                    'timestamp': point.get('timestamp', datetime.now(timezone.utc).isoformat())
                }
                batch.put_item(Item=item)
                logger.debug(f"Stored metric: {item}")

    def get_last_run(self, user_id: str, metric_type: str) -> Optional[str]:
        """Get the last successful run timestamp for a user/metric."""
        try:
            response = self.runs_table.get_item(
                Key={
                    'user_id': user_id,
                    'metric_type': metric_type
                }
            )
            last_run = response.get('Item', {}).get('last_run_time')
            logger.debug(f"Retrieved last run for {user_id}/{metric_type}: {last_run}")
            return last_run
        except Exception as e:
            logger.warning(f"Could not retrieve last run: {e}")
            return None

    def update_last_run(self, user_id: str, metric_type: str) -> None:
        """Update the last run timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        self.runs_table.put_item(
            Item={
                'user_id': user_id,
                'metric_type': metric_type,
                'last_run_time': now
            }
        )
        logger.debug(f"Updated last run for {user_id}/{metric_type}: {now}")

    def get_all_users(self) -> List[str]:
        """Get list of all users from runs table."""
        try:
            response = self.runs_table.scan(
                ProjectionExpression='user_id'
            )
            users = list(set(item['user_id'] for item in response.get('Items', [])))
            logger.debug(f"Found {len(users)} users")
            return users if users else ['default']  # Return default user if none exist
        except Exception as e:
            logger.warning(f"Could not retrieve users: {e}")
            return ['default']
