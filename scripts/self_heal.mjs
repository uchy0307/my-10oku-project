// scripts/self_heal.mjs
// 失敗した workflow run のログを取得 → エラー抽出 → Gemini で原因推定 + 修正案 →
// GitHub Issue を起票（同一エラー既存 Open Issue があればコメント追記）。
// 同一エラーが累計3回以上発生していれば `repeated-failure` ラベルを付与する。
//
// env:
//   GH_TOKEN              GitHub Actions の GITHUB_TOKEN（read actions + write issues）
//   WORKFLOW_RUN_ID       失敗した workflow_run の id
//   WORKFLOW_NAME         失敗した workflow の name
//   WORKFLOW_HTML_URL     run の URL（任意、Issue 本文に貼る）
//   GITHUB_REPOSITORY     "owner/repo"
//   GEMINI_API_KEY        Gemini API key（gemini-2.5-flash）

import { Octokit } from '@octokit/rest';
import crypto from 'node:crypto';
import process from 'node:process';

const {
  GH_TOKEN,
  WORKFLOW_RUN_ID,
  WORKFLOW_NAME,
  WORKFLOW_HTML_URL = '',
  GITHUB_REPOSITORY,
  GEMINI_API_KEY,
} = process.env;

if (!GH_TOKEN) {
  console.error('[self_heal] GH_TOKEN が未設定です。');
  process.exit(1);
}
if (!WORKFLOW_RUN_ID) {
  console.error('[self_heal] WORKFLOW_RUN_ID が未設定です。');
  process.exit(1);
}
if (!GITHUB_REPOSITORY) {
  console.error('[self_heal] GITHUB_REPOSITORY が未設定です。');
  process.exit(1);
}

const [owner, repo] = GITHUB_REPOSITORY.split('/');
const octokit = new Octokit({ auth: GH_TOKEN });

const REPEATED_THRESHOLD = 3;
const SELF_HEAL_LABEL = 'self-heal';
const REPEATED_LABEL = 'repeated-failure';

/** workflow run の全ジョブのログを ZIP で取得し、テキスト連結して返す */
async function fetchRunLogs(runId) {
  try {
    const res = await octokit.actions.downloadWorkflowRunLogs({
      owner,
      repo,
      run_id: Number(runId),
    });
    // ZIPバイナリ。シンプルに ASCII 抽出（厳密 unzip しなくても error 行は拾える）。
    const buf = Buffer.from(res.data);
    // 制御文字をスペース化 + 連続スペース圧縮
    const text = buf.toString('latin1').replace(/[\x00-\x08\x0E-\x1F]/g, ' ');
    return text;
  } catch (err) {
    console.warn('[self_heal] ログ取得に失敗:', err?.message || err);
    return '';
  }
}

/** ログ文字列から「エラーっぽい行」を最大 N 行抽出 */
function extractErrorLines(rawLog, maxLines = 40) {
  if (!rawLog) return [];
  const lines = rawLog.split(/\r?\n/);
  const hits = [];
  const errorRe = /(error|fail|fatal|exception|traceback|exit code [1-9]|##\[error\])/i;
  for (const line of lines) {
    if (!line) continue;
    if (errorRe.test(line)) {
      // 行が長すぎるとノイズなので 400 文字に切る
      hits.push(line.length > 400 ? line.slice(0, 400) + '…' : line);
      if (hits.length >= maxLines) break;
    }
  }
  return hits;
}

/** 同一エラー判定用の安定ハッシュ（先頭の代表エラー文を正規化してハッシュ化） */
function fingerprintError(errorLines) {
  const sample = errorLines
    .slice(0, 5)
    .join('\n')
    .replace(/\d+/g, '#')
    .replace(/[a-f0-9]{7,}/gi, '#')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 500);
  return crypto.createHash('sha1').update(sample).digest('hex').slice(0, 10);
}

/** Gemini に原因推定+修正案を聞く（失敗時は null） */
async function askGemini(workflowName, errorLines) {
  if (!GEMINI_API_KEY) {
    console.warn('[self_heal] GEMINI_API_KEY 未設定。Gemini 推定はスキップ。');
    return null;
  }
  const prompt = [
    'あなたは GitHub Actions のセルフヒーリング担当エンジニアです。',
    `失敗した workflow: ${workflowName}`,
    '',
    '以下はログから抽出した代表的なエラー行です。',
    '```',
    errorLines.join('\n'),
    '```',
    '',
    '出力フォーマット（厳守）:',
    '## 推定される原因',
    '- 箇条書きで3点以内',
    '',
    '## 修正案',
    '1. 最も可能性の高い修正手順を3つ以内、具体的なコマンド/ファイル/設定変更で示す',
    '',
    '## 緊急度',
    '- low / medium / high のいずれか1語',
  ].join('\n');

  const url =
    'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=' +
    encodeURIComponent(GEMINI_API_KEY);

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{ role: 'user', parts: [{ text: prompt }] }],
        generationConfig: { temperature: 0.2, maxOutputTokens: 1024 },
      }),
    });
    if (!res.ok) {
      const errText = await res.text();
      console.warn(`[self_heal] Gemini API error ${res.status}: ${errText.slice(0, 300)}`);
      return null;
    }
    const json = await res.json();
    const text =
      json?.candidates?.[0]?.content?.parts?.map((p) => p.text).join('') ?? null;
    return text;
  } catch (err) {
    console.warn('[self_heal] Gemini 呼び出し失敗:', err?.message || err);
    return null;
  }
}

/** self-heal / repeated-failure ラベルを存在保証 */
async function ensureLabels() {
  const labelsToEnsure = [
    { name: SELF_HEAL_LABEL, color: 'd73a4a', description: 'Auto-created by self-heal workflow' },
    { name: REPEATED_LABEL, color: 'b60205', description: 'Same error has occurred 3+ times' },
  ];
  for (const lbl of labelsToEnsure) {
    try {
      await octokit.issues.createLabel({ owner, repo, ...lbl });
    } catch (err) {
      if (err.status !== 422) {
        console.warn(`[self_heal] label ${lbl.name} 生成失敗:`, err.message);
      }
    }
  }
}

/** 同一 fingerprint の既存 Open Issue を検索 */
async function findExistingIssue(fingerprint) {
  const q = `repo:${owner}/${repo} is:issue is:open in:body "fingerprint:${fingerprint}"`;
  try {
    const res = await octokit.search.issuesAndPullRequests({ q });
    return res.data.items[0] || null;
  } catch (err) {
    console.warn('[self_heal] Issue 検索失敗:', err?.message || err);
    return null;
  }
}

/** 同一 fingerprint の累計発生回数（open+closed）を数える */
async function countFingerprintOccurrences(fingerprint) {
  const q = `repo:${owner}/${repo} is:issue in:body "fingerprint:${fingerprint}"`;
  try {
    const res = await octokit.search.issuesAndPullRequests({ q });
    return res.data.total_count || 0;
  } catch {
    return 0;
  }
}

async function main() {
  console.log(`[self_heal] start: workflow=${WORKFLOW_NAME} run=${WORKFLOW_RUN_ID}`);

  const rawLog = await fetchRunLogs(WORKFLOW_RUN_ID);
  const errorLines = extractErrorLines(rawLog);
  if (errorLines.length === 0) {
    errorLines.push('(ログからエラー行を抽出できませんでした。ログZIPの解析が必要です。)');
  }
  const fingerprint = fingerprintError(errorLines);
  console.log(`[self_heal] fingerprint=${fingerprint} errorLines=${errorLines.length}`);

  const gemini = await askGemini(WORKFLOW_NAME || 'unknown', errorLines);

  await ensureLabels();

  const existing = await findExistingIssue(fingerprint);
  const totalOccurrences = (await countFingerprintOccurrences(fingerprint)) + (existing ? 0 : 1);
  const isRepeated = totalOccurrences >= REPEATED_THRESHOLD;

  const runUrl =
    WORKFLOW_HTML_URL ||
    `https://github.com/${owner}/${repo}/actions/runs/${WORKFLOW_RUN_ID}`;

  const body = [
    `**Workflow**: \`${WORKFLOW_NAME}\``,
    `**Run**: ${runUrl}`,
    `**Run ID**: \`${WORKFLOW_RUN_ID}\``,
    `**fingerprint**: \`fingerprint:${fingerprint}\``,
    `**累計発生回数（このfingerprint）**: ${totalOccurrences}`,
    '',
    '## 抽出されたエラー（先頭）',
    '```',
    errorLines.slice(0, 20).join('\n'),
    '```',
    '',
    '## Gemini 推定（gemini-2.5-flash）',
    gemini || '_(Gemini 応答なし。GEMINI_API_KEY 未設定 or API失敗)_',
    '',
    '---',
    '_このIssueは self-heal workflow により自動起票されました。_',
  ].join('\n');

  const labels = [SELF_HEAL_LABEL];
  if (isRepeated) labels.push(REPEATED_LABEL);

  if (existing) {
    // 既存 Issue にコメント追記
    await octokit.issues.createComment({
      owner,
      repo,
      issue_number: existing.number,
      body: [
        `### 再発検知 (run #${WORKFLOW_RUN_ID})`,
        `- run: ${runUrl}`,
        `- 累計: ${totalOccurrences} 回`,
        '',
        '#### 抽出エラー',
        '```',
        errorLines.slice(0, 15).join('\n'),
        '```',
      ].join('\n'),
    });
    if (isRepeated) {
      try {
        await octokit.issues.addLabels({
          owner,
          repo,
          issue_number: existing.number,
          labels: [REPEATED_LABEL],
        });
      } catch (err) {
        console.warn('[self_heal] repeated label 付与失敗:', err.message);
      }
    }
    console.log(`[self_heal] 既存 Issue #${existing.number} にコメント追記`);
  } else {
    const title = `[Self-Heal] ${WORKFLOW_NAME} #${WORKFLOW_RUN_ID} 失敗`;
    const created = await octokit.issues.create({
      owner,
      repo,
      title,
      body,
      labels,
    });
    console.log(`[self_heal] Issue #${created.data.number} を起票`);
  }
}

main().catch((err) => {
  console.error('[self_heal] FATAL:', err);
  process.exit(1);
});
