import json
from typing import Dict, Any, List
from integrations.registry import IntegrationRegistry
from utils.db import MetricsDB
from utils.logger import setup_logger

logger = setup_logger(__name__)


def _store_dynamic_metrics(uid: str, metric: str, data_points: List[Dict], db: MetricsDB, start_date: str) -> Dict[str, Any]:
    """Store metrics with dynamic types (e.g., ClickUp tasks)."""
    grouped = {}
    for point in data_points:
        mt = point.get('metric_type', metric)
        if mt not in grouped:
            grouped[mt] = []
        grouped[mt].append(point)

    total_stored = 0
    for metric_type, points in grouped.items():
        for point in points:
            logger.info(f"{uid}/{metric_type} - {point['date']}: {point['value']}")

        db.store_metrics(uid, metric_type, points)
        total_stored += len(points)
        logger.info(f"Successfully stored {len(points)} points for {uid}/{metric_type}")

    if not start_date:
        db.update_last_run(uid, metric)

    return {'user_id': uid, 'metric': metric, 'count': total_stored, 'status': 'success'}


def _store_single_metric(uid: str, metric: str, data_points: List[Dict], db: MetricsDB, start_date: str) -> Dict[str, Any]:
    """Store metrics with single type."""
    for point in data_points:
        logger.info(f"{uid}/{metric} - {point['date']}: {point['value']}")

    db.store_metrics(uid, metric, data_points)

    if not start_date:
        db.update_last_run(uid, metric)

    logger.info(f"Successfully stored {len(data_points)} points for {uid}/{metric}")
    return {'user_id': uid, 'metric': metric, 'count': len(data_points), 'status': 'success'}


def _process_metric(uid: str, metric: str, integration, db: MetricsDB, start_date: str, end_date: str) -> Dict[str, Any]:
    """Process a single metric for a user."""
    logger.info(f"Processing metric '{metric}' for user '{uid}'")

    # Get last run time or use provided start_date
    last_run = start_date if start_date else db.get_last_run(uid, metric)
    logger.info(f"Using {'provided start_date' if start_date else 'last run'}: {last_run}")

    # Fetch data
    data_points = integration.fetch_data(last_run, end_date)
    logger.info(f"Fetched {len(data_points)} data points")

    if not data_points:
        logger.info(f"No new data for {uid}/{metric}")
        return {'user_id': uid, 'metric': metric, 'count': 0, 'status': 'no_data'}

    # Check if data points have dynamic metric_type
    has_dynamic_types = any('metric_type' in point for point in data_points)

    if has_dynamic_types:
        return _store_dynamic_metrics(uid, metric, data_points, db, start_date)
    else:
        return _store_single_metric(uid, metric, data_points, db, start_date)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for metrics collection.

    Event payload:
    - metric: Optional[str] - Specific metric to run (e.g., 'steps'). If not provided, runs all.
    - user_id: Optional[str] - Specific user. If not provided, runs for all users.
    - start_date: Optional[str] - Start date (YYYY-MM-DD). Overrides last_run logic.
    - end_date: Optional[str] - End date (YYYY-MM-DD). Defaults to now.
    - source: Optional[str] - Source of invocation (e.g., 'manual', 'eventbridge').
    """
    metric_name = event.get('metric')
    user_id = event.get('user_id')
    start_date = event.get('start_date')
    end_date = event.get('end_date')
    source = event.get('source', 'eventbridge')

    # Determine run type
    run_type = "MANUAL" if source == 'manual' else "AUTOMATIC"

    # Log run parameters
    logger.info(f"=== Lambda Invocation ({run_type}) ===")
    logger.info(f"User ID: {user_id or 'all users'}")
    logger.info(f"Metric: {metric_name or 'all metrics'}")
    logger.info(f"Start Date: {start_date or 'from last run'}")
    logger.info(f"End Date: {end_date or 'now'}")
    logger.info("=" * 50)

    db = MetricsDB()
    registry = IntegrationRegistry()

    results = []
    errors = []

    try:
        # Determine which metrics to run
        metrics_to_run = [metric_name] if metric_name else registry.list_metrics()
        logger.info(f"Running metrics: {metrics_to_run}")

        # Determine which users to process
        users = [user_id] if user_id else db.get_all_users()
        logger.info(f"Processing {len(users)} user(s)")

        # Process each metric for each user
        for metric in metrics_to_run:
            for uid in users:
                try:
                    integration = registry.get_integration(metric, uid)
                    result = _process_metric(uid, metric, integration, db, start_date, end_date)
                    results.append(result)
                except Exception as e:
                    error_msg = f"Error processing {metric} for {uid}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    errors.append({'user_id': uid, 'metric': metric, 'error': str(e)})

        logger.info(f"Lambda execution completed: {len(results)} successful, {len(errors)} errors")
        return {
            'statusCode': 200 if not errors else 207,
            'body': json.dumps({
                'results': results,
                'errors': errors,
                'total_processed': len(results),
                'total_errors': len(errors)
            })
        }

    except Exception as e:
        logger.error(f"Fatal error in Lambda handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
