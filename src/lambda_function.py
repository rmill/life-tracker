import json
from typing import Dict, Any
from integrations.registry import IntegrationRegistry
from utils.db import MetricsDB
from utils.logger import setup_logger

logger = setup_logger(__name__)


def _process_metric(uid: str, metric: str, integration, db: MetricsDB, start_date: str, end_date: str) -> Dict[str, Any]:
    """Process a single metric for a user."""
    logger.info(f"Processing metric '{metric}' for user '{uid}'")

    # Get last run time or use provided start_date
    if start_date:
        last_run = start_date
        logger.info(f"Using provided start_date: {start_date}")
    else:
        last_run = db.get_last_run(uid, metric)
        logger.info(f"Last run for {uid}/{metric}: {last_run}")

    # Fetch and store data
    data_points = integration.fetch_data(last_run, end_date)
    logger.info(f"Fetched {len(data_points)} data points")

    # Log actual values
    for point in data_points:
        logger.info(f"{uid}/{metric} - {point['date']}: {point['value']}")

    if data_points:
        db.store_metrics(uid, metric, data_points)
        # Only update last_run if not using manual date override
        if not start_date:
            db.update_last_run(uid, metric)
        logger.info(f"Successfully stored {len(data_points)} points for {uid}/{metric}")
        return {'user_id': uid, 'metric': metric, 'count': len(data_points), 'status': 'success'}
    else:
        logger.info(f"No new data for {uid}/{metric}")
        return {'user_id': uid, 'metric': metric, 'count': 0, 'status': 'no_data'}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for metrics collection.

    Event payload:
    - metric: Optional[str] - Specific metric to run (e.g., 'steps'). If not provided, runs all.
    - user_id: Optional[str] - Specific user. If not provided, runs for all users.
    - start_date: Optional[str] - Start date (YYYY-MM-DD). Overrides last_run logic.
    - end_date: Optional[str] - End date (YYYY-MM-DD). Defaults to now.
    """
    metric_name = event.get('metric')
    user_id = event.get('user_id')
    start_date = event.get('start_date')
    end_date = event.get('end_date')

    # Determine run type
    is_manual = bool(start_date or end_date)
    run_type = "MANUAL" if is_manual else "AUTOMATIC"

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
