#!/bin/bash
set -e

BACKEND_STORE="sqlite:////mlflow/data/mlflow.db"
ARTIFACT_ROOT="s3://${R2_BUCKET_NAME:-mini-project-lake}/mlflow-artifacts"

echo "================================================================="
echo "       📊 STARTING MLFLOW TRACKING SERVER 📊"
echo "• Backend Store : $BACKEND_STORE"
echo "• Artifact Root : $ARTIFACT_ROOT (Cloudflare R2 $0 Egress)"
echo "• Endpoint URL  : $MLFLOW_S3_ENDPOINT_URL"
echo "================================================================="

exec mlflow server \
    --backend-store-uri "$BACKEND_STORE" \
    --default-artifact-root "$ARTIFACT_ROOT" \
    --host 0.0.0.0 \
    --port 5000
