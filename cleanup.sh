#!/bin/bash
set -e

CONFIG_FILE="deploy.config"

if [ ! -f "$CONFIG_FILE" ]; then
    read -p "Config file not found. Please enter the name of the stack to delete: " STACK_NAME
else
    source "$CONFIG_FILE"
fi

if [ -z "$STACK_NAME" ]; then
    echo "Stack name is empty. Aborting."
    exit 1
fi

read -p "Are you sure you want to delete the stack '$STACK_NAME'? (y/N): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Cleanup aborted."
    exit 0
fi

echo "--- Deleting CloudFormation Stack '$STACK_NAME'... ---"
aws cloudformation delete-stack --stack-name "$STACK_NAME"

echo "Deletion initiated. Check the AWS CloudFormation console for progress."