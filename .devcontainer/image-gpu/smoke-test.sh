#!/usr/bin/env bash
# GPU 用イメージの内容を、API キー・外部 API・GPU を使わずに確認する。
# CI（devcontainer-image-gpu.yml）とローカルの docker run から実行する。
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

python - <<'PY'
import importlib

modules = [
    "ipykernel",
    "torch",
    "transformers",
    "accelerate",
    "huggingface_hub",
    "openai",
    "requests",
]
for name in modules:
    importlib.import_module(name)
print(f"[smoke-test] import OK: {len(modules)} modules")

import torch

# CUDA 版の torch であること（CI には GPU がないため、GPU が使えるかは確かめない）
if torch.version.cuda is None:
    raise SystemExit(f"[smoke-test] NG: torch {torch.__version__} は CUDA 版ではありません")
print(f"[smoke-test] torch {torch.__version__} (CUDA {torch.version.cuda})")
PY

python -m pip check

echo "[smoke-test] OK"
