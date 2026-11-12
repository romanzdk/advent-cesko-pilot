import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

// Synthetic public fixture only: never load the parent's live events.json.
export const fixture = {
  schemaVersion: 1, generatedAt: '2026-11-12T10:00:00Z', season: 2026, region: 'Mnichovice a okolí', events: [
    { id: 'fixture-b', title: 'Vánoční dílna', town: 'Mnichovice', venue: 'Klub', date: '2026-11-28', endDate: null, startTime: '16:00', endTime: null, category: 'tvoreni', price: '150 Kč', registration: 'Nutná rezervace', registrationUrl: 'https://example.cz/rezervace', description: 'Testovací dílna adventních věnců.', notes: ['Kapacita je omezená.'], audience: 'dospělí', status: 'confirmed', verifiedAt: '2026-11-12T10:00:00Z', sourceUrl: 'https://example.cz/dilna', location: { lat: 49.936, lon: 14.711, precision: 'town', label: 'Mnichovice', sourceUrl: 'https://example.cz/poloha' } },
    { id: 'fixture-a', title: 'Rozsvícení stromu', town: 'Říčany', venue: 'Náměstí', date: '2026-11-20', endDate: null, startTime: null, endTime: null, category: 'strom', price: null, registration: null, registrationUrl: null, description: 'Testovací slavnost.', notes: ['Přesný začátek zatím není uveden.'], audience: 'všichni', status: 'time-unconfirmed', verifiedAt: '2026-11-12T10:00:00Z', sourceUrl: 'https://example.cz/strom', location: { lat: 49.99, lon: 14.655, precision: 'venue', label: 'Náměstí', sourceUrl: 'https://example.cz/poloha' } },
    { id: 'fixture-c', title: '<img src=x onerror=alert(1)> Adventní setkání', town: 'Mnichovice', venue: 'Klub', date: '2026-12-05', endDate: null, startTime: '14:00', endTime: '17:00', category: 'setkani', price: 'Zdarma', registration: null, registrationUrl: 'javascript:alert(1)', description: '<script>window.injected=true</script>', notes: [], audience: 'senioři / omezené zaměření', status: 'confirmed', verifiedAt: '2026-11-12T10:00:00Z', sourceUrl: 'javascript:alert(1)', location: { lat: 49.936, lon: 14.711, precision: 'town', label: 'Mnichovice', sourceUrl: 'https://example.cz/poloha' } }
  ]
};
const regionalFixture = {
  ...fixture,
  events: fixture.events.map((event, index) => ({ ...event,
    region: ['Plzeňský kraj', 'Liberecký kraj', 'Jihomoravský kraj'][index],
    town: ['Plasy', 'Turnov', 'Kuřim'][index],
    location: { ...event.location, lat: [49.935, 50.587, 49.299][index], lon: [13.39, 15.157, 16.531][index], label: ['Plasy', 'Turnov', 'Kuřim'][index] }
  }))
};
const coverageFixture = {
  generatedAt: '2026-11-12T10:00:00Z', window: { from: '2026-11-20', through: '2026-12-24' },
  regions: ['Plzeňský kraj', 'Liberecký kraj', 'Jihomoravský kraj'],
  sources: ['ok', 'partial', 'error'].map((status, index) => ({
    id: `source-${index}`, town: ['Plasy', 'Turnov', '<img src=x onerror=alert(1)> Kuřim'][index],
    region: ['Plzeňský kraj', 'Liberecký kraj', 'Jihomoravský kraj'][index],
    url: index === 2 ? 'javascript:alert(1)' : `https://example.cz/source-${index}`,
    adapter: 'municipal', coverageNote: 'Pořadatelský výběr, nikoli celý městský kalendář.', excludedCount: 7, status, lastChecked: '2026-11-12T10:00:00Z', lastSuccess: index === 2 ? null : '2026-11-12T10:00:00Z',
    eventCount: [2, 1, 0][index], reviewCount: [0, 3, 0][index], lastError: index === 2 ? '<script>window.injected=true</script>' : null
  })),
  metrics: { durationSeconds: 125.4, requestCount: 18, http304: 0, cacheUnchanged: 0, eventsNew: 3, eventsChanged: 0, eventsUnchanged: 0, eventsPublished: 3, reviewCount: 3, aiCalls: 0 },
  complete: false, coverageNote: 'Testovací omezený výběr veřejných zdrojů.'
};
let browser, server, origin;
before(async () => {
  let executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || chromium.executablePath();
  if (!existsSync(executablePath) && !process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE) {
    const cache = join(homedir(), '.cache', 'ms-playwright');
    const installed = (await readdir(cache).catch(() => [])).filter(name => name.startsWith('chromium_headless_shell-')).sort((a, b) => b.localeCompare(a, 'en', { numeric: true }));
    for (const name of installed) {
      const candidate = join(cache, name, 'chrome-headless-shell-linux64', 'chrome-headless-shell');
      if (existsSync(candidate)) { executablePath = candidate; break; }
    }
  }
  browser = await chromium.launch({ executablePath, headless: true, args: ['--no-sandbox'] });
  server = createServer(async (req, res) => {
    let path = new URL(req.url, 'http://local').pathname.replace(/^\/(?:advent-mnichovice|advent-cesko-pilot)\//, '/');
    if (path === '/') path = '/index.html';
    // An explicit asset allowlist prevents accidentally reading live data.
    if (!/^\/(index\.html|app\.js|helpers\.js|styles\.css|favicon\.svg|vendor\/leaflet\.(js|css))$/.test(path)) { res.writeHead(404).end(); return; }
    try {
      const data = await readFile(new URL(`../site${path}`, import.meta.url));
      res.setHeader('Content-Type', path.endsWith('.js') ? 'text/javascript' : path.endsWith('.css') ? 'text/css' : path.endsWith('.svg') ? 'image/svg+xml' : 'text/html; charset=utf-8');
      res.setHeader('X-Content-Type-Options', 'nosniff');
      res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://tile.openstreetmap.org; connect-src 'self'; object-src 'none'; base-uri 'self'");
      res.end(data);
    } catch { res.setHeader('Content-Type', 'text/html'); res.end('<!doctype html><html lang="cs"><title>Missing frontend</title><body>Frontend not implemented</body></html>'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  origin = `http://127.0.0.1:${server.address().port}`;
});
after(async () => {
  await browser?.close();
  if (server) await new Promise(resolve => server.close(resolve));
});
async function app(run, { data = fixture, base = '/advent-cesko-pilot/', mobile = false, responseStatus = 200, delay = 0, libraryFail = false, coverage = coverageFixture, coverageStatus = 200, coveragePending = false } = {}) {
  const context = await browser.newContext({ viewport: mobile ? { width: 393, height: 852 } : { width: 1440, height: 1000 }, timezoneId: 'America/Los_Angeles' });
  try {
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.clock.install({ time: new Date('2026-11-12T12:00:00Z') });
    await page.route('**/events.json', async route => {
      if (delay) await new Promise(resolve => setTimeout(resolve, delay));
      await route.fulfill({ status: responseStatus, contentType: 'application/json', body: JSON.stringify(data) });
    });
    await page.route('**/coverage.json', async route => {
      if (coveragePending) return;
      await route.fulfill({ status: coverageStatus, contentType: 'application/json', body: JSON.stringify(coverage) });
    });
    await page.route('https://tile.openstreetmap.org/**', route => route.abort());
    if (libraryFail) await page.route('**/vendor/leaflet.js', route => route.abort());
    await page.goto(origin + base);
    await run(page, errors);
  } finally { await context.close(); }
}

test('scope summary counts six coverage regions and twelve sources, not event towns', async () => {
  const regions = [...coverageFixture.regions, 'Středočeský kraj', 'Jihočeský kraj', 'Kraj Vysočina'];
  const data = { ...fixture, events: regions.map((region, i) => ({ ...regionalFixture.events[i % 3],
    id: `six-${i}`, region, town: `Obec ${i}`, sourceUrl: `https://example.cz/event-${i}`,
    location: { ...regionalFixture.events[i % 3].location, lat: [49.935, 50.587, 49.299, 49.91, 48.97, 49.39][i], lon: [13.39, 15.157, 16.531, 14.71, 14.47, 15.59][i] }
  })) };
  const coverage = { ...coverageFixture, regions, sources: Array.from({ length: 12 }, (_, i) => ({
    ...coverageFixture.sources[0], id: `source-${i}`, region: regions[i % 6], town: `Zdroj ${i}`
  })) };
  await app(async page => {
    await page.waitForSelector('.event-card');
    assert.equal(await page.locator('#scope-summary').count(), 1);
    await page.waitForFunction(() => document.getElementById('scope-summary').textContent === '6 krajů · 12 zdrojů');
    assert.equal(await page.locator('#region option').count(), 7);
    await page.waitForSelector('#map .leaflet-interactive');
    assert.equal(await page.locator('#map .leaflet-interactive').count(), 6);
    for (const region of regions) {
      await page.locator('#region').selectOption(region);
      assert.equal(await page.locator('.event-card').count(), 1);
      assert.equal(await page.locator('#town option').count(), 2);
      assert.equal(await page.locator('#scope-summary').innerText(), '6 krajů · 12 zdrojů');
    }
  }, { data, coverage });
  for (const change of ['duplicate-id', 'wrong-region']) {
    const malformed = structuredClone(coverage);
    if (change === 'duplicate-id') malformed.sources[0].id = malformed.sources[1].id;
    else malformed.sources[0].region = 'Neznámý kraj';
    await app(async page => {
      await page.waitForSelector('.event-card');
      await page.waitForFunction(() => document.getElementById('coverage-content').textContent.includes('Pokrytí zdrojů se nepodařilo'));
      assert.equal(await page.locator('#scope-summary').innerText(), '');
    }, { data, coverage: malformed, mobile: true });
  }
  await app(async page => {
    await page.waitForSelector('.event-card');
    await page.waitForFunction(() => document.getElementById('coverage-content').textContent.includes('Pokrytí zdrojů se nepodařilo'));
    assert.equal(await page.locator('#scope-summary').innerText(), '');
    assert.match(await page.locator('.scope-note:not(#scope-summary)').innerText(), /Výběr veřejných zdrojů/);
  }, { data, coverageStatus: 503, mobile: true });
});

for (const [label, window] of [
  ['invalid start month', { from: '2026-99-20', through: '2026-12-24' }],
  ['invalid end month', { from: '2026-11-20', through: '2026-99-24' }],
  ['invalid start calendar day', { from: '2026-02-30', through: '2026-12-24' }],
  ['invalid end calendar day', { from: '2026-11-20', through: '2026-11-31' }],
  ['reversed dates', { from: '2026-12-24', through: '2026-11-20' }]
]) {
  test(`coverage rejects ${label} without scope summary or broken event filters`, async () => {
    await app(async (page, errors) => {
      await page.waitForSelector('.event-card');
      await page.waitForFunction(() => {
        const panel = document.getElementById('coverage-content');
        return panel.querySelector('.coverage-source') || panel.textContent.includes('Pokrytí zdrojů se nepodařilo');
      });
      assert.equal(await page.locator('#scope-summary').innerText(), '');
      assert.match(await page.locator('#coverage-content').textContent(), /Pokrytí zdrojů se nepodařilo načíst/);
      assert.equal(await page.locator('.event-card').count(), 3);
      await page.locator('#category').selectOption('strom');
      assert.equal(await page.locator('.event-card').count(), 1);
      assert.deepEqual(errors, []);
    }, { coverage: { ...coverageFixture, window }, mobile: true });
  });
}

test('region scope limits towns, combines with other filters and resets cleanly', async () => {
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    assert.equal(await page.locator('#region[name="region"]').count(), 1);
    assert.deepEqual(await page.locator('#region option').allTextContents(), ['Všechny kraje', 'Jihomoravský kraj', 'Liberecký kraj', 'Plzeňský kraj']);
    await page.locator('#town').selectOption('Turnov');
    await page.locator('#region').selectOption('Plzeňský kraj');
    assert.equal(await page.locator('#town').inputValue(), '');
    assert.deepEqual(await page.locator('#town option').allTextContents(), ['Všechny obce', 'Plasy']);
    assert.equal(await page.locator('.event-card').getAttribute('data-id'), 'fixture-b');
    assert.match(await page.locator('#result-count').innerText(), /Plzeňský kraj/);
    await page.locator('#town').selectOption('Plasy');
    assert.match(await page.locator('#result-count').innerText(), /Plasy/);
    await page.locator('#category').selectOption('strom');
    await page.waitForSelector('.empty-state');
    await page.getByRole('button', { name: 'Zrušit filtry', exact: true }).click();
    assert.equal(await page.locator('#region').inputValue(), '');
    assert.equal(await page.locator('#town option').count(), 4);
    assert.equal(await page.locator('.event-card').count(), 3);
    assert.deepEqual(errors, []);
  }, { data: regionalFixture, mobile: true });
});

test('map names its bounded Christmas 2026 scope and excludes out-of-window events', async () => {
  const data = { ...regionalFixture, events: [
    ...regionalFixture.events,
    ...['2025-11-28', '2026-11-19', '2026-12-24', '2026-12-25', '2027-11-28'].map((date, index) => ({ ...regionalFixture.events[0], id: `boundary-${index}`, date }))
  ] };
  await app(async page => {
    await page.waitForSelector('.event-card');
    assert.equal(await page.locator('h1').innerText(), 'Advent v Česku 2026');
    assert.equal(await page.title(), 'Advent v Česku 2026');
    assert.match(await page.locator('.intro').innerText(), /Sezonní výběr veřejných akcí 2026/);
    assert.match(await page.locator('.intro').innerText(), /Výběr veřejných zdrojů, nikoli úplný přehled krajů ani celé ČR\./);
    assert.doesNotMatch(await page.locator('.footer').innerText(), /pilot/i);
    assert.doesNotMatch(await page.locator('.edition').innerText(), /3 KRAJE/);
    assert.match(await page.locator('.intro').innerText(), /20\. 11\. – 24\. 12\. 2026/);
    assert.equal(await page.getByRole('link', { name: 'Mnichovice a okolí', exact: true }).getAttribute('href'), 'https://romanzdk.github.io/advent-mnichovice/');
    assert.deepEqual(await page.locator('.event-card').evaluateAll(cards => cards.map(card => card.dataset.id)), ['fixture-a', 'fixture-b', 'fixture-c', 'boundary-2']);
    await page.locator('#search').fill('dílna');
    await page.getByRole('button', { name: 'Zrušit filtry', exact: true }).click();
    assert.equal(await page.locator('.event-card').count(), 4);
  }, { data, mobile: true });
});

test('three-region map fits every location rather than clipping distant towns', async () => {
  await app(async page => {
    await page.waitForSelector('#map .leaflet-interactive');
    const markers = await page.locator('#map .leaflet-interactive').evaluateAll(nodes => nodes.map(node => {
      const marker = node.getBoundingClientRect();
      const map = document.getElementById('map').getBoundingClientRect();
      return { label: node.getAttribute('aria-label'), fits: marker.left >= map.left && marker.right <= map.right && marker.top >= map.top && marker.bottom <= map.bottom };
    }));
    assert.equal(markers.length, 3);
    assert(markers.every(marker => marker.fits), JSON.stringify(markers));
    await page.locator('#region').selectOption('Liberecký kraj');
    assert.equal(await page.locator('#map .leaflet-interactive').count(), 1);
    await page.getByRole('button', { name: 'Zrušit filtry', exact: true }).click();
    assert.equal(await page.locator('#map .leaflet-interactive').count(), 3);
  }, { data: regionalFixture });
});

test('coverage discloses real bounded collection safely without blocking events on failure or delay', async () => {
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    assert.equal(await page.locator('details#coverage').count(), 1);
    assert.equal(await page.locator('#coverage').getAttribute('open'), null);
    const summary = page.locator('#coverage summary');
    assert.equal(await summary.innerText(), 'Zdroje a pokrytí');
    assert((await summary.boundingBox()).height >= 44);
    await summary.click();
    await page.waitForSelector('.coverage-source', { timeout: 3000 });
    assert.equal(await page.locator('.coverage-source').count(), 3);
    const text = await page.locator('#coverage').innerText();
    for (const label of ['ověřeno', 'částečně', 'nedostupné', 'Plasy', 'Plzeňský kraj', '12. 11. 2026', '11:00', '2 min 5 s', 'AI volání při posledním automatickém sběru: 0', coverageFixture.coverageNote]) assert(text.includes(label), label);
    assert.match(text, /nejvýše 2 stránky výpisu a 14 detailů na zdroj/);
    assert.match(text, /Pořadatelský výběr, nikoli celý městský kalendář/);
    assert.match(text, /Mimo rozsah: 7/);
    assert.match(await page.locator('.coverage-source').first().innerText(), /Publikované akce: 2 · K ověření: 0/);
    assert.match(await page.locator('.coverage-source').nth(1).innerText(), /Publikované akce: 1 · K ověření: 3/);
    assert.equal(await page.locator('#coverage a').first().getAttribute('href'), 'https://example.cz/source-0');
    assert.equal(await page.locator('#coverage img, #coverage script, #coverage table, #coverage a[href^="javascript:"]').count(), 0);
    assert.match(text, /<script>window.injected=true<\/script>/);
    for (const width of [393, 320]) {
      await page.setViewportSize({ width, height: 852 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    }
    await page.addStyleTag({ content: 'html { font-size: 125%; }' });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.deepEqual(errors, []);
    await page.screenshot({ path: fileURLToPath(new URL('./coverage-mobile-fixture.png', import.meta.url)), fullPage: true });
  }, { data: regionalFixture, mobile: true, base: '/' });
  for (const options of [{ coverageStatus: 503 }, { coverage: {} }]) {
    await app(async (page, errors) => {
      await page.waitForSelector('.event-card');
      await page.locator('#coverage summary').click();
      await page.waitForFunction(() => document.getElementById('coverage-content').textContent.includes('Pokrytí zdrojů se nepodařilo načíst'));
      assert.equal(await page.locator('.event-card').count(), 3);
      await page.locator('#category').selectOption('strom');
      assert.equal(await page.locator('.event-card').count(), 1);
      assert.deepEqual(errors, []);
    }, { ...options, mobile: true });
  }
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    assert.equal(await page.locator('.event-card').count(), 3);
    await page.locator('#coverage summary').click();
    assert.match(await page.locator('#coverage-content').innerText(), /Načítáme/);
    assert.equal(await page.locator('#category').isEnabled(), true);
    assert.deepEqual(errors, []);
  }, { coveragePending: true, mobile: true });
});

test('desktop filters retain one compact row with the added region control', async () => {
  await app(async page => {
    await page.waitForSelector('.event-card');
    for (const width of [1440, 1100]) {
      await page.setViewportSize({ width, height: 1000 });
      const bottoms = await page.locator('#filters input, #filters select, #filters button').evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().bottom));
      assert(Math.max(...bottoms) - Math.min(...bottoms) < 2, JSON.stringify({ width, bottoms }));
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    }
    await page.screenshot({ path: fileURLToPath(new URL('./pilot-desktop-fixture.png', import.meta.url)), fullPage: false });
  }, { data: regionalFixture });
});

test('default mobile date and type labels have room for native select arrows', async () => {
  await app(async page => {
    await page.waitForSelector('.event-card');
    for (const width of [393, 320]) {
      await page.setViewportSize({ width, height: 852 });
      const clipped = await page.locator('select').evaluateAll(nodes => nodes.filter(node => {
        const style = getComputedStyle(node);
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        context.font = style.font;
        return context.measureText(node.selectedOptions[0].textContent).width + parseFloat(style.paddingLeft) + parseFloat(style.paddingRight) + 12 > node.clientWidth;
      }).map(node => ({ id: node.id, width: node.clientWidth, font: getComputedStyle(node).font, text: node.selectedOptions[0].textContent })));
      assert.deepEqual(clipped, [], `clipped defaults at ${width}px`);
    }
  }, { mobile: true });
});

test('mobile fields avoid iPhone autozoom, masthead stays on one line and tablet reset remains touch-sized', async () => {
  await app(async page => {
    await page.waitForSelector('.event-card');
    const fontSizes = await page.locator('input, select').evaluateAll(nodes => nodes.map(n => parseFloat(getComputedStyle(n).fontSize)));
    assert(fontSizes.every(size => size >= 16), JSON.stringify(fontSizes));
    const wordmark = await page.locator('.wordmark span:first-child').boundingBox();
    assert(wordmark.height < 35, `wordmark height: ${wordmark.height}`);
    await page.keyboard.press('Tab');
    assert.equal(await page.locator('.skip-link').evaluate(node => node === document.activeElement), true);
    assert((await page.locator('.skip-link').boundingBox()).y >= 0);
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#results').evaluate(node => node === document.activeElement), true);
    await page.setViewportSize({ width: 900, height: 900 });
    assert((await page.locator('.reset-button').boundingBox()).height >= 44);
  }, { mobile: true });
});

test('loading, invalid data and retry states remain usable; missing map library never hides list', async () => {
  await app(async page => {
    assert.equal(await page.locator('#results').getAttribute('aria-busy'), 'true');
    assert.match(await page.locator('#results').innerText(), /Načítáme/);
    await page.waitForSelector('.event-card');
  }, { delay: 600 });
  await app(async page => {
    await page.waitForSelector('.load-error', { timeout: 3000 });
    assert.equal(await page.locator('#results').getAttribute('aria-busy'), 'false');
    await page.route('**/events.json', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify(fixture) }));
    await page.getByRole('button', { name: 'Zkusit znovu' }).click();
    await page.waitForSelector('.event-card');
    assert.equal(await page.locator('.event-card').count(), 3);
  }, { data: { schemaVersion: 2, events: [] } });
  await app(async page => {
    await page.waitForSelector('.load-error');
    assert.match(await page.locator('#map-notice').innerText(), /přehled/);
  }, { responseStatus: 500 });
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    await page.waitForFunction(() => document.getElementById('map-notice').textContent.includes('Mapu se nepodařilo'));
    assert.equal(await page.locator('.event-card').count(), 3);
    await page.locator('#search').fill('stromu');
    assert.equal(await page.locator('.event-card').count(), 1);
    assert.deepEqual(errors, []);
  }, { libraryFail: true, base: '/' });
  await app(async page => {
    await page.waitForSelector('.empty-state');
    assert.equal(await page.locator('#results').getAttribute('aria-busy'), 'false');
  }, { data: { ...fixture, events: [] }, base: '/' });
});

test('individual calendar downloads contain the chosen event and navigation discloses town precision', async () => {
  await app(async page => {
    await page.waitForSelector('.event-card');
    const card = page.locator('[data-id="fixture-b"]');
    const downloadPromise = page.waitForEvent('download', { timeout: 3000 });
    await card.getByRole('button', { name: /Do kalendáře/ }).click({ timeout: 3000 });
    const download = await downloadPromise;
    assert.equal(download.suggestedFilename(), 'advent-fixture-b.ics');
    let text = '';
    for await (const part of await download.createReadStream()) text += part.toString('utf8');
    assert.match(text, /SUMMARY:Vánoční dílna/);
    assert.match(text.replace(/\r\n /g, ''), /konec orientační/);
    assert.equal((text.match(/BEGIN:VEVENT/g) || []).length, 1);
    const navigation = card.getByRole('link', { name: /Do obce/ });
    assert.match(await navigation.getAttribute('href'), /^https:\/\/www\.openstreetmap\.org\/directions\?/);
    assert.match(await navigation.getAttribute('href'), /49.936/);
  });
});

test('map groups shared places, selects a card and follows active filters even without tiles', async () => {
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    await page.waitForSelector('#map .leaflet-interactive', { timeout: 3000 });
    assert.equal(await page.locator('#map .leaflet-interactive').count(), 2);
    assert.match(await page.locator('#map-notice').innerText(), /podklad/);
    assert.match(await page.locator('.leaflet-control-attribution').innerText(), /OpenStreetMap/);
    const marker = page.locator('#map .leaflet-interactive[aria-label*="Mnichovice"]');
    await marker.focus();
    await marker.press('Enter');
    await page.waitForSelector('.popup-event');
    assert.equal(await page.locator('.popup-event').count(), 2);
    await page.locator('.popup-event').last().click();
    assert.equal(await page.locator('.event-card.selected').getAttribute('data-id'), 'fixture-c');
    assert.equal(await page.locator('.event-card.selected').evaluate(node => node === document.activeElement), true);
    await page.locator('#category').selectOption('strom');
    await page.waitForFunction(() => document.querySelectorAll('#map .leaflet-interactive').length === 1);
    assert.deepEqual(errors, []);
    await page.screenshot({ path: fileURLToPath(new URL('./desktop-fixture.png', import.meta.url)), fullPage: true });
  });
  await app(async page => {
    await page.waitForSelector('.event-card');
    await page.locator('#show-map').click();
    await page.waitForSelector('#map .leaflet-interactive');
    await page.locator('#map .leaflet-interactive[aria-label*="Mnichovice"]').click();
    await page.locator('.popup-event').first().click();
    assert.equal(await page.locator('#results').isVisible(), true);
    assert.equal(await page.locator('.event-card.selected').getAttribute('data-id'), 'fixture-b');
    await page.screenshot({ path: fileURLToPath(new URL('./mobile-fixture.png', import.meta.url)), fullPage: true });
  }, { mobile: true });
});

test('responsive list/map controls keep mobile targets usable without horizontal scrolling', async () => {
  await app(async page => {
    await page.waitForSelector('.event-card');
    assert.equal(await page.locator('#map-panel').isVisible(), false);
    await page.locator('#show-map').click();
    assert.equal(await page.locator('#map-panel').isVisible(), true);
    assert.equal(await page.locator('#results').isVisible(), false);
    assert.equal(await page.locator('#show-map').getAttribute('aria-pressed'), 'true');
    await page.locator('#show-list').click();
    assert.equal(await page.locator('#results').isVisible(), true);
    for (const width of [393, 320]) {
      await page.setViewportSize({ width, height: 700 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      const sizes = await page.locator('input, select, button, .event-actions a').evaluateAll(nodes => nodes.filter(n => n.getBoundingClientRect().width > 0).map(n => ({ name: n.textContent || n.id, height: n.getBoundingClientRect().height })));
      assert(sizes.every(size => size.height >= 44), JSON.stringify(sizes));
    }
    await page.addStyleTag({ content: 'html { font-size: 125%; }' });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.setViewportSize({ width: 1440, height: 1000 });
    assert.equal(await page.locator('#results').isVisible(), true);
    assert.equal(await page.locator('#map-panel').isVisible(), true);
    const listBox = await page.locator('#results').boundingBox();
    const mapBox = await page.locator('#map-panel').boundingBox();
    assert(mapBox.x > listBox.x + listBox.width);
  }, { mobile: true });
});

test('filters combine, announce empty results and reset to all season dates', async () => {
  await app(async page => {
    await page.waitForSelector('.event-card');
    await page.locator('#search').fill('vanocni');
    await page.waitForFunction(() => document.querySelectorAll('.event-card').length === 1);
    assert.equal(await page.locator('.event-card').getAttribute('data-id'), 'fixture-b');
    await page.locator('#town').selectOption('Říčany');
    await page.waitForSelector('.empty-state');
    assert.match(await page.locator('.empty-state').innerText(), /Žádná akce/);
    await page.getByRole('button', { name: 'Zrušit filtry', exact: true }).click();
    await page.waitForFunction(() => document.querySelectorAll('.event-card').length === 3);
    await page.locator('#category').selectOption('strom');
    await page.waitForFunction(() => document.querySelectorAll('.event-card').length === 1);
    assert.equal(await page.locator('.event-card').getAttribute('data-id'), 'fixture-a');
    await page.getByRole('button', { name: 'Zrušit filtry', exact: true }).click();
    await page.clock.setFixedTime(new Date('2026-11-27T23:30:00Z'));
    await page.locator('#period').selectOption('today');
    await page.waitForFunction(() => document.querySelectorAll('.event-card').length === 1);
    assert.equal(await page.locator('.event-card').getAttribute('data-id'), 'fixture-b');
    await page.locator('#period').selectOption('weekend');
    assert.match(await page.locator('#result-count').innerText(), /28\. 11\./);
    await page.locator('#search').press('Enter');
    assert.equal(await page.locator('#period').inputValue(), 'weekend');
  });
});

test('season list loads chronologically with honest metadata and safe text', async () => {
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card', { timeout: 3000 });
    assert.deepEqual(await page.locator('.event-card').evaluateAll(cards => cards.map(c => c.dataset.id)), ['fixture-a', 'fixture-b', 'fixture-c']);
    assert.equal(await page.locator('#period').inputValue(), 'all');
    assert.match(await page.locator('[data-id="fixture-a"]').innerText(), /Čas bude upřesněn/);
    assert.match(await page.locator('[data-id="fixture-b"]').innerText(), /150 Kč/);
    assert.match(await page.locator('[data-id="fixture-b"]').innerText(), /Dospělí/);
    assert.match(await page.locator('[data-id="fixture-c"]').innerText(), /Senioři/);
    assert.equal(await page.locator('.event-card img, .event-card script').count(), 0);
    assert.equal(await page.locator('a[href^="javascript:"]').count(), 0);
    assert.equal(await page.locator('.event-card').first().locator('a.source-link').getAttribute('href'), 'https://example.cz/strom');
    assert.match(await page.locator('.event-card').first().innerText(), /Ověřeno 12\. 11\. 2026/);
    assert.deepEqual(errors, []);
  });
});

test('review screenshots use synthetic display content and mobile map stays lazy until requested', async () => {
  const displayFixture = { ...fixture, events: fixture.events.map(event => event.id === 'fixture-c' ? { ...event, title: 'Adventní setkání pro seniory', description: 'Testovací předvánoční posezení v sousedském klubu.', sourceUrl: 'https://example.cz/setkani' } : event) };
  for (const mobile of [false, true]) {
    await app(async page => {
      await page.waitForSelector('.event-card');
      if (mobile) assert.equal(await page.locator('#map.leaflet-container').count(), 0);
      else await page.waitForSelector('#map .leaflet-interactive');
      await page.screenshot({ path: fileURLToPath(new URL(`./${mobile ? 'mobile' : 'desktop'}-fixture.png`, import.meta.url)), fullPage: false });
    }, { data: displayFixture, mobile });
  }
});
