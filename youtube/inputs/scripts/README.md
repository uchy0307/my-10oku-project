# youtube/inputs/scripts/

100本事前ストック化されたYouTube本編スクリプト。`bulk_generate_scripts.mjs` が
`youtube/topics.json` の各 topic から Gemini API で生成し、ここに `script_NNN.json` として
保存する。`youtube_auto.yml` cron は `generate_script.mjs` の pre-stock fast path で
これらを順番に消費し、`output/<id>_script.txt` + `output/<id>_meta.json` を出力する。

## schema (`script_NNN.json`)

```json
{
  "id": "001",
  "topic_id": "001",
  "title": "...",
  "category": "人物軸|合戦軸|文化軸|経済軸|地理軸|風俗軸",
  "description": "YouTube説明文 500-800字",
  "tags": ["tag1", ...],
  "thumbnail_text": "...",
  "chapters": [
    {
      "index": 1,
      "title": "...",
      "narration": "1800-2400字の純粋ナレーション",
      "image_prompts": ["historic Japanese ...", ...]
    },
    ...
  ],
  "total_chars": 10500,
  "target_chars_min": 9600,
  "target_chars_max": 12000,
  "generated_at": "ISO8601",
  "generator": "bulk_generate_scripts.mjs v1"
}
```

## 再生成・追加生成

```
# CI 上 (GitHub Actions タブ → Bulk Generate 100 Scripts → Run workflow)
#   max: 25 (defaults), ids: 081,082 (任意指定)
# quota 切れたら graceful exit。再 dispatch で残りから続行。
```
