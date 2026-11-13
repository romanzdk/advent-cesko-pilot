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
const full = { mode: 'full', title: 'Vánoční dílna', town: 'Beroun', date: '2026-11-28', sourceURL: 'https://example.cz/program', consent: true };
test('full event requires essentials and serializes every visitor field without invented metadata', () => {
  for (const field of ['title', 'town', 'date', 'sourceURL']) assert.throws(() => feedback.draftURL({ ...full, [field]: '' }), /Vyplňte/);
  const fields = { ...full, region: 'Středočeský kraj', venue: 'Klub, Hlavní 1', endDate: '2026-11-29', startTime: '16:00', endTime: '18:00', category: 'tvoreni', price: '150 Kč', registration: 'Rezervace nutná', registrationURL: 'https://example.cz/rezervace', audience: 'Dospělí', description: 'Věnce & dekorace', notes: 'Vlastní nůžky' };
  const draft = new URL(feedback.draftURL(fields)), body = draft.searchParams.get('body');
  assert.equal(draft.searchParams.get('title'), '[Akce] Vánoční dílna');
  for (const [key, value] of Object.entries(fields)) if (!['mode', 'consent'].includes(key)) assert(body.includes(value), key);
  for (const label of ['Název', 'Kraj', 'Obec', 'Místo / adresa', 'Datum', 'Konec', 'Začátek', 'Cena', 'Registrace', 'Vhodnost', 'Popis', 'Poznámky', 'Veřejný zdroj']) assert(body.includes(label), label);
  assert.doesNotMatch(body, /verifiedAt|latitude|longitude|confirmed/);
});
test('full dates and clocks are real, ordered and seasonal; unknown dates strip inactive values', () => {
  for (const date of ['2026-11-31', '2026-02-30', '2026-11-19', '2026-12-25', '2025-11-28', '2026-1-28', '2026-11-28\n']) assert.throws(() => feedback.draftURL({ ...full, date }), /datum|Datum/);
  for (const endDate of ['2026-11-27', '2026-12-32', '2027-01-01']) assert.throws(() => feedback.draftURL({ ...full, endDate }), /datum|Datum|Konec/);
  assert.doesNotThrow(() => feedback.draftURL({ ...full, endDate: '2026-12-31' }));
  for (const startTime of ['24:00', '12:60', '9:00', '10:00\n']) assert.throws(() => feedback.draftURL({ ...full, startTime }), /čas|HH:MM/);
  assert.throws(() => feedback.draftURL({ ...full, startTime: '16:00', endTime: '15:59' }), /čas|Konec/);
  assert.doesNotThrow(() => feedback.draftURL({ ...full, startTime: '16:00', endTime: '16:00' }));
  assert.doesNotThrow(() => feedback.draftURL({ ...full, endDate: '2026-11-29', startTime: '16:00', endTime: '10:00' }));
  const body = new URL(feedback.draftURL({ ...full, dateUnknown: true, date: 'bad', endDate: 'bad', startTime: '24:99', endTime: 'bad' })).searchParams.get('body');
  assert.match(body, /Datum\nNeznámé/); assert.doesNotMatch(body, /bad|24:99|Konec –|Začátek –/);
  const noStart = new URL(feedback.draftURL({ ...full, endTime: '18:00' })).searchParams.get('body');
  assert.match(noStart, /Začátek – čas\nNeuvedeno/); assert.doesNotMatch(noStart, /celodenní|00:00/);
});
test('full validates closed choices, public URLs, consent and explicit lengths including encoded cap', () => {
  for (const fields of [{ region: 'Atlantida' }, { category: 'concert' }, { mode: 'other' }]) assert.throws(() => feedback.draftURL({ ...full, ...fields }), /výběr|režim/);
  for (const consent of [false, undefined, 'true']) assert.throws(() => feedback.draftURL({ ...full, consent }), /veřejný/);
  for (const key of ['sourceURL', 'registrationURL']) for (const url of ['https://user:pass@example.cz', 'http://8.8.8.8', 'http://127.1', 'https://example.test', 'https://printer.local', 'http://[2606:4700::1111]', 'ftp://example.cz', 'https://intranet', 'https://example.cz:443\n']) assert.throws(() => feedback.draftURL({ ...full, [key]: url }), /veřejný.*HTTP/);
  for (const [key, max] of Object.entries({ title: 100, town: 100, venue: 200, price: 200, registration: 500, registrationURL: 800, sourceURL: 800, audience: 200, description: 1000, notes: 1000 })) assert.throws(() => feedback.draftURL({ ...full, [key]: 'x'.repeat(max + 1) }), /dlouh/);
  assert.throws(() => feedback.draftURL({ ...full, description: '漢'.repeat(1000) }), /dlouh/);
  assert.doesNotThrow(() => feedback.draftURL({ ...full, region: '', category: '', registrationURL: 'http://example.cz/booking?x=1&y=2' }));
});
test('quick mode applies the same public-host boundary to IPs and local/test endpoints', () => {
  for (const sourceURL of ['https://8.8.8.8/path', 'https://printer.lan', 'https://router.home', 'https://example.test']) assert.throws(() => feedback.draftURL({ mode: 'quick', sourceURL, consent: true }), /veřejný.*HTTP/);
});
test('quick mode ignores all inactive full-only values while retaining original three-field behavior', () => {
  const draft = new URL(feedback.draftURL({ mode: 'quick', town: 'Brno', title: 'x'.repeat(999), date: 'bad', category: 'bad', registrationURL: 'javascript:bad', consent: true }));
  assert.equal(draft.searchParams.get('title'), '[Tip] Brno');
  assert.doesNotMatch(draft.searchParams.get('body'), /javascript:bad|Kategorie|Název/);
});
test('anonymous payload retains all structured fields, omits unknown clocks and ignores quick inactive fields', () => {
  const fields = { ...full, region: 'Středočeský kraj', category: 'tvoreni', venue: 'Klub', price: '150 Kč', registration: 'Rezervace', registrationURL: 'https://example.cz/booking', audience: 'Dospělí', notes: 'Poznámka', description: '漢'.repeat(1000), endTime: '18:00' };
  const payload = feedback.proposalPayload(fields);
  assert.equal(payload.mode, 'event');
  for (const [key, value] of Object.entries(fields)) if (key !== 'mode') assert.equal(payload[key], value, key);
  const unknown = feedback.proposalPayload({ ...fields, dateUnknown: true, startTime: 'bad', endTime: 'bad' });
  for (const key of ['date', 'endDate', 'startTime', 'endTime']) assert.equal(key in unknown, false, key);
  assert.equal(unknown.dateUnknown, true);
  assert.deepEqual(feedback.proposalPayload({ mode: 'quick', town: 'Brno', consent: true, registrationURL: 'bad' }), { mode: 'tip', town: 'Brno', sourceURL: '', description: '', consent: true, website: '' });
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
