#!/usr/bin/env node
/**
 * 既投稿の音声ドラマ動画 description を視聴者向けの本編訴求のみに update。
 * 内部実装 (edge-tts / 試作版 / 後日公開等) を一切排除。
 */
import fs from 'node:fs';
import path from 'node:path';
import { google } from 'googleapis';

const ROOT = process.cwd();
if (fs.existsSync(path.join(ROOT, '.env'))) {
  for (const line of fs.readFileSync(path.join(ROOT, '.env'), 'utf8').split(/\r?\n/)) {
    const m = line.match(/^([A-Z_][A-Z0-9_]*)=(.*)$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
}

// 修正対象: 音声ドラマ既投稿 1 本
const TARGETS = [
  {
    videoId: 'QYKdjDxSIyM',
    kind: 'history',
    title: '島津義弘 関ヶ原 敵中突破の刻｜捨て奸の死兵が示した魂',
    description: [
      '慶長五年九月十五日、関ヶ原。',
      '十五万対十五万の戦場で、薩摩の老将・島津義弘は齢六十六、率いる兵わずか千五百で布陣した。',
      '半日で西軍は崩壊、退路は閉ざされる。',
      '義弘が選んだのは「敵中突破」──家康の本陣を貫いて駆け抜ける、戦国史上もっとも誇り高い退却劇。',
      '捨て奸（すてがまり）。命を捨てて主君を逃がす死兵の戦法で、',
      '千五百のうち薩摩に帰り着いたのはわずか八十余名。',
      '死ぬ覚悟が、生き残る道を開く。',
      'これが薩摩武士の哲学であり、三百年後の明治維新を中心となった薩摩藩の伏線となった。',
      '',
      '#日本史 #戦国 #島津義弘 #関ヶ原 #薩摩武士 #武士道',
    ].join('\n'),
    tags: ['日本史', '戦国時代', '島津義弘', '関ヶ原', '薩摩武士', '武士道', '捨て奸'],
    categoryId: '22',
  },
];

const clientId = process.env.YOUTUBE_CLIENT_ID;
const clientSec = process.env.YOUTUBE_CLIENT_SECRET;

async function update(t) {
  const refresh = t.kind === 'history'
    ? process.env.YOUTUBE_REFRESH_TOKEN
    : process.env.OTONA_YOUTUBE_REFRESH_TOKEN;
  const oa = new google.auth.OAuth2(clientId, clientSec);
  oa.setCredentials({ refresh_token: refresh });
  const youtube = google.youtube({ version: 'v3', auth: oa });

  console.log(`updating ${t.videoId} (${t.kind}): ${t.title}`);
  try {
    await youtube.videos.update({
      part: ['snippet'],
      requestBody: {
        id: t.videoId,
        snippet: {
          title: t.title.slice(0, 95),
          description: t.description.slice(0, 4500),
          tags: t.tags.slice(0, 15),
          categoryId: t.categoryId,
          defaultLanguage: 'ja',
          defaultAudioLanguage: 'ja',
        },
      },
    });
    console.log(`  -> OK`);
  } catch (e) {
    console.error(`  -> FAIL: ${e?.message || e}`);
  }
}

for (const t of TARGETS) await update(t);
console.log('done');
