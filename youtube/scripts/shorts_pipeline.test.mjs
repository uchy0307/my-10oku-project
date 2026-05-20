// youtube/scripts/shorts_pipeline.test.mjs
// node --test youtube/scripts/shorts_pipeline.test.mjs
//
// 純粋関数 (pickUnusedComboPure / isDuplicateSegment / backfillUsedSegments) の
// 振る舞いをテストする。YouTube API は呼ばない。

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  pickUnusedComboPure,
  isDuplicateSegment,
  backfillUsedSegments,
  START_GRID,
  CLIP_DURATION,
  TAIL_BUFFER,
  DUP_TOLERANCE_SEC,
} from './shorts_pipeline.mjs';

// ──────────────────────────────────────────────────────────────────────────
// isDuplicateSegment
// ──────────────────────────────────────────────────────────────────────────

test('isDuplicateSegment: 同 videoId・同 startSec → 重複', () => {
  const used = [{ sourceVideoId: 'AAA', startSec: 60 }];
  assert.equal(isDuplicateSegment(used, 'AAA', 60), true);
});

test('isDuplicateSegment: 同 videoId・±5s 以内 → 重複', () => {
  const used = [{ sourceVideoId: 'AAA', startSec: 60 }];
  assert.equal(isDuplicateSegment(used, 'AAA', 64), true);
  assert.equal(isDuplicateSegment(used, 'AAA', 55), true);
});

test('isDuplicateSegment: 同 videoId・±5s 超え → 非重複', () => {
  const used = [{ sourceVideoId: 'AAA', startSec: 60 }];
  assert.equal(isDuplicateSegment(used, 'AAA', 70), false);
  assert.equal(isDuplicateSegment(used, 'AAA', 300), false);
});

test('isDuplicateSegment: 別 videoId → 非重複', () => {
  const used = [{ sourceVideoId: 'AAA', startSec: 60 }];
  assert.equal(isDuplicateSegment(used, 'BBB', 60), false);
});

test('isDuplicateSegment: 空 used → false', () => {
  assert.equal(isDuplicateSegment([], 'AAA', 60), false);
  assert.equal(isDuplicateSegment(null, 'AAA', 60), false);
  assert.equal(isDuplicateSegment(undefined, 'AAA', 60), false);
});

test('isDuplicateSegment: startSec を持たない record は無視', () => {
  const used = [{ sourceVideoId: 'AAA' /* startSec なし */ }];
  assert.equal(isDuplicateSegment(used, 'AAA', 60), false);
});

// ──────────────────────────────────────────────────────────────────────────
// pickUnusedComboPure
// ──────────────────────────────────────────────────────────────────────────

const longVid = (id, sec = 1800) => ({ videoId: id, durationSec: sec });

test('pickUnusedComboPure: 空の used に対して 1 番目の startSec × 1 番目の videoId が選ばれる', () => {
  const cands = [longVid('A'), longVid('B'), longVid('C')];
  const picked = pickUnusedComboPure(cands, []);
  assert.deepEqual(picked, { sourceVideoId: 'A', startSec: START_GRID[0] });
});

test('pickUnusedComboPure: rotation は startSec 外 × videoId 内 (まず別動画を優先)', () => {
  const cands = [longVid('A'), longVid('B'), longVid('C')];
  // A@60 を used に追加 → 次は B@60 (同じ startSec のまま別動画)
  let used = [{ sourceVideoId: 'A', startSec: START_GRID[0] }];
  let picked = pickUnusedComboPure(cands, used);
  assert.deepEqual(picked, { sourceVideoId: 'B', startSec: START_GRID[0] });
  used.push({ sourceVideoId: 'B', startSec: START_GRID[0] });
  picked = pickUnusedComboPure(cands, used);
  assert.deepEqual(picked, { sourceVideoId: 'C', startSec: START_GRID[0] });
  used.push({ sourceVideoId: 'C', startSec: START_GRID[0] });
  // 全 videoId が startSec=60 を使い切ったので 次の startSec=300 に進む。最初は A。
  picked = pickUnusedComboPure(cands, used);
  assert.deepEqual(picked, { sourceVideoId: 'A', startSec: START_GRID[1] });
});

test('pickUnusedComboPure: duration < startSec + clipDuration + tailBuffer なら skip', () => {
  // A は 100s しかないので startSec=60 でも 60+58+30=148 > 100 でアウト
  // 同様に B も 短すぎる。C だけが使える。
  const cands = [
    { videoId: 'A', durationSec: 100 },
    { videoId: 'B', durationSec: 100 },
    { videoId: 'C', durationSec: 1800 },
  ];
  const picked = pickUnusedComboPure(cands, []);
  assert.equal(picked.sourceVideoId, 'C');
  assert.equal(picked.startSec, START_GRID[0]);
});

test('pickUnusedComboPure: 全 combo 使い切ったら null', () => {
  const cands = [longVid('A', 200)]; // 200s 動画 → grid[0]=60s でしか組合せ無い (300s 以降は overflow)
  // 200 >= 60 + 58 + 30 = 148 → OK
  // 200 >= 300 + 58 + 30 = 388 → NG
  const used = [{ sourceVideoId: 'A', startSec: 60 }];
  const picked = pickUnusedComboPure(cands, used);
  assert.equal(picked, null);
});

test('pickUnusedComboPure: 重複は許容差以内も skip する', () => {
  const cands = [longVid('A')];
  const used = [{ sourceVideoId: 'A', startSec: 62 }]; // 60 と ±2s 以内
  // A@60 は重複扱いで skip → A@300 が選ばれる
  const picked = pickUnusedComboPure(cands, used);
  assert.deepEqual(picked, { sourceVideoId: 'A', startSec: 300 });
});

test('pickUnusedComboPure: candidates 空なら null', () => {
  assert.equal(pickUnusedComboPure([], []), null);
  assert.equal(pickUnusedComboPure(null, []), null);
});

test('pickUnusedComboPure: 不正 candidate (durationSec 無し) は skip', () => {
  const cands = [
    { videoId: 'X' /* durationSec 無し */ },
    longVid('Y'),
  ];
  const picked = pickUnusedComboPure(cands, []);
  assert.equal(picked.sourceVideoId, 'Y');
});

test('pickUnusedComboPure: 既存 4 本 (重複バグ再現シナリオ) が同じ source/start を返さない', () => {
  // 旧バグ: source 同一 + startSec=30 固定 → 4 連続同じ Short
  // 新ロジックでは startSec は START_GRID から選ばれ、used に既存 (A,30) があっても
  // (A,60), (B,60), ... と別 combination を選ぶ。
  const cands = [longVid('A'), longVid('B'), longVid('C'), longVid('D')];
  const used = [
    { sourceVideoId: 'A', startSec: 30 },
    { sourceVideoId: 'B', startSec: 30 },
    { sourceVideoId: 'C', startSec: 30 },
    { sourceVideoId: 'D', startSec: 30 },
  ];
  const picked1 = pickUnusedComboPure(cands, used);
  assert.deepEqual(picked1, { sourceVideoId: 'A', startSec: 60 });
  const picked2 = pickUnusedComboPure(cands, [...used, picked1]);
  assert.deepEqual(picked2, { sourceVideoId: 'B', startSec: 60 });
  // どちらも startSec=30 ではないので旧バグ再発しない
  assert.notEqual(picked1.startSec, 30);
  assert.notEqual(picked2.startSec, 30);
});

// ──────────────────────────────────────────────────────────────────────────
// backfillUsedSegments
// ──────────────────────────────────────────────────────────────────────────

test('backfillUsedSegments: 旧 records (startSec 無し) を default 30 で usedSegments に詰める', () => {
  const state = {
    records: [
      { sourceVideoId: 'X', shortsVideoId: 'sx1', shortsUrl: 'u1', uploadedAt: '2026-05-18T00:00:00Z' },
      { sourceVideoId: 'Y', shortsVideoId: 'sy1', shortsUrl: 'u2', uploadedAt: '2026-05-19T00:00:00Z' },
    ],
    usedSegments: [],
  };
  const { changed, state: next } = backfillUsedSegments(state);
  assert.equal(changed, true);
  assert.equal(next.usedSegments.length, 2);
  assert.equal(next.usedSegments[0].sourceVideoId, 'X');
  assert.equal(next.usedSegments[0].startSec, 30);
  assert.equal(next.usedSegments[0].legacy, true);
});

test('backfillUsedSegments: 既に usedSegments にある combo は重複追加しない', () => {
  const state = {
    records: [
      { sourceVideoId: 'X', shortsVideoId: 'sx1', shortsUrl: 'u1', uploadedAt: 't' },
    ],
    usedSegments: [
      { sourceVideoId: 'X', startSec: 30 },
    ],
  };
  const { changed, state: next } = backfillUsedSegments(state);
  assert.equal(changed, false);
  assert.equal(next.usedSegments.length, 1);
});

test('backfillUsedSegments: records が無くても crash しない', () => {
  const { changed } = backfillUsedSegments({});
  assert.equal(changed, false);
});

// ──────────────────────────────────────────────────────────────────────────
// 定数の sanity check
// ──────────────────────────────────────────────────────────────────────────

test('定数 sanity: START_GRID は単調増加', () => {
  for (let i = 1; i < START_GRID.length; i++) {
    assert.ok(START_GRID[i] > START_GRID[i - 1], 'START_GRID must be strictly increasing at index ' + i);
  }
});

test('定数 sanity: CLIP_DURATION ≤ 59 (Shorts 60s 制限)', () => {
  assert.ok(CLIP_DURATION <= 59);
  assert.ok(CLIP_DURATION > 0);
});

test('定数 sanity: TAIL_BUFFER と DUP_TOLERANCE_SEC は妥当な範囲', () => {
  assert.ok(TAIL_BUFFER >= 0);
  assert.ok(DUP_TOLERANCE_SEC >= 0);
});
