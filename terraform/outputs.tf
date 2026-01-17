output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.metrics_collector.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.metrics_collector.arn
}

output "metrics_table_name" {
  description = "Name of the metrics DynamoDB table"
  value       = aws_dynamodb_table.metrics.name
}

output "runs_table_name" {
  description = "Name of the runs DynamoDB table"
  value       = aws_dynamodb_table.runs.name
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group name"
  value       = aws_cloudwatch_log_group.lambda_logs.name
}

output "eventbridge_rule_name" {
  description = "EventBridge rule name"
  value       = aws_cloudwatch_event_rule.daily_trigger.name
}
