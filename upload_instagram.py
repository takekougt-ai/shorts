"""
Mystery Shorts Pipeline — upload_instagram.py
Instagram Reels 投稿（Instagram Graph API v19.0）

前提:
  - ビジネスアカウント + Facebookページ紐付けが必要
  - 動画は公開アクセス可能なURL（Google Drive / GCS / S3）が必要
"""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
POLLING_INTERVAL = 10  # 秒
POLLING_TIMEOUT = 300  # 5分


def upload_instagram(
    video_url: str,
    caption: str,
) -> str:
    """
    Instagram Reels に動画を投稿する。

    Args:
        video_url: 公開アクセス可能な動画URL（ローカルファイル不可）
        caption: キャプション文（ハッシュタグ含む）

    Returns:
        投稿されたメディアID
    """
    access_token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    user_id = os.environ.get("INSTAGRAM_USER_ID")
    if not access_token:
        raise EnvironmentError("INSTAGRAM_ACCESS_TOKEN が設定されていません")
    if not user_id:
        raise EnvironmentError("INSTAGRAM_USER_ID が設定されていません")

    # Step 1: コンテナ作成
    logger.info("Instagram: メディアコンテナ作成中...")
    container_id = _create_container(access_token, user_id, video_url, caption)
    logger.info(f"コンテナID: {container_id}")

    # Step 2: 処理完了待機（ポーリング）
    logger.info("Instagram: メディア処理待機中...")
    _wait_for_container(access_token, container_id)

    # Step 3: 公開
    logger.info("Instagram: メディア公開中...")
    media_id = _publish_container(access_token, user_id, container_id)
    logger.info(f"Instagram 投稿完了: media_id={media_id}")
    return media_id


def _create_container(
    access_token: str, user_id: str, video_url: str, caption: str
) -> str:
    """メディアコンテナを作成してコンテナIDを返す"""
    url = f"{GRAPH_API_BASE}/{user_id}/media"
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true",
        "access_token": access_token,
    }
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"Instagram コンテナ作成エラー {e.code}: {error_body}") from e

    container_id = result.get("id")
    if not container_id:
        raise RuntimeError(f"コンテナID取得失敗: {result}")
    return container_id


def _wait_for_container(access_token: str, container_id: str) -> None:
    """コンテナの処理完了を最大 POLLING_TIMEOUT 秒待機する"""
    elapsed = 0
    while elapsed < POLLING_TIMEOUT:
        params = urllib.parse.urlencode(
            {
                "fields": "status_code,status",
                "access_token": access_token,
            }
        )
        url = f"{GRAPH_API_BASE}/{container_id}?{params}"
        req = urllib.request.Request(url, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError(f"Instagram ポーリングエラー {e.code}: {error_body}") from e

        status_code = result.get("status_code", "")
        logger.info(f"  ステータス: {status_code} ({elapsed}秒経過)")

        if status_code == "FINISHED":
            return
        if status_code == "ERROR":
            raise RuntimeError(f"Instagram メディア処理エラー: {result}")

        time.sleep(POLLING_INTERVAL)
        elapsed += POLLING_INTERVAL

    raise TimeoutError(f"Instagram メディア処理タイムアウト ({POLLING_TIMEOUT}秒)")


def _publish_container(
    access_token: str, user_id: str, container_id: str
) -> str:
    """コンテナを公開してメディアIDを返す"""
    url = f"{GRAPH_API_BASE}/{user_id}/media_publish"
    params = {
        "creation_id": container_id,
        "access_token": access_token,
    }
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"Instagram 公開エラー {e.code}: {error_body}") from e

    media_id = result.get("id")
    if not media_id:
        raise RuntimeError(f"メディアID取得失敗: {result}")
    return media_id
