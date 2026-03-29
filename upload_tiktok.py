"""
Mystery Shorts Pipeline — upload_tiktok.py
TikTok Content Posting API v2 投稿

前提:
  - TikTok for Developers でアプリ審査通過が必要（2〜4週間）
  - TIKTOK_ACCESS_TOKEN の設定が必要
"""

import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"
CHUNK_SIZE = 10 * 1024 * 1024  # 10MB


def upload_tiktok(
    video_path: str,
    title: str,
    description: str = "",
) -> str:
    """
    TikTok に動画を投稿する。

    Args:
        video_path: 動画ファイルパス
        title: 動画タイトル（TikTok では description として扱われる）
        description: 追加説明（任意）

    Returns:
        publish_id
    """
    access_token = os.environ.get("TIKTOK_ACCESS_TOKEN")
    if not access_token:
        raise EnvironmentError("TIKTOK_ACCESS_TOKEN が設定されていません")

    video_file = Path(video_path)
    if not video_file.exists():
        raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")

    file_size = video_file.stat().st_size

    # Step 1: アップロード初期化（upload_url 取得）
    logger.info("TikTok: アップロード初期化中...")
    publish_id, upload_url = _init_upload(access_token, title, file_size)
    logger.info(f"publish_id: {publish_id}")

    # Step 2: 動画ファイルアップロード
    logger.info("TikTok: 動画アップロード中...")
    _upload_file(upload_url, video_path, file_size)

    logger.info(f"TikTok 投稿完了: publish_id={publish_id}")
    return publish_id


def _init_upload(
    access_token: str, title: str, file_size: int
) -> tuple[str, str]:
    """アップロードを初期化し (publish_id, upload_url) を返す"""
    url = f"{TIKTOK_API_BASE}/post/publish/video/init/"
    payload = {
        "post_info": {
            "title": title,
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": CHUNK_SIZE,
            "total_chunk_count": (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE,
        },
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"TikTok 初期化エラー {e.code}: {error_body}") from e

    if result.get("error", {}).get("code", "ok") != "ok":
        raise RuntimeError(f"TikTok 初期化失敗: {result}")

    data_block = result.get("data", {})
    publish_id = data_block.get("publish_id")
    upload_url = data_block.get("upload_url")

    if not publish_id or not upload_url:
        raise RuntimeError(f"publish_id/upload_url 取得失敗: {result}")

    return publish_id, upload_url


def _upload_file(upload_url: str, video_path: str, file_size: int) -> None:
    """動画ファイルをチャンク単位でアップロードする"""
    total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

    with open(video_path, "rb") as f:
        for chunk_index in range(total_chunks):
            chunk_data = f.read(CHUNK_SIZE)
            chunk_size = len(chunk_data)
            start_byte = chunk_index * CHUNK_SIZE
            end_byte = start_byte + chunk_size - 1

            logger.info(
                f"  チャンク [{chunk_index + 1}/{total_chunks}]: "
                f"bytes {start_byte}-{end_byte}/{file_size}"
            )

            req = urllib.request.Request(
                upload_url,
                data=chunk_data,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
                    "Content-Length": str(chunk_size),
                },
                method="PUT",
            )

            try:
                with urllib.request.urlopen(req, timeout=120):
                    pass
            except urllib.error.HTTPError as e:
                # 206 Partial Content は正常
                if e.code == 206:
                    continue
                error_body = e.read().decode("utf-8")
                raise RuntimeError(
                    f"TikTok チャンクアップロードエラー {e.code}: {error_body}"
                ) from e
