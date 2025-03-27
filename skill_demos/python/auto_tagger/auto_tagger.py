import os
import json
import boto3
import logging
import traceback
from datetime import datetime, timezone
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound

# ---------------------------------------------------------------------
# Configure Logging
# ---------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("monitoring-tagger")

# ---------------------------------------------------------------------
# Environment / Config
# ---------------------------------------------------------------------
REGION = os.getenv("REGION", "na-east-1")  # Default changed to na-east-1
TAG_KEY = os.getenv("TAG_KEY", "needs_monitored")
TAG_VALUE = os.getenv("TAG_VALUE", "true")

# Main bucket/prefix for S3 upload
S3_BUCKET = os.getenv("S3_BUCKET", "tool-files")
S3_PREFIX = os.getenv("S3_PREFIX", "auto_tagger/montagged")
S3_LOGS_PREFIX = f"{S3_PREFIX}/logs"
S3_INVENTORY_PREFIX = f"{S3_PREFIX}/inventory"

# Local directories for logs & inventory
LOCAL_LOG_DIR = os.getenv("LOCAL_LOG_DIR", "logs")
LOCAL_INVENTORY_DIR = os.getenv("LOCAL_INVENTORY_DIR", "inventory")

# AWS Profile - allows local execution with different profiles
AWS_PROFILE = os.getenv("AWS_PROFILE", None)

# Check if running in Lambda
IS_LAMBDA = 'AWS_LAMBDA_FUNCTION_NAME' in os.environ


def create_boto3_client(service_name):
    """Create boto3 client with appropriate configuration based on environment."""
    try:
        # If a profile is specified and we're not in Lambda, use it
        if AWS_PROFILE and not IS_LAMBDA:
            session = boto3.Session(profile_name=AWS_PROFILE, region_name=REGION)
            client = session.client(service_name, region_name=REGION)
        else:
            # Default client creation with region
            client = boto3.client(service_name, region_name=REGION)

        # Log the client configuration for debugging
        logger.info(f"Created {service_name} client for region {REGION}")
        
        return client
    except (NoCredentialsError, ProfileNotFound) as e:
        logger.error(f"AWS credentials error: {str(e)}")
        raise


def lambda_handler(event, context):
    """
    Entry point for Lambda or local execution.
    
    Args:
        event (dict): Event data (may contain configuration overrides)
        context: Lambda context object (will be None for local execution)
    
    Returns:
        dict: Summary of tagging results
    """
    logger.info("Starting monitoring tagging script")
    
    # Process event for possible overrides
    if event and isinstance(event, dict):
        config_overrides = event.get('config', {})
        for key, value in config_overrides.items():
            if key.upper() in globals():
                globals()[key.upper()] = value
                logger.info(f"Overriding {key.upper()} with value from event: {value}")
    
    # Prepare local directories
    try:
        os.makedirs(LOCAL_LOG_DIR, exist_ok=True)
        os.makedirs(LOCAL_INVENTORY_DIR, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create local directories: {str(e)}")
        # Continue anyway, we'll handle file operations carefully

    # Initialize results
    result = {
        "statusCode": 500,  # Assume failure until successful completion
        "tagged_new": 0,
        "already_tagged": 0,
        "failed": 0,
        "errors": []
    }

    # Initialize AWS clients
    try:
        logger.info(f"Initializing AWS clients for region: {REGION}")
        ec2_client = create_boto3_client("ec2")
        ecs_client = create_boto3_client("ecs")
        eks_client = create_boto3_client("eks")
        lambda_client = create_boto3_client("lambda")
        s3_client = create_boto3_client("s3")
        
        # Print account info for debugging (optional)
        try:
            sts_client = create_boto3_client("sts")
            account_id = sts_client.get_caller_identity().get('Account')
            logger.info(f"Connected to AWS Account: {account_id}")
        except Exception as e:
            logger.warning(f"Could not determine AWS account ID: {e}")
            
    except Exception as e:
        logger.error(f"Failed to initialize AWS clients: {str(e)}")
        result["errors"].append(f"AWS client initialization error: {str(e)}")
        return result
    
    # Data structures for logs and inventory
    discovered_resources = {}
    log_entries = []

    # Helper function: adds resource to discovered_resources if not present
    def ensure_resource_record(resource_id, resource_type, resource_name=None):
        if resource_id not in discovered_resources:
            discovered_resources[resource_id] = {
                "resource_name": resource_name or "",
                "resource_type": resource_type,
                "status": None,
                "error_message": None
            }
        else:
            # If we have a name, update if empty
            if resource_name and not discovered_resources[resource_id].get("resource_name"):
                discovered_resources[resource_id]["resource_name"] = resource_name

    def add_log_entry(resource_type, resource_id, status, message):
        entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "resource_type": resource_type,
            "resource_id": resource_id,
            "status": status,  # "success", "failure", or "info"
            "message": message
        }
        log_entries.append(entry)
        
        # Also log to the logger
        if status == "info":
            logger.info(f"{resource_type} - {resource_id}: {message}")
        elif status == "success":
            logger.info(f"{resource_type} - {resource_id}: {message}")
        elif status == "failure":
            logger.error(f"{resource_type} - {resource_id}: {message}")

    # For each resource, we do partial tagging: if one fails, we log and continue
    def safe_ec2_tag_single(resource_id, key, value, resource_type):
        """Tag a single EC2 resource by ID, capturing partial failures."""
        try:
            ec2_client.create_tags(
                Resources=[resource_id],
                Tags=[{"Key": key, "Value": value}]
            )
            discovered_resources[resource_id]["status"] = "tagged"
            add_log_entry(resource_type, resource_id, "success", f"Tagged with {key}={value}")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            discovered_resources[resource_id]["status"] = "failed"
            discovered_resources[resource_id]["error_message"] = f"{error_code}: {error_message}"
            add_log_entry(resource_type, resource_id, "failure", f"Tagging failed: {error_code}: {error_message}")
            return False
        except Exception as e:
            discovered_resources[resource_id]["status"] = "failed"
            discovered_resources[resource_id]["error_message"] = str(e)
            add_log_entry(resource_type, resource_id, "failure", f"Tagging failed with unexpected error: {str(e)}")
            return False

    # ------------------- Tagging Functions -------------------

    # ------------------- EC2 Instances -------------------
    def tag_ec2_instances():
        add_log_entry("EC2", "ALL", "info", "Discovering EC2 Instances...")
        try:
            paginator = ec2_client.get_paginator('describe_instances')
            instance_count = 0
            
            for page in paginator.paginate():
                for reservation in page.get('Reservations', []):
                    for instance in reservation.get('Instances', []):
                        instance_count += 1
                        instance_id = instance["InstanceId"]
                        tags = instance.get("Tags", [])
                        name_tag = get_tag_value(tags, "Name")
                        ensure_resource_record(instance_id, "EC2", name_tag)

                        current_val = get_tag_value(tags, TAG_KEY)
                        if current_val == TAG_VALUE:
                            discovered_resources[instance_id]["status"] = "already_tagged"
                            add_log_entry("EC2", instance_id, "info", f"Already tagged with {TAG_KEY}={TAG_VALUE}")
                        else:
                            # Tag individually so partial failures don't break everything
                            safe_ec2_tag_single(instance_id, TAG_KEY, TAG_VALUE, "EC2")
            
            add_log_entry("EC2", "ALL", "info", f"Processed {instance_count} EC2 instances")
        except Exception as e:
            add_log_entry("EC2", "ALL", "failure", f"Error discovering EC2 instances: {str(e)}")
            logger.error(f"Error discovering EC2 instances: {str(e)}")
            logger.error(traceback.format_exc())

    # ------------------- ECS Clusters and Services -------------------
    def tag_ecs_clusters_and_services():
        add_log_entry("ECS", "ALL", "info", "Discovering ECS Clusters & Services...")

        try:
            # 1) Clusters
            clusters_resp = ecs_client.list_clusters()
            cluster_arns = clusters_resp.get("clusterArns", [])
            add_log_entry("ECS", "ALL", "info", f"Found {len(cluster_arns)} ECS clusters")
            
            for cluster_arn in cluster_arns:
                # Add to inventory up front
                ensure_resource_record(cluster_arn, "ECS_CLUSTER")

                try:
                    tags_resp = ecs_client.list_tags_for_resource(resourceArn=cluster_arn)
                    existing_tags = tags_resp.get("tags", [])  # list of {"key":..., "value":...}
                    # Check existing
                    found = False
                    for t in existing_tags:
                        if t["key"] == TAG_KEY:
                            found = True
                            if t["value"] == TAG_VALUE:
                                discovered_resources[cluster_arn]["status"] = "already_tagged"
                                add_log_entry("ECS_CLUSTER", cluster_arn, "info", f"Already tagged with {TAG_KEY}={TAG_VALUE}")
                            else:
                                # We need to update
                                t["value"] = TAG_VALUE
                    if not found:
                        existing_tags.append({"key": TAG_KEY, "value": TAG_VALUE})

                    # If not found or we updated the value
                    if discovered_resources[cluster_arn]["status"] is None:
                        # Attempt to retag
                        try:
                            ecs_client.tag_resource(resourceArn=cluster_arn, tags=existing_tags)
                            discovered_resources[cluster_arn]["status"] = "tagged"
                            add_log_entry("ECS_CLUSTER", cluster_arn, "success", f"Tagged ECS cluster with {TAG_KEY}={TAG_VALUE}")
                        except ClientError as e:
                            error_code = e.response['Error']['Code']
                            error_message = e.response['Error']['Message']
                            discovered_resources[cluster_arn]["status"] = "failed"
                            discovered_resources[cluster_arn]["error_message"] = f"{error_code}: {error_message}"
                            add_log_entry("ECS_CLUSTER", cluster_arn, "failure", f"Tagging ECS cluster failed: {error_code}: {error_message}")
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    error_message = e.response['Error']['Message']
                    discovered_resources[cluster_arn]["status"] = "failed"
                    discovered_resources[cluster_arn]["error_message"] = f"{error_code}: {error_message}"
                    add_log_entry("ECS_CLUSTER", cluster_arn, "failure", f"Could not read ECS cluster tags: {error_code}: {error_message}")
                except Exception as e:
                    discovered_resources[cluster_arn]["status"] = "failed"
                    discovered_resources[cluster_arn]["error_message"] = str(e)
                    add_log_entry("ECS_CLUSTER", cluster_arn, "failure", f"Unexpected error with ECS cluster: {str(e)}")

            # 2) Services for each cluster
            service_count = 0
            for cluster_arn in cluster_arns:
                try:
                    paginator = ecs_client.get_paginator('list_services')
                    for page in paginator.paginate(cluster=cluster_arn):
                        service_arns = page.get('serviceArns', [])
                        service_count += len(service_arns)
                        
                        for svc_arn in service_arns:
                            ensure_resource_record(svc_arn, "ECS_SERVICE")
                            try:
                                tags_resp = ecs_client.list_tags_for_resource(resourceArn=svc_arn)
                                existing_tags = tags_resp.get("tags", [])
                                found = False
                                correct_already = False
                                for t in existing_tags:
                                    if t["key"] == TAG_KEY:
                                        found = True
                                        if t["value"] == TAG_VALUE:
                                            correct_already = True
                                        else:
                                            t["value"] = TAG_VALUE
                                if correct_already:
                                    discovered_resources[svc_arn]["status"] = "already_tagged"
                                    add_log_entry("ECS_SERVICE", svc_arn, "info", f"Already tagged with {TAG_KEY}={TAG_VALUE}")
                                else:
                                    if not found:
                                        existing_tags.append({"key": TAG_KEY, "value": TAG_VALUE})
                                    # Attempt tagging
                                    try:
                                        ecs_client.tag_resource(resourceArn=svc_arn, tags=existing_tags)
                                        discovered_resources[svc_arn]["status"] = "tagged"
                                        add_log_entry("ECS_SERVICE", svc_arn, "success", f"Tagged ECS service with {TAG_KEY}={TAG_VALUE}")
                                    except ClientError as e:
                                        error_code = e.response['Error']['Code']
                                        error_message = e.response['Error']['Message']
                                        discovered_resources[svc_arn]["status"] = "failed"
                                        discovered_resources[svc_arn]["error_message"] = f"{error_code}: {error_message}"
                                        add_log_entry("ECS_SERVICE", svc_arn, "failure", f"Tagging ECS service failed: {error_code}: {error_message}")
                            except Exception as e:
                                discovered_resources[svc_arn]["status"] = "failed"
                                discovered_resources[svc_arn]["error_message"] = str(e)
                                add_log_entry("ECS_SERVICE", svc_arn, "failure", f"Could not read ECS service tags: {str(e)}")
                except Exception as e:
                    add_log_entry("ECS", cluster_arn, "failure", f"Error listing services for cluster: {str(e)}")
            
            add_log_entry("ECS", "ALL", "info", f"Processed {service_count} ECS services across {len(cluster_arns)} clusters")
        
        except Exception as e:
            add_log_entry("ECS", "ALL", "failure", f"Error discovering ECS resources: {str(e)}")
            logger.error(f"Error discovering ECS resources: {str(e)}")
            logger.error(traceback.format_exc())

    # ------------------- EKS Clusters -------------------
    def tag_eks_clusters():
        add_log_entry("EKS", "ALL", "info", "Discovering EKS Clusters...")
        try:
            cluster_list = eks_client.list_clusters().get("clusters", [])
            add_log_entry("EKS", "ALL", "info", f"Found {len(cluster_list)} EKS clusters")
            
            for cluster_name in cluster_list:
                # We'll store by the cluster ARN
                try:
                    desc = eks_client.describe_cluster(name=cluster_name)
                    cluster_arn = desc["cluster"]["arn"]
                    ensure_resource_record(cluster_arn, "EKS_CLUSTER", cluster_name)

                    # Get current tags
                    current_tags = eks_client.list_tags_for_resource(resourceArn=cluster_arn).get("tags", {})
                    if current_tags.get(TAG_KEY) == TAG_VALUE:
                        discovered_resources[cluster_arn]["status"] = "already_tagged"
                        add_log_entry("EKS_CLUSTER", cluster_arn, "info", f"Already tagged with {TAG_KEY}={TAG_VALUE}")
                    else:
                        # Update
                        current_tags[TAG_KEY] = TAG_VALUE
                        try:
                            eks_client.tag_resource(resourceArn=cluster_arn, tags=current_tags)
                            discovered_resources[cluster_arn]["status"] = "tagged"
                            add_log_entry("EKS_CLUSTER", cluster_arn, "success", f"Tagged EKS cluster {cluster_name}")
                        except ClientError as e:
                            error_code = e.response['Error']['Code']
                            error_message = e.response['Error']['Message']
                            discovered_resources[cluster_arn]["status"] = "failed"
                            discovered_resources[cluster_arn]["error_message"] = f"{error_code}: {error_message}"
                            add_log_entry("EKS_CLUSTER", cluster_arn, "failure", f"Tagging EKS cluster failed: {error_code}: {error_message}")
                except ClientError as e:
                    # If we can't even describe, log it
                    error_code = e.response['Error']['Code']
                    error_message = e.response['Error']['Message']
                    add_log_entry("EKS_CLUSTER", cluster_name, "failure", f"Describe EKS cluster failed: {error_code}: {error_message}")
                except Exception as e:
                    add_log_entry("EKS_CLUSTER", cluster_name, "failure", f"Unexpected error with EKS cluster: {str(e)}")
        except Exception as e:
            add_log_entry("EKS", "ALL", "failure", f"Error discovering EKS clusters: {str(e)}")
            logger.error(f"Error discovering EKS clusters: {str(e)}")
            logger.error(traceback.format_exc())

    # ------------------- Lambda Functions -------------------
    def tag_lambda_functions():
        add_log_entry("Lambda", "ALL", "info", "Discovering Lambda Functions...")
        try:
            paginator = lambda_client.get_paginator('list_functions')
            function_count = 0
            
            for page in paginator.paginate():
                functions = page.get('Functions', [])
                function_count += len(functions)
                
                for function in functions:
                    function_name = function['FunctionName']
                    function_arn = function['FunctionArn']
                    
                    ensure_resource_record(function_arn, "LAMBDA", function_name)
                    
                    try:
                        # Get existing tags
                        tags_response = lambda_client.list_tags(Resource=function_arn)
                        existing_tags = tags_response.get('Tags', {})
                        
                        if existing_tags.get(TAG_KEY) == TAG_VALUE:
                            discovered_resources[function_arn]["status"] = "already_tagged"
                            add_log_entry("LAMBDA", function_arn, "info", f"Lambda function already tagged with {TAG_KEY}={TAG_VALUE}")
                        else:
                            # Add our tag
                            existing_tags[TAG_KEY] = TAG_VALUE
                            
                            try:
                                lambda_client.tag_resource(
                                    Resource=function_arn,
                                    Tags=existing_tags
                                )
                                discovered_resources[function_arn]["status"] = "tagged"
                                add_log_entry("LAMBDA", function_arn, "success", f"Tagged Lambda function with {TAG_KEY}={TAG_VALUE}")
                            except ClientError as e:
                                error_code = e.response['Error']['Code']
                                error_message = e.response['Error']['Message']
                                discovered_resources[function_arn]["status"] = "failed"
                                discovered_resources[function_arn]["error_message"] = f"{error_code}: {error_message}"
                                add_log_entry("LAMBDA", function_arn, "failure", f"Tagging Lambda function failed: {error_code}: {error_message}")
                                
                    except Exception as e:
                        discovered_resources[function_arn]["status"] = "failed"
                        discovered_resources[function_arn]["error_message"] = str(e)
                        add_log_entry("LAMBDA", function_arn, "failure", f"Could not read Lambda function tags: {str(e)}")
            
            add_log_entry("LAMBDA", "ALL", "info", f"Processed {function_count} Lambda functions")
            
        except Exception as e:
            add_log_entry("LAMBDA", "ALL", "failure", f"Error discovering Lambda functions: {str(e)}")
            logger.error(f"Error discovering Lambda functions: {str(e)}")
            logger.error(traceback.format_exc())

    # ---------------------------------------------------------------
    # UTILITY FUNCTIONS
    # ---------------------------------------------------------------
    def get_tag_value(tags, key):
        if not tags:
            return None
        for t in tags:
            if t.get("Key") == key or t.get("key") == key:
                return t.get("Value") or t.get("value")
        return None

    # ---------------------------------------------------------------
    # ACTUAL WORK: DISCOVER & TAG
    # ---------------------------------------------------------------
    try:
        # Tag each resource type, catching any unexpected errors to continue
        try:
            tag_ec2_instances()
        except Exception as e:
            logger.error(f"Unexpected error in EC2 tagging: {str(e)}")
            result["errors"].append(f"EC2 tagging error: {str(e)}")
            
        try:
            tag_ecs_clusters_and_services()
        except Exception as e:
            logger.error(f"Unexpected error in ECS tagging: {str(e)}")
            result["errors"].append(f"ECS tagging error: {str(e)}")
            
        try:
            tag_eks_clusters()
        except Exception as e:
            logger.error(f"Unexpected error in EKS tagging: {str(e)}")
            result["errors"].append(f"EKS tagging error: {str(e)}")
            
        try:
            tag_lambda_functions()
        except Exception as e:
            logger.error(f"Unexpected error in Lambda tagging: {str(e)}")
            result["errors"].append(f"Lambda tagging error: {str(e)}")

        # ---------------------------------------------------------------
        # Write logs & inventory to local disk
        # Then upload to S3
        # ---------------------------------------------------------------
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

        # 1) Logs file
        logs_filename = os.path.join(LOCAL_LOG_DIR, f"monitoring_logs_{timestamp_str}.json")
        inventory_filename = os.path.join(LOCAL_INVENTORY_DIR, f"monitoring_inventory_{timestamp_str}.json")
        
        # Write files locally
        try:
            with open(logs_filename, "w") as f:
                json.dump(log_entries, f, indent=2)
            logger.info(f"Wrote logs to {logs_filename}")
        except Exception as e:
            logger.error(f"Failed to write logs file: {str(e)}")
            result["errors"].append(f"Failed to write logs file: {str(e)}")

        try:
            with open(inventory_filename, "w") as f:
                json.dump(discovered_resources, f, indent=2)
            logger.info(f"Wrote inventory to {inventory_filename}")
        except Exception as e:
            logger.error(f"Failed to write inventory file: {str(e)}")
            result["errors"].append(f"Failed to write inventory file: {str(e)}")

        # Upload to S3 if a bucket is specified
        if S3_BUCKET:
            logger.info(f"Attempting to upload files to S3 bucket: {S3_BUCKET}")
            
            # We'll make S3 upload optional - if it fails, we'll log the error but not fail the script
            try:
                # Check if bucket is accessible (optional)
                s3_client.head_bucket(Bucket=S3_BUCKET)
                logger.info(f"S3 bucket {S3_BUCKET} exists and is accessible")
            except Exception as e:
                logger.warning(f"Could not verify S3 bucket {S3_BUCKET}: {str(e)}")
                # Continue to try uploading anyway

            # Attempt logs upload
            try:
                s3_client.upload_file(
                    logs_filename,
                    S3_BUCKET,
                    f"{S3_LOGS_PREFIX}/monitoring_logs_{timestamp_str}.json"
                )
                logger.info(f"Uploaded logs to s3://{S3_BUCKET}/{S3_LOGS_PREFIX}/monitoring_logs_{timestamp_str}.json")
            except Exception as e:
                error_msg = f"Failed to upload logs to S3: {str(e)}"
                logger.error(error_msg)
                add_log_entry("system", "s3_upload_logs", "failure", error_msg)
                result["errors"].append(error_msg)

            # Attempt inventory upload
            try:
                s3_client.upload_file(
                    inventory_filename,
                    S3_BUCKET,
                    f"{S3_INVENTORY_PREFIX}/monitoring_inventory_{timestamp_str}.json"
                )
                logger.info(f"Uploaded inventory to s3://{S3_BUCKET}/{S3_INVENTORY_PREFIX}/monitoring_inventory_{timestamp_str}.json")
            except Exception as e:
                error_msg = f"Failed to upload inventory to S3: {str(e)}"
                logger.error(error_msg)
                add_log_entry("system", "s3_upload_inventory", "failure", error_msg)
                result["errors"].append(error_msg)

        # Prepare final result
        tagged_new = 0
        tagged_already = 0
        failed = 0
        
        for rid, info in discovered_resources.items():
            status = info.get("status")
            if status == "tagged":
                tagged_new += 1
            elif status == "already_tagged":
                tagged_already += 1
            elif status == "failed":
                failed += 1

        # Set results
        result["tagged_new"] = tagged_new
        result["already_tagged"] = tagged_already
        result["failed"] = failed
        result["statusCode"] = 200

        summary = f"Monitoring tagging complete! Tagged {tagged_new} new resources, {tagged_already} already tagged, {failed} failed."
        result["message"] = summary
        result["logs_file"] = logs_filename
        result["inventory_file"] = inventory_filename
        
        logger.info(summary)
        
    except Exception as e:
        # Catch-all for any unexpected errors in the main flow
        error_msg = f"Unhandled error in monitoring tagger: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        result["errors"].append(error_msg)
    
    return result


# Entry point for executing as a script (local usage or SSM Run Command)
def main():
    """Main entry point for local execution or SSM run-command usage"""
    logger.info("Starting monitoring tagger script in local/SSM mode")
    
    # Parse command line arguments here if needed
    import argparse
    parser = argparse.ArgumentParser(description='Monitor AWS resources and tag them')
    parser.add_argument('--profile', help='AWS profile to use')
    parser.add_argument('--region', help='AWS region to use')
    parser.add_argument('--tag-key', help='Tag key to apply')
    parser.add_argument('--tag-value', help='Tag value to apply')
    parser.add_argument('--s3-bucket', help='S3 bucket for output')
    parser.add_argument('--s3-prefix', help='S3 prefix for output')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with extra logging')
    
    args = parser.parse_args()
    
    # Set debug mode if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Override environment variables with command line args if provided
    if args.profile:
        os.environ['AWS_PROFILE'] = args.profile
        logger.info(f"Using AWS profile: {args.profile}")
    if args.region:
        os.environ['REGION'] = args.region
        logger.info(f"Using AWS region: {args.region}")
    else:
        logger.info(f"Using default region: {REGION}")
    if args.tag_key:
        os.environ['TAG_KEY'] = args.tag_key
    if args.tag_value:
        os.environ['TAG_VALUE'] = args.tag_value
    if args.s3_bucket:
        os.environ['S3_BUCKET'] = args.s3_bucket
    if args.s3_prefix:
        os.environ['S3_PREFIX'] = args.s3_prefix
    
    # Call the lambda handler with empty event
    result = lambda_handler({}, None)
    
    # Print result
    print(json.dumps(result, indent=2))
    
    if result["statusCode"] != 200:
        logger.error("Script finished with errors")
        return 1
    else:
        logger.info("Script finished successfully")
        return 0


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
