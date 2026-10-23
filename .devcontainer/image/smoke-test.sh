#!/usr/bin/env bash
# 共通イメージの内容を、API キー・外部 API・Docker デーモンを使わずに確認する。
# CI（devcontainer-image.yml）とローカルの docker run から実行する。
set -euo pipefail

fail() {
  echo "[smoke-test] NG: $*" >&2
  exit 1
}

python_version="$(python -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
[[ "${python_version}" == "3.13" ]] || fail "Python 3.13 を期待しましたが ${python_version} でした"
[[ "$(command -v python)" == "/usr/local/bin/python" ]] || fail "python が /usr/local/bin/python ではありません"

uv --version | grep -q '^uv 0\.13\.4' || fail "uv 0.13.4 ではありません: $(uv --version)"
git --version >/dev/null || fail "git がありません"
docker --version | grep -q 'Docker version 29\.9\.2' || fail "Docker CLI 29.9.2 ではありません: $(docker --version)"
if command -v dockerd >/dev/null 2>&1; then
  fail "Docker デーモン（dockerd）は含めない想定です"
fi
command -v seminar-docker-check >/dev/null || fail "seminar-docker-check がありません"

python - <<'PY'
import importlib

modules = [
    "ipykernel",
    "openai",
    "requests",
    "langchain",
    "langchain_core",
    "langchain_openai",
    "langchain_community",
    "langchain_experimental",
    "langchain_tavily",
    "langchain_text_splitters",
    "langchain_mcp_adapters",
    "langgraph",
    "langgraph_cli",
    "fastmcp",
    "pydantic",
    "numpy",
    "httpx",
    "ddgs",
    "dotenv",
    "matplotlib",
    "matplotlib_fontja",
    "setuptools",
]
for name in modules:
    importlib.import_module(name)
print(f"[smoke-test] import OK: {len(modules)} modules")
PY

python -m pip check
langgraph --version >/dev/null || fail "langgraph CLI を実行できません"

echo "[smoke-test] OK"
