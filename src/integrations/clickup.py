from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import boto3
import requests
from integrations.base import BaseIntegration
from utils.logger import setup_logger

logger = setup_logger(__name__)


class ClickUpTasksIntegration(BaseIntegration):
    """ClickUp tasks integration - fetches completed tasks and calculates time spent per task type."""

    def __init__(self, user_id: str):
        super().__init__(user_id)
        self.ssm = boto3.client('ssm')
        self.api_token = self._get_api_token()
        self.list_id = self._get_list_id()
        self.team_id = self._get_team_id()
        self.base_url = "https://api.clickup.com/api/v2"
        self.custom_types = self._get_custom_types()

    def _get_api_token(self) -> str:
        """Retrieve ClickUp API token from SSM."""
        try:
            response = self.ssm.get_parameter(
                Name=f"/life-stats/clickup/{self.user_id}/token",
                WithDecryption=True
            )
            return response['Parameter']['Value']
        except Exception as e:
            logger.error(f"Failed to retrieve ClickUp API token: {e}")
            raise

    def _get_list_id(self) -> str:
        """Retrieve ClickUp List ID from SSM."""
        try:
            response = self.ssm.get_parameter(
                Name=f"/life-stats/clickup/{self.user_id}/list-id",
                WithDecryption=False
            )
            return response['Parameter']['Value']
        except Exception as e:
            logger.error(f"Failed to retrieve ClickUp List ID: {e}")
            raise

    def _get_team_id(self) -> str:
        """Retrieve ClickUp Team ID from SSM."""
        try:
            response = self.ssm.get_parameter(
                Name=f"/life-stats/clickup/{self.user_id}/team-id",
                WithDecryption=False
            )
            return response['Parameter']['Value']
        except Exception as e:
            logger.error(f"Failed to retrieve ClickUp Team ID: {e}")
            raise

    def _get_custom_types(self) -> Dict[int, str]:
        """Fetch custom task types from ClickUp API."""
        try:
            response = self._make_request(f"/team/{self.team_id}/custom_item")
            custom_types = {}
            for item in response.get('custom_items', []):
                custom_types[item['id']] = item['name']
            logger.info(f"Loaded {len(custom_types)} custom task types")
            return custom_types
        except Exception as e:
            logger.error(f"Failed to fetch custom task types: {e}")
            return {}

    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated request to ClickUp API."""
        headers = {
            "Authorization": self.api_token,
            "Content-Type": "application/json"
        }
        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def _calculate_duration_hours(self, start_time: int, end_time: int) -> float:
        """Calculate duration in hours from millisecond timestamps."""
        duration_ms = end_time - start_time
        duration_hours = duration_ms / (1000 * 60 * 60)
        return round(duration_hours, 2)

    def _split_task_by_day(self, task: Dict) -> List[Dict]:
        """Split task into separate entries if it spans multiple days."""
        start_ms = int(task['start_date'])
        end_ms = int(task['date_done'])
        
        start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)
        
        # Check if same day
        if start_dt.date() == end_dt.date():
            return [task]
        
        # Split across days
        split_tasks = []
        current_start = start_dt
        
        while current_start.date() <= end_dt.date():
            day_end = current_start.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            if day_end > end_dt:
                day_end = end_dt
            
            split_task = task.copy()
            split_task['start_date'] = str(int(current_start.timestamp() * 1000))
            split_task['date_done'] = str(int(day_end.timestamp() * 1000))
            split_tasks.append(split_task)
            
            # Move to next day
            current_start = (current_start + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        
        return split_tasks

    def fetch_data(self, since: Optional[str] = None, until: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch completed tasks from ClickUp and group by task type and date."""
        start_date, end_date = self._get_date_range(since, until)
        
        logger.info(f"Fetching ClickUp tasks for {self.user_id} from {start_date} to {end_date}")
        
        try:
            # Fetch tasks from list with status filter
            params = {
                "archived": "false",
                "include_closed": "true",
                "statuses[]": "done"
            }
            
            response = self._make_request(f"/list/{self.list_id}/task", params)
            tasks = response.get('tasks', [])
            
            logger.info(f"Fetched {len(tasks)} completed tasks from ClickUp")
            
            # Group by task type and date
            grouped_data = {}
            
            for task in tasks:
                # Skip tasks without required fields
                if not task.get('start_date') or not task.get('date_done'):
                    logger.debug(f"Skipping task {task.get('id')} - missing start/end time")
                    continue
                
                # Split task if it spans multiple days
                split_tasks = self._split_task_by_day(task)
                
                for split_task in split_tasks:
                    start_ms = int(split_task['start_date'])
                    end_ms = int(split_task['date_done'])
                    
                    task_date = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
                    
                    # Filter by date range
                    if task_date < start_date or task_date > end_date:
                        continue
                    
                    date_str = task_date.strftime('%Y-%m-%d')
                    
                    # Get task type from custom_item_id
                    custom_item_id = split_task.get('custom_item_id')
                    task_type = self.custom_types.get(custom_item_id, 'unknown')
                    
                    tags = [tag['name'] for tag in split_task.get('tags', [])]
                    
                    # Calculate duration
                    duration = self._calculate_duration_hours(start_ms, end_ms)
                    
                    # Create key for grouping
                    key = (date_str, task_type)
                    
                    if key not in grouped_data:
                        grouped_data[key] = {
                            'date': date_str,
                            'task_type': task_type,
                            'total_hours': 0,
                            'tags': set()
                        }
                    
                    grouped_data[key]['total_hours'] += duration
                    grouped_data[key]['tags'].update(tags)
            
            # Convert to output format
            data_points = []
            for (date_str, task_type), data in grouped_data.items():
                data_points.append({
                    'date': date_str,
                    'metric_type': task_type.lower().replace(' ', '_'),
                    'value': {
                        'hours': Decimal(str(round(data['total_hours'], 2))),
                        'tags': sorted(list(data['tags']))
                    },
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                logger.debug(f"Task type '{task_type}' on {date_str}: {data['total_hours']} hours")
            
            logger.info(f"Successfully processed {len(data_points)} task type/date combinations")
            return data_points
            
        except Exception as e:
            logger.error(f"Error fetching ClickUp data: {e}", exc_info=True)
            raise
