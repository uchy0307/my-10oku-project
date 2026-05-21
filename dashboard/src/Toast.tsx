import { useEffect } from "react";

type Props = {
  message: string;
  tone?: "info" | "ok" | "error";
  onDismiss: () => void;
};

export function Toast({ message, tone = "info", onDismiss }: Props) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 3000);
    return () => clearTimeout(t);
  }, [message, onDismiss]);

  const cls =
    tone === "ok"
      ? "bg-emerald-600/90 text-white"
      : tone === "error"
      ? "bg-red-600/90 text-white"
      : "bg-slate-800 text-slate-100";

  return (
    <div className="fixed left-1/2 -translate-x-1/2 bottom-6 z-50 pointer-events-none">
      <div className={`${cls} rounded-full px-4 py-2 text-sm shadow-lg`}>
        {message}
      </div>
    </div>
  );
}
