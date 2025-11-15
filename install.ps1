# ===== ここから変更 =====
$MCP_SERVER_TITLE = "Pilates MCP Server"
$MCP_SERVER_KEY = "pilates-mcp-server"
$GITHUB_USER = "Readify-App"
$GITHUB_REPO = "pilates-mcp-server"
$PACKAGE_NAME = "pilates-mcp-server"
$USAGE_EXAMPLE = "渋谷のピラティススタジオを検索して"
# ===== ここまで変更 =====

# 管理者権限チェック
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

Write-Host "================================================" -ForegroundColor Blue
Write-Host "$MCP_SERVER_TITLE - 自動インストーラー" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Blue
Write-Host ""

# 設定ファイルのパス
$CONFIG_DIR = "$env:APPDATA\Claude"
$CONFIG_FILE = "$CONFIG_DIR\claude_desktop_config.json"

# 1. uv のインストール確認
Write-Host "[1/5] uv のインストール確認中..." -ForegroundColor Yellow
try {
    $uvVersion = uv --version
    Write-Host "✓ uv は既にインストールされています ($uvVersion)" -ForegroundColor Green
} catch {
    Write-Host "uv がインストールされていません。インストールします..." -ForegroundColor Yellow
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
    Write-Host "✓ uv をインストールしました" -ForegroundColor Green
}

# 2. Python のインストール確認
Write-Host "[2/5] Python 3.10+ の確認中..." -ForegroundColor Yellow
$pythonList = uv python list 2>&1 | Out-String
if ($pythonList -match "3\.1[0-9]") {
    Write-Host "✓ Python 3.10+ は既にインストールされています" -ForegroundColor Green
} else {
    Write-Host "Python 3.12 をインストールします..." -ForegroundColor Yellow
    uv python install 3.12
    Write-Host "✓ Python 3.12 をインストールしました" -ForegroundColor Green
}

# 3. MCPサーバーのクローン
$INSTALL_DIR = "$env:USERPROFILE\mcp-servers\$PACKAGE_NAME"
Write-Host "[3/5] $MCP_SERVER_TITLE をダウンロード中..." -ForegroundColor Yellow

if (Test-Path $INSTALL_DIR) {
    Write-Host "既存のインストールを削除します..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $INSTALL_DIR
}

New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\mcp-servers" | Out-Null
git clone "https://github.com/$GITHUB_USER/$GITHUB_REPO.git" $INSTALL_DIR

if (-not (Test-Path $INSTALL_DIR)) {
    Write-Host "エラー: ダウンロードに失敗しました" -ForegroundColor Red
    exit 1
}

Set-Location $INSTALL_DIR
Write-Host "✓ ダウンロード完了" -ForegroundColor Green

# 4. 依存関係のインストール
Write-Host "[4/5] 依存関係をインストール中..." -ForegroundColor Yellow
uv sync
Write-Host "✓ 依存関係のインストール完了" -ForegroundColor Green

# 5. Claude Desktop設定の更新
Write-Host "[5/5] Claude Desktop の設定を更新中..." -ForegroundColor Yellow

if (-not (Test-Path $CONFIG_DIR)) {
    New-Item -ItemType Directory -Force -Path $CONFIG_DIR | Out-Null
}

if (-not (Test-Path $CONFIG_FILE)) {
    '{"mcpServers":{}}' | Out-File -FilePath $CONFIG_FILE -Encoding UTF8
}

# JSON設定を読み込み
$config = Get-Content $CONFIG_FILE -Raw | ConvertFrom-Json

# mcpServersオブジェクトが存在しない場合は作成
if (-not $config.mcpServers) {
    $config | Add-Member -MemberType NoteProperty -Name "mcpServers" -Value ([PSCustomObject]@{})
}

# サーバー設定を追加
$serverConfig = [PSCustomObject]@{
    command = "uv"
    args = @("--directory", $INSTALL_DIR, "run", $PACKAGE_NAME)
}

$config.mcpServers | Add-Member -MemberType NoteProperty -Name $MCP_SERVER_KEY -Value $serverConfig -Force

# JSON形式で保存
$config | ConvertTo-Json -Depth 10 | Out-File -FilePath $CONFIG_FILE -Encoding UTF8

Write-Host "✓ 設定ファイルを更新しました" -ForegroundColor Green
Write-Host ""
Write-Host "================================================" -ForegroundColor Blue
Write-Host "🎉 インストール完了！" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Blue
Write-Host ""
Write-Host "次のステップ:" -ForegroundColor Yellow
Write-Host "1. " -NoNewline
Write-Host "Claude Desktop アプリを再起動" -ForegroundColor Red -NoNewline
Write-Host "してください"
Write-Host "2. 再起動後、以下のように試してください:"
Write-Host "   「$USAGE_EXAMPLE」" -ForegroundColor Green
Write-Host ""
Write-Host "設定ファイルの場所:" -ForegroundColor Blue
Write-Host "   $CONFIG_FILE"
Write-Host ""
