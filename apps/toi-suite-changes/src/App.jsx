import React, { lazy, Suspense, useState, useEffect, useMemo } from "react";
import { BrowserRouter, Routes, Route, useParams, Link, useNavigate } from "react-router-dom";
import AppGate from "./AppGate.jsx";
import QuickAnalyze from "./QuickAnalyze.jsx";
import Onboarding, { loadOnboarding, clearOnboarding } from "./components/Onboarding.jsx";
import GlobalShareButton from "./components/GlobalShareButton.jsx";
import GlobalRallyNav from "./components/GlobalRallyNav.jsx";
import EngagementBar from "./components/EngagementBar.jsx";
import DailyPick from "./components/DailyPick.jsx";
import Landing from "./pages/Landing.jsx";          // ← 新規
import QuickSample from "./pages/QuickSample.jsx";   // ← 新規
import { recordSession } from "./lib/streak.js";

// Vite glob import - 全Page*.jsxを動的に発見
const pageModules = import.meta.glob("./pages/Page*.jsx");

const C = {
  bg: "#f0ede8", surface: "#ffffff", surface2: "#e8e4de", surface3: "#ddd8d0",
  border: "#c8c0b4", borderActive: "#8a6030",
  gold: "#8a6030", goldLight: "#f5e8d0", goldDim: "#5a3a10",
  goldBg: "rgba(138,96,48,0.08)", text: "#1a1210",
  textSub: "#3a3028", textMuted: "#6a5e50",
};

// 200本のメタデータ (カタログ用)
import { APP_INDEX } from "./appIndex.js";

function Loading() {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", color: C.gold, fontSize: 14 }}>
      🌀 読み込み中...
    </div>
  );
}

function NotFound() {
  return (
    <div style={{ minHeight: "100vh", padding: 40, textAlign: "center", background: C.bg }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>🤔</div>
      <div style={{ fontSize: 18, color: C.gold, fontWeight: 700, marginBottom: 12 }}>そのアプリは見つかりません</div>
      <Link to="/" style={{ color: C.gold }}>← トップに戻る</Link>
    </div>
  );
}

function MasterOnlyGate({ children }) {
  const unlocked = (() => {
    try { return localStorage.getItem("toi_master_v1") === "1"; }
    catch { return false; }
  })();
  if (unlocked) return children;
  return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", padding: 20, boxSizing: "border-box" }}>
      <div style={{ maxWidth: 380, width: "100%", background: C.surface, border: `1.5px solid ${C.border}`, borderRadius: 14, padding: 24, boxSizing: "border-box", textAlign: "center" }}>
        <div style={{ fontSize: 44, marginBottom: 10 }}>🔒</div>
        <div style={{ fontSize: 16, fontWeight: 800, color: C.gold, marginBottom: 8 }}>メンバーのみ利用可能</div>
        <div style={{ fontSize: 11, color: C.textSub, lineHeight: 1.7, marginBottom: 16 }}>
          このアプリ(#000 メタ人格分析)は<br />
          <strong>メンバーシップ加入者専用</strong>です<br />
          マスターコードを入力するとアクセスできます
        </div>
        <Link to="/catalog" style={{ display: "inline-block", padding: "10px 20px", background: `linear-gradient(135deg,${C.gold},${C.goldDim})`, color: "#fff", borderRadius: 10, fontSize: 12, fontWeight: 700, textDecoration: "none" }}>← カタログに戻る</Link>
      </div>
    </div>
  );
}

function PageRoute() {
  const { id } = useParams();
  useEffect(() => { recordSession(id); }, [id]);
  const path = `./pages/Page${id}.jsx`;
  const loader = pageModules[path];
  if (!loader) return <NotFound />;
  const Component = useMemo(() => lazy(loader), [path]);

  if (id === "000") {
    return (
      <MasterOnlyGate>
        <div>
          <BackBar currentId={id} />
          <Suspense fallback={<Loading />}>
            <Component />
          </Suspense>
        </div>
      </MasterOnlyGate>
    );
  }

  return (
    <AppGate appId={id}>
      <div>
        <BackBar currentId={id} />
        <Suspense fallback={<Loading />}>
          <Component />
        </Suspense>
      </div>
    </AppGate>
  );
}

function BackBar({ currentId }) {
  const navigate = useNavigate();
  const [showAnalyze, setShowAnalyze] = useState(false);
  const openChatGPT = async () => {
    const newTab = window.open("about:blank", "_blank");
    let prompt = "";
    try { prompt = await navigator.clipboard.readText(); } catch (e) {}
    let url = "https://chatgpt.com/";
    if (prompt && prompt.length > 5 && prompt.length <= 1500) {
      url = `https://chatgpt.com/?q=${encodeURIComponent(prompt)}`;
    }
    if (newTab) {
      try { newTab.opener = null; newTab.location.href = url; }
      catch (e) { try { newTab.close && newTab.close(); } catch {} window.location.href = url; }
    } else {
      window.location.href = url;
    }
  };
  return (
    <>
      <div style={{ position: "sticky", top: 0, zIndex: 100, background: C.surface, borderBottom: `1px solid ${C.border}`, padding: "8px 10px", display: "flex", alignItems: "center", gap: 4, maxWidth: 540, margin: "0 auto", boxSizing: "border-box" }}>
        <button onClick={() => navigate("/catalog")} style={{ background: "transparent", border: "none", color: C.gold, fontSize: 11, cursor: "pointer", padding: "4px 6px" }}>
          ← カタログ
        </button>
        <div style={{ flex: 1 }} />
        <button onClick={() => setShowAnalyze(true)} title="クリップボードと履歴から簡易分析" style={{ background: C.goldBg, border: `1px solid ${C.borderActive}`, color: C.gold, fontSize: 10, cursor: "pointer", padding: "5px 7px", borderRadius: 6, fontWeight: 700 }}>
          📊 簡易分析
        </button>
        <button onClick={openChatGPT} title="ChatGPTでプロンプト分析" style={{ background: C.goldBg, border: `1px solid ${C.borderActive}`, color: C.gold, fontSize: 10, cursor: "pointer", padding: "5px 7px", borderRadius: 6, fontWeight: 700 }}>
          🤖 AI起動
        </button>
        {currentId !== "000" && (
          <button onClick={() => navigate("/000")} style={{ color: C.gold, fontSize: 10, padding: "5px 7px", borderRadius: 6, background: C.goldBg, border: `1px solid ${C.borderActive}`, fontWeight: 700, cursor: "pointer" }}>
            🧬 #000
          </button>
        )}
      </div>
      {showAnalyze && <QuickAnalyze onClose={() => setShowAnalyze(false)} />}
    </>
  );
}

function CatalogGate({ children }) {
  const [unlocked, setUnlocked] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    if (localStorage.getItem("toi_master_v1") === "1") setUnlocked(true);
  }, []);

  const tryUnlock = async () => {
    setError(""); setVerifying(true);
    const trimmed = code.trim().toUpperCase();
    try {
      const buf = new TextEncoder().encode(trimmed);
      const sha = await crypto.subtle.digest("SHA-256", buf);
      const hash = Array.from(new Uint8Array(sha)).map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 10);
      const { CODE_HASHES } = await import("./codeHashes.js");
      if (hash === CODE_HASHES["MASTER"]) {
        localStorage.setItem("toi_master_v1", "1");
        setUnlocked(true);
      } else {
        setError("マスターコードが正しくありません");
      }
    } catch (e) {
      setError("照合エラー");
    } finally { setVerifying(false); }
  };

  if (unlocked) return children;

  return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", padding: "20px", boxSizing: "border-box" }}>
      <div style={{ maxWidth: 380, width: "100%", background: C.surface, border: `1.5px solid ${C.border}`, borderRadius: 14, padding: 20, boxSizing: "border-box" }}>
        <div style={{ fontSize: 36, textAlign: "center", marginBottom: 8 }}>🗝️</div>
        <div style={{ fontSize: 16, fontWeight: 800, color: C.gold, textAlign: "center", marginBottom: 6 }}>
          200の問い シリーズ カタログ
        </div>
        <div style={{ fontSize: 11, color: C.textSub, textAlign: "center", marginBottom: 20, lineHeight: 1.7 }}>
          全200本のアプリ一覧は<strong>メンバーシップ加入者のみ</strong>閲覧できます<br />
          マスターコードを入力してください
        </div>
        <input
          type="text"
          value={code}
          onChange={e => setCode(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") tryUnlock(); }}
          placeholder="例: TOI-MASTER-XXXXXX"
          autoFocus
          style={{ width: "100%", background: C.bg, border: `1.5px solid ${C.border}`, borderRadius: 10, padding: "12px 10px", fontSize: 12, fontFamily: "monospace", marginBottom: 10, color: C.text, textAlign: "center", letterSpacing: 0.5, boxSizing: "border-box" }}
        />
        {error && <div style={{ fontSize: 11, color: "#8a3030", marginBottom: 10, textAlign: "center" }}>⚠️ {error}</div>}
        <button onClick={tryUnlock} disabled={verifying || !code.trim()} style={{ width: "100%", padding: "12px 0", background: verifying || !code.trim() ? "#ccc" : `linear-gradient(135deg,${C.gold},${C.goldDim})`, border: "none", borderRadius: 10, color: "#fff", fontSize: 13, fontWeight: 700 }}>
          {verifying ? "🌀 照合中..." : "🔓 アンロック"}
        </button>
        <div style={{ marginTop: 18, paddingTop: 14, borderTop: `1px solid ${C.border}`, fontSize: 10, color: C.textMuted, lineHeight: 1.7 }}>
          💡 個別アプリは直接URL (例: /003) でアクセスし、個別コードで解除できます。<br />
          メンバーシップなら全アプリが1コードで解除されます。<br />
          <br />
          <Link to="/" style={{ color: C.gold }}>← トップに戻る</Link>
        </div>
      </div>
    </div>
  );
}

function Catalog() {
  const [search, setSearch] = useState("");
  const [history, setHistory] = useState({});
  const [onboarding, setOnboarding] = useState(() => loadOnboarding());
  const [showOnboarding, setShowOnboarding] = useState(() => !loadOnboarding());

  useEffect(() => {
    const h = {};
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        const m = key && key.match(/^app(\d{2,3})_history_v1$/);
        if (m) {
          try {
            const data = JSON.parse(localStorage.getItem(key) || "[]");
            h[m[1].padStart(3, "0")] = data.length;
          } catch (e) {}
        }
      }
    } catch (e) {}
    setHistory(h);
  }, []);

  if (showOnboarding) {
    return (
      <Onboarding
        onComplete={(payload) => {
          setOnboarding(payload);
          setShowOnboarding(false);
        }}
      />
    );
  }

  const recommendedSet = new Set((onboarding && onboarding.recommended) || []);

  const filtered = APP_INDEX.filter(a => {
    if (!search) return true;
    return a.name.includes(search) || a.id.includes(search) || (a.category || "").includes(search);
  });

  const recommended = !search && recommendedSet.size > 0
    ? APP_INDEX.filter(a => recommendedSet.has(a.id))
    : [];

  const grouped = {};
  for (const a of filtered) {
    const cat = a.category || "その他";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(a);
  }

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: "sans-serif", maxWidth: 540, margin: "0 auto" }}>
      <div style={{ padding: "20px 18px", background: `linear-gradient(135deg,${C.gold},${C.goldDim})`, color: "#fff", position: "relative" }}>
        <div style={{ fontSize: 22, fontWeight: 800, marginBottom: 4 }}>200の問い シリーズ</div>
        <div style={{ fontSize: 11, color: "#f5e8d0", lineHeight: 1.6 }}>自己理解を深める200本のAI対話アプリ統合スイート</div>
        <button
          onClick={() => { clearOnboarding(); setOnboarding(null); setShowOnboarding(true); }}
          title="オンボーディングをやり直す"
          style={{ position: "absolute", top: 14, right: 14, background: "rgba(255,255,255,0.18)", border: "1px solid rgba(255,255,255,0.35)", color: "#fff", fontSize: 10, padding: "5px 9px", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}
        >
          🔄 やり直す
        </button>
      </div>

      <EngagementBar />
      <DailyPick onboarding={onboarding} />

      {recommended.length > 0 && (
        <div style={{ padding: "14px 14px 0" }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: C.gold, marginBottom: 8, padding: "0 4px" }}>
            ✨ あなたへのおすすめ ({recommended.length}本)
          </div>
          <div style={{ display: "flex", overflowX: "auto", gap: 8, padding: "4px 0 8px", marginBottom: 6 }}>
            {recommended.map(a => {
              const hcount = history[a.id] || 0;
              return (
                <Link key={a.id} to={`/${a.id}`} style={{ textDecoration: "none", flexShrink: 0 }}>
                  <div style={{ width: 130, background: C.surface, border: `1.5px solid ${C.borderActive}`, borderRadius: 10, padding: "10px 8px", boxSizing: "border-box" }}>
                    <div style={{ fontSize: 22, textAlign: "center", marginBottom: 4 }}>{a.emoji}</div>
                    <div style={{ fontSize: 10, fontWeight: 700, color: C.text, lineHeight: 1.3, minHeight: 26 }}>#{a.id} {a.name}</div>
                    {hcount > 0 && <div style={{ fontSize: 9, color: C.gold, marginTop: 4 }}>📊 {hcount}回</div>}
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      <Link to="/000" style={{ textDecoration: "none" }}>
        <div style={{ margin: 14, padding: 16, background: C.surface, border: `2px solid ${C.borderActive}`, borderRadius: 14, display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ fontSize: 36 }}>🧬</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 800, color: C.gold }}>#000 200の問い 人格分析</div>
            <div style={{ fontSize: 10, color: C.textSub, marginTop: 4, lineHeight: 1.6 }}>全アプリ実績から横断的にあなたの人格を可視化する最上位メタアプリ</div>
          </div>
          <div style={{ color: C.gold, fontSize: 18 }}>→</div>
        </div>
      </Link>

      <div style={{ padding: "0 14px 14px" }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="🔍 アプリを検索 (例: 強み、副業、感情)"
          style={{ width: "100%", background: C.surface, border: `1.5px solid ${C.border}`, borderRadius: 10, color: C.text, padding: "10px 14px", fontSize: 13, boxSizing: "border-box" }}
        />
      </div>

      <div style={{ padding: "0 14px 40px" }}>
        {Object.entries(grouped).map(([cat, apps]) => (
          <div key={cat} style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: C.gold, marginBottom: 8, padding: "0 4px" }}>📂 {cat} ({apps.length}本)</div>
            {apps.map(a => {
              const hcount = history[a.id] || 0;
              return (
                <Link key={a.id} to={`/${a.id}`} style={{ textDecoration: "none" }}>
                  <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: "10px 12px", marginBottom: 6, display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ fontSize: 20 }}>{a.emoji}</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: C.text }}>#{a.id} {a.name}</div>
                      {hcount > 0 && <div style={{ fontSize: 9, color: C.gold, marginTop: 2 }}>📊 {hcount}回実施済み</div>}
                    </div>
                    <div style={{ color: C.textMuted, fontSize: 14 }}>›</div>
                  </div>
                </Link>
              );
            })}
          </div>
        ))}
        {filtered.length === 0 && (
          <div style={{ textAlign: "center", padding: 40, color: C.textMuted, fontSize: 12 }}>
            該当するアプリがありません
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  useEffect(() => {
    document.body.style.background = "#f0ede8";
    document.documentElement.style.background = "#f0ede8";
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        {/* 公開LP */}
        <Route path="/" element={<Landing />} />
        <Route path="/sample" element={<QuickSample />} />
        {/* 会員カタログ */}
        <Route path="/catalog" element={<CatalogGate><Catalog /></CatalogGate>} />
        {/* 個別アプリ */}
        <Route path="/:id" element={<PageRoute />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      <GlobalShareButton />
      <GlobalRallyNav />
    </BrowserRouter>
  );
}
