#!/usr/bin/env bash
# session16/.venv を作成し、session16/requirements.txt の固定版と Notebook カーネル用の ipykernel を入れる。
# 第16回のフレームワーク群は共通イメージの依存（openai など）と版が異なるため、システムの Python には入れない。
# requirements.txt がない版の教材では、共通イメージのパッケージを引き継ぐ venv にする。
set -euo pipefail

SESSION_DIR="$(readlink -f "$(dirname "${BASH_SOURCE[0]}")/../../session16")"  # クローン先のディレクトリ名によらない
IPYKERNEL_VERSION="7.4.0"  # 共通イメージと同じ版

cd "${SESSION_DIR}" || exit 1

if [[ "$(id -un)" != "vscode" ]]; then
  echo "[session16] 環境の作成・更新は vscode ユーザーで実行してください。docker exec を使う場合は --user vscode を指定してください。" >&2
  exit 1
fi

if [[ -d .venv && ( ! -w .venv || ( -d .venv/bin && ! -w .venv/bin ) ) ]]; then
  echo "[session16] 既存の .venv に書き込めません。所有者・権限を確認し、必要なら .venv だけを退避して vscode ユーザーで再作成してください。" >&2
  exit 1
fi

# --seed: Notebook の %pip が venv の pip を使うため
if [[ -f requirements.txt ]]; then
  if ! uv venv --seed --allow-existing .venv \
    || ! uv pip install --python .venv/bin/python -r requirements.txt "ipykernel==${IPYKERNEL_VERSION}"; then
    echo "[session16] .venv の作成または requirements.txt の導入に失敗しました。直前の uv のエラーを確認して原因を解消し、vscode ユーザーでこのスクリプトを再実行してください。" >&2
    exit 1
  fi
else
  uv venv --seed --allow-existing --system-site-packages .venv
fi
