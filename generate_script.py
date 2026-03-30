"""
Mystery Shorts Pipeline — generate_script.py
Gemini 2.5 Flash で台本JSON生成
"""

import os
import json
import logging
import re
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    f"/{GEMINI_MODEL}:generateContent"
)

SYSTEM_PROMPT = """あなたは日本語ショート動画の台本ライターです。
以下のテーマカテゴリからひとつ選び、視聴者を引き込む台本をJSON形式で生成してください。

テーマカテゴリ（毎回異なるものを選ぶこと）:
- 星座占い（今週の運勢、恋愛運、金運など）
- 日本の都市伝説（未解決事件、怪談、不思議な場所）
- 世界の不思議（未解明の遺跡、超常現象、未確認生物）
- 風水・開運（部屋の配置、運を呼ぶアイテム、NGな習慣）
- 予言・予知夢（ノストラダムス、ジュスト、現代の予言）
- 心霊体験（実話怪談、霊的スポット、除霊の話）
- 陰謀論（政府の隠蔽、フリーメイソン、月面着陸の謎）

出力は以下のJSONスキーマに従ってください。JSONのみを出力し、説明文は不要です。

{
  "theme": "テーマ名（例: 日本の都市伝説）",
  "title": "動画タイトル（25〜40字、SEO最適化、数字や衝撃ワードを含める）",
  "description": "動画説明文（150〜200字、関連ハッシュタグを末尾に含める）",
  "tags": ["タグ1", "タグ2", ..., "タグ8"],
  "narration_segments": [
    {
      "text": "ナレーションテキスト（40〜60字）",
      "image_keyword": "Pexels検索用英語キーワード（1〜3単語）"
    }
  ],
  "bgm_mood": "mysterious | dark | ethereal | dramatic のいずれか"
}

narration_segmentsは8〜10個、各40〜60字で構成してください。
冒頭は視聴者の興味を引くフック、末尾はチャンネル登録を促すCTAで締めてください。"""


def generate_script() -> dict:
    """Gemini 2.5 Flash で台本JSONを生成して返す"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY が設定されていません")

    url = f"{GEMINI_API_URL}?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [{"text": SYSTEM_PROMPT}],
                "role": "user",
            }
        ],
        "generationConfig": {
            "temperature": 1.0,
            "maxOutputTokens": 4096,
        },
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    logger.info(f"Gemini API リクエスト送信: {GEMINI_MODEL}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"Gemini API エラー {e.code}: {error_body}") from e

    # レスポンスからテキスト抽出
    try:
        raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Gemini レスポンス解析失敗: {result}") from e

    # ```json ... ``` の除去
    raw_text = re.sub(r"^```json\s*", "", raw_text.strip())
    raw_text = re.sub(r"\s*```$", "", raw_text.strip())

    try:
        script = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON解析失敗。生テキスト: {raw_text[:500]}") from e

    _validate_script(script)
    logger.info(f"台本生成完了: {script['title']}")
    return script


def _validate_script(script: dict) -> None:
    """台本スキーマの簡易バリデーション"""
    required_keys = {"theme", "title", "description", "tags", "narration_segments", "bgm_mood"}
    missing = required_keys - set(script.keys())
    if missing:
        raise ValueError(f"台本に必須キーがありません: {missing}")

    if not isinstance(script["narration_segments"], list) or len(script["narration_segments"]) < 1:
        raise ValueError("narration_segments が空です")

    valid_moods = {"mysterious", "dark", "ethereal", "dramatic"}
    if script.get("bgm_mood") not in valid_moods:
        logger.warning(f"不正なbgm_mood: {script.get('bgm_mood')}。'mysterious'にフォールバック")
        script["bgm_mood"] = "mysterious"
