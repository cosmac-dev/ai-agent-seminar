"""各回の devcontainer.json が共通イメージだけを参照していることを確認する。

python3 .devcontainer/image/check-configs.py で実行する（リポジトリのルートから）。
"""

import json
import re
import sys
from pathlib import Path

DEVCONTAINER_DIR = Path(__file__).resolve().parents[1]
IMAGE_NAME = "ghcr.io/cosmac-dev/ai-agent-seminar-devcontainer"
# ホストの Docker ソケットを共有してよい回（サンドボックスで DockerExecutionPolicy を使う回）
DOCKER_SOCKET_SESSIONS = {"session10", "session11", "session12"}
DOOD_FEATURE = "ghcr.io/devcontainers/features/docker-outside-of-docker:1.10.1"


def load_jsonc(path: Path) -> dict:
    # 設定ファイルでは行コメント（行頭の //）だけを使う
    text = re.sub(r"^\s*//.*$", "", path.read_text(encoding="utf-8"), flags=re.M)
    return json.loads(text)


def main() -> int:
    version = (DEVCONTAINER_DIR / "image" / "VERSION").read_text(encoding="utf-8").strip()
    expected_image = f"{IMAGE_NAME}:{version}"
    errors = []
    configs = sorted(DEVCONTAINER_DIR.glob("**/devcontainer.json"))
    for path in configs:
        rel = path.relative_to(DEVCONTAINER_DIR.parent)
        session = path.parent.name if path.parent != DEVCONTAINER_DIR else "root"
        config = load_jsonc(path)
        if config.get("image") != expected_image:
            errors.append(f"{rel}: image が {expected_image} ではありません: {config.get('image')}")
        if "build" in config or "dockerFile" in config:
            errors.append(f"{rel}: build / dockerFile は使わず共通イメージを参照してください")
        features = config.get("features", {})
        mounts = " ".join(str(m) for m in config.get("mounts", []))
        uses_socket = DOOD_FEATURE in features or "docker.sock" in mounts
        if session in DOCKER_SOCKET_SESSIONS:
            if DOOD_FEATURE not in features or "docker-host.sock" not in mounts:
                errors.append(f"{rel}: Docker ソケットの共有設定がありません")
        elif uses_socket:
            errors.append(f"{rel}: この回では Docker ソケットを共有しません")
        unexpected = set(features) - {DOOD_FEATURE}
        if unexpected:
            errors.append(f"{rel}: 想定外の feature: {sorted(unexpected)}")
        for key in ("privileged", "capAdd", "securityOpt", "runArgs"):
            if key in config:
                errors.append(f"{rel}: {key} で権限を追加しないでください")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"OK: {len(configs)} configs reference {expected_image}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
