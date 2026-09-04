#!/usr/bin/env bash
# ADOT計装に必要な環境変数をエクスポートする。`source scripts/otel_env.sh`で読み込む。
set -euo pipefail

export OTEL_PYTHON_DISTRO=aws_distro
export OTEL_PYTHON_CONFIGURATOR=aws_configurator
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_RESOURCE_ATTRIBUTES=service.name=agentcore-evaluations-demo
export AWS_REGION=ap-northeast-1
export KNOWLEDGE_BASE_ID=$(terraform -chdir="$(dirname "${BASH_SOURCE[0]}")/../terraform/main" output -raw knowledge_base_id)

# スパンをX-Ray(Transaction Search)へ直接送るためのOTLPエンドポイント
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="https://xray.${AWS_REGION}.amazonaws.com/v1/traces"
# session.id baggageをスパン属性へ伝播させるため、Agent Observabilityを有効化
export AGENT_OBSERVABILITY_ENABLED=true
# ログOTLPエクスポート(未設定のためエラーになる)は本タスクの対象外なので無効化
export OTEL_LOGS_EXPORTER=none
