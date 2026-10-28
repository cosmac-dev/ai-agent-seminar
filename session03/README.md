# 第3回：LLMを動かして理解する③

## 事前準備

> 第一回の事前準備が済んでいる場合は不要です。

1. Google アカウント（Colab 使用のため）
2. `session03_llm_basics.ipynb` を Colab で開けることを確認（下記「Colab でノートブックを開く」参照）


### Colab でノートブックを開く

同じ階層の [`session03_llm_basics.ipynb`](session03_llm_basics.ipynb) を Colab 上で開けるか、事前に確認してください。

1. GitHub 上で `session03/session03_llm_basics.ipynb` を開く
2. ノートブック先頭の **[Open In Colab]** をクリックする。Google に未ログインの場合はログイン画面が出るので、事前準備 1 のアカウントでログインする。Colab を初めて使う場合は、利用規約の同意やウェルカム画面が出ることがあるので、表示に従って進める
3. Colab で`session03_llm_basics.ipynb`が表示されることを確認する

## ローカル（Dev Container）で実行する場合

Dev Container の構成は 2 つあります（[リポジトリの README](../README.md#vs-codedev-container) を参照）。どちらのイメージも vLLM と Ollama を含まないため、ノートブックのセルでコンテナにインストールするか、コンテナの外（ホストなど）で起動したサーバーに接続します。

| 構成 | 対象 | vLLM（A） | Ollama（B） |
| --- | --- | --- | --- |
| **ai-agent-seminar-session03 (NVIDIA GPU)** | NVIDIA GPU のあるマシン | コンテナにインストール、またはコンテナの外のサーバーに接続 | コンテナにインストール、またはホストで起動 |
| **ai-agent-seminar-session03** | それ以外（Mac など） | A-1 は実行不可。A-2 はコンテナの外の NVIDIA GPU のあるマシンのサーバーに接続（用意できない場合は Colab で実行） | コンテナにインストール、またはホストで起動 |

- コンテナにインストールする場合: ノートブックの `INSTALL_VLLM`・`INSTALL_OLLAMA` を `True` にして実行します。どちらも数分かかり、vLLM はコンテナの容量がおよそ 3 GB 増えます。vLLM はインストール後にカーネルを再起動し、Ollama はターミナルで `ollama serve` を起動します。コンテナを作り直した場合はインストールし直します。
- ホストの Ollama を使う場合: ホストに [Ollama](https://ollama.com/download) をインストールし、ホストのターミナルで `ollama pull qwen3:0.6b` を実行しておきます。Mac では Mac の GPU を使います。
- 接続先: コンテナにインストールした場合は `localhost` に接続します。それ以外は、構成が環境変数 `VLLM_SERVER_HOST`・`OLLAMA_SERVER_HOST` で渡す接続先（既定は `host.docker.internal`）に接続します。変える場合は、ホストで同じ名前の環境変数を設定してからコンテナを作り直します。
- `host.docker.internal` は Docker Desktop で使えます。Linux の Docker Engine では、ホストの IP アドレス（例: `172.17.0.1`）を設定し、サーバーをすべてのインターフェースで待ち受けるように起動します。ホストの Ollama に接続できない場合も、`OLLAMA_HOST=0.0.0.0 ollama serve` で起動し直します。
