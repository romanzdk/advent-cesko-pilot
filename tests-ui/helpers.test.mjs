import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
let helpers = {};
try { helpers = await import('../site/helpers.js'); } catch (error) { if (error.code !== 'ERR_MODULE_NOT_FOUND') throw error; }
const event = (id, date, startTime = null, extra = {}) => ({ id, title: id, date, startTime, town: 'Beroun', category: 'strom', status: 'confirmed', ...extra });
test('event permalinks preserve literal IDs and only share the current origin and base path', () => {
  assert.equal(typeof helpers.eventPermalink, 'function');
  for (const path of ['/', '/advent-cesko-pilot/', '/advent-cesko-pilot/index.html']) {
    assert.equal(helpers.eventPermalink('e-Ab_19-0', `https://example.cz${path}?query=secret&lat=49.123#other`), `https://example.cz${path}#akce=e-Ab_19-0`);
  }
  for (const id of ['', 'e-evil<script>', ' e-123', 'e-123 ', 'e-a/b', 'e-%61', null]) assert.equal(helpers.eventPermalink(id, 'https://example.cz/'), null);
  assert.equal(helpers.eventPermalink('e-test', 'javascript:alert(1)'), null);
});
test('event fragments accept exact IDs without decoding, normalizing or interpreting extra parameters', () => {
  assert.equal(typeof helpers.eventIdFromHash, 'function');
  assert.equal(helpers.eventIdFromHash('#akce=e-Ab_19-0'), 'e-Ab_19-0');
  for (const hash of ['', '#results', '#akce=', '#akce=%65-test', '#akce=e-test&lat=49', '#akce=e-test?query=x', '#akce=e-test%0A', '#akce=<img src=x>', '#akce=e-test/../../', '#akce=e-test#x', '#akce=e-test\n']) assert.equal(helpers.eventIdFromHash(hash), null, hash);
});
test('crow-flies distance validates coordinates and nearby filtering is inclusive without reordering', () => {
  assert.equal(typeof helpers.distanceKm, 'function');
  const zero = { lat: 0, lon: 0 }, east = { lat: 0, lon: 1 };
  assert(Math.abs(helpers.distanceKm(zero, east) - 111.1950802335329) < 0.000001);
  assert.equal(helpers.distanceKm(zero, zero), 0);
  for (const invalid of [null, {}, { lat: null, lon: 0 }, { lat: NaN, lon: 0 }, { lat: 91, lon: 0 }, { lat: 0, lon: 181 }]) assert.equal(helpers.distanceKm(zero, invalid), Infinity);
  const events = [{ id: 'east', location: east }, { id: 'zero', location: zero }, { id: 'unmapped' }, { id: 'invalid', location: { lat: null, lon: 0 } }];
  assert.deepEqual(helpers.nearbyEvents(events, zero, helpers.distanceKm(zero, east)).map(e => e.id), ['east', 'zero']);
  assert.deepEqual(helpers.nearbyEvents(events, zero, 25).map(e => e.id), ['zero']);
  assert.deepEqual(helpers.nearbyEvents(events, null, 50), []);
  assert.deepEqual(helpers.nearbyEvents(events, zero, -1), []);
  assert.equal(events.length, 4);
});
test('season date highlights recognize weekends and Christmas Eve without timezone shifts', () => {
  assert.deepEqual(helpers.dayHighlight('2026-11-27'), {weekend:false, holiday:null});
  assert.deepEqual(helpers.dayHighlight('2026-11-28'), {weekend:true, holiday:null});
  assert.deepEqual(helpers.dayHighlight('2026-11-29'), {weekend:true, holiday:null});
  assert.deepEqual(helpers.dayHighlight('2026-12-24'), {weekend:false, holiday:'Štědrý den'});
  assert.deepEqual(helpers.dayHighlight('2026-11-31'), {weekend:false, holiday:null});
});

test('map categories have distinct colors and shared mixed places stay neutral', () => {
  assert.equal(typeof helpers.markerCategory, 'function');
  assert.equal(helpers.markerCategory([{ category:'strom' }, { category:'strom' }]), 'strom');
  assert.equal(helpers.markerCategory([{ category:'strom' }, { category:'trhy' }]), 'mixed');
  assert.equal(helpers.markerCategory([{ category:'__proto__' }]), 'mixed');
  assert.equal(helpers.markerCategory([]), 'mixed');
  assert.equal(new Set(Object.values(helpers.MAP_COLORS)).size, 7);
  for (const color of Object.values(helpers.MAP_COLORS)) assert.match(color, /^#[0-9a-f]{6}$/i);
});


test('social metadata describes the current project with a full-size local PNG preview', async () => {
  const html = await readFile(new URL('../site/index.html', import.meta.url), 'utf8');
  const metadata = new Map([...html.matchAll(/<meta\b[^>]*>/gi)].map(([tag]) => {
    const attributes = Object.fromEntries([...tag.matchAll(/([\w:-]+)\s*=\s*["']([^"']*)["']/g)].map(([, key, value]) => [key, value]));
    return [attributes.property || attributes.name, attributes.content];
  }));
  for (const [key, value] of Object.entries({
    'og:title': 'Advent v Česku 2026',
    'og:site_name': 'Advent v Česku',
    'og:locale': 'cs_CZ',
    'og:type': 'website',
    'og:image': 'https://raw.githubusercontent.com/romanzdk/advent-cesko-pilot/main/site/social-preview.png',
    'og:image:width': '1280',
    'og:image:height': '640',
    'twitter:card': 'summary_large_image'
  })) assert.equal(metadata.get(key), value, key);
  const png = await readFile(new URL('../site/social-preview.png', import.meta.url));
  assert.deepEqual(png.subarray(0, 8), Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
  assert.equal(png.toString('ascii', 12, 16), 'IHDR');
  assert.equal(png.readUInt32BE(16), 1280);
  assert.equal(png.readUInt32BE(20), 640);
});

test('default season list is chronological, including dates before today and unknown times last', () => {
  assert.equal(typeof helpers.filterEvents, 'function');
  const events = [event('later', '2026-12-20'), event('unknown', '2026-11-20'), event('early', '2026-11-20', '16:00')];
  assert.deepEqual(helpers.filterEvents(events, {}, new Date('2026-12-01T10:00:00Z')).map(e => e.id), ['early', 'unknown', 'later']);
  assert.equal(events[0].id, 'later');
});
test('combined filters use accent-insensitive search and overlap multiday events', () => {
  const events = [event('Vánoční dílna', '2026-11-27', '15:00', { category: 'tvoreni', endDate: '2026-11-30' }), event('other', '2026-11-28')];
  assert.deepEqual(helpers.filterEvents(events, { query: 'vanocni', town: 'Beroun', category: 'tvoreni', period: 'weekend' }, new Date('2026-11-25T12:00:00Z')).map(e => e.id), ['Vánoční dílna']);
  assert.equal(helpers.filterEvents(events, { town: 'Říčany' }).length, 0);
  assert.equal(helpers.filterEvents(events, { category: 'betlem' }).length, 0);
  assert.equal(helpers.filterEvents(events, { query: 'nonsense' }).length, 0);
});
test('town suggestions are local, scoped, sorted, deduplicated, normalized and bounded to eight', () => {
  assert.equal(typeof helpers.townSuggestions, 'function');
  const events = ['Říčany','Beroun','Říčany','Český Brod', ...Array.from({length:10}, (_, i) => `Obec ${i}`)].map(town => ({town,region:'A'}));
  events.push({town:'Říčany u Brna',region:'B'}, {town:null,region:'A'});
  assert.deepEqual(helpers.townSuggestions(events, 'A', '  ICAN '), ['Říčany']);
  assert.deepEqual(helpers.townSuggestions(events, '', 'ric'), ['Říčany','Říčany u Brna']);
  assert.deepEqual(helpers.townSuggestions(events, 'A', 'CES'), ['Český Brod']);
  assert.deepEqual(helpers.townSuggestions(events, 'empty', ''), []);
  const all = helpers.townSuggestions(events, 'A', '');
  assert.equal(all.length, 8);
  assert.deepEqual(all, [...new Set(events.filter(e => e.region === 'A' && e.town).map(e => e.town))].sort((a,b) => a.localeCompare(b,'cs')).slice(0,8));
});

test('town text matches accent-insensitive partial names only and composes with other filters', () => {
  const events = [event('match', '2026-11-28', null, {town:'Říčany',region:'A'}), event('wrong-region', '2026-11-28', null, {town:'Říčany',region:'B'}), event('name-only', '2026-11-28', null, {title:'Říčany',region:'A'})];
  assert.deepEqual(helpers.filterEvents(events, {town:'  ICAN ',region:'A',category:'strom',period:'custom',dateFrom:'2026-11-28',dateTo:'2026-11-28'}).map(e => e.id), ['match']);
  assert.equal(helpers.filterEvents(events, {town:'nic'}).length, 0);
  assert.equal(helpers.filterEvents(events, {town:'   '}).length, 3);
});

test('custom dates include both endpoints and overlapping multiday events without mutating input', () => {
  const events = [event('before', '2026-11-27'), event('first', '2026-11-28'), event('last', '2026-11-30'), event('after', '2026-12-01'), event('overlap', '2026-11-25', null, { endDate: '2026-11-28' })];
  assert.deepEqual(helpers.filterEvents(events, { period: 'custom', dateFrom: '2026-11-28', dateTo: '2026-11-30' }).map(e => e.id), ['overlap', 'first', 'last']);
  assert.equal(events[0].id, 'before');
});

test('custom bounds reject impossible, reversed and out-of-season dates instead of showing an unfiltered list', () => {
  for (const [dateFrom, dateTo] of [['2026-12-10', '2026-12-01'], ['2026-11-31', '2026-12-01'], ['2026-11-01', '2026-12-01'], ['2026-12-01', '2026-12-25'], ['2026-99-01', '2026-12-24'], ['not-a-date', '2026-12-24']]) {
    assert.throws(() => helpers.filterEvents([event('one', '2026-12-01')], { period: 'custom', dateFrom, dateTo }), RangeError);
  }
});

test('custom bounds support open ends, one day and ignore inactive custom dates for presets', () => {
  assert.deepEqual(helpers.filterBounds({ period: 'custom', dateFrom: '2026-12-01' }), ['2026-12-01', '2026-12-24']);
  assert.deepEqual(helpers.filterBounds({ period: 'custom', dateTo: '2026-11-28' }), ['2026-11-20', '2026-11-28']);
  assert.deepEqual(helpers.filterBounds({ period: 'custom' }), ['2026-11-20', '2026-12-24']);
  assert.deepEqual(helpers.filterBounds({ period: 'custom', dateFrom: '2026-12-05', dateTo: '2026-12-05' }), ['2026-12-05', '2026-12-05']);
  for (const period of ['all', 'today', 'weekend']) assert.deepEqual(helpers.filterBounds({ period, dateFrom: 'invalid', dateTo: 'reversed' }, new Date('2026-11-27T23:30:00Z')), helpers.periodBounds(period, new Date('2026-11-27T23:30:00Z')));
});

test('date labels never describe an unknown programme time as all-day', () => {
  assert.equal(typeof helpers.timeLabel, 'function');
  assert.equal(helpers.timeLabel(event('unknown', '2026-11-28')), 'Čas bude upřesněn');
  assert.equal(helpers.timeLabel(event('start', '2026-11-28', '16:00')), 'od 16:00');
  assert.equal(helpers.timeLabel(event('range', '2026-11-28', '16:00', { endTime: '18:00' })), '16:00–18:00');
});
test('public links only allow https and co-located events share one marker', () => {
  assert.equal(typeof helpers.safeHttps, 'function');
  assert.equal(helpers.safeHttps('javascript:alert(1)'), null);
  assert.equal(helpers.safeHttps('http://example.cz'), null);
  assert.equal(helpers.safeHttps('https://user:secret@example.cz'), null);
  assert.equal(helpers.safeHttps('https://example.cz/program'), 'https://example.cz/program');
  const location = { lat: 49.964, lon: 14.073, precision: 'town', label: 'Beroun' };
  const groups = helpers.groupLocations([event('a', '2026-11-28', null, { location }), event('b', '2026-12-05', null, { location }), event('unmapped', '2026-12-06'), event('bad', '2026-12-07', null, { location: { lat: 100, lon: 14 } })]);
  assert.equal(groups.length, 1);
  assert.deepEqual(groups[0].events.map(e => e.id), ['a', 'b']);
});
test('individual calendar export distinguishes published time from an estimated end', () => {
  assert.equal(typeof helpers.eventIcs, 'function');
  const base = event('public-123', '2026-11-28', '16:00', { title: 'Dílna, věnce; advent\\\nDalší řádek', description: 'Popis', notes: ['Rezervace nutná'], sourceUrl: 'https://example.cz/program', venue: 'Klub', verifiedAt: '2026-11-12T10:00:00Z' });
  const rawIcs = helpers.eventIcs(base, new Date('2026-11-12T10:00:00Z'));
  const ics = rawIcs.replace(/\r\n /g, '');
  assert.match(ics, /DTSTART;TZID=Europe\/Prague:20261128T160000/);
  assert.match(ics, /DURATION:PT1H/);
  assert.match(ics, /konec orientační/);
  assert.match(ics, /BEGIN:VTIMEZONE/);
  assert.match(ics, /SUMMARY:Dílna\\, věnce\\; advent/);
  assert.match(ics, /DTSTAMP:20261112T100000Z/);
  const known = helpers.eventIcs({ ...base, endTime: '19:00' });
  assert.match(known, /DTEND;TZID=Europe\/Prague:20261128T190000/);
  assert.doesNotMatch(known, /konec orientační/);
  const unknown = helpers.eventIcs({ ...base, startTime: null, endTime: null });
  assert.match(unknown, /DTSTART;VALUE=DATE:20261128/);
  assert.match(unknown, /DTEND;VALUE=DATE:20261129/);
  assert.match(unknown, /Čas programu není zveřejněn/);
  assert.doesNotMatch(unknown, /DURATION:PT1H/);
  assert(rawIcs.split('\r\n').every(line => Buffer.byteLength(line) <= 75));
});

test('calendar export identifies the current nationwide project', () => {
  const ics = helpers.eventIcs(event('brand-check', '2026-11-28'));
  assert(ics.split('\r\n').includes('PRODID:-//Advent v Cesku//CZ'));
});

test('calendar UID is stable across edits and export times in the current season namespace', () => {
  const base = event('public-123', '2026-11-28', '16:00');
  const first = helpers.eventIcs(base, new Date('2026-11-12T10:00:00Z'));
  const edited = helpers.eventIcs({ ...base, title: 'Nový název', date: '2026-12-05', town: 'Praha' }, new Date('2026-11-13T12:00:00Z'));
  const uid = ics => ics.replace(/\r\n /g, '').split('\r\n').find(line => line.startsWith('UID:'));
  assert.equal(uid(first), 'UID:public-123@advent-cesko-2026');
  assert.equal(uid(edited), uid(first));
  assert.notEqual(uid(helpers.eventIcs({ ...base, id: 'public-456' })), uid(first));
});

test('calendar handles overnight published ends without exporting an end before the start', () => {
  const ics = helpers.eventIcs(event('night', '2026-11-28', '23:00', { endTime: '01:00' }));
  assert.match(ics, /DTEND;TZID=Europe\/Prague:20261129T010000/);
});

test('Prague calendar and weekend boundaries survive UTC midnight and DST', () => {
  assert.equal(helpers.pragueDate(new Date('2026-11-27T23:30:00Z')), '2026-11-28');
  assert.deepEqual(helpers.periodBounds('weekend', new Date('2026-11-29T15:00:00Z')), ['2026-11-28', '2026-11-29']);
  assert.deepEqual(helpers.periodBounds('weekend', new Date('2026-10-24T22:30:00Z')), ['2026-10-24', '2026-10-25']);
});
