import type { CardState } from "./types";
import { fmtJst } from "./time";

type Props = { card: CardState };

export function PlatformCard({ card }: Props) {
  const { quota, todayCount, latest, loading, error, icon, label } = card;
  const ratio = quota > 0 ? todayCount / quota : 0;
  const tone = error ? "border-red-500/60 bg-red-950/40" : todayCount >= quota ? "border-emerald-500/60 bg-emerald-950/30" : ratio >= 0.5 ? "border-amber-500/60 bg-amber-950/20" : "border-slate-700 bg-panel";
  return (
    <a href={latest?.url ?? "#"} target="_blank" rel="noopener noreferrer" className={`flex flex-col rounded-2xl border ${tone} p-4 transition-active hover:brightness-110 active:scale-[0.98] no-underline text-inherit min-h-[148px]`}>
      <div className="flex items-start justify-between">
        <div className="text-3xl leading-none">{icon}</div>
        <div className="text-right">
          <div className="text-xs text-slate-400">本日</div>
          <div className="text-xl font-bold">{loading ? "…" : `${todayCount}/${quota}`}{!loading && todayCount >= quota ? " ✅" : ""}</div>
        </div>
      </div>
      <div className="mt-2 text-sm font-semibold text-slate-200">{label}</div>
      <div className="mt-1 text-xs text-slate-400 line-clamp-2 min-h-[2.25rem]">{error ? `読込エラー: ${error}` : loading ? "読み込み中…" : latest ? latest.title : "本日の更新はまだ"}</div>
      <div className="mt-auto pt-2 text-[11px] text-slate-500">{latest ? fmtJst(latest.publishedAt) + " JST" : "—"}</div>
    </a>
  );
}
