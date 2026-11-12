import { filterEvents, filterBounds, SEASON_START, SEASON_END, timeLabel, safeHttps, groupLocations, eventIcs, distanceKm, nearbyEvents, MAP_COLORS, markerCategory } from './helpers.js';
import { dayHighlight, townSuggestions } from './helpers.js';

const $ = id => document.getElementById(id);
const categories = { strom: 'Rozsvícení stromu', mikulas: 'Mikuláš', trhy: 'Trhy a jarmarky', tvoreni: 'Tvoření', setkani: 'Setkání', betlem: 'Betlémy' };
const dateFormat = new Intl.DateTimeFormat('cs-CZ', { day: 'numeric', month: 'numeric', year: 'numeric', timeZone: 'Europe/Prague' });
const dayFormat = new Intl.DateTimeFormat('cs-CZ', { weekday: 'short', timeZone: 'Europe/Prague' });
const monthFormat = new Intl.DateTimeFormat('cs-CZ', { month: 'long', year: 'numeric', timeZone: 'Europe/Prague' });
let events = [];
let coverageRegions = [];
let eventsLoaded = false;
let visibleEvents = [];
let map, markerLayer, mapPromise;
let tileFailed = false;
let userPosition = null, userMarker, locationTimer;
let locationGeneration = 0;
const desktop = matchMedia('(min-width: 821px)');

function selectEvent(id) {
  setView('list');
  for (const card of document.querySelectorAll('.event-card')) {
    const selected = card.dataset.id === id;
    card.classList.toggle('selected', selected);
    if (selected) {
      const top = window.scrollY + card.getBoundingClientRect().top - 24;
      window.scrollTo({ top, behavior: 'instant' });
      card.focus({ preventScroll: true });
    }
  }
}
function updateMap() {
  if (!$('map-legend').children.length) for (const [category, color] of Object.entries(MAP_COLORS)) {
    const item = el('li'), swatch = el('span', null, 'map-legend-swatch');
    swatch.style.backgroundColor = color;
    swatch.setAttribute('aria-hidden', 'true');
    item.append(swatch, document.createTextNode(categories[category] || 'Více typů akcí'));
    $('map-legend').append(item);
  }
  const groups = groupLocations(visibleEvents);
  const mappedCount = groups.reduce((sum, group) => sum + group.events.length, 0);
  $('map-count').textContent = `${groups.length} ${groups.length === 1 ? 'místo' : groups.length < 5 ? 'místa' : 'míst'}`;
  if (!map) return;
  markerLayer.clearLayers();
  userMarker?.remove();
  userMarker = null;
  const bounds = userPosition ? [[userPosition.lat, userPosition.lon]] : [];
  if (userPosition) userMarker = globalThis.L.circleMarker(bounds[0], { radius: 9, color: '#fff', weight: 3, fillColor: '#2265b0', fillOpacity: 1, interactive: false, className: 'user-location-marker' }).addTo(map);
  for (const group of groups) {
    const category = markerCategory(group.events);
    const categoryLabel = categories[category] || 'Více typů akcí';
    const popup = el('div', null, 'map-popup');
    popup.append(el('h3', group.label), el('p', categoryLabel));
    if (group.precision === 'town') popup.append(el('p', 'Pouze střed obce, nikoli přesné místo konání.'));
    for (const event of group.events) {
      const button = el('button', `${dateFormat.format(dateValue(event.date))} · ${event.title}`, 'popup-event');
      button.type = 'button';
      button.addEventListener('click', () => { map.closePopup(); selectEvent(event.id); });
      popup.append(button);
    }
    const marker = globalThis.L.circleMarker([group.lat, group.lon], { radius: 22, color: '#fffdf7', weight: 2, fillColor: MAP_COLORS[category], fillOpacity: .87, className: 'map-marker' }).addTo(markerLayer);
    marker.bindPopup(popup, { maxWidth: 280 });
    const path = marker.getElement();
    path.setAttribute('tabindex', '0');
    path.setAttribute('role', 'button');
    path.dataset.category = category;
    path.setAttribute('aria-label', `${group.label}: ${group.events.length} ${group.events.length === 1 ? 'akce' : 'akcí'} · ${categoryLabel}`);
    path.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); event.stopPropagation(); marker.openPopup(); }
    });
    bounds.push([group.lat, group.lon]);
  }
  userMarker?.bringToFront();
  if (userPosition && !groups.length) map.setView(bounds[0], 10, { animate: false });
  else if (bounds.length) map.fitBounds(bounds, { padding: [48, 48], maxZoom: 13, animate: false });
  const unmapped = visibleEvents.length - mappedCount;
  $('map-notice').textContent = tileFailed ? 'Mapový podklad se nepodařilo načíst. Body a seznam akcí zůstávají dostupné.' : unmapped ? `${unmapped} akcí nemá polohu; najdete je v seznamu.` : 'Vyberte bod pro akce v daném místě.';
}
async function ensureMap() {
  if (map) { map.invalidateSize(); return; }
  if (mapPromise) return mapPromise;
  mapPromise = (async () => {
    try {
      await import('./vendor/leaflet.js');
      const L = globalThis.L;
      if (!L?.map) throw new Error('Map library unavailable');
      map = L.map('map', { scrollWheelZoom: false, zoomControl: true }).setView([49.8, 15.4], 7);
      const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>',
        maxZoom: 18, minZoom: 5, keepBuffer: 1, updateWhenIdle: true
      });
      tiles.on('tileerror', () => {
        tileFailed = true;
        $('map-notice').textContent = 'Mapový podklad se nepodařilo načíst. Body a seznam akcí zůstávají dostupné.';
      });
      tiles.addTo(map);
      markerLayer = L.layerGroup().addTo(map);
      const observer = new ResizeObserver(() => map.invalidateSize());
      observer.observe($('map'));
      updateMap();
    } catch {
      $('map-notice').textContent = 'Mapu se nepodařilo načíst. Všechny akce najdete v seznamu.';
    }
  })();
  return mapPromise;
}
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function publicLink(text, value, className) {
  const href = safeHttps(value);
  if (!href) return null;
  const link = el('a', text, className);
  link.href = href;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  return link;
}
function dateValue(value) { return new Date(value.length === 10 ? `${value}T12:00:00Z` : value); }
function card(event) {
  const article = el('article', null, 'event-card');
  article.dataset.id = event.id;
  article.tabIndex = -1;
  const date = dateValue(event.date);
  const rail = el('div', null, 'date-rail');
  const day = dayHighlight(event.date);
  const dayLabel = day.holiday ? `Svátek · ${day.holiday}` : day.weekend ? 'Víkend' : null;
  if (dayLabel) {
    rail.classList.add(day.holiday ? 'is-holiday' : 'is-weekend');
    rail.title = `${dayLabel} — podle data začátku akce`;
  }
  const time = el('time'); time.dateTime = event.date;
  time.setAttribute('aria-label', `${dateFormat.format(date)}${dayLabel ? ` · ${dayLabel}` : ''}`);
  time.append(el('span', dayFormat.format(date)), el('strong', String(date.getUTCDate())), el('span', new Intl.DateTimeFormat('cs-CZ', { month: 'short', timeZone: 'Europe/Prague' }).format(date)));
  rail.append(time);
  const body = el('div', null, 'event-body');
  const badges = el('div', null, 'badges');
  badges.append(el('span', categories[event.category] || 'Akce', 'category-badge'));
  if (dayLabel) badges.append(el('span', dayLabel, `day-badge ${day.holiday ? 'holiday-badge' : 'weekend-badge'}`));
  if (event.audience !== 'všichni') badges.append(el('span', event.audience === 'dospělí' ? 'Dospělí' : event.audience === 'omezené zaměření' ? 'Omezené zaměření' : 'Senioři / omezené zaměření', 'audience-badge'));
  if (event.status === 'cancelled') badges.append(el('span', 'Zrušeno', 'warning-badge'));
  body.append(badges, el('h3', event.title), el('p', [event.town, event.venue].filter(Boolean).join(' · '), 'event-place'));
  const timing = el('p', timeLabel(event), event.startTime ? 'event-time' : 'event-time uncertain');
  if (event.endDate && event.endDate !== event.date) timing.append(document.createTextNode(` · do ${dateFormat.format(dateValue(event.endDate))}`));
  body.append(timing);
  if (event.description) body.append(el('p', event.description, 'event-description'));
  const facts = el('p', event.price || 'Vstupné neuvedeno', 'event-facts');
  if (event.registration) facts.append(document.createTextNode(` · ${event.registration}`));
  const booking = publicLink('Rezervace u pořadatele ↗', event.registrationUrl, 'booking-link');
  if (booking) { facts.append(document.createTextNode(' · '), booking); }
  body.append(facts);
  if (event.notes?.length) {
    const notes = el('ul', null, 'event-notes');
    for (const note of event.notes) notes.append(el('li', note));
    body.append(notes);
  }
  if (event.location?.precision === 'town') body.append(el('p', 'Poloha na mapě: pouze střed obce.', 'location-note'));
  const actions = el('div', null, 'event-actions');
  const source = publicLink('Zdroj a podrobnosti ↗', event.sourceUrl, 'source-link');
  if (source) actions.append(source);
  else actions.append(el('span', 'Zdroj není dostupný', 'muted'));
  if (groupLocations([event]).length) {
    const url = new URL('https://www.google.com/maps/dir/');
    url.searchParams.set('api', '1');
    url.searchParams.set('destination', `${event.location.lat},${event.location.lon}`);
    const navigation = publicLink(event.location.precision === 'town' ? 'Do obce ↗' : 'Navigovat ↗', url.href, 'navigation-link');
    navigation.title = event.location.precision === 'town' ? 'Google Maps: navigace do středu obce; přesné místo ověřte u pořadatele' : 'Google Maps: navigace na místo konání';
    actions.append(navigation);
  }
  const calendar = el('button', 'Do kalendáře (.ics)', 'calendar-button');
  calendar.type = 'button';
  calendar.addEventListener('click', () => {
    const url = URL.createObjectURL(new Blob([eventIcs(event)], { type: 'text/calendar;charset=utf-8' }));
    const download = el('a');
    download.href = url;
    download.download = `advent-${String(event.id).replace(/[^a-zA-Z0-9_-]/g, '')}.ics`;
    download.hidden = true;
    document.body.append(download);
    download.click();
    download.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  });
  actions.append(calendar);
  body.append(actions);
  const verified = dateValue(event.verifiedAt);
  if (!Number.isNaN(verified.getTime())) body.append(el('p', `Ověřeno ${dateFormat.format(verified)}`, 'verified'));
  article.append(rail, body);
  return article;
}
function populateOptions(id, values, label) {
  const select = $(id);
  const selected = select.value;
  const all = el('option', label); all.value = '';
  select.replaceChildren(all);
  for (const value of [...new Set(values.filter(value => typeof value === 'string' && value))].sort((a, b) => a.localeCompare(b, 'cs'))) {
    const option = el('option', value); option.value = value; select.append(option);
  }
  select.value = selected;
  if (select.selectedIndex < 0) select.value = '';
}
function updateRegions() {
  const published = new Set(events.map(event => event.region));
  populateOptions('region', [...coverageRegions, ...published], 'Všechny kraje');
  if (eventsLoaded) for (const option of $('region').options) {
    if (option.value && !published.has(option.value)) option.textContent = `${option.value} · zatím bez akcí`;
  }
}
function closeTowns() {
  $('town-options').hidden = true;
  $('town').setAttribute('aria-expanded', 'false');
  $('town').removeAttribute('aria-activedescendant');
}
function updateTowns() {
  const options = townSuggestions(events, $('region').value, $('town').value).map((town, index) => {
    const option = el('li', town);
    option.id = `town-option-${index}`;
    option.setAttribute('role', 'option');
    option.setAttribute('aria-selected', 'false');
    option.addEventListener('click', () => {
      $('town').value = town;
      $('town').focus({ preventScroll: true });
      render();
      closeTowns();
    });
    return option;
  });
  $('town-options').replaceChildren(...options);
  $('town').removeAttribute('aria-activedescendant');
  const open = options.length > 0 && document.activeElement === $('town');
  $('town-options').hidden = !open;
  $('town').setAttribute('aria-expanded', String(open));
}
$('town').addEventListener('focus', updateTowns);
$('town').addEventListener('click', updateTowns);
$('town').addEventListener('keydown', event => {
  if (event.isComposing) return;
  if (event.key === 'Escape' || event.key === 'Tab') {
    if (event.key === 'Escape' && !$('town-options').hidden) event.preventDefault();
    closeTowns();
  } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault();
    if ($('town-options').hidden) updateTowns();
    const options = [...$('town-options').children];
    if (!options.length) return;
    const active = options.findIndex(option => option.id === $('town').getAttribute('aria-activedescendant'));
    const index = active < 0 ? (event.key === 'ArrowDown' ? 0 : options.length - 1) : (active + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length;
    options.forEach((option, i) => option.setAttribute('aria-selected', String(i === index)));
    $('town').setAttribute('aria-activedescendant', options[index].id);
    options[index].scrollIntoView({ block: 'nearest' });
  } else if (event.key === 'Enter' && !$('town-options').hidden) {
    const active = $($('town').getAttribute('aria-activedescendant'));
    if (active) { event.preventDefault(); active.click(); }
  }
});
for (const type of ['pointerdown', 'focusin']) document.addEventListener(type, event => {
  if (!event.target.closest('.town-field')) closeTowns();
});
function render() {
  if (!eventsLoaded) return;
  $('clear-search').hidden = !$('search').value;
  $('clear-town').hidden = !$('town').value;
  const customDates = $('period').value === 'custom';
  $('date-range').hidden = !customDates;
  for (const id of ['date-from', 'date-to']) $(id).disabled = !customDates;
  const filters = Object.fromEntries(new FormData($('filters')));
  let visible = [], bounds = null, rangeError = '';
  try {
    if (customDates && ['date-from', 'date-to'].some(id => $(id).validity.badInput)) throw new RangeError('Zadejte platné datum.');
    const now = new Date();
    bounds = filterBounds(filters, now);
    visible = filterEvents(events, filters, now);
    if (userPosition) visible = nearbyEvents(visible, userPosition, Number($('nearby-radius').value));
  } catch (error) {
    if (!(error instanceof RangeError)) throw error;
    rangeError = error.message;
  }
  $('date-range-error').textContent = rangeError;
  $('date-range-error').hidden = !rangeError;
  for (const id of ['date-from', 'date-to']) $(id).setAttribute('aria-invalid', String(Boolean(rangeError)));
  const fragment = document.createDocumentFragment();
  if (!visible.length) {
    const empty = el('div', null, 'empty-state state-message');
    const emptyRegion = filters.region && !events.some(event => event.region === filters.region);
    empty.append(el('h3', rangeError ? 'Zkontrolujte rozsah dat' : 'Žádná akce pro tento výběr'), el('p', rangeError || (emptyRegion ? 'Pro tento kraj zatím nemáme publikované akce. Neznamená to, že se zde nic nekoná. Přehled má neúplné pokrytí.' : userPosition ? 'Žádné akce ve zvoleném okruhu a filtrech; přehled má neúplné pokrytí. Zkuste větší okruh nebo jiné filtry.' : 'Zkuste jiný termín, obec nebo zrušte filtry.')));
    fragment.append(empty);
  }
  let month;
  for (const event of visible) {
    if (event.date.slice(0, 7) !== month) {
      month = event.date.slice(0, 7);
      fragment.append(el('h2', monthFormat.format(dateValue(event.date)), 'month-heading'));
    }
    fragment.append(card(event));
  }
  $('results').replaceChildren(fragment);
  $('results').setAttribute('aria-busy', 'false');
  const period = bounds ? `${dateFormat.format(dateValue(bounds[0]))}–${dateFormat.format(dateValue(bounds[1]))}` : 'všechny termíny';
  const scope = [filters.region, filters.town].filter(Boolean);
  $('result-count').textContent = rangeError ? 'Opravte rozsah dat.' : `${visible.length} ${visible.length === 1 ? 'akce' : visible.length < 5 ? 'akce' : 'akcí'} · ${[...scope, period].join(' · ')}`;
  visibleEvents = visible;
  updateMap();
}
function setView(view) {
  $('explore').dataset.view = view;
  $('show-list').setAttribute('aria-pressed', String(view === 'list'));
  $('show-map').setAttribute('aria-pressed', String(view === 'map'));
  if (view === 'map' || desktop.matches) ensureMap();
}
desktop.addEventListener('change', () => { if (desktop.matches) ensureMap(); });
function clearLocation() {
  locationGeneration++;
  clearTimeout(locationTimer);
  userPosition = null;
  $('nearby-options').hidden = true;
  $('nearby-radius').value = '50';
  $('clear-location').hidden = true;
  $('locate-user').disabled = !eventsLoaded;
  $('location-status').textContent = '';
}
$('clear-location').addEventListener('click', () => { clearLocation(); render(); });
$('nearby-radius').addEventListener('change', render);
$('locate-user').addEventListener('click', event => {
  if (!event.isTrusted || !eventsLoaded) return;
  const generation = ++locationGeneration;
  const fail = message => { if (generation !== locationGeneration) return; clearLocation(); $('location-status').textContent = message; render(); };
  if (!isSecureContext) return fail('Poloha vyžaduje zabezpečené připojení HTTPS.');
  if (!navigator.geolocation) return fail('Tento prohlížeč zjištění polohy nepodporuje.');
  $('locate-user').disabled = true;
  $('clear-location').hidden = false;
  $('location-status').textContent = 'Zjišťujeme orientační polohu…';
  locationTimer = setTimeout(() => fail('Vypršel časový limit zjišťování polohy. Zkuste to znovu.'), 10000);
  navigator.geolocation.getCurrentPosition(async result => {
    if (generation !== locationGeneration) return;
    clearTimeout(locationTimer);
    const coords = result?.coords;
    const position = { lat: coords?.latitude, lon: coords?.longitude, accuracy: coords?.accuracy };
    if (!Number.isFinite(distanceKm(position, position)) || !Number.isFinite(position.accuracy) || position.accuracy < 0) return fail('Poloha nyní není dostupná. Zkuste to znovu.');
    userPosition = position;
    $('locate-user').disabled = false;
    $('nearby-options').hidden = false;
    $('location-status').textContent = `${position.accuracy > 5000 ? 'Nízká přesnost. ' : ''}Orientační poloha, přesnost přibližně ${Math.round(position.accuracy)} m.`;
    render();
    setView('map');
    await ensureMap();
    if (generation !== locationGeneration) return;
    if (!map) {
      $('location-status').textContent += ' Mapu se nepodařilo načíst; okolní akce najdete v seznamu.';
      setView('list');
    }
  }, error => fail(error?.code === 1 ? 'Zjištění polohy nebylo povoleno. Přehled funguje i bez ní.' : error?.code === 3 ? 'Vypršel časový limit zjišťování polohy. Zkuste to znovu.' : 'Poloha nyní není dostupná. Zkuste to znovu.'), { timeout: 10000, maximumAge: 60000, enableHighAccuracy: false });
});
$('show-list').addEventListener('click', () => setView('list'));
$('show-map').addEventListener('click', () => setView('map'));
$('filters').addEventListener('submit', event => event.preventDefault());
$('clear-search').addEventListener('click', () => {
  $('search').value = '';
  render();
  $('search').focus({ preventScroll: true });
});
$('clear-town').addEventListener('click', () => {
  $('town').value = '';
  render();
  $('town').focus({ preventScroll: true });
  updateTowns();
});
$('region').addEventListener('change', () => {
  if (!townSuggestions(events, $('region').value, $('town').value).length) $('town').value = '';
  updateTowns();
});
$('filters').addEventListener('input', event => {
  render();
  if (event.target === $('town')) updateTowns(); else closeTowns();
});
$('filters').addEventListener('change', event => { if (event.target !== $('town')) { closeTowns(); render(); } });
$('filters').addEventListener('reset', event => {
  event.preventDefault();
  $('search').value = '';
  $('period').value = 'all';
  $('date-from').value = '';
  $('date-to').value = '';
  $('category').value = '';
  $('region').value = '';
  $('town').value = '';
  closeTowns();
  clearLocation();
  render();
});
function validData(data) {
  const date = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(`${value}T12:00:00Z`)) && new Date(`${value}T12:00:00Z`).toISOString().slice(0, 10) === value;
  const time = value => value === null || typeof value === 'string' && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value);
  return data?.schemaVersion === 1 && Array.isArray(data.events) && Number.isFinite(Date.parse(data.generatedAt)) && data.events.every(event =>
    event && typeof event.id === 'string' && /^[a-zA-Z0-9_-]+$/.test(event.id) &&
    typeof event.title === 'string' && typeof event.town === 'string' && date(event.date) &&
    (event.endDate === null || date(event.endDate) && event.endDate >= event.date) && time(event.startTime) && time(event.endTime) &&
    typeof event.description === 'string' && Array.isArray(event.notes) && event.notes.every(note => typeof note === 'string') &&
    Object.hasOwn(categories, event.category) && ['všichni', 'dospělí', 'senioři / omezené zaměření', 'omezené zaměření'].includes(event.audience) &&
    ['confirmed', 'time-unconfirmed', 'cancelled'].includes(event.status) && Number.isFinite(Date.parse(event.verifiedAt))
  ) && new Set(data.events.map(event => event.id)).size === data.events.length;
}
async function load() {
  eventsLoaded = false;
  $('locate-user').disabled = true;
  for (const control of $('filters').elements) control.disabled = true;
  $('results').setAttribute('aria-busy', 'true');
  $('results').replaceChildren(el('p', 'Načítáme adventní akce…', 'state-message'));
  $('result-count').textContent = 'Načítáme přehled…';
  try {
    const response = await fetch(new URL('./events.json', import.meta.url), { cache: 'no-cache', signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw new Error('Přehled není dostupný');
    const data = await response.json();
    if (!validData(data)) throw new Error('Neplatný formát přehledu');
    events = data.events.filter(event => event.date <= SEASON_END && (event.endDate || event.date) >= SEASON_START);
    eventsLoaded = true;
    $('locate-user').disabled = false;
    updateRegions();
    $('data-updated').textContent = `Přehled aktualizován ${dateFormat.format(dateValue(data.generatedAt))}.`;
    for (const control of $('filters').elements) control.disabled = false;
    render();
    if (desktop.matches || $('explore').dataset.view === 'map') ensureMap();
  } catch {
    $('results').setAttribute('aria-busy', 'false');
    const error = el('div', null, 'load-error state-message');
    error.setAttribute('role', 'alert');
    error.append(el('h3', 'Přehled se nepodařilo načíst'), el('p', 'Zkontrolujte připojení a zkuste to znovu.'));
    const retry = el('button', 'Zkusit znovu');
    retry.type = 'button';
    retry.addEventListener('click', load);
    error.append(retry);
    $('results').replaceChildren(error);
    $('result-count').textContent = 'Přehled není dostupný';
    $('map-notice').textContent = 'Nejprve je potřeba načíst přehled akcí. Zkuste to znovu v seznamu.';
  }
}
const checkedFormat = new Intl.DateTimeFormat('cs-CZ', { day: 'numeric', month: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Prague' });
const checkedLabel = value => value && Number.isFinite(Date.parse(value)) ? checkedFormat.format(new Date(value)) : 'neuvedeno';
const countValue = value => Number.isInteger(value) && value >= 0;
function validCoverage(data) {
  const date = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(`${value}T12:00:00Z`)) && new Date(`${value}T12:00:00Z`).toISOString().slice(0, 10) === value;
  return data && Number.isFinite(Date.parse(data.generatedAt)) &&
    date(data.window?.from) && date(data.window?.through) && data.window.through >= data.window.from &&
    Array.isArray(data.regions) && data.regions.every(region => typeof region === 'string') && new Set(data.regions).size === data.regions.length &&
    typeof data.coverageNote === 'string' && typeof data.complete === 'boolean' &&
    Number.isFinite(data.metrics?.durationSeconds) && data.metrics.durationSeconds >= 0 && countValue(data.metrics.requestCount) && countValue(data.metrics.aiCalls) &&
    Array.isArray(data.sources) && new Set(data.sources.map(source => source?.id)).size === data.sources.length &&
    data.sources.every(source => source && typeof source.id === 'string' && source.id && typeof source.town === 'string' && data.regions.includes(source.region) &&
      ['ok', 'partial', 'error'].includes(source.status) && countValue(source.eventCount) && countValue(source.reviewCount));
}
async function loadCoverage() {
  try {
    const response = await fetch(new URL('./coverage.json', import.meta.url), { cache: 'no-cache', signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw new Error('Pokrytí není dostupné');
    const data = await response.json();
    if (!validCoverage(data)) throw new Error('Neplatný formát pokrytí');
    coverageRegions = data.regions;
    updateRegions();
    const regions = new Set(data.regions).size;
    const sourceCount = new Set(data.sources.map(source => source.id)).size;
    $('scope-summary').textContent = `${regions} ${regions === 1 ? 'kraj' : regions < 5 ? 'kraje' : 'krajů'} · ${sourceCount} ${sourceCount === 1 ? 'zdroj' : sourceCount < 5 ? 'zdroje' : 'zdrojů'}`;
    const fragment = document.createDocumentFragment();
    fragment.append(el('p', data.coverageNote));
    fragment.append(el('p', `Sledované období: ${dateFormat.format(dateValue(data.window.from))}–${dateFormat.format(dateValue(data.window.through))}. Kraje: ${data.regions.join(', ')}.`));
    fragment.append(el('p', 'Sběr je omezený: nejvýše 2 stránky výpisu a 14 detailů na zdroj. Nejde o úplný přehled akcí; nulový počet neznamená, že se ve městě nic nekoná.'));
    const seconds = Math.round(data.metrics.durationSeconds);
    const duration = seconds >= 60 ? `${Math.floor(seconds / 60)} min ${seconds % 60} s` : `${seconds} s`;
    fragment.append(el('p', `Poslední sběr: ${checkedLabel(data.generatedAt)} (Česko) · Doba sběru: ${duration} · HTTP požadavky: ${data.metrics.requestCount}.`, 'coverage-metrics'));
    fragment.append(el('p', `AI volání při posledním automatickém sběru: ${data.metrics.aiCalls}`, 'coverage-metrics'));
    const sources = el('ul', null, 'coverage-sources');
    const statuses = { ok: 'ověřeno', partial: 'částečně', error: 'nedostupné' };
    for (const source of data.sources) {
      const item = el('li', null, 'coverage-source');
      const heading = el('div', null, 'coverage-source-heading');
      const title = el('h3');
      title.append(publicLink(source.town, source.url) || el('span', source.town));
      heading.append(title, el('span', statuses[source.status], `source-status source-${source.status}`));
      item.append(heading, el('p', source.region), el('p', `Poslední kontrola: ${checkedLabel(source.lastChecked)} (Česko)`));
      if (source.lastSuccess) item.append(el('p', `Poslední úspěch: ${checkedLabel(source.lastSuccess)} (Česko)`));
      item.append(el('p', `Publikované akce: ${source.eventCount} · K ověření: ${source.reviewCount}${countValue(source.excludedCount) ? ` · Mimo rozsah: ${source.excludedCount}` : ''}`));
      if (typeof source.coverageNote === 'string' && source.coverageNote) item.append(el('p', source.coverageNote));
      if (typeof source.lastError === 'string' && source.lastError) item.append(el('p', source.lastError, 'coverage-error'));
      sources.append(item);
    }
    fragment.append(sources);
    $('coverage-content').replaceChildren(fragment);
  } catch {
    $('scope-summary').textContent = '';
    $('coverage-content').replaceChildren(el('p', 'Pokrytí zdrojů se nepodařilo načíst. To nebrání prohlížení akcí; zdroj najdete u každé z nich.'));
  }
}
load();
loadCoverage();
