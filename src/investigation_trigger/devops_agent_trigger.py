import hashlib
import hmac
import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    webhook_url = os.environ["DEVOPS_AGENT_WEBHOOK_URL"]
    webhook_secret = os.environ["DEVOPS_AGENT_WEBHOOK_SECRET"]

    detail = event.get("detail", {})
    alarm_name = detail.get("alarmName", "Unknown Alarm")
    alarm_description = detail.get("alarmDescription", "")
    state_reason = detail.get("state", {}).get("reason", "")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    payload = json.dumps({
        "eventType": "incident",
        "incidentId": f"{alarm_name}-{timestamp}",
        "action": "created",
        "priority": "HIGH",
        "title": f"CloudWatch Alarm: {alarm_name}",
        "description": f"{alarm_description}\n\nReason: {state_reason}".strip(),
        "timestamp": timestamp,
        "service": alarm_name,
    })

    # Generic webhook uses HMAC-SHA256: sign "{timestamp}:{payload}" with secret
    signature = hmac.new(
        webhook_secret.encode("utf-8"),
        f"{timestamp}:{payload}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    import base64
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

    return {"statusCode": 200}
