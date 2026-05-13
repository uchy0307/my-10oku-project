// note-auto/capture_refresh_token.mjs
// YouTube Data API用のrefresh_tokenを取得する1回限りのスクリプト
//
// 使い方:
//   1. cd C:\Users\user\Documents\10oku-project
//   2. node note-auto/capture_refresh_token.mjs
//   3. 表示されたURLをブラウザで開く（自動で開きます）
//   4. 「許可」をクリック
//   5. localhost にリダイレクトされてトークンがコンソールに表示される

import http from 'node:http';
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const CLIENT_SECRET_PATH = path.join(__dirname, 'client_secret.json');

const SCOPES = [
  'https://www.googleapis.com/auth/youtube.upload',
  'https://www.googleapis.com/auth/youtube',
];

async function main() {
  const raw = await fs.readFile(CLIENT_SECRET_PATH, 'utf-8');
  const cfg = JSON.parse(raw);
  const inst = cfg.installed || cfg.web;
  if (!inst) throw new Error('client_secret.json に installed/web キーがありません');
  const CLIENT_ID = inst.client_id;
  const CLIENT_SECRET = inst.client_secret;
  const AUTH_URI = inst.auth_uri || 'https://accounts.google.com/o/oauth2/auth';
  const TOKEN_URI = inst.token_uri || 'https://oauth2.googleapis.com/token';

  // ローカルサーバー先起動（OSにポートを自動割当てさせる）
  let REDIRECT_URI = null;
  const codePromise = new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      try {
        const u = new URL(req.url, REDIRECT_URI);
        const c = u.searchParams.get('code');
        const err = u.searchParams.get('error');
        if (err) {
          res.writeHead(400, { 'Content-Type': 'text/html; charset=utf-8' });
          res.end(`<h1>エラー: ${err}</h1>`);
          server.close();
          reject(new Error(`OAuth error: ${err}`));
          return;
        }
        if (!c) {
          res.writeHead(400, { 'Content-Type': 'text/html; charset=utf-8' });
          res.end('<h1>code パラメータが見つかりません</h1>');
          return;
        }
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(`
          <html><body style="font-family:sans-serif;padding:40px">
          <h1>成功</h1>
          <p>このウィンドウは閉じて構いません。ターミナルに戻ってください。</p>
          </body></html>`);
        server.close();
        resolve(c);
      } catch (e) {
        reject(e);
      }
    });
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const addr = server.address();
      REDIRECT_URI = `http://localhost:${addr.port}`;
      console.log(`ローカルサーバー起動: ${REDIRECT_URI} （Allow待ち...）`);

      const authUrl = new URL(AUTH_URI);
      authUrl.searchParams.set('client_id', CLIENT_ID);
      authUrl.searchParams.set('redirect_uri', REDIRECT_URI);
      authUrl.searchParams.set('response_type', 'code');
      authUrl.searchParams.set('scope', SCOPES.join(' '));
      authUrl.searchParams.set('access_type', 'offline');
      authUrl.searchParams.set('prompt', 'consent');

      console.log('================================================');
      console.log('以下のURLをブラウザで開き、「許可」をクリックしてください:');
      console.log(authUrl.toString());
      console.log('================================================');

      // ブラウザを自動で開く（Windows: PowerShell経由で & エスケープ問題回避）
      try {
        const psCmd = `Start-Process '${authUrl.toString().replace(/'/g, "''")}'`;
        spawn('powershell', ['-NoProfile', '-Command', psCmd], { detached: true });
      } catch (e) {
        console.warn('ブラウザ自動起動失敗。URLを手動で開いてください:', e.message);
      }
    });
  });
  const code = await codePromise;

  console.log('code 受信完了。refresh_token を取得中...');

  // code → tokens 交換
  const body = new URLSearchParams({
    code,
    client_id: CLIENT_ID,
    client_secret: CLIENT_SECRET,
    redirect_uri: REDIRECT_URI,
    grant_type: 'authorization_code',
  });

  const res = await fetch(TOKEN_URI, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });
  const tokens = await res.json();
  if (!res.ok) {
    console.error('Token交換失敗:', tokens);
    process.exit(1);
  }

  console.log('');
  console.log('========================================');
  console.log('SUCCESS!');
  console.log('========================================');
  console.log('CLIENT_ID:        ', CLIENT_ID);
  console.log('CLIENT_SECRET:    ', CLIENT_SECRET);
  console.log('REFRESH_TOKEN:    ', tokens.refresh_token);
  console.log('========================================');
  console.log('');
  console.log('ファイルにも保存しました: note-auto/youtube_tokens.json');

  // ローカルファイル保存（GitHub Secretへ転記用）
  const tokensPath = path.join(__dirname, 'youtube_tokens.json');
  await fs.writeFile(
    tokensPath,
    JSON.stringify({
      YOUTUBE_CLIENT_ID: CLIENT_ID,
      YOUTUBE_CLIENT_SECRET: CLIENT_SECRET,
      YOUTUBE_REFRESH_TOKEN: tokens.refresh_token,
      access_token: tokens.access_token,
      expires_in: tokens.expires_in,
      scope: tokens.scope,
      token_type: tokens.token_type,
      capturedAt: new Date().toISOString(),
    }, null, 2),
    'utf-8'
  );
  console.log('完了。');
}

main().catch((err) => {
  console.error('FAILED:', err);
  process.exit(1);
});
