# Samurai Automation Uploader — API Review Submission

**Project:** Samurai Automation Uploader (Project: `samuraiautomation`)
**Channels:**
- https://www.youtube.com/@Japanese.Samurai.Channel (3,080 subscribers, Japanese history education)
- https://www.youtube.com/@Otona_Psychology (psychology / adult life skills, growing)

**Type:** Internal-only server-side automation. No public-facing app, no end-user UI.

---

## What this client does

A daily batch on the channel owner's machine:

1. Generates educational scripts in Japanese (Gemini API).
2. Synthesizes narration audio (edge-tts).
3. Renders 1920×1080 MP4 with ffmpeg (slideshow + burnt-in subtitles).
4. **Uploads the finished MP4 to YouTube via `videos.insert`** (this is the API call under review).
5. Sets a custom thumbnail via `thumbnails.set`.
6. Optionally updates metadata via `videos.update`.

The script `youtube_upload_demo.mjs` (this directory) is the exact upload module used in production, simplified for review.

---

## API methods used

| Method | Quota | Frequency |
|---|---|---|
| `videos.insert` | 1,600 units | 1 per video upload |
| `thumbnails.set` | 50 units | 1 per video upload |
| `videos.update` | 50 units | 0–1 per video (occasional metadata fix) |

**Per-video total:** ~1,700 units.

---

## Daily volume

| Content type | Length | Daily count |
|---|---|---|
| History long-form (@Japanese.Samurai.Channel) | ~30 min | 3 |
| History shorts (@Japanese.Samurai.Channel/shorts) | ~1 min | 5 |
| Psychology long-form (@Otona_Psychology) | ~25 min | 3 |
| Psychology shorts (@Otona_Psychology/shorts) | ~1 min | 5 |
| **Total** | — | **16 videos/day** |

**Calculation:** 16 × 1,700 = **27,200 units/day** at full daily volume.

The current default quota of 10,000 units allows only ~6 uploads/day, which causes batch overflow and pipeline failures. Requesting **100,000 units/day** to comfortably support 16/day plus a safety margin for retries and metadata corrections.

---

## How `videos.insert` is called

See `youtube_upload_demo.mjs`. Key points:

- **Auth:** OAuth 2.0 with a refresh token for the channel owner. No end-user OAuth — single operator, single project.
- **Privacy:** `public` (videos go live immediately for audience consumption).
- **Resumable upload:** uses `media.body` stream with `maxBodyLength: 2 GiB`.
- **Duplicate guard:** every successful upload is recorded in `uploaded.json` (per-channel). The script `process.exit(99)` if `INDEX` is already present, preventing accidental re-upload of the same content. This was added after a manual-review incident where the same script index was uploaded multiple times across days.
- **Tags:** ≤ 15 strings per video. Always Japanese language.

---

## How to run (review reproduction)

The script requires three environment variables and one prebuilt MP4 per index:

```
YOUTUBE_CLIENT_ID=<your OAuth client id>
YOUTUBE_CLIENT_SECRET=<your OAuth client secret>
YOUTUBE_REFRESH_TOKEN=<channel owner refresh token>
```

Set `LONG_INDEX=001` (3-digit zero-padded), place the prebuilt video at `./.work/001/output.mp4` and a thumbnail at `./.work/001/thumbnail.jpg`, then:

```
node youtube_upload_demo.mjs
```

A successful run prints the uploaded video URL and writes `uploaded.json`.

---

## Output examples (recent uploads)

| Channel | Recent upload |
|---|---|
| @Japanese.Samurai.Channel | https://youtube.com/watch?v=zBtj9-UnRMU |
| @Japanese.Samurai.Channel | https://youtube.com/watch?v=g4s0crATquw |
| @Otona_Psychology | https://youtube.com/watch?v=Vzk12M_Y_VI |
| @Otona_Psychology | https://youtube.com/watch?v=-rN-gLZ6ips |

All content is original, AI-narrated Japanese educational material. No music piracy, no third-party copyrighted content. Images are pulled from Wikimedia Commons (CC) and original-illustration stock libraries.

---

## Compliance notes

- **One OAuth project, one client.** No multi-tenant. No reseller.
- **No public landing for this script.** It runs server-side on the channel owner's PC.
- **No abusive patterns.** Daily batch with `videos.insert` calls spaced ≥ 30 seconds apart (per channel).
- **Retry policy:** none. If an upload fails, the index is kept un-marked and is retried next day. No tight-loop retries.
- **Channel separation:** two refresh tokens, one per channel. `YOUTUBE_REFRESH_TOKEN` for the samurai history channel, `OTONA_YOUTUBE_REFRESH_TOKEN` for the psychology channel. Hard-fails if the wrong token is configured, to prevent cross-channel mis-uploads.

---

## Contact

uchiyamatakayuki0307@gmail.com
