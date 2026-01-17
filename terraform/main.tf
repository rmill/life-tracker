terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket = "life-stats-terraform-state"
    key    = "terraform.tfstate"
    region = "us-west-2"
  }
}

provider "aws" {
  region = var.aws_region
}

# DynamoDB Table - Metrics
resource "aws_dynamodb_table" "metrics" {
  name           = "${var.project_name}-metrics"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "user_id"
  range_key      = "metric_date"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "metric_date"
    type = "S"
  }

  tags = {
    Name        = "${var.project_name}-metrics"
    Environment = var.environment
    Project     = var.project_name
  }
}

# DynamoDB Table - Runs
resource "aws_dynamodb_table" "runs" {
  name           = "${var.project_name}-runs"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "user_id"
  range_key      = "metric_type"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "metric_type"
    type = "S"
  }

  tags = {
    Name        = "${var.project_name}-runs"
    Environment = var.environment
    Project     = var.project_name
  }
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-lambda-role"
    Environment = var.environment
    Project     = var.project_name
  }
}

# IAM Policy for Lambda
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchWriteItem"
        ]
        Resource = [
          aws_dynamodb_table.metrics.arn,
          aws_dynamodb_table.runs.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:*:parameter/${var.project_name}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/${var.project_name}*"
      }
    ]
  })
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.project_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "${var.project_name}-logs"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Lambda Function Package
resource "null_resource" "lambda_package" {
  triggers = {
    requirements = filemd5("${path.module}/../requirements-lambda.txt")
    source_hash  = sha256(join("", [for f in fileset("${path.module}/../src", "**") : filesha256("${path.module}/../src/${f}")]))
  }

  provisioner "local-exec" {
    command = <<EOF
      cd ${path.module}/..
      rm -rf lambda_package
      mkdir -p lambda_package
      cp -r src/* lambda_package/
      pip install -r requirements-lambda.txt -t lambda_package/ --upgrade
      cd lambda_package && zip -r ../terraform/lambda_function.zip . -x "*.pyc" -x "__pycache__/*"
    EOF
  }
}

resource "aws_lambda_function" "metrics_collector" {
  filename         = "${path.module}/lambda_function.zip"
  function_name    = var.project_name
  role            = aws_iam_role.lambda_role.arn
  handler         = "lambda_function.handler"
  source_code_hash = filebase64sha256("${path.module}/lambda_function.zip")
  runtime         = "python3.11"
  timeout         = 300
  memory_size     = 256

  environment {
    variables = {
      METRICS_TABLE = aws_dynamodb_table.metrics.name
      RUNS_TABLE    = aws_dynamodb_table.runs.name
      LOG_LEVEL     = "INFO"
    }
  }

  tags = {
    Name        = var.project_name
    Environment = var.environment
    Project     = var.project_name
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_logs,
    aws_iam_role_policy.lambda_policy,
    null_resource.lambda_package
  ]
}

# EventBridge Rule - Daily Trigger
resource "aws_cloudwatch_event_rule" "daily_trigger" {
  name                = "${var.project_name}-daily-trigger"
  description         = "Trigger metrics collection every 24 hours"
  schedule_expression = var.schedule_expression

  tags = {
    Name        = "${var.project_name}-daily-trigger"
    Environment = var.environment
    Project     = var.project_name
  }
}

# EventBridge Target
resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.daily_trigger.name
  target_id = "MetricsCollectorLambda"
  arn       = aws_lambda_function.metrics_collector.arn
}

# Lambda Permission for EventBridge
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.metrics_collector.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_trigger.arn
}
