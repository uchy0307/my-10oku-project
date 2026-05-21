import { CONFIG } from "./config";
import type { FeedItem } from "./types";

function withProxy(url: string): string {
  if (!CONFIG.CORS_PROXY) return url;
  return CONFIG.CORS_PROXY + encodeURIComponent(url);
}

type NoteApiContents = { data?: { contents?: Array<{ key?: string; id?: number | string; name?: string; publishAt?: string; noteUrl?: string; type?: string; }>; }; };

export async function fetchNote(): Promise<FeedItem[]> {
  const url = `https://note.com/api/v2/creators/${CONFIG.NOTE_CREATOR}/contents?kind=note&page=1`;
  const res = await fetch(withProxy(url));
  if (!res.ok) throw new Error(`note API ${res.status}`);
  const json = (await res.json()) as NoteApiContents;
  const contents = json?.data?.contents ?? [];
  return contents
    .filter((c) => !!c.publishAt && !!c.name)
    .map<FeedItem>((c) => ({
      id: String(c.key ?? c.id ?? c.noteUrl ?? c.name),
      title: c.name ?? "(無題)",
      url: c.noteUrl ?? `https://note.com/${CONFIG.NOTE_CREATOR}`,
      publishedAt: c.publishAt as string
    }));
}

export async function fetchYouTubeRss(channelId: string): Promise<FeedItem[]> {
  const url = `https://www.youtube.com/feeds/videos.xml?channel_id=${channelId}`;
  const res = await fetch(withProxy(url));
  if (!res.ok) throw new Error(`YT RSS ${res.status}`);
  const xml = await res.text();
  const doc = new DOMParser().parseFromString(xml, "application/xml");
  const entries = Array.from(doc.getElementsByTagName("entry"));
  return entries.map<FeedItem>((entry) => {
    const id = entry.getElementsByTagName("yt:videoId")[0]?.textContent ?? entry.getElementsByTagName("id")[0]?.textContent ?? "";
    const title = entry.getElementsByTagName("title")[0]?.textContent ?? "(無題)";
    const published = entry.getElementsByTagName("published")[0]?.textContent ?? "";
    const linkEl = entry.getElementsByTagName("link")[0];
    const href = linkEl?.getAttribute("href") ?? `https://www.youtube.com/watch?v=${id}`;
    return { id, title, url: href, publishedAt: published };
  });
}

export function filterShorts(items: FeedItem[]): FeedItem[] {
  return items.filter((it) => {
    const t = it.title.toLowerCase();
    if (t.includes("#shorts") || t.includes("#short")) return true;
    if (it.url.includes("/shorts/")) return true;
    return false;
  });
}
