import base64
import hashlib
import hmac
import json
import logging
import os
import re
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

logs_client = boto3.client("logs")
secrets_client = boto3.client("secretsmanager")

_webhook_credentials = None


def _get_webhook_credentials():
    global _webhook_credentials
    if _webhook_credentials is None:
        secret_arn = os.environ["WEBHOOK_SECRET_ARN"]
        response = secrets_client.get_secret_value(SecretId=secret_arn)
        secret = json.loads(response["SecretString"])
        _webhook_credentials = secret["webhook_url"], secret["webhook_secret"]
    return _webhook_credentials


def _get_failed_file_name(log_group_name: str) -> str:
    """Query CloudWatch Logs Insights for the most recent LOG-ERROR and extract file_name."""
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = now_ms - 5 * 60 * 1000

    try:
        query_id = logs_client.start_query(
            logGroupName=log_group_name,
            startTime=start_ms,
            endTime=now_ms,
            queryString="fields @message | filter @message like /LOG-ERROR/ | sort @timestamp desc | limit 1",
        )["queryId"]

        result = {"status": "Running"}
        for _ in range(20):
            time.sleep(1)
            result = logs_client.get_query_results(queryId=query_id)
            if result["status"] in ("Complete", "Failed", "Cancelled"):
                break

        if result["status"] != "Complete" or not result["results"]:
            return "unknown"

        message = next(
            (f["value"] for f in result["results"][0] if f["field"] == "@message"),
            None,
        )
        if not message:
            return "unknown"

        match = re.search(r"file_name=(\S+)", message)
        return match.group(1) if match else "unknown"
    except Exception as e:
        logger.warning("Failed to extract file_name from logs: %s", e)
        return "unknown"


def handler(event, context):
    webhook_url, webhook_secret = _get_webhook_credentials()
    log_group_name = os.environ["LOG_GROUP_NAME"]

    detail = event.get("detail", {})
    alarm_name = detail.get("alarmName", "Unknown Alarm")
    alarm_description = detail.get("alarmDescription", "")
    state_reason = detail.get("state", {}).get("reason", "")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    file_name = _get_failed_file_name(log_group_name)
    logger.info("Detected failed file_name=%s", file_name)

    description = f"{alarm_description}\n\nFailed file: {file_name}\nReason: {state_reason}".strip()

    payload = json.dumps({
        "eventType": "incident",
        "incidentId": f"{alarm_name}-{timestamp}",
        "action": "created",
        "priority": "HIGH",
        "title": f"CloudWatch Alarm: {alarm_name}",
        "description": description,
        "timestamp": timestamp,
        "service": alarm_name,
        "metadata": {"file_name": file_name},
    })

    signature = hmac.new(
        webhook_secret.encode("utf-8"),
        f"{timestamp}:{payload}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature_b64 = base64.b64encode(signature).decode("utf-8")

    req = urllib.request.Request(
        webhook_url,
        data=payload.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-amzn-event-timestamp": timestamp,
            "x-amzn-event-signature": signature_b64,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            logger.info("DevOps Agent response status=%s body=%s", response.status, body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        logger.error("DevOps Agent webhook failed status=%s body=%s", e.code, body)
        raise

    return {"statusCode": 200, "file_name": file_name}
