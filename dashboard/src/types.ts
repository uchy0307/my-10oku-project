export type FeedItem = {
  id: string;
  title: string;
  url: string;
  publishedAt: string;
  durationSec?: number;
};

export type PlatformKind = "note" | "samurai" | "otona" | "shorts";

export type RunStatus = "idle" | "dispatching" | "queued" | "in_progress" | "completed" | "failure" | "cancelled";

export type RunState = {
  status: RunStatus;
  runId?: number;
  runUrl?: string;
  conclusion?: string;
  lastInputs?: Record<string, string>;
};

export type CardState = {
  kind: PlatformKind;
  label: string;
  icon: string;
  quota: number;
  todayCount: number;
  latest?: FeedItem;
  loading: boolean;
  error?: string;
  run: RunState;
};

export type WorkflowSpec = {
  file: string;
  defaultInputs?: Record<string, string>;
  cycleField?: string;
  cycleMin?: number;
  cycleMax?: number;
  cyclePad?: number;
};
