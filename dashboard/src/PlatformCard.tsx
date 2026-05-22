import type { CardState } from "./types";
import { fmtJst } from "./time";

type Props = {
  card: CardState;
  patReady: boolean;
  onRun: () => void;
};

function runBadge(card: CardState) {
  const r = card.run;
  if (r.status === "idle") return null;
  let label = "";
  let cls = "";
  switch (r.status) {
    case "dispatching":
      label = "起動中…";
      cls = "bg-slate-600 text-white";
      break;
    case "queued":
      label = "queued";
      cls = "bg-slate-500 text-white";
      break;
    case "in_progress":
      label = "in_progress";
      cls = "bg-amber-500 text-slate-900";
      break;
    case "completed":
      label = "完了";
      cls = "bg-emerald-600 text-white";
      break;
    case "failure":
      label = "失敗";
      cls = "bg-red-600 text-white";
      break;
    case "cancelled":
      label = "中止";
      cls = "bg-slate-500 text-white";
      break;
  }
  return (
    <span className={`inline-block rounded-full px-2 py-[1px] text-[10px] font-semibold ${cls}`}>
      {label}
    </span>
  );
}

export function PlatformCard({ card, patReady, onRun }: Props) {
  const { quota, todayCount, latest, loading, error, icon, label, run } = card;
  const ratio = quota > 0 ? todayCount / quota : 0;
  const tone = error
    ? "border-red-500/60 bg-red-950/40"
    : todayCount >= quota
    ? "border-emerald-500/60 bg-emerald-950/30"
    : ratio >= 0.5
    ? "border-amber-500/60 bg-amber-950/20"
    : "border-slate-700 bg-panel";

  const handleRun = (e: any) => {
    e.preventDefault();
    e.stopPropagation();
    onRun();
  };

  return (
    <div className={`relative flex flex-col rounded-2xl border ${tone} p-4 min-h-[170px]`}>
      <a
        href={latest?.url ?? "#"}
        target="_blank"
        rel="noopener noreferrer"
        className="absolute inset-0 rounded-2xl"
        aria-label={`${label} 最新コンテンツへ`}
      />
      <div className="relative flex items-start justify-between">
        <div className="text-3xl leading-none">{icon}</div>
        <div className="text-right">
          <div className="text-xs text-slate-400">本日</div>
          <div className="text-xl font-bold">
            {loading ? "…" : `${todayCount}/${quota}`}
            {!loading && todayCount >= quota ? " ✅" : ""}
          </div>
        </div>
      </div>
      <div className="relative mt-2 text-sm font-semibold text-slate-200">{label}</div>
      <div className="relative mt-1 text-xs text-slate-400 line-clamp-2 min-h-[2.25rem]">
        {error
          ? `読込エラー: ${error}`
          : loading
          ? "読み込み中…"
          : latest
          ? latest.title
          : "本日の更新はまだ"}
      </div>
      <div className="relative mt-auto pt-2 flex items-center justify-between gap-2">
        <span className="text-[11px] text-slate-500">
          {latest ? fmtJst(latest.publishedAt) + " JST" : "—"}
        </span>
        <div className="flex items-center gap-2">
          {runBadge(card)}
          <button
            onClick={handleRun}
            disabled={!patReady || run.status === "dispatching"}
            className="rounded-lg bg-amber-500 text-slate-900 font-bold px-2.5 py-1 text-xs disabled:opacity-40 disabled:cursor-not-allowed hover:brightness-110 active:scale-95 z-10"
            aria-label={`${label} を実行`}
            title={patReady ? "▶実行" : "⚙️で PAT 設定が必要"}
          >
            ▶実行
          </button>
        </div>
      </div>
      {run.runUrl && (
        <a
          href={run.runUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="relative mt-1 text-[10px] text-slate-500 hover:text-slate-300 z-10 underline truncate"
          onClick={(e) => e.stopPropagation()}
        >
          ▶ Run #{run.runId} ↗
        </a>
      )}
    </div>
  );
}
