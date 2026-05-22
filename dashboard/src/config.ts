import type { WorkflowSpec, PlatformKind } from "./types";

export const CONFIG = {
  NOTE_CREATOR: "happy_happy_4649",
  SAMURAI_YT_CHANNEL_ID: "UChsS2R5ao05wsptKmutSaoA",
  OTONA_YT_CHANNEL_ID: "UClMciBTt4e1QUV1q6l9qrWQ",
  DAILY_QUOTA: { note: 5, samurai: 3, otona: 3, shorts: 5 },
  CORS_PROXY: "/api/proxy?url=",
  REFRESH_INTERVAL_MS: 30000,
  SHORTS_MAX_SECONDS: 90,
  TIMEZONE: "Asia/Tokyo",
  GITHUB_OWNER: "uchy0307",
  GITHUB_REPO: "my-10oku-project",
  GITHUB_REF: "main",
  RUN_POLL_INTERVAL_MS: 5000,
  RUN_POLL_MAX_ATTEMPTS: 60,
  PAT_STORAGE_KEY: "uchy_dashboard_pat_v1",
  CYCLE_LONG_KEY: "uchy_dashboard_last_long_v1",
  CYCLE_SHORT_KEY: "uchy_dashboard_last_short_v1"
};

export const WORKFLOWS: Record<PlatformKind, WorkflowSpec> = {
  note: { file: "note_auto_post.yml", defaultInputs: { max: "1" } },
  samurai: { file: "history_v2.yml", cycleField: "long_index", cycleMin: 1, cycleMax: 3, cyclePad: 3 },
  otona: { file: "new_youtube_auto.yml" },
  shorts: { file: "shorts_v2.yml", cycleField: "short_index", cycleMin: 1, cycleMax: 5, cyclePad: 3 }
};
