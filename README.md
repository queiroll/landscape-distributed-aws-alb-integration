# Dynamic AWS Application Load Balancer for Juju

This project automates the deployment and management of an AWS Application Load Balancer (ALB) for an application deployed via Juju on EC2. It uses a tag-based, event-driven approach to automatically discover and register new Juju-managed instances as they are created, providing a seamless integration between the Juju model and native AWS load balancing.

This solution has been designed for a Canonical Landscape deployment but is generic enough to be adapted for any Juju-managed application that exposes HTTP/S services.

---
## Configuration Parameters

The CloudFormation template requires the following parameters at deployment time:

* **`JujuModelUUID` (Required)**
    * The unique UUID of the Juju model you want to target.
    * You can find this by running `juju models` or by looking at the tags of an existing instance.
    * Example: `be486ec1-dc9e-4e73-8d38-65adf280a911`

* **`JujuAppName` (Optional)**
    * The name of the Juju application to target.
    * Default: `landscape-server`

* **`VpcId` (Required)**
    * The ID of the VPC where your Juju model is deployed.
    * Example: `vpc-0123456789abcdef`

* **`PublicSubnetIds` (Required)**
    * A comma-separated list of the public subnet IDs for the ALB.
    * Example: `subnet-0123abc,subnet-5678def`

* **`AcmCertificateArn` (Required)**
    * The Amazon Resource Name (ARN) of an active SSL/TLS certificate in AWS Certificate Manager (ACM).
    * Example: `arn:aws:acm:eu-central-1:12345678:certificate/xxxx-xxxx-xxxx`

---
## Prerequisites

* An existing Juju model deployed on AWS EC2.
* The target application (e.g., `landscape-server`) already deployed within that model.
* An active SSL/TLS certificate for your desired domain in AWS Certificate Manager (ACM).
* AWS CLI installed and configured with appropriate permissions.
* An S3 bucket to store the deployment assets.

---
## Installation

A helper script is provided to simplify deployment. You can run the script on a Client with AWS CLI or in AWS CloudShell in the Account and Region where your Juju resources are running. On the first run, it will prompt you for parameters (like Juju Model UUID, VPC ID, etc.) and save them to a deploy.config file that will be taken as input for subsequent deployments.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/queiroll/lanscape-distributed-aws-alb-integration
    cd lanscape_distributed_aws_alb_integration
    ```

2.  **Run the deployment script:**
    The script will guide you through providing the necessary parameters and deploy the stack.
    ```bash
    ./deploy.sh
    ```
**Note on Configuration:** The first time you run ./deploy.sh, it will interactively prompt you for the required parameters. Your answers will be saved to a new file named deploy.config. On subsequent runs, the script will read this file and use your saved answers as the default values.

## Testing and Final Cutover

After the CloudFormation stack has been successfully deployed, follow these steps to test the integration and complete the migration from haproxy.

1.  **Test the ALB Endpoint:** Find the ALBDNSName in your CloudFormation stack's "Outputs" tab. Point your custom domain's DNS to this address and access your application via https://<your-domain>. Verify that the Landscape application is working correctly.

1.  **Remove the haproxy units:** Once you have confirmed that the ALB is handling traffic correctly, You can remove the haproxy units to free up resources.
    ```bash
    juju remove-unit --force haproxy/<unit_number>
    ```

---
## Cleanup

To remove all the resources created by this solution (the ALB, Lambda function, security groups, etc.), run the cleanup script.
```bash
./cleanup.sh
```

**Note:** The cleanup.sh script reads the stack name from the deploy.config file to ensure it targets the correct CloudFormation stack for deletion. If the file is missing, it will prompt you for the stack name.