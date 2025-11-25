# server.py
# ピラティススタジオ情報取得MCPサーバー

import httpx
import logging
import json
from mcp.server.fastmcp import FastMCP

# ログ設定
import os
import tempfile

# ログファイルのパスを取得（書き込み可能なディレクトリを使用）
log_dir = os.path.join(tempfile.gettempdir(), 'pilates-mcp-server')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'debug.log')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WordPress設定（直接指定）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WP_SITE_URL = "https://plizgym.co.jp"
WP_USERNAME = "admin"
WP_APP_PASSWORD = "QmMz beXP roCr 8qZP 6GqX 5KYT"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCPサーバー作成
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
mcp = FastMCP("pilates-mcp-server")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ヘルパー関数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_status_emoji(status: str) -> str:
    """ステータスに応じた絵文字を返す"""
    return {"publish": "🟢", "draft": "📝", "private": "🔒", "pending": "⏳"}.get(status, "❓")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ツール定義
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ========================================
# ツール1: スタジオリスト取得
# ========================================
@mcp.tool()
async def pilates_list(
    店舗名: str = "",
    エリア: str = "",
    件数: int = 20
) -> str:
    """
    ピラティススタジオの一覧を取得します（下書き含む）。
    店舗名やエリアで検索できます。
    """
    logger.info(f"pilates_list called with 店舗名={店舗名}, エリア={エリア}, 件数={件数}")
    
    async with httpx.AsyncClient() as client:
        try:
            auth = (WP_USERNAME, WP_APP_PASSWORD)
            
            search_query = 店舗名 or エリア or ""
            logger.debug(f"Search query: {search_query}")
            
            params = {
                "per_page": 件数,
                "status": "any"  # 下書き・公開・非公開すべて取得
            }
            
            if search_query:
                params["search"] = search_query
            
            response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/pilates-studio",
                params=params,
                auth=auth,
                timeout=30.0
            )
            
            logger.debug(f"Response status: {response.status_code}")
            
            # ステータスコードチェック
            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                logger.error(f"API Error: {response.status_code} - {error_data}")
                return f"APIエラーが発生しました: {error_data.get('message', 'Unknown error')}"
            
            stores = response.json()
            
            # レスポンスが配列でない場合のチェック
            if not isinstance(stores, list):
                logger.error(f"Unexpected response format: {type(stores)}")
                return f"予期しないレスポンス形式です"
            
            logger.debug(f"Found {len(stores)} stores")
            
            if not stores:
                return "該当するスタジオが見つかりませんでした。"
            
            result = f"🏢 ピラティススタジオ情報（{len(stores)}件）\n\n"
            
            for store in stores:
                status_emoji = get_status_emoji(store.get('status', ''))
                result += f"━━━━━━━━━━━━━━━━\n"
                result += f"{status_emoji} {store['title']['rendered']}\n"
                result += f"🆔 ID: {store['id']} | ステータス: {store.get('status', '不明')}\n"
                
                # カスタムフィールド取得
                if 'custom_fields' in store:
                    fields = store['custom_fields']
                    
                    # 簡易地区
                    if '簡易地区' in fields:
                        area = fields['簡易地区'][0] if isinstance(fields['簡易地区'], list) else fields['簡易地区']
                        result += f"📌 エリア: {area}\n"
                    
                    # 表用特徴
                    if '表用特徴' in fields:
                        feature = fields['表用特徴'][0] if isinstance(fields['表用特徴'], list) else fields['表用特徴']
                        result += f"✨ 特徴: {feature}\n"
                    
                    # 表用料金
                    if '表用料金' in fields:
                        price = fields['表用料金'][0] if isinstance(fields['表用料金'], list) else fields['表用料金']
                        result += f"💰 料金: {price}\n"
                
                result += f"🔗 {store['link']}\n\n"
            
            return result
        
        except Exception as e:
            logger.exception(f"Error in pilates_list: {e}")
            return f"エラーが発生しました: {str(e)}"


# ========================================
# ツール2: スタジオ詳細取得
# ========================================
@mcp.tool()
async def pilates_detail(店舗名: str) -> str:
    """
    特定のピラティススタジオの詳細情報をすべて取得します（下書き含む）。
    """
    logger.info(f"pilates_detail called with 店舗名={店舗名}")
    
    async with httpx.AsyncClient() as client:
        try:
            auth = (WP_USERNAME, WP_APP_PASSWORD)
            
            # 店舗を検索（下書き含む）
            logger.debug(f"Searching for store: {店舗名}")
            search_response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/pilates-studio",
                params={"search": 店舗名, "per_page": 1, "status": "any"},
                auth=auth,
                timeout=30.0
            )
            
            logger.debug(f"Search response status: {search_response.status_code}")
            
            # ステータスコードチェック
            if search_response.status_code != 200:
                error_data = search_response.json() if search_response.text else {}
                logger.error(f"Search API Error: {search_response.status_code} - {error_data}")
                return f"APIエラーが発生しました: {error_data.get('message', 'Unknown error')}"
            
            stores = search_response.json()
            
            # レスポンスが配列でない場合のチェック
            if not isinstance(stores, list):
                logger.error(f"Unexpected response format: {type(stores)}")
                return f"予期しないレスポンス形式です"
            
            logger.debug(f"Search results count: {len(stores)}")
            
            if not stores:
                logger.warning(f"No stores found for: {店舗名}")
                return f"「{店舗名}」が見つかりませんでした。"
            
            store_id = stores[0]['id']
            logger.info(f"Found store ID: {store_id}")
            
            # 詳細取得
            logger.debug(f"Fetching details for store ID: {store_id}")
            detail_response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/pilates-studio/{store_id}",
                auth=auth,
                timeout=30.0
            )
            
            logger.debug(f"Detail response status: {detail_response.status_code}")
            
            # ステータスコードをチェック
            if detail_response.status_code != 200:
                logger.error(f"HTTP error: {detail_response.status_code}")
                return f"エラーが発生しました: HTTPステータス {detail_response.status_code}"
            
            store = detail_response.json()
            logger.debug(f"Store data keys: {store.keys()}")
            
            # titleキーが存在するかチェック
            if 'title' not in store or 'rendered' not in store.get('title', {}):
                return f"データ形式が正しくありません。"
            
            status_emoji = get_status_emoji(store.get('status', ''))
            result = f"━━━━━━━━━━━━━━━━━━━━\n"
            result += f"{status_emoji} {store['title']['rendered']}\n"
            result += f"🆔 ID: {store['id']} | ステータス: {store.get('status', '不明')}\n"
            result += f"━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # 本文
            if store.get('content', {}).get('rendered'):
                import re
                content = store['content']['rendered']
                content = re.sub('<[^<]+?>', '', content)
                result += f"📝 説明:\n{content.strip()[:500]}...\n\n"
            
            # カスタムフィールド
            if 'custom_fields' in store:
                fields = store['custom_fields']
                
                # 基本情報
                result += "━━━ 📍 基本情報 ━━━\n\n"
                
                if '簡易地区' in fields:
                    area = fields['簡易地区'][0] if isinstance(fields['簡易地区'], list) else fields['簡易地区']
                    result += f"エリア: {area}\n"
                if '住所' in fields:
                    addr = fields['住所'][0] if isinstance(fields['住所'], list) else fields['住所']
                    result += f"住所: {addr}\n"
                if '営業時間' in fields:
                    hours = fields['営業時間'][0] if isinstance(fields['営業時間'], list) else fields['営業時間']
                    result += f"⏰ 営業時間: {hours}\n"
                if '定休日' in fields:
                    holiday = fields['定休日'][0] if isinstance(fields['定休日'], list) else fields['定休日']
                    result += f"🔒 定休日: {holiday}\n"
                if 'アクセス' in fields:
                    access = fields['アクセス'][0] if isinstance(fields['アクセス'], list) else fields['アクセス']
                    result += f"🚃 アクセス: {access}\n"
                if '駐車場' in fields:
                    parking = fields['駐車場'][0] if isinstance(fields['駐車場'], list) else fields['駐車場']
                    result += f"🅿️ 駐車場: {parking}\n"
                if '店舗公式サイト' in fields:
                    site = fields['店舗公式サイト'][0] if isinstance(fields['店舗公式サイト'], list) else fields['店舗公式サイト']
                    result += f"🌐 公式サイト: {site}\n"
                
                # 料金情報
                result += "\n━━━ 💰 料金情報 ━━━\n\n"
                
                if '初期費用' in fields:
                    init_cost = fields['初期費用'][0] if isinstance(fields['初期費用'], list) else fields['初期費用']
                    result += f"初期費用: {init_cost}\n"
                if '体験' in fields:
                    trial = fields['体験'][0] if isinstance(fields['体験'], list) else fields['体験']
                    result += f"✨ 体験: {trial}\n"
                if '表用料金' in fields:
                    price_summary = fields['表用料金'][0] if isinstance(fields['表用料金'], list) else fields['表用料金']
                    result += f"料金目安: {price_summary}\n"
                
                # レッスン情報
                result += "\n━━━ 🏃 レッスン情報 ━━━\n\n"
                
                if 'レッスン時間' in fields:
                    lesson_time = fields['レッスン時間'][0] if isinstance(fields['レッスン時間'], list) else fields['レッスン時間']
                    result += f"⏱️ レッスン時間: {lesson_time}\n"
                if 'レッスン方式' in fields:
                    lesson_type = fields['レッスン方式'][0] if isinstance(fields['レッスン方式'], list) else fields['レッスン方式']
                    result += f"📋 レッスン方式: {lesson_type}\n"
                if 'ジャンル' in fields:
                    genre = fields['ジャンル'][0] if isinstance(fields['ジャンル'], list) else fields['ジャンル']
                    result += f"🎯 ジャンル: {genre}\n"
                if '男性利用可否' in fields:
                    male = fields['男性利用可否'][0] if isinstance(fields['男性利用可否'], list) else fields['男性利用可否']
                    result += f"👨 男性利用: {male}\n"
                
                # キャンペーン情報
                if 'キャンペーン内容' in fields or 'キャンペーン期間' in fields:
                    result += "\n━━━ 🎉 キャンペーン情報 ━━━\n\n"
                    if 'キャンペーン期間' in fields:
                        period = fields['キャンペーン期間'][0] if isinstance(fields['キャンペーン期間'], list) else fields['キャンペーン期間']
                        result += f"期間: {period}\n"
                    if 'キャンペーン内容' in fields:
                        campaign = fields['キャンペーン内容'][0] if isinstance(fields['キャンペーン内容'], list) else fields['キャンペーン内容']
                        result += f"内容: {campaign}\n"
            
            result += f"\n🔗 詳細URL: {store['link']}\n"
            
            return result
        
        except Exception as e:
            logger.exception(f"Error in pilates_detail: {e}")
            return f"エラーが発生しました: {str(e)}"


# ========================================
# ツール3: IDで直接取得
# ========================================
@mcp.tool()
async def pilates_by_id(投稿ID: int) -> str:
    """
    投稿IDを指定してピラティススタジオの情報を取得します（下書き含む）。
    """
    logger.info(f"pilates_by_id called with ID={投稿ID}")
    
    async with httpx.AsyncClient() as client:
        try:
            auth = (WP_USERNAME, WP_APP_PASSWORD)
            
            logger.debug(f"Fetching pilates studio with ID: {投稿ID}")
            response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/pilates-studio/{投稿ID}",
                auth=auth,
                timeout=30.0
            )
            
            logger.debug(f"Response status: {response.status_code}")
            
            # ステータスコードをチェック
            if response.status_code == 404:
                return f"ID {投稿ID} のスタジオが見つかりませんでした。"
            
            if response.status_code != 200:
                return f"エラーが発生しました: HTTPステータス {response.status_code}"
            
            store = response.json()
            
            # titleキーが存在するかチェック
            if 'title' not in store or 'rendered' not in store.get('title', {}):
                return f"ID {投稿ID} のデータ形式が正しくありません。レスポンス: {store}"
            
            status_emoji = get_status_emoji(store.get('status', ''))
            result = f"━━━━━━━━━━━━━━━━━━━━\n"
            result += f"{status_emoji} {store['title']['rendered']}\n"
            result += f"🆔 ID: {store['id']} | ステータス: {store.get('status', '不明')}\n"
            result += f"━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # カスタムフィールドをすべて表示
            if 'custom_fields' in store:
                result += "【すべてのカスタムフィールド】\n\n"
                fields = store['custom_fields']
                
                for key, value in fields.items():
                    if not key.startswith('_'):  # 内部フィールドを除外
                        val = value[0] if isinstance(value, list) and value else value
                        result += f"{key}: {val}\n"
            
            result += f"\n🔗 {store['link']}\n"
            
            return result
        
        except Exception as e:
            logger.exception(f"Error in pilates_by_id: {e}")
            return f"エラーが発生しました: {str(e)}"


# ========================================
# ツール4: エリアで絞り込み
# ========================================
@mcp.tool()
async def pilates_by_area(エリア: str, 件数: int = 10) -> str:
    """
    エリア名でピラティススタジオを検索します（下書き含む）。
    例: 東京都葛飾区、渋谷、新宿など
    """
    logger.info(f"pilates_by_area called with エリア={エリア}, 件数={件数}")
    
    async with httpx.AsyncClient() as client:
        try:
            auth = (WP_USERNAME, WP_APP_PASSWORD)
            
            # 全件取得してカスタムフィールドでフィルタリング（下書き含む）
            logger.debug("Fetching all stores for area filtering")
            response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/pilates-studio",
                params={"per_page": 100, "status": "any"},
                auth=auth,
                timeout=30.0
            )
            
            logger.debug(f"Response status: {response.status_code}")
            
            # ステータスコードチェック
            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                logger.error(f"API Error: {response.status_code} - {error_data}")
                return f"APIエラーが発生しました: {error_data.get('message', 'Unknown error')}"
            
            all_stores = response.json()
            
            # レスポンスが配列でない場合のチェック
            if not isinstance(all_stores, list):
                logger.error(f"Unexpected response format: {type(all_stores)}")
                return f"予期しないレスポンス形式です"
            
            logger.debug(f"Total stores fetched: {len(all_stores)}")
            
            # エリアでフィルタリング
            logger.debug(f"Filtering stores by area: {エリア}")
            filtered = []
            for store in all_stores:
                if 'custom_fields' in store:
                    fields = store['custom_fields']
                    if '簡易地区' in fields:
                        area = fields['簡易地区'][0] if isinstance(fields['簡易地区'], list) else fields['簡易地区']
                        if エリア in area:
                            filtered.append(store)
                            logger.debug(f"Matched store: {store.get('title', {}).get('rendered', 'Unknown')}")
            
            logger.info(f"Filtered {len(filtered)} stores for area: {エリア}")
            
            if not filtered:
                logger.warning(f"No stores found for area: {エリア}")
                return f"「{エリア}」のスタジオが見つかりませんでした。"
            
            # 指定件数まで
            filtered = filtered[:件数]
            
            result = f"🏢 {エリア}のピラティススタジオ（{len(filtered)}件）\n\n"
            
            for store in filtered:
                status_emoji = get_status_emoji(store.get('status', ''))
                result += f"━━━━━━━━━━━━━━━━\n"
                result += f"{status_emoji} {store['title']['rendered']}\n"
                result += f"🆔 ID: {store['id']} | ステータス: {store.get('status', '不明')}\n"
                
                if 'custom_fields' in store:
                    fields = store['custom_fields']
                    
                    if '住所' in fields:
                        addr = fields['住所'][0] if isinstance(fields['住所'], list) else fields['住所']
                        result += f"住所: {addr}\n"
                    
                    if '表用料金' in fields:
                        price = fields['表用料金'][0] if isinstance(fields['表用料金'], list) else fields['表用料金']
                        result += f"💰 {price}\n"
                
                result += f"🔗 {store['link']}\n\n"
            
            return result
        
        except Exception as e:
            logger.exception(f"Error in pilates_by_area: {e}")
            return f"エラーが発生しました: {str(e)}"


# ========================================
# ツール5: カスタムフィールドを更新
# ========================================
@mcp.tool()
async def pilates_update(
    投稿ID: int,
    フィールド名: str,
    新しい値: str
) -> str:
    """
    ピラティススタジオのカスタムフィールドを更新します。
    
    対応フィールド例:
    - 表用特徴, 表用料金, 表用アクセス
    - 簡易地区, 住所, 営業時間, 定休日, アクセス, 駐車場, 店舗公式サイト
    - 初期費用, 体験, レッスン時間
    - キャンペーン期間, キャンペーン内容
    - AFF_URL, 目次, ボタン名
    """
    logger.info(f"pilates_update called with ID={投稿ID}, field={フィールド名}")
    
    async with httpx.AsyncClient() as client:
        try:
            auth = (WP_USERNAME, WP_APP_PASSWORD)
            
            # POSTリクエストで更新
            response = await client.post(
                f"{WP_SITE_URL}/wp-json/wp/v2/pilates-studio/{投稿ID}",
                auth=auth,
                json={
                    "custom_fields": {
                        フィールド名: 新しい値
                    }
                },
                timeout=30.0
            )
            
            logger.debug(f"Update response status: {response.status_code}")
            
            if response.status_code == 200:
                store = response.json()
                return f"✅ 更新成功！\n\n投稿ID: {投稿ID}\nタイトル: {store['title']['rendered']}\n\n更新内容:\n  {フィールド名}: {新しい値}"
            else:
                error = response.json()
                logger.error(f"Update failed: {error}")
                return f"❌ 更新失敗\n\nエラー: {error.get('message', error)}"
        
        except Exception as e:
            logger.exception(f"Error in pilates_update: {e}")
            return f"エラーが発生しました: {str(e)}"


# ========================================
# ツール6: 複数フィールドを一括更新
# ========================================
@mcp.tool()
async def pilates_update_multiple(
    投稿ID: int,
    更新データJSON: str
) -> str:
    """
    複数のカスタムフィールドを一括更新します。
    
    更新データJSONの形式:
    {"簡易地区": "東京都渋谷区", "表用料金": "月額10,000円〜"}
    """
    logger.info(f"pilates_update_multiple called with ID={投稿ID}")
    
    try:
        data = json.loads(更新データJSON)
    except json.JSONDecodeError as e:
        return f"❌ JSONの形式が正しくありません\n\nエラー: {str(e)}\n\n正しい形式の例:\n{{\"簡易地区\": \"東京都渋谷区\", \"表用料金\": \"月額10,000円〜\"}}"
    
    async with httpx.AsyncClient() as client:
        try:
            auth = (WP_USERNAME, WP_APP_PASSWORD)
            
            response = await client.post(
                f"{WP_SITE_URL}/wp-json/wp/v2/pilates-studio/{投稿ID}",
                auth=auth,
                json={"custom_fields": data},
                timeout=30.0
            )
            
            logger.debug(f"Update response status: {response.status_code}")
            
            if response.status_code == 200:
                store = response.json()
                result = f"✅ 更新成功！\n\n投稿ID: {投稿ID}\nタイトル: {store['title']['rendered']}\n\n更新内容:\n"
                for key, value in data.items():
                    result += f"  • {key}: {value}\n"
                return result
            else:
                error = response.json()
                logger.error(f"Update failed: {error}")
                return f"❌ 更新失敗\n\nエラー: {error.get('message', error)}"
        
        except Exception as e:
            logger.exception(f"Error in pilates_update_multiple: {e}")
            return f"エラーが発生しました: {str(e)}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# サーバー起動
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
