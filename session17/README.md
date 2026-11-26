# 第17回: Computer Use

## 前提条件

1. Git
2. 実行環境（いずれか）
   - **Dev Containers**（Docker 利用。推奨）
   - ローカルの Python 3.10 以上 ＋ Jupyter（または **VS Code** Jupyter 拡張機能）＋ Docker
3. OpenAI の API キー（`OPENAI_API_KEY`）

本回は Docker コンテナの中で仮想デスクトップを動かすため、Docker が必要。Google Colab では実行できない。

本回では、Docker コンテナの中の Linux のデスクトップ（Xvfb + Xfce）を操作するエージェントを、2つの方式で実装する。

- スクリーンショット方式: OpenAI の computer tool。スクリーンショットを見たモデルが、座標でクリックやキー入力を指示する。エージェントは OpenAI Agents SDK で作る。
- アクセシビリティツリー方式: Linux のアクセシビリティの仕組み（AT-SPI）で画面の要素をテキストにして渡し、モデルが要素を指定する。エージェントは LangChain で作る。

Notebook の実行は OpenAI のモデル（computer tool は `gpt-5.5`、アクセシビリティツリーは `gpt-5.4-mini`）を使うため、利用料金が発生する。

## 事前準備

### リポジトリのクローン

```bash
git clone https://github.com/cosmac-dev/ai-agent-seminar.git
cd ai-agent-seminar/session17
```

既にクローン済みの場合は、ローカルの変更を保全して最新の教材に更新し、本回のディレクトリへ移動する。

### Notebook の実行

- Dev Container: VS Codeでリポジトリを開き、**Dev Containers: Reopen in Container** から `ai-agent-seminar-session17` を選ぶ。[専用設定](../.devcontainer/session17/devcontainer.json)が完成版パッケージと OpenAI Agents SDK を導入し、仮想デスクトップのコンテナを起動するためにホストの Docker ソケットを共有する。
- ローカル: Python 3.10 以上の Jupyter カーネルを選び、`session17/` をカレントディレクトリとして上から順にセルを実行する。Notebook のセットアップセルが `openai`・`openai-agents`・`langchain`・`langchain-openai` を導入する。Docker を起動しておく。

API キーは Notebook の入力欄、または環境変数 `OPENAI_API_KEY` で設定する。キーをコード・出力・Git に保存しない。

Notebook 内ではトップレベルの `await` を使用する。`asyncio.run` は通常の Python スクリプトで使用する。
Windows では Dev Container を推奨する（Docker のコマンドを非同期のサブプロセスで実行するため）。

## Notebook

- [`session17_computer_use.ipynb`](session17_computer_use.ipynb)

## ディレクトリ構成

| ファイル・ディレクトリ | 役割 |
| --- | --- |
| [`session17_computer_use.ipynb`](session17_computer_use.ipynb) | 概念の解説とハンズオン。仮想デスクトップは `desktop/` から作る |
| [`src/computer_use_agent/`](src/computer_use_agent/) | Notebook の完成版実装 |
| [`desktop/`](desktop/) | 仮想デスクトップのイメージ（`Dockerfile`、起動スクリプト、AT-SPI で要素を読むスクリプト、作業用のファイル） |
| [`tests/`](tests/) | OpenAI API を使わない回帰テスト |

## 仮想デスクトップ

仮想デスクトップでは、ファイルマネージャ（Thunar）とテキストエディタ（Mousepad）が開いている。
エージェントは「受信」フォルダの領収書を読み、経費一覧（`経費一覧.csv`）に1行追加して保存し、領収書を「処理済み」フォルダに移す。

操作はすべて、ホストから `docker exec` でコンテナの中のコマンドを実行して行う。

| 役割 | コマンド |
| --- | --- |
| 画面を撮る | ImageMagick の `import` |
| 入力する | `xdotool` |
| 画面の要素を読む | `a11y`（[`desktop/a11y.py`](desktop/a11y.py)。AT-SPI でアクセシビリティツリーを読む） |

エージェントはコンテナの中の画面だけを操作し、ホストの画面や入力デバイスには触れない。コンテナは次の設定で起動する。

- `--network none`（外部ネットワークに出られない）
- `--cap-drop ALL`、`--security-opt no-new-privileges`（特権を持たない）
- `--memory 2g`、`--pids-limit 512`（使える資源を制限する）
- ホストのファイルと Docker ソケットをマウントしない

イメージはおよそ 700 MB で、初回のビルドには数分かかる。Notebook のセルがビルドする。手動で作る場合は `session17/` で次を実行する。

```bash
docker build -f desktop/Dockerfile -t ai-agent-seminar-desktop:17 .
```

## パッケージ: `computer-use-agent`

`src/computer_use_agent` は Notebook の完成版実装。Notebook では実装を省いた、取り消しにくい操作の前の確認（`guard.py`）と、人への引き継ぎ（`__main__.py`）も含む。別セッションを import しない。
依存パッケージは `openai`、`openai-agents`、`langchain`、`langchain-openai`。仮想デスクトップの操作には Docker を使う。

```bash
python -m pip install -e .
```

完成版デモは次のコマンドで実行できる。保存の前で止めて人に引き継ぎ、保存と移動の直前にも端末で確認を求める。

```bash
python -m computer_use_agent --build          # スクリーンショット方式（computer tool × Agents SDK）で操作。初回はイメージを作る
python -m computer_use_agent --method a11y    # アクセシビリティツリー方式（AT-SPI × LangChain）で操作
```

`--model` でモデルを指定できる（既定は、computer tool が `gpt-5.5`、アクセシビリティツリーが `gpt-5.4-mini`）。

## テスト

OpenAI API を呼ばず、操作を記録するだけの偽の仮想デスクトップで、Agents SDK 用の `AsyncComputer`、LangChain 用の Tool、ガードを確かめる。
仮想デスクトップを使うテストは、Docker と仮想デスクトップのイメージが必要（ない場合はスキップする）。

```bash
python -m pip install -e ".[test]"
python -m pytest tests
```
