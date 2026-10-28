# syntax=docker/dockerfile:1
# NVIDIA GPU を前提とする回（第1回、第3回の GPU 版）の Dev Container イメージ。
# linux/amd64 と linux/arm64（DGX Spark など NVIDIA GPU のある Arm のマシン）をビルドする。
# 構成（.devcontainer/session01/ など）はビルド済みのこのイメージを "image" で参照し、hostRequirements.gpu で GPU を使う。
# 依存を変える場合は requirements.in を編集して requirements-<アーキテクチャ>.txt を再生成し、VERSION を上げる。

# ベースイメージと uv は共通イメージ（../image/Dockerfile）と同じものをタグとダイジェストの両方で固定する。
ARG BASE_IMAGE=mcr.microsoft.com/devcontainers/python:3.2.6-3.13-trixie@sha256:5ea7e72d3c1beb6aefdfea8001483345c39af4898e22f2c543deb6a00802ede4
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.4@sha256:9f130421e930bfbdc563c00740466603f8723158e90297d07957c2294640262b

FROM ${UV_IMAGE} AS uv

FROM ${BASE_IMAGE}

COPY --from=uv /uv /uvx /usr/local/bin/

# torch（CUDA 版）・transformers などをシステムの Python 3.13 に固定版で入れる。
# requirements-<アーキテクチャ>.txt は requirements.in から uv pip compile --generate-hashes で生成したもの。
# arm64 は PyPI の torch が CPU 版のため、torch を PyTorch の CUDA 12.8 用インデックスから取る（--torch-backend cu128）。
ARG TARGETARCH
COPY requirements-${TARGETARCH}.txt /tmp/seminar-requirements.txt
RUN if [ "${TARGETARCH}" = "arm64" ]; then export UV_TORCH_BACKEND=cu128; fi \
    && uv pip install --system --require-hashes --no-cache -r /tmp/seminar-requirements.txt \
    && rm /tmp/seminar-requirements.txt

COPY --chmod=0755 smoke-test.sh /usr/local/share/ai-agent-seminar/smoke-test.sh

# uv が別の Python を取得せず、イメージの Python 3.13 を使うようにする。
ENV UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python

ARG IMAGE_VERSION=0.0.0-dev
LABEL org.opencontainers.image.title="ai-agent-seminar-devcontainer-gpu" \
      org.opencontainers.image.description="NVIDIA GPU Dev Container image for ai-agent-seminar sessions" \
      org.opencontainers.image.version="${IMAGE_VERSION}"
