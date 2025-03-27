# AWS Monitoring Auto-Tagger

This script automatically discovers AWS resources (EC2, ECS, EKS, Lambda) and applies a designated tag (by default, `needs_monitored=true`) to each resource. It also writes logs and an inventory of discovered resources to local directories or uploads them to S3, depending on your configuration.

## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
  - [Local Execution](#local-execution)
  - [SSM/Run Command Execution](#ssmrun-command-execution)
  - [Lambda Execution](#lambda-execution)
- [Configuration](#configuration)
- [Logging and Inventory](#logging-and-inventory)
- [FAQ / Troubleshooting](#faq--troubleshooting)
- [License](#license)

## Features

### Automated Resource Discovery
- Discovers EC2 instances, ECS clusters/services, EKS clusters, and Lambda functions in the specified AWS region.

### Tag Application
- Applies a configurable key/value tag (default: `needs_monitored=true`) to each discovered resource that does not already have the tag.

### Partial Failure Handling
- Logs any individual resource tagging failures but continues processing remaining resources.

### Local or Cloud Execution
- **Local**: Run via Python on your workstation or a server using a specified AWS Profile.
- **SSM**: Store this script in S3, download, and execute it on a target EC2 instance via AWS SSM Run Command.
- **Lambda**: The function `lambda_handler` can be invoked as a regular AWS Lambda function.

### Logging and Inventory
- Writes logs and an inventory JSON to local files by default and optionally uploads these to S3.

## Prerequisites

- **Python 3.7+**
  - The script uses Python 3 features (e.g., f-strings, type hints).

- **AWS Credentials**
  - You need appropriate AWS credentials (access key, secret key, session token if required) with permissions to:
    - Describe and Tag EC2 resources
    - Describe and Tag ECS resources
    - Describe and Tag EKS resources
    - Describe and Tag Lambda functions
    - Read/Write to Amazon S3 (if uploading logs)

- **AWS CLI or Boto3**
  - If running locally or via SSM, ensure boto3 is installed.
  - AWS CLI is optional but recommended to confirm credentials and interact with S3.

## Installation

### Clone or Download Script
```bash
git clone https://github.com/your-org/your-repo.git
cd your-repo
# or simply place auto_tagger.py in your working directory
```

### Install Dependencies
(If you do not already have boto3 installed, or want to manage dependencies in a virtualenv.)
```bash
pip install boto3
```

### Set Up AWS Credentials
- Ensure you have an AWS profile configured in `~/.aws/credentials` OR environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, etc.)
- If you're running in AWS Lambda or using an IAM role on an EC2 instance, make sure the IAM role has the proper permissions.

## Usage

### Local Execution

#### Run Using the Default Configuration
```bash
python auto_tagger.py
```

By default, the script will look for credentials in your environment or default AWS profile, and it will run against region `na-east-1`, tagging resources with `needs_monitored=true`.

#### Specify Custom Arguments
```bash
python auto_tagger.py \
  --profile yourAwsProfile \
  --region us-east-1 \
  --tag-key "needs_monitored" \
  --tag-value "false" \
  --s3-bucket "my-logs-bucket" \
  --s3-prefix "my/logs/prefix" \
  --debug
```

Here's what each argument means:
- `--profile`: The AWS CLI profile to use for credentials
- `--region`: The AWS region to search for resources (default: `na-east-1`)
- `--tag-key`: The tag key to apply (default: `needs_monitored`)
- `--tag-value`: The tag value to apply (default: `true`)
- `--s3-bucket`: S3 bucket where logs and inventory files are uploaded
- `--s3-prefix`: A prefix (folder path) in the bucket for these files
- `--debug`: Enables verbose debug logging

### SSM/Run Command Execution

#### Upload Script to S3
```bash
aws s3 cp auto_tagger.py s3://YOUR_BUCKET_NAME/scripts/auto_tagger.py
```

#### Send Command
```bash
aws ssm send-command \
    --document-name "AWS-RunShellScript" \
    --instance-ids "i-0abcdef1234567890" \
    --parameters commands="
      aws s3 cp s3://YOUR_BUCKET_NAME/scripts/auto_tagger.py .
      python auto_tagger.py --region na-east-1 --tag-key needs_monitored --tag-value true --s3-bucket MY_LOG_BUCKET --s3-prefix auto_tagger_output
    " \
    --comment "Run auto-tagging script" \
    --output-s3-bucket-name "YOUR_SSM_LOG_BUCKET" \
    --query "Command.CommandId"
```

#### Monitor
- Check AWS Systems Manager Run Command output to see the script's console output.
- The script will produce local logs on the instance (in `logs/`) and optionally upload them to the specified S3 path.

### Lambda Execution

#### Create a New Lambda Function
- In AWS Console, create a Python 3.x Lambda function.
- Configure an IAM role for the function with `Describe*`, `Tag*` permissions on EC2/ECS/EKS/Lambda, plus `s3:PutObject` if needed for logs.

#### Upload the Script
- Zip the `auto_tagger.py` file (and any required libraries, if not using a Lambda layer).
- Upload via console or CLI.

#### Set Environment Variables
Go to the Configuration tab and set the following keys if needed:
- `REGION`: e.g., `na-east-1`
- `TAG_KEY`: e.g., `needs_monitored`
- `TAG_VALUE`: e.g., `true`
- `S3_BUCKET`: e.g., `my-logs-bucket`
- `S3_PREFIX`: e.g., `auto_tagger_output`

#### Test the Lambda
- Invoke the Lambda manually or via an event.
- Check the CloudWatch Logs to see results and any errors.

## Configuration

You can configure the script by environment variables or command-line arguments:

### Environment Variables
- `REGION` (default: `na-east-1`)
- `TAG_KEY` (default: `needs_monitored`)
- `TAG_VALUE` (default: `true`)
- `S3_BUCKET` (default: `smxtech-tool-files`)
- `S3_PREFIX` (default: `auto_tagger/montagged`)
- `LOCAL_LOG_DIR` (default: `logs`)
- `LOCAL_INVENTORY_DIR` (default: `inventory`)
- `AWS_PROFILE` (default: none)

### Command-Line Arguments
Specified with the same names (e.g., `--region` overrides `REGION`, etc.). Command-line arguments take precedence over environment variables.

## Logging and Inventory

### Local Files
- By default, the script writes JSON logs to `<LOCAL_LOG_DIR>/monitoring_logs_TIMESTAMP.json`.
- It writes an inventory of discovered resources to `<LOCAL_INVENTORY_DIR>/monitoring_inventory_TIMESTAMP.json`.
- `TIMESTAMP` is a UTC datetime in the format `YYYYmmdd-HHMMSS`.

### S3 Upload
- If `S3_BUCKET` is set, the script attempts to upload both logs and inventory to:
  - `s3://<S3_BUCKET>/<S3_PREFIX>/logs/monitoring_logs_TIMESTAMP.json`
  - `s3://<S3_BUCKET>/<S3_PREFIX>/inventory/monitoring_inventory_TIMESTAMP.json`
- If the bucket is inaccessible or the upload fails, errors are logged, but the script continues.

## FAQ / Troubleshooting

### Permission Errors
- Make sure your IAM role or AWS profile has permission to `DescribeInstances`, `CreateTags`, `ListClusters`, `ListTagsForResource`, `TagResource`, etc.

### No Resources Tagged
- Verify you have resources in the selected region that do not already have the specified tag.
- Check logs for detailed error messages.

### S3 Upload Fails
- Confirm the `S3_BUCKET` value is correct and your role/profile can upload to that bucket.
- Check that the region of the S3 bucket matches or is accessible from your selected AWS region (S3 is global, but VPC endpoints or governance could matter).

### Local Credential/Permission Issues
- Run `aws sts get-caller-identity --profile yourProfile` to confirm your local credentials are set up correctly.