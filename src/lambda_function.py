import json
from typing import Dict, Any
from integrations.registry import IntegrationRegistry
from utils.db import MetricsDB
from utils.logger import setup_logger

logger = setup_logger(__name__)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for metrics collection.

    Event payload:
    - metric: Optional[str] - Specific metric to run (e.g., 'steps'). If not provided, runs all.
    - user_id: Optional[str] - Specific user. If not provided, runs for all users.
    - start_date: Optional[str] - Start date (YYYY-MM-DD). Overrides last_run logic.
    - end_date: Optional[str] - End date (YYYY-MM-DD). Defaults to now.
    """
    logger.info(f"Lambda invoked with event: {json.dumps(event)}")

    metric_name = event.get('metric')
    user_id = event.get('user_id')
    start_date = event.get('start_date')
    end_date = event.get('end_date')

    db = MetricsDB()
    registry = IntegrationRegistry()

    results = []
    errors = []

    try:
        # Determine which metrics to run
        if metric_name:
            metrics_to_run = [metric_name]
            logger.info(f"Running single metric: {metric_name}")
        else:
            metrics_to_run = registry.list_metrics()
            logger.info(f"Running all metrics: {metrics_to_run}")

        # Determine which users to process
        users = [user_id] if user_id else db.get_all_users()
        logger.info(f"Processing {len(users)} user(s)")

        # Process each metric for each user
        for metric in metrics_to_run:
            for uid in users:
                try:
                    logger.info(f"Processing metric '{metric}' for user '{uid}'")
                    integration = registry.get_integration(metric, uid)

                    # Get last run time or use provided start_date
                    if start_date:
                        last_run = start_date  # Pass as-is, will be parsed as YYYY-MM-DD
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
                        results.append({
                            'user_id': uid,
                            'metric': metric,
                            'count': len(data_points),
                            'status': 'success'
                        })
                        logger.info(f"Successfully stored {len(data_points)} points for {uid}/{metric}")
                    else:
                        logger.info(f"No new data for {uid}/{metric}")
                        results.append({
                            'user_id': uid,
                            'metric': metric,
                            'count': 0,
                            'status': 'no_data'
                        })

                except Exception as e:
                    error_msg = f"Error processing {metric} for {uid}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    errors.append({
                        'user_id': uid,
                        'metric': metric,
                        'error': str(e)
                    })

        response = {
            'statusCode': 200 if not errors else 207,
            'body': json.dumps({
                'results': results,
                'errors': errors,
                'total_processed': len(results),
                'total_errors': len(errors)
            })
        }

        logger.info(f"Lambda execution completed: {len(results)} successful, {len(errors)} errors")
        return response

    except Exception as e:
        logger.error(f"Fatal error in Lambda handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
