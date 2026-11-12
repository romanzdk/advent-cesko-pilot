import test from 'node:test';
import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
test('Czech public tip template owns optional maintainer metadata, not URL parameters', async () => {
  const template = await readFile(new URL('../.github/ISSUE_TEMPLATE/tip.md', import.meta.url), 'utf8').catch(() => '');
  assert.match(template, /labels:.*enhancement/);
  assert.match(template, /assignees:.*romanzdk/);
  for (const text of ['name:', 'about:', "title: '[Tip] '", 'Obec', 'zdroj', 'Podrobnosti', '20. 11.', '24. 12. 2026', 'osobní údaje', 'existující']) assert(template.includes(text), text);
});
let feedback = {};
try { feedback = await import('../site/feedback-helpers.js'); } catch (error) { if (error.code !== 'ERR_MODULE_NOT_FOUND') throw error; }
test('empty payload and missing public consent are rejected', () => {
  assert.throws(() => feedback.draftURL({ consent: true }), /obec|odkaz|popis/);
  assert.throws(() => feedback.draftURL({ town: 'Brno', consent: false }), /veřejný/);
});
test('field, title and final encoded URL limits reject instead of truncating', () => {
  for (const [key, length] of [['town', 101], ['sourceURL', 801], ['description', 1001]]) {
    assert.throws(() => feedback.draftURL({ ...valid, [key]: 'a'.repeat(length) }), /dlouh/);
  }
  assert.throws(() => feedback.draftURL({ description: 'a'.repeat(120), consent: true }), /dlouh/);
  assert.throws(() => feedback.draftURL({ town: 'Brno', description: '漢'.repeat(1000), consent: true }), /dlouh/);
});
test('source accepts public http/https only and never silently normalizes payload', () => {
  for (const sourceURL of ['javascript:alert(1)', 'data:text/plain,no', 'https://user:pass@example.cz', 'http://localhost/x', 'http://127.1', 'http://10.0.0.1', 'http://172.16.1.1', 'http://192.168.1.1', 'http://169.254.1.1', 'http://[::1]', 'http://[::ffff:127.0.0.1]', 'https://printer.local', 'not a url']) {
    assert.throws(() => feedback.draftURL({ ...valid, sourceURL }), /veřejný.*HTTP/);
  }
  const draft = new URL(feedback.draftURL({ sourceURL: 'http://example.cz/A?x=1&b=2#C', consent: true }));
  assert.equal(draft.searchParams.get('title'), '[Tip] example.cz');
  assert(draft.searchParams.get('body').includes('http://example.cz/A?x=1&b=2#C'));
});
test('issue views ignore PRs, wrong repositories and malformed links and cap at ten', () => {
  assert.equal(typeof feedback.issueViews, 'function');
  const issue = { number: 1, title: '<img src=x onerror=alert(1)>', state: 'open', html_url: 'https://github.com/romanzdk/advent-cesko-pilot/issues/1' };
  const invalid = [{ ...issue, pull_request: {} }, ...['javascript:alert(1)', 'https://github.com/other/repo/issues/1', 'https://github.com/romanzdk/advent-cesko-pilot/issues/1?x=1', 'https://user@github.com/romanzdk/advent-cesko-pilot/issues/1'].map(html_url => ({ ...issue, html_url })), { ...issue, state: 'bogus' }];
  assert.deepEqual(feedback.issueViews([...invalid, issue, { ...issue, state: 'closed' }]).map(i => i.state), ['open', 'closed']);
  assert.equal(feedback.issueViews([issue])[0].title, issue.title);
  assert.equal(feedback.issueViews(Array(15).fill(issue)).length, 10);
  assert.throws(() => feedback.issueViews({ message: 'API failure' }));
});
test('description-only draft uses the first nonempty trimmed line as its title', () => {
  const draft = new URL(feedback.draftURL({ description: '\n  Vánoční dílna & trhy\nDalší podrobnosti', consent: true }));
  assert.equal(draft.searchParams.get('title'), '[Tip] Vánoční dílna & trhy');
});
const valid = { town: ' Říčany & okolí? #1 ', sourceURL: ' https://example.cz/žluťoučký?a=1&b=2#část ', description: ' Tip & dotaz? #ano\nDruhý řádek ', consent: true };
test('draft preserves trimmed Unicode and special characters with only official draft parameters', () => {
  assert.equal(typeof feedback.draftURL, 'function');
  const draft = new URL(feedback.draftURL(valid));
  assert.equal(draft.origin, 'https://github.com');
  assert.equal(draft.pathname, '/romanzdk/advent-cesko-pilot/issues/new');
  assert.deepEqual([...draft.searchParams.keys()].sort(), ['body', 'template', 'title']);
  assert.equal(draft.searchParams.get('template'), 'tip.md');
  assert.equal(draft.searchParams.get('title'), '[Tip] Říčany & okolí? #1');
  const body = draft.searchParams.get('body');
  for (const text of [valid.town.trim(), valid.sourceURL.trim(), valid.description.trim()]) assert(body.includes(text));
  assert(draft.href.length <= 7000);
});
