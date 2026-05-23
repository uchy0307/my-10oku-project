import { useEffect, useState } from "react";

const SERVER_KEY = "uchy_bat_server_url";
const DEFAULT_SERVER = "http://localhost:7373";

type BatAction = {
  id: string;
  label: string;
  icon: string;
  description?: string;
};

const ACTIONS: BatAction[] = [
  { id: "restart_server", label: "サーバー 再起動", icon: "🔄", description: "新ボタン反映時に押す" },
  { id: "upload_psych_001_sample", label: "大人#001 字幕焼込＋YT投稿", icon: "📤", description: "Whisper字幕→YouTube限定公開" },
  { id: "upload_history_007_sample", label: "歴史#007 YT投稿", icon: "⚔️", description: "明智光秀 限定公開" },
  { id: "upload_shorts_sample", label: "Shorts YT投稿", icon: "⚡", description: "歴史Shorts 限定公開" },
  { id: "inject_rules", label: "ルール再注入", icon: "📜", description: "次セッションにルール再読込フラグ" },
  { id: "wiki_refill", label: "Wiki画像 補充", icon: "🖼️", description: "Wikipedia から画像 500枚補充" },
  { id: "whisper_setup", label: "Whisper 初回設定", icon: "🎙️", description: "Whisper をインストール（初回のみ）" },
  { id: "whisper_psych_001", label: "字幕 生成 (心理学001)", icon: "📝", description: "Whisper で字幕生成" },
  { id: "build_3_samples", label: "見本動画 3本生成", icon: "🎬", description: "歴史/大人/Shorts 一括生成" },
  { id: "build_history_007", label: "歴史 #007 生成", icon: "⚔️", description: "明智光秀 本能寺 動画" },
  { id: "build_psych_001", label: "大人 #001 生成", icon: "🧠", description: "心理学 #001 動画" }
];

type RunStatus = { id: string; status: "idle" | "running" | "ok" | "error"; message?: string };

export function BatButtons({ onToast }: { onToast: (msg: string, tone?: "info" | "ok" | "error") => void }) {
  const [serverUrl, setServerUrl] = useState<string>(() => localStorage.getItem(SERVER_KEY) || DEFAULT_SERVER);
  const [showSettings, setShowSettings] = useState(false);
  const [pending, setPending] = useState<Record<string, RunStatus>>({});

  useEffect(() => {
    localStorage.setItem(SERVER_KEY, serverUrl);
  }, [serverUrl]);

  const run = async (action: BatAction) => {
    setPending((p) => ({ ...p, [action.id]: { id: action.id, status: "running" } }));
    onToast(`${action.label} 起動中…`, "info");
    try {
      const res = await fetch(`${serverUrl.replace(/\/$/, "")}/run/${action.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setPending((p) => ({ ...p, [action.id]: { id: action.id, status: "ok", message: json.message } }));
      onToast(`${action.label} 起動成功`, "ok");
    } catch (e: any) {
      setPending((p) => ({ ...p, [action.id]: { id: action.id, status: "error", message: e?.message ?? String(e) } }));
      onToast(`${action.label} 失敗: ${e?.message ?? e}`, "error");
    }
  };

  return (
    <section className="mt-6 rounded-2xl border border-slate-700 bg-slate-900/40 p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-bold text-slate-200">PC 操作ボタン</h2>
        <button
          onClick={() => setShowSettings((s) => !s)}
          className="text-[10px] text-slate-400 hover:text-slate-200"
        >
          {showSettings ? "閉じる" : "サーバー設定"}
        </button>
      </div>

      {showSettings && (
        <div className="mb-3 rounded-lg bg-slate-950/60 p-3 text-[11px]">
          <label className="block text-slate-300 mb-1">サーバー URL（自宅PC + cloudflared トンネル）</label>
          <input
            value={serverUrl}
            onChange={(e) => setServerUrl(e.target.value)}
            placeholder="https://pc.uchy0307.uk"
            className="w-full rounded-md bg-slate-800 border border-slate-700 px-2 py-1 text-slate-100 text-[11px]"
          />
          <p className="mt-2 text-slate-500 text-[10px]">
            ローカルテストは {DEFAULT_SERVER} のまま。スマホから操作するには cloudflared 等でトンネルを公開して URL を貼り付け。
          </p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        {ACTIONS.map((a) => {
          const st = pending[a.id];
          const isRunning = st?.status === "running";
          return (
            <button
              key={a.id}
              onClick={() => run(a)}
              disabled={isRunning}
              className={`flex flex-col items-start gap-1 rounded-xl border px-3 py-2 text-left text-[11px] transition ${
                isRunning ? "border-amber-600 bg-amber-950/30" :
                st?.status === "ok" ? "border-emerald-600 bg-emerald-950/30" :
                st?.status === "error" ? "border-rose-600 bg-rose-950/30" :
                "border-slate-700 bg-slate-900/60 hover:bg-slate-800/60"
              } disabled:opacity-60`}
            >
              <span className="text-base">{a.icon}</span>
              <span className="font-semibold text-slate-100">{a.label}</span>
              {a.description && <span className="text-slate-500 text-[10px]">{a.description}</span>}
              {st?.message && <span className="text-slate-400 text-[10px] mt-1">{st.message}</span>}
            </button>
          );
        })}
      </div>

      <p className="mt-3 text-[10px] text-slate-500 leading-relaxed">
        ボタンを押すと、自宅PCの小型サーバー経由で対応する .bat / .py が実行されます。
        スマホからも操作可能（cloudflared トンネル要設定）。
      </p>
    </section>
  );
}
