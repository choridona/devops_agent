import json
import logging
import os
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    enable_upload = os.environ.get("ENABLE_UPLOAD", "false").lower() == "true"
    bucket_name = os.environ["S3_BUCKET_NAME"]

    file_name = event.get("file_name", "sample.txt")
    file_content = event.get("file_content", "Hello from Lambda!")

    if not enable_upload:
        logger.error("LOG-ERROR file_name=%s bucket=%s reason=upload_disabled", file_name, bucket_name)
        return {
            "statusCode": 403,
            "body": json.dumps({"message": "Upload is disabled by configuration."}),
        }

    s3_client = boto3.client("s3")
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=file_name,
            Body=file_content.encode("utf-8"),
        )
        logger.info("LOG-SUCCESS file_name=%s bucket=%s", file_name, bucket_name)
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "File uploaded successfully.",
                "bucket": bucket_name,
                "key": file_name,
            }),
        }
    except ClientError as e:
        logger.error("LOG-ERROR file_name=%s bucket=%s reason=s3_client_error error=%s", file_name, bucket_name, str(e))
        raise
