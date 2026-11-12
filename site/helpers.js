const normalize = value => String(value || '').normalize('NFD').replace(/\p{Diacritic}/gu, '').toLocaleLowerCase('cs');

export function pragueDate(now = new Date()) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Prague', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now);
}

function addDays(date, count) {
  const value = new Date(`${date}T12:00:00Z`);
  value.setUTCDate(value.getUTCDate() + count);
  return value.toISOString().slice(0, 10);
}

export function periodBounds(period, now = new Date()) {
  const today = pragueDate(now);
  if (period === 'today') return [today, today];
  if (period === 'weekend') {
    const weekday = new Date(`${today}T12:00:00Z`).getUTCDay();
    const saturday = addDays(today, weekday === 0 ? -1 : 6 - weekday);
    return [saturday, addDays(saturday, 1)];
  }
  return null;
}

export const SEASON_START = '2026-11-20';
export const SEASON_END = '2026-12-24';

export function filterBounds(filters = {}, now = new Date()) {
  if (filters.period !== 'custom') return periodBounds(filters.period, now);
  const from = filters.dateFrom || SEASON_START, through = filters.dateTo || SEASON_END;
  const valid = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(`${value}T12:00:00Z`)) && new Date(`${value}T12:00:00Z`).toISOString().slice(0, 10) === value;
  if (!valid(from) || !valid(through)) throw new RangeError('Zadejte platné datum.');
  if (from < SEASON_START || from > SEASON_END || through < SEASON_START || through > SEASON_END) throw new RangeError('Vyberte datum mezi 20. 11. a 24. 12. 2026.');
  if (from > through) throw new RangeError('Datum Od nesmí být později než datum Do.');
  return [from, through];
}

export function safeHttps(value) {
  if (typeof value !== 'string') return null;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

export function distanceKm(from, to) {
  const valid = point => point && Number.isFinite(point.lat) && Number.isFinite(point.lon) && Math.abs(point.lat) <= 90 && Math.abs(point.lon) <= 180;
  if (!valid(from) || !valid(to)) return Infinity;
  const rad = value => value * Math.PI / 180;
  const a = Math.sin(rad(to.lat - from.lat) / 2) ** 2 + Math.cos(rad(from.lat)) * Math.cos(rad(to.lat)) * Math.sin(rad(to.lon - from.lon) / 2) ** 2;
  return 6371.0088 * 2 * Math.asin(Math.sqrt(Math.min(1, a)));
}
export function nearbyEvents(events, position, radiusKm) {
  if (!Number.isFinite(radiusKm) || radiusKm < 0) return [];
  return events.filter(event => distanceKm(position, event.location) <= radiusKm + 1e-9);
}

// In the published 20 Nov–24 Dec 2026 window, Christmas Eve is the only Czech public holiday.
// Source: https://ppropo.mpsv.cz/pdf/zakon_245_2000.pdf (§ 2).
export function dayHighlight(value) {
  const date = new Date(`${value}T12:00:00Z`);
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) return { weekend:false, holiday:null };
  return { weekend:[0,6].includes(date.getUTCDay()), holiday:value === '2026-12-24' ? 'Štědrý den' : null };
}

export const MAP_COLORS = Object.freeze({ strom:'#2f6b45', mikulas:'#b33d42', trhy:'#a36b17', tvoreni:'#8054a3', setkani:'#257b87', betlem:'#79513c', mixed:'#657168' });
export function markerCategory(events) {
  const kinds = [...new Set(events.map(event => event.category))];
  return kinds.length === 1 && Object.hasOwn(MAP_COLORS, kinds[0]) ? kinds[0] : 'mixed';
}

export function groupLocations(events) {
  const groups = new Map();
  for (const event of events) {
    const location = event.location;
    if (!location || !Number.isFinite(location.lat) || !Number.isFinite(location.lon) || Math.abs(location.lat) > 90 || Math.abs(location.lon) > 180) continue;
    const key = `${location.lat.toFixed(5)},${location.lon.toFixed(5)}`;
    if (!groups.has(key)) groups.set(key, { ...location, events: [] });
    groups.get(key).events.push(event);
  }
  return [...groups.values()];
}

export function timeLabel(event) {
  if (!event.startTime) return 'Čas bude upřesněn';
  return event.endTime ? `${event.startTime}–${event.endTime}` : `od ${event.startTime}`;
}

const icsEscape = value => String(value || '').replace(/\\/g, '\\\\').replace(/\r\n|\r|\n/g, '\\n').replace(/;/g, '\\;').replace(/,/g, '\\,');
const compact = value => value.replace(/[-:]/g, '');
function foldLine(line) {
  const parts = [];
  let current = '';
  for (const char of line) {
    if (new TextEncoder().encode(current + char).length > 75) { parts.push(current); current = ' '; }
    current += char;
  }
  parts.push(current);
  return parts.join('\r\n');
}

export function eventIcs(event, now = new Date()) {
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Advent v Cesku//CZ', 'CALSCALE:GREGORIAN',
    'BEGIN:VTIMEZONE', 'TZID:Europe/Prague', 'BEGIN:STANDARD', 'DTSTART:19701025T030000', 'TZOFFSETFROM:+0200', 'TZOFFSETTO:+0100', 'RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU', 'END:STANDARD',
    'BEGIN:DAYLIGHT', 'DTSTART:19700329T020000', 'TZOFFSETFROM:+0100', 'TZOFFSETTO:+0200', 'RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU', 'END:DAYLIGHT', 'END:VTIMEZONE',
    'BEGIN:VEVENT', `UID:${String(event.id).replace(/[^a-zA-Z0-9_-]/g, '')}@advent-cesko-2026`, `DTSTAMP:${now.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z')}`];
  const description = [event.description, ...(event.notes || []), event.price && `Vstupné: ${event.price}`, event.registration && `Rezervace: ${event.registration}`].filter(Boolean);
  if (event.startTime) {
    lines.push(`DTSTART;TZID=Europe/Prague:${compact(event.date)}T${compact(event.startTime)}00`);
    if (event.endTime) {
      const endDate = event.endDate || (event.endTime < event.startTime ? addDays(event.date, 1) : event.date);
      lines.push(`DTEND;TZID=Europe/Prague:${compact(endDate)}T${compact(event.endTime)}00`);
    }
    else { lines.push('DURATION:PT1H'); description.push('Kalendářní délka 1 hodina; konec orientační, pořadatel jej nezveřejnil.'); }
  } else {
    lines.push(`DTSTART;VALUE=DATE:${compact(event.date)}`, `DTEND;VALUE=DATE:${compact(addDays(event.endDate || event.date, 1))}`);
    description.push('Čas programu není zveřejněn. Zápis dne v kalendáři neznamená celodenní program.');
  }
  const source = safeHttps(event.sourceUrl);
  if (source) { lines.push(`URL:${source}`); description.push(`Zdroj: ${source}`); }
  lines.push(`SUMMARY:${icsEscape(event.title)}`, `LOCATION:${icsEscape([event.venue, event.town].filter(Boolean).join(', '))}`, `DESCRIPTION:${icsEscape(description.join('\n'))}`);
  if (event.status === 'cancelled') lines.push('STATUS:CANCELLED');
  lines.push('END:VEVENT', 'END:VCALENDAR');
  return lines.map(foldLine).join('\r\n') + '\r\n';
}

export function filterEvents(events, filters = {}, now = new Date()) {
  const bounds = filterBounds(filters, now);
  const query = normalize(filters.query).trim();
  return events.filter(event =>
    (!filters.region || event.region === filters.region) &&
    (!filters.town || event.town === filters.town) &&
    (!filters.category || event.category === filters.category) &&
    (!query || normalize([event.title, event.town, event.venue, event.description].join(' ')).includes(query)) &&
    (!bounds || (event.date <= bounds[1] && (event.endDate || event.date) >= bounds[0]))
  ).sort((a, b) => `${a.date} ${a.startTime || '99:99'}`.localeCompare(`${b.date} ${b.startTime || '99:99'}`) || a.title.localeCompare(b.title, 'cs'));
}
