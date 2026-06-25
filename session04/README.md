# 第4回：ReAct

## 前提条件

1. Git
2. 実行環境（いずれか）
   - ローカルの Python 3.10 以上 ＋ Jupyter（または **VS Code** Jupyter 拡張機能）
   - **Dev Containers**（Docker 利用。ローカル環境を汚したくない場合）
   - **Google Colab**

## 事前準備

### リポジトリのクローン

ローカルにリポジトリを取得します。任意の作業ディレクトリで以下を実行してください。

```bash
git clone https://github.com/cosmac-dev/ai-agent-seminar.git
cd ai-agent-seminar/session04
```

> 既にリポジトリをクローン済みの場合は、最新の状態に更新してください。
>
> ```bash
> cd ai-agent-seminar
> git pull
> ```

## Dev Container （任意）

ローカル環境を汚したくない場合は**Dev Container** を使用可能。

### Dev Container の前提条件

1. Docker
2. [Visual Studio Code](https://code.visualstudio.com/) / [Cursor](https://cursor.com/)
3. [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

### 起動手順

1. クローンした `ai-agent-seminar` フォルダを VS Code で開く
2. コマンドパレット（`F1` または `Ctrl`/`Cmd` + `Shift` + `P`）を開き、**Dev Containers: Reopen in Container** を実行する
3. 構成の選択を求められたら **ai-agent-seminar-session04** を選ぶ
4. 初回はコンテナのビルドと依存パッケージのインストール（`postCreateCommand`）が走るため、完了まで数分待つ

> コンテナは `session04` ディレクトリをワークスペースとして開く
