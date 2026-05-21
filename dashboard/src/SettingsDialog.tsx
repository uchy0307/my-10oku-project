import { useEffect, useState } from "react";
import { clearPat, getPat, setPat } from "./github";

type Props = { open: boolean; onClose: () => void; onSaved: () => void; };

export function SettingsDialog({ open, onClose, onSaved }: Props) {
  const [value, setValue] = useState("");
  const [hasExisting, setHasExisting] = useState(false);

  useEffect(() => {
    if (open) { setHasExisting(!!getPat()); setValue(""); }
  }, [open]);

  if (!open) return null;

  const handleSave = () => { const v = value.trim(); if (!v) return; setPat(v); onSaved(); onClose(); };
  const handleClear = () => { clearPat(); setHasExisting(false); onSaved(); };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div className="w-full max-w-sm rounded-2xl bg-panel border border-slate-700 p-5" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-base font-bold mb-1">設定</h2>
        <p className="text-[11px] text-slate-400 mb-4">GitHub PAT (workflow scope) を入力。localStorage に保存され、▶実行ボタンの workflow_dispatch に使用されます。</p>
        <label className="block text-xs text-slate-300 mb-1">GitHub Personal Access Token</label>
        <input type="password" value={value} onChange={(e) => setValue(e.target.value)} placeholder={hasExisting ? "保存済み (再入力で上書き)" : "ghp_xxx / github_pat_xxx"} className="w-full rounded-lg bg-ink border border-slate-600 px-3 py-2 text-sm focus:outline-none focus:border-amber-500" autoComplete="off" />
        <div className="mt-4 flex items-center justify-between gap-2">
          {hasExisting ? <button onClick={handleClear} className="text-xs text-red-400 hover:text-red-300 underline">保存済み PAT を削除</button> : <span />}
          <div className="flex gap-2">
            <button onClick={onClose} className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs">閉じる</button>
            <button onClick={handleSave} disabled={!value.trim()} className="rounded-lg bg-amber-500 text-slate-900 font-semibold px-3 py-1.5 text-xs disabled:opacity-40">保存</button>
          </div>
        </div>
        <p className="mt-4 text-[10px] text-slate-500 leading-relaxed">PAT 発行: GitHub → Settings → Developer settings → Personal access tokens → Fine-grained → Repository access: my-10oku-project → Permissions: Actions=Read and Write。</p>
      </div>
    </div>
  );
}
