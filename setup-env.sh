#!/usr/bin/env bash
# 저장소 루트에 .env 생성 (.env.example 복사)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/.env"
EXAMPLE="$ROOT/.env.example"

if [[ ! -f "$EXAMPLE" ]]; then
  echo "오류: .env.example 이 없습니다" >&2
  exit 1
fi

if [[ -f "$ENV_FILE" ]]; then
  echo "이미 있습니다: $ENV_FILE"
  echo "덮어쓰려면: rm .env && ./setup-env.sh"
  exit 0
fi

cp "$EXAMPLE" "$ENV_FILE"
echo "생성됨: $ENV_FILE"
echo "ANTHROPIC_API_KEY, OPENAI_API_KEY 등을 편집한 뒤 백엔드를 재시작하세요."
