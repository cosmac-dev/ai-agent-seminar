# syntax=docker/dockerfile:1
# 全セッション共通の Dev Container イメージ。
# 各回の .devcontainer/sessionNN/devcontainer.json はビルド済みのこのイメージを "image" で参照する。
# バージョンを変える場合は README.md の手順で requirements.txt を再生成し、IMAGE_VERSION を上げる。

# ベースイメージと uv はタグとダイジェストの両方で固定する（linux/amd64・linux/arm64 の index）。
ARG BASE_IMAGE=mcr.microsoft.com/devcontainers/python:3.2.6-3.13-trixie@sha256:5ea7e72d3c1beb6aefdfea8001483345c39af4898e22f2c543deb6a00802ede4
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.4@sha256:9f130421e930bfbdc563c00740466603f8723158e90297d07957c2294640262b

FROM ${UV_IMAGE} AS uv

FROM ${BASE_IMAGE}

# Docker CLI だけを Docker 公式の apt リポジトリから入れる（デーモンは入れない）。
# ホストのソケットへの接続は、必要な回の devcontainer.json だけが docker-outside-of-docker feature で行う。
ARG DOCKER_CLI_VERSION=5:29.9.2-1~debian.13~trixie
ARG DOCKER_APT_SIGNER_FINGERPRINT=9DC858229FC7DD38854AE2D88D81803C0EBFCD88

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /tmp/docker.asc \
    && actual="$(gpg --show-keys --with-colons /tmp/docker.asc | awk -F: '/^fpr:/ {print $10; exit}')" \
    && if [[ "${actual}" != "${DOCKER_APT_SIGNER_FINGERPRINT}" ]]; then \
         echo "Docker apt key fingerprint mismatch: ${actual}" >&2; exit 1; \
       fi \
    && gpg --dearmor -o /etc/apt/keyrings/docker.gpg /tmp/docker.asc \
    && rm /tmp/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends "docker-ce-cli=${DOCKER_CLI_VERSION}" \
    && apt-mark hold docker-ce-cli \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/

# 教材で使うフレームワーク・SDK をシステムの Python 3.13 に固定版で入れる。
# requirements.txt は requirements.in から uv pip compile --generate-hashes で生成したもの。
COPY requirements.txt /tmp/seminar-requirements.txt
RUN uv pip install --system --require-hashes --no-cache -r /tmp/seminar-requirements.txt \
    && rm /tmp/seminar-requirements.txt

COPY --chmod=0755 seminar-docker-check.sh /usr/local/bin/seminar-docker-check
COPY --chmod=0755 smoke-test.sh /usr/local/share/ai-agent-seminar/smoke-test.sh

# uv が別の Python を取得せず、イメージの Python 3.13 を使うようにする（session14 の uv sync を含む）。
ENV UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python

ARG IMAGE_VERSION=0.0.0-dev
LABEL org.opencontainers.image.title="ai-agent-seminar-devcontainer" \
      org.opencontainers.image.description="Common Dev Container image for ai-agent-seminar sessions" \
      org.opencontainers.image.version="${IMAGE_VERSION}"
