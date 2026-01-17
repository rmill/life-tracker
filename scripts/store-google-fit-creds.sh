#!/bin/bash
# Script to store Google Fit credentials in SSM Parameter Store
# Run this after AWS setup is complete

set -e

echo "=== Store Google Fit Credentials in SSM ==="
echo

read -p "Enter Google Fit Client ID: " CLIENT_ID
read -sp "Enter Google Fit Client Secret: " CLIENT_SECRET
echo

AWS_REGION=${AWS_REGION:-us-west-2}

echo
echo "Storing credentials in SSM Parameter Store (region: $AWS_REGION)..."

aws ssm put-parameter \
  --name "/life-stats/google-fit/client-id" \
  --value "$CLIENT_ID" \
  --type SecureString \
  --overwrite \
  --region "$AWS_REGION"

aws ssm put-parameter \
  --name "/life-stats/google-fit/client-secret" \
  --value "$CLIENT_SECRET" \
  --type SecureString \
  --overwrite \
  --region "$AWS_REGION"

echo
echo "✓ Credentials stored successfully!"
echo
echo "Verify with:"
echo "  aws ssm get-parameter --name '/life-stats/google-fit/client-id' --region $AWS_REGION"
