// youtube/scripts/verify_topic_match.test.mjs
// node --test youtube/scripts/verify_topic_match.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseArgs, extractKeywords, verifyTopicMatch } from './verify_topic_match.mjs';

test('parseArgs: デフォルト値 (Phase D2: 5/0.7/7)', () => {
  const a = parseArgs([]);
  assert.equal(a.minOccurrences, 5);
  assert.equal(a.coverage, 0.7);
  assert.equal(a.primaryMinOccurrences, 7);
  assert.equal(a.categoryAware, true);
});

test('parseArgs: 必要オプションを取得', () => {
  const a = parseArgs(['--script', 's.txt', '--topic-id', '011', '--min-occurrences', '5', '--coverage', '0.6', '--primary-min', '10', '--category', '合戦軸']);
  assert.equal(a.script, 's.txt');
  assert.equal(a.topicId, '011');
  assert.equal(a.minOccurrences, 5);
  assert.equal(a.coverage, 0.6);
  assert.equal(a.primaryMinOccurrences, 10);
  assert.equal(a.category, '合戦軸');
});

test('extractKeywords: 「長篠の戦い 鉄砲が変えた戦場」 → ["長篠","鉄砲","戦場"]', () => {
  const kw = extractKeywords('長篠の戦い 鉄砲が変えた戦場');
  assert.deepEqual(kw, ['長篠', '鉄砲', '戦場']);
});

test('extractKeywords: 「織田信長 桶狭間の真実」 → 漢字連続', () => {
  const kw = extractKeywords('織田信長 桶狭間の真実');
  assert.ok(kw.includes('織田信長'));
  assert.ok(kw.includes('桶狭間'));
  assert.ok(kw.includes('真実'));
});

test('extractKeywords: カタカナ含む（「シリーズ」 は GENERIC で除外、「サムライ」 は採用）', () => {
  const kw = extractKeywords('幕末偉人伝 サムライ');
  assert.ok(kw.includes('幕末偉人伝'));
  assert.ok(kw.includes('サムライ'));
});

test('extractKeywords: 「合戦」「戦い」など汎用語は除外', () => {
  const kw = extractKeywords('賤ヶ岳の戦い 秀吉の勝負手');
  assert.ok(!kw.includes('戦い'));
  assert.ok(kw.includes('賤ヶ岳'));
});

test('extractKeywords: 1字漢字は除外（戦/変 単独）', () => {
  const kw = extractKeywords('応仁の乱 一字なし');
  assert.ok(kw.includes('応仁'));
  assert.ok(!kw.includes('乱'));
});

test('verifyTopicMatch: 武田信玄ナレ × 長篠題目 → coverage 0% で FAIL', () => {
  const script = `風林火山。武田信玄。甲斐の虎。戦国最強の武将。
彼の生涯。武田家の血。甲斐源氏。`;
  const keywords = ['長篠', '鉄砲', '戦場'];
  const r = verifyTopicMatch(script, keywords, { minOccurrences: 3, coverage: 0.5 });
  assert.equal(r.pass, false);
  assert.equal(r.coveredCount, 0);
});

test('verifyTopicMatch: 長篠ナレ × 長篠題目 → coverage 高で PASS', () => {
  const script = `長篠の戦いは、織田信長と徳川家康の連合軍が武田勝頼を破った合戦。
鉄砲の三段撃ち。長篠の鉄砲衆。鉄砲、鉄砲、また鉄砲。長篠城。長篠の野。`;
  const keywords = ['長篠', '鉄砲', '戦場'];
  const r = verifyTopicMatch(script, keywords, { minOccurrences: 3, coverage: 0.5 });
  assert.equal(r.pass, true);
  assert.ok(r.coveredCount >= 2);
});

test('Phase D2 verifyTopicMatch: 合戦軸 primary check - 長篠が 7回未満 → FAIL', () => {
  const script = '長篠長篠長篠長篠長篠 鉄砲鉄砲鉄砲鉄砲鉄砲 戦場戦場戦場戦場戦場';
  const keywords = ['長篠', '鉄砲', '戦場'];
  const r = verifyTopicMatch(script, keywords, {
    minOccurrences: 5, coverage: 0.7, primaryMinOccurrences: 7, category: '合戦軸',
  });
  assert.equal(r.coveragePass, true);
  assert.equal(r.primaryPass, false);
  assert.equal(r.pass, false);
  assert.equal(r.primaryKw, '長篠');
  assert.equal(r.primaryCount, 5);
});

test('Phase D2 verifyTopicMatch: 合戦軸 primary check - 長篠が 7回以上 → PASS', () => {
  const script = '長篠長篠長篠長篠長篠長篠長篠長篠 鉄砲鉄砲鉄砲鉄砲鉄砲 戦場戦場戦場戦場戦場';
  const keywords = ['長篠', '鉄砲', '戦場'];
  const r = verifyTopicMatch(script, keywords, {
    minOccurrences: 5, coverage: 0.7, primaryMinOccurrences: 7, category: '合戦軸',
  });
  assert.equal(r.coveragePass, true);
  assert.equal(r.primaryPass, true);
  assert.equal(r.pass, true);
  assert.equal(r.primaryCount, 8);
});

test('Phase D2 verifyTopicMatch: 人物軸 では primary check 適用しない', () => {
  const script = '織田信長織田信長織田信長織田信長織田信長 桶狭間桶狭間桶狭間桶狭間桶狭間 真実真実真実真実真実';
  const keywords = ['織田信長', '桶狭間', '真実'];
  const r = verifyTopicMatch(script, keywords, {
    minOccurrences: 5, coverage: 0.7, primaryMinOccurrences: 7, category: '人物軸',
  });
  assert.equal(r.coveragePass, true);
  assert.equal(r.primaryPass, true);
  assert.equal(r.pass, true);
});

test('Phase D2 verifyTopicMatch: 武田信玄ナレ × 長篠題目 合戦軸 → FAIL', () => {
  const script = `風林火山。武田信玄。甲斐の虎。戦国最強の武将。
彼の生涯。武田家の血。甲斐源氏。武田、武田、武田、武田、武田、武田、武田。`;
  const keywords = ['長篠', '鉄砲', '戦場'];
  const r = verifyTopicMatch(script, keywords, {
    minOccurrences: 5, coverage: 0.7, primaryMinOccurrences: 7, category: '合戦軸',
  });
  assert.equal(r.pass, false);
  assert.equal(r.coveredCount, 0);
  assert.equal(r.primaryCount, 0);
});

test('verifyTopicMatch: 部分的に topic に触れるが大半は別 → FAIL', () => {
  const script = `武田信玄の伝記。風林火山。甲斐の虎。武田家。武田領。
長篠について軽く触れる。残りは信玄の話。武田、武田、武田。`;
  const keywords = ['長篠', '鉄砲', '戦場'];
  const r = verifyTopicMatch(script, keywords, { minOccurrences: 3, coverage: 0.5 });
  assert.equal(r.pass, false);
});

test('verifyTopicMatch: keywords が空なら 0 coverage (pass 値は coverage>=threshold)', () => {
  const r = verifyTopicMatch('whatever', [], { minOccurrences: 3, coverage: 0.5 });
  assert.equal(r.coverage, 0);
  assert.equal(r.pass, false);
});

test('verifyTopicMatch: 閾値 0 なら常に pass (空 keywordsでも)', () => {
  const r = verifyTopicMatch('whatever', [], { minOccurrences: 3, coverage: 0 });
  assert.equal(r.pass, true);
});

test('verifyTopicMatch: perKw レポート構造', () => {
  const r = verifyTopicMatch('長篠長篠長篠 鉄砲', ['長篠', '鉄砲'], { minOccurrences: 3, coverage: 0.5 });
  const nagashino = r.perKw.find(x => x.kw === '長篠');
  const teppou = r.perKw.find(x => x.kw === '鉄砲');
  assert.equal(nagashino.count, 3);
  assert.equal(nagashino.sufficient, true);
  assert.equal(teppou.count, 1);
  assert.equal(teppou.sufficient, false);
});
