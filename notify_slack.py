"""
Mystery Shorts Pipeline — notify_slack.py
Slack Incoming Webhook で完了・エラー通知
"""

import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)


def notify_slack(
    theme: str,
    title: str,
    video_path: str,
    youtube_url: str = None,
    instagram_url: str = None,
    error: str = None,
) -> None:
    """
    Slack Incoming Webhook で通知を送信する。

    Args:
        theme: 動画テーマ
        title: 動画タイトル
        video_path: 生成された動画ファイルパス
        youtube_url: YouTube Shorts URL（任意）
        instagram_url: Instagram Reels URL（任意）
        error: エラーメッセージ（失敗時）
    """
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL が設定されていません。Slack通知をスキップします")
        return

    if error:
        payload = _build_error_payload(theme, title, error)
    else:
        payload = _build_success_payload(
            theme, title, video_path, youtube_url, instagram_url
        )

    _send_webhook(webhook_url, payload)


def notify_slack_error(error_message: str, step: str = "") -> None:
    """
    パイプラインエラーを Slack に通知する。

    Args:
        error_message: エラーメッセージ
        step: 失敗したステップ名（任意）
    """
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL が設定されていません。Slack通知をスキップします")
        return

    step_info = f" (ステップ: {step})" if step else ""
    payload = {
        "text": f":x: Mystery Shorts Pipeline 失敗{step_info}",
        "attachments": [
            {
                "color": "danger",
                "fields": [
                    {
                        "title": "エラー内容",
                        "value": error_message[:500],
                        "short": False,
                    }
                ],
            }
        ],
    }

    _send_webhook(webhook_url, payload)


def _build_success_payload(
    theme: str,
    title: str,
    video_path: str,
    youtube_url: str = None,
    instagram_url: str = None,
) -> dict:
    """成功通知のペイロードを構築する"""
    video_size = ""
    try:
        size_bytes = Path(video_path).stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        video_size = f"{size_mb:.1f} MB"
    except OSError:
        pass

    fields = [
        {"title": "テーマ", "value": theme, "short": True},
        {"title": "タイトル", "value": title, "short": False},
        {"title": "動画ファイル", "value": video_path, "short": True},
    ]
    if video_size:
        fields.append({"title": "ファイルサイズ", "value": video_size, "short": True})
    if youtube_url:
        fields.append({"title": "YouTube", "value": youtube_url, "short": False})
    if instagram_url:
        fields.append({"title": "Instagram", "value": instagram_url, "short": False})

    return {
        "text": ":clapper: Mystery Shorts 生成完了！",
        "attachments": [
            {
                "color": "good",
                "fields": fields,
            }
        ],
    }


def _build_error_payload(theme: str, title: str, error: str) -> dict:
    """エラー通知のペイロードを構築する"""
    return {
        "text": ":x: Mystery Shorts Pipeline でエラーが発生しました",
        "attachments": [
            {
                "color": "danger",
                "fields": [
                    {"title": "テーマ", "value": theme, "short": True},
                    {"title": "タイトル", "value": title, "short": False},
                    {
                        "title": "エラー内容",
                        "value": str(error)[:500],
                        "short": False,
                    },
                ],
            }
        ],
    }


def _send_webhook(webhook_url: str, payload: dict) -> None:
    """Slack Incoming Webhook にペイロードを送信する"""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            response_text = resp.read().decode("utf-8")
            if response_text != "ok":
                logger.warning(f"Slack Webhook 非okレスポンス: {response_text}")
            else:
                logger.info("Slack通知送信完了")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        logger.error(f"Slack Webhook エラー {e.code}: {error_body}")
    except Exception as e:
        logger.error(f"Slack通知送信失敗: {e}")
