# Mystery Shorts Pipeline — CLAUDE.md

Claude Code がこのプロジェクトを理解・操作するためのリファレンスドキュメント。

-----

## プロジェクト概要

占い・都市伝説系ショート動画を**全自動生成・投稿**するパイプライン。
GitHub Actions で毎朝9時JST に起動し、動画1本を生成してYouTube Shorts / Instagram Reels / TikTok に投稿する。

### 技術スタック

|レイヤー|使用技術                                                                  |
|----|----------------------------------------------------------------------|
|台本生成|Gemini 2.5 Flash API                                                  |
|音声生成|ElevenLabs API (eleven_multilingual_v2)                               |
|画像取得|Pexels API                                                            |
|動画合成|MoviePy + ffmpeg                                                      |
|投稿  |YouTube Data API v3 / Instagram Graph API / TikTok Content Posting API|
|通知  |Slack Incoming Webhook                                                |
|自動実行|GitHub Actions (cron)                                                 |
|言語  |Python 3.11                                                           |

-----

## ディレクトリ構成

```
mystery-shorts/
├── CLAUDE.md                    # ← このファイル
├── main.py                      # エントリーポイント・パイプライン制御
├── generate_script.py           # Gemini 2.5 Flash で台本JSON生成
├── generate_audio.py            # ElevenLabs TTS 音声生成
├── fetch_images.py              # Pexels API 背景画像取得
├── create_video.py              # MoviePy 動画合成・BGMミックス
├── upload_youtube.py            # YouTube Shorts 投稿
├── upload_instagram.py          # Instagram Reels 投稿
├── upload_tiktok.py             # TikTok 投稿（API審査後）
├── notify_slack.py              # Slack 完了・エラー通知
├── requirements.txt             # Python依存パッケージ
├── bgm/                         # BGM音源（ムード別・各自用意）
│   ├── mysterious/
│   ├── dark/
│   ├── ethereal/
│   └── dramatic/
├── output/                      # 生成ファイル（.gitignore推奨）
│   ├── audio/                   # セグメント音声 segment_00.mp3 ...
│   └── images/                  # 背景画像 bg_00.jpg ...
└── .github/
    └── workflows/
        └── daily_video.yml      # GitHub Actions ワークフロー
```

-----

## パイプラインフロー

```
main.py::run()
  │
  ├─① generate_script.py::generate_script()
  │     Gemini 2.5 Flash にテーマ・台本・タイトル・タグをJSON生成させる
  │     → dict: { theme, title, description, tags, narration_segments[], bgm_mood }
  │
  ├─② generate_audio.py::generate_audio_segments(narration_segments)
  │     ElevenLabs API でセグメントごとに音声ファイルを生成
  │     → List[AudioSegment]: { index, text, audio_path, duration }
  │
  ├─③ fetch_images.py::fetch_images(narration_segments)
  │     Pexels API で image_keyword ごとに縦型画像を取得
  │     → List[str]: 画像ファイルパスのリスト
  │
  ├─④ create_video.py::create_video(segments, audio_segments, image_paths, bgm_mood, output_path)
  │     MoviePy でセグメントを合成 → 縦型(1080x1920) mp4 を書き出し
  │     BGMは bgm/{mood}/ フォルダからランダム選択・ボリューム15%でミックス
  │
  └─⑤ notify_slack.py::notify_slack(theme, title, video_path)
        Slack Webhook で完了通知（投稿URL付き）
```

投稿モジュール（upload_*.py）は現在 main.py から呼び出されていない。
実装済みだが、各プラットフォームの認証セットアップ後に main.py の `run()` に組み込む。

-----

## 各モジュールの仕様

### generate_script.py

- **モデル**: `gemini-2.5-flash-preview-04-17`
- **エンドポイント**: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- **temperature**: 1.0（毎回違うテーマを出させるため高め）
- **出力形式**: JSON のみ（プロンプトで厳命）
- **テーマローテーション**: 星座占い / 日本都市伝説 / 世界の不思議 / 風水 / 予言 / 心霊 / 陰謀論
- **narration_segments**: 8〜10個、各40〜60字
- **注意**: Gemini が稀に ```json で囲んで返すことがあるため、除去処理あり

```python
# 出力スキーマ
{
  "theme": str,
  "title": str,           # 25〜40字、SEO最適化
  "description": str,     # 150〜200字、ハッシュタグ含む
  "tags": List[str],      # 8個
  "narration_segments": [
    { "text": str, "image_keyword": str }
  ],
  "bgm_mood": "mysterious" | "dark" | "ethereal" | "dramatic"
}
```

### generate_audio.py

- **モデル**: `eleven_multilingual_v2`
- **VOICE_ID**: 環境変数 `ELEVENLABS_VOICE_ID`（デフォルト: Adam `pNInz6obpgDQGcFmaJgB`）
- **無料枠**: 1万文字/月（1本あたり約500文字 → 月20本まで無料）
- **出力**: `output/audio/segment_00.mp3` … 連番
- **duration取得**: MoviePy の `AudioFileClip` で実測（fallback: 5秒）
- **追加機能**: `generate_audio_with_timestamps()` でタイムスタンプ付き生成も可能（字幕同期用）

### fetch_images.py

- **API**: Pexels Search API `https://api.pexels.com/v1/search`
- **orientation**: portrait（縦型優先）
- **フォールバック**: キーワードで見つからない場合は `FALLBACK_KEYWORDS` リストから試行
- **最終フォールバック**: PIL で星空の黒背景を自動生成
- **出力**: `output/images/bg_00.jpg` … 連番
- **注意**: 毎回違う画像を取得するため `page=random.randint(1,3)` でランダム化

### create_video.py

- **解像度**: 1080 × 1920（9:16縦型）
- **FPS**: 30
- **フォント**: `Noto-Sans-CJK-JP`（`apt-get install fonts-noto-cjk` 必須）
- **字幕位置**: 縦72%（下寄り）、フォントサイズ62px、黒縁取り2.5px
- **テキスト折り返し**: 22文字で自動改行
- **BGMボリューム**: 15%（ナレーションが聞こえるように）
- **BGMフォルダ**: `bgm/{mood}/` → フォルダがなければ `bgm/` 直下にフォールバック
- **画像リサイズ**: アスペクト比を保ちつつカバーフィット（縦長・横長どちらも対応）

### upload_youtube.py

- **認証**: OAuth2（`Credentials.from_authorized_user_info`）
- **Shorts判定**: `#Shorts` を description に追加 + タグに `"Shorts"` を付与
- **初回トークン生成**: `python upload_youtube.py --generate-token` → `token.json` 生成
- **token.json の内容を `YOUTUBE_CREDENTIALS` に設定**（JSON文字列として）
- **カテゴリ**: 22（People & Blogs）
- **アップロード**: resumable upload（5MBチャンク）

### upload_instagram.py

- **API**: Instagram Graph API v19.0
- **フロー**: コンテナ作成 → 処理待機（ポーリング）→ 公開（3ステップ）
- **前提**: ビジネスアカウント + Facebookページ紐付けが必要
- **動画URL**: 公開アクセス可能なURLが必要（ローカルファイル不可）
  - Google Drive 共有リンクか GCS/S3 に事前アップが必要
- **待機タイムアウト**: 最大5分（10秒間隔でポーリング）

### upload_tiktok.py

- **API**: TikTok Content Posting API v2
- **前提**: TikTok for Developers でアプリ審査通過が必要（2〜4週間）
- **フロー**: init（upload_url取得）→ ファイルアップロード → 公開確認
- **審査待ちの代替**: TikTok Creator Studio 手動 or Zapier/Make 連携

-----

## 環境変数一覧

|変数名                     |説明                        |取得先                  |
|------------------------|--------------------------|---------------------|
|`GEMINI_API_KEY`        |Gemini API キー             |aistudio.google.com  |
|`ELEVENLABS_API_KEY`    |ElevenLabs API キー         |elevenlabs.io        |
|`ELEVENLABS_VOICE_ID`   |使用Voice ID                |ElevenLabs ダッシュボード   |
|`PEXELS_API_KEY`        |Pexels API キー             |pexels.com/api       |
|`YOUTUBE_CREDENTIALS`   |token.json の中身（JSON文字列）   |初回ローカル生成             |
|`INSTAGRAM_ACCESS_TOKEN`|Instagram 長期アクセストークン      |Meta for Developers  |
|`INSTAGRAM_USER_ID`     |Instagram ビジネスアカウントID     |Graph API Explorer   |
|`TIKTOK_ACCESS_TOKEN`   |TikTok アクセストークン           |TikTok for Developers|
|`SLACK_WEBHOOK_URL`     |Slack Incoming Webhook URL|Slack App 管理画面       |

GitHub Actions では全て `secrets.*` として設定。

-----

## よくある修正タスクと対応ファイル

|やりたいこと         |対象ファイル                                                  |
|---------------|--------------------------------------------------------|
|テーマ・プロンプトを変更する |`generate_script.py` の `SYSTEM_PROMPT`                  |
|別のAIモデルに切り替える  |`generate_script.py` の `GEMINI_MODEL` と `GEMINI_API_URL`|
|音声の声・スタイルを変える  |`generate_audio.py` の `VOICE_ID` と `voice_settings`     |
|字幕のフォント・サイズを変える|`create_video.py` の `_make_text_clip()`                 |
|BGMボリュームを変える   |`create_video.py` の `_mix_bgm()` → `.volumex(0.15)`     |
|投稿先を追加する       |`main.py` の `run()` に `upload_*.py` の呼び出しを追加            |
|実行スケジュールを変える   |`.github/workflows/daily_video.yml` の `cron`            |
|Slack通知の内容を変える |`notify_slack.py` の `payload`                           |

-----

## ローカル実行手順

```bash
# 1. 依存インストール
pip install -r requirements.txt
sudo apt-get install -y fonts-noto-cjk ffmpeg

# 2. BGM配置（pixabay.comなどから著作権フリーのmp3を取得）
mkdir -p bgm/mysterious
cp your_bgm.mp3 bgm/mysterious/

# 3. 環境変数設定
export GEMINI_API_KEY=AIza...
export ELEVENLABS_API_KEY=sk_...
export ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB
export PEXELS_API_KEY=...
export SLACK_WEBHOOK_URL=https://hooks.slack.com/...

# 4. 実行
python main.py
# → output/YYYYMMDD_HHMM_shorts.mp4 が生成される
```

-----

## 未実装・TODO

- [ ] `main.py` に `upload_youtube()` の呼び出しを組み込む（YouTube認証セットアップ後）
- [ ] `main.py` に `upload_instagram()` の呼び出しを組み込む（動画の公開URL化が必要）
- [ ] `main.py` に `upload_tiktok()` の呼び出しを組み込む（API審査通過後）
- [ ] Instagram 用に動画を Google Drive にアップして公開URLを取得する `upload_gdrive.py` の実装
- [ ] ElevenLabs の月次文字数使用量モニタリング
- [ ] 生成済みテーマの履歴管理（重複防止）→ `output/*_script.json` を参照する仕組み

-----

## コスト

|サービス            |月30本の費用                     |
|----------------|----------------------------|
|Gemini 2.5 Flash|**無料**（無料枠500req/日）         |
|ElevenLabs      |**無料**（1万文字/月・約20本分）超過後 $5/月|
|Pexels          |**無料**                      |
|GitHub Actions  |**無料**（2000分/月枠内）           |
|**合計**          |**$0〜5/月**                  |
