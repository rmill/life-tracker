#!/bin/bash
# Copy OAuth token from local AWS to pipeline AWS account

USER_ID=${1:-zerocool}

echo "Fetching token from local AWS account..."
TOKEN_VALUE=$(aws ssm get-parameter \
  --name "/life-stats/google-fit/${USER_ID}/token" \
  --with-decryption \
  --query 'Parameter.Value' \
  --output text)

echo "Storing token in pipeline AWS account..."
# You'll need to configure pipeline AWS credentials first
aws ssm put-parameter \
  --name "/life-stats/google-fit/${USER_ID}/token" \
  --value "$TOKEN_VALUE" \
  --type SecureString \
  --overwrite

echo "✓ Token copied successfully!"
