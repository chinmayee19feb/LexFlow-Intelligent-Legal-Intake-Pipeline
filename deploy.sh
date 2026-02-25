#!/bin/bash
# LexFlow Deploy Script
# Run this after `aws cloudformation deploy` to package and upload Lambda code.
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - pip installed
#   - jq installed (brew install jq / apt install jq)
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh

set -e  # Exit on any error

REGION="us-east-1"
STACK_NAME="lexflow"

echo ""
echo "════════════════════════════════════════════════════════"
echo "  LexFlow Deploy"
echo "════════════════════════════════════════════════════════"
echo ""

# ── STEP 1: Store API key in SSM (only needed once) ──────────────────────
if ! aws ssm get-parameter --name /lexflow/anthropic-api-key --region $REGION &>/dev/null; then
  echo "▶ SSM parameter /lexflow/anthropic-api-key not found."
  read -p "  Enter your Anthropic API key: " ANTHROPIC_KEY
  aws ssm put-parameter \
    --name /lexflow/anthropic-api-key \
    --value "$ANTHROPIC_KEY" \
    --type SecureString \
    --region $REGION
  echo "  ✓ API key stored in SSM"
else
  echo "✓ SSM parameter already exists — skipping"
fi

echo ""

# ── STEP 2: Deploy CloudFormation stack ──────────────────────────────────
echo "▶ Deploying CloudFormation stack..."
read -p "  Attorney alert email address: " ATTORNEY_EMAIL
read -p "  From (SES-verified sender) email address: " FROM_EMAIL

aws cloudformation deploy \
  --template-file cloudformation.yaml \
  --stack-name $STACK_NAME \
  --capabilities CAPABILITY_NAMED_IAM \
  --region $REGION \
  --parameter-overrides \
    AttorneyEmail="$ATTORNEY_EMAIL" \
    FromEmail="$FROM_EMAIL"

echo "  ✓ CloudFormation stack deployed"
echo ""

# ── STEP 3: Package intake Lambda ────────────────────────────────────────
echo "▶ Packaging lexflow-intake Lambda..."

cd lexflow-intake
pip install -r requirements.txt -t ./package --quiet
cp handler.py ai_classifier.py prompt.py emailer.py db.py ./package/
cd package
zip -r ../../intake-lambda.zip . --quiet
cd ../..
rm -rf lexflow-intake/package

echo "  ✓ intake-lambda.zip created ($(du -sh intake-lambda.zip | cut -f1))"

# ── STEP 4: Package dashboard Lambda ─────────────────────────────────────
echo "▶ Packaging lexflow-dashboard Lambda..."

cd lexflow-dashboard
mkdir -p package
cp handler.py db.py ./package/
cd package
zip -r ../../dashboard-lambda.zip . --quiet
cd ../..
rm -rf lexflow-dashboard/package

echo "  ✓ dashboard-lambda.zip created"

# ── STEP 5: Upload Lambda code ───────────────────────────────────────────
echo "▶ Uploading Lambda code..."

aws lambda update-function-code \
  --function-name lexflow-intake \
  --zip-file fileb://intake-lambda.zip \
  --region $REGION \
  --output text --query 'CodeSize' | xargs -I{} echo "  ✓ lexflow-intake uploaded ({} bytes)"

aws lambda update-function-code \
  --function-name lexflow-dashboard \
  --zip-file fileb://dashboard-lambda.zip \
  --region $REGION \
  --output text --query 'CodeSize' | xargs -I{} echo "  ✓ lexflow-dashboard uploaded ({} bytes)"

# ── STEP 6: Get outputs ──────────────────────────────────────────────────
echo ""
echo "▶ Fetching stack outputs..."

API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text)

INTAKE_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query "Stacks[0].Outputs[?OutputKey=='IntakeFormUrl'].OutputValue" \
  --output text)

DASHBOARD_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query "Stacks[0].Outputs[?OutputKey=='DashboardUrl'].OutputValue" \
  --output text)

# Write API endpoint to a local file so frontend build can reference it
echo "$API_ENDPOINT" > .api-endpoint

echo ""
echo "════════════════════════════════════════════════════════"
echo "  ✅ Deploy complete!"
echo "════════════════════════════════════════════════════════"
echo ""
echo "  API Endpoint : $API_ENDPOINT"
echo "  Intake Form  : $INTAKE_URL"
echo "  Dashboard    : $DASHBOARD_URL"
echo ""
echo "  Next steps:"
echo "  1. Verify your SES email identities if not already done:"
echo "     aws ses verify-email-identity --email-address $ATTORNEY_EMAIL --region $REGION"
echo "     aws ses verify-email-identity --email-address $FROM_EMAIL --region $REGION"
echo ""
echo "  2. Build and upload frontends:"
echo "     ./deploy-frontend.sh $API_ENDPOINT"
echo ""
echo "  3. Test the pipeline:"
echo "     curl -X POST $API_ENDPOINT/intake \\"
echo "       -H 'Content-Type: application/json' \\"
echo "       -d '{\"client_name\":\"Test User\",\"client_email\":\"$ATTORNEY_EMAIL\",\"client_phone\":\"+1234567890\",\"incident_date\":\"2025-01-15\",\"prior_attorney\":false,\"description\":\"I was hit by a car at a pedestrian crossing. The driver ran a red light. I have a broken wrist and police report.\"}'"
echo ""
