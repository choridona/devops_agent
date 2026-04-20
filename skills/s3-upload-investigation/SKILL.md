---
name: s3-upload-error-investigation
description: Use this skill when investigating LOG-ERROR incidents triggered by the s3-upload-function-log-error
  CloudWatch alarm. This skill applies to S3 upload failures where the ENABLE_UPLOAD environment variable
  may be disabled or S3 permissions may be misconfigured. The investigation waits 10 minutes to check
  for automatic recovery by looking for a matching LOG-SUCCESS entry, then escalates to detailed root
  cause analysis if recovery is not confirmed. Notify all findings to Slack upon completion.
---

# S3 Upload Error Investigation

Use this skill when the `s3-upload-function-log-error` CloudWatch alarm fires.

## Step 1: Identify the failed file

Query CloudWatch Logs Insights on log group `/aws/lambda/s3-upload-function`:

```
fields @timestamp, @message
| filter @message like /LOG-ERROR/
| sort @timestamp desc
| limit 5
```

Extract `file_name` from the log message (format: `LOG-ERROR file_name=<name> bucket=<bucket> reason=<reason>`).

Note the `reason` field:
- `upload_disabled` — ENABLE_UPLOAD=false, upload intentionally blocked
- `s3_client_error` — S3 API error occurred

## Step 2: Wait 10 minutes

Wait 10 minutes from the alarm time before proceeding.
This allows time for automatic recovery or manual intervention.

## Step 3: Check for automatic recovery

Query CloudWatch Logs Insights for LOG-SUCCESS with the same `file_name`:

```
fields @timestamp, @message
| filter @message like /LOG-SUCCESS/
| filter @message like /file_name=<file_name>/
| sort @timestamp desc
| limit 1
```

Time range: last 15 minutes.

## Step 4: Evaluate and notify Slack

**If LOG-SUCCESS found for the same file_name:**

Send a Slack notification:
> ✅ 調査完了 - OK
> アラーム: `s3-upload-function-log-error`
> ファイル `<file_name>` は10分以内に正常にアップロードされました。

Investigation complete.

**If LOG-SUCCESS NOT found:**

Proceed to Step 5.

## Step 5: Detailed investigation

**5a. Check ENABLE_UPLOAD setting**

Check the Lambda environment variable for `s3-upload-function`:
- If `ENABLE_UPLOAD=false` → upload is intentionally disabled. This is the root cause.
- Recommendation: Set `ENABLE_UPLOAD=true` and redeploy the CloudFormation stack.

**5b. Check recent error pattern**

Query the last 30 minutes of LOG-ERROR entries to assess frequency:

```
fields @timestamp, @message
| filter @message like /LOG-ERROR/
| sort @timestamp desc
| limit 20
```

**5c. Check S3 permissions (if reason=s3_client_error)**

Verify the Lambda execution role has `s3:PutObject` on the target bucket.

## Step 6: Notify Slack with findings

Send a Slack notification summarizing:

- File name that failed
- Root cause (upload_disabled / s3_client_error / unknown)
- Recommended action (enable ENABLE_UPLOAD / fix S3 permissions / escalate)

Example:
> ❌ 調査継続 - 要確認
> アラーム: `s3-upload-function-log-error`
> ファイル `<file_name>` の自動回復を確認できませんでした。
> 原因: `<reason>`
> 対応: `<recommendation>`
