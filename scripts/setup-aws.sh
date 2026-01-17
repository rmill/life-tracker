#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config.env"

echo -e "${GREEN}=== Life Stats AWS Setup ===${NC}\n"

# Check prerequisites
command -v aws >/dev/null 2>&1 || { echo -e "${RED}Error: AWS CLI is required but not installed.${NC}" >&2; exit 1; }

# Load config file if exists
if [ -f "$CONFIG_FILE" ]; then
    echo -e "${GREEN}Loading configuration from config.env${NC}"
    source "$CONFIG_FILE"
else
    echo -e "${YELLOW}No config.env found. Copy config.env.example to config.env and customize it.${NC}"
    echo -e "${YELLOW}Falling back to interactive mode...${NC}\n"
fi

# Get inputs (use config values as defaults)
read -p "Enter AWS Region [${AWS_REGION:-us-west-2}]: " INPUT_REGION
AWS_REGION=${INPUT_REGION:-${AWS_REGION:-us-west-2}}

read -p "Enter GitHub repository (format: owner/repo) [${GITHUB_REPO}]: " INPUT_REPO
GITHUB_REPO=${INPUT_REPO:-${GITHUB_REPO}}
if [ -z "$GITHUB_REPO" ]; then
    echo -e "${RED}Error: GitHub repository is required${NC}"
    exit 1
fi

read -p "Enter GitHub branch [${GITHUB_BRANCH:-main}]: " INPUT_BRANCH
GITHUB_BRANCH=${INPUT_BRANCH:-${GITHUB_BRANCH:-main}}

echo -e "\n${YELLOW}Getting AWS account ID...${NC}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}Account ID: ${AWS_ACCOUNT_ID}${NC}"

# Create OIDC provider for GitHub Actions
echo -e "\n${YELLOW}Setting up GitHub OIDC provider...${NC}"
OIDC_PROVIDER_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"

if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_PROVIDER_ARN" 2>/dev/null; then
    echo -e "${GREEN}OIDC provider already exists${NC}"
else
    aws iam create-open-id-connect-provider \
        --url https://token.actions.githubusercontent.com \
        --client-id-list sts.amazonaws.com \
        --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
    echo -e "${GREEN}OIDC provider created${NC}"
fi

# Create IAM role for GitHub Actions
echo -e "\n${YELLOW}Creating IAM role for GitHub Actions...${NC}"
ROLE_NAME="life-stats-github-actions"

TRUST_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "${OIDC_PROVIDER_ARN}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${GITHUB_REPO}:ref:refs/heads/${GITHUB_BRANCH}"
        }
      }
    }
  ]
}
EOF
)

if aws iam get-role --role-name "$ROLE_NAME" 2>/dev/null; then
    echo -e "${YELLOW}Role exists, updating trust policy...${NC}"
    aws iam update-assume-role-policy --role-name "$ROLE_NAME" --policy-document "$TRUST_POLICY"
else
    aws iam create-role --role-name "$ROLE_NAME" --assume-role-policy-document "$TRUST_POLICY"
    echo -e "${GREEN}Role created${NC}"
fi

# Attach policies to role
echo -e "\n${YELLOW}Attaching policies to role...${NC}"

INLINE_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:*",
        "lambda:*",
        "iam:*",
        "logs:*",
        "events:*",
        "ssm:GetParameter",
        "ssm:GetParameters"
      ],
      "Resource": "*"
    }
  ]
}
EOF
)

aws iam put-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "life-stats-deployment" \
    --policy-document "$INLINE_POLICY"

echo -e "${GREEN}Policies attached${NC}"

ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"

# Setup SSM parameters for Google Fit
echo -e "\n${YELLOW}Setting up SSM parameters...${NC}"

# Check if credentials are in config file
if [ -n "$GOOGLE_FIT_CLIENT_ID" ] && [ -n "$GOOGLE_FIT_CLIENT_SECRET" ]; then
    echo -e "${GREEN}Using Google Fit credentials from config file${NC}"
    SETUP_GOOGLE="y"
else
    read -p "Do you want to configure Google Fit credentials now? (y/n) [n]: " SETUP_GOOGLE
    SETUP_GOOGLE=${SETUP_GOOGLE:-n}
fi

if [ "$SETUP_GOOGLE" = "y" ]; then
    # Prompt only if not in config
    if [ -z "$GOOGLE_FIT_CLIENT_ID" ]; then
        read -p "Enter Google Fit Client ID: " GOOGLE_FIT_CLIENT_ID
    fi
    if [ -z "$GOOGLE_FIT_CLIENT_SECRET" ]; then
        read -sp "Enter Google Fit Client Secret: " GOOGLE_FIT_CLIENT_SECRET
        echo
    fi
    
    aws ssm put-parameter \
        --name "/life-stats/google-fit/client-id" \
        --value "$GOOGLE_FIT_CLIENT_ID" \
        --type SecureString \
        --overwrite \
        --region "$AWS_REGION" 2>/dev/null || true
    
    aws ssm put-parameter \
        --name "/life-stats/google-fit/client-secret" \
        --value "$GOOGLE_FIT_CLIENT_SECRET" \
        --type SecureString \
        --overwrite \
        --region "$AWS_REGION" 2>/dev/null || true
    
    echo -e "${GREEN}Google Fit credentials stored in SSM${NC}"
    echo -e "${YELLOW}Note: You'll need to add user-specific OAuth tokens later${NC}"
else
    echo -e "${YELLOW}Skipping Google Fit setup. You can add credentials later with:${NC}"
    echo "aws ssm put-parameter --name '/life-stats/google-fit/client-id' --value 'YOUR_CLIENT_ID' --type SecureString"
    echo "aws ssm put-parameter --name '/life-stats/google-fit/client-secret' --value 'YOUR_CLIENT_SECRET' --type SecureString"
fi

# Summary
echo -e "\n${GREEN}=== Setup Complete ===${NC}\n"
echo -e "${GREEN}AWS Account ID:${NC} ${AWS_ACCOUNT_ID}"
echo -e "${GREEN}AWS Region:${NC} ${AWS_REGION}"
echo -e "${GREEN}GitHub Repo:${NC} ${GITHUB_REPO}"
echo -e "${GREEN}IAM Role ARN:${NC} ${ROLE_ARN}"

echo -e "\n${YELLOW}Next steps:${NC}"
echo "1. Add this secret to your GitHub repository:"
echo -e "   ${GREEN}AWS_ROLE_ARN${NC} = ${ROLE_ARN}"
echo ""
echo "2. Update terraform/variables.tf if needed (region, etc.)"
echo ""
echo "3. Commit and push to trigger deployment:"
echo "   git add ."
echo "   git commit -m 'Initial setup'"
echo "   git push origin main"
