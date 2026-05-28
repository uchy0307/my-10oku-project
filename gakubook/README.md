# gakubook ｜ 学問・教養 解説系チャンネル（試作）

`@gakubook` を参考にした「顔出しなし・ナレーション＋図解スライド」型の
教養解説動画を生成する試作ライン。

## 構成

```
script.json            ← 台本（章ごとの paragraphs + 図解 points）
scripts/
  make_test_video.py   ← 台本 → 音声 → スライド → 字幕焼込み → mp4
output/                ← 生成物（mp4/wav/slides は .gitignore）
```

## 実行

```bash
python3 scripts/make_test_video.py
# => output/<id>_video.mp4
```

## 既知の制約（このクラウド環境）

- Gemini / Google TTS / ElevenLabs / edge-tts は全てプロキシ(403)でブロック。
- そのためナレーションはオフライン espeak-ng + pykakasi(漢字→かな)で代替。
  音声はロボット声で、構成・演出・字幕同期の確認用。
- 本番ナレーションは API キーを付けて既存パイプライン
  (new-youtube-local/scripts/step2_voice_google_tts.py 等) を使う想定。

## 依存

```bash
apt-get install -y ffmpeg espeak-ng fonts-noto-cjk
pip install Pillow pykakasi
```
