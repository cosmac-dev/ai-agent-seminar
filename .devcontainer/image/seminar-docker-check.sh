#!/usr/bin/env bash
# Docker outside of Docker の疎通確認と、サンドボックス用イメージの取得。
# docker-outside-of-docker feature を有効にした回（第10回〜第12回）の postCreateCommand から
# `seminar-docker-check sessionNN` として呼び出す。手動での再実行も同じコマンドで行う。
# サンドボックスは --pull=never で実行するため、イメージがホスト側に存在しないとコマンドが失敗する。
#
# 失敗してもコンテナ作成は止めない（Docker を使わない範囲は実行できる）。
set -uo pipefail

LABEL="${1:-ai-agent-seminar}"
SANDBOX_IMAGE="${SANDBOX_IMAGE:-python:3.12-alpine}"
SOCKET_WAIT_SECONDS=30

if ! command -v docker >/dev/null 2>&1; then
  echo "[${LABEL}] docker CLI が見つかりません。共通イメージを取得し直してください（Dev Containers: Rebuild Container Without Cache）。" >&2
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
  cat >&2 <<MSG
[${LABEL}] ホストの Docker デーモンに接続できません。次を確認してください。
  - macOS / Windows: Docker Desktop が起動しているか
  - WSL: Docker Desktop の WSL integration が有効か、または WSL 内の Docker Engine が起動しているか
  - Linux: /var/run/docker.sock が存在するか（rootless の場合はホストで CMC_DOCKER_SOCKET を設定）
  - この回の devcontainer.json で docker-outside-of-docker feature が有効か
確認後に「Dev Containers: Rebuild Container」を実行してください。
MSG
  exit 0
fi

if docker image inspect "${SANDBOX_IMAGE}" >/dev/null 2>&1; then
  echo "[${LABEL}] サンドボックス用イメージを確認しました: ${SANDBOX_IMAGE}"
  exit 0
fi

echo "[${LABEL}] サンドボックス用イメージを取得します: ${SANDBOX_IMAGE}"
if ! docker pull "${SANDBOX_IMAGE}"; then
  echo "[${LABEL}] イメージの取得に失敗しました。ネットワークを確認し、docker pull ${SANDBOX_IMAGE} を手動で実行してください。" >&2
fi
