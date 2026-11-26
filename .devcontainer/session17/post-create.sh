#!/usr/bin/env bash
# 第17回の Dev Container の作成時に実行する。
# - 完成版パッケージ（session17/src/computer_use_agent）を editable で導入し、OpenAI Agents SDK を導入する
# - 仮想デスクトップ用に、ホストの Docker デーモンへ接続できるか確認し、ベースイメージを取得する
set -euo pipefail

SESSION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../session17" && pwd)"

python -m pip install --no-build-isolation --no-deps -e "${SESSION_DIR}"
# OpenAI Agents SDK は共通イメージに含まれないため、ここで導入する（ほかの依存は共通イメージにある）
python -m pip install "openai-agents==0.26.0"

# 疎通を確認し、仮想デスクトップのベースイメージ（session17/desktop/Dockerfile の BASE_IMAGE）を先に取得しておく
base_image="$(sed -n 's/^ARG BASE_IMAGE=//p' "${SESSION_DIR}/desktop/Dockerfile")"
SANDBOX_IMAGE="${base_image}" seminar-docker-check session17
