#!/bin/bash
set -e

CONFIG_FILE="deploy.config"
STACK_NAME="juju-landscape-alb-stack"
TEMPLATE_FILE="template.yaml"
PACKAGED_TEMPLATE="packaged-template.yaml"

# Load existing config if it exists
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# Guided prompts for required parameters
echo "--- Juju ALB Automation Deployment ---"
read -p "Enter Stack Name [$STACK_NAME]: " input_stack_name
STACK_NAME=${input_stack_name:-$STACK_NAME}

read -p "Enter Juju Model UUID [$JUJU_MODEL_UUID]: " input_juju_model_uuid
JUJU_MODEL_UUID=${input_juju_model_uuid:-$JUJU_MODEL_UUID}

JUJU_APP_NAME=${JUJU_APP_NAME:-landscape-server}
read -p "Enter Target Juju App Name [$JUJU_APP_NAME]: " input_juju_app_name
JUJU_APP_NAME=${input_juju_app_name:-$JUJU_APP_NAME}

read -p "Enter VPC ID where Juju resources are running [$VPC_ID]: " input_vpc_id
VPC_ID=${input_vpc_id:-$VPC_ID}

read -p "Enter Public Subnet IDs (comma-separated) to deploy the Load Balancer. Consider using one Subnet for each AZ in the Region [$PUBLIC_SUBNETS]: " input_public_subnets
PUBLIC_SUBNETS=${input_public_subnets:-$PUBLIC_SUBNETS}

read -p "Enter ACM Certificate ARN [$ACM_CERT_ARN]: " input_acm_cert_arn
ACM_CERT_ARN=${input_acm_cert_arn:-$ACM_CERT_ARN}

read -p "Enter S3 Bucket name for deployment assets [$S3_BUCKET]: " input_s3_bucket
S3_BUCKET=${input_s3_bucket:-$S3_BUCKET}

# Save config for future runs
echo "Saving configuration to $CONFIG_FILE..."
cat > $CONFIG_FILE << EOL
STACK_NAME="$STACK_NAME"
JUJU_MODEL_UUID="$JUJU_MODEL_UUID"
JUJU_APP_NAME="$JUJU_APP_NAME"
VPC_ID="$VPC_ID"
PUBLIC_SUBNETS="$PUBLIC_SUBNETS"
ACM_CERT_ARN="$ACM_CERT_ARN"
S3_BUCKET="$S3_BUCKET"
EOL

echo ""
echo "--- Packaging local code and uploading to S3... ---"
aws cloudformation package \
  --template-file "$TEMPLATE_FILE" \
  --s3-bucket "$S3_BUCKET" \
  --output-template-file "$PACKAGED_TEMPLATE"

echo ""
echo "--- Deploying CloudFormation Stack... ---"
aws cloudformation deploy \
  --template-file "$PACKAGED_TEMPLATE" \
  --stack-name "$STACK_NAME" \
  --parameter-overrides \
    JujuModelUUID="$JUJU_MODEL_UUID" \
    JujuAppName="$JUJU_APP_NAME" \
    VpcId="$VPC_ID" \
    PublicSubnetIds="$PUBLIC_SUBNETS" \
    AcmCertificateArn="$ACM_CERT_ARN" \
  --capabilities CAPABILITY_IAM

echo ""
echo "Deployment initiated. Check the AWS CloudFormation console for progress."