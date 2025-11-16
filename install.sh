#!/bin/bash
set -e

# ===== ここから変更 =====
MCP_SERVER_TITLE="Pilates MCP Server"
MCP_SERVER_KEY="pilates-mcp-server"
GITHUB_USER="Readify-App"
GITHUB_REPO="pilates-mcp-server"
PACKAGE_NAME="pilates-mcp-server"
USAGE_EXAMPLE="渋谷のピラティススタジオを検索して"
# ===== ここまで変更 =====

# 色の定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}${MCP_SERVER_TITLE} - 自動インストーラー${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# OS判定
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/Claude"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    CONFIG_DIR="$HOME/.config/claude-desktop"
else
    echo -e "${RED}エラー: サポートされていないOSです${NC}"
    exit 1
fi

CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"

# 必要なコマンドの確認
echo -e "${YELLOW}[0/5] 必要なコマンドの確認中...${NC}"

# curl の確認
if ! command -v curl &> /dev/null; then
    echo -e "${RED}エラー: curl がインストールされていません${NC}"
    echo -e "${YELLOW}macOS の場合: curl は通常プリインストールされています${NC}"
    exit 1
fi

# git の確認
if ! command -v git &> /dev/null; then
    echo -e "${RED}エラー: git がインストールされていません${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "${YELLOW}以下のコマンドでインストールしてください:${NC}"
        echo -e "  xcode-select --install"
    else
        echo -e "${YELLOW}以下のコマンドでインストールしてください:${NC}"
        echo -e "  sudo apt-get install git"
    fi
    exit 1
fi

# ネットワーク接続の確認（オプション）
echo -e "${YELLOW}ネットワーク接続を確認中...${NC}"
if ! curl -s --max-time 5 https://github.com > /dev/null 2>&1; then
    echo -e "${YELLOW}警告: インターネット接続を確認できませんでした${NC}"
    echo -e "${YELLOW}続行しますが、ダウンロードが失敗する可能性があります${NC}"
else
    echo -e "${GREEN}✓ ネットワーク接続を確認しました${NC}"
fi

echo -e "${GREEN}✓ 必要なコマンドが揃っています${NC}"
echo ""

# 1. uv のインストール確認
echo -e "${YELLOW}[1/5] uv のインストール確認中...${NC}"
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}uv がインストールされていません。インストールします...${NC}"
    if curl -LsSf https://astral.sh/uv/install.sh | sh; then
        export PATH="$HOME/.cargo/bin:$PATH"
        # PATHを確実に反映させるため、再度確認
        if command -v uv &> /dev/null; then
            echo -e "${GREEN}✓ uv をインストールしました${NC}"
        else
            # まだ見つからない場合は、シェルの設定ファイルに追加を促す
            echo -e "${YELLOW}uv がインストールされましたが、PATH に追加する必要があります${NC}"
            echo -e "${YELLOW}以下のコマンドを実行してから、再度このスクリプトを実行してください:${NC}"
            echo -e "  export PATH=\"\$HOME/.cargo/bin:\$PATH\""
            echo -e "${YELLOW}または、~/.zshrc に以下を追加してください:${NC}"
            echo -e "  export PATH=\"\$HOME/.cargo/bin:\$PATH\""
            exit 1
        fi
    else
        echo -e "${RED}エラー: uv のインストールに失敗しました${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ uv は既にインストールされています${NC}"
fi

# 2. Python のインストール確認
echo -e "${YELLOW}[2/5] Python 3.10+ の確認中...${NC}"
if uv python list 2>/dev/null | grep -q "3.1"; then
    echo -e "${GREEN}✓ Python 3.10+ は既にインストールされています${NC}"
else
    echo -e "${YELLOW}Python 3.10+ をインストールします...${NC}"
    if uv python install 3.12; then
        echo -e "${GREEN}✓ Python 3.12 をインストールしました${NC}"
    else
        echo -e "${RED}エラー: Python 3.12 のインストールに失敗しました${NC}"
        exit 1
    fi
fi

# 3. MCPサーバーのクローン
INSTALL_DIR="$HOME/mcp-servers/${PACKAGE_NAME}"
echo -e "${YELLOW}[3/5] ${MCP_SERVER_TITLE} をダウンロード中...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}既存のインストールを削除します...${NC}"
    rm -rf "$INSTALL_DIR"
fi
mkdir -p "$HOME/mcp-servers"
if git clone "https://github.com/${GITHUB_USER}/${GITHUB_REPO}.git" "$INSTALL_DIR"; then
    cd "$INSTALL_DIR" || {
        echo -e "${RED}エラー: ダウンロードしたディレクトリに移動できませんでした${NC}"
        exit 1
    }
    echo -e "${GREEN}✓ ダウンロード完了${NC}"
else
    echo -e "${RED}エラー: リポジトリのダウンロードに失敗しました${NC}"
    echo -e "${YELLOW}インターネット接続を確認してください${NC}"
    exit 1
fi

# 4. 依存関係のインストール
echo -e "${YELLOW}[4/5] 依存関係をインストール中...${NC}"
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}エラー: pyproject.toml が見つかりません${NC}"
    echo -e "${YELLOW}リポジトリのダウンロードに問題がある可能性があります${NC}"
    exit 1
fi
if uv sync; then
    echo -e "${GREEN}✓ 依存関係のインストール完了${NC}"
else
    echo -e "${RED}エラー: 依存関係のインストールに失敗しました${NC}"
    echo -e "${YELLOW}インターネット接続と pyproject.toml の内容を確認してください${NC}"
    exit 1
fi

# 5. Claude Desktop設定の更新
echo -e "${YELLOW}[5/5] Claude Desktop の設定を更新中...${NC}"

# 設定ディレクトリの作成と権限確認
if ! mkdir -p "$CONFIG_DIR"; then
    echo -e "${RED}エラー: 設定ディレクトリの作成に失敗しました${NC}"
    echo -e "${YELLOW}パス: $CONFIG_DIR${NC}"
    exit 1
fi

# 設定ファイルのバックアップ（既存の場合）
if [ -f "$CONFIG_FILE" ]; then
    BACKUP_FILE="${CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    if cp "$CONFIG_FILE" "$BACKUP_FILE" 2>/dev/null; then
        echo -e "${YELLOW}既存の設定ファイルをバックアップしました: $(basename "$BACKUP_FILE")${NC}"
    fi
else
    echo '{"mcpServers":{}}' > "$CONFIG_FILE"
    if [ ! -f "$CONFIG_FILE" ]; then
        echo -e "${RED}エラー: 設定ファイルの作成に失敗しました${NC}"
        echo -e "${YELLOW}書き込み権限を確認してください${NC}"
        exit 1
    fi
fi

# jq を使って設定を更新
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}jq をインストールします...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if ! command -v brew &> /dev/null; then
            echo -e "${RED}エラー: Homebrew がインストールされていません${NC}"
            echo -e "${YELLOW}以下のコマンドでインストールしてください:${NC}"
            echo -e "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            exit 1
        fi
        if brew install jq; then
            echo -e "${GREEN}✓ jq をインストールしました${NC}"
        else
            echo -e "${RED}エラー: jq のインストールに失敗しました${NC}"
            exit 1
        fi
    else
        if sudo apt-get update && sudo apt-get install -y jq; then
            echo -e "${GREEN}✓ jq をインストールしました${NC}"
        else
            echo -e "${RED}エラー: jq のインストールに失敗しました${NC}"
            exit 1
        fi
    fi
    # インストール後、再度確認
    if ! command -v jq &> /dev/null; then
        echo -e "${RED}エラー: jq のインストール後もコマンドが見つかりません${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ jq は既にインストールされています${NC}"
fi

# uv のフルパスを取得（Claude Desktopの環境変数にPATHが含まれていない場合に備える）
UV_PATH="uv"
if command -v uv &> /dev/null; then
    UV_PATH=$(command -v uv)
else
    # 通常のインストール場所を確認
    if [ -f "$HOME/.cargo/bin/uv" ]; then
        UV_PATH="$HOME/.cargo/bin/uv"
    else
        echo -e "${YELLOW}警告: uv のパスを自動検出できませんでした。'uv' を使用します${NC}"
        echo -e "${YELLOW}Claude Desktop の環境変数に PATH が設定されていることを確認してください${NC}"
    fi
fi

# 既存の設定を確認（デバッグ用）
if jq -e ".mcpServers[\"$MCP_SERVER_KEY\"]" "$CONFIG_FILE" > /dev/null 2>&1; then
    echo -e "${YELLOW}既存の設定を確認中...${NC}"
    EXISTING_DIR=$(jq -r ".mcpServers[\"$MCP_SERVER_KEY\"].args[1] // empty" "$CONFIG_FILE" 2>/dev/null)
    if [ -n "$EXISTING_DIR" ] && [ "$EXISTING_DIR" != "$INSTALL_DIR" ]; then
        echo -e "${YELLOW}既存の設定で間違ったディレクトリパスが検出されました${NC}"
        echo -e "${YELLOW}  現在: $EXISTING_DIR${NC}"
        echo -e "${YELLOW}  正しい: $INSTALL_DIR${NC}"
        echo -e "${YELLOW}設定を更新します...${NC}"
    fi
fi

# 設定を追加（既存の設定がある場合は上書き）
# jqでJSON文字列として正しくエスケープするため、--arg を使用
if jq --arg key "$MCP_SERVER_KEY" \
   --arg uv_path "$UV_PATH" \
   --arg dir "$INSTALL_DIR" \
   --arg pkg "$PACKAGE_NAME" \
   '.mcpServers[$key] = {
     "command": $uv_path,
     "args": ["--directory", $dir, "run", $pkg]
   }' "$CONFIG_FILE" > "$CONFIG_FILE.tmp" 2>/dev/null; then
    if mv "$CONFIG_FILE.tmp" "$CONFIG_FILE" 2>/dev/null; then
        # 設定ファイルの内容を検証
        if jq -e ".mcpServers[\"$MCP_SERVER_KEY\"]" "$CONFIG_FILE" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ 設定ファイルを更新しました${NC}"
            # 生成された設定を表示（デバッグ用）
            echo -e "${BLUE}生成された設定:${NC}"
            jq ".mcpServers[\"$MCP_SERVER_KEY\"]" "$CONFIG_FILE" 2>/dev/null | sed 's/^/  /'
        else
            echo -e "${RED}エラー: 設定が正しく追加されていません${NC}"
            exit 1
        fi
    else
        echo -e "${RED}エラー: 設定ファイルの保存に失敗しました${NC}"
        rm -f "$CONFIG_FILE.tmp"
        exit 1
    fi
else
    echo -e "${RED}エラー: 設定ファイルの更新に失敗しました${NC}"
    echo -e "${YELLOW}JSON ファイルの形式を確認してください${NC}"
    rm -f "$CONFIG_FILE.tmp"
    exit 1
fi
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}🎉 インストール完了！${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "${YELLOW}次のステップ:${NC}"
echo -e "1. ${RED}Claude Desktop アプリを再起動${NC}してください"
echo -e "2. 再起動後、以下のように試してください:"
echo -e "   ${GREEN}「${USAGE_EXAMPLE}」${NC}"
echo ""
echo -e "${BLUE}設定ファイルの場所:${NC}"
echo -e "   $CONFIG_FILE"
echo ""
