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

Dev Container の構成は 2 つあります（[リポジトリの README](../README.md#vs-codedev-container) を参照）。どちらのイメージも vLLM と Ollama を含まないため、ノートブックのセルでコンテナにインストールして使います。

| 構成 | 対象 | vLLM（A） | Ollama（B） |
| --- | --- | --- | --- |
| **ai-agent-seminar-session03 (NVIDIA GPU)** | NVIDIA GPU のあるマシン | コンテナにインストール | コンテナにインストール |
| **ai-agent-seminar-session03** | それ以外（Mac など） | コンテナでは実行不可（A-2 はホストのサーバーに接続可） | コンテナにインストール（CPU で動作） |

ノートブックの `INSTALL_VLLM`・`INSTALL_OLLAMA` を `True` にして実行します。どちらも数分かかり、vLLM はコンテナの容量がおよそ 3 GB 増えます。vLLM はインストール後にカーネルを再起動し、Ollama はターミナルで `ollama serve` を起動します。コンテナを作り直した場合はインストールし直します。

コンテナの外（ホストなど）で起動したサーバーに接続することもできます。ホストで環境変数 `LLM_SERVER_HOST`（A-2 の OpenAI 互換サーバー）・`OLLAMA_SERVER_HOST`（Ollama）に接続先のホスト名を設定してから、コンテナを作り直します。Docker Desktop では、ホストを `host.docker.internal` で指定できます。ポートとモデル名は、ノートブックのものに合わせてください。
