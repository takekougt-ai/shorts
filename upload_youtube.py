"""
Mystery Shorts Pipeline — upload_youtube.py
YouTube Shorts 投稿
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
YOUTUBE_API_SERVICE = "youtube"
YOUTUBE_API_VERSION = "v3"
CHUNK_SIZE = 5 * 1024 * 1024  # 5MB


def upload_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: list,
) -> str:
    """
    YouTube Shorts に動画をアップロードする。

    Args:
        video_path: 動画ファイルパス
        title: 動画タイトル
        description: 動画説明文
        tags: タグリスト

    Returns:
        アップロードされた動画ID
    """
    credentials_json = os.environ.get("YOUTUBE_CREDENTIALS")
    if not credentials_json:
        raise EnvironmentError("YOUTUBE_CREDENTIALS が設定されていません")

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    credentials_info = json.loads(credentials_json)
    credentials = Credentials.from_authorized_user_info(
        credentials_info, YOUTUBE_SCOPES
    )

    youtube = build(YOUTUBE_API_SERVICE, YOUTUBE_API_VERSION, credentials=credentials)

    # Shorts 用に description と tags を調整
    shorts_description = description + "\n\n#Shorts"
    shorts_tags = tags + ["Shorts"]

    body = {
        "snippet": {
            "title": title,
            "description": shorts_description,
            "tags": shorts_tags,
            "categoryId": "22",  # People & Blogs
            "defaultLanguage": "ja",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        chunksize=CHUNK_SIZE,
        resumable=True,
        mimetype="video/mp4",
    )

    logger.info(f"YouTube アップロード開始: {title}")
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            logger.info(f"  アップロード進捗: {progress}%")

    video_id = response.get("id")
    logger.info(f"YouTube アップロード完了: https://www.youtube.com/shorts/{video_id}")
    return video_id


def generate_token():
    """
    OAuth2 認証フローを実行して token.json を生成する。
    初回セットアップ時のみ使用: python upload_youtube.py --generate-token
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_secrets_file = "client_secrets.json"
    if not Path(client_secrets_file).exists():
        print(
            f"ERROR: {client_secrets_file} が見つかりません。"
            "Google Cloud Console からダウンロードしてください。"
        )
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, YOUTUBE_SCOPES)
    credentials = flow.run_local_server(port=0)

    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes),
    }

    with open("token.json", "w") as f:
        json.dump(token_data, f, indent=2)

    print("token.json を生成しました。")
    print("この内容を YOUTUBE_CREDENTIALS シークレットに設定してください:")
    print(json.dumps(token_data))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube Shorts アップローダー")
    parser.add_argument(
        "--generate-token",
        action="store_true",
        help="OAuth2 トークンを生成して token.json に保存する",
    )
    args = parser.parse_args()

    if args.generate_token:
        generate_token()
    else:
        parser.print_help()
