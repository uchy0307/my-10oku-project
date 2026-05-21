export type FeedItem = {
  id: string;
  title: string;
  url: string;
  publishedAt: string;
  durationSec?: number;
};

export type PlatformKind = "note" | "samurai" | "otona" | "shorts";

export type CardState = {
  kind: PlatformKind;
  label: string;
  icon: string;
  quota: number;
  todayCount: number;
  latest?: FeedItem;
  loading: boolean;
  error?: string;
};
