ARG VARIANT=1-3.13-bookworm
FROM mcr.microsoft.com/devcontainers/python:${VARIANT}

RUN rm -f /etc/apt/sources.list.d/yarn.list

RUN python3 -m pip install --break-system-packages --upgrade pip \
    && python3 -m pip install --break-system-packages uv
