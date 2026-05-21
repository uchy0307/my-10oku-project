import { useCallback, useEffect, useState } from "react";
import { CONFIG } from "./config";
import type { CardState, FeedItem, PlatformKind } from "./types";
import { fetchNote, fetchYouTubeRss, filterShorts } from "./fetchers";
import { countToday, fmtNow } from "./time";
import { PlatformCard } from "./PlatformCard";

const INITIAL: Record<PlatformKind, CardState> = {
  note: { kind: "note", label: "Note", icon: "📝", quota: CONFIG.DAILY_QUOTA.note, todayCount: 0, loading: true },
  samurai: { kind: "samurai", label: "歴史YT", icon: "⚔️", quota: CONFIG.DAILY_QUOTA.samurai, todayCount: 0, loading: true },
  otona: { kind: "otona", label: "大人YT", icon: "🧠", quota: CONFIG.DAILY_QUOTA.otona, todayCount: 0, loading: true },
  shorts: { kind: "shorts", label: "Shorts", icon: "⚡", quota: CONFIG.DAILY_QUOTA.shorts, todayCount: 0, loading: true }
};

function applyItems(prev: CardState, items: FeedItem[]): CardState {
  const sorted = [...items].sort((a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime());
  return { ...prev, loading: false, error: undefined, todayCount: countToday(sorted.map((i) => i.publishedAt)), latest: sorted[0] };
}

function applyError(prev: CardState, msg: string): CardState {
  return { ...prev, loading: false, error: msg };
}

export default function App() {
  const [cards, setCards] = useState<Record<PlatformKind, CardState>>(INITIAL);
  const [lastSync, setLastSync] = useState<string>("");
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setRefreshing(true);
    const [noteRes, samuraiRes, otonaRes] = await Promise.allSettled([fetchNote(), fetchYouTubeRss(CONFIG.SAMURAI_YT_CHANNEL_ID), fetchYouTubeRss(CONFIG.OTONA_YT_CHANNEL_ID)]);
    setCards((prev) => {
      const next = { ...prev };
      next.note = noteRes.status === "fulfilled" ? applyItems(prev.note, noteRes.value) : applyError(prev.note, String(noteRes.reason?.message ?? noteRes.reason));
      if (samuraiRes.status === "fulfilled") { next.samurai = applyItems(prev.samurai, samuraiRes.value); next.shorts = applyItems(prev.shorts, filterShorts(samuraiRes.value)); } else { const msg = String(samuraiRes.reason?.message ?? samuraiRes.reason); next.samurai = applyError(prev.samurai, msg); next.shorts = applyError(prev.shorts, msg); }
      next.otona = otonaRes.status === "fulfilled" ? applyItems(prev.otona, otonaRes.value) : applyError(prev.otona, String(otonaRes.reason?.message ?? otonaRes.reason));
      return next;
    });
    setLastSync(fmtNow()); setRefreshing(false);
  }, []);

  useEffect(() => { load(); const id = setInterval(load, CONFIG.REFRESH_INTERVAL_MS); return () => clearInterval(id); }, [load]);

  const order: PlatformKind[] = ["note", "samurai", "otona", "shorts"];

  return (
    <div className="min-h-screen bg-ink text-slate-100 px-4 py-5 max-w-md mx-auto">
      <header className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-lg font-bold tracking-tight">うっちー Tasks</h1>
          <p className="text-[11px] text-slate-400">Phase A · 読み取り専用 · {lastSync ? `更新 ${lastSync}` : "初回読み込み中"}</p>
        </div>
        <button onClick={load} disabled={refreshing} className="rounded-xl border border-slate-600 px-3 py-1.5 text-xs hover:bg-slate-800 disabled:opacity-50" aria-label="更新">{refreshing ? "更新中…" : "更新"}</button>
      </header>
      <main className="grid grid-cols-2 gap-3">{order.map((k) => <PlatformCard key={k} card={cards[k]} />)}</main>
      <footer className="mt-6 text-[10px] text-slate-500 leading-relaxed">▶実行ボタンは Phase B で別子窓に。本画面はタップ→最新コンテンツへ遷移します。</footer>
    </div>
  );
}
