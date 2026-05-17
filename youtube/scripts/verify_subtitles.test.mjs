// youtube/scripts/verify_subtitles.test.mjs
// node --test youtube/scripts/verify_subtitles.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  parseArgs,
  normalizeScript,
  parseAss,
  parseSrt,
  parseSubtitle,
  bigrams,
  splitChapters,
  verify,
} from './verify_subtitles.mjs';

test('parseArgs: 必須2引数とthreshold', () => {
  const a = parseArgs(['--script', 'a.txt', '--subtitle', 'b.ass', '--threshold', '0.9']);
  assert.equal(a.script, 'a.txt');
  assert.equal(a.subtitle, 'b.ass');
  assert.equal(a.threshold, 0.9);
});

test('normalizeScript: [VISUAL:...] や ** や # を除去', () => {
  const src = '## タイトル\n[VISUAL: 城]\n織田信長は**桶狭間**で勝利した。\n#日本史 #歴史\n_余談_\n';
  const got = normalizeScript(src);
  assert.ok(!got.includes('VISUAL'));
  assert.ok(!got.includes('**'));
  assert.ok(!got.includes('#日本史'));
  assert.ok(got.includes('織田信長は桶狭間で勝利した'));
  assert.ok(got.includes('余談'));
});

test('normalizeScript: テロップ:ラベル行頭剥がし', () => {
  const got = normalizeScript('ナレーション：これはテストです。\n字幕: 表示文言');
  assert.ok(got.includes('これはテストです'));
  assert.ok(got.includes('表示文言'));
  assert.ok(!got.startsWith('ナレーション'));
});

test('parseAss: Dialogue行を時刻と本文に分解', () => {
  const ass = `[Script Info]
ScriptType: v4.00+

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:03.00,Default,,0,0,0,,織田信長は桶狭間で
Dialogue: 0,0:00:03.00,0:00:06.50,Default,,0,0,0,,今川義元を討ち取った
`;
  const segs = parseAss(ass);
  assert.equal(segs.length, 2);
  assert.equal(segs[0].text, '織田信長は桶狭間で');
  assert.equal(segs[1].text, '今川義元を討ち取った');
  assert.equal(segs[0].start, 0);
  assert.equal(segs[0].end, 3);
  assert.equal(segs[1].end, 6.5);
});

test('parseAss: {\\override} と \\N を吸収', () => {
  const ass = `[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,{\\b1}強調\\Nテキスト
`;
  const segs = parseAss(ass);
  assert.equal(segs.length, 1);
  assert.equal(segs[0].text, '強調 テキスト');
});

test('parseSrt: index付き標準形', () => {
  const srt = `1
00:00:00,000 --> 00:00:03,000
最初の字幕

2
00:00:03,000 --> 00:00:06,000
次の字幕
`;
  const segs = parseSrt(srt);
  assert.equal(segs.length, 2);
  assert.equal(segs[0].text, '最初の字幕');
  assert.equal(segs[1].text, '次の字幕');
});

test('parseSubtitle: 拡張子で自動判別', () => {
  const ass = `[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,A
`;
  const srt = `1
00:00:00,000 --> 00:00:01,000
A
`;
  assert.equal(parseSubtitle('x.ass', ass).length, 1);
  assert.equal(parseSubtitle('x.srt', srt).length, 1);
});

test('bigrams: 句読点と空白を除去して連続文字bigram', () => {
  const b = bigrams('織田信長、桶狭間で勝利した。');
  assert.ok(b.has('織田'));
  assert.ok(b.has('田信'));
  assert.ok(b.has('信長'));
  assert.ok(b.has('長桶'));   // 読点を跨いで連続
  assert.ok(b.has('勝利'));
  assert.ok(b.has('した'));
});

test('splitChapters: 空行 paragraph 分割', () => {
  const t = '第一段。これは前段。\n\n第二段。続き。\n\n第三段。';
  const ch = splitChapters(t);
  assert.equal(ch.length, 3);
  assert.ok(ch[0].startsWith('第一段'));
});

test('verify: テキスト一致 → avg≒1.0 で pass', () => {
  const script = `織田信長は桶狭間の戦いで今川義元を討ち取った。

その後、天下統一に向け進軍した。`;
  const segments = [
    { start: 0, end: 3, text: '織田信長は桶狭間の戦いで' },
    { start: 3, end: 6, text: '今川義元を討ち取った' },
    { start: 6, end: 9, text: '天下統一に向け進軍した' },
  ];
  const r = verify(script, segments, { threshold: 0.85 });
  assert.equal(r.pass, true);
  assert.ok(r.avg >= 0.95, `avg ${r.avg} should be near 1`);
});

test('verify: 字幕に script に無い別文言混入 → fail', () => {
  const script = `織田信長は桶狭間の戦いで今川義元を討ち取った。`;
  const segments = [
    { start: 0, end: 3, text: 'まったく無関係なテキスト宇宙人襲来' },
    { start: 3, end: 6, text: '別の異星人ピザ宅配' },
  ];
  const r = verify(script, segments, { threshold: 0.85 });
  assert.equal(r.pass, false, `avg=${r.avg} should be < 0.85`);
});

test('verify: 部分一致(typo混入)でも 0.85 以上を維持', () => {
  const script = `武田信玄は甲斐の虎と呼ばれた名将である。`;
  const segments = [
    { start: 0, end: 3, text: '武田信玄は甲斐の虎と' },
    { start: 3, end: 6, text: '呼ばれた名将である' },
  ];
  const r = verify(script, segments, { threshold: 0.85 });
  assert.equal(r.pass, true);
});

test('verify: 閾値カスタマイズ', () => {
  const script = `あいうえおかきくけこ`;
  const segments = [{ start: 0, end: 1, text: 'あいうえお' }];
  const r1 = verify(script, segments, { threshold: 0.5 });
  assert.equal(r1.pass, true);
  const r2 = verify(script, segments, { threshold: 0.99 });
  assert.equal(r2.pass, true); // 完全部分集合なのでscore=1
});
