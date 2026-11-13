export const ISSUES = 'https://github.com/romanzdk/advent-cesko-pilot/issues';
export const ISSUES_API = 'https://api.github.com/repos/romanzdk/advent-cesko-pilot/issues?state=all&sort=updated&direction=desc&per_page=10';
export function issueViews(data) {
  if (!Array.isArray(data)) throw new Error('Invalid issue response');
  return data.filter(i => i && !i.pull_request && Number.isSafeInteger(i.number) && i.number > 0 && typeof i.title === 'string' && ['open', 'closed'].includes(i.state) && i.html_url === `${ISSUES}/${i.number}`).slice(0, 10).map(i => ({ title: i.title, state: i.state, url: i.html_url }));
}
const labels = { title: 'Název', region: 'Kraj', town: 'Obec', venue: 'Místo / adresa', date: 'Datum', endDate: 'Konec – datum', startTime: 'Začátek – čas', endTime: 'Konec – čas', category: 'Kategorie', price: 'Cena', registration: 'Registrace – podmínky', registrationURL: 'Registrace – veřejný odkaz', audience: 'Vhodnost / publikum', description: 'Popis', notes: 'Poznámky', sourceURL: 'Veřejný zdroj' };
export const REGIONS = ['Hlavní město Praha', 'Jihočeský kraj', 'Jihomoravský kraj', 'Karlovarský kraj', 'Kraj Vysočina', 'Královéhradecký kraj', 'Liberecký kraj', 'Moravskoslezský kraj', 'Olomoucký kraj', 'Pardubický kraj', 'Plzeňský kraj', 'Středočeský kraj', 'Ústecký kraj', 'Zlínský kraj'];
export const CATEGORIES = { strom: 'Rozsvícení stromu', mikulas: 'Mikuláš', trhy: 'Trhy a jarmarky', tvoreni: 'Tvoření', setkani: 'Setkání', betlem: 'Betlémy' };
function publicURL(value) {
  try {
    const u = new URL(value), h = u.hostname.toLowerCase().replace(/\.$/, '');
    if (!/^https?:$/.test(u.protocol) || u.username || u.password || /[\s\\]/u.test(value) || !h.includes('.') || h.includes(':') || /^\d+\.\d+\.\d+\.\d+$/.test(h) || /(?:^|\.)(localhost|local|internal|lan|home|test|invalid|example|onion)$/.test(h)) throw new Error();
  } catch { throw new Error('Použijte veřejný odkaz HTTP nebo HTTPS bez přihlašovacích údajů (ne IP ani místní adresu).'); }
}
function fullDraft(input, fieldsOnly = false) {
  const fields = Object.fromEntries(Object.keys(labels).map(key => [key, String(input[key] ?? '').trim()]));
  const dated = ['date', 'endDate', 'startTime', 'endTime'];
  if (input.dateUnknown === true) {
    for (const key of dated) delete fields[key];
    fields.date = 'Neznámé';
  } else {
    for (const key of ['date', 'endDate']) if (input[key]) {
      const value = input[key], parsed = new Date(`${value}T00:00:00Z`);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value || value < '2026-11-20' || value > (key === 'date' ? '2026-12-24' : '2026-12-31')) throw new Error('Datum musí být skutečné ISO datum v sezóně 20. 11. – 24. 12. 2026 (konec nejvýše 31. 12.).');
    }
    if (fields.endDate && fields.endDate < fields.date) throw new Error('Konec – datum nesmí předcházet začátku.');
    for (const key of ['startTime', 'endTime']) if (input[key] && !/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(input[key])) throw new Error('Použijte čas HH:MM (00:00–23:59).');
    if ((!fields.endDate || fields.endDate === fields.date) && fields.startTime && fields.endTime && fields.endTime < fields.startTime) throw new Error('Konec – čas nesmí předcházet začátku ve stejný den.');
  }
  const limits = { title: 100, town: 100, venue: 200, price: 200, registration: 500, registrationURL: 800, sourceURL: 800, audience: 200, description: 1000, notes: 1000 };
  for (const [key, max] of Object.entries(limits)) if (fields[key].length > max) throw new Error(`${labels[key]}: text je příliš dlouhý (max. ${max} znaků).`);
  if (fields.region && !REGIONS.includes(input.region) || fields.category && !Object.hasOwn(CATEGORIES, input.category)) throw new Error('Použijte hodnotu z výběru kraje / kategorie.');
  for (const key of ['sourceURL', 'registrationURL']) if (fields[key]) publicURL(input[key]);
  for (const key of ['title', 'town', 'date', 'sourceURL']) if (!fields[key]) throw new Error(`Vyplňte ${labels[key]}.`);
  if (input.consent !== true) throw new Error('Potvrďte, že návrh bude veřejný.');
  if (fieldsOnly) return fields;
  const body = Object.entries(fields).map(([key, value]) => `### ${labels[key]}\n${value || 'Neuvedeno'}`).join('\n\n') + '\n\nNávrh je veřejný, bez osobních údajů. Zařazení do mapy není automatické. Ověření a geodata doplní správce po kontrole. Před odesláním zkontrolujte existující tipy.';
  const url = `${ISSUES}/new?${new URLSearchParams({ template: 'tip.md', title: `[Akce] ${fields.title}`, body })}`;
  if (url.length > 7000) throw new Error('Odkaz je příliš dlouhý (max. 7000 znaků). Zkraťte návrh; žádná pole nebyla oříznuta.');
  return url;
}
export function draftURL(input) {
  if (input.mode !== undefined && !['full', 'quick'].includes(input.mode)) throw new Error('Neplatný režim formuláře.');
  if (input.mode === 'full') return fullDraft(input);
  return quickDraft(input);
}
function quickDraft({ town = '', sourceURL = '', description = '', consent }, fieldsOnly = false) {
  town = town.trim(); sourceURL = sourceURL.trim(); description = description.trim();
  if (town.length > 100 || sourceURL.length > 800 || description.length > 1000) throw new Error('Text je příliš dlouhý. Limity: obec 100, odkaz 800, popis 1000 znaků.');
  if (!town && !sourceURL && !description) throw new Error('Vyplňte obec, odkaz nebo popis.');
  if (consent !== true) throw new Error('Potvrďte, že návrh bude veřejný.');
  if (sourceURL) publicURL(sourceURL);
  if (fieldsOnly) return { town, sourceURL, description };
  const title = `[Tip] ${town || description.split('\n')[0] || new URL(sourceURL).hostname}`;
  if (title.length >= 120) throw new Error('Název je příliš dlouhý. Zkraťte první řádek popisu nebo doplňte obec.');
  const body = `### Obec\n${town}\n\n### Veřejný zdroj\n${sourceURL}\n\n### Podrobnosti\n${description}\n\nObdobí: 20. 11. – 24. 12. 2026. Návrh je veřejný, bez osobních údajů. Zařazení do mapy není automatické.\nPřed odesláním prosím zkontrolujte existující tipy.`;
  const url = `${ISSUES}/new?${new URLSearchParams({ template: 'tip.md', title, body })}`;
  if (url.length > 7000) throw new Error('Odkaz je příliš dlouhý. Zkraťte prosím návrh.');
  return url;
}
export const API_BASE = 'https://hermes.dory-geological.ts.net:10000';
export async function feedbackRequest(path, payload, timeout = 8000) {
  const response = await fetch(`${API_BASE}${path}`, { method: payload ? 'POST' : 'GET', credentials: 'omit', signal: AbortSignal.timeout(timeout), ...(payload ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) } : {}) });
  const data = await response.json();
  if (!response.ok) throw Object.assign(new Error(data.message || 'Služba nyní není dostupná.'), { code: data.error, http: response.status });
  return data;
}
export function proposalPayload(input) {
  const mode = input.mode === 'full' ? 'event' : input.mode === 'quick' ? 'tip' : input.mode;
  let fields;
  if (mode === 'event') {
    fields = fullDraft(input, true);
    if (input.dateUnknown === true) for (const key of ['date', 'endDate', 'startTime', 'endTime']) delete fields[key];
    fields.dateUnknown = input.dateUnknown === true;
  } else if (mode === 'tip') fields = quickDraft(input, true);
  else if (mode === 'error') {
    if (input.consent !== true) throw new Error('Potvrďte, že hlášení bude veřejné.');
    if (!['date', 'time', 'venue', 'cancelled', 'other'].includes(input.errorKind) || typeof input.eventId !== 'string' || !input.eventId) throw new Error('Neplatná akce nebo druh chyby.');
    fields = { eventId: input.eventId, errorKind: input.errorKind, description: String(input.description || '').trim(), sourceURL: String(input.sourceURL || '').trim() };
    if (!fields.description || fields.description.length > 1000 || fields.sourceURL.length > 800) throw new Error('Vyplňte popis do 1000 znaků a odkaz do 800 znaků.');
    if (fields.sourceURL) publicURL(fields.sourceURL);
  } else throw new Error('Neplatný režim formuláře.');
  return { mode, ...fields, consent: input.consent === true, website: String(input.website || '') };
}
