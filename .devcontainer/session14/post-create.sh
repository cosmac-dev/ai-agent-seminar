#!/usr/bin/env bash
# uv.lock どおりに session14/.venv を作成し、Notebook カーネル用に ipykernel を追加する。
set -euo pipefail

SESSION_DIR="/workspaces/ai-agent-seminar/session14"

cd "${SESSION_DIR}" || exit 1

if [[ "$(id -un)" != "vscode" ]]; then
  echo "[session14] 環境の作成・更新は vscode ユーザーで実行してください。docker exec を使う場合は --user vscode を指定してください。" >&2
  exit 1
fi

if [[ -d .venv && ( ! -w .venv || ( -d .venv/bin && ! -w .venv/bin ) ) ]]; then
  echo "[session14] 既存の .venv に書き込めません。所有者・権限を確認し、必要なら .venv だけを退避して vscode ユーザーで再作成してください。.env は削除しないでください。" >&2
  exit 1
fi

if ! uv sync --locked; then
  echo "[session14] uv sync --locked に失敗しました。直前の uv のエラーを確認して原因を解消し、vscode ユーザーで session14 の uv sync --locked を再実行してください。" >&2
  exit 1
fi

if [[ ! -f .env && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "[session14] OPENAI_API_KEY が未設定で、session14/.env もありません。API を使う前に、ホストの CMC_OPENAI_API_KEY または session14/.env にキーを設定してください。.env は Dynaconf が自動で読み込みます。" >&2
fi
