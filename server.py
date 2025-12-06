# server.py
# ピラティススタジオ情報取得MCPサーバー

import httpx
import logging
import json
import base64
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
WP_USERNAME = "admin@plizgym.co.jp"
WP_APP_PASSWORD = "SDVb bgJk W4zh okVe ruBh GvDy"
WP_POST_TYPE = "pilates-studio"
ALLOWED_STATUSES = ["publish", "draft"]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 認証ヘッダーを生成（WordPress REST API用）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_auth_headers():
    """
    WordPress REST API用のBasic認証ヘッダーを生成
    参考: https://developer.wordpress.org/rest-api/using-the-rest-api/authentication/
    """
    credentials = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    token = base64.b64encode(credentials.encode()).decode('utf-8')
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json"
    }

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


def _build_status_param(arg: str | None = None) -> str:
    """
    ステータスパラメータを構築する。
    指定がない場合はデフォルトで publish,draft を返す。
    """
    if not arg:
        return ",".join(ALLOWED_STATUSES)
    
    tokens = [token.strip().lower() for token in arg.split(",") if token.strip()]
    selected = [token for token in tokens if token in ALLOWED_STATUSES]
    
    if not selected:
        selected = ALLOWED_STATUSES.copy()
    
    # 重複除去（順序保持）
    ordered_unique: list[str] = []
    for status in selected:
        if status not in ordered_unique:
            ordered_unique.append(status)
    
    return ",".join(ordered_unique)


def _get_custom_fields_from_post(post_data: dict) -> dict:
    """
    投稿データからカスタムフィールドを取得する。
    WordPress REST APIでは、カスタムフィールドは以下のいずれかの形式で返される：
    1. `meta`キー内（従来の方法）
    2. `custom_fields`キー内（一部のプラグイン）
    3. ルートレベルに直接（register_post_meta()でshow_in_rest => trueを設定した場合）
    
    すべてをチェックして、存在するものを統合して返す。
    """
    result = {}
    
    # 1. custom_fieldsをチェック（一部のプラグインが使用）
    if 'custom_fields' in post_data and post_data['custom_fields']:
        logger.debug(f"Found custom_fields with {len(post_data['custom_fields'])} fields")
        result.update(post_data['custom_fields'])
    
    # 2. metaをチェック（WordPress標準）
    if 'meta' in post_data and post_data['meta']:
        logger.debug(f"Found meta with {len(post_data['meta'])} fields")
        result.update(post_data['meta'])
    
    # 3. ルートレベルからカスタムフィールドを抽出
    # register_post_meta()でshow_in_rest => trueを設定したフィールドはルートレベルに直接含まれる
    known_custom_fields = [
        # 表用情報
        '表用特徴', '表用料金', '表用アクセス',
        # 基本情報
        '簡易地区', '住所', '営業時間', '定休日', 'アクセス', '駐車場', '店舗公式サイト',
        # 料金系情報
        'h4料金プラン直下', '初期費用', '体験', '価格',
        # レッスン情報
        'レッスン時間', 'レッスン方式', 'ジャンル', '取材体験済', '男性利用可否',
        # 広告強化施策
        'AFF_URL', '目次', 'ボタン名',
        # 画像類
        '画像_説明付',
        # キャンペーン情報
        'キャンペーン期間', 'キャンペーン内容',
        # 関連記事
        '関連記事', '体験_ユーチューブ',
    ]
    
    # 標準的なWordPress REST APIのキー（カスタムフィールドではない）
    standard_keys = {
        'id', 'date', 'date_gmt', 'guid', 'modified', 'modified_gmt', 'slug', 'status',
        'type', 'link', 'title', 'content', 'excerpt', 'author', 'featured_media',
        'comment_status', 'ping_status', 'sticky', 'template', 'format', 'meta',
        'categories', 'tags', 'custom_fields', 'yoast_head', 'yoast_head_json',
        '_links', 'acf', 'jetpack_featured_media_url', 'jetpack_shortlink',
        'jetpack_sharing_enabled', 'jetpack_likes_enabled', 'publicize_connections',
        'featured_image', 'permalink_template', 'generated_slug', 'parent',
        'menu_order', 'taxonomy', 'description', 'count', 'name', 'slug',
        'taxonomy', 'term_group', 'term_taxonomy_id', 'term_id', 'filter',
        'rendered', 'protected', 'raw'
    }
    
    # ルートレベルからカスタムフィールドを抽出
    for key, value in post_data.items():
        # 標準キーでなく、既知のカスタムフィールド名と一致する場合
        if key not in standard_keys and (key in known_custom_fields or not key.startswith('_')):
            # まだresultに含まれていない場合のみ追加
            if key not in result:
                result[key] = value
                logger.debug(f"Found custom field at root level: {key}")
    
    if result:
        logger.debug(f"Total custom fields found: {len(result)}")
        return result
    
    # どちらも存在しない場合
    logger.debug("No custom_fields or meta found in post data")
    logger.debug(f"Available keys in post data: {list(post_data.keys())}")
    return {}


def _format_fields_for_display(fields: dict, include_internal: bool = False) -> str:
    """
    カスタムフィールドを表示用にフォーマットする。
    完全な構造（ネストされた配列など）を保持する。
    """
    if not fields:
        return "カスタムフィールドが見つかりませんでした。"
    
    result = "【カスタムフィールド（完全な構造）】\n\n"
    
    for key, value in fields.items():
        if not include_internal and key.startswith('_'):
            continue
        
        # 完全な構造をJSON形式で表示
        try:
            formatted_value = json.dumps(value, ensure_ascii=False, indent=2)
            result += f"{key}:\n{formatted_value}\n\n"
        except Exception as e:
            # JSON化できない場合は文字列として表示
            result += f"{key}: {str(value)}\n\n"
    
    return result

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
    件数: int = 20,
    status: str = "publish,draft"
) -> str:
    """
    ピラティススタジオの一覧を取得します（下書き含む）。
    店舗名やエリアで検索できます。
    WordPress 管理画面と同等の情報を取得できます。
    
    Args:
        店舗名: 店舗名で検索
        エリア: エリアで検索
        件数: 取得件数 (1-100)
        status: 取得する投稿ステータス（例: "publish", "draft", "publish,draft"）
    """
    logger.info(f"pilates_list called with 店舗名={店舗名}, エリア={エリア}, 件数={件数}, status={status}")
    
    async with httpx.AsyncClient() as client:
        try:
            headers = get_auth_headers()
            
            search_query = 店舗名 or エリア or ""
            logger.debug(f"Search query: {search_query}")
            
            params = {
                "per_page": min(max(件数, 1), 100),
                "context": "edit",  # 編集コンテキストで下書きも取得可能に
                "status": _build_status_param(status)  # カンマ区切りで複数ステータスを指定可能
            }
            
            if search_query:
                params["search"] = search_query
            
            response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/{WP_POST_TYPE}",
                params=params,
                headers=headers,
                timeout=30.0
            )
            
            logger.debug(f"Response status: {response.status_code}")
            
            # 権限エラーの場合はcontext=editを削除して再試行
            if response.status_code in (401, 403) or (response.status_code != 200 and ("権限" in str(response.text) or "rest_forbidden" in str(response.text))):
                logger.warning("context=editで権限エラーが発生。context=editなしで再試行します。")
                params.pop("context", None)
                # statusパラメータも削除（権限がない場合は公開済みのみ取得）
                params.pop("status", None)
                response = await client.get(
                    f"{WP_SITE_URL}/wp-json/wp/v2/{WP_POST_TYPE}",
                    params=params,
                    headers=headers,
                    timeout=30.0
                )
            
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
async def pilates_detail(店舗名: str, status: str = "publish,draft") -> str:
    """
    特定のピラティススタジオの詳細情報をすべて取得します（下書き含む）。
    WordPress 管理画面と同等の情報を取得できます。
    
    Args:
        店舗名: 検索する店舗名
        status: 取得する投稿ステータス（例: "publish", "draft", "publish,draft"）
    """
    logger.info(f"pilates_detail called with 店舗名={店舗名}, status={status}")
    
    async with httpx.AsyncClient() as client:
        try:
            headers = get_auth_headers()
            
            # 店舗を検索（下書き含む）
            logger.debug(f"Searching for store: {店舗名}")
            search_params = {
                "search": 店舗名,
                "per_page": 1,
                "context": "edit",  # 編集コンテキストで下書きも取得可能に
                "status": _build_status_param(status)  # カンマ区切りで複数ステータスを指定可能
            }
            search_response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/{WP_POST_TYPE}",
                params=search_params,
                headers=headers,
                timeout=30.0
            )
            
            logger.debug(f"Search response status: {search_response.status_code}")
            
            # 権限エラーの場合はcontext=editを削除して再試行
            if search_response.status_code in (401, 403) or (search_response.status_code != 200 and ("権限" in str(search_response.text) or "rest_forbidden" in str(search_response.text))):
                logger.warning("context=editで権限エラーが発生。context=editなしで再試行します。")
                search_params.pop("context", None)
                search_params.pop("status", None)
                search_response = await client.get(
                    f"{WP_SITE_URL}/wp-json/wp/v2/{WP_POST_TYPE}",
                    params=search_params,
                    headers=headers,
                    timeout=30.0
                )
            
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
            
            # 詳細取得（編集コンテキストで下書きも取得可能に）
            logger.debug(f"Fetching details for store ID: {store_id}")
            detail_response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/{WP_POST_TYPE}/{store_id}",
                params={"context": "edit"},
                headers=headers,
                timeout=30.0
            )
            
            logger.debug(f"Detail response status: {detail_response.status_code}")
            
            # 権限エラーの場合はcontext=editを削除して再試行
            if detail_response.status_code in (401, 403) or (detail_response.status_code != 200 and ("権限" in str(detail_response.text) or "rest_forbidden" in str(detail_response.text))):
                logger.warning("context=editで権限エラーが発生。context=editなしで再試行します。")
                detail_response = await client.get(
                    f"{WP_SITE_URL}/wp-json/wp/v2/{WP_POST_TYPE}/{store_id}",
                    params={},
                    headers=headers,
                    timeout=30.0
                )
            
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
            
            # カスタムフィールド（metaまたはcustom_fieldsから取得）
            fields = _get_custom_fields_from_post(store)
            if fields:
                
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
                
                if 'h4料金プラン直下' in fields:
                    price_plan = fields['h4料金プラン直下']
                    if isinstance(price_plan, list):
                        result += f"📋 料金プラン: {json.dumps(price_plan, ensure_ascii=False, indent=2)}\n\n"
                    else:
                        result += f"📋 料金プラン: {price_plan}\n\n"
                
                if '初期費用' in fields:
                    init_cost = fields['初期費用'][0] if isinstance(fields['初期費用'], list) else fields['初期費用']
                    result += f"初期費用: {init_cost}\n"
                if '体験' in fields:
                    trial = fields['体験'][0] if isinstance(fields['体験'], list) else fields['体験']
                    result += f"✨ 体験: {trial}\n"
                if '表用料金' in fields:
                    price_summary = fields['表用料金'][0] if isinstance(fields['表用料金'], list) else fields['表用料金']
                    result += f"料金目安: {price_summary}\n"
                
                # 価格（配列）の表示
                if '価格' in fields:
                    price_data = fields['価格']
                    result += f"\n💵 価格詳細:\n"
                    if isinstance(price_data, list):
                        # 配列の場合、完全な構造をJSON形式で表示
                        result += json.dumps(price_data, ensure_ascii=False, indent=2)
                    else:
                        result += f"{price_data}"
                    result += f"\n"
                
                # レッスン情報
                result += "\n━━━ 🏃 レッスン情報 ━━━\n\n"
                
                if 'レッスン時間' in fields:
                    lesson_time = fields['レッスン時間'][0] if isinstance(fields['レッスン時間'], list) else fields['レッスン時間']
                    result += f"⏱️ レッスン時間: {lesson_time}\n"
                
                if 'レッスン方式' in fields:
                    lesson_type = fields['レッスン方式']
                    result += f"📋 レッスン方式:\n"
                    if isinstance(lesson_type, list):
                        result += json.dumps(lesson_type, ensure_ascii=False, indent=2)
                    else:
                        result += f"{lesson_type}"
                    result += f"\n\n"
                
                if 'ジャンル' in fields:
                    genre = fields['ジャンル']
                    result += f"🎯 ジャンル:\n"
                    if isinstance(genre, list):
                        result += json.dumps(genre, ensure_ascii=False, indent=2)
                    else:
                        result += f"{genre}"
                    result += f"\n\n"
                
                if '男性利用可否' in fields:
                    male = fields['男性利用可否']
                    result += f"👨 男性利用可否:\n"
                    if isinstance(male, list):
                        result += json.dumps(male, ensure_ascii=False, indent=2)
                    else:
                        result += f"{male}"
                    result += f"\n\n"
                
                if '取材体験済' in fields:
                    experience = fields['取材体験済']
                    result += f"📝 取材体験済:\n"
                    if isinstance(experience, list):
                        result += json.dumps(experience, ensure_ascii=False, indent=2)
                    else:
                        result += f"{experience}"
                    result += f"\n\n"
                
                # 画像類
                if '画像_説明付' in fields:
                    images = fields['画像_説明付']
                    result += "\n━━━ 🖼️ 画像情報 ━━━\n\n"
                    if isinstance(images, list):
                        result += json.dumps(images, ensure_ascii=False, indent=2)
                    else:
                        result += f"{images}"
                    result += f"\n\n"
                
                # 広告強化施策
                if 'AFF_URL' in fields or '目次' in fields or 'ボタン名' in fields:
                    result += "\n━━━ 📢 広告強化施策 ━━━\n\n"
                    if 'AFF_URL' in fields:
                        aff_url = fields['AFF_URL'][0] if isinstance(fields['AFF_URL'], list) else fields['AFF_URL']
                        result += f"🔗 AFF_URL: {aff_url}\n"
                    if '目次' in fields:
                        toc = fields['目次'][0] if isinstance(fields['目次'], list) else fields['目次']
                        result += f"📑 目次: {toc}\n"
                    if 'ボタン名' in fields:
                        button = fields['ボタン名'][0] if isinstance(fields['ボタン名'], list) else fields['ボタン名']
                        result += f"🔘 ボタン名: {button}\n"
                
                # キャンペーン情報
                if 'キャンペーン内容' in fields or 'キャンペーン期間' in fields:
                    result += "\n━━━ 🎉 キャンペーン情報 ━━━\n\n"
                    if 'キャンペーン期間' in fields:
                        period = fields['キャンペーン期間'][0] if isinstance(fields['キャンペーン期間'], list) else fields['キャンペーン期間']
                        result += f"期間: {period}\n"
                    if 'キャンペーン内容' in fields:
                        campaign = fields['キャンペーン内容'][0] if isinstance(fields['キャンペーン内容'], list) else fields['キャンペーン内容']
                        result += f"内容: {campaign}\n"
                
                # 関連記事
                if '関連記事' in fields or '体験_ユーチューブ' in fields:
                    result += "\n━━━ 🔗 関連情報 ━━━\n\n"
                    if '関連記事' in fields:
                        related = fields['関連記事']
                        result += f"📰 関連記事:\n"
                        if isinstance(related, list):
                            result += json.dumps(related, ensure_ascii=False, indent=2)
                        else:
                            result += f"{related}"
                        result += f"\n\n"
                    if '体験_ユーチューブ' in fields:
                        youtube = fields['体験_ユーチューブ'][0] if isinstance(fields['体験_ユーチューブ'], list) else fields['体験_ユーチューブ']
                        result += f"🎥 体験_ユーチューブ: {youtube}\n"
            else:
                result += "\n⚠️ カスタムフィールドが見つかりませんでした。\n"
                result += f"完全な構造を取得するには、`pilates_get_fields_raw`ツール（投稿ID: {store.get('id')}）を使用してください。\n"
            
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
    WordPress 管理画面と同等の情報を取得できます。
    """
    logger.info(f"pilates_by_id called with ID={投稿ID}")
    
    async with httpx.AsyncClient() as client:
        try:
            headers = get_auth_headers()
            
            logger.debug(f"Fetching pilates studio with ID: {投稿ID}")
            response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/{WP_POST_TYPE}/{投稿ID}",
                params={"context": "edit"},  # 編集コンテキストで下書きも取得可能に
                headers=headers,
                timeout=30.0
            )
            
            logger.debug(f"Response status: {response.status_code}")
            
            # 権限エラーの場合はcontext=editを削除して再試行
            if response.status_code in (401, 403) or (response.status_code != 200 and ("権限" in str(response.text) or "rest_forbidden" in str(response.text))):
                # エラーレスポンスの内容をログに記録
                try:
                    error_data = response.json() if response.text else {}
                    logger.warning(f"権限エラー詳細: {error_data}")
                except:
                    logger.warning(f"権限エラーレスポンス: {response.text[:200] if response.text else 'No response body'}")
                
                logger.warning("context=editで権限エラーが発生。context=editなしで再試行します。")
                response = await client.get(
                    f"{WP_SITE_URL}/wp-json/wp/v2/{WP_POST_TYPE}/{投稿ID}",
                    params={},
                    headers=headers,
                    timeout=30.0
                )
            
            # ステータスコードをチェック
            if response.status_code == 404:
                return f"ID {投稿ID} のスタジオが見つかりませんでした。"
            
            if response.status_code != 200:
                try:
                    error_data = response.json() if response.text else {}
                    error_message = error_data.get('message', f'HTTPステータス {response.status_code}')
                    error_code = error_data.get('code', '')
                    logger.error(f"API Error: {response.status_code} - {error_data}")
                    
                    # 401エラーの場合は認証エラーとして詳細を表示
                    if response.status_code == 401:
                        return (
                            f"❌ 認証エラー（401 Unauthorized）が発生しました。\n"
                            f"エラー: {error_message}\n"
                            f"コード: {error_code}\n\n"
                            f"考えられる原因:\n"
                            f"1. WordPressのアプリケーションパスワードが無効になっている\n"
                            f"2. ユーザー名またはパスワードが間違っている\n"
                            f"3. この投稿ID（{投稿ID}）にアクセスする権限がない\n"
                            f"4. 認証情報が正しく送信されていない\n\n"
                            f"WordPress管理画面でアプリケーションパスワードを再生成してください。"
                        )
                    return f"エラーが発生しました: {error_message}"
                except Exception as e:
                    logger.error(f"Error parsing response: {e}")
                    return f"エラーが発生しました: HTTPステータス {response.status_code}"
            
            store = response.json()
            logger.debug(f"Store data keys: {list(store.keys())}")
            
            # titleキーが存在するかチェック
            if 'title' not in store or 'rendered' not in store.get('title', {}):
                return f"ID {投稿ID} のデータ形式が正しくありません。レスポンス: {store}"
            
            status_emoji = get_status_emoji(store.get('status', ''))
            result = f"━━━━━━━━━━━━━━━━━━━━\n"
            result += f"{status_emoji} {store['title']['rendered']}\n"
            result += f"🆔 ID: {store['id']} | ステータス: {store.get('status', '不明')}\n"
            result += f"━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # カスタムフィールドをすべて表示（完全な構造）
            fields = _get_custom_fields_from_post(store)
            if fields:
                result += _format_fields_for_display(fields, include_internal=False)
            else:
                result += "【カスタムフィールド】\n\n"
                result += "カスタムフィールドが見つかりませんでした。\n"
                result += f"利用可能なキー: {', '.join(store.keys())}\n"
            
            result += f"\n🔗 {store['link']}\n"
            
            return result
        
        except Exception as e:
            logger.exception(f"Error in pilates_by_id: {e}")
            return f"エラーが発生しました: {str(e)}"


# ========================================
# ツール3-2: カスタムフィールドの完全な構造を取得
# ========================================
@mcp.tool()
async def pilates_get_fields_raw(投稿ID: int, include_internal: bool = False) -> str:
    """
    ピラティススタジオのカスタムフィールドの完全な構造を取得します。
    ネストされた配列や複雑な構造も含めて、すべての情報をJSON形式で表示します。
    WordPress 管理画面と同等の完全な情報を取得できます。
    
    Args:
        投稿ID: 取得対象の投稿ID
        include_internal: Trueの場合、アンダースコアで始まる内部フィールドも含める（デフォルト: False）
    
    戻り値:
        カスタムフィールドの完全な構造をJSON形式で表示した文字列
    """
    logger.info(f"pilates_get_fields_raw called with ID={投稿ID}, include_internal={include_internal}")
    
    async with httpx.AsyncClient() as client:
        try:
            headers = get_auth_headers()
            
            logger.debug(f"Fetching pilates studio with ID: {投稿ID}")
            response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/{WP_POST_TYPE}/{投稿ID}",
                params={"context": "edit"},
                headers=headers,
                timeout=30.0
            )
            
            logger.debug(f"Response status: {response.status_code}")
            
            # 権限エラーの場合はcontext=editを削除して再試行
            if response.status_code in (401, 403) or (response.status_code != 200 and ("権限" in str(response.text) or "rest_forbidden" in str(response.text))):
                logger.warning("context=editで権限エラーが発生。context=editなしで再試行します。")
                response = await client.get(
                    f"{WP_SITE_URL}/wp-json/wp/v2/{WP_POST_TYPE}/{投稿ID}",
                    params={},
                    headers=headers,
                    timeout=30.0
                )
            
            if response.status_code == 404:
                return f"ID {投稿ID} のスタジオが見つかりませんでした。"
            
            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_message = error_data.get('message', f'HTTPステータス {response.status_code}')
                logger.error(f"API Error: {response.status_code} - {error_data}")
                return f"エラーが発生しました: {error_message}"
            
            store = response.json()
            logger.debug(f"Store data keys: {list(store.keys())}")
            
            # タイトル情報
            title = store.get('title', {}).get('rendered', 'タイトル未設定')
            status = store.get('status', '不明')
            
            result = f"━━━━━━━━━━━━━━━━━━━━\n"
            result += f"📝 {title}\n"
            result += f"🆔 ID: {store.get('id')} | ステータス: {status}\n"
            result += f"━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # カスタムフィールドの完全な構造を取得
            fields = _get_custom_fields_from_post(store)
            
            if fields:
                result += _format_fields_for_display(fields, include_internal=include_internal)
            else:
                result += "カスタムフィールドが見つかりませんでした。\n"
                result += f"利用可能なキー: {', '.join(store.keys())}\n"
                # デバッグ用：レスポンスの一部を表示
                result += f"\n【デバッグ情報】\n"
                result += f"レスポンスのサンプル（最初の5キー）:\n"
                for i, key in enumerate(list(store.keys())[:5]):
                    result += f"  - {key}: {type(store[key]).__name__}\n"
            
            result += f"\n🔗 {store.get('link', 'N/A')}\n"
            result += f"✏️ 編集URL: {WP_SITE_URL}/wp-admin/post.php?post={store.get('id')}&action=edit\n"
            
            return result
        
        except Exception as e:
            logger.exception(f"Error in pilates_get_fields_raw: {e}")
            return f"エラーが発生しました: {str(e)}"


# ========================================
# ツール4: エリアで絞り込み
# ========================================
@mcp.tool()
async def pilates_by_area(エリア: str, 件数: int = 10, status: str = "publish,draft") -> str:
    """
    エリア名でピラティススタジオを検索します（下書き含む）。
    例: 東京都葛飾区、渋谷、新宿など
    WordPress 管理画面と同等の情報を取得できます。
    
    Args:
        エリア: 検索するエリア名
        件数: 取得件数
        status: 取得する投稿ステータス（例: "publish", "draft", "publish,draft"）
    """
    logger.info(f"pilates_by_area called with エリア={エリア}, 件数={件数}, status={status}")
    
    async with httpx.AsyncClient() as client:
        try:
            headers = get_auth_headers()
            
            # 全件取得してカスタムフィールドでフィルタリング（下書き含む）
            logger.debug("Fetching all stores for area filtering")
            area_params = {
                "per_page": 100,
                "context": "edit",  # 編集コンテキストで下書きも取得可能に
                "status": _build_status_param(status)  # カンマ区切りで複数ステータスを指定可能
            }
            response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/{WP_POST_TYPE}",
                params=area_params,
                headers=headers,
                timeout=30.0
            )
            
            logger.debug(f"Response status: {response.status_code}")
            
            # 権限エラーの場合はcontext=editを削除して再試行
            if response.status_code in (401, 403) or (response.status_code != 200 and ("権限" in str(response.text) or "rest_forbidden" in str(response.text))):
                logger.warning("context=editで権限エラーが発生。context=editなしで再試行します。")
                area_params.pop("context", None)
                area_params.pop("status", None)
                response = await client.get(
                    f"{WP_SITE_URL}/wp-json/wp/v2/{WP_POST_TYPE}",
                    params=area_params,
                    headers=headers,
                    timeout=30.0
                )
            
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ヘルパー関数（更新用）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def _pilates_wp_post(path: str, payload: dict) -> dict:
    """
    WordPress REST APIにPOSTリクエストを送信
    """
    url = path
    if not url.startswith("http"):
        url = f"{WP_SITE_URL}/wp-json/wp/v2/{path.lstrip('/')}"
    
    headers = get_auth_headers()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=30.0)
        
        if response.status_code >= 400:
            error_data = response.json() if response.text else {"message": str(response.text)}
            raise RuntimeError(
                f"WordPress APIエラー (HTTP {response.status_code}): {json.dumps(error_data, ensure_ascii=False)}"
            )
        
        result = response.json()
        if isinstance(result, dict):
            return result
        raise RuntimeError("予期しないレスポンス形式です。JSONオブジェクトを受信できませんでした。")


def _pilates_format_update_summary(
    post: dict,
    updated_fields: dict,
    field_group: str
) -> str:
    """更新結果をフォーマット"""
    title = post.get('title', {}).get('rendered', 'タイトル未設定')
    lines = [
        "✅ 更新成功",
        f"ID: {post.get('id')}",
        f"タイトル: {title}",
        f"対象: {field_group}",
        "",
        "更新内容:"
    ]
    for key, value in updated_fields.items():
        lines.append(f"  • {key}: {value}")
    return "\n".join(lines)


def _pilates_parse_fields_json(raw: str) -> tuple[dict | None, str | None]:
    """JSON文字列をパース"""
    if not raw or not raw.strip():
        return None, None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"❌ JSONの形式が正しくありません: {exc}"
    if not isinstance(data, dict):
        return None, "❌ JSONはオブジェクト（Key/Value形式）で指定してください。"
    return data, None


async def _pilates_handle_update_tool(
    *,
    post_id: int,
    fields_json: str,
    container: str,
    wrap_payload: bool,
) -> str:
    """カスタムフィールド更新の共通処理"""
    try:
        data = json.loads(fields_json)
    except json.JSONDecodeError as exc:
        return (
            "❌ JSONの形式に問題があります。\n"
            f"エラー: {exc}\n"
            "例: {\"カスタムフィールド名\": \"値\"}"
        )
    
    if not isinstance(data, dict) or not data:
        return "❌ JSONはキーと値を持つオブジェクト形式で指定してください。"
    
    container = (container or "meta").strip()
    wrap_payload = bool(wrap_payload)
    
    if wrap_payload:
        # containerでラップして送信
        if container not in ("custom_fields", "meta", "acf"):
            return (
                f"❌ container='{container}' はサポートされていません。"
                " 使用可能: custom_fields / meta / acf"
            )
        payload = {container: data}
        summary_fields = data
        field_group = f"pilates-studio:{container}"
    else:
        # そのまま送信
        payload = data
        summary_fields = data
        field_group = "pilates-studio:raw"
    
    logger.info(
        "[Pilates] 更新開始 id=%s container=%s wrap=%s",
        post_id,
        container,
        wrap_payload,
    )
    
    try:
        post = await _pilates_wp_post(f"{WP_POST_TYPE}/{post_id}", payload)
    except RuntimeError as exc:
        logger.error(
            "[Pilates] 更新失敗 id=%s : %s",
            post_id,
            exc,
        )
        return f"❌ 更新に失敗しました。\n{exc}"
    
    return _pilates_format_update_summary(post, summary_fields, field_group)


# ========================================
# ツール5: カスタムフィールド更新
# ========================================
@mcp.tool()
async def pilates_update_fields(
    投稿ID: int,
    フィールドJSON: str,
    container: str = "meta",
    wrap_payload: bool = True,
) -> str:
    """
    ピラティススタジオのカスタムフィールドを更新します。
    
    Args:
        投稿ID: 更新対象の投稿ID
        フィールドJSON: {"フィールド名": "値"} 形式のJSON文字列
        container: custom_fields / meta / acf のいずれか（wrap_payload=True の場合）
        wrap_payload: True で JSON を container 内に包んで送信、False で JSON をそのまま送信
    
    例:
        フィールドJSON: '{"簡易地区": "東京都渋谷区", "表用料金": "月額10,000円〜"}'
    """
    logger.info(f"pilates_update_fields called with ID={投稿ID}")
    
    return await _pilates_handle_update_tool(
        post_id=投稿ID,
        fields_json=フィールドJSON,
        container=container,
        wrap_payload=wrap_payload,
    )


def _pilates_normalize_single_status(status: str | None) -> str:
    """ステータスを正規化（単一ステータス用）"""
    value = (status or "").strip().lower()
    if value in ALLOWED_STATUSES:
        return value
    return "draft"


def _pilates_format_post_action_result(action: str, post: dict) -> str:
    """投稿アクション結果をフォーマット"""
    title = post.get('title', {}).get('rendered', 'タイトル未設定')
    status = post.get('status', 'unknown')
    post_id = post.get('id')
    link = post.get('link') or ""
    edit_url = f"{WP_SITE_URL}/wp-admin/post.php?post={post_id}&action=edit" if post_id else "N/A"
    lines = [
        action,
        f"🆔 ID: {post_id} / status: {status}",
        f"📍 タイトル: {title}",
        f"🔗 表示URL: {link or 'N/A'}",
        f"✏️ 編集URL: {edit_url}",
    ]
    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# カスタムタクソノミー用ツール
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _normalize_taxonomy_name(taxonomy_name: str) -> str:
    """
    タクソノミー名を正規化する。
    日本語名をスラッグに変換する。
    
    Args:
        taxonomy_name: タクソノミー名（日本語名またはスラッグ）
    
    Returns:
        正規化されたタクソノミースラッグ
    """
    # 日本語名からスラッグへのマッピング
    name_to_slug = {
        "特徴": "pilates-features",
        "スタジオ名": "studio_name",
        "pilates-features": "pilates-features",
        "studio_name": "studio_name",
        "studio-name": "studio_name",  # ハイフン形式も受け入れる
        "pilates_features": "pilates-features",  # アンダースコア形式も受け入れる
    }
    
    normalized = name_to_slug.get(taxonomy_name.strip(), taxonomy_name.strip())
    logger.debug(f"Taxonomy name normalized: '{taxonomy_name}' -> '{normalized}'")
    return normalized


# ========================================
# ツール16: タクソノミーのターム一覧取得
# ========================================
@mcp.tool()
async def pilates_get_taxonomy_terms(タクソノミー名: str, 件数: int = 100) -> str:
    """
    指定したタクソノミーのターム一覧を取得します。
    
    Args:
        タクソノミー名: 取得するタクソノミーの名前（例: "特徴", "スタジオ名", "pilates-features", "studio_name"）
        件数: 取得件数（デフォルト: 100）
    
    例:
        タクソノミー名: "特徴" または "スタジオ名" または "pilates-features" または "studio_name"
    """
    logger.info(f"pilates_get_taxonomy_terms called with タクソノミー名={タクソノミー名}, 件数={件数}")
    
    # タクソノミー名を正規化（スラッグに変換）
    taxonomy_slug = _normalize_taxonomy_name(タクソノミー名)
    
    async with httpx.AsyncClient() as client:
        try:
            headers = get_auth_headers()
            
            params = {
                "per_page": min(max(件数, 1), 100),
                "context": "edit"
            }
            
            response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/{taxonomy_slug}",
                params=params,
                headers=headers,
                timeout=30.0
            )
            
            logger.debug(f"Response status: {response.status_code}")
            
            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                logger.error(f"API Error: {response.status_code} - {error_data}")
                return f"APIエラーが発生しました: {error_data.get('message', 'Unknown error')}"
            
            terms = response.json()
            
            if not isinstance(terms, list):
                logger.error(f"Unexpected response format: {type(terms)}")
                return f"予期しないレスポンス形式です"
            
            logger.debug(f"Found {len(terms)} terms")
            
            if not terms:
                return f"「{タクソノミー名}」（スラッグ: {taxonomy_slug}）タクソノミーのタームが見つかりませんでした。"
            
            result = f"🏷️ {タクソノミー名} タクソノミー（スラッグ: {taxonomy_slug}）のターム一覧（{len(terms)}件）\n\n"
            
            for term in terms:
                result += f"━━━━━━━━━━━━━━━━\n"
                result += f"🆔 ID: {term.get('id')}\n"
                result += f"📝 名前: {term.get('name')}\n"
                result += f"🔗 スラッグ: {term.get('slug', 'N/A')}\n"
                result += f"📊 投稿数: {term.get('count', 0)}\n"
                if term.get('description'):
                    result += f"📄 説明: {term.get('description')}\n"
                result += f"\n"
            
            return result
        
        except Exception as e:
            logger.exception(f"Error in pilates_get_taxonomy_terms: {e}")
            return f"エラーが発生しました: {str(e)}"


# ========================================
# ツール17: 投稿に紐づくタクソノミーターム取得
# ========================================
@mcp.tool()
async def pilates_get_post_taxonomy_terms(投稿ID: int, タクソノミー名: str = "") -> str:
    """
    投稿に紐づいているタクソノミーのタームを取得します。
    
    Args:
        投稿ID: 取得対象の投稿ID
        タクソノミー名: 取得するタクソノミーの名前（空の場合はすべてのタクソノミーを取得）
    
    例:
        タクソノミー名: "特徴" または "スタジオ名"（空の場合はすべて）
    """
    logger.info(f"pilates_get_post_taxonomy_terms called with 投稿ID={投稿ID}, タクソノミー名={タクソノミー名}")
    
    async with httpx.AsyncClient() as client:
        try:
            headers = get_auth_headers()
            
            response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/{WP_POST_TYPE}/{投稿ID}",
                params={"context": "edit"},
                headers=headers,
                timeout=30.0
            )
            
            logger.debug(f"Response status: {response.status_code}")
            
            if response.status_code == 404:
                return f"ID {投稿ID} の投稿が見つかりませんでした。"
            
            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_message = error_data.get('message', f'HTTPステータス {response.status_code}')
                logger.error(f"API Error: {response.status_code} - {error_data}")
                return f"エラーが発生しました: {error_message}"
            
            post = response.json()
            title = post.get('title', {}).get('rendered', 'タイトル未設定')
            
            result = f"━━━━━━━━━━━━━━━━━━━━\n"
            result += f"📝 {title}\n"
            result += f"🆔 投稿ID: {投稿ID}\n"
            result += f"━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # タクソノミー情報を取得
            if タクソノミー名:
                # 特定のタクソノミーのみ（スラッグに変換）
                taxonomy_slug = _normalize_taxonomy_name(タクソノミー名)
                if taxonomy_slug in post:
                    terms = post[taxonomy_slug]
                    if terms:
                        result += f"🏷️ {タクソノミー名} タクソノミー（スラッグ: {taxonomy_slug}）:\n\n"
                        for term in terms:
                            result += f"  • ID: {term.get('id')} | 名前: {term.get('name')} | スラッグ: {term.get('slug', 'N/A')}\n"
                    else:
                        result += f"🏷️ {タクソノミー名} タクソノミー（スラッグ: {taxonomy_slug}）: タームが設定されていません\n"
                else:
                    result += f"⚠️ {タクソノミー名} タクソノミー（スラッグ: {taxonomy_slug}）が見つかりませんでした。\n"
                    result += f"利用可能なキー: {', '.join([k for k in post.keys() if not k.startswith('_')])}\n"
            else:
                # すべてのタクソノミー
                result += "🏷️ すべてのタクソノミー:\n\n"
                found_any = False
                for key, value in post.items():
                    # タクソノミーは通常配列で、各要素にid, name, slugなどが含まれる
                    if isinstance(value, list) and value and isinstance(value[0], dict) and 'id' in value[0] and 'name' in value[0]:
                        found_any = True
                        result += f"【{key}】\n"
                        for term in value:
                            result += f"  • ID: {term.get('id')} | 名前: {term.get('name')} | スラッグ: {term.get('slug', 'N/A')}\n"
                        result += f"\n"
                
                if not found_any:
                    result += "タクソノミータームが設定されていません。\n"
            
            return result
        
        except Exception as e:
            logger.exception(f"Error in pilates_get_post_taxonomy_terms: {e}")
            return f"エラーが発生しました: {str(e)}"


# ========================================
# ツール18: 新しいタームを作成
# ========================================
@mcp.tool()
async def pilates_create_taxonomy_term(
    タクソノミー名: str,
    ターム名: str,
    スラッグ: str = "",
    説明: str = ""
) -> str:
    """
    指定したタクソノミーに新しいタームを作成します。
    
    Args:
        タクソノミー名: タームを追加するタクソノミーの名前（例: "特徴", "スタジオ名", "pilates-features", "studio_name"）
        ターム名: 作成するタームの名前（必須）
        スラッグ: タームのスラッグ（空の場合はターム名から自動生成）
        説明: タームの説明
    
    例:
        タクソノミー名: "特徴" または "pilates-features"
        ターム名: "マシンピラティス"
    """
    logger.info(f"pilates_create_taxonomy_term called with タクソノミー名={タクソノミー名}, ターム名={ターム名}")
    
    clean_term_name = (ターム名 or "").strip()
    if not clean_term_name:
        return "ターム名を指定してください。"
    
    # タクソノミー名を正規化（スラッグに変換）
    taxonomy_slug = _normalize_taxonomy_name(タクソノミー名)
    
    async with httpx.AsyncClient() as client:
        try:
            headers = get_auth_headers()
            
            payload: dict = {
                "name": clean_term_name
            }
            if スラッグ:
                payload["slug"] = スラッグ
            if 説明:
                payload["description"] = 説明
            
            response = await client.post(
                f"{WP_SITE_URL}/wp-json/wp/v2/{taxonomy_slug}",
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            logger.debug(f"Response status: {response.status_code}")
            
            if response.status_code >= 400:
                error_data = response.json() if response.text else {}
                error_message = error_data.get('message', f'HTTPステータス {response.status_code}')
                logger.error(f"API Error: {response.status_code} - {error_data}")
                return f"❌ ターム作成に失敗しました: {error_message}"
            
            term = response.json()
            
            result = f"✅ タームを作成しました\n\n"
            result += f"🏷️ タクソノミー: {タクソノミー名}（スラッグ: {taxonomy_slug}）\n"
            result += f"🆔 ID: {term.get('id')}\n"
            result += f"📝 名前: {term.get('name')}\n"
            result += f"🔗 スラッグ: {term.get('slug', 'N/A')}\n"
            if term.get('description'):
                result += f"📄 説明: {term.get('description')}\n"
            
            return result
        
        except Exception as e:
            logger.exception(f"Error in pilates_create_taxonomy_term: {e}")
            return f"エラーが発生しました: {str(e)}"


# ========================================
# ツール19: 投稿にタクソノミータームを追加・更新
# ========================================
@mcp.tool()
async def pilates_update_post_taxonomy_terms(
    投稿ID: int,
    タクソノミー名: str,
    タームIDリスト: str = "",
    ターム名リスト: str = ""
) -> str:
    """
    投稿にタクソノミーのタームを追加・更新します。
    タームIDまたはターム名で指定できます。
    
    Args:
        投稿ID: 更新対象の投稿ID
        タクソノミー名: 更新するタクソノミーの名前（例: "特徴", "スタジオ名", "pilates-features", "studio_name"）
        タームIDリスト: タームIDのカンマ区切りリスト（例: "1,2,3"）
        ターム名リスト: ターム名のカンマ区切りリスト（例: "マシンピラティス,マットピラティス"）
    
    注意: タームIDリストとターム名リストの両方を指定した場合、タームIDリストが優先されます。
    
    例:
        タクソノミー名: "特徴" または "pilates-features"
        ターム名リスト: "マシンピラティス,マットピラティス"
    """
    logger.info(f"pilates_update_post_taxonomy_terms called with 投稿ID={投稿ID}, タクソノミー名={タクソノミー名}")
    
    if not タームIDリスト and not ターム名リスト:
        return "タームIDリストまたはターム名リストを指定してください。"
    
    # タクソノミー名を正規化（スラッグに変換）
    taxonomy_slug = _normalize_taxonomy_name(タクソノミー名)
    
    async with httpx.AsyncClient() as client:
        try:
            headers = get_auth_headers()
            
            # タームを決定
            if タームIDリスト:
                # タームIDリストを使用
                term_ids = [int(tid.strip()) for tid in タームIDリスト.split(",") if tid.strip()]
                payload = {taxonomy_slug: term_ids}
            else:
                # ターム名リストを使用
                term_names = [name.strip() for name in ターム名リスト.split(",") if name.strip()]
                payload = {taxonomy_slug: term_names}
            
            response = await client.post(
                f"{WP_SITE_URL}/wp-json/wp/v2/{WP_POST_TYPE}/{投稿ID}",
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            logger.debug(f"Response status: {response.status_code}")
            
            if response.status_code >= 400:
                error_data = response.json() if response.text else {}
                error_message = error_data.get('message', f'HTTPステータス {response.status_code}')
                logger.error(f"API Error: {response.status_code} - {error_data}")
                return f"❌ ターム更新に失敗しました: {error_message}"
            
            post = response.json()
            title = post.get('title', {}).get('rendered', 'タイトル未設定')
            
            # 更新後のタームを取得
            updated_terms = post.get(taxonomy_slug, [])
            
            result = f"✅ タクソノミータームを更新しました\n\n"
            result += f"📝 投稿: {title}\n"
            result += f"🆔 投稿ID: {投稿ID}\n"
            result += f"🏷️ タクソノミー: {タクソノミー名}（スラッグ: {taxonomy_slug}）\n\n"
            result += f"設定されたターム:\n"
            
            if updated_terms:
                for term in updated_terms:
                    result += f"  • ID: {term.get('id')} | 名前: {term.get('name')}\n"
            else:
                result += "  （タームが設定されていません）\n"
            
            return result
        
        except Exception as e:
            logger.exception(f"Error in pilates_update_post_taxonomy_terms: {e}")
            return f"エラーが発生しました: {str(e)}"


# ========================================
# ツール12: pilates-studio 投稿作成
# ========================================
@mcp.tool()
async def pilates_create_post(
    タイトル: str,
    本文: str = "",
    status: str = "draft",
    フィールドJSON: str = "",
    抜粋: str = "",
    slug: str = "",
    特徴タームIDリスト: str = "",
    特徴ターム名リスト: str = "",
    スタジオ名タームIDリスト: str = "",
    スタジオ名ターム名リスト: str = ""
) -> str:
    """
    ピラティススタジオ カスタム投稿を新規作成します。
    
    Args:
        タイトル: 投稿のタイトル（必須）
        本文: 投稿の本文
        status: 投稿ステータス（"publish" または "draft"、デフォルト: "draft"）
        フィールドJSON: カスタムフィールドのJSON文字列
        抜粋: 投稿の抜粋
        slug: 投稿のスラッグ
        特徴タームIDリスト: 特徴タクソノミーのタームID（カンマ区切り、例: "1,2,3"）
        特徴ターム名リスト: 特徴タクソノミーのターム名（カンマ区切り、例: "マシンピラティス,マットピラティス"）
        スタジオ名タームIDリスト: スタジオ名タクソノミーのタームID（カンマ区切り）
        スタジオ名ターム名リスト: スタジオ名タクソノミーのターム名（カンマ区切り）
    
    カスタムフィールドの構造:
    - 表用情報: 表用特徴、表用料金、表用アクセス
    - 基本情報: 簡易地区、住所、営業時間、定休日、アクセス、駐車場、店舗公式サイト
    - 料金系情報: h4料金プラン直下、初期費用、体験、価格（配列）
    - レッスン情報: レッスン時間、レッスン方式（配列）、ジャンル（配列）、取材体験済（配列）、男性利用可否（配列）
    - 広告強化施策: AFF_URL、目次、ボタン名
    - 画像類: 画像_説明付（配列）
    - キャンペーン情報: キャンペーン期間、キャンペーン内容
    - 関連記事: 関連記事（配列）、体験_ユーチューブ
    
    例:
        フィールドJSON: '{"簡易地区": "東京都渋谷区", "表用料金": "月額10,000円〜", "価格": [...]}'
        特徴ターム名リスト: "マシンピラティス,マットピラティス"
    """
    logger.info(f"pilates_create_post called with タイトル={タイトル}")
    
    clean_title = (タイトル or "").strip()
    if not clean_title:
        return "タイトルを指定してください。"
    
    payload: dict = {
        "title": clean_title,
        "status": _pilates_normalize_single_status(status),
    }
    if 本文:
        payload["content"] = 本文
    if 抜粋:
        payload["excerpt"] = 抜粋
    if slug:
        payload["slug"] = slug
    
    fields, error = _pilates_parse_fields_json(フィールドJSON)
    if error:
        return error
    if fields:
        payload["meta"] = fields
    
    # タクソノミータームの設定（スラッグを使用）
    if 特徴タームIDリスト:
        term_ids = [int(tid.strip()) for tid in 特徴タームIDリスト.split(",") if tid.strip()]
        payload["pilates-features"] = term_ids
    elif 特徴ターム名リスト:
        term_names = [name.strip() for name in 特徴ターム名リスト.split(",") if name.strip()]
        payload["pilates-features"] = term_names
    
    if スタジオ名タームIDリスト:
        term_ids = [int(tid.strip()) for tid in スタジオ名タームIDリスト.split(",") if tid.strip()]
        payload["studio_name"] = term_ids
    elif スタジオ名ターム名リスト:
        term_names = [name.strip() for name in スタジオ名ターム名リスト.split(",") if name.strip()]
        payload["studio_name"] = term_names
    
    try:
        post = await _pilates_wp_post(WP_POST_TYPE, payload)
    except RuntimeError as exc:
        logger.error("[Pilates] 投稿作成失敗: %s", exc)
        return f"❌ 作成に失敗しました。\n{exc}"
    
    return _pilates_format_post_action_result("✅ pilates-studio 投稿を作成しました", post)


# ========================================
# ツール13: pilates-studio 投稿更新
# ========================================
@mcp.tool()
async def pilates_update_post(
    投稿ID: int,
    タイトル: str = "",
    本文: str = "",
    status: str = "",
    フィールドJSON: str = "",
    抜粋: str = "",
    slug: str = "",
    特徴タームIDリスト: str = "",
    特徴ターム名リスト: str = "",
    スタジオ名タームIDリスト: str = "",
    スタジオ名ターム名リスト: str = ""
) -> str:
    """
    ピラティススタジオ 投稿のタイトル / 本文 / ステータス / メタ情報 / タクソノミーを更新します。
    
    Args:
        投稿ID: 更新対象の投稿ID（必須）
        タイトル: 新しいタイトル
        本文: 新しい本文
        status: 新しいステータス（"publish" または "draft"）
        フィールドJSON: カスタムフィールドのJSON文字列
        抜粋: 新しい抜粋
        slug: 新しいスラッグ
        特徴タームIDリスト: 特徴タクソノミーのタームID（カンマ区切り、例: "1,2,3"）
        特徴ターム名リスト: 特徴タクソノミーのターム名（カンマ区切り、例: "マシンピラティス,マットピラティス"）
        スタジオ名タームIDリスト: スタジオ名タクソノミーのタームID（カンマ区切り）
        スタジオ名ターム名リスト: スタジオ名タクソノミーのターム名（カンマ区切り）
    
    カスタムフィールドの構造:
    - 表用情報: 表用特徴、表用料金、表用アクセス
    - 基本情報: 簡易地区、住所、営業時間、定休日、アクセス、駐車場、店舗公式サイト
    - 料金系情報: h4料金プラン直下、初期費用、体験、価格（配列）
    - レッスン情報: レッスン時間、レッスン方式（配列）、ジャンル（配列）、取材体験済（配列）、男性利用可否（配列）
    - 広告強化施策: AFF_URL、目次、ボタン名
    - 画像類: 画像_説明付（配列）
    - キャンペーン情報: キャンペーン期間、キャンペーン内容
    - 関連記事: 関連記事（配列）、体験_ユーチューブ
    
    例:
        フィールドJSON: '{"簡易地区": "東京都渋谷区", "表用料金": "月額10,000円〜"}'
        特徴ターム名リスト: "マシンピラティス,マットピラティス"
    """
    logger.info(f"pilates_update_post called with ID={投稿ID}")
    
    payload: dict = {}
    if タイトル:
        payload["title"] = タイトル
    if 本文:
        payload["content"] = 本文
    if 抜粋:
        payload["excerpt"] = 抜粋
    if slug:
        payload["slug"] = slug
    if status:
        payload["status"] = _pilates_normalize_single_status(status)
    
    fields, error = _pilates_parse_fields_json(フィールドJSON)
    if error:
        return error
    if fields:
        payload.setdefault("meta", {}).update(fields)
    
    # タクソノミータームの設定（スラッグを使用）
    if 特徴タームIDリスト:
        term_ids = [int(tid.strip()) for tid in 特徴タームIDリスト.split(",") if tid.strip()]
        payload["pilates-features"] = term_ids
    elif 特徴ターム名リスト:
        term_names = [name.strip() for name in 特徴ターム名リスト.split(",") if name.strip()]
        payload["pilates-features"] = term_names
    
    if スタジオ名タームIDリスト:
        term_ids = [int(tid.strip()) for tid in スタジオ名タームIDリスト.split(",") if tid.strip()]
        payload["studio_name"] = term_ids
    elif スタジオ名ターム名リスト:
        term_names = [name.strip() for name in スタジオ名ターム名リスト.split(",") if name.strip()]
        payload["studio_name"] = term_names
    
    if not payload:
        return "更新項目を1つ以上指定してください。"
    
    try:
        post = await _pilates_wp_post(f"{WP_POST_TYPE}/{投稿ID}", payload)
    except RuntimeError as exc:
        logger.error("[Pilates] 投稿更新失敗: %s", exc)
        return f"❌ 更新に失敗しました。\n{exc}"
    
    return _pilates_format_post_action_result("✅ pilates-studio 投稿を更新しました", post)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# media-free-content カスタム投稿タイプ用ツール
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ========================================
# ツール6: media-free-content 一覧取得
# ========================================
@mcp.tool()
async def media_free_content_list(
    キーワード: str = "",
    件数: int = 20,
    status: str = "publish,draft"
) -> str:
    """
    media-free-content カスタム投稿の一覧を取得します（下書き含む）。
    WordPress 管理画面と同等の情報を取得できます。
    
    Args:
        キーワード: タイトルや本文で検索するキーワード
        件数: 取得件数 (1-100)
        status: 取得する投稿ステータス（例: "publish", "draft", "publish,draft"）
    """
    logger.info(f"media_free_content_list called with キーワード={キーワード}, 件数={件数}, status={status}")
    
    async with httpx.AsyncClient() as client:
        try:
            headers = get_auth_headers()
            
            params = {
                "per_page": min(max(件数, 1), 100),
                "context": "edit",  # 編集コンテキストで下書きも取得可能に
                "status": _build_status_param(status)  # カンマ区切りで複数ステータスを指定可能
            }
            
            if キーワード:
                params["search"] = キーワード
            
            response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/media-free-content",
                params=params,
                headers=headers,
                timeout=30.0
            )
            
            logger.debug(f"Response status: {response.status_code}")
            
            # 権限エラーの場合はcontext=editを削除して再試行
            if response.status_code in (401, 403) or (response.status_code != 200 and ("権限" in str(response.text) or "rest_forbidden" in str(response.text))):
                logger.warning("context=editで権限エラーが発生。context=editなしで再試行します。")
                params.pop("context", None)
                params.pop("status", None)
                response = await client.get(
                    f"{WP_SITE_URL}/wp-json/wp/v2/media-free-content",
                    params=params,
                    headers=headers,
                    timeout=30.0
                )
            
            # ステータスコードチェック
            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                logger.error(f"API Error: {response.status_code} - {error_data}")
                return f"APIエラーが発生しました: {error_data.get('message', 'Unknown error')}"
            
            posts = response.json()
            
            # レスポンスが配列でない場合のチェック
            if not isinstance(posts, list):
                logger.error(f"Unexpected response format: {type(posts)}")
                return f"予期しないレスポンス形式です"
            
            logger.debug(f"Found {len(posts)} posts")
            
            if not posts:
                return "該当する投稿が見つかりませんでした。"
            
            result = f"📝 media-free-content 投稿情報（{len(posts)}件）\n\n"
            
            for post in posts:
                status_emoji = get_status_emoji(post.get('status', ''))
                result += f"━━━━━━━━━━━━━━━━\n"
                result += f"{status_emoji} {post['title']['rendered']}\n"
                result += f"🆔 ID: {post['id']} | ステータス: {post.get('status', '不明')}\n"
                result += f"📅 日付: {post.get('date', 'N/A')}\n"
                result += f"🔗 {post['link']}\n\n"
            
            return result
        
        except Exception as e:
            logger.exception(f"Error in media_free_content_list: {e}")
            return f"エラーが発生しました: {str(e)}"


# ========================================
# ツール7: media-free-content 詳細取得
# ========================================
@mcp.tool()
async def media_free_content_detail(タイトル: str, status: str = "publish,draft") -> str:
    """
    特定のmedia-free-content投稿の詳細情報をすべて取得します（下書き含む）。
    WordPress 管理画面と同等の情報を取得できます。
    
    Args:
        タイトル: 検索する投稿のタイトル
        status: 取得する投稿ステータス（例: "publish", "draft", "publish,draft"）
    """
    logger.info(f"media_free_content_detail called with タイトル={タイトル}, status={status}")
    
    async with httpx.AsyncClient() as client:
        try:
            headers = get_auth_headers()
            
            # 投稿を検索（下書き含む）
            logger.debug(f"Searching for post: {タイトル}")
            search_params = {
                "search": タイトル,
                "per_page": 1,
                "context": "edit",  # 編集コンテキストで下書きも取得可能に
                "status": _build_status_param(status)  # カンマ区切りで複数ステータスを指定可能
            }
            search_response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/media-free-content",
                params=search_params,
                headers=headers,
                timeout=30.0
            )
            
            logger.debug(f"Search response status: {search_response.status_code}")
            
            # 権限エラーの場合はcontext=editを削除して再試行
            if search_response.status_code in (401, 403) or (search_response.status_code != 200 and ("権限" in str(search_response.text) or "rest_forbidden" in str(search_response.text))):
                logger.warning("context=editで権限エラーが発生。context=editなしで再試行します。")
                search_params.pop("context", None)
                search_params.pop("status", None)
                search_response = await client.get(
                    f"{WP_SITE_URL}/wp-json/wp/v2/media-free-content",
                    params=search_params,
                    headers=headers,
                    timeout=30.0
                )
            
            # ステータスコードチェック
            if search_response.status_code != 200:
                error_data = search_response.json() if search_response.text else {}
                logger.error(f"Search API Error: {search_response.status_code} - {error_data}")
                return f"APIエラーが発生しました: {error_data.get('message', 'Unknown error')}"
            
            posts = search_response.json()
            
            # レスポンスが配列でない場合のチェック
            if not isinstance(posts, list):
                logger.error(f"Unexpected response format: {type(posts)}")
                return f"予期しないレスポンス形式です"
            
            logger.debug(f"Search results count: {len(posts)}")
            
            if not posts:
                logger.warning(f"No posts found for: {タイトル}")
                return f"「{タイトル}」が見つかりませんでした。"
            
            post_id = posts[0]['id']
            logger.info(f"Found post ID: {post_id}")
            
            # 詳細取得（編集コンテキストで下書きも取得可能に）
            logger.debug(f"Fetching details for post ID: {post_id}")
            detail_response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/media-free-content/{post_id}",
                params={"context": "edit"},
                headers=headers,
                timeout=30.0
            )
            
            logger.debug(f"Detail response status: {detail_response.status_code}")
            
            # 権限エラーの場合はcontext=editを削除して再試行
            if detail_response.status_code in (401, 403) or (detail_response.status_code != 200 and ("権限" in str(detail_response.text) or "rest_forbidden" in str(detail_response.text))):
                logger.warning("context=editで権限エラーが発生。context=editなしで再試行します。")
                detail_response = await client.get(
                    f"{WP_SITE_URL}/wp-json/wp/v2/media-free-content/{post_id}",
                    params={},
                    headers=headers,
                    timeout=30.0
                )
            
            # ステータスコードをチェック
            if detail_response.status_code != 200:
                logger.error(f"HTTP error: {detail_response.status_code}")
                return f"エラーが発生しました: HTTPステータス {detail_response.status_code}"
            
            post = detail_response.json()
            logger.debug(f"Post data keys: {post.keys()}")
            
            # titleキーが存在するかチェック
            if 'title' not in post or 'rendered' not in post.get('title', {}):
                return f"データ形式が正しくありません。"
            
            status_emoji = get_status_emoji(post.get('status', ''))
            result = f"━━━━━━━━━━━━━━━━━━━━\n"
            result += f"{status_emoji} {post['title']['rendered']}\n"
            result += f"🆔 ID: {post['id']} | ステータス: {post.get('status', '不明')}\n"
            result += f"📅 公開日: {post.get('date', 'N/A')} | 最終更新: {post.get('modified', 'N/A')}\n"
            result += f"━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # 本文
            if post.get('content', {}).get('rendered'):
                import re
                content = post['content']['rendered']
                content = re.sub('<[^<]+?>', '', content)
                result += f"📝 本文:\n{content.strip()[:1000]}...\n\n"
            
            # カスタムフィールド（metaまたはcustom_fieldsから取得）
            fields = _get_custom_fields_from_post(post)
            if fields:
                result += "━━━ 🔧 カスタムフィールド ━━━\n\n"
                result += _format_fields_for_display(fields, include_internal=False)
            else:
                result += "\n⚠️ カスタムフィールドが見つかりませんでした。\n"
                result += f"完全な構造を取得するには、`media_free_content_get_fields_raw`ツール（投稿ID: {post.get('id')}）を使用してください。\n"
            
            result += f"\n🔗 詳細URL: {post['link']}\n"
            
            return result
        
        except Exception as e:
            logger.exception(f"Error in media_free_content_detail: {e}")
            return f"エラーが発生しました: {str(e)}"


# ========================================
# ツール8: media-free-content IDで直接取得
# ========================================
@mcp.tool()
async def media_free_content_by_id(投稿ID: int) -> str:
    """
    投稿IDを指定してmedia-free-content投稿の情報を取得します（下書き含む）。
    WordPress 管理画面と同等の情報を取得できます。
    """
    logger.info(f"media_free_content_by_id called with ID={投稿ID}")
    
    async with httpx.AsyncClient() as client:
        try:
            headers = get_auth_headers()
            
            logger.debug(f"Fetching media-free-content post with ID: {投稿ID}")
            response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/media-free-content/{投稿ID}",
                params={"context": "edit"},  # 編集コンテキストで下書きも取得可能に
                headers=headers,
                timeout=30.0
            )
            
            logger.debug(f"Response status: {response.status_code}")
            
            # 権限エラーの場合はcontext=editを削除して再試行
            if response.status_code in (401, 403) or (response.status_code != 200 and ("権限" in str(response.text) or "rest_forbidden" in str(response.text))):
                logger.warning("context=editで権限エラーが発生。context=editなしで再試行します。")
                response = await client.get(
                    f"{WP_SITE_URL}/wp-json/wp/v2/media-free-content/{投稿ID}",
                    params={},
                    headers=headers,
                    timeout=30.0
                )
            
            # ステータスコードをチェック
            if response.status_code == 404:
                return f"ID {投稿ID} の投稿が見つかりませんでした。"
            
            if response.status_code != 200:
                return f"エラーが発生しました: HTTPステータス {response.status_code}"
            
            post = response.json()
            logger.debug(f"Post data keys: {list(post.keys())}")
            
            # titleキーが存在するかチェック
            if 'title' not in post or 'rendered' not in post.get('title', {}):
                return f"ID {投稿ID} のデータ形式が正しくありません。レスポンス: {post}"
            
            status_emoji = get_status_emoji(post.get('status', ''))
            result = f"━━━━━━━━━━━━━━━━━━━━\n"
            result += f"{status_emoji} {post['title']['rendered']}\n"
            result += f"🆔 ID: {post['id']} | ステータス: {post.get('status', '不明')}\n"
            result += f"📅 公開日: {post.get('date', 'N/A')} | 最終更新: {post.get('modified', 'N/A')}\n"
            result += f"━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # カスタムフィールドをすべて表示（完全な構造）
            fields = _get_custom_fields_from_post(post)
            if fields:
                result += _format_fields_for_display(fields, include_internal=False)
            else:
                result += "【カスタムフィールド】\n\n"
                result += "カスタムフィールドが見つかりませんでした。\n"
                result += f"利用可能なキー: {', '.join(post.keys())}\n"
            
            result += f"\n🔗 {post['link']}\n"
            
            return result
        
        except Exception as e:
            logger.exception(f"Error in media_free_content_by_id: {e}")
            return f"エラーが発生しました: {str(e)}"


# ========================================
# ツール8-2: media-free-content カスタムフィールドの完全な構造を取得
# ========================================
@mcp.tool()
async def media_free_content_get_fields_raw(投稿ID: int, include_internal: bool = False) -> str:
    """
    media-free-content カスタム投稿のカスタムフィールドの完全な構造を取得します。
    ネストされた配列や複雑な構造も含めて、すべての情報をJSON形式で表示します。
    WordPress 管理画面と同等の完全な情報を取得できます。
    
    Args:
        投稿ID: 取得対象の投稿ID
        include_internal: Trueの場合、アンダースコアで始まる内部フィールドも含める（デフォルト: False）
    
    戻り値:
        カスタムフィールドの完全な構造をJSON形式で表示した文字列
    """
    logger.info(f"media_free_content_get_fields_raw called with ID={投稿ID}, include_internal={include_internal}")
    
    async with httpx.AsyncClient() as client:
        try:
            headers = get_auth_headers()
            
            logger.debug(f"Fetching media-free-content post with ID: {投稿ID}")
            response = await client.get(
                f"{WP_SITE_URL}/wp-json/wp/v2/media-free-content/{投稿ID}",
                params={"context": "edit"},
                headers=headers,
                timeout=30.0
            )
            
            logger.debug(f"Response status: {response.status_code}")
            
            # 権限エラーの場合はcontext=editを削除して再試行
            if response.status_code in (401, 403) or (response.status_code != 200 and ("権限" in str(response.text) or "rest_forbidden" in str(response.text))):
                logger.warning("context=editで権限エラーが発生。context=editなしで再試行します。")
                response = await client.get(
                    f"{WP_SITE_URL}/wp-json/wp/v2/media-free-content/{投稿ID}",
                    params={},
                    headers=headers,
                    timeout=30.0
                )
            
            if response.status_code == 404:
                return f"ID {投稿ID} の投稿が見つかりませんでした。"
            
            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_message = error_data.get('message', f'HTTPステータス {response.status_code}')
                logger.error(f"API Error: {response.status_code} - {error_data}")
                return f"エラーが発生しました: {error_message}"
            
            post = response.json()
            logger.debug(f"Post data keys: {list(post.keys())}")
            
            # タイトル情報
            title = post.get('title', {}).get('rendered', 'タイトル未設定')
            status = post.get('status', '不明')
            
            result = f"━━━━━━━━━━━━━━━━━━━━\n"
            result += f"📝 {title}\n"
            result += f"🆔 ID: {post.get('id')} | ステータス: {status}\n"
            result += f"📅 公開日: {post.get('date', 'N/A')} | 最終更新: {post.get('modified', 'N/A')}\n"
            result += f"━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # カスタムフィールドの完全な構造を取得
            fields = _get_custom_fields_from_post(post)
            
            if fields:
                result += _format_fields_for_display(fields, include_internal=include_internal)
            else:
                result += "カスタムフィールドが見つかりませんでした。\n"
                result += f"利用可能なキー: {', '.join(post.keys())}\n"
                # デバッグ用：レスポンスの一部を表示
                result += f"\n【デバッグ情報】\n"
                result += f"レスポンスのサンプル（最初の5キー）:\n"
                for i, key in enumerate(list(post.keys())[:5]):
                    result += f"  - {key}: {type(post[key]).__name__}\n"
            
            result += f"\n🔗 {post.get('link', 'N/A')}\n"
            result += f"✏️ 編集URL: {WP_SITE_URL}/wp-admin/post.php?post={post.get('id')}&action=edit\n"
            
            return result
        
        except Exception as e:
            logger.exception(f"Error in media_free_content_get_fields_raw: {e}")
            return f"エラーが発生しました: {str(e)}"


# ========================================
# ツール9: media-free-content カスタムフィールド更新
# ========================================
async def _media_free_content_handle_update_tool(
    *,
    post_id: int,
    fields_json: str,
    container: str,
    wrap_payload: bool,
) -> str:
    """media-free-content カスタムフィールド更新の共通処理"""
    try:
        data = json.loads(fields_json)
    except json.JSONDecodeError as exc:
        return (
            "❌ JSONの形式に問題があります。\n"
            f"エラー: {exc}\n"
            "例: {\"カスタムフィールド名\": \"値\"}"
        )
    
    if not isinstance(data, dict) or not data:
        return "❌ JSONはキーと値を持つオブジェクト形式で指定してください。"
    
    container = (container or "meta").strip()
    wrap_payload = bool(wrap_payload)
    
    if wrap_payload:
        # containerでラップして送信
        if container not in ("custom_fields", "meta", "acf"):
            return (
                f"❌ container='{container}' はサポートされていません。"
                " 使用可能: custom_fields / meta / acf"
            )
        payload = {container: data}
        summary_fields = data
        field_group = f"media-free-content:{container}"
    else:
        # そのまま送信
        payload = data
        summary_fields = data
        field_group = "media-free-content:raw"
    
    logger.info(
        "[MediaFreeContent] 更新開始 id=%s container=%s wrap=%s",
        post_id,
        container,
        wrap_payload,
    )
    
    try:
        post = await _pilates_wp_post(f"media-free-content/{post_id}", payload)
    except RuntimeError as exc:
        logger.error(
            "[MediaFreeContent] 更新失敗 id=%s : %s",
            post_id,
            exc,
        )
        return f"❌ 更新に失敗しました。\n{exc}"
    
    return _pilates_format_update_summary(post, summary_fields, field_group)


@mcp.tool()
async def media_free_content_update_fields(
    投稿ID: int,
    フィールドJSON: str,
    container: str = "meta",
    wrap_payload: bool = True,
) -> str:
    """
    media-free-content カスタム投稿のカスタムフィールドを更新します。
    
    Args:
        投稿ID: 更新対象の投稿ID
        フィールドJSON: {"フィールド名": "値"} 形式のJSON文字列
        container: custom_fields / meta / acf のいずれか（wrap_payload=True の場合）
        wrap_payload: True で JSON を container 内に包んで送信、False で JSON をそのまま送信
    
    例:
        フィールドJSON: '{"表示エリア": "塚口", "リード文": "説明文"}'
    """
    logger.info(f"media_free_content_update_fields called with ID={投稿ID}")
    
    return await _media_free_content_handle_update_tool(
        post_id=投稿ID,
        fields_json=フィールドJSON,
        container=container,
        wrap_payload=wrap_payload,
    )


def _media_free_content_parse_fields_json(raw: str) -> tuple[dict | None, str | None]:
    """JSON文字列をパース（media-free-content用）"""
    if not raw or not raw.strip():
        return None, None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"❌ JSONの形式が正しくありません: {exc}"
    if not isinstance(data, dict):
        return None, "❌ JSONはオブジェクト（Key/Value形式）で指定してください。"
    return data, None


def _media_free_content_normalize_single_status(status: str | None) -> str:
    """ステータスを正規化（単一ステータス用）"""
    value = (status or "").strip().lower()
    if value in ALLOWED_STATUSES:
        return value
    return "draft"


def _media_free_content_format_post_action_result(action: str, post: dict) -> str:
    """投稿アクション結果をフォーマット"""
    title = post.get('title', {}).get('rendered', 'タイトル未設定')
    status = post.get('status', 'unknown')
    post_id = post.get('id')
    link = post.get('link') or ""
    edit_url = f"{WP_SITE_URL}/wp-admin/post.php?post={post_id}&action=edit" if post_id else "N/A"
    lines = [
        action,
        f"🆔 ID: {post_id} / status: {status}",
        f"📍 タイトル: {title}",
        f"🔗 表示URL: {link or 'N/A'}",
        f"✏️ 編集URL: {edit_url}",
    ]
    return "\n".join(lines)


# ========================================
# ツール10: media-free-content 投稿作成
# ========================================
@mcp.tool()
async def media_free_content_create_post(
    タイトル: str,
    本文: str = "",
    status: str = "draft",
    フィールドJSON: str = "",
    抜粋: str = "",
    slug: str = ""
) -> str:
    """
    media-free-content カスタム投稿を新規作成します。
    
    Args:
        タイトル: 投稿のタイトル（必須）
        本文: 投稿の本文
        status: 投稿ステータス（"publish" または "draft"、デフォルト: "draft"）
        フィールドJSON: カスタムフィールドのJSON文字列
            例: '{"表示エリア": "塚口", "リード文": "説明文", "目的セクション": [...]}'
        抜粋: 投稿の抜粋
        slug: 投稿のスラッグ
    
    カスタムフィールドの構造:
    - 表示エリア: 文字列（例: "塚口"）
    - リード文: 文字列
    - 目的セクション: 配列
      - 目的名: 文字列
      - スタジオカード: 配列
        - 投稿ID: 数値
        - アクセス: 文字列
        - 料金: 文字列
        - 特徴1: 文字列
        - 特徴2: 文字列
        - 特徴3: 文字列
    """
    logger.info(f"media_free_content_create_post called with タイトル={タイトル}")
    
    clean_title = (タイトル or "").strip()
    if not clean_title:
        return "タイトルを指定してください。"
    
    payload: dict = {
        "title": clean_title,
        "status": _media_free_content_normalize_single_status(status),
    }
    if 本文:
        payload["content"] = 本文
    if 抜粋:
        payload["excerpt"] = 抜粋
    if slug:
        payload["slug"] = slug
    
    fields, error = _media_free_content_parse_fields_json(フィールドJSON)
    if error:
        return error
    if fields:
        payload["meta"] = fields
    
    try:
        post = await _pilates_wp_post("media-free-content", payload)
    except RuntimeError as exc:
        logger.error("[MediaFreeContent] 投稿作成失敗: %s", exc)
        return f"❌ 作成に失敗しました。\n{exc}"
    
    return _media_free_content_format_post_action_result("✅ media-free-content 投稿を作成しました", post)


# ========================================
# ツール11: media-free-content 投稿更新
# ========================================
@mcp.tool()
async def media_free_content_update_post(
    投稿ID: int,
    タイトル: str = "",
    本文: str = "",
    status: str = "",
    フィールドJSON: str = "",
    抜粋: str = "",
    slug: str = ""
) -> str:
    """
    media-free-content 投稿のタイトル / 本文 / ステータス / メタ情報を更新します。
    
    Args:
        投稿ID: 更新対象の投稿ID（必須）
        タイトル: 新しいタイトル
        本文: 新しい本文
        status: 新しいステータス（"publish" または "draft"）
        フィールドJSON: カスタムフィールドのJSON文字列
            例: '{"表示エリア": "塚口", "リード文": "説明文"}'
        抜粋: 新しい抜粋
        slug: 新しいスラッグ
    
    カスタムフィールドの構造:
    - 表示エリア: 文字列
    - リード文: 文字列
    - 目的セクション: 配列（ネストされた構造）
    """
    logger.info(f"media_free_content_update_post called with ID={投稿ID}")
    
    payload: dict = {}
    if タイトル:
        payload["title"] = タイトル
    if 本文:
        payload["content"] = 本文
    if 抜粋:
        payload["excerpt"] = 抜粋
    if slug:
        payload["slug"] = slug
    if status:
        payload["status"] = _media_free_content_normalize_single_status(status)
    
    fields, error = _media_free_content_parse_fields_json(フィールドJSON)
    if error:
        return error
    if fields:
        payload.setdefault("meta", {}).update(fields)
    
    if not payload:
        return "更新項目を1つ以上指定してください。"
    
    try:
        post = await _pilates_wp_post(f"media-free-content/{投稿ID}", payload)
    except RuntimeError as exc:
        logger.error("[MediaFreeContent] 投稿更新失敗: %s", exc)
        return f"❌ 更新に失敗しました。\n{exc}"
    
    return _media_free_content_format_post_action_result("✅ media-free-content 投稿を更新しました", post)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 通常投稿（posts）用ツール
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ========================================
# ツール14: 通常投稿作成
# ========================================
@mcp.tool()
async def post_create(
    タイトル: str,
    本文: str = "",
    status: str = "draft",
    フィールドJSON: str = "",
    抜粋: str = "",
    slug: str = ""
) -> str:
    """
    通常投稿（post）を新規作成します。
    
    Args:
        タイトル: 投稿のタイトル（必須）
        本文: 投稿の本文
        status: 投稿ステータス（"publish" または "draft"、デフォルト: "draft"）
        フィールドJSON: カスタムフィールドのJSON文字列
        抜粋: 投稿の抜粋
        slug: 投稿のスラッグ
    
    例:
        フィールドJSON: '{"カスタムフィールド名": "値"}'
    """
    logger.info(f"post_create called with タイトル={タイトル}")
    
    clean_title = (タイトル or "").strip()
    if not clean_title:
        return "タイトルを指定してください。"
    
    payload: dict = {
        "title": clean_title,
        "status": _pilates_normalize_single_status(status),
    }
    if 本文:
        payload["content"] = 本文
    if 抜粋:
        payload["excerpt"] = 抜粋
    if slug:
        payload["slug"] = slug
    
    fields, error = _pilates_parse_fields_json(フィールドJSON)
    if error:
        return error
    if fields:
        payload["meta"] = fields
    
    try:
        post = await _pilates_wp_post("posts", payload)
    except RuntimeError as exc:
        logger.error("[Posts] 投稿作成失敗: %s", exc)
        return f"❌ 作成に失敗しました。\n{exc}"
    
    return _pilates_format_post_action_result("✅ 通常投稿を作成しました", post)


# ========================================
# ツール15: 通常投稿更新
# ========================================
@mcp.tool()
async def post_update(
    投稿ID: int,
    タイトル: str = "",
    本文: str = "",
    status: str = "",
    フィールドJSON: str = "",
    抜粋: str = "",
    slug: str = ""
) -> str:
    """
    通常投稿（post）のタイトル / 本文 / ステータス / メタ情報を更新します。
    
    Args:
        投稿ID: 更新対象の投稿ID（必須）
        タイトル: 新しいタイトル
        本文: 新しい本文
        status: 新しいステータス（"publish" または "draft"）
        フィールドJSON: カスタムフィールドのJSON文字列
        抜粋: 新しい抜粋
        slug: 新しいスラッグ
    
    例:
        フィールドJSON: '{"カスタムフィールド名": "値"}'
    """
    logger.info(f"post_update called with ID={投稿ID}")
    
    payload: dict = {}
    if タイトル:
        payload["title"] = タイトル
    if 本文:
        payload["content"] = 本文
    if 抜粋:
        payload["excerpt"] = 抜粋
    if slug:
        payload["slug"] = slug
    if status:
        payload["status"] = _pilates_normalize_single_status(status)
    
    fields, error = _pilates_parse_fields_json(フィールドJSON)
    if error:
        return error
    if fields:
        payload.setdefault("meta", {}).update(fields)
    
    if not payload:
        return "更新項目を1つ以上指定してください。"
    
    try:
        post = await _pilates_wp_post(f"posts/{投稿ID}", payload)
    except RuntimeError as exc:
        logger.error("[Posts] 投稿更新失敗: %s", exc)
        return f"❌ 更新に失敗しました。\n{exc}"
    
    return _pilates_format_post_action_result("✅ 通常投稿を更新しました", post)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# サーバー起動
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
