ARG VARIANT=1-3.12-bookworm
FROM mcr.microsoft.com/devcontainers/python:${VARIANT}

# ベースイメージに残る yarn の apt リポジトリは署名鍵を検証できず、apt-get update が失敗する。
# docker-outside-of-docker feature は apt 経由で docker CLI を導入するため、先に取り除く。
RUN rm -f /etc/apt/sources.list.d/yarn.list

RUN python -m pip install --upgrade pip \
    && python -m pip install ipykernel
