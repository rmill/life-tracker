from typing import Dict, Type, List
from integrations.base import BaseIntegration
from integrations.google_fit import GoogleFitStepsIntegration
from integrations.open_meteo import OpenMeteoWeatherIntegration
from utils.logger import setup_logger

logger = setup_logger(__name__)


class IntegrationRegistry:
    """Registry for all available metric integrations."""

    _integrations: Dict[str, Type[BaseIntegration]] = {
        'steps': GoogleFitStepsIntegration,
        'weather': OpenMeteoWeatherIntegration,
    }

    def get_integration(self, metric_name: str, user_id: str) -> BaseIntegration:
        """Get integration instance for a metric."""
        integration_class = self._integrations.get(metric_name)
        if not integration_class:
            raise ValueError(f"Unknown metric: {metric_name}")

        logger.debug(f"Creating integration for metric '{metric_name}'")
        return integration_class(user_id)

    def list_metrics(self) -> List[str]:
        """List all available metrics."""
        return list(self._integrations.keys())

    @classmethod
    def register(cls, metric_name: str, integration_class: Type[BaseIntegration]) -> None:
        """Register a new integration."""
        cls._integrations[metric_name] = integration_class
        logger.info(f"Registered integration for metric '{metric_name}'")
