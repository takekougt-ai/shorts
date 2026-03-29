"""
Mystery Shorts Pipeline — fetch_images.py
Pexels API で背景画像取得
"""

import os
import logging
import random
import urllib.request
import urllib.error
import urllib.parse
import json
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

PEXELS_API_URL = "https://api.pexels.com/v1/search"
IMAGES_OUTPUT_DIR = Path("output/images")

FALLBACK_KEYWORDS = [
    "mystery",
    "night sky",
    "dark forest",
    "fog",
    "ancient ruins",
    "universe",
    "shadow",
    "moonlight",
]


def fetch_images(narration_segments: List[dict]) -> List[str]:
    """
    ナレーションセグメントの image_keyword を元に Pexels から縦型画像を取得する。

    Args:
        narration_segments: [{"text": str, "image_keyword": str}, ...]

    Returns:
        画像ファイルパスのリスト（segments と同数）
    """
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        raise EnvironmentError("PEXELS_API_KEY が設定されていません")

    IMAGES_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image_paths = []

    for i, segment in enumerate(narration_segments):
        keyword = segment.get("image_keyword", "mystery")
        output_path = IMAGES_OUTPUT_DIR / f"bg_{i:02d}.jpg"

        logger.info(f"  画像取得 [{i+1}/{len(narration_segments)}]: '{keyword}'")
        success = _fetch_single_image(api_key, keyword, str(output_path))

        if not success:
            # フォールバックキーワードで再試行
            logger.warning(f"  '{keyword}' で画像取得失敗。フォールバック試行...")
            for fallback_kw in random.sample(FALLBACK_KEYWORDS, len(FALLBACK_KEYWORDS)):
                success = _fetch_single_image(api_key, fallback_kw, str(output_path))
                if success:
                    logger.info(f"  フォールバック成功: '{fallback_kw}'")
                    break

        if not success:
            # 最終フォールバック: PIL で星空背景を生成
            logger.warning(f"  全キーワード失敗。生成フォールバック画像を使用")
            _generate_fallback_image(str(output_path))

        image_paths.append(str(output_path))

    return image_paths


def _fetch_single_image(api_key: str, keyword: str, output_path: str) -> bool:
    """Pexels から1枚の縦型画像を取得して保存する。成功時 True を返す。"""
    page = random.randint(1, 3)
    params = urllib.parse.urlencode(
        {
            "query": keyword,
            "orientation": "portrait",
            "size": "large",
            "per_page": 10,
            "page": page,
        }
    )
    url = f"{PEXELS_API_URL}?{params}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": api_key},
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as e:
        logger.warning(f"  Pexels API エラー ({keyword}): {e}")
        return False

    photos = data.get("photos", [])
    if not photos:
        return False

    # ランダムに1枚選択
    photo = random.choice(photos)
    image_url = photo.get("src", {}).get("large2x") or photo.get("src", {}).get("large")
    if not image_url:
        return False

    try:
        urllib.request.urlretrieve(image_url, output_path)
        return True
    except Exception as e:
        logger.warning(f"  画像ダウンロード失敗 ({image_url}): {e}")
        return False


def _generate_fallback_image(output_path: str) -> None:
    """PIL で星空の黒背景画像を生成する（Pexels が全て失敗した場合）"""
    try:
        from PIL import Image, ImageDraw
        import random as rnd

        img = Image.new("RGB", (1080, 1920), color=(5, 5, 20))
        draw = ImageDraw.Draw(img)

        # 星を描画
        for _ in range(300):
            x = rnd.randint(0, 1080)
            y = rnd.randint(0, 1920)
            radius = rnd.choice([1, 1, 1, 2, 2, 3])
            brightness = rnd.randint(150, 255)
            draw.ellipse(
                [x - radius, y - radius, x + radius, y + radius],
                fill=(brightness, brightness, brightness),
            )

        img.save(output_path, "JPEG", quality=90)
        logger.info(f"  フォールバック星空画像を生成: {output_path}")
    except ImportError:
        logger.error("PIL がインストールされていません。空白画像を生成します")
        # 最小限のJPEGバイナリ（空白）
        _write_minimal_image(output_path)


def _write_minimal_image(output_path: str) -> None:
    """PIL なしで最小JPEGファイルを書き出す（緊急フォールバック）"""
    import subprocess
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "color=c=black:size=1080x1920:rate=1",
                "-frames:v", "1", output_path,
            ],
            check=True,
            capture_output=True,
        )
    except Exception as e:
        logger.error(f"ffmpeg フォールバック画像生成失敗: {e}")
