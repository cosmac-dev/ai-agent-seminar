#!/usr/bin/env bash
# 共通イメージをローカルでビルドし、各構成が参照する名前でローカルにタグ付けする。
# GHCR へのログイン・push は行わない。タグはこのマシンの Docker にだけ存在する。
#
#   bash .devcontainer/image/build-local.sh            # このマシンのアーキテクチャでビルド
#   PLATFORM=linux/amd64 bash .devcontainer/image/build-local.sh
#
# 同名のイメージがローカルにあると、Dev Containers（VS Code / devcontainer CLI）は取得せずにそれを使う。
set -euo pipefail

IMAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="ghcr.io/cosmac-dev/ai-agent-seminar-devcontainer"
VERSION="$(tr -d '[:space:]' < "${IMAGE_DIR}/VERSION")"
REFERENCE="${IMAGE_NAME}:${VERSION}"

platform_args=()
if [[ -n "${PLATFORM:-}" ]]; then
  platform_args=(--platform "${PLATFORM}")
fi

docker buildx build "${platform_args[@]}" --load \
  --build-arg IMAGE_VERSION="${VERSION}-local" \
  -t "${REFERENCE}" \
  -t "ai-agent-seminar-devcontainer:local" \
  "${IMAGE_DIR}"

docker run --rm --network none --user vscode "${REFERENCE}" \
  bash /usr/local/share/ai-agent-seminar/smoke-test.sh

echo "[build-local] ローカルにタグ付けしました: ${REFERENCE}（GHCR には push していません）"
