#!/bin/bash
# Import existing AWS resources into Terraform state

set -e

cd "$(dirname "$0")/../terraform"

echo "Importing existing resources into Terraform state..."

# Import DynamoDB tables
terraform import aws_dynamodb_table.metrics life-stats-metrics 2>/dev/null || echo "Metrics table already in state"
terraform import aws_dynamodb_table.runs life-stats-runs 2>/dev/null || echo "Runs table already in state"

# Import IAM role and policy
terraform import aws_iam_role.lambda_role life-stats-lambda-role 2>/dev/null || echo "Lambda role already in state"
terraform import aws_iam_role_policy.lambda_policy life-stats-lambda-role:life-stats-lambda-policy 2>/dev/null || echo "Lambda policy already in state"

# Import CloudWatch log group
terraform import aws_cloudwatch_log_group.lambda_logs /aws/lambda/life-stats 2>/dev/null || echo "Log group already in state"

# Import Lambda function
terraform import aws_lambda_function.metrics_collector life-stats 2>/dev/null || echo "Lambda already in state"

# Import EventBridge rule and target
terraform import aws_cloudwatch_event_rule.daily_trigger life-stats-daily-trigger 2>/dev/null || echo "EventBridge rule already in state"
terraform import aws_cloudwatch_event_target.lambda_target life-stats-daily-trigger/MetricsCollectorLambda 2>/dev/null || echo "EventBridge target already in state"

# Import Lambda permission
terraform import aws_lambda_permission.allow_eventbridge life-stats/AllowExecutionFromEventBridge 2>/dev/null || echo "Lambda permission already in state"

echo "✓ Import complete! Run 'terraform plan' to verify."
