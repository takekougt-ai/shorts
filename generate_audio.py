"""
Mystery Shorts Pipeline — generate_audio.py
ElevenLabs API で音声生成
"""

import os
import json
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
ELEVENLABS_TIMESTAMPS_URL = (
    "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
)
ELEVENLABS_VOICES_URL = "https://api.elevenlabs.io/v1/voices"
DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # Adam（ライブラリボイス・有料プランのみ）
TTS_MODEL = "eleven_multilingual_v2"
AUDIO_OUTPUT_DIR = Path("output/audio")


def generate_audio_segments(narration_segments: List[dict]) -> List[dict]:
    """
    ナレーションセグメントリストから音声ファイルを生成する。

    Args:
        narration_segments: [{"text": str, "image_keyword": str}, ...]

    Returns:
        [{"index": int, "text": str, "audio_path": str, "duration": float}, ...]
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise EnvironmentError("ELEVENLABS_API_KEY が設定されていません")

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
    AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for i, segment in enumerate(narration_segments):
        text = segment["text"]
        audio_path = AUDIO_OUTPUT_DIR / f"segment_{i:02d}.mp3"

        logger.info(f"  音声生成 [{i+1}/{len(narration_segments)}]: {text[:30]}...")
        voice_id = _generate_single_audio_with_fallback(api_key, voice_id, text, str(audio_path))

        duration = _get_audio_duration(str(audio_path))
        results.append(
            {
                "index": i,
                "text": text,
                "audio_path": str(audio_path),
                "duration": duration,
            }
        )

    return results


def generate_audio_with_timestamps(
    narration_segments: List[dict],
) -> List[dict]:
    """
    タイムスタンプ付き音声生成（字幕同期用）。

    Returns:
        [{"index": int, "text": str, "audio_path": str, "duration": float,
          "word_timestamps": [{"word": str, "start": float, "end": float}]}, ...]
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise EnvironmentError("ELEVENLABS_API_KEY が設定されていません")

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
    AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for i, segment in enumerate(narration_segments):
        text = segment["text"]
        audio_path = AUDIO_OUTPUT_DIR / f"segment_{i:02d}.mp3"

        logger.info(f"  タイムスタンプ付き音声生成 [{i+1}/{len(narration_segments)}]")
        word_timestamps = _generate_audio_with_timestamps(
            api_key, voice_id, text, str(audio_path)
        )

        duration = _get_audio_duration(str(audio_path))
        results.append(
            {
                "index": i,
                "text": text,
                "audio_path": str(audio_path),
                "duration": duration,
                "word_timestamps": word_timestamps,
            }
        )

    return results


def _get_usable_voice_id(api_key: str) -> str:
    """アカウントで使用可能なボイスIDを取得して返す"""
    req = urllib.request.Request(
        ELEVENLABS_VOICES_URL,
        headers={"xi-api-key": api_key},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"ElevenLabs ボイス一覧取得失敗: {e}") from e

    voices = data.get("voices", [])
    # cloned / generated / professional は自分のボイスで使用可能
    for category in ("cloned", "generated", "professional"):
        for v in voices:
            if v.get("category") == category:
                logger.info(f"  フォールバックボイス使用: {v['name']} ({v['voice_id']})")
                return v["voice_id"]

    # premade ボイスを最後の手段として試す
    for v in voices:
        if v.get("category") == "premade":
            logger.info(f"  premadeボイスで試行: {v['name']} ({v['voice_id']})")
            return v["voice_id"]

    raise RuntimeError(
        "使用可能なボイスが見つかりません。ElevenLabs で Voice Design からボイスを作成してください。"
    )


def _generate_single_audio_with_fallback(
    api_key: str, voice_id: str, text: str, output_path: str
) -> str:
    """402エラー時にアカウントのボイスへ自動フォールバックしてTTSを実行。使用したvoice_idを返す"""
    try:
        _generate_single_audio(api_key, voice_id, text, output_path)
        return voice_id
    except RuntimeError as e:
        if "402" not in str(e) and "payment" not in str(e).lower():
            raise
        logger.warning(f"  ボイス '{voice_id}' が使用不可。アカウントのボイスを検索中...")
        fallback_id = _get_usable_voice_id(api_key)
        _generate_single_audio(api_key, fallback_id, text, output_path)
        return fallback_id


def _generate_single_audio(
    api_key: str, voice_id: str, text: str, output_path: str
) -> None:
    """ElevenLabs TTS API で単一音声ファイルを生成"""
    url = ELEVENLABS_API_URL.format(voice_id=voice_id)
    payload = {
        "text": text,
        "model_id": TTS_MODEL,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            audio_data = resp.read()
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        if e.code == 402:
            raise RuntimeError(
                "ElevenLabs 402エラー: このボイスは無料プランでは使用できません。"
                "ElevenLabs の My Voices からボイスIDを取得して "
                "ELEVENLABS_VOICE_ID シークレットを更新してください。"
            ) from e
        raise RuntimeError(
            f"ElevenLabs API エラー {e.code}: {error_body}"
        ) from e

    with open(output_path, "wb") as f:
        f.write(audio_data)


def _generate_audio_with_timestamps(
    api_key: str, voice_id: str, text: str, output_path: str
) -> list:
    """タイムスタンプ付き音声生成API呼び出し"""
    url = ELEVENLABS_TIMESTAMPS_URL.format(voice_id=voice_id)
    payload = {
        "text": text,
        "model_id": TTS_MODEL,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(
            f"ElevenLabs Timestamps API エラー {e.code}: {error_body}"
        ) from e

    # Base64エンコードされた音声データをデコードして保存
    import base64
    audio_b64 = result.get("audio_base64", "")
    if audio_b64:
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(audio_b64))

    # タイムスタンプを抽出
    alignment = result.get("alignment", {})
    chars = alignment.get("characters", [])
    char_starts = alignment.get("character_start_times_seconds", [])
    char_ends = alignment.get("character_end_times_seconds", [])

    # 単語単位に集約
    word_timestamps = []
    current_word = ""
    word_start = 0.0
    for ch, start, end in zip(chars, char_starts, char_ends):
        if ch == " " and current_word:
            word_timestamps.append(
                {"word": current_word, "start": word_start, "end": end}
            )
            current_word = ""
        else:
            if not current_word:
                word_start = start
            current_word += ch
    if current_word:
        word_timestamps.append(
            {"word": current_word, "start": word_start, "end": char_ends[-1]}
        )

    return word_timestamps


def _get_audio_duration(audio_path: str) -> float:
    """音声ファイルの再生時間を取得（fallback: 5秒）"""
    try:
        from moviepy.audio.io.AudioFileClip import AudioFileClip

        with AudioFileClip(audio_path) as clip:
            return clip.duration
    except Exception as e:
        logger.warning(f"音声長取得失敗 ({audio_path}): {e}。5秒でフォールバック")
        return 5.0
