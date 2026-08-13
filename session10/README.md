# 第9回: Human-in-the-Loop, Sandbox

## Notebook

- [`session09_hitl_sbx.ipynb`](session09_hitl_sbx.ipynb)

OpenAI API を利用するセルには `OPENAI_API_KEY`、Web 検索には `TAVILY_API_KEY` が必要です。
必要な依存パッケージは、ノートブック冒頭のセットアップセルでインストールします。

## 実行環境

- VS Code（ローカル）
- Google Colab
- VS Code（Dev Container）

ただし、ノートブックで扱う `ExecutionPolicy` は、実行環境の OS、利用できる CLI、
サンドボックス機構によって制限されることがあります。ノートブックの
**「利用できるExecutionPolicyの確認」** セルを実行し、現在の環境で利用できる Policy を
確認してください。

| ExecutionPolicy | 必要なもの | 主な制限 |
| --- | --- | --- |
| `HostExecutionPolicy` | `/bin/bash` を実行できる環境 | ファイルとネットワークは隔離されない。Windows のネイティブ Python など、`/bin/bash` がない環境では利用できない |
| `CodexSandboxExecutionPolicy` | Codex CLI と、OS が提供するサンドボックス機構 | 主に macOS / Linux 向け。コンテナ内では Landlock などを利用できず、起動に失敗することがある |
| `DockerExecutionPolicy` | Docker CLI、接続可能な Docker デーモン、`python:3.12-alpine` イメージ | Google Colab など Docker デーモンを利用できない環境では実行できない |

利用できない Policy があっても、HITL など他の章は実行できます。

## 事前準備

### ExecutionPolicy の設定

LangGraph Server では、`.env` の `GUARDED_AGENT_EXECUTION_POLICY` で
`ShellToolMiddleware` の実行環境を上書きできます。

```bash
cp .env.example .env
```

`.env` では `host`、`docker`、`codex` のいずれかを指定してください。未指定時は
`host` を使用します。

```dotenv
GUARDED_AGENT_EXECUTION_POLICY=docker
```

### リポジトリのクローン

ローカルにリポジトリを取得

```bash
git clone https://github.com/cosmac-dev/ai-agent-seminar.git
cd ai-agent-seminar/session08
```

> 既にリポジトリをクローン済みの場合は、最新の状態に更新
>
> ```bash
> cd ai-agent-seminar
> git pull
> ```


## Google Colab利用時の注意

Colabでは通常Dockerデーモンを利用できません。Codex CLIはインストールできますが、Colabランタイムの権限制約によりCodexのLinuxサンドボックスが動作しない場合があります。

## VS Code（Dev Container）利用時の注意

Dev Container 内からホストの Docker デーモンを利用する
**Docker outside of Docker（DooD）** を有効にしています。

- ホストの Docker ソケットを `/var/run/docker-host.sock` として共有し、feature が用意する
  プロキシを通して `/var/run/docker.sock` から利用する
- サンドボックスのコンテナは Dev Container 内ではなく、ホストの Docker デーモン上で起動する
- Docker in Docker と異なり `--privileged` は不要で、ホストのイメージキャッシュを利用できる

macOS / Windows では Docker Desktop、WSL では Docker Desktop の WSL integration または
WSL 内の Docker Engine、Linux では Docker Engine を起動しておきます。rootless Docker や
既定以外のソケットを使う場合は、VS Code を起動する前に `CMC_DOCKER_SOCKET` を設定します。

```bash
export CMC_DOCKER_SOCKET="$HOME/.colima/default/docker.sock"  # Colima
export CMC_DOCKER_SOCKET="$HOME/.orbstack/run/docker.sock"    # OrbStack
export CMC_DOCKER_SOCKET="$HOME/.rd/docker.sock"              # Rancher Desktop
export CMC_DOCKER_SOCKET="/run/user/$(id -u)/docker.sock"     # rootless Docker
```

コンテナ作成時に
[`post-create.sh`](../.devcontainer/session09/post-create.sh) が Docker の疎通を確認し、
`python:3.12-alpine` を取得します。失敗してもコンテナ作成は中断しないため、必要に応じて
次のコマンドで再実行できます。

```bash
bash /workspaces/ai-agent-seminar/.devcontainer/session09/post-create.sh
```

動作確認:

```bash
docker version
docker run --rm --network=none python:3.12-alpine python -c "print('ok')"
```

`HostExecutionPolicy` は Dev Container 自体でコマンドを実行します。
`DockerExecutionPolicy` は DooD による専用コンテナを使用できます。
`CodexSandboxExecutionPolicy` は、Dev Container 内でホストカーネルのサンドボックス機構を
利用できない場合があるため、環境によっては起動しません。

### トラブルシューティング

| 症状 | 対処 |
| --- | --- |
| `Cannot connect to the Docker daemon` | Docker Desktop / Docker Engine の起動を確認し、**Dev Containers: Rebuild Container** を実行 |
| `docker: command not found` | **Dev Containers: Rebuild Container Without Cache** を実行 |
| `Error response from daemon: No such image` | `docker pull python:3.12-alpine` を実行 |
| `permission denied ... docker.sock` | Linux では Docker グループを確認。rootless Docker では `CMC_DOCKER_SOCKET` を設定 |
| API キーがコンテナに渡らない | キーを設定したターミナルから VS Code を起動し直し、コンテナをリビルド |
