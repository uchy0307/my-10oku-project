import { useCallback, useEffect, useRef, useState } from "react";
import { isAfter } from "date-fns";
import { CONFIG, WORKFLOWS } from "./config";
import type { CardState, FeedItem, PlatformKind, RunState } from "./types";
import { fetchNote, fetchYouTubeRss, filterShorts } from "./fetchers";
import { countToday, fmtNow, jstStartOfToday } from "./time";
import { PlatformCard } from "./PlatformCard";
import { SettingsDialog } from "./SettingsDialog";
import { Toast } from "./Toast";
import { dispatchWorkflow, getPat, listRecentRuns, nextCycleIndex, padIndex } from "./github";

const IDLE_RUN: RunState = { status: "idle" };

const INITIAL: Record<PlatformKind, CardState> = {
  note: { kind: "note", label: "Note", icon: "\u{1F4DD}", quota: CONFIG.DAILY_QUOTA.note, todayCount: 0, compliantCount: 0, loading: true, run: IDLE_RUN },
  samurai: { kind: "samurai", label: "歴史YT", icon: "⚔️", quota: CONFIG.DAILY_QUOTA.samurai, todayCount: 0, compliantCount: 0, loading: true, run: IDLE_RUN },
  otona: { kind: "otona", label: "大人YT", icon: "\u{1F9E0}", quota: CONFIG.DAILY_QUOTA.otona, todayCount: 0, compliantCount: 0, loading: true, run: IDLE_RUN },
  shorts: { kind: "shorts", label: "Shorts", icon: "⚡", quota: CONFIG.DAILY_QUOTA.shorts, todayCount: 0, compliantCount: 0, loading: true, run: IDLE_RUN }
};

function todayItems(items: FeedItem[]): FeedItem[] {
  const cutoff = jstStartOfToday();
  return items.filter((it) => !!it.publishedAt && isAfter(new Date(it.publishedAt), cutoff));
}

// 完全準拠 (完成品) 判定。判定不能なスペックは失敗作=ゼロ扱い。
function countCompliant(kind: PlatformKind, items: FeedItem[]): number {
  const today = todayItems(items);
  if (kind === "note") {
    // 価格100円 + アプリリンク/アクセスコード本文 + Word3本添付 + 47歳文面なしを RSS だけでは検証不能→ 0
    return 0;
  }
  if (kind === "samurai" || kind === "otona") {
    // 30分以上 + NanamiNeural音声 + 字幕同期等。RSSは durationSec 未取得のため事実上 0。
    return today.filter((it) => (it.durationSec ?? 0) >= 1800).length;
  }
  // shorts: 再生可能 + タイトル重複なし
  const counts = new Map<string, number>();
  today.forEach((it) => counts.set(it.title, (counts.get(it.title) || 0) + 1));
  return today.filter((it) => (counts.get(it.title) || 0) === 1).length;
}

function applyItems(prev: CardState, items: FeedItem[]): CardState {
  const sorted = [...items].sort((a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime());
  return {
    ...prev,
    loading: false,
    error: undefined,
    todayCount: countToday(sorted.map((i) => i.publishedAt)),
    compliantCount: countCompliant(prev.kind, sorted),
    latest: sorted[0]
  };
}

function applyError(prev: CardState, msg: string): CardState {
  return { ...prev, loading: false, error: msg };
}

function buildInputs(kind: PlatformKind): Record<string, string> {
  const wf = WORKFLOWS[kind];
  const out: Record<string, string> = { ...(wf.defaultInputs ?? {}) };
  if (wf.cycleField && wf.cycleMin != null && wf.cycleMax != null) {
    const key = kind === "samurai" ? CONFIG.CYCLE_LONG_KEY : kind === "shorts" ? CONFIG.CYCLE_SHORT_KEY : `uchy_dashboard_cycle_${kind}`;
    const n = nextCycleIndex(key, wf.cycleMin, wf.cycleMax);
    out[wf.cycleField] = wf.cyclePad ? padIndex(n, wf.cyclePad) : String(n);
  }
  return out;
}

export default function App() {
  const [cards, setCards] = useState<Record<PlatformKind, CardState>>(INITIAL);
  const [lastSync, setLastSync] = useState<string>("");
  const [refreshing, setRefreshing] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [patReady, setPatReady] = useState<boolean>(() => !!getPat());
  const [toast, setToast] = useState<{ msg: string; tone?: "info" | "ok" | "error" } | null>(null);
  const pollersRef = useRef<Record<string, number | undefined>>({});

  const load = useCallback(async () => {
    setRefreshing(true);
    const [noteRes, samuraiRes, otonaRes] = await Promise.allSettled([
      fetchNote(),
      fetchYouTubeRss(CONFIG.SAMURAI_YT_CHANNEL_ID),
      fetchYouTubeRss(CONFIG.OTONA_YT_CHANNEL_ID)
    ]);
    setCards((prev) => {
      const next = { ...prev };
      next.note = noteRes.status === "fulfilled" ? applyItems(prev.note, noteRes.value) : applyError(prev.note, String(noteRes.reason?.message ?? noteRes.reason));
      if (samuraiRes.status === "fulfilled") {
        next.samurai = applyItems(prev.samurai, samuraiRes.value);
        next.shorts = applyItems(prev.shorts, filterShorts(samuraiRes.value));
      } else {
        const msg = String(samuraiRes.reason?.message ?? samuraiRes.reason);
        next.samurai = applyError(prev.samurai, msg);
        next.shorts = applyError(prev.shorts, msg);
      }
      next.otona = otonaRes.status === "fulfilled" ? applyItems(prev.otona, otonaRes.value) : applyError(prev.otona, String(otonaRes.reason?.message ?? otonaRes.reason));
      return next;
    });
    setLastSync(fmtNow());
    setRefreshing(false);
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, CONFIG.REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [load]);

  const setRun = useCallback((kind: PlatformKind, patch: Partial<RunState>) => {
    setCards((prev) => ({ ...prev, [kind]: { ...prev[kind], run: { ...prev[kind].run, ...patch } } }));
  }, []);

  const pollRun = useCallback(async (kind: PlatformKind, workflowFile: string, dispatchedAt: number) => {
    const pat = getPat();
    if (!pat) return;
    let attempts = 0;
    const tick = async () => {
      attempts += 1;
      try {
        const runs = await listRecentRuns(workflowFile, pat, 5);
        const candidate = runs.find((r) => new Date(r.created_at).getTime() >= dispatchedAt - 5000);
        if (candidate) {
          const isDone = candidate.status === "completed";
          const concl = candidate.conclusion;
          setRun(kind, {
            status: isDone ? (concl === "success" ? "completed" : concl === "cancelled" ? "cancelled" : "failure") : (candidate.status as RunState["status"]),
            runId: candidate.id,
            runUrl: candidate.html_url,
            conclusion: concl ?? undefined
          });
          if (isDone) return;
        }
      } catch (e) {
        setRun(kind, { status: "failure" });
        return;
      }
      if (attempts >= CONFIG.RUN_POLL_MAX_ATTEMPTS) return;
      pollersRef.current[kind] = window.setTimeout(tick, CONFIG.RUN_POLL_INTERVAL_MS);
    };
    pollersRef.current[kind] = window.setTimeout(tick, CONFIG.RUN_POLL_INTERVAL_MS);
  }, [setRun]);

  const handleRun = useCallback(async (kind: PlatformKind) => {
    const pat = getPat();
    if (!pat) {
      setToast({ msg: "⚙️_PAT_NEEDED", tone: "error" });
      return;
    }
    const wf = WORKFLOWS[kind];
    const inputs = buildInputs(kind);
    setRun(kind, { status: "dispatching", lastInputs: inputs });
    const dispatchedAt = Date.now();
    try {
      await dispatchWorkflow(wf.file, inputs, pat);
      setRun(kind, { status: "queued" });
      const inputsStr = Object.keys(inputs).length ? " (" + Object.entries(inputs).map(([k, v]) => `${k}=${v}`).join(", ") + ")" : "";
      setToast({ msg: `${cards[kind].label} dispatched${inputsStr}`, tone: "ok" });
      pollRun(kind, wf.file, dispatchedAt);
    } catch (e: any) {
      setRun(kind, { status: "failure" });
      setToast({ msg: `${cards[kind].label} dispatch 失敗: ${e?.message ?? e}`, tone: "error" });
    }
  }, [cards, setRun, pollRun]);

  useEffect(() => {
    return () => {
      Object.values(pollersRef.current).forEach((t) => t && window.clearTimeout(t));
    };
  }, []);

  const order: PlatformKind[] = ["note", "samurai", "otona", "shorts"];

  return (
    <div className="min-h-screen bg-ink text-slate-100 px-4 py-5 max-w-md mx-auto">
      <header className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-lg font-bold tracking-tight">うっちー様 Tasks</h1>
          <p className="text-[11px] text-slate-400">Phase B · 読込専用 · {lastSync ? `更新 ${lastSync}` : "初回読み込み中"}</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setSettingsOpen(true)} className="rounded-xl border border-slate-600 px-3 py-1.5 text-xs hover:bg-slate-800" aria-label="設定" title="設定">⚙️</button>
          <button onClick={load} disabled={refreshing} className="rounded-xl border border-slate-600 px-3 py-1.5 text-xs hover:bg-slate-800 disabled:opacity-50" aria-label="更新">{refreshing ? "更新中…" : "更新"}</button>
        </div>
      </header>

      <main className="grid grid-cols-2 gap-3">
        {order.map((k) => (
          <PlatformCard key={k} card={cards[k]} />
        ))}
      </main>

      <footer className="mt-6 text-[10px] text-slate-500 leading-relaxed">
        <p>このダッシュボードは読込専用です。Note / YouTube RSS の最新を ~30秒間隔で取得して表示します。</p>
        <p className="mt-1">完成本数は、プラットフォームごとの「完全準拠」検査を通った本数です。判定できないものは失敗作扱い(0本)となります。</p>
      </footer>

      <SettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} onSaved={() => setPatReady(!!getPat())} />

      {toast && <Toast message={toast.msg} tone={toast.tone} onDismiss={() => setToast(null)} />}
    </div>
  );
}
