#!/usr/bin/env bash
# terraform applyで構築したリソース情報をもとに.envファイルを生成する。
# `./scripts/generate_env.sh`で実行する(terraform apply後、リソース再作成時は再実行する)。

set -euo pipefail

SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
TF_DIR="${SCRIPT_DIR}/../terraform/main"
ENV_FILE="${SCRIPT_DIR}/../.env"

AWS_REGION=ap-northeast-1

# retrieveツールが接続するKnowledge BaseのID
KNOWLEDGE_BASE_ID=$(terraform -chdir="$TF_DIR" output -raw knowledge_base_id) || {
  echo "terraform output の取得に失敗しました。先に terraform apply を実行してください。" >&2
  exit 1
}

cat > "$ENV_FILE" <<EOF
# scripts/generate_env.shが生成するファイル。手動編集しない。
AWS_REGION=${AWS_REGION}
KNOWLEDGE_BASE_ID=${KNOWLEDGE_BASE_ID}
EOF

echo ".envを生成しました: ${ENV_FILE}"
