# S3 Upload Lambda

フィーチャーフラグ付きで S3 へファイルをアップロードする AWS Lambda 関数です。

## 概要

| 項目 | 内容 |
|------|------|
| ランタイム | Python 3.12 |
| メモリ | 128 MB |
| タイムアウト | 30 秒 |
| デプロイ方式 | AWS SAM |

## アーキテクチャ

```
呼び出し元 → Lambda (s3-upload-function)
                │
                ├─ ENABLE_UPLOAD=false → 403 (アップロード無効)
                │
                └─ ENABLE_UPLOAD=true  → S3 PutObject → バケット
```

## パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `EnableUpload` | String | `false` | `true` でアップロード有効化 |
| `S3BucketName` | String | (必須) | アップロード先 S3 バケット名 |

## デプロイ

```bash
# ビルド
sam build

# 初回デプロイ（対話形式 / samconfig.toml を生成）
sam deploy --guided

# パラメータ指定でデプロイ
sam deploy \
  --stack-name s3-upload-lambda \
  --region ap-northeast-1 \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    EnableUpload=true \
    S3BucketName=my-bucket

# 2回目以降（samconfig.toml が存在する場合）
sam deploy

# フラグを切り替えてだけ再デプロイ
sam deploy \
  --parameter-overrides \
    EnableUpload=false \
    S3BucketName=dev-ops-agent-test-004246190174-ap-northeast-1-an \
    DevOpsAgentWebhookUrl=https://event-ai.ap-northeast-1.api.aws/webhook/generic/44b3c194-3cc3-4d12-afa0-aeb8b6cc582e \
    DevOpsAgentWebhookSecret=qfzO3dmGoxOg0aKmhk0ZZtSW6xh4EHUWNCv3+BWISqI=

# スタック削除
sam delete --stack-name s3-upload-lambda
```

## Lambda の呼び出し

### イベント形式

```json
{
  "file_name": "hello.txt",
  "file_content": "アップロードする内容"
}
```

| フィールド | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| `file_name` | いいえ | `sample.txt` | S3 オブジェクトキー |
| `file_content` | いいえ | `Hello from Lambda!` | ファイルの内容（UTF-8 文字列） |

### CLI での実行例

```bash
aws lambda invoke \
  --function-name s3-upload-function \
  --payload '{"file_name": "test.txt", "file_content": "Hello"}' \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json
```

### レスポンス例

**成功 (200)**
```json
{
  "statusCode": 200,
  "body": "{\"message\": \"File uploaded successfully.\", \"bucket\": \"my-bucket\", \"key\": \"test.txt\"}"
}
```

**アップロード無効 (403)**
```json
{
  "statusCode": 403,
  "body": "{\"message\": \"Upload is disabled by configuration.\"}"
}
```

## 環境変数

| 変数名 | 説明 |
|--------|------|
| `ENABLE_UPLOAD` | `true` のときのみ S3 へアップロード |
| `S3_BUCKET_NAME` | アップロード先バケット名 |

## IAM 権限

SAM の `S3CrudPolicy` により、指定バケットへの CRUD 操作が自動付与されます。

## ログ

CloudWatch Logs グループ: `/aws/lambda/s3-upload-function`（保持期間: 30 日）

## ディレクトリ構成

```
.
├── template.yaml       # SAM テンプレート
└── src/
    └── lambda_function.py  # Lambda ハンドラ
```
