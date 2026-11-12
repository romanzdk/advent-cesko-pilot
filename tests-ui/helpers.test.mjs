import test from 'node:test';
import assert from 'node:assert/strict';
let helpers = {};
try { helpers = await import('../site/helpers.js'); } catch (error) { if (error.code !== 'ERR_MODULE_NOT_FOUND') throw error; }
const event = (id, date, startTime = null, extra = {}) => ({ id, title: id, date, startTime, town: 'Mnichovice', category: 'strom', status: 'confirmed', ...extra });
test('default season list is chronological, including dates before today and unknown times last', () => {
  assert.equal(typeof helpers.filterEvents, 'function');
  const events = [event('later', '2026-12-20'), event('unknown', '2026-11-20'), event('early', '2026-11-20', '16:00')];
  assert.deepEqual(helpers.filterEvents(events, {}, new Date('2026-12-01T10:00:00Z')).map(e => e.id), ['early', 'unknown', 'later']);
  assert.equal(events[0].id, 'later');
});
test('combined filters use accent-insensitive search and overlap multiday events', () => {
  const events = [event('Vánoční dílna', '2026-11-27', '15:00', { category: 'tvoreni', endDate: '2026-11-30' }), event('other', '2026-11-28')];
  assert.deepEqual(helpers.filterEvents(events, { query: 'vanocni', town: 'Mnichovice', category: 'tvoreni', period: 'weekend' }, new Date('2026-11-25T12:00:00Z')).map(e => e.id), ['Vánoční dílna']);
  assert.equal(helpers.filterEvents(events, { town: 'Říčany' }).length, 0);
  assert.equal(helpers.filterEvents(events, { category: 'betlem' }).length, 0);
  assert.equal(helpers.filterEvents(events, { query: 'nonsense' }).length, 0);
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
  const location = { lat: 49.93, lon: 14.71, precision: 'town', label: 'Mnichovice' };
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

test('calendar handles overnight published ends without exporting an end before the start', () => {
  const ics = helpers.eventIcs(event('night', '2026-11-28', '23:00', { endTime: '01:00' }));
  assert.match(ics, /DTEND;TZID=Europe\/Prague:20261129T010000/);
});

test('Prague calendar and weekend boundaries survive UTC midnight and DST', () => {
  assert.equal(helpers.pragueDate(new Date('2026-11-27T23:30:00Z')), '2026-11-28');
  assert.deepEqual(helpers.periodBounds('weekend', new Date('2026-11-29T15:00:00Z')), ['2026-11-28', '2026-11-29']);
  assert.deepEqual(helpers.periodBounds('weekend', new Date('2026-10-24T22:30:00Z')), ['2026-10-24', '2026-10-25']);
});
