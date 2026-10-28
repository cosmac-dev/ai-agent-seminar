#!/usr/bin/env bash
# ホストの Hugging Face のキャッシュ（読み取り専用でマウント）にあるモデルを、コンテナのキャッシュから使えるようにする。
# モデルごとにディレクトリをコピーし、ファイルはホストへのシンボリックリンクにする（cp -rs）。refs だけは実ファイルにする。
# コンテナで新たに取得したファイル（別のモデル、同じモデルの新しい版）はコンテナのキャッシュにだけ保存され、
# コンテナとともに破棄される。ホストのキャッシュには書き込まない。
# .devcontainer/session01/ と .devcontainer/session03-gpu/ に同じ内容で置く。
set -euo pipefail

HOST_HUB=/mnt/host-hf-hub
CONTAINER_HUB="${HOME}/.cache/huggingface/hub"

# ホストで HF_HUB_CACHE を設定していない場合はディレクトリでないもの（/dev/null）がマウントされる
[[ -d "${HOST_HUB}" ]] || exit 0

mkdir -p "${CONTAINER_HUB}"
linked=0
for source in "${HOST_HUB}"/models--*; do
  [[ -d "${source}" ]] || continue
  target="${CONTAINER_HUB}/$(basename "${source}")"
  # コンテナで既に使っているモデルはそのままにする
  [[ -e "${target}" ]] && continue
  cp -rs "${source}" "${target}"
  if [[ -d "${source}/refs" ]]; then
    rm -rf "${target}/refs"
    cp -r "${source}/refs" "${target}/refs"
  fi
  linked=$((linked + 1))
done
echo "[link-host-models] ホストのモデルを ${linked} 件追加しました（${HOST_HUB}）"
