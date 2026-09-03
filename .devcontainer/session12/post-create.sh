#!/usr/bin/env bash
# Docker outside of Docker の疎通確認と、サンドボックス用イメージの取得。
# session12_planning_reflection_2.ipynb のサンドボックスは --pull=never で実行するため、
# イメージがホスト側に存在しないとコマンドが失敗する。
#
# 失敗してもコンテナ作成は止めない（Docker を使わない範囲は実行できる）。
set -uo pipefail

SANDBOX_IMAGE="${SANDBOX_IMAGE:-python:3.12-alpine}"
SOCKET_WAIT_SECONDS=30

if ! command -v docker >/dev/null 2>&1; then
  echo "[session12] docker CLI が見つかりません。devcontainer.json の docker-outside-of-docker feature が有効か確認してください。" >&2
  exit 0
fi

# feature の entrypoint が /var/run/docker.sock へのプロキシを用意するまで待つ
for _ in $(seq 1 "${SOCKET_WAIT_SECONDS}"); do
  if docker version >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! docker version >/dev/null 2>&1; then
  cat >&2 <<'MSG'
[session12] ホストの Docker デーモンに接続できません。次を確認してください。
  - macOS / Windows: Docker Desktop が起動しているか
  - WSL: Docker Desktop の WSL integration が有効か、または WSL 内の Docker Engine が起動しているか
  - Linux: /var/run/docker.sock が存在するか（rootless の場合はホストで CMC_DOCKER_SOCKET を設定）
確認後に「Dev Containers: Rebuild Container」を実行してください。
MSG
  exit 0
fi

if docker image inspect "${SANDBOX_IMAGE}" >/dev/null 2>&1; then
  echo "[session12] サンドボックス用イメージを確認しました: ${SANDBOX_IMAGE}"
  exit 0
fi

echo "[session12] サンドボックス用イメージを取得します: ${SANDBOX_IMAGE}"
if ! docker pull "${SANDBOX_IMAGE}"; then
  echo "[session12] イメージの取得に失敗しました。ネットワークを確認し、docker pull ${SANDBOX_IMAGE} を手動で実行してください。" >&2
fi
