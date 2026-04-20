# DevOps Agent 自動調査デモ

S3 アップロード Lambda を使った DevOps Agent 自動調査のデモ環境です。

## アーキテクチャ

```
呼び出し元 → Lambda (s3-upload-function)
                │
                ├─ ENABLE_UPLOAD=false → LOG-ERROR file_name=xxx
                │       │
                │       └─ CloudWatch MetricFilter → Alarm
                │               │
                │               └─ EventBridge Rule
                │                       │
                │                       └─ InvestigationTriggerFunction
                │                               │ CW Logs から file_name 取得
                │                               │ Secrets Manager から認証情報取得
                │                               └─ DevOps Agent Webhook
                │                                       │
                │                          Skills に従い自律調査
                │                          ├─ 10分待機
                │                          ├─ LOG-SUCCESS 確認
                │                          └─ Slack 通知（コンソール設定済み）
                │
                └─ ENABLE_UPLOAD=true → LOG-SUCCESS file_name=xxx → S3 PutObject
```

---

## デプロイ手順

### ステップ 1: 初回 SAM デプロイ

```bash
sam build

sam deploy \
  --stack-name devops-agent-demo \
  --region ap-northeast-1 \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --parameter-overrides EnableUpload=false
```

デプロイ後、以下の Output を控える。

| Output キー | 用途 |
|-------------|------|
| `AgentSpaceId` | コンソールで Webhook 作成時に使用 |
| `WebhookCredentialsSecretArn` | Webhook 認証情報の格納先 |

---

### ステップ 2: コンソールでの作業（初回のみ）

#### 2-1. Generic Webhook を作成

1. [DevOps Agent コンソール](https://console.aws.amazon.com/devops-agent/) を開く
2. `AgentSpaceId` に対応する Agent Space を選択
3. **Integrations** → **Generic Webhook** → **Create**
4. 生成された **Webhook URL** と **Secret** をメモする

> Webhook ServiceId はコンソール経由でのみ登録できるため、CloudFormation 外で作成する。

#### 2-2. Secrets Manager: 認証情報を更新

```bash
aws secretsmanager put-secret-value \
  --secret-id <WebhookCredentialsSecretArn> \
  --secret-string '{"webhook_url":"<Webhook URL>","webhook_secret":"<Secret>"}'
```

#### 2-3. Skills のアップロード

1. `skills/s3-upload-investigation/` を zip 圧縮する
   ```bash
   cd skills && zip -r s3-upload-investigation.zip s3-upload-investigation/
   ```
2. DevOps Agent コンソール → **Skills** → **Upload** でアップロード

---

### 2回目以降の SAM デプロイ

`EnableUpload` の切り替えのみで OK。

```bash
sam deploy --parameter-overrides EnableUpload=true   # アップロード有効化
sam deploy --parameter-overrides EnableUpload=false  # エラーパターン（調査トリガー）
```

---

## Lambda の呼び出し

```bash
aws lambda invoke \
  --function-name s3-upload-function \
  --payload '{"file_name": "test.txt"}' \
  --cli-binary-format raw-in-base64-out \
  response.json
```

---

## ログフォーマット

| 種別 | フォーマット |
|------|------------|
| エラー | `LOG-ERROR file_name=xxx bucket=yyy reason=zzz` |
| 成功 | `LOG-SUCCESS file_name=xxx bucket=yyy` |

`reason` の値:
- `upload_disabled` — ENABLE_UPLOAD=false
- `s3_client_error` — S3 API エラー

---

## パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `EnableUpload` | `false` | `true` でアップロード有効化 |

---

## ディレクトリ構成

```
.
├── template.yaml
├── samconfig.toml
├── skills/
│   └── s3-upload-investigation/
│       └── SKILL.md
└── src/
    ├── lambda_function.py
    └── investigation_trigger/
        └── devops_agent_trigger.py
```
