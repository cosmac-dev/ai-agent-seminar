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

第9回の構成はホストの Docker ソケットを共有しないため、`DockerExecutionPolicy` は利用できません。
Docker のサンドボックスは、Docker outside of Docker を有効にした第10回の構成で扱います。
準備手順は [`session10/README.md`](../session10/README.md) を参照してください。

`HostExecutionPolicy` は Dev Container 自体でコマンドを実行します。
`CodexSandboxExecutionPolicy` は、Dev Container 内でホストカーネルのサンドボックス機構を
利用できない場合があるため、環境によっては起動しません。

### トラブルシューティング

| 症状 | 対処 |
| --- | --- |
| API キーがコンテナに渡らない | キーを設定したターミナルから VS Code を起動し直し、コンテナをリビルド |
