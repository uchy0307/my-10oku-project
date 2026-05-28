import React, { useState } from "react";
import { Link } from "react-router-dom";

/**
 * QuickSample.jsx
 * 無料3問のミニ自己分析。
 * - 6軸のうち代表3軸（決断力・洞察力・大義）を簡易判定
 * - 結果画面で「もっと深く知るならnote購入→カタログ解錠」CTA
 */

const C = {
  bg: "#f0ede8",
  surface: "#ffffff",
  gold: "#8a6030",
  goldDim: "#5a3a10",
  goldLight: "#f5e8d0",
  text: "#1a1210",
  textSub: "#3a3028",
};

const QUESTIONS = [
  {
    axis: "決断力",
    icon: "⚔️",
    q: "重大な決断を迫られたとき、あなたは",
    choices: [
      { t: "状況を整理して即決する", s: 3 },
      { t: "選択肢を比較して決める", s: 2 },
      { t: "信頼できる人に相談する", s: 1 },
      { t: "判断を先送りしがち", s: 0 },
    ],
  },
  {
    axis: "洞察力",
    icon: "👁️",
    q: "初対面の人を見るとき、あなたが最も気にするのは",
    choices: [
      { t: "言葉にしない素ぶり・気配", s: 3 },
      { t: "話の論理や中身", s: 2 },
      { t: "肩書きや経歴", s: 1 },
      { t: "あまり気にしない", s: 0 },
    ],
  },
  {
    axis: "大義",
    icon: "🏯",
    q: "あなたが行動する一番の動機は",
    choices: [
      { t: "自分や家族を超えた何かのため", s: 3 },
      { t: "自分の信念・矜持のため", s: 2 },
      { t: "実利・成果のため", s: 1 },
      { t: "やる気が出るときだけ", s: 0 },
    ],
  },
];

const PROFILES = [
  {
    range: [8, 9],
    name: "侍型",
    icon: "⚔️",
    text:
      "覚悟・矜持・大義のすべてを宿す稀有な人。決断は鋭く、本質を見抜き、自分を超えた何かのために動ける。さらに200の問いで自分の輪郭を細かく彫り込めば、人を導く器になります。",
  },
  {
    range: [6, 7],
    name: "求道型",
    icon: "🏯",
    text:
      "強い軸を持ちながら、まだ磨き残しに気づいている人。残り3軸（精神力・適応力・規律心）を強化すれば、揺るがぬ自分になれます。",
  },
  {
    range: [4, 5],
    name: "彷徨型",
    icon: "🌫️",
    text:
      "葛藤の中で問いを抱えている人。最も成長余地が大きい段階です。200の問いで自分の弱みを直視し、強みを再発見する旅が必要。",
  },
  {
    range: [0, 3],
    name: "兆し型",
    icon: "🌱",
    text:
      "まだ自分を知ることが始まったばかり。ここから6軸すべてを少しずつ整えていけば、半年後には別人になれます。",
  },
];

export default function QuickSample() {
  const [step, setStep] = useState(0);
  const [scores, setScores] = useState([]);

  if (step < QUESTIONS.length) {
    const q = QUESTIONS[step];
    return (
      <div
        style={{
          minHeight: "100vh",
          background: C.bg,
          padding: "24px 16px",
          fontFamily: "system-ui,sans-serif",
        }}
      >
        <div style={{ maxWidth: 480, margin: "0 auto" }}>
          <div
            style={{
              textAlign: "center",
              fontSize: 11,
              color: C.gold,
              marginBottom: 8,
              letterSpacing: "0.2em",
            }}
          >
            {step + 1} / {QUESTIONS.length}
          </div>
          <div
            style={{
              fontSize: 14,
              color: C.gold,
              fontWeight: 800,
              textAlign: "center",
              marginBottom: 6,
            }}
          >
            {q.icon} {q.axis}
          </div>
          <h2
            style={{
              fontSize: 19,
              color: C.text,
              fontWeight: 700,
              textAlign: "center",
              lineHeight: 1.6,
              marginBottom: 28,
              fontFamily: '"Hiragino Mincho ProN","Yu Mincho",serif',
            }}
          >
            {q.q}
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {q.choices.map((c, i) => (
              <button
                key={i}
                onClick={() => {
                  setScores([...scores, c.s]);
                  setStep(step + 1);
                }}
                style={{
                  padding: "16px 18px",
                  background: C.surface,
                  border: `1.5px solid ${C.goldLight}`,
                  borderRadius: 14,
                  textAlign: "left",
                  cursor: "pointer",
                  fontSize: 14,
                  color: C.text,
                  fontWeight: 600,
                  fontFamily: "system-ui,sans-serif",
                  transition: "all 0.15s",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = C.gold;
                  e.currentTarget.style.background = C.goldLight;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = C.goldLight;
                  e.currentTarget.style.background = C.surface;
                }}
              >
                {c.t}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Result screen
  const total = scores.reduce((s, x) => s + x, 0);
  const profile =
    PROFILES.find((p) => total >= p.range[0] && total <= p.range[1]) ||
    PROFILES[PROFILES.length - 1];

  return (
    <div
      style={{
        minHeight: "100vh",
        background: C.bg,
        padding: "40px 16px",
        fontFamily: "system-ui,sans-serif",
      }}
    >
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ fontSize: 56, marginBottom: 8 }}>{profile.icon}</div>
          <div
            style={{
              fontSize: 11,
              letterSpacing: "0.3em",
              color: C.gold,
              marginBottom: 6,
            }}
          >
            あなたの傾向は
          </div>
          <h1
            style={{
              fontSize: 36,
              fontWeight: 900,
              color: C.goldDim,
              lineHeight: 1.2,
              marginBottom: 4,
            }}
          >
            {profile.name}
          </h1>
          <div style={{ fontSize: 12, color: C.textSub }}>
            （3軸合計 {total} / 9 点）
          </div>
        </div>

        <div
          style={{
            background: C.surface,
            border: `1.5px solid ${C.goldLight}`,
            borderRadius: 16,
            padding: 20,
            marginBottom: 24,
          }}
        >
          <div
            style={{
              fontSize: 14,
              color: C.text,
              lineHeight: 1.9,
              fontFamily: '"Hiragino Mincho ProN","Yu Mincho",serif',
            }}
          >
            {profile.text}
          </div>
        </div>

        <div
          style={{
            background: C.goldLight,
            borderRadius: 16,
            padding: "22px 18px",
            marginBottom: 16,
            textAlign: "center",
          }}
        >
          <div
            style={{
              fontSize: 13,
              fontWeight: 800,
              color: C.goldDim,
              marginBottom: 10,
            }}
          >
            残り3軸 + 200の問いで深く知る
          </div>
          <div
            style={{
              fontSize: 11,
              color: C.textSub,
              lineHeight: 1.7,
              marginBottom: 16,
            }}
          >
            精神力・適応力・規律心の3軸を含む完全分析と、
            <br />
            200本のAI対話アプリは note記事の購入で解錠されます。
          </div>
          <a
            href="https://note.com/happy_happy_4649"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "inline-block",
              padding: "12px 28px",
              borderRadius: 999,
              background: `linear-gradient(135deg,${C.gold},${C.goldDim})`,
              color: "#fff",
              fontSize: 13,
              fontWeight: 800,
              textDecoration: "none",
              marginBottom: 12,
            }}
          >
            📝 note記事を見る（1本100円〜）
          </a>
          <div>
            <Link
              to="/catalog"
              style={{
                fontSize: 11,
                color: C.gold,
                textDecoration: "underline",
              }}
            >
              既にコードを持っている →
            </Link>
          </div>
        </div>

        <div style={{ textAlign: "center", marginTop: 24 }}>
          <Link
            to="/"
            style={{ fontSize: 11, color: C.textSub, textDecoration: "none" }}
          >
            ← トップに戻る
          </Link>
        </div>
      </div>
    </div>
  );
}
