import { CONFIG } from "./config";

const API = "https://api.github.com";

export function getPat(): string | null {
  try {
    return localStorage.getItem(CONFIG.PAT_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setPat(pat: string): void {
  try {
    localStorage.setItem(CONFIG.PAT_STORAGE_KEY, pat);
  } catch {/* ignore */}
}

export function clearPat(): void {
  try {
    localStorage.removeItem(CONFIG.PAT_STORAGE_KEY);
  } catch {/* ignore */}
}

function authHeaders(pat: string): HeadersInit {
  return {
    Authorization: `Bearer ${pat}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
  };
}

export type DispatchInput = Record<string, string>;

export async function dispatchWorkflow(workflowFile: string, inputs: DispatchInput, pat: string): Promise<void> {
  const url = `${API}/repos/${CONFIG.GITHUB_OWNER}/${CONFIG.GITHUB_REPO}/actions/workflows/${workflowFile}/dispatches`;
  const res = await fetch(url, { method: "POST", headers: { ...authHeaders(pat), "Content-Type": "application/json" }, body: JSON.stringify({ ref: CONFIG.GITHUB_REF, inputs }) });
  if (res.status !== 204) { const txt = await res.text().catch(() => ""); throw new Error(`dispatch ${res.status}: ${txt.slice(0, 200)}`); }
}

export type Run = { id: number; status: string; conclusion: string | null; html_url: string; created_at: string; event: string; };

export async function listRecentRuns(workflowFile: string, pat: string, perPage = 5): Promise<Run[]> {
  const url = `${API}/repos/${CONFIG.GITHUB_OWNER}/${CONFIG.GITHUB_REPO}/actions/workflows/${workflowFile}/runs?event=workflow_dispatch&per_page=${perPage}`;
  const res = await fetch(url, { headers: authHeaders(pat) });
  if (!res.ok) throw new Error(`runs ${res.status}`);
  const json = await res.json();
  return (json?.workflow_runs ?? []) as Run[];
}

export function nextCycleIndex(storageKey: string, min: number, max: number): number {
  let last: number;
  try { last = parseInt(localStorage.getItem(storageKey) || String(min - 1), 10); } catch { last = min - 1; }
  let next = last + 1;
  if (next > max || next < min) next = min;
  try { localStorage.setItem(storageKey, String(next)); } catch {/* ignore */}
  return next;
}

export function padIndex(n: number, pad: number): string { return String(n).padStart(pad, "0"); }
