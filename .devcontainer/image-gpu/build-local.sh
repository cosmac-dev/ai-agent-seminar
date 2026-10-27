#!/usr/bin/env bash
# GPU 用イメージをローカルでビルドし、構成が参照する名前でローカルにタグ付けする（linux/amd64）。
# GHCR へのログイン・push は行わない。タグはこのマシンの Docker にだけ存在する。
#
#   bash .devcontainer/image-gpu/build-local.sh
#
# 同名のイメージがローカルにあると、Dev Containers（VS Code / devcontainer CLI）は取得せずにそれを使う。
set -euo pipefail

IMAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="ghcr.io/cosmac-dev/ai-agent-seminar-devcontainer-gpu"
VERSION="$(tr -d '[:space:]' < "${IMAGE_DIR}/VERSION")"
REFERENCE="${IMAGE_NAME}:${VERSION}"

docker buildx build --platform linux/amd64 --load \
  --build-arg IMAGE_VERSION="${VERSION}-local" \
  -t "${REFERENCE}" \
  -t "ai-agent-seminar-devcontainer-gpu:local" \
  "${IMAGE_DIR}"

docker run --rm --network none --user vscode "${REFERENCE}" \
  bash /usr/local/share/ai-agent-seminar/smoke-test.sh

echo "[build-local] ローカルにタグ付けしました: ${REFERENCE}（GHCR には push していません）"
