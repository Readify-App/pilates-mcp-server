# Pilates MCP Server

Claude Desktop用のピラティススタジオ情報MCPサーバーです。

## 特徴

- 非エンジニアでも1コマンドでインストール可能
- Claude Desktopに自動統合
- ピラティススタジオの情報を提供
  - スタジオ一覧の取得
  - スタジオ詳細情報の取得
  - エリアでの絞り込み
  - IDでの直接取得

## インストール方法

### macOS / Linux

ターミナルで以下のコマンドを実行してください:

```bash
curl -sSL https://raw.githubusercontent.com/Readify-App/pilates-mcp-server/main/install.sh | bash
```

### Windows

PowerShellで以下のコマンドを実行してください:

```powershell
irm https://raw.githubusercontent.com/Readify-App/pilates-mcp-server/main/install.ps1 | iex
```

## インストール後の手順

1. Claude Desktopを再起動
2. 🔨 アイコンが表示されることを確認
3. ピラティススタジオに関する質問を始める!

## 使用例

インストール後、以下のように質問できます:

```
渋谷のピラティススタジオを検索して
```

```
zen place pilatesの詳細を教えて
```

```
東京都のピラティススタジオを教えて
```

## 必要な環境

- Python 3.10以上
- Claude Desktop
- インターネット接続

## 利用可能なツール

### 1. `pilates_list`
ピラティススタジオの一覧を取得します。

**パラメータ:**
- `店舗名`: 検索したいスタジオ名（オプション）
- `エリア`: 検索したいエリア（オプション）
- `件数`: 取得件数（デフォルト: 20）

### 2. `pilates_detail`
特定のピラティススタジオの詳細情報を取得します。

**パラメータ:**
- `店舗名`: スタジオ名（必須）

### 3. `pilates_by_id`
投稿IDを指定してピラティススタジオの情報を取得します。

**パラメータ:**
- `投稿ID`: スタジオのID（必須）

### 4. `pilates_by_area`
エリア名でピラティススタジオを検索します。

**パラメータ:**
- `エリア`: エリア名（例: 東京都葛飾区、渋谷、新宿など）（必須）
- `件数`: 取得件数（デフォルト: 10）

## トラブルシューティング

### MCPサーバーが表示されない場合

設定ファイルを確認してください:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### インストールに失敗する場合

1. Python 3.10以上がインストールされているか確認
2. インターネット接続を確認
3. Claude Desktopが最新版か確認

## 開発者向け情報

### プロジェクト構造

```
pilates-mcp-server/
├── .gitignore           # 固定(ログファイル除外)
├── pyproject.toml       # 固定(パッケージ設定)
├── server.py            # ツール定義(メインロジック)← ここだけ編集
├── main.py              # 固定(エントリーポイント)
├── install.sh           # macOS/Linux自動インストーラー(固定)
├── install.ps1          # Windows自動インストーラー(固定)
└── README.md            # このファイル
```

### ローカル開発

```bash
# リポジトリをクローン
git clone https://github.com/Readify-App/pilates-mcp-server.git
cd pilates-mcp-server

# 依存関係をインストール
uv sync

# サーバーを実行
uv run pilates-mcp-server
```

### server.pyの編集

`server.py`のみを編集してツールの機能を追加・変更できます。他のファイルは固定です。

### データソース

このMCPサーバーは、以下のWordPress APIからデータを取得しています:
- サイト: https://plizgym.co.jp
- カスタム投稿タイプ: `pilates-studio`

## ライセンス

MIT License

## サポート

問題が発生した場合は、GitHubのIssuesで報告してください。
