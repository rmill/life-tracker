from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone


class BaseIntegration(ABC):
    """Base class for all metric integrations."""

    def __init__(self, user_id: str):
        self.user_id = user_id

    @abstractmethod
    def fetch_data(self, since: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch metric data from external API.

        Args:
            since: ISO timestamp of last run. If None, fetch last 7 days.

        Returns:
            List of data points: [{'date': 'YYYY-MM-DD', 'value': float, 'timestamp': str}, ...]
        """
        pass

    def _get_date_range(self, since: Optional[str] = None) -> Tuple[datetime, datetime]:
        """Calculate date range for data fetch."""
        end_date = datetime.now(timezone.utc)

        if since:
            start_date = datetime.fromisoformat(since.replace('Z', '+00:00'))
        else:
            # First run: fetch last 7 days
            start_date = end_date - timedelta(days=7)

        return start_date, end_date
