#!/usr/bin/env bash
# ホストにある Hugging Face のモデルを、コンテナのキャッシュから使えるようにする。モデルは次から探す（どちらも読み取り専用でマウント）。
# - /mnt/host-hf-hub: ホストのディレクトリ（ホストで HF_HUB_CACHE を設定した場合。未設定ならディレクトリでない /dev/null）
# - /mnt/hf-hub-volume: Docker のボリューム（既定は ai-agent-seminar-hf-hub。直下か hub/ の下にモデルを置く）
# 同じモデルが両方にある場合は、ホストのディレクトリを使う。
# モデルごとにディレクトリをコピーし、ファイルはマウント先へのシンボリックリンクにする（cp -rs）。refs だけは実ファイルにする。
# コンテナで新たに取得したファイル（別のモデル、同じモデルの新しい版）はコンテナのキャッシュにだけ保存され、
# コンテナとともに破棄される。マウントしたディレクトリ・ボリュームには書き込まない。
# .devcontainer/session01/ と .devcontainer/session03-gpu/ に同じ内容で置く。
set -euo pipefail

SOURCE_HUBS=(/mnt/host-hf-hub /mnt/hf-hub-volume /mnt/hf-hub-volume/hub)
CONTAINER_HUB="${HOME}/.cache/huggingface/hub"

mkdir -p "${CONTAINER_HUB}"
linked=0
for hub in "${SOURCE_HUBS[@]}"; do
  [[ -d "${hub}" ]] || continue
  for source in "${hub}"/models--*; do
    [[ -d "${source}" ]] || continue
    target="${CONTAINER_HUB}/$(basename "${source}")"
    # 先に見つけたモデルと、コンテナで既に使っているモデルはそのままにする
    [[ -e "${target}" ]] && continue
    cp -rs "${source}" "${target}"
    if [[ -d "${source}/refs" ]]; then
      rm -rf "${target}/refs"
      cp -r "${source}/refs" "${target}/refs"
    fi
    linked=$((linked + 1))
  done
done
echo "[link-host-models] ホストのモデルを ${linked} 件追加しました"
