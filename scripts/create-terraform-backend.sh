#!/bin/bash
# Create S3 bucket for Terraform state

set -e

BUCKET_NAME="life-stats-terraform-state"
REGION="us-west-2"

echo "Creating S3 bucket for Terraform state..."

aws s3api create-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION" 2>/dev/null || echo "Bucket may already exist"

aws s3api put-bucket-versioning \
  --bucket "$BUCKET_NAME" \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket "$BUCKET_NAME" \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

echo "✓ S3 bucket created and configured: $BUCKET_NAME"
