"""
Mystery Shorts Pipeline — create_video.py
MoviePy で縦型ショート動画を合成
"""

import logging
import os
import random
import textwrap
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# ImageMagick のパスを明示的に設定（GitHub Actions 環境対応）
try:
    from moviepy.config import change_settings
    change_settings({"IMAGEMAGICK_BINARY": "/usr/bin/convert"})
except Exception:
    pass

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
FONT_NAME = "Noto-Sans-CJK-JP"
FONT_SIZE = 62
TEXT_WRAP_WIDTH = 22
TEXT_POSITION_Y_RATIO = 0.72
TEXT_COLOR = "white"
TEXT_STROKE_COLOR = "black"
TEXT_STROKE_WIDTH = 2.5
BGM_VOLUME = 0.15
BGM_DIR = Path("bgm")


def create_video(
    segments: List[dict],
    audio_segments: List[dict],
    image_paths: List[str],
    bgm_mood: str,
    output_path: str,
) -> None:
    """
    セグメントを合成して縦型(1080x1920) mp4 を書き出す。

    Args:
        segments: [{"text": str, "image_keyword": str}, ...]
        audio_segments: [{"index": int, "text": str, "audio_path": str, "duration": float}, ...]
        image_paths: 背景画像ファイルパスのリスト
        bgm_mood: BGMムード ("mysterious"|"dark"|"ethereal"|"dramatic")
        output_path: 出力mp4ファイルパス
    """
    from moviepy.editor import (
        AudioFileClip,
        CompositeAudioClip,
        CompositeVideoClip,
        ImageClip,
        concatenate_videoclips,
    )

    clips = []
    for i, (seg, audio_seg) in enumerate(zip(segments, audio_segments)):
        img_path = image_paths[i] if i < len(image_paths) else image_paths[-1]
        duration = audio_seg["duration"]
        text = seg["text"]

        # 背景画像クリップ
        bg_clip = _make_image_clip(img_path, duration)

        # テキストクリップ
        txt_clip = _make_text_clip(text, duration)

        # 音声クリップ
        audio_clip = AudioFileClip(audio_seg["audio_path"])

        # セグメントクリップを合成
        segment_clip = CompositeVideoClip([bg_clip, txt_clip]).set_duration(duration)
        segment_clip = segment_clip.set_audio(audio_clip)
        clips.append(segment_clip)

    # 全セグメントを結合
    final_video = concatenate_videoclips(clips, method="compose")

    # BGMミックス
    bgm_path = _select_bgm(bgm_mood)
    if bgm_path:
        final_video = _mix_bgm(final_video, bgm_path)

    # 書き出し
    logger.info(f"動画書き出し中: {output_path}")
    final_video.write_videofile(
        output_path,
        fps=VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile="output/temp_audio.m4a",
        remove_temp=True,
        logger=None,
    )
    logger.info(f"動画書き出し完了: {output_path}")


def _make_image_clip(img_path: str, duration: float):
    """画像をカバーフィットで縦型(1080x1920)にリサイズしたImageClipを返す"""
    from moviepy.editor import ImageClip
    from PIL import Image
    import numpy as np

    img = Image.open(img_path).convert("RGB")
    img_w, img_h = img.size

    # カバーフィット: 縦横比を保ちつつ全面を埋める
    scale = max(VIDEO_WIDTH / img_w, VIDEO_HEIGHT / img_h)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # 中央クロップ
    left = (new_w - VIDEO_WIDTH) // 2
    top = (new_h - VIDEO_HEIGHT) // 2
    img = img.crop((left, top, left + VIDEO_WIDTH, top + VIDEO_HEIGHT))

    frame = np.array(img)
    return ImageClip(frame).set_duration(duration)


def _make_text_clip(text: str, duration: float):
    """字幕テキストクリップを生成して返す"""
    from moviepy.editor import TextClip

    # 22文字で折り返し
    wrapped = "\n".join(textwrap.wrap(text, width=TEXT_WRAP_WIDTH))

    txt_clip = TextClip(
        wrapped,
        fontsize=FONT_SIZE,
        font=FONT_NAME,
        color=TEXT_COLOR,
        stroke_color=TEXT_STROKE_COLOR,
        stroke_width=TEXT_STROKE_WIDTH,
        method="caption",
        size=(VIDEO_WIDTH - 80, None),
        align="center",
    )

    y_pos = int(VIDEO_HEIGHT * TEXT_POSITION_Y_RATIO)
    txt_clip = txt_clip.set_position(("center", y_pos)).set_duration(duration)
    return txt_clip


def _select_bgm(mood: str) -> str | None:
    """BGMファイルを選択して返す。見つからなければ None"""
    mood_dir = BGM_DIR / mood
    if mood_dir.exists():
        mp3_files = list(mood_dir.glob("*.mp3"))
        if mp3_files:
            return str(random.choice(mp3_files))

    # フォールバック: bgm/ 直下
    if BGM_DIR.exists():
        mp3_files = list(BGM_DIR.glob("*.mp3"))
        if mp3_files:
            logger.warning(f"BGMムード '{mood}' のフォルダなし。bgm/ 直下から選択")
            return str(random.choice(mp3_files))

    logger.warning("BGMファイルが見つかりません。BGMなしで合成します")
    return None


def _mix_bgm(video, bgm_path: str):
    """BGMを15%ボリュームでミックスしたビデオクリップを返す"""
    from moviepy.editor import AudioFileClip, CompositeAudioClip, afx

    video_duration = video.duration

    bgm_clip = AudioFileClip(bgm_path)
    # 動画尺に合わせてループまたはカット
    if bgm_clip.duration < video_duration:
        bgm_clip = afx.audio_loop(bgm_clip, duration=video_duration)
    else:
        bgm_clip = bgm_clip.subclip(0, video_duration)

    bgm_clip = bgm_clip.volumex(BGM_VOLUME)

    mixed_audio = CompositeAudioClip([video.audio, bgm_clip])
    return video.set_audio(mixed_audio)
