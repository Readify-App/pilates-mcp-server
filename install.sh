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

# 1. uv のインストール確認
echo -e "${YELLOW}[1/5] uv のインストール確認中...${NC}"
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}uv がインストールされていません。インストールします...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
    echo -e "${GREEN}✓ uv をインストールしました${NC}"
else
    echo -e "${GREEN}✓ uv は既にインストールされています${NC}"
fi

# 2. Python のインストール確認
echo -e "${YELLOW}[2/5] Python 3.10+ の確認中...${NC}"
if ! uv python list | grep -q "3.1"; then
    echo -e "${YELLOW}Python 3.10+ をインストールします...${NC}"
    uv python install 3.12
    echo -e "${GREEN}✓ Python 3.12 をインストールしました${NC}"
else
    echo -e "${GREEN}✓ Python 3.10+ は既にインストールされています${NC}"
fi

# 3. MCPサーバーのクローン
INSTALL_DIR="$HOME/mcp-servers/${PACKAGE_NAME}"
echo -e "${YELLOW}[3/5] ${MCP_SERVER_TITLE} をダウンロード中...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}既存のインストールを削除します...${NC}"
    rm -rf "$INSTALL_DIR"
fi
mkdir -p "$HOME/mcp-servers"
git clone "https://github.com/${GITHUB_USER}/${GITHUB_REPO}.git" "$INSTALL_DIR"
cd "$INSTALL_DIR"
echo -e "${GREEN}✓ ダウンロード完了${NC}"

# 4. 依存関係のインストール
echo -e "${YELLOW}[4/5] 依存関係をインストール中...${NC}"
uv sync
echo -e "${GREEN}✓ 依存関係のインストール完了${NC}"

# 5. Claude Desktop設定の更新
echo -e "${YELLOW}[5/5] Claude Desktop の設定を更新中...${NC}"
mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_FILE" ]; then
    echo '{"mcpServers":{}}' > "$CONFIG_FILE"
fi

# jq を使って設定を更新
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}jq をインストールします...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install jq
    else
        sudo apt-get update && sudo apt-get install -y jq
    fi
fi

# 設定を追加
jq --arg key "$MCP_SERVER_KEY" \
   --arg dir "$INSTALL_DIR" \
   '.mcpServers[$key] = {
     "command": "uv",
     "args": ["--directory", $dir, "run", "'"$PACKAGE_NAME"'"]
   }' "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"

echo -e "${GREEN}✓ 設定ファイルを更新しました${NC}"
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
