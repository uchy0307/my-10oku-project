import { useCallback, useEffect, useState } from "react";

const RAW_BASE = "https://raw.githubusercontent.com/uchy0307/my-10oku-project/main";
const MEMORY_URL = RAW_BASE + "/dashboard/public/MEMORY.md";
const LEARNED_URL = RAW_BASE + "/agent/memory/learned_from_history.md";
const FEEDBACK_INDEX_URL = "https://api.github.com/repos/uchy0307/my-10oku-project/contents/agent/memory";
const LS_LEARNED = "uchy_learned_history_v1";
const LS_HISTORY = "uchy_dispatch_history_v1";
const CACHE_MS = 5 * 60 * 1000;

let memCache: { text: string; ts: number } | null = null;

async function fetchMemory(): Promise<string> {
  if (memCache && Date.now() - memCache.ts < CACHE_MS) return memCache.text;
  const url = MEMORY_URL + "?t=" + Date.now();
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("MEMORY " + res.status);
  const text = await res.text();
  memCache = { text, ts: Date.now() };
  return text;
}

async function fetchFeedback(): Promise<string> {
  try {
    const res = await fetch(FEEDBACK_INDEX_URL + "?t=" + Date.now(), { cache: "no-store" });
    if (!res.ok) return "";
    const files = await res.json();
    if (!Array.isArray(files)) return "";
    const targets = files.filter((f: any) => typeof f?.name === "string" && f.name.startsWith("feedback_"));
    const out: string[] = [];
    for (const f of targets.slice(0, 5)) {
      try {
        const r = await fetch(f.download_url, { cache: "no-store" });
        if (r.ok) {
          const t = await r.text();
          out.push("### " + f.name + "\n" + t);
        }
      } catch { /* skip */ }
    }
    return out.join("\n\n");
  } catch { return ""; }
}

async function fetchLearned(): Promise<string> {
  try {
    const res = await fetch(LEARNED_URL + "?t=" + Date.now(), { cache: "no-store" });
    if (!res.ok) return "";
    return await res.text();
  } catch { return ""; }
}

async function sendToDispatch(text: string): Promise<"share" | "clipboard" | "none"> {
  let copied = false;
  try {
    await navigator.clipboard.writeText(text);
    copied = true;
  } catch { /* ignore */ }
  try {
    const hist = JSON.parse(localStorage.getItem(LS_HISTORY) || "[]");
    hist.unshift({ ts: new Date().toISOString(), text: text.slice(0, 4000) });
    localStorage.setItem(LS_HISTORY, JSON.stringify(hist.slice(0, 50)));
  } catch { /* ignore */ }
  const nav: any = navigator;
  if (typeof nav.share === "function") {
    try {
      await nav.share({ title: "うっちー様 → Cowork", text });
      return "share";
    } catch { /* user dismissed or unsupported */ }
  }
  try {
    const a = document.createElement("a");
    a.href = "claude://chat?message=" + encodeURIComponent(text.slice(0, 1500));
    a.rel = "noopener";
    a.click();
  } catch { /* ignore */ }
  return copied ? "clipboard" : "none";
}

function analyzeHistory(history: { ts: string; text: string }[]): string {
  const violationKeywords = ["違反", "禁止", "違う", "ダメ", "やめて", "間違い", "却下"];
  const hits: string[] = [];
  for (let i = 0; i < history.length; i++) {
    const h = history[i];
    const hit = violationKeywords.find((k) => h.text.includes(k));
    if (hit) {
      const ctx = history.slice(Math.max(0, i - 5), i + 1).map((x) => `- [${x.ts}] ${x.text.slice(0, 200)}`).join("\n");
      hits.push("## 違反候補 (キーワード: " + hit + ")\n" + ctx);
    }
  }
  return hits.length ? hits.join("\n\n") : "(明示的な違反語は検出されず)";
}

type Props = { onToast: (msg: string, tone?: "info" | "ok" | "error") => void };

export function RuleInjector({ onToast }: Props) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [lastFetch, setLastFetch] = useState<string>("");
  const [ruleSummary, setRuleSummary] = useState<string>("");

  useEffect(() => {
    fetchMemory().then((m) => {
      const firstLines = m.split("\n").filter((l) => /^\d+\./.test(l.trim())).slice(0, 3).join(" / ");
      setRuleSummary(firstLines || "ルール取得済み");
      setLastFetch(new Date().toLocaleTimeString("ja-JP"));
    }).catch(() => { /* ignore */ });
  }, []);

  const announce = (res: "share" | "clipboard" | "none", label: string) => {
    if (res === "share") onToast(label + ": 共有メニュー起動", "ok");
    else if (res === "clipboard") onToast(label + ": コピー完了 (Cowork に貼り付け)", "ok");
    else onToast(label + ": 送信に失敗", "error");
  };

  const reinjectRule = useCallback(async () => {
    setBusy("rule");
    try {
      const mem = await fetchMemory();
      const fb = await fetchFeedback();
      const body = "【うっちー様・恒久ルール 再注入】\n\n" + mem + (fb ? "\n\n【追加フィードバック】\n" + fb : "");
      const res = await sendToDispatch(body);
      announce(res, "ルール再注入");
      setLastFetch(new Date().toLocaleTimeString("ja-JP"));
    } catch (e: any) {
      onToast("ルール取得失敗: " + (e?.message || e), "error");
    } finally { setBusy(null); }
  }, [onToast]);

  const sendFree = useCallback(async () => {
    const t = text.trim();
    if (!t) { onToast("文字を入力してください", "error"); return; }
    setBusy("free");
    try {
      const res = await sendToDispatch(t);
      announce(res, "自由文送信");
      if (res !== "none") setText("");
    } finally { setBusy(null); }
  }, [text, onToast]);

  const learnFromHistory = useCallback(async () => {
    setBusy("learn");
    try {
      const hist = JSON.parse(localStorage.getItem(LS_HISTORY) || "[]");
      const remote = await fetchLearned();
      const analysis = analyzeHistory(hist);
      const out = "# 履歴学習結果\n\n更新: " + new Date().toISOString() + "\n\n## ローカル送信履歴件数: " + hist.length + "\n\n" + analysis + (remote ? "\n\n## GitHub保存版 (前回)\n" + remote : "");
      localStorage.setItem(LS_LEARNED, out);
      onToast("履歴学習完了 (件数: " + hist.length + ")", "ok");
    } catch (e: any) {
      onToast("学習失敗: " + (e?.message || e), "error");
    } finally { setBusy(null); }
  }, [onToast]);

  const injectLearned = useCallback(async () => {
    setBusy("inject");
    try {
      const mem = await fetchMemory();
      const learned = localStorage.getItem(LS_LEARNED) || await fetchLearned() || "(学習未実行 — 📚 ボタンを先に押してください)";
      const body = "【ルール本体】\n" + mem + "\n\n【履歴学習結果】\n" + learned;
      const res = await sendToDispatch(body);
      announce(res, "学習注入");
    } catch (e: any) {
      onToast("学習注入失敗: " + (e?.message || e), "error");
    } finally { setBusy(null); }
  }, [onToast]);

  const btn = "rounded-xl border border-slate-600 px-3 py-2 text-xs hover:bg-slate-800 disabled:opacity-50";
  const wide = btn + " w-full";

  return (
    <section className="mt-5 border-t border-slate-700 pt-4" data-testid="rule-injector">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-bold">ルール管理</h2>
        <span className="text-[10px] text-slate-500">{lastFetch ? "取得 " + lastFetch : "未取得"}</span>
      </div>
      {ruleSummary && (
        <p className="text-[10px] text-slate-400 mb-2 line-clamp-2">{ruleSummary}</p>
      )}
      <div className="grid grid-cols-2 gap-2">
        <button data-testid="btn-reinject" onClick={reinjectRule} disabled={busy !== null} className={wide}>
          {busy === "rule" ? "送信中…" : "📋 ルール再注入"}
        </button>
        <button data-testid="btn-learn" onClick={learnFromHistory} disabled={busy !== null} className={wide}>
          {busy === "learn" ? "学習中…" : "📚 履歴から学習"}
        </button>
        <button data-testid="btn-inject-learned" onClick={injectLearned} disabled={busy !== null} className={wide + " col-span-2"}>
          {busy === "inject" ? "送信中…" : "📤 学習注入 (ルール＋学習)"}
        </button>
      </div>
      <div className="mt-3 flex gap-2">
        <input
          data-testid="free-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="自由文を入力…"
          className="flex-1 rounded-xl bg-slate-800 border border-slate-600 px-3 py-2 text-xs placeholder-slate-500 focus:outline-none focus:border-slate-400"
        />
        <button data-testid="btn-send-free" onClick={sendFree} disabled={busy !== null} className={btn}>
          {busy === "free" ? "…" : "💬 送信"}
        </button>
      </div>
      <p className="mt-2 text-[10px] text-slate-500 leading-relaxed">
        押すと内容をコピー＋共有メニューを起動します。Cowork アプリで貼り付けて送信してください。
      </p>
    </section>
  );
}
