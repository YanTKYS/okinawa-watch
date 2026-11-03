const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const display = require('../web/display.js');
const policy = require('../config/rules.json').display;
const initial = require('../data/articles.json').articles;
const today = '2026-11-03';
const article = (changes = {}) => ({
  id: 'test', title: '公園の催し', url: 'https://example.com/a', labels: ['発見'],
  topic: '催し・体験', published_at: '2026-11-03', collected_at: '2026-11-03T10:00:00+09:00', timing: null, ...changes
});

test('initial 20 records: 17 visible, 15 unverified events, 2 ended and 1 old', () => {
  const before = JSON.stringify(initial);
  const entries = display.entries(initial, policy, today);
  assert.equal(entries.filter(e => display.visible(e)).length, 17);
  const events = entries.filter(e => display.visible(e, {filter: '催し（日付未確認）'}));
  assert.equal(events.length, 15);
  for (const phrase of ['11月7日・8日', '11/8', '11/28・29']) {
    assert.ok(events.some(e => e.article.title.includes(phrase)), phrase);
  }
  assert.equal(entries.filter(e => display.visible(e, {filter: '今だけ'})).length, 0);
  assert.equal(entries.filter(e => display.visible(e, {includeEnded: true, includeOlder: true})).length, 20);
  assert.deepEqual(display.report(initial, policy, today).counts, {visible: 17, old_unverified: 1, confirmed_ended: 2});
  assert.equal(JSON.stringify(initial), before, 'display decisions never edit saved dates or labels');
});

test('age limit includes its last JST calendar day, then hides at midnight', () => {
  const a = article({published_at: '2026-11-01T15:00:00Z'}); // Nov 2 in Japan.
  assert.equal(display.describe(a, policy, '2026-11-16').age_days, 14);
  assert.equal(display.describe(a, policy, '2026-11-16').hidden_reason, null);
  assert.equal(display.describe(a, policy, '2026-11-17').hidden_reason, 'old_unverified');
  assert.equal(display.day('2026-11-16T14:59:59Z'), '2026-11-16');
  assert.equal(display.day('2026-11-16T15:00:00Z'), '2026-11-17');
});

test('missing publication uses first collection, never last seen or today', () => {
  const a = article({published_at: null, collected_at: '2026-10-01T10:00:00+09:00', last_seen_at: '2026-11-03T12:00:00+09:00'});
  const state = display.describe(a, policy, today);
  assert.equal(state.reference_kind, 'collected');
  assert.equal(state.reference_date, '2026-10-01');
  assert.equal(state.hidden_reason, 'old_unverified');
  const missing = display.describe(article({published_at: null, collected_at: null}), policy, today);
  assert.equal(missing.hidden_reason, 'freshness_unknown');
  assert.equal(missing.age_days, null);
});

test('configured age limit applies without inventing event dates', () => {
  const a = article({published_at: '2026-11-02'});
  assert.equal(display.describe(a, {...policy, unverified_max_age_days: 0}, today).hidden_reason, 'old_unverified');
  assert.equal(display.describe(a, {...policy, unverified_max_age_days: 1}, today).hidden_reason, null);
  const state = display.describe(article({title: '11/8に開催', published_at: '2026-11-08'}), policy, today);
  assert.equal(state.status, 'unverified_event');
  assert.equal(state.unverified, true);
});

test('confirmed future dates remain available even with old publication dates', () => {
  const a = article({published_at: '2026-01-01', labels: ['今だけ'], timing: {start: '2026-11-08', end: '2026-11-08'}});
  assert.equal(display.describe(a, policy, today).status, 'upcoming');
  assert.equal(display.describe(a, policy, '2026-11-08').status, 'confirmed');
  assert.equal(display.describe(a, policy, '2026-11-09').status, 'ended');
  assert.equal(display.describe(a, policy, today).hidden_reason, null);
  const [entry] = display.entries([a], policy, today);
  assert.ok(display.visible(entry, {filter: '今だけ'}));
  assert.ok(!display.visible(entry, {filter: '催し（日付未確認）'}));
});

test('old unverified and ended records stay behind ordinary records on restore', () => {
  const inputs = [
    article({id:'ended', published_at:today, labels:['今だけ'], timing:{start:'2026-11-02', end:'2026-11-02'}}),
    article({id:'old', published_at:'2026-10-10'}),
    article({id:'upcoming', published_at:'2026-01-01', labels:['今だけ'], timing:{start:'2026-11-08', end:'2026-11-08'}}),
    article({id:'fresh', published_at:'2026-11-02'})
  ];
  const entries = display.entries(inputs, policy, today);
  assert.deepEqual(entries.map(e => e.article.id), ['fresh','upcoming','old','ended']);
  assert.deepEqual(entries.filter(e => display.visible(e)).map(e => e.article.id), ['fresh','upcoming']);
  assert.deepEqual(entries.filter(e => display.visible(e, {includeOlder:true})).map(e => e.article.id), ['fresh','upcoming','old']);
  assert.deepEqual(entries.filter(e => display.visible(e, {includeEnded:true})).map(e => e.article.id), ['fresh','upcoming','ended']);
});

test('event and deadline cues are configurable and independent of the topic filter', () => {
  const event = article({topic:'文化・学び', title:'図書館で11/8に開催'});
  assert.equal(display.describe(event, policy, today).status, 'unverified_event');
  const deadline = article({topic:'買い物', title:'本日限定クーポン'});
  assert.equal(display.describe(deadline, policy, today).status, 'unverified_deadline');
  assert.equal(display.describe(deadline, {...policy, deadline_keywords:[]}, today).status, 'discovery');
  const entry = display.entries([event], policy, today)[0];
  assert.ok(display.visible(entry, {filter:'催し（日付未確認）', topic:'文化・学び'}));
  assert.ok(!display.visible(entry, {filter:'催し（日付未確認）', topic:'買い物'}));
});

test('unknown dates and invalid dates stay unverified with an auditable reason', () => {
  assert.equal(display.day('2026-02-30'), null);
  const a = article({published_at:null, collected_at:null, timing:{end:'2026-02-30'}});
  const result = display.report([a], policy, today);
  assert.equal(result.articles[0].status, 'unverified_event');
  assert.equal(result.articles[0].hidden_reason, 'freshness_unknown');
  assert.equal(result.articles[0].url, a.url);
  assert.equal(result.articles[0].title, a.title);
  assert.ok(display.visible(display.entries([a], policy, today)[0], {includeOlder:true}));
});
