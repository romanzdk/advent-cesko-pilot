import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
const screenshotPath = name => join(process.env.TMPDIR || join(homedir(), '.hermes/cache/scratch'), name);
import { chromium } from 'playwright';

// Synthetic public fixture only: never load the parent's live events.json.
export const fixture = {
  schemaVersion: 1, generatedAt: '2026-11-12T10:00:00Z', season: 2026, region: 'Beroun a okolí', events: [
    { id: 'fixture-b', title: 'Vánoční dílna', town: 'Beroun', venue: 'Klub', date: '2026-11-28', endDate: null, startTime: '16:00', endTime: null, category: 'tvoreni', price: '150 Kč', registration: 'Nutná rezervace', registrationUrl: 'https://example.cz/rezervace', description: 'Testovací dílna adventních věnců.', notes: ['Kapacita je omezená.'], audience: 'dospělí', status: 'confirmed', verifiedAt: '2026-11-12T10:00:00Z', sourceUrl: 'https://example.cz/dilna', location: { lat: 49.964, lon: 14.073, precision: 'town', label: 'Beroun', sourceUrl: 'https://example.cz/poloha' } },
    { id: 'fixture-a', title: 'Rozsvícení stromu', town: 'Říčany', venue: 'Náměstí', date: '2026-11-20', endDate: null, startTime: null, endTime: null, category: 'strom', price: null, registration: null, registrationUrl: null, description: 'Testovací slavnost.', notes: ['Přesný začátek zatím není uveden.'], audience: 'všichni', status: 'time-unconfirmed', verifiedAt: '2026-11-12T10:00:00Z', sourceUrl: 'https://example.cz/strom', location: { lat: 49.99, lon: 14.655, precision: 'venue', label: 'Náměstí', sourceUrl: 'https://example.cz/poloha' } },
    { id: 'fixture-c', title: '<img src=x onerror=alert(1)> Adventní setkání', town: 'Beroun', venue: 'Klub', date: '2026-12-05', endDate: null, startTime: '14:00', endTime: '17:00', category: 'setkani', price: 'Zdarma', registration: null, registrationUrl: 'javascript:alert(1)', description: '<script>window.injected=true</script>', notes: [], audience: 'senioři / omezené zaměření', status: 'confirmed', verifiedAt: '2026-11-12T10:00:00Z', sourceUrl: 'javascript:alert(1)', location: { lat: 49.964, lon: 14.073, precision: 'town', label: 'Beroun', sourceUrl: 'https://example.cz/poloha' } }
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
    let path = new URL(req.url, 'http://local').pathname.replace(/^\/advent-cesko-pilot\//, '/');
    if (path === '/') path = '/index.html';
    // An explicit asset allowlist prevents accidentally reading live data.
    if (!/^\/(index\.html|app\.js|helpers\.js|feedback\.js|feedback-helpers\.js|styles\.css|favicon\.svg|vendor\/leaflet\.(js|css))$/.test(path)) { res.writeHead(404).end(); return; }
    try {
      const data = await readFile(new URL(`../site${path}`, import.meta.url));
      res.setHeader('Content-Type', path.endsWith('.js') ? 'text/javascript' : path.endsWith('.css') ? 'text/css' : path.endsWith('.svg') ? 'image/svg+xml' : 'text/html; charset=utf-8');
      res.setHeader('X-Content-Type-Options', 'nosniff');
      res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://tile.openstreetmap.org; connect-src 'self' https://api.github.com; object-src 'none'; base-uri 'self'");
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
async function app(run, { data = fixture, base = '/advent-cesko-pilot/', mobile = false, responseStatus = 200, delay = 0, libraryFail = false, coverage = coverageFixture, coverageStatus = 200, coveragePending = false, javaScriptEnabled = true, geoMock = false } = {}) {
  const context = await browser.newContext({ viewport: mobile ? { width: 393, height: 852 } : { width: 1440, height: 1000 }, timezoneId: 'America/Los_Angeles', hasTouch: mobile, javaScriptEnabled });
  try {
    if (geoMock) await context.addInitScript(installGeoMock);
    const page = await context.newPage();
    await context.route('https://api.github.com/**', route => route.fulfill({ status: 200, contentType: 'application/json', body: '[]', headers: { 'access-control-allow-origin': '*' } }));
    await context.route('https://github.com/**', route => route.fulfill({ status: 200, contentType: 'text/html', body: '<title>Draft interception fixture</title>' }));
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

// Mocked GPS only; no hardware permission or real location is used.
function installGeoMock() {
    window.geoCalls = [];
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition(success, failure, options) { window.geoCalls.push({ success, failure, options }); } } });
    window.storageWrites = [];
    Storage.prototype.setItem = (...args) => window.storageWrites.push(args);
}
async function mockLocation(page) { await page.evaluate(installGeoMock); }
async function geoSuccess(page, index = 0) {
  await page.evaluate(index => window.geoCalls[index].success({ coords: { latitude: 49.964, longitude: 14.073, accuracy: 30 } }), index);
}
const permalinkFixture = { ...fixture, events: fixture.events.map(event => ({ ...event, id: event.id.replace('fixture-', 'e-') })) };
test('permalink titles are real safe links; initial deep link selects, focuses and scrolls after loading', async () => {
  for (const mobile of [false, true]) await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    const target = page.locator('[data-id="e-c"]');
    assert.equal(await target.locator('h3 a').count(), 1);
    assert.equal(await target.locator('h3 a').getAttribute('href'), `${origin}/advent-cesko-pilot/#akce=e-c`);
    assert.equal(await target.locator('h3 a').textContent(), permalinkFixture.events[2].title);
    assert.equal(await target.locator('h3 img').count(), 0);
    await page.waitForSelector('[data-id="e-c"].selected', { timeout:3000 });
    assert.equal(await target.evaluate(n => n === document.activeElement), true);
    assert.equal(await page.locator('#results').isVisible(), true);
    const box = await target.boundingBox();
    assert(box.y >= 0 && box.y < (await page.viewportSize()).height - 100, JSON.stringify(box));
    assert.equal(await page.evaluate(() => window.geoCalls.length), 0);
    assert.deepEqual(errors, []);
  }, { data:permalinkFixture, base:'/advent-cesko-pilot/?query=secret&lat=49.123#akce=e-c', delay:300, mobile, geoMock:true });
});

test('permalink navigation handles title clicks, hash changes and history without reloading or rerendering visible cards', async () => {
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    await page.evaluate(() => { window.sameDocument = true; window.originalCard = document.querySelector('[data-id="e-b"]'); });
    const requests = [];
    page.on('request', request => requests.push(request.url()));
    const target = page.locator('[data-id="e-b"]');
    await target.locator('h3 a').focus();
    await target.locator('h3 a').press('Enter');
    await page.waitForSelector('[data-id="e-b"].selected', {timeout:3000});
    assert.equal(new URL(page.url()).hash, '#akce=e-b');
    assert.equal(await target.evaluate(n => n === window.originalCard && n === document.activeElement), true);
    await page.evaluate(() => { location.hash = 'akce=e-a'; });
    await page.waitForSelector('[data-id="e-a"].selected', {timeout:3000});
    await page.goBack();
    await page.waitForSelector('[data-id="e-b"].selected', {timeout:3000});
    await page.goBack();
    await page.waitForFunction(() => document.querySelectorAll('.event-card.selected').length === 0, null, {timeout:3000});
    await page.goForward();
    await page.waitForSelector('[data-id="e-b"].selected', {timeout:3000});
    await target.locator('h3 a').click(); // Same fragment still focuses the card.
    assert.equal(await target.evaluate(n => n === document.activeElement), true);
    assert.equal(await page.evaluate(() => window.sameDocument), true);
    assert.deepEqual(requests, []);
    assert.deepEqual(errors, []);
  }, {data:permalinkFixture, mobile:true, base:'/advent-cesko-pilot/?query=private'});
});

test('permalink reveals a filtered target, clears only incompatible filters and fences pending GPS', async () => {
  const data = {...regionalFixture,events:regionalFixture.events.map(event => ({...event,id:event.id.replace('fixture-','e-')}))};
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    await page.locator('#locate-user').click();
    await geoSuccess(page);
    await page.locator('#nearby-radius').selectOption('25');
    await page.locator('#search').fill('dilna');
    await page.locator('#region').selectOption('Plzeňský kraj');
    await page.locator('#town').fill('Plasy');
    await page.locator('#category').selectOption('tvoreni');
    await page.locator('#period').selectOption('custom');
    await page.locator('#date-from').fill('2026-12-05');
    await page.locator('#date-to').fill('2026-11-20');
    await page.locator('#show-map').click();
    await page.evaluate(() => { location.hash = 'akce=e-a'; });
    await page.waitForSelector('[data-id="e-a"].selected', {timeout:3000});
    assert.equal(await page.locator('#results').isVisible(), true);
    for (const id of ['search','region','town','category','date-from','date-to']) assert.equal(await page.locator(`#${id}`).inputValue(), '');
    assert.equal(await page.locator('#period').inputValue(), 'all');
    assert.equal(await page.locator('#nearby-options').isVisible(), false);
    assert.equal(await page.locator('[data-id="e-a"]').evaluate(n => n === document.activeElement), true);
    await page.locator('#locate-user').click(); // A pending callback must not undo navigation.
    await page.evaluate(() => { location.hash = 'akce=e-b'; });
    await page.waitForSelector('[data-id="e-b"].selected', {timeout:3000});
    await geoSuccess(page, 1);
    assert.equal(await page.locator('#nearby-options').isVisible(), false);
    assert.equal(await page.locator('#show-list').getAttribute('aria-pressed'), 'true');
    await page.locator('#search').fill('dilna');
    await page.locator('#region').selectOption('Plzeňský kraj');
    await page.locator('#category').selectOption('tvoreni');
    await page.locator('#town').fill('pla');
    await page.locator('[data-id="e-b"] h3 a').click();
    for (const [id,value] of Object.entries({search:'dilna',region:'Plzeňský kraj',category:'tvoreni',town:'pla'})) assert.equal(await page.locator(`#${id}`).inputValue(), value);
    assert.deepEqual(errors, []);
  }, {data,mobile:true,geoMock:true});
});

test('permalink missing or malformed IDs show an honest non-destructive message and safe usable catalogue', async () => {
  for (const hash of ['#akce=e-removed', '#akce=%65-a', '#akce=<img src=x onerror=window.injected=true>', '#akce=e-a&lat=49.123']) await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    assert.equal(await page.locator('#permalink-status').count(), 1);
    assert.match(await page.locator('#permalink-status').innerText(), /není platný|není v aktuálním přehledu/);
    assert.equal(await page.locator('.event-card').count(), 3);
    assert.equal(await page.locator('.event-card.selected').count(), 0);
    await page.locator('#search').fill('dilna');
    const requests = [];
    page.on('request', request => requests.push(request.url()));
    await page.evaluate(() => { location.hash = 'akce=e-unknown'; });
    await page.waitForFunction(() => document.getElementById('permalink-status').textContent.includes('není v aktuálním'), null, {timeout:3000});
    assert.equal(await page.locator('#search').inputValue(), 'dilna');
    assert.equal(await page.locator('#search').evaluate(n => n === document.activeElement), true);
    assert.equal(await page.locator('.event-card').count(), 1);
    assert.equal(await page.locator('#permalink-status img, #permalink-status script').count(), 0);
    assert.equal(await page.evaluate(() => window.injected), undefined);
    await page.evaluate(() => { location.hash = 'akce=e-a'; });
    await page.waitForSelector('[data-id="e-a"].selected', {timeout:3000});
    assert.equal(await page.locator('#permalink-status').isVisible(), false);
    await page.evaluate(() => { location.hash = 'results'; });
    await page.waitForFunction(() => !document.querySelector('.event-card.selected'), null, {timeout:3000});
    assert.equal(await page.locator('#permalink-status').isVisible(), false);
    assert.deepEqual(requests, []);
    assert.deepEqual(errors, []);
  }, {data:permalinkFixture,mobile:true,base:`/${hash}`});
});

test('sharing copies one canonical own-site link from a trusted click without navigation, filters or source queries', async () => {
  const data = {...permalinkFixture, events:permalinkFixture.events.map(event => ({...event, title:`Upravený název ${event.id}`,sourceUrl:'https://organizer.example/event?token=source-secret'}))};
  for (const base of ['/?lat=49.123&lon=14.123', '/advent-cesko-pilot/?query=private']) await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    const target = page.locator('[data-id="e-b"]'), button = target.getByRole('button',{name:'Sdílet: Upravený název e-b',exact:true});
    assert.equal(await button.count(), 1);
    assert.equal(await button.innerText(), 'Sdílet');
    await page.evaluate(() => {
      window.copies = [];
      Object.defineProperty(navigator,'share',{configurable:true,value:undefined});
      Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async value => {window.copies.push(value);}}});
    });
    await button.evaluate(n => n.click());
    assert.deepEqual(await page.evaluate(() => window.copies), []);
    await page.locator('#category').selectOption('tvoreni');
    const share = page.locator('[data-id="e-b"] .share-button');
    await share.scrollIntoViewIfNeeded();
    const y = await page.evaluate(() => scrollY), url = page.url();
    const requests = [];
    page.on('request', request => requests.push(request.url()));
    await share.click();
    const expected = `${origin}${new URL(origin + base).pathname}#akce=e-b`;
    assert.deepEqual(await page.evaluate(() => window.copies), [expected]);
    assert.match(await target.locator('.share-status').innerText(), /Odkaz zkopírován/);
    assert.equal(await target.locator('h3 a').getAttribute('href'), expected);
    assert.equal(page.url(), url);
    assert.equal(await page.evaluate(() => scrollY), y);
    assert.equal(await page.locator('#category').inputValue(), 'tvoreni');
    assert.equal(await share.evaluate(n => n === document.activeElement), true);
    assert.equal(await page.evaluate(() => window.geoCalls.length), 0);
    assert.deepEqual(requests, []);
    assert.deepEqual(errors, []);
  }, {data,mobile:true,base,geoMock:true});
});

test('sharing prefers native share in the trusted activation with only the own-site URL and event title', async () => {
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    await page.evaluate(() => {
      window.shares = []; window.copies = [];
      Object.defineProperty(navigator,'share',{configurable:true,value:async data => {window.shares.push({data,active:navigator.userActivation.isActive});}});
      Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text => window.copies.push(text)}});
    });
    const card = page.locator('[data-id="e-c"]'), button = card.locator('.share-button');
    await button.click();
    assert.deepEqual(await page.evaluate(() => window.shares), [{data:{title:permalinkFixture.events[2].title,url:`${origin}/advent-cesko-pilot/#akce=e-c`},active:true}]);
    assert.deepEqual(await page.evaluate(() => window.copies), []);
    assert.match(await card.locator('.share-status').innerText(), /předán ke sdílení/);
    assert.equal(new URL(page.url()).hash, '');
    assert.deepEqual(errors, []);
  }, {data:permalinkFixture,mobile:true});
});

test('sharing native cancellation is quiet and never falls through to clipboard or claims a copy', async () => {
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    await page.evaluate(() => {
      window.copies = [];
      Object.defineProperty(navigator,'share',{configurable:true,value:undefined});
      Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text => window.copies.push(text)}});
    });
    const card = page.locator('[data-id="e-b"]');
    await card.locator('.share-button').click();
    assert.equal(await card.locator('.share-status').isVisible(), true);
    await page.evaluate(() => Object.defineProperty(navigator,'share',{configurable:true,value:async () => {throw new DOMException('Cancelled','AbortError');}}));
    await card.locator('.share-button').click();
    assert.equal(await card.locator('.share-status').isVisible(), false);
    assert.equal(await page.evaluate(() => window.copies.length), 1);
    assert.deepEqual(errors, []);
  }, {data:permalinkFixture,mobile:true});
});

test('sharing denied or unavailable APIs expose a real selectable own-site URL, never a false copied result', async () => {
  for (const failure of ['clipboard-denied','clipboard-missing','clipboard-abort','native-denied','native-sync']) await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    await page.evaluate(failure => {
      window.copies = [];
      const reject = () => {throw new DOMException('Denied',failure === 'clipboard-abort' ? 'AbortError' : 'NotAllowedError');};
      Object.defineProperty(navigator,'share',{configurable:true,value:failure === 'native-sync' ? reject : failure === 'native-denied' ? async () => reject() : undefined});
      Object.defineProperty(navigator,'clipboard',{configurable:true,value:failure === 'clipboard-missing' ? undefined : {writeText:async () => {window.copies.push('attempt');reject();}}});
    }, failure);
    const card = page.locator('[data-id="e-b"]');
    await card.locator('.share-button').click();
    assert.equal(await card.locator('.share-status a').count(), 1);
    const link = card.locator('.share-status a'), expected = `${origin}/advent-cesko-pilot/#akce=e-b`;
    assert.equal(await link.getAttribute('href'), expected);
    assert.equal(await link.textContent(), expected);
    assert.match(await card.locator('.share-status').innerText(), /Zkopírujte odkaz ručně/);
    assert.doesNotMatch(await card.locator('.share-status').innerText(), /zkopírován|předán ke sdílení/);
    assert.equal(await card.locator('.share-button').isEnabled(), true);
    if (failure.startsWith('native-')) assert.deepEqual(await page.evaluate(() => window.copies), []);
    await page.evaluate(() => { window.sameDocument = true; });
    await link.click();
    await page.waitForSelector('[data-id="e-b"].selected', {timeout:3000});
    assert.equal(await page.evaluate(() => window.sameDocument), true);
    assert.deepEqual(errors, []);
  }, {data:permalinkFixture,mobile:true,base:'/advent-cesko-pilot/?query=secret&lat=49.123'});
});

test('sharing keeps only the latest per-card feedback active even when promises finish out of order', async () => {
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    await page.evaluate(() => {
      window.pendingCopies = [];
      Object.defineProperty(navigator,'share',{configurable:true,value:undefined});
      Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:() => new Promise((resolve,reject) => window.pendingCopies.push({resolve,reject}))}});
    });
    const a = page.locator('[data-id="e-a"]'), b = page.locator('[data-id="e-b"]');
    await a.locator('.share-button').click();
    await b.locator('.share-button').click();
    await page.evaluate(() => window.pendingCopies[1].resolve());
    assert.equal(await b.locator('.share-status').isVisible(), true);
    await page.evaluate(() => window.pendingCopies[0].resolve());
    assert.equal(await a.locator('.share-status').isVisible(), false);
    assert.equal(await page.locator('.share-status:not([hidden])').count(), 1);
    await a.locator('.share-button').click();
    assert.equal(await b.locator('.share-status').isVisible(), false);
    await page.evaluate(() => window.pendingCopies[2].reject(new Error('denied')));
    assert.equal(await a.locator('.share-status a').count(), 1);
    await page.evaluate(() => Object.defineProperty(navigator,'share',{configurable:true,value:async () => {throw new DOMException('cancel','AbortError');}}));
    await b.locator('.share-button').click();
    assert.equal(await page.locator('.share-status:not([hidden])').count(), 0);
    assert.deepEqual(errors, []);
  }, {data:permalinkFixture,mobile:true});
});

test('sharing long links and event titles fit 393px and 320px with touch-sized selectable fallback', async () => {
  const id = `e-${'a'.repeat(180)}`;
  const data = {...fixture,events:[{...fixture.events[0],id,title:'Vánoční dílna'}]};
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    await page.evaluate(() => {
      Object.defineProperty(navigator,'share',{configurable:true,value:undefined});
      Object.defineProperty(navigator,'clipboard',{configurable:true,value:undefined});
    });
    await page.locator('.share-button').click();
    for (const width of [393,320]) {
      await page.setViewportSize({width,height:852});
      for (const selector of ['.event-permalink','.share-button','.share-url']) {
        const node = page.locator(selector), box = await node.boundingBox();
        assert(box && box.height >= 44 && box.width >= 44 && box.x >= 0 && box.x + box.width <= width, `${selector}: ${JSON.stringify(box)}`);
      }
      assert.equal(await page.locator('.share-url').evaluate(n => getComputedStyle(n).userSelect), 'all');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    }
    await page.locator('.share-url').focus();
    assert.equal(await page.locator('.share-url').evaluate(n => n === document.activeElement), true);
    await page.addStyleTag({content:'html { font-size:125%; }'});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.locator('.event-card').screenshot({path:screenshotPath('event-permalink-share-mobile-fixture.png')});
    assert.deepEqual(errors, []);
  }, {data,mobile:true});
});

test('permalink uses the latest hash while data is pending and survives an honest load error and retry', async () => {
  await app(async (page, errors) => {
    assert.equal(await page.locator('#results').getAttribute('aria-busy'), 'true');
    await page.evaluate(() => { location.hash = 'akce=e-b'; });
    await page.waitForSelector('[data-id="e-b"].selected', {timeout:3000});
    assert.equal(await page.locator('.event-card.selected').count(), 1);
    assert.deepEqual(errors, []);
  }, {data:permalinkFixture,mobile:true,base:'/#akce=e-a',delay:700});
  await app(async (page, errors) => {
    await page.waitForSelector('.load-error');
    assert.equal(await page.locator('#permalink-status').isVisible(), false);
    await page.evaluate(() => { location.hash = 'akce=e-c'; });
    assert.equal(await page.locator('.load-error button').isEnabled(), true);
    await page.route('**/events.json', route => route.fulfill({contentType:'application/json',body:JSON.stringify(permalinkFixture)}));
    await page.locator('.load-error button').click();
    await page.waitForSelector('[data-id="e-c"].selected', {timeout:3000});
    assert.equal(await page.locator('[data-id="e-c"]').evaluate(n => n === document.activeElement), true);
    assert.deepEqual(errors, []);
  }, {data:permalinkFixture,mobile:true,base:'/#akce=e-a',responseStatus:503});
});

test('permalink does not revive a removed or out-of-season event and ordinary filtering does not steal focus', async () => {
  await app(async page => {
    await page.waitForSelector('.event-card');
    assert.match(await page.locator('#permalink-status').innerText(), /není v aktuálním přehledu/);
    assert.equal(await page.locator('[data-id="e-old"]').count(), 0);
    await page.evaluate(() => { location.hash = 'akce=e-b'; });
    await page.waitForSelector('[data-id="e-b"].selected', {timeout:3000});
    await page.locator('#search').fill('strom');
    assert.equal(await page.locator('#search').evaluate(n => n === document.activeElement), true);
    assert.equal(await page.locator('.event-card').getAttribute('data-id'), 'e-a');
  }, {data:{...permalinkFixture,events:[...permalinkFixture.events,{...fixture.events[0],id:'e-old',date:'2025-11-28'}]},mobile:true,base:'/#akce=e-old'});
});

test('permalink data IDs with trailing newlines are rejected instead of silently repaired into a different link', async () => {
  await app(async page => {
    await page.waitForFunction(() => document.querySelector('.event-card, .load-error'), null, {timeout:3000});
    assert.equal(await page.locator('.load-error').count(), 1);
    assert.equal(await page.locator('.event-card').count(), 0);
    assert.equal(await page.locator('.load-error button').isEnabled(), true);
  }, {data:{...fixture,events:[{...fixture.events[0],id:'e-a\n'}]},mobile:true,base:'/#akce=e-a'});
});

test('permalink canonical base is the static app directory even when opened through index.html', async () => {
  await app(async page => {
    await page.waitForSelector('.event-card');
    const link = page.locator('[data-id="e-b"] h3 a');
    assert.equal(await link.getAttribute('href'), `${origin}/advent-cesko-pilot/#akce=e-b`);
    await page.evaluate(() => { window.sameDocument = true; });
    await link.click();
    await page.waitForSelector('[data-id="e-b"].selected', {timeout:3000});
    assert.equal(await page.evaluate(() => window.sameDocument), true);
  }, {data:permalinkFixture,mobile:true,base:'/advent-cesko-pilot/index.html?query=private'});
});

test('permalink recovers a partially entered native date instead of leaving the target hidden', async () => {
  await app(async page => {
    await page.waitForSelector('.event-card');
    await page.locator('#period').selectOption('custom');
    const from = page.locator('#date-from');
    await from.fill('2026-11-28');
    await from.press('Backspace');
    assert.equal(await from.evaluate(n => n.validity.badInput), true, 'native partially entered date fixture');
    assert.equal(await page.locator('.event-card').count(), 0);
    await page.evaluate(() => { location.hash = 'akce=e-b'; });
    await page.waitForSelector('[data-id="e-b"].selected', {timeout:3000});
    assert.equal(await page.locator('#period').inputValue(), 'all');
    assert.equal(await page.locator('#date-range-error').isVisible(), false);
  }, {data:permalinkFixture,mobile:true});
});

test('town autocomplete filters partial text without diacritics, survives edits and selects canonical local names', async () => {
  for (const mobile of [false, true]) await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    const town = page.getByRole('combobox', {name:'Obec',exact:true});
    assert.equal(await town.count(), 1);
    assert.equal(await town.getAttribute('id'), 'town');
    assert.equal(await town.getAttribute('name'), 'town');
    assert.equal(await town.getAttribute('placeholder'), 'Začněte psát obec…');
    assert.equal(await town.getAttribute('aria-controls'), 'town-options');
    await town.fill('ric');
    assert.equal(await town.inputValue(), 'ric');
    assert.equal(await page.locator('.event-card').getAttribute('data-id'), 'fixture-a');
    assert.equal(await town.getAttribute('aria-expanded'), 'true');
    assert.deepEqual(await page.locator('#town-options').getByRole('option').allTextContents(), ['Říčany']);
    await town.fill('ican');
    await page.locator('#category').selectOption('strom');
    assert.equal(await town.inputValue(), 'ican');
    await town.click();
    await page.getByRole('option', {name:'Říčany',exact:true}).click();
    assert.equal(await town.inputValue(), 'Říčany');
    assert.equal(await town.getAttribute('aria-expanded'), 'false');
    assert.equal(await town.evaluate(n => n === document.activeElement), true);
    assert.deepEqual(errors, []);
  }, {mobile});
});

test('town keyboard navigation keeps input focus, selects with Enter and dismisses without changing text', async () => {
  await app(async page => {
    await page.waitForSelector('.event-card');
    const town = page.locator('#town'), options = page.locator('#town-options [role=option]');
    await town.focus();
    await town.press('ArrowDown');
    assert.equal(await town.getAttribute('aria-activedescendant'), await options.first().getAttribute('id'));
    assert.equal(await options.first().getAttribute('aria-selected'), 'true');
    await town.press('ArrowDown');
    assert.equal(await town.getAttribute('aria-activedescendant'), await options.nth(1).getAttribute('id'));
    await town.press('ArrowUp');
    assert.equal(await town.evaluate(n => n === document.activeElement), true);
    await town.press('Enter');
    assert.equal(await town.inputValue(), 'Beroun');
    assert.equal(await town.getAttribute('aria-expanded'), 'false');
    assert.equal(await town.getAttribute('aria-activedescendant'), null);
    await town.fill('ric');
    await town.press('ArrowUp');
    await town.press('Escape');
    assert.equal(await town.inputValue(), 'ric');
    assert.equal(await town.getAttribute('aria-expanded'), 'false');
    await town.press('ArrowDown');
    await town.press('Tab');
    assert.equal(await town.inputValue(), 'ric');
    assert.equal(await town.getAttribute('aria-expanded'), 'false');
    assert.equal(await town.evaluate(n => n === document.activeElement), false);
    await town.click();
    await page.locator('h1').click();
    assert.equal(await town.getAttribute('aria-expanded'), 'false');
    await town.focus();
    await page.locator('#search').focus();
    assert.equal(await town.getAttribute('aria-expanded'), 'false');
  });
});

test('town region changes preserve matching partial text and clear only incompatible towns', async () => {
  await app(async page => {
    await page.waitForSelector('.event-card');
    await page.locator('#search').fill('dilna');
    await page.locator('#category').selectOption('tvoreni');
    await page.locator('#period').selectOption('custom');
    await page.locator('#date-from').fill('2026-11-28');
    await page.locator('#town').fill('pla');
    await page.locator('#region').selectOption('Plzeňský kraj');
    assert.equal(await page.locator('#town').inputValue(), 'pla');
    await page.locator('#region').selectOption('Liberecký kraj');
    assert.equal(await page.locator('#town').inputValue(), '');
    for (const [id,value] of Object.entries({search:'dilna',category:'tvoreni',period:'custom','date-from':'2026-11-28'})) assert.equal(await page.locator(`#${id}`).inputValue(), value);
    await page.locator('#town').fill('zzz');
    await page.locator('#search').fill('jiný');
    assert.equal(await page.locator('#town').inputValue(), 'zzz');
    await page.locator('#filters button[type=reset]').click();
    assert.equal(await page.locator('#search').inputValue(), '');
    assert.equal(await page.locator('#town').inputValue(), '');
  }, {data:regionalFixture,mobile:true});
});

test('town clear is labelled and touch-sized, restores focus without scroll and preserves every other filter', async () => {
  for (const mobile of [false,true]) await app(async page => {
    await page.waitForSelector('.event-card');
    await page.locator('#locate-user').click();
    await geoSuccess(page);
    await page.locator('#nearby-radius').selectOption('25');
    await page.locator('#region').selectOption('Plzeňský kraj');
    await page.locator('#category').selectOption('tvoreni');
    await page.locator('#period').selectOption('custom');
    await page.locator('#date-from').fill('2026-11-28');
    await page.locator('#date-to').fill('2026-11-29');
    await page.locator('#search').fill('dilna');
    const clear = page.locator('#clear-town');
    assert.equal(await clear.count(), 1);
    assert.equal(await clear.getAttribute('aria-label'), 'Vymazat obec');
    assert.equal(await clear.isVisible(), false);
    await page.locator('#town').fill('pla');
    await page.locator('#town').press('Escape');
    const box = await clear.boundingBox();
    assert(box.width >= 44 && box.height >= 44);
    const y = await page.evaluate(() => scrollY);
    await clear.click();
    assert.equal(await page.locator('#town').inputValue(), '');
    assert.equal(await clear.isVisible(), false);
    assert.equal(await page.locator('#town').evaluate(n => n === document.activeElement), true);
    assert.equal(await page.evaluate(() => scrollY), y);
    for (const [id,value] of Object.entries({search:'dilna',region:'Plzeňský kraj',category:'tvoreni',period:'custom','date-from':'2026-11-28','date-to':'2026-11-29','nearby-radius':'25'})) assert.equal(await page.locator(`#${id}`).inputValue(), value);
    assert.equal(await page.locator('#clear-location').isVisible(), true);
  }, {data:regionalFixture,mobile,geoMock:true});
});

test('town mobile suggestions are bounded, scroll without selection, survive blur and render hostile town names as text', async () => {
  const hostile = 'Z <img src=x onerror=window.injected=true> Obec';
  const data = {...fixture,events:[hostile,'Beroun','Český Brod','Český Krumlov','Černošín','Humpolec','Jilemnice','Kuřim','Plasy','Rajhrad','Semily','Telč','Turnov','Říčany'].map((town,i) => ({...fixture.events[0],id:`town-${i}`,town,region:'Plzeňský kraj'}))};
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    const requests = [];
    page.on('request', request => requests.push(request.url()));
    const town = page.locator('#town'), list = page.locator('#town-options');
    for (const width of [393,320]) {
      await page.setViewportSize({width,height:852});
      await town.fill('');
      await town.click();
      assert.equal(await list.locator('[role=option]').count(), 8);
      const box = await list.boundingBox();
      assert(box.height <= 240 && box.x >= 0 && box.x + box.width <= width);
      assert.equal(await list.evaluate(n => n.scrollHeight > n.clientHeight), true);
      assert(Number.parseFloat(await town.evaluate(n => getComputedStyle(n).fontSize)) >= 16);
      assert((await town.boundingBox()).height >= 44);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    }
    await page.setViewportSize({width:393,height:852});
    await town.click();
    await page.screenshot({path:screenshotPath('town-autocomplete-mobile-fixture.png')});
    const box = await list.boundingBox(), x = box.x + box.width / 2, y = box.y + 180;
    const cdp = await page.context().newCDPSession(page);
    try {
      await cdp.send('Input.dispatchTouchEvent', {type:'touchStart',touchPoints:[{x,y}]});
      for (const delta of [20,50,90,130]) await cdp.send('Input.dispatchTouchEvent', {type:'touchMove',touchPoints:[{x,y:y-delta}]});
      await cdp.send('Input.dispatchTouchEvent', {type:'touchEnd',touchPoints:[]});
    } finally { await cdp.detach(); }
    assert.equal(await town.inputValue(), '');
    assert(await list.evaluate(n => n.scrollTop > 0), 'real touch gesture scrolls the list');
    assert.equal(await town.getAttribute('aria-expanded'), 'true');
    await town.fill('ric');
    await town.evaluate(n => n.blur());
    assert.equal(await list.isVisible(), true);
    await list.getByRole('option',{name:'Říčany',exact:true}).tap();
    assert.equal(await town.inputValue(), 'Říčany');
    assert.equal(await town.evaluate(n => n === document.activeElement), true);
    await town.fill('<img');
    assert.equal(await list.innerText(), hostile);
    assert.equal(await list.locator('img,script').count(), 0);
    await list.getByRole('option').tap();
    assert.equal(await town.inputValue(), hostile);
    assert.equal(await page.evaluate(() => window.injected), undefined);
    assert.deepEqual(requests, []);
    assert.deepEqual(await page.evaluate(() => window.storageWrites), []);
    assert.equal(await page.evaluate(() => window.geoCalls.length), 0);
    assert.deepEqual(errors, []);
  }, {data,mobile:true,geoMock:true});
});

test('location is gated by loaded events and trusted clicks without erasing fetch recovery', async () => {
  await app(async page => {
    await page.waitForSelector('.load-error');
    await mockLocation(page);
    assert.equal(await page.locator('#locate-user').isDisabled(), true);
    await page.locator('#locate-user').evaluate(n => n.dispatchEvent(new MouseEvent('click', { bubbles:true })));
    assert.equal(await page.locator('.load-error button').count(), 1);
    assert.equal(await page.evaluate(() => window.geoCalls.length), 0);
  }, { responseStatus:503 });
  await app(async page => {
    await page.waitForSelector('.event-card');
    await mockLocation(page);
    await page.locator('#locate-user').evaluate(n => n.click());
    assert.equal(await page.evaluate(() => window.geoCalls.length), 0);
    await page.locator('#locate-user').click();
    assert.equal(await page.evaluate(() => window.geoCalls.length), 1);
  });
});

test('nearby is opt-in, filters chronologically, keeps other filters and clears the separate user marker', async () => {
  for (const mobile of [false, true]) await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    const originalURL = page.url();
    assert.equal(await page.locator('#locate-user').count(), 1);
    assert.equal(await page.locator('#nearby-radius').isVisible(), false);
    assert.equal(await page.evaluate(() => window.geoCalls.length), 0);
    await page.locator('#locate-user').click();
    assert.equal(await page.locator('#locate-user').isDisabled(), true);
    assert.equal(await page.locator('#clear-location').isVisible(), true);
    assert.deepEqual(await page.evaluate(() => window.geoCalls[0].options), { timeout: 10000, maximumAge: 60000, enableHighAccuracy: false });
    await geoSuccess(page);
    await page.waitForSelector('.user-location-marker');
    assert.equal(await page.locator('#nearby-radius').inputValue(), '50');
    assert.deepEqual(await page.locator('.event-card').evaluateAll(nodes => nodes.map(n => n.dataset.id)), ['fixture-a', 'fixture-b', 'fixture-c']);
    assert.equal(await page.locator('#map-count').innerText(), '2 místa');
    if (mobile) assert.equal(await page.locator('#map-panel').isVisible(), true);
    await page.locator('#nearby-radius').selectOption('25');
    assert.equal(await page.locator('.event-card').count(), 2);
    assert.equal(await page.locator('.map-marker').count(), 1);
    assert.equal(await page.locator('.user-location-marker').count(), 1);
    assert.equal(await page.locator('#map .leaflet-overlay-pane svg g path').last().getAttribute('class'), 'user-location-marker');
    await page.locator('#category').selectOption('tvoreni');
    assert.equal(await page.locator('.event-card').count(), 1);
    await page.locator('#clear-location').click();
    assert.equal(await page.locator('.user-location-marker').count(), 0);
    assert.equal(await page.locator('#category').inputValue(), 'tvoreni');
    assert.equal(await page.locator('#nearby-radius').isVisible(), false);
    assert.equal(page.url(), originalURL);
    assert.deepEqual(await page.evaluate(() => window.storageWrites), []);
    assert.deepEqual(errors, []);
  }, { mobile, geoMock: true });
});

test('nearby failures are inline and retryable, invalid coordinates never filter and low accuracy is disclosed', async () => {
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    await mockLocation(page);
    for (const [code, text] of [[1, /nebylo povoleno/], [2, /není dostupná/], [3, /časový limit/]]) {
      await page.locator('#locate-user').click();
      await page.evaluate(code => window.geoCalls.at(-1).failure({ code }), code);
      assert.match(await page.locator('#location-status').innerText(), text);
      assert.equal(await page.locator('#locate-user').isEnabled(), true);
      assert.equal(await page.locator('.event-card').count(), 3);
    }
    for (const coords of [null, { latitude: null, longitude: 14, accuracy: 1 }, { latitude: 91, longitude: 14, accuracy: 1 }, { latitude: 49, longitude: 181, accuracy: 1 }, { latitude: 49, longitude: 14, accuracy: -1 }]) {
      await page.locator('#locate-user').click();
      await page.evaluate(coords => window.geoCalls.at(-1).success({ coords }), coords);
      assert.match(await page.locator('#location-status').innerText(), /není dostupná/);
      assert.equal(await page.locator('#nearby-radius').isVisible(), false);
    }
    await page.locator('#locate-user').click();
    await page.evaluate(() => window.geoCalls.at(-1).success({ coords: { latitude: NaN, longitude: 14, accuracy: 1 } }));
    assert.equal(await page.locator('#locate-user').isEnabled(), true);
    await page.locator('#locate-user').click();
    await page.evaluate(() => window.geoCalls.at(-1).success({ coords: { latitude: 49.964, longitude: 14.073, accuracy: 20000 } }));
    assert.match(await page.locator('#location-status').innerText(), /Nízká přesnost/);
    await page.locator('#clear-location').click();
    await page.evaluate(() => Object.defineProperty(navigator, 'geolocation', { configurable: true, value: undefined }));
    await page.locator('#locate-user').click();
    assert.match(await page.locator('#location-status').innerText(), /nepodporuje/);
    await page.evaluate(() => Object.defineProperty(window, 'isSecureContext', { configurable: true, value: false }));
    await page.locator('#locate-user').click();
    assert.match(await page.locator('#location-status').innerText(), /HTTPS/);
    assert.deepEqual(errors, []);
  });
});

test('nearby cancellation and global reset ignore late callbacks and bound a pending request', async () => {
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    await mockLocation(page);
    for (const selector of ['#clear-location', '#filters button[type=reset]']) {
      await page.locator('#locate-user').click();
      const index = await page.evaluate(() => window.geoCalls.length - 1);
      await page.locator(selector).click();
      await geoSuccess(page, index);
      assert.equal(await page.locator('#nearby-radius').isVisible(), false);
      assert.equal(await page.locator('.user-location-marker').count(), 0);
      assert.equal(await page.locator('#locate-user').isEnabled(), true);
    }
    await page.locator('#locate-user').click();
    await page.clock.runFor(10500);
    assert.equal(await page.locator('#locate-user').isEnabled(), true);
    assert.match(await page.locator('#location-status').innerText(), /časový limit/);
    await geoSuccess(page, 2);
    assert.equal(await page.locator('#nearby-radius').isVisible(), false);
    await page.locator('#locate-user').click();
    await geoSuccess(page, 3);
    await page.locator('#filters button[type=reset]').click();
    assert.equal(await page.locator('#nearby-radius').isVisible(), false);
    assert.equal(await page.locator('.user-location-marker').count(), 0);
    assert.deepEqual(errors, []);
  });
});

test('nearby list survives map failure and empty radius explains limited coverage', async () => {
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    await mockLocation(page);
    await page.locator('#locate-user').click();
    await geoSuccess(page);
    await page.waitForFunction(() => document.getElementById('location-status').textContent.includes('Mapu se nepodařilo'));
    assert.equal(await page.locator('#results').isVisible(), true);
    await page.locator('#nearby-radius').selectOption('25');
    assert.equal(await page.locator('.event-card').count(), 2);
    await page.locator('#category').selectOption('strom');
    assert.match(await page.locator('.empty-state').innerText(), /ve zvoleném okruhu a filtrech/);
    assert.match(await page.locator('.empty-state').innerText(), /neúplné pokrytí/);
    assert.deepEqual(errors, []);
  }, { mobile: true, libraryFail: true });
});

test('nearby secondary controls fit touch targets on narrow screens without changing the primary row', async () => {
  await app(async page => {
    await page.waitForSelector('.event-card');
    await mockLocation(page);
    assert.equal(await page.locator('#filters #locate-user').count(), 0);
    assert.equal(await page.locator('.geo-controls').evaluate(n => getComputedStyle(n).display), 'flex');
    await page.locator('#locate-user').click();
    await geoSuccess(page);
    for (const width of [393, 320]) {
      await page.setViewportSize({ width, height: 852 });
      for (const selector of ['#locate-user', '#nearby-radius', '#clear-location']) {
        const box = await page.locator(selector).boundingBox();
        assert(box && box.height >= 44 && box.x >= 0 && box.x + box.width <= width, selector);
      }
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    }
    assert.match(await page.locator('#location-hint').innerText(), /vzdušnou čarou.*střed obce.*Poloha se neukládá\. OpenStreetMap.*prohlížené oblasti\./);
    await page.setViewportSize({ width:393, height:1000 });
    await page.locator('.geo-controls').scrollIntoViewIfNeeded();
    await page.screenshot({ path:screenshotPath('nearby-mobile-fixture.png') });
  }, { mobile: true });
});

test('custom date range filters list and map inclusively and composes with other filters on desktop and mobile', async () => {
  const data = { ...fixture, events: [...fixture.events, { ...fixture.events[0], id: 'fixture-span', title: 'Vícedenní trhy', date: '2026-11-25', endDate: '2026-11-30', category: 'trhy' }] };
  for (const mobile of [false, true]) await app(async page => {
    await page.waitForSelector('.event-card');
    assert.equal(await page.locator('#date-range').isVisible(), false);
    await page.locator('#period').selectOption('custom');
    await page.locator('#date-from').fill('2026-11-28');
    await page.locator('#date-to').fill('2026-11-28');
    assert.deepEqual(await page.locator('.event-card').evaluateAll(nodes => nodes.map(n => n.dataset.id)), ['fixture-span', 'fixture-b']);
    assert.match(await page.locator('#result-count').innerText(), /28\. 11\. 2026/);
    await page.locator('#category').selectOption('tvoreni');
    assert.equal(await page.locator('.event-card').count(), 1);
    if (mobile) await page.locator('#show-map').click();
    await page.waitForSelector('#map .leaflet-interactive');
    assert.equal(await page.locator('#map .leaflet-interactive').count(), 1);
    await page.locator('#category').selectOption('');
    await page.locator('#period').selectOption('all');
    assert.equal(await page.locator('.event-card').count(), 4);
    assert.equal(await page.locator('#date-range').isVisible(), false);
    await page.locator('#period').selectOption('custom');
    assert.equal(await page.locator('.event-card').count(), 2);
    await page.locator('#filters button[type=reset]').click();
    assert.equal(await page.locator('.event-card').count(), 4);
    assert.equal(await page.locator('#date-from').inputValue(), '');
    assert.equal(await page.locator('#date-to').inputValue(), '');
    assert.equal(await page.locator('#date-range').isVisible(), false);
  }, { data, mobile });
});

test('invalid date ranges clear stale results and recover while allowing one-sided ranges', async () => {
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    await page.waitForSelector('#map .leaflet-interactive');
    await page.locator('#period').selectOption('custom');
    await page.locator('#date-from').fill('2026-12-05');
    await page.locator('#date-to').fill('2026-11-28');
    assert.equal(await page.locator('#date-range-error').isVisible(), true);
    assert.match(await page.locator('#date-range-error').innerText(), /Od.*Do/);
    assert.equal(await page.locator('.event-card').count(), 0);
    assert.equal(await page.locator('#map .leaflet-interactive').count(), 0);
    assert.match(await page.locator('#result-count').innerText(), /Opravte/);
    await page.locator('#date-to').fill('2026-12-05');
    assert.equal(await page.locator('.event-card').count(), 1);
    assert.equal(await page.locator('#date-range-error').isVisible(), false);
    await page.locator('#date-from').fill('');
    assert.equal(await page.locator('.event-card').count(), 3);
    await page.locator('#date-from').fill('2026-11-01');
    assert.match(await page.locator('#date-range-error').innerText(), /20\. 11\./);
    assert.equal(await page.locator('.event-card').count(), 0);
    await page.locator('#period').selectOption('all');
    assert.equal(await page.locator('.event-card').count(), 3);
    assert.equal(await page.locator('#date-range-error').isVisible(), false);
    assert.deepEqual(errors, []);
  });
});

test('custom date inputs remain usable on narrow screens and with enlarged text', async () => {
  await app(async page => {
    await page.waitForSelector('.event-card');
    await page.locator('#period').selectOption('custom');
    await page.locator('#date-from').fill('2026-11-28');
    await page.locator('#date-to').fill('2026-12-05');
    for (const width of [1440, 900, 393, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const id of ['date-from', 'date-to']) {
        const input = page.locator(`#${id}`), box = await input.boundingBox();
        assert(box.height >= 44 && box.x >= 0 && box.x + box.width <= width);
        assert(Number.parseFloat(await input.evaluate(n => getComputedStyle(n).fontSize)) >= 16);
        assert.equal(await input.getAttribute('min'), '2026-11-20');
        assert.equal(await input.getAttribute('max'), '2026-12-24');
      }
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      if (width === 393) await page.screenshot({ path: screenshotPath('date-range-mobile-fixture.png') });
      if (width === 1440) await page.screenshot({ path: screenshotPath('date-range-desktop-fixture.png') });
    }
    await page.locator('#date-range').evaluate(node => { for (const input of node.querySelectorAll('input')) input.style.fontSize = '24px'; });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert((await page.locator('#date-from').boundingBox()).width > 200);
  });
});

test('event dates distinguish weekends and holidays with text labels and start-date-only coloring', async () => {
  const data = { ...fixture, events:[...fixture.events, {...fixture.events[0],id:'weekday',date:'2026-11-27',endDate:'2026-11-30'}, {...fixture.events[0],id:'sunday',date:'2026-11-29'}, {...fixture.events[0],id:'holiday',date:'2026-12-24'}] };
  for (const mobile of [false,true]) await app(async page => {
    await page.waitForSelector('.event-card');
    const weekend=page.locator('[data-id="fixture-b"]'), holiday=page.locator('[data-id="holiday"]'), weekday=page.locator('[data-id="weekday"]');
    assert.equal(await weekend.locator('.date-rail.is-weekend').count(),1);
    assert.equal(await page.locator('[data-id="sunday"] .date-rail.is-weekend').count(),1);
    assert.equal(await holiday.locator('.date-rail.is-holiday').count(),1);
    assert.equal(await weekday.locator('.date-rail.is-weekend').count(),0);
    assert.equal(await weekend.locator('.day-badge').innerText(),'Víkend');
    assert.equal(await holiday.locator('.day-badge').innerText(),'Svátek · Štědrý den');
    assert.equal(await weekday.locator('.day-badge').count(),0);
    const colors=[];
    for (const c of [weekday,weekend,holiday]) colors.push(await c.locator('.date-rail').evaluate(n=>getComputedStyle(n).color));
    assert.equal(new Set(colors).size,3);
    assert.match(await holiday.locator('time').getAttribute('aria-label'),/Štědrý den/);
    assert.match(await weekend.locator('time').getAttribute('aria-label'),/Víkend/);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    if(mobile) await page.locator('#results').screenshot({path:screenshotPath('calendar-days-mobile-fixture.png')});
  },{data,mobile});
});

test('map markers use category colors, mixed places remain neutral and filtering recolors them', async () => {
  for (const mobile of [false, true]) await app(async page => {
    await page.waitForSelector('.event-card');
    if (mobile) await page.locator('#show-map').click();
    await page.waitForSelector('.map-marker');
    assert.equal(await page.locator('.map-marker[data-category=strom]').count(), 1);
    assert.equal(await page.locator('.map-marker[data-category=strom]').getAttribute('fill'), '#2f6b45');
    const mixed = page.locator('.map-marker[data-category=mixed]');
    assert.equal(await mixed.getAttribute('fill'), '#657168');
    assert.match(await mixed.getAttribute('aria-label'), /Více typů akcí/);
    assert.equal(await page.locator('#map-legend li').count(), 7);
    assert.match(await page.locator('#map-legend').innerText(), /Rozsvícení stromu.*Mikuláš.*Trhy a jarmarky/s);
    await page.locator('#category').selectOption('tvoreni');
    assert.equal(await page.locator('.map-marker').count(), 1);
    assert.equal(await page.locator('.map-marker').getAttribute('fill'), '#8054a3');
    assert.match(await page.locator('.map-marker').getAttribute('aria-label'), /Tvoření/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    if (mobile) await page.locator('.map-panel').screenshot({path:screenshotPath('category-map-mobile-fixture.png')});
  }, {mobile});
});

test('search clear button removes the entire query, preserves other filters and restores input focus', async () => {
  for (const mobile of [false, true]) await app(async page => {
    await page.waitForSelector('.event-card');
    const clear = page.locator('#clear-search');
    assert.equal(await clear.count(), 1);
    assert.equal(await clear.getAttribute('aria-label'), 'Vymazat hledání');
    assert.equal(await clear.isVisible(), false);
    await page.locator('#region').selectOption('Plzeňský kraj');
    await page.locator('#town').fill('Plasy');
    await page.locator('#category').selectOption('tvoreni');
    await page.locator('#period').selectOption('custom');
    await page.locator('#date-from').fill('2026-11-27');
    await page.locator('#date-to').fill('2026-11-29');
    await page.locator('#search').fill('celý neexistující dotaz');
    assert.equal(await page.locator('.event-card').count(), 0);
    assert.equal(await clear.isVisible(), true);
    const box = await clear.boundingBox();
    assert(box.width >= 44 && box.height >= 44);
    await clear.click();
    assert.equal(await page.locator('#search').inputValue(), '');
    assert.equal(await clear.isVisible(), false);
    assert.equal(await page.locator('#search').evaluate(n => n === document.activeElement), true);
    assert.equal(await page.locator('.event-card').count(), 1);
    for (const [id, value] of Object.entries({ region:'Plzeňský kraj', town:'Plasy', category:'tvoreni', period:'custom', 'date-from':'2026-11-27', 'date-to':'2026-11-29' })) assert.equal(await page.locator(`#${id}`).inputValue(), value);
    await page.locator('#search').fill('další dotaz');
    await clear.focus();
    await clear.press('Enter');
    assert.equal(await page.locator('#search').inputValue(), '');
    assert.equal(await page.locator('#search').evaluate(n => n === document.activeElement), true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  }, { data:regionalFixture, mobile });
});

test('personal origin story replaces the edition with a compact header question on desktop and mobile', async () => {
  for (const width of [1440, 393, 320]) await app(async page => {
    await page.setViewportSize({ width, height: 852 });
    const story = page.locator('header details.origin-story');
    const summary = story.locator('summary');
    assert.equal(await summary.count(), 1);
    assert.equal(await summary.innerText(), '?');
    assert.equal(await summary.getAttribute('aria-label'), 'Proč tahle mapa vznikla');
    assert.equal(await page.locator('.edition, footer .origin-story').count(), 0);
    assert.equal(await story.locator('.origin-story-panel').isVisible(), false);
    const bareQuestion = async () => assert.deepEqual(await summary.evaluate(n => {
      const s = getComputedStyle(n);
      return { background:s.backgroundColor, border:s.borderTopWidth, radius:s.borderRadius, size:s.fontSize, weight:s.fontWeight };
    }), { background:'rgba(0, 0, 0, 0)', border:'0px', radius:'0px', size:'14px', weight:'400' });
    await bareQuestion();
    await summary.hover();
    await bareQuestion();
    const triggerBox = await summary.boundingBox();
    assert(triggerBox.width >= 44 && triggerBox.height >= 44);
    const wordmarkBox = await page.locator('.wordmark').boundingBox();
    assert(wordmarkBox.x + wordmarkBox.width <= triggerBox.x);
    await summary.click({ timeout: 3000 });
    assert.equal(await story.locator('.origin-story-panel').isVisible(), true);
    await bareQuestion();
    assert.equal(await story.locator('h2').innerText(), 'Proč tahle mapa vznikla');
    assert.equal(await story.locator('p').innerText(), 'Moje žena má ráda vánoční atmosféru a trhy. Tahle mapa vznikla, abychom měli po ruce tipy, kam spolu vyrazit.');
    const panelBox = await story.locator('.origin-story-panel').boundingBox();
    assert(panelBox.x >= 0 && panelBox.x + panelBox.width <= width);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    if (width === 393) await page.locator('.masthead').screenshot({ path: screenshotPath('origin-story-header-mobile-fixture.png') });
    await summary.press('Enter');
    assert.equal(await story.locator('.origin-story-panel').isVisible(), false);
  }, { javaScriptEnabled: false });
});

test('feedback API failures are not empty results and never block drafts or map', async () => {
  for (const failure of ['429', 'network', 'timeout']) await app(async (page, errors) => {
    await page.route('https://api.github.com/**', route => failure === '429' ? route.fulfill({ status: 429, body: '{}', headers: { 'access-control-allow-origin': '*' } }) : failure === 'network' ? route.abort() : undefined);
    await page.locator('#feedback > summary').click();
    await page.waitForFunction(() => document.getElementById('feedback-list-status').textContent.includes('nepodařilo'), { timeout: 8000 });
    assert.doesNotMatch(await page.locator('#feedback-list-status').innerText(), /žádná hlášení/);
    assert.equal(await page.locator('#feedback-form').isVisible(), true);
    await page.locator('#feedback-mode').selectOption('quick');
    await page.locator('#feedback-town').fill('Brno');
    await page.locator('#feedback-consent').check();
    await page.evaluate(() => { window.open = () => null; });
    await page.locator('#feedback-form button').click();
    assert.equal(await page.locator('#feedback-draft').isVisible(), true);
    const target = new URL(await page.locator('#feedback-draft').getAttribute('href'));
    assert.equal(target.searchParams.get('title'), '[Tip] Brno');
    assert.equal(await page.locator('#feedback-town').inputValue(), 'Brno');
    await page.locator('#show-map').click();
    await page.waitForSelector('#map .leaflet-interactive');
    assert.equal(await page.locator('.event-card').count(), 3);
    assert.deepEqual(errors, []);
  }, { mobile: true });
});

test('feedback fallback template anchor works without JavaScript', async () => {
  await app(async page => {
    await page.locator('#feedback > summary').click();
    const link = page.getByRole('link', { name: 'Napsat tip přímo na GitHubu (i bez JavaScriptu)' });
    assert.equal(await link.isVisible(), true);
    assert.equal(await link.getAttribute('href'), 'https://github.com/romanzdk/advent-cesko-pilot/issues/new?template=tip.md');
    assert.equal(await page.locator('#feedback-form').isVisible(), false);
  }, { javaScriptEnabled: false, mobile: true });
});

test('feedback module failure retains a direct template link and working event filters', async () => {
  await app(async page => {
    await page.route('**/feedback.js', route => route.abort());
    await page.reload();
    await page.waitForSelector('.event-card');
    await page.locator('#feedback > summary').click();
    assert.equal(await page.getByRole('link', { name: 'Napsat tip přímo na GitHubu (i bez JavaScriptu)' }).isVisible(), true);
    assert.equal(await page.locator('#feedback-form').isVisible(), false);
    await page.locator('#category').selectOption('strom');
    assert.equal(await page.locator('.event-card').count(), 1);
  }, { mobile: true });
});

test('feedback lazily fetches once, renders safe open/closed fixture issues and searches existing phrases', async () => {
  for (const mobile of [false, true]) await app(async (page, errors) => {
    let calls = 0;
    await page.route('https://api.github.com/**', async route => {
      calls++;
      assert.equal(route.request().url(), 'https://api.github.com/repos/romanzdk/advent-cesko-pilot/issues?state=all&sort=updated&direction=desc&per_page=10');
      assert.equal(route.request().method(), 'GET');
      await route.fulfill({ contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: JSON.stringify([
        { number: 42, title: '<img src=x onerror="window.injected=true"> Říčany', state: 'open', html_url: 'https://github.com/romanzdk/advent-cesko-pilot/issues/42' },
        { number: 43, title: 'Vyřešený testovací tip', state: 'closed', html_url: 'https://github.com/romanzdk/advent-cesko-pilot/issues/43' },
        { number: 44, title: 'Unsafe', state: 'open', html_url: 'javascript:alert(1)' }
      ]) });
    });
    await page.waitForSelector('.event-card');
    assert.equal(calls, 0);
    await page.evaluate(() => {
      const nativeFetch = window.fetch;
      window.fetch = (url, options) => {
        if (String(url).startsWith('https://api.github.com/')) window.feedbackFetch = { credentials: options.credentials, signal: options.signal instanceof AbortSignal };
        return nativeFetch(url, options);
      };
    });
    await page.locator('#feedback > summary').click();
    await page.waitForSelector('#feedback-issues li');
    assert.deepEqual(await page.evaluate(() => window.feedbackFetch), { credentials: 'omit', signal: true });
    assert.equal(await page.locator('#feedback-issues li').count(), 2);
    assert.match(await page.locator('#feedback-issues').innerText(), /Otevřeno/);
    assert.match(await page.locator('#feedback-issues').innerText(), /Uzavřeno/);
    assert.equal(await page.locator('#feedback-issues img').count(), 0);
    assert.equal(await page.evaluate(() => window.injected), undefined);
    await page.locator('#feedback > summary').click();
    await page.locator('#feedback > summary').click();
    assert.equal(calls, 1);
    await page.locator('#feedback-search').fill('Říčany & dílna? #1');
    const search = new URL(await page.locator('#feedback-search-link').getAttribute('href'));
    assert.equal(search.origin, 'https://github.com');
    assert.equal(search.searchParams.get('q'), 'is:issue Říčany & dílna? #1');
    assert.equal(await page.getByRole('link', { name: 'Všechny tipy a hlášení na GitHubu' }).getAttribute('href'), 'https://github.com/romanzdk/advent-cesko-pilot/issues?q=is%3Aissue');
    assert.deepEqual(errors, []);
  }, { mobile });
});

test('feedback draft requires input and consent, preserves fields and only GETs GitHub on visitor action', async () => {
  for (const mobile of [false, true]) await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    assert.equal(await page.locator('#feedback').count(), 1);
    await page.locator('#feedback > summary').click();
    const form = page.locator('#feedback-form');
    await page.locator('#feedback-mode').selectOption('quick');
    await page.locator('#feedback-consent').check();
    await form.getByRole('button', { name: 'Připravit návrh na GitHubu' }).click();
    assert.match(await page.locator('#feedback-message').innerText(), /obec, odkaz nebo popis/);
    await page.locator('#feedback-town').fill('Říčany & okolí? #1');
    await page.locator('#feedback-description').fill('<img src=x onerror=alert(1)> & text');
    await page.locator('#feedback-consent').uncheck();
    assert.equal(await form.evaluate(f => f.checkValidity()), false);
    await page.locator('#feedback-consent').check();
    const requests = [];
    page.context().on('request', r => { if (r.url().startsWith('https://github.com/')) requests.push([r.method(), r.url()]); });
    const popupPromise = page.context().waitForEvent('page');
    await form.getByRole('button', { name: 'Připravit návrh na GitHubu' }).click();
    const popup = await popupPromise;
    await popup.waitForLoadState();
    const target = new URL(popup.url());
    assert.equal(target.origin, 'https://github.com');
    assert.equal(target.pathname, '/romanzdk/advent-cesko-pilot/issues/new');
    assert.deepEqual([...target.searchParams.keys()].sort(), ['body', 'template', 'title']);
    assert.equal(target.searchParams.get('title'), '[Tip] Říčany & okolí? #1');
    assert(target.searchParams.get('body').includes('<img src=x onerror=alert(1)> & text'));
    assert(requests.length && requests.every(([method]) => method === 'GET'));
    assert.equal(await popup.evaluate(() => window.opener), null);
    assert.equal(await page.locator('#feedback-town').inputValue(), 'Říčany & okolí? #1');
    assert.match(await page.locator('#feedback-message').innerText(), /dokončíte na GitHubu/);
    for (const locator of ['#feedback > summary', '#feedback-form button', '#feedback-town', '#feedback-source', '#feedback-description', '#feedback-consent', '#feedback a']) {
      for (const box of await page.locator(locator).evaluateAll(nodes => nodes.filter(n => n.getClientRects().length).map(n => ({ height: n.getBoundingClientRect().height })))) assert(box.height >= 44, locator);
    }
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.match(await page.locator('#feedback').innerText(), /účet GitHub/);
    assert.match(await page.locator('#feedback').innerText(), /osobní údaje/);
    assert.match(await page.locator('#feedback').innerText(), /není automatické/);
    await page.locator('#category').selectOption('strom');
    assert.equal(await page.locator('.event-card').count(), 1);
    if (mobile) await page.locator('#show-map').click();
    await page.waitForSelector('#map .leaflet-interactive');
    assert.equal(await page.locator('#map .leaflet-interactive').count(), 1);
    assert.deepEqual(errors, []);
  }, { mobile });
});

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
      await page.locator('#town').focus();
      assert.equal(await page.locator('#town-options [role=option]').count(), 1);
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

test('region filter includes every covered region even when its events are not published yet', async () => {
  const regions = ['Hlavní město Praha', 'Jihočeský kraj', 'Jihomoravský kraj', 'Karlovarský kraj', 'Kraj Vysočina', 'Královéhradecký kraj', 'Liberecký kraj', 'Moravskoslezský kraj', 'Olomoucký kraj', 'Pardubický kraj', 'Plzeňský kraj', 'Středočeský kraj', 'Ústecký kraj', 'Zlínský kraj'];
  for (const mobile of [false, true]) await app(async (page, errors) => {
    await page.waitForFunction(() => document.getElementById('scope-summary').textContent.startsWith('14 krajů'));
    await page.waitForSelector('.event-card');
    const options = await page.locator('#region option').evaluateAll(nodes => nodes.map(n => ({ value: n.value, text: n.textContent, disabled: n.disabled })));
    assert.deepEqual(options.filter(n => n.value).map(n => n.value), [...regions].sort((a,b) => a.localeCompare(b,'cs')));
    assert.equal(options.find(n => n.value === 'Zlínský kraj').text, 'Zlínský kraj · zatím bez akcí');
    assert.equal(options.find(n => n.value === 'Zlínský kraj').disabled, false);
    assert.equal(options.find(n => n.value === 'Plzeňský kraj').text, 'Plzeňský kraj');
    await page.locator('#region').selectOption('Zlínský kraj');
    assert.equal(await page.locator('.event-card').count(), 0);
    assert.match(await page.locator('.empty-state').innerText(), /Pro tento kraj zatím nemáme publikované akce/);
    assert.match(await page.locator('.empty-state').innerText(), /Neznamená to, že se zde nic nekoná/);
    await page.locator('#town').focus();
    assert.equal(await page.locator('#town-options [role=option]').count(), 0);
    assert.equal(await page.locator('#town').getAttribute('aria-expanded'), 'false');
    await page.getByRole('button', {name:'Zrušit filtry',exact:true}).click();
    assert.equal(await page.locator('#region').inputValue(), '');
    assert.equal(await page.locator('.event-card').count(), 3);
    assert.equal(await page.locator('#region option').count(), 15);
    assert.deepEqual(errors, []);
  }, {data:regionalFixture,coverage:{...coverageFixture,regions},mobile});
});

test('late coverage expands regions without resetting an active event filter', async () => {
  await app(async (page, errors) => {
    let pendingCoverage;
    await page.route('**/coverage.json', route => { pendingCoverage = route; });
    await page.reload();
    await page.waitForSelector('.event-card');
    await page.locator('#region').selectOption('Liberecký kraj');
    await page.locator('#town').fill('Turnov');
    await page.locator('#search').fill('strom');
    assert(pendingCoverage);
    await pendingCoverage.fulfill({contentType:'application/json',body:JSON.stringify({...coverageFixture,regions:[...coverageFixture.regions,'Zlínský kraj']})});
    await page.waitForFunction(() => document.getElementById('scope-summary').textContent.startsWith('4 kraje'));
    assert.equal(await page.locator('#region option').count(), 5);
    assert.equal(await page.locator('#region').inputValue(), 'Liberecký kraj');
    assert.equal(await page.locator('#town').inputValue(), 'Turnov');
    assert.equal(await page.locator('#search').inputValue(), 'strom');
    assert.equal(await page.locator('.event-card').count(), 1);
    assert.equal(await page.locator('#region option[value="Zlínský kraj"]').innerText(), 'Zlínský kraj · zatím bez akcí');
    assert.deepEqual(errors, []);
  }, {data:regionalFixture,coveragePending:true});
});

test('regions from early coverage survive delayed events and unavailable coverage falls back to event regions', async () => {
  for (const coverageStatus of [200,503]) await app(async (page, errors) => {
    if (coverageStatus === 200) await page.waitForFunction(() => document.getElementById('scope-summary').textContent.startsWith('4 kraje'));
    await page.waitForSelector('.event-card');
    assert.equal(await page.locator('#region option').count(), coverageStatus === 200 ? 5 : 4);
    assert.equal(await page.locator('#region option[value="Plzeňský kraj"]').innerText(), 'Plzeňský kraj');
    await page.locator('#region').selectOption('Plzeňský kraj');
    await page.locator('#category').selectOption('tvoreni');
    assert.equal(await page.locator('.event-card').count(), 1);
    await page.locator('#category').selectOption('betlem');
    assert.equal(await page.locator('.event-card').count(), 0);
    assert.doesNotMatch(await page.locator('.empty-state').innerText(), /Pro tento kraj zatím nemáme publikované akce/);
    assert.deepEqual(errors, []);
  }, {data:regionalFixture,delay:400,coverage:{...coverageFixture,regions:[...coverageFixture.regions,'Zlínský kraj']},coverageStatus});
});

test('region scope limits towns, combines with other filters and resets cleanly', async () => {
  await app(async (page, errors) => {
    await page.waitForSelector('.event-card');
    assert.equal(await page.locator('#region[name="region"]').count(), 1);
    assert.deepEqual(await page.locator('#region option').allTextContents(), ['Všechny kraje', 'Jihomoravský kraj', 'Liberecký kraj', 'Plzeňský kraj']);
    await page.locator('#town').fill('Turnov');
    await page.locator('#region').selectOption('Plzeňský kraj');
    assert.equal(await page.locator('#town').inputValue(), '');
    await page.locator('#town').focus();
    assert.deepEqual(await page.locator('#town-options [role=option]').allTextContents(), ['Plasy']);
    assert.equal(await page.locator('.event-card').getAttribute('data-id'), 'fixture-b');
    assert.match(await page.locator('#result-count').innerText(), /Plzeňský kraj/);
    await page.locator('#town').fill('Plasy');
    assert.match(await page.locator('#result-count').innerText(), /Plasy/);
    await page.locator('#category').selectOption('strom');
    await page.waitForSelector('.empty-state');
    await page.getByRole('button', { name: 'Zrušit filtry', exact: true }).click();
    assert.equal(await page.locator('#region').inputValue(), '');
    await page.locator('#town').focus();
    assert.equal(await page.locator('#town-options [role=option]').count(), 3);
    assert.equal(await page.locator('.event-card').count(), 3);
    assert.deepEqual(errors, []);
  }, { data: regionalFixture, mobile: true });
});

test('footer credits Roman and links his website, GitHub and project', async () => {
  for (const mobile of [false, true]) {
    await app(async page => {
      await page.waitForSelector('.event-card');
      const footer = page.locator('footer');
      await footer.scrollIntoViewIfNeeded();
      assert.match(await footer.innerText(), /Autor: Roman Žydyk/);
      for (const [name, href] of [['romanzdk.com', 'https://romanzdk.com/'], ['GitHub autora', 'https://github.com/romanzdk'], ['Kód projektu', 'https://github.com/romanzdk/advent-cesko-pilot']]) {
        const link = footer.getByRole('link', {name, exact: true});
        assert.equal(await link.getAttribute('href'), href);
        assert.equal(await link.isVisible(), true);
        const box = await link.boundingBox();
        assert(box && box.height >= 44);
      }
      assert.equal(await footer.getByRole('link').count(), 3);
      assert.deepEqual(await footer.getByRole('link').evaluateAll(links => links.map(link => link.href)), ['https://romanzdk.com/', 'https://github.com/romanzdk', 'https://github.com/romanzdk/advent-cesko-pilot']);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    }, {mobile});
  }
});

test('restricted audience is not labelled as seniors', async () => {
  await app(async page => {
    await page.waitForSelector('.event-card');
    assert.equal(await page.locator('.audience-badge').innerText(), 'Omezené zaměření');
  }, {data: {...fixture, events: [{...fixture.events[0], audience: 'omezené zaměření'}]}});
});

test('map names its bounded Christmas 2026 scope and excludes out-of-window events', async () => {
  const data = { ...regionalFixture, events: [
    ...regionalFixture.events,
    ...['2025-11-28', '2026-11-19', '2026-12-24', '2026-12-25', '2027-11-28'].map((date, index) => ({ ...regionalFixture.events[0], id: `boundary-${index}`, date }))
  ] };
  await app(async page => {
    await page.waitForSelector('.event-card');
    assert.equal(await page.locator('h1').innerText(), 'Adventní akce v Česku 2026');
    assert.equal(await page.title(), 'Kam na advent — adventní akce v Česku 2026');
    assert.equal(await page.locator('.wordmark').getAttribute('aria-label'), 'Kam na advent, úvod');
    assert.match(await page.locator('.wordmark').innerText(), /^kam\s+na advent/);
    assert.equal(await page.locator('meta[property="og:site_name"]').getAttribute('content'), 'Kam na advent');
    assert.match(await page.locator('meta[property="og:title"]').getAttribute('content'), /^Kam na advent/);
    assert.match(await page.locator('meta[name="twitter:title"]').getAttribute('content'), /^Kam na advent/);
    for (const width of [1440, 393, 320]) {
      await page.setViewportSize({ width, height: 900 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      const name = await page.locator('.wordmark').boundingBox();
      const help = await page.locator('.origin-story summary').boundingBox();
      assert(name.x + name.width <= help.x);
    }
    assert.match(await page.locator('.intro').innerText(), /Sezonní výběr veřejných akcí 2026/);
    assert.match(await page.locator('.intro').innerText(), /Výběr veřejných zdrojů, nikoli úplný přehled krajů ani celé ČR\./);
    assert.doesNotMatch(await page.locator('.footer').innerText(), /pilot/i);
    assert.equal(await page.locator('.edition').count(), 0);
    assert.match(await page.locator('.intro').innerText(), /20\. 11\. – 24\. 12\. 2026/);
    assert.equal(await page.locator('.footer-links a').count(), 3);
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
    assert.match(text, /Limity sběru se liší podle zdroje/);
    assert.doesNotMatch(text, /nejvýše 2 stránky výpisu a 14 detailů na zdroj/);
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
    await page.screenshot({ path: screenshotPath('coverage-mobile-fixture.png'), fullPage: true });
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
      const bottoms = await page.locator('#filters input, #filters select, #filters button').evaluateAll(nodes => nodes.filter(node => node.getClientRects().length).map(node => node.getBoundingClientRect().bottom));
      assert(Math.max(...bottoms) - Math.min(...bottoms) < 2, JSON.stringify({ width, bottoms }));
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    }
    await page.screenshot({ path: screenshotPath('pilot-desktop-fixture.png'), fullPage: false });
  }, { data: regionalFixture });
});

test('default mobile date and type labels have room for native select arrows', async () => {
  await app(async page => {
    await page.waitForSelector('.event-card');
    for (const width of [393, 320]) {
      await page.setViewportSize({ width, height: 852 });
      const clipped = await page.locator('select').evaluateAll(nodes => nodes.filter(node => node.getClientRects().length).filter(node => {
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
    const destination = new URL(await navigation.getAttribute('href'));
    assert.equal(destination.origin, 'https://www.google.com');
    assert.equal(destination.pathname, '/maps/dir/');
    assert.equal(destination.searchParams.get('api'), '1');
    assert.equal(destination.searchParams.get('destination'), '49.964,14.073');
    assert.equal(destination.searchParams.has('origin'), false);
    assert.equal(await navigation.getAttribute('target'), '_blank');
    assert.equal(await navigation.getAttribute('rel'), 'noopener noreferrer');
    assert.match(await navigation.getAttribute('title'), /Google Maps.*středu obce/);
    const precise = page.locator('[data-id="fixture-a"] .navigation-link');
    assert.match(await precise.innerText(), /Navigovat/);
    assert.equal(new URL(await precise.getAttribute('href')).searchParams.get('destination'), '49.99,14.655');
  });
});

test('map groups shared places, selects a card and follows active filters even without tiles', async () => {
  await app(async (page, errors) => {
    const originalURL = page.url();
    await page.waitForSelector('.event-card');
    await page.waitForSelector('#map .leaflet-interactive', { timeout: 3000 });
    assert.equal(await page.locator('#map .leaflet-interactive').count(), 2);
    assert.match(await page.locator('#map-notice').innerText(), /podklad/);
    assert.match(await page.locator('.leaflet-control-attribution').innerText(), /OpenStreetMap/);
    const marker = page.locator('#map .leaflet-interactive[aria-label*="Beroun"]');
    await marker.focus();
    await marker.press('Enter');
    await page.waitForSelector('.popup-event');
    assert.equal(await page.locator('.popup-event').count(), 2);
    await page.locator('.popup-event').last().click();
    assert.equal(await page.locator('.event-card.selected').getAttribute('data-id'), 'fixture-c');
    assert.equal(await page.locator('.event-card.selected').evaluate(node => node === document.activeElement), true);
    assert.equal(page.url(), originalURL, 'ordinary map selection does not create permalink history');
    await page.locator('#category').selectOption('strom');
    await page.waitForFunction(() => document.querySelectorAll('#map .leaflet-interactive').length === 1);
    assert.deepEqual(errors, []);
    await page.screenshot({ path: screenshotPath('desktop-fixture.png'), fullPage: true });
  });
  await app(async page => {
    await page.waitForSelector('.event-card');
    await page.locator('#show-map').click();
    await page.waitForSelector('#map .leaflet-interactive');
    await page.locator('#map .leaflet-interactive[aria-label*="Beroun"]').click();
    await page.locator('.popup-event').first().click();
    assert.equal(await page.locator('#results').isVisible(), true);
    assert.equal(await page.locator('.event-card.selected').getAttribute('data-id'), 'fixture-b');
    assert.equal(new URL(page.url()).hash, '', 'ordinary mobile map selection does not create permalink history');
    await page.screenshot({ path: screenshotPath('mobile-fixture.png'), fullPage: true });
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
    await page.locator('#town').fill('Říčany');
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
      await page.screenshot({ path: screenshotPath(`${mobile ? 'mobile' : 'desktop'}-fixture.png`), fullPage: false });
    }, { data: displayFixture, mobile });
  }
});


test('structured event defaults to full, preserves inactive drafts and prepares honest popup fallback', async () => {
  await app(async (page, errors) => {
    await page.locator('#feedback > summary').click();
    const mode = page.locator('#feedback-mode');
    assert.equal(await mode.count(), 1);
    assert.equal(await mode.inputValue(), 'full');
    assert.equal(await page.locator('#feedback-optional').getAttribute('open'), null);
    assert.equal(await page.locator('#feedback-region option').count(), 15);
    assert.equal(await page.locator('#feedback-category option').count(), 7);
    await page.locator('#feedback-title').fill('<img src=x> Dílna');
    await page.locator('#feedback-town').fill('Beroun');
    await page.locator('#feedback-source').fill('https://example.cz/event');
    await page.locator('#feedback-date').fill('2026-11-28');
    await page.locator('#feedback-optional > summary').click();
    await page.locator('#feedback-start-time').fill('16:00');
    await page.locator('#feedback-end-time').fill('15:00');
    await page.locator('#feedback-consent').check();
    await page.evaluate(() => { window.open = () => { throw new Error('Popup denied'); }; });
    await page.locator('#feedback-form button').click();
    assert.match(await page.locator('#feedback-message').innerText(), /Konec/);
    await page.locator('#feedback-date-unknown').check();
    assert.equal(await page.locator('#feedback-date').isDisabled(), true);
    await page.locator('#feedback-form button').click();
    assert.equal(await page.locator('#feedback-draft').isVisible(), true);
    let body = new URL(await page.locator('#feedback-draft').getAttribute('href')).searchParams.get('body');
    assert.match(body, /Datum\nNeznámé/);
    assert.doesNotMatch(body, /16:00|15:00|2026-11-28/);
    assert.match(await page.locator('#feedback-message').innerText(), /návrh|Návrh/);
    assert.doesNotMatch(await page.locator('#feedback-message').innerText(), /odesláno/i);
    await mode.selectOption('quick');
    assert.equal(await page.locator('#feedback-draft').isVisible(), false);
    assert.equal(await page.locator('#feedback-title').isDisabled(), true);
    await page.locator('#feedback-form button').click();
    body = new URL(await page.locator('#feedback-draft').getAttribute('href')).searchParams.get('body');
    assert.doesNotMatch(body, /<img src=x>|Datum|Kategorie/);
    await mode.selectOption('full');
    await page.locator('#feedback-date-unknown').uncheck();
    assert.equal(await page.locator('#feedback-title').inputValue(), '<img src=x> Dílna');
    assert.equal(await page.locator('#feedback-date').inputValue(), '2026-11-28');
    assert.equal(await page.locator('#feedback-start-time').inputValue(), '16:00');
    assert.equal(await page.locator('#feedback img').count(), 0);
    await page.locator('#feedback-end-time').fill('18:00');
    await page.locator('#feedback-form button').click();
    assert.equal(await page.locator('#feedback-draft').isVisible(), true);
    for (const width of [393, 320]) {
      await page.setViewportSize({width, height:852});
      for (const selector of ['#feedback-form input:not([type=checkbox])', '#feedback-form select', '#feedback-form textarea', '#feedback-form button', '#feedback-form summary', '#feedback-form .feedback-consent']) {
        for (const box of await page.locator(selector).evaluateAll(nodes => nodes.filter(n => n.getClientRects().length).map(n => ({x:n.getBoundingClientRect().x,width:n.getBoundingClientRect().width,height:n.getBoundingClientRect().height,font:parseFloat(getComputedStyle(n).fontSize)})))) {
          assert(box.height >= 44 && box.x >= 0 && box.x + box.width <= width, JSON.stringify(box));
          assert(box.font >= 16, JSON.stringify(box));
        }
      }
      await page.addStyleTag({content:'html {font-size:125%}'});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    }
    await page.locator('#feedback-form').screenshot({path:screenshotPath('structured-event-form-mobile-fixture.png')});
    assert.deepEqual(errors, []);
  }, {mobile:true});
});
