# Life Stats POC

Automated daily metrics collection system using AWS Lambda, DynamoDB, and external API integrations.

## Architecture

- **Lambda**: Python 3.11 function for metric collection
- **DynamoDB**: Two tables for metrics storage and run tracking
- **EventBridge**: Triggers Lambda every 24 hours
- **SSM Parameter Store**: Stores API credentials securely
- **Terraform**: Infrastructure as Code
- **GitHub Actions**: CI/CD pipeline with OIDC authentication

## Features

- ✅ Idempotent metric collection
- ✅ Tracks last run to fetch incremental data
- ✅ Fetches previous 7 days on first run
- ✅ Supports multiple users and metrics
- ✅ Extensible integration framework
- ✅ Detailed CloudWatch logging
- ✅ Horizontal scaling (run all metrics or single metric)

## Project Structure

```
life-stats/
├── src/
│   ├── lambda_function.py          # Lambda handler
│   ├── integrations/
│   │   ├── base.py                 # Base integration class
│   │   ├── google_fit.py           # Google Fit implementation
│   │   └── registry.py             # Integration registry
│   └── utils/
│       ├── db.py                   # DynamoDB interface
│       └── logger.py               # CloudWatch logging
├── terraform/
│   ├── main.tf                     # Infrastructure definition
│   ├── variables.tf                # Configuration variables
│   └── outputs.tf                  # Output values
├── scripts/
│   ├── setup-aws.sh                # AWS setup automation
│   ├── test-local.py               # Local testing script
│   ├── config.env.example          # Configuration template
│   └── test-event.json             # Example test event
├── .github/
│   └── workflows/
│       └── deploy.yml              # CI/CD pipeline
└── requirements-lambda.txt         # Python dependencies

```

## Database Schema

### Metrics Table (`life-stats-metrics`)
```
Partition Key: user_id (String)
Sort Key: metric_date (String) - format: "YYYY-MM-DD#metric_type"

Attributes:
- metric_type: String (e.g., "steps")
- date: String (YYYY-MM-DD)
- value: Number
- timestamp: String (ISO 8601)
```

### Runs Table (`life-stats-runs`)
```
Partition Key: user_id (String)
Sort Key: metric_type (String)

Attributes:
- last_run_time: String (ISO 8601)
```

## Setup

### Prerequisites
- AWS CLI configured with appropriate credentials
- Terraform >= 1.0
- Python 3.11+
- GitHub repository (for CI/CD)

### Step 1: Configure Setup

```bash
# Copy example config
cp scripts/config.env.example scripts/config.env

# Edit config.env with your values:
# - AWS_REGION
# - GITHUB_REPO (owner/repo)
# - GITHUB_BRANCH
# - GOOGLE_FIT_CLIENT_ID (optional)
# - GOOGLE_FIT_CLIENT_SECRET (optional)
```

### Step 2: Run AWS Setup

```bash
./scripts/setup-aws.sh
```

This script will:
- Create GitHub OIDC provider in AWS
- Create IAM role for GitHub Actions
- Store Google Fit credentials in SSM (if provided)
- Output the IAM role ARN

### Step 3: Configure GitHub

Add the following secret to your GitHub repository:
- `AWS_ROLE_ARN`: The IAM role ARN from setup script output

**Settings → Secrets and variables → Actions → New repository secret**

### Step 4: Deploy Infrastructure

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

Or push to main branch to trigger GitHub Actions deployment:

```bash
git add .
git commit -m "Initial deployment"
git push origin main
```

### Step 5: Add User OAuth Tokens

For each user, store their Google Fit OAuth token:

```bash
aws ssm put-parameter \
  --name "/life-stats/google-fit/USER_ID/token" \
  --value "USER_OAUTH_TOKEN" \
  --type SecureString
```

## Local Development

### Setup Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-lambda.txt
```

## Testing

### Run Functional Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_functional.py::test_database_schema_metrics
```

**Note:** Functional tests require AWS credentials and will create temporary DynamoDB tables (`life-stats-metrics-test`, `life-stats-runs-test`).

### Test External API Integrations

Validate connectivity and authentication with external services:

```bash
# Run external API tests
pytest tests/test_external_api.py -v

# Run with live API calls and OAuth auto-generation (opens browser)
TEST_USER_ID=your-test-user AUTO_GENERATE_OAUTH=true SKIP_LIVE_API_TESTS=false pytest tests/test_external_api.py -v

# Run with existing OAuth token
TEST_USER_ID=your-test-user SKIP_LIVE_API_TESTS=false pytest tests/test_external_api.py -v
```

**Note:** External API tests validate Google Fit integration, credential configuration, and API client libraries. Live API tests require a valid OAuth token.

### Run Integration Tests

Integration tests validate the deployed infrastructure:

```bash
# Run integration tests against deployed resources
pytest tests/test_integration.py -v

# Run with OAuth token generation (opens browser for authorization)
TEST_USER_ID=your-test-user AUTO_GENERATE_OAUTH=true pytest tests/test_integration.py::test_end_to_end_with_real_oauth -v

# Run with existing OAuth token
TEST_USER_ID=your-test-user pytest tests/test_integration.py::test_end_to_end_with_real_oauth -v
```

**Note:** Integration tests require the infrastructure to be deployed and AWS credentials configured. The `test_end_to_end_with_real_oauth` test requires a valid Google Fit OAuth token.

### Manual Testing

Test the Lambda function manually without pytest:

```bash
# Test all metrics for all users
./scripts/test-local.py

# Test specific metric
./scripts/test-local.py --metric steps

# Test specific user
./scripts/test-local.py --user-id test-user

# Use custom event
./scripts/test-local.py --event scripts/test-event.json
```

**Note:** Local testing requires AWS credentials configured for DynamoDB and SSM access.

## Adding New Integrations

1. Create new integration class in `src/integrations/`:

```python
from integrations.base import BaseIntegration

class MyIntegration(BaseIntegration):
    def fetch_data(self, since=None):
        # Implement data fetching logic
        return [
            {'date': '2026-01-17', 'value': 123, 'timestamp': '...'}
        ]
```

2. Register in `src/integrations/registry.py`:

```python
from integrations.my_integration import MyIntegration

class IntegrationRegistry:
    _integrations = {
        'steps': GoogleFitStepsIntegration,
        'my_metric': MyIntegration,  # Add here
    }
```

3. Deploy updated Lambda function

## Lambda Event Format

```json
{
  "metric": "steps",      // Optional: specific metric to run
  "user_id": "user123"    // Optional: specific user to process
}
```

- No parameters: Runs all metrics for all users
- `metric` only: Runs specific metric for all users
- `user_id` only: Runs all metrics for specific user
- Both: Runs specific metric for specific user

## Monitoring

### CloudWatch Logs

```bash
aws logs tail /aws/lambda/life-stats --follow
```

### Query Metrics

```bash
# Get all metrics for a user
aws dynamodb query \
  --table-name life-stats-metrics \
  --key-condition-expression "user_id = :uid" \
  --expression-attribute-values '{":uid":{"S":"user123"}}'

# Get specific metric for date range
aws dynamodb query \
  --table-name life-stats-metrics \
  --key-condition-expression "user_id = :uid AND metric_date BETWEEN :start AND :end" \
  --expression-attribute-values '{
    ":uid":{"S":"user123"},
    ":start":{"S":"2026-01-01#steps"},
    ":end":{"S":"2026-01-31#steps"}
  }'
```

### Manual Lambda Invocation

```bash
# Run all metrics
aws lambda invoke \
  --function-name life-stats \
  --payload '{}' \
  response.json

# Run specific metric
aws lambda invoke \
  --function-name life-stats \
  --payload '{"metric":"steps"}' \
  response.json
```

## Troubleshooting

### Lambda fails with "No users found"
- Add a user's OAuth token to SSM Parameter Store
- Or manually add a record to the runs table

### "Access Denied" errors
- Verify IAM role has correct permissions
- Check SSM parameter names match expected format

### Google Fit API errors
- Verify OAuth token is valid and not expired
- Check client ID and secret are correct
- Ensure Google Fit API is enabled in Google Cloud Console

## Cost Estimation

**Monthly costs (approximate):**
- Lambda: ~$0.20 (1 invocation/day, 30s runtime)
- DynamoDB: ~$1-5 (depends on data volume)
- CloudWatch Logs: ~$0.50
- SSM Parameter Store: Free tier

**Total: ~$2-6/month** for typical usage

## Security Best Practices

- ✅ Credentials stored in SSM Parameter Store (encrypted)
- ✅ IAM roles with least privilege
- ✅ GitHub Actions uses OIDC (no long-lived credentials)
- ✅ CloudWatch logs for audit trail
- ⚠️ Rotate OAuth tokens regularly
- ⚠️ Review IAM policies periodically

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally with `./scripts/test-local.py`
5. Submit a pull request

## Support

For issues or questions, please open a GitHub issue.
