"""
Mystery Shorts Pipeline — main.py
エントリーポイント・パイプライン制御
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

from generate_script import generate_script
from generate_audio import generate_audio_segments
from fetch_images import fetch_images
from create_video import create_video
from upload_youtube import upload_youtube
from notify_slack import notify_slack

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run():
    """メインパイプライン実行"""
    logger.info("=== Mystery Shorts Pipeline 開始 ===")

    # 出力ディレクトリの準備
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = Path("output")
    audio_dir = output_dir / "audio"
    images_dir = output_dir / "images"
    audio_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    video_path = output_dir / f"{timestamp}_shorts.mp4"
    script_path = output_dir / f"{timestamp}_script.json"

    # ① 台本生成
    logger.info("【Step 1/4】台本生成中...")
    script = generate_script()
    logger.info(f"テーマ: {script['theme']}")
    logger.info(f"タイトル: {script['title']}")

    # 台本をJSONで保存
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
    logger.info(f"台本保存: {script_path}")

    # ② 音声生成
    logger.info("【Step 2/4】音声生成中...")
    audio_segments = generate_audio_segments(script["narration_segments"])
    logger.info(f"{len(audio_segments)}個のセグメント音声生成完了")

    # ③ 画像取得
    logger.info("【Step 3/4】背景画像取得中...")
    image_paths = fetch_images(script["narration_segments"])
    logger.info(f"{len(image_paths)}枚の画像取得完了")

    # ④ 動画合成
    logger.info("【Step 4/4】動画合成中...")
    create_video(
        segments=script["narration_segments"],
        audio_segments=audio_segments,
        image_paths=image_paths,
        bgm_mood=script.get("bgm_mood", "mysterious"),
        output_path=str(video_path),
    )
    logger.info(f"動画生成完了: {video_path}")

    # ⑤ YouTube アップロード
    youtube_url = None
    if os.environ.get("YOUTUBE_CREDENTIALS"):
        logger.info("【Step 5/5】YouTube Shorts アップロード中...")
        try:
            video_id = upload_youtube(
                video_path=str(video_path),
                title=script["title"],
                description=script["description"],
                tags=script["tags"],
            )
            youtube_url = f"https://www.youtube.com/shorts/{video_id}"
            logger.info(f"YouTube アップロード完了: {youtube_url}")
        except Exception as e:
            logger.error(f"YouTube アップロード失敗（パイプラインは継続）: {e}")
    else:
        logger.info("YOUTUBE_CREDENTIALS 未設定のためYouTubeアップロードをスキップ")

    # ⑥ Slack通知
    logger.info("Slack通知送信中...")
    notify_slack(
        theme=script["theme"],
        title=script["title"],
        video_path=str(video_path),
        youtube_url=youtube_url,
    )

    logger.info("=== Mystery Shorts Pipeline 完了 ===")
    logger.info(f"出力動画: {video_path}")
    return str(video_path)


if __name__ == "__main__":
    run()
