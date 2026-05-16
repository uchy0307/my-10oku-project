# samurai プロジェクトとの差分メモ

new-youtube は samurai (既存 Node.js プロジェクト) と独立したフォルダで運用しますが、設計上は samurai の知見を流用しています。**samurai 既存ファイルは一切改変しません。**

## 共通利用できる部分 (参考実装として参照)

| samurai 側ファイル        | new-youtube 側で参考にした箇所                                                              |
| ------------------------- | ------------------------------------------------------------------------------------------- |
| `generate_voice.mjs`      | GCP TTS `ja-JP-Neural2-B` の voice 設定値 (`step2_voice.GCP_VOICE`)                          |
| `fetch_portrait.mjs`      | Pollinations.ai リトライ機構 (3 回・指数バックオフ) を `step3_images.generate_image` で踏襲   |
| `compile_video.mjs`       | ffmpeg `-f concat` で章別 mp4 をマージする手法 → `step4_compile._ffmpeg_concat` に移植        |
| `.github/workflows/*.yml` | cron スケジュール定義の構造 / Secrets の渡し方                                              |

## 主な変更点 (samurai → new-youtube)

| 項目        | samurai (既存)              | new-youtube (新規)                                                |
| ----------- | --------------------------- | ----------------------------------------------------------------- |
| 実装言語    | Node.js (mjs)               | Python 3.10+                                                      |
| 動画長      | 短尺中心                    | 10分長尺                                                          |
| アスペクト  | (samurai 既存に準拠)        | 横16:9 (1280x720)                                                 |
| キャラ      | 武士・歴史人物              | 30代キャリア女性 (大人女性向けライフスタイル)                     |
| 字幕焼込    | ffmpeg drawtext             | MoviePy TextClip + ImageMagick (Noto Sans CJK JP)                 |
| 音声        | GCP TTS のみ                | ElevenLabs Multilingual v2 を優先・GCP Neural2-B を fallback      |
| 画像        | Pollinations.ai flux        | 同 (テンプレ・NG単語フィルタを新規追加)                          |
| 台本入力    | 既存スクリプト              | Gemini API で JSON 自動生成 (Step 0 新規)                         |
| アップロード | 既存ロジック                | Step 5 スケルトン (resumable upload, publishAt 予約対応)          |

## 設計の差分 (考え方)

- **euphemism 置換辞書を撤廃**: 安全機構回避設計はやらない。NG 単語は検出時 `ValueError` で即停止。
- **画像プロンプト固定テンプレ**: シーン部分のみ Gemini が出力。キャラ・服装・構図はコード側で固定し、性的示唆を含む形容詞は通さない (NG_TOKENS 拒否)。
- **章単位の中間 mp4 生成 → ffmpeg concat**: MoviePy の巨大 clip を保持しないことでメモリ圧を下げる。
- **キャッシュ**: 画像は SHA256(prompt+seed) で再利用。chapter mp3 も再実行時はキャッシュ参照。
- **検証の2重化**: Gemini 出力 JSON はそのまま `step1_load.read_script()` に通し、NG 単語混入なら停止。

## 運用上の注意

- cron 時刻 (JST 06:00 / 18:00) が samurai の cron と衝突する場合は、`new-youtube/.github/workflows/new_youtube_auto.yml` 側で時刻を調整してください。
- assets/calm_lounge.mp3 (BGM) は samurai の素材ライブラリから流用可。コピーのみで samurai 側を改変しない。
- 同じ Pollinations.ai を叩くためレート制御は samurai と new-youtube で共有する想定 (将来 RateLimiter を共通モジュール化検討)。
