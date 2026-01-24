from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone


class BaseIntegration(ABC):
    """Base class for all metric integrations."""

    def __init__(self, user_id: str):
        self.user_id = user_id

    @abstractmethod
    def fetch_data(self, since: Optional[str] = None, until: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch metric data from external API.

        Args:
            since: ISO timestamp of last run. If None, fetch last 7 days.
            until: ISO timestamp or YYYY-MM-DD for end date. If None, use now.

        Returns:
            List of data points: [{'date': 'YYYY-MM-DD', 'value': float, 'timestamp': str}, ...]
        """
        pass

    def _get_date_range(self, since: Optional[str] = None, until: Optional[str] = None) -> Tuple[datetime, datetime]:
        """Calculate date range for data fetch."""
        if until:
            # Parse until date (could be YYYY-MM-DD or ISO timestamp)
            try:
                end_date = datetime.strptime(until, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            except ValueError:
                end_date = datetime.fromisoformat(until.replace('Z', '+00:00'))
        else:
            end_date = datetime.now(timezone.utc)

        if since:
            try:
                # Try parsing as YYYY-MM-DD first (manual override)
                start_date = datetime.strptime(since, '%Y-%m-%d').replace(hour=0, minute=0, second=0, tzinfo=timezone.utc)
            except ValueError:
                # ISO timestamp from last_run - fetch previous day at midnight
                last_run = datetime.fromisoformat(since.replace('Z', '+00:00'))
                start_date = (last_run - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # First run: fetch last 7 days
            start_date = end_date - timedelta(days=7)

        return start_date, end_date
