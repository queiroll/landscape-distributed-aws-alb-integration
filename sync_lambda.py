import os
import json
import logging
import boto3
import urllib3

# --- Setup & Environment Variables ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)
ec2_client = boto3.client("ec2")
elbv2_client = boto3.client("elbv2")
http = urllib3.PoolManager()

MODEL_UUID = os.environ.get("MODEL_UUID")
APP_NAME = os.environ.get("APP_NAME")
TARGET_GROUP_ARNS = os.environ.get("TARGET_GROUP_ARNS", "").split(',')
INGRESS_SG_ID = os.environ.get("INGRESS_SG_ID")

def attach_ingress_sg(instance_id):
    """Attaches the dedicated ingress security group to an instance if not already present."""
    if not INGRESS_SG_ID: return
    try:
        response = ec2_client.describe_instance_attribute(InstanceId=instance_id, Attribute='groupSet')
        existing_sg_ids = [sg['GroupId'] for sg in response['Groups']]
        if INGRESS_SG_ID not in existing_sg_ids:
            logger.info(f"Attaching Ingress SG {INGRESS_SG_ID} to instance {instance_id}.")
            new_sg_list = existing_sg_ids + [INGRESS_SG_ID]
            ec2_client.modify_instance_attribute(InstanceId=instance_id, Groups=new_sg_list)
    except Exception as e:
        logger.error(f"Failed to attach security group to instance {instance_id}: {e}")
        raise

def detach_ingress_sg(instance_id):
    """Detaches the dedicated ingress security group from an instance."""
    if not INGRESS_SG_ID: return
    try:
        response = ec2_client.describe_instance_attribute(InstanceId=instance_id, Attribute='groupSet')
        existing_sg_ids = [sg['GroupId'] for sg in response['Groups']]
        if INGRESS_SG_ID in existing_sg_ids:
            logger.info(f"Detaching Ingress SG {INGRESS_SG_ID} from instance {instance_id}.")
            new_sg_list = [sg_id for sg_id in existing_sg_ids if sg_id != INGRESS_SG_ID]
            ec2_client.modify_instance_attribute(InstanceId=instance_id, Groups=new_sg_list)
    except Exception as e:
        # During a delete, we should log the error but not necessarily fail the entire process
        logger.error(f"Failed to detach security group from instance {instance_id}: {e}")


def get_instances_by_tags(model_uuid, app_name):
    """Finds running or pending instances by matching the 'juju-units-deployed' tag."""
    paginator = ec2_client.get_paginator('describe_instances')
    pages = paginator.paginate(Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'pending']}, {'Name': 'tag:juju-model-uuid', 'Values': [model_uuid]}])
    instance_ids = []
    app_prefix = f"{app_name}/"
    for page in pages:
        for reservation in page['Reservations']:
            for instance in reservation['Instances']:
                for tag in instance.get('Tags', []):
                    if tag['Key'] == 'juju-units-deployed' and tag['Value'].startswith(app_prefix):
                        instance_ids.append(instance['InstanceId'])
                        break
    return instance_ids

def update_target_groups(instance_ids):
    """SIMPLIFIED: Registers a list of instances with all target groups."""
    logger.info(f"Registering instances {instance_ids} in {len(TARGET_GROUP_ARNS)} target groups.")
    targets = [{"Id": iid} for iid in instance_ids]
    if not targets: return
    for tg_arn in TARGET_GROUP_ARNS:
        if not tg_arn: continue
        try:
            elbv2_client.register_targets(TargetGroupArn=tg_arn, Targets=targets)
        except Exception as e:
            logger.error(f"Failed to update target group {tg_arn}: {e}")

def handle_state_change_event(event):
    """Handles an EC2 'running' state change event."""
    instance_id = event["detail"]["instance-id"]
    state = event["detail"]["state"]
    if state != "running": return
    try:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        if not response.get('Reservations') or not response['Reservations'][0].get('Instances'): return
        instance = response['Reservations'][0]['Instances'][0]
        instance_tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
        if instance_tags.get('juju-model-uuid') != MODEL_UUID: return
        app_prefix = f"{APP_NAME}/"
        if not instance_tags.get('juju-units-deployed', '').startswith(app_prefix): return
        
        logger.info(f"Instance {instance_id} is a match. Proceeding with registration.")
        attach_ingress_sg(instance_id)
        update_target_groups([instance_id])
    except Exception as e:
        logger.error(f"Error handling state change for instance {instance_id}: {e}")

def send_cfn_response(event, context, response_status, response_data={}):
    response_url = event['ResponseURL']
    response_body = {'Status': response_status, 'Reason': 'See logs in CloudWatch', 'PhysicalResourceId': context.log_stream_name, 'StackId': event['StackId'], 'RequestId': event['RequestId'], 'LogicalResourceId': event['LogicalResourceId'], 'Data': response_data}
    json_response_body = json.dumps(response_body)
    headers = {'content-type': '', 'content-length': str(len(json_response_body))}
    try: http.request('PUT', response_url, headers=headers, body=json_response_body)
    except Exception as e: logger.error(f"send_cfn_response failed: {e}")

def lambda_handler(event, context):
    try:
        if event.get("RequestType"): # CloudFormation Custom Resource
            if event["RequestType"] in ["Create", "Update"]:
                instance_ids = get_instances_by_tags(MODEL_UUID, APP_NAME)
                for iid in instance_ids:
                    attach_ingress_sg(iid)
                update_target_groups(instance_ids)
            
            elif event["RequestType"] == "Delete":
                logger.info("Handling CloudFormation Delete event: detaching security group from instances.")
                instance_ids = get_instances_by_tags(MODEL_UUID, APP_NAME)
                for iid in instance_ids:
                    detach_ingress_sg(iid)
            
            send_cfn_response(event, context, "SUCCESS")

        elif event.get("detail-type") == "EC2 Instance State-change Notification": # EventBridge
            handle_state_change_event(event)

    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        if event.get("RequestType"):
            send_cfn_response(event, context, "FAILED")