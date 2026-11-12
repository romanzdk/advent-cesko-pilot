"""Deterministic collector regression tests; no live network required."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = json.loads((ROOT / 'data/sources.json').read_text())
RESEARCH = ROOT / 'tests/fixtures/research'
LEGACY_SEMILY = json.loads((ROOT/'tests/fixtures/legacy-semily-source.json').read_text())


def collector():
    path = ROOT / 'scripts/collector.py'
    assert path.exists(), 'collector implementation is missing'
    spec = importlib.util.spec_from_file_location('collector', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ParserTests(unittest.TestCase):
    def test_actual_galileo_plasy(self):
        c = collector()
        source = REGISTRY['sources'][0]
        html = (RESEARCH / 'pilot-plzensky/fixtures/plasy_tree.html').read_bytes()
        event = c.parse_event(html, source, source['seed_urls'][0], REGISTRY['window'])
        self.assertEqual((event['date'], event['startTime']), ('2026-11-28', '16:30'))
        self.assertEqual(event['town'], 'Plasy')
        self.assertLessEqual(len(event['description']), 200)

    def test_safety_and_public_metadata(self):
        c = collector()
        s = REGISTRY['sources'][0]
        def parse(date_text='5. 12. 2026 17:00', venue='Plasy', extra='', title='Mikulášská besídka'):
            html = f'<h1>{title}</h1><div class="event-detail"><h2 class="action-date">{date_text}</h2><h2 class="venue">{venue}</h2><div class="lead">{extra}</div></div><footer>2026</footer>'
            return c.parse_event(html, s, s['seed_urls'][0], REGISTRY['window'])
        for d in ['5. 12. 2025 17:00', '5. 12. 17:00', '31. 11. 2026', '']:
            with self.subTest(date=d), self.assertRaises(c.Review): parse(d)
        with self.assertRaises(c.Review): parse(venue='Kulturní dům, Semily')
        with self.assertRaises(c.Review): parse(venue='Babina')
        e = parse(extra='Na akci je nutné přihlášení. osobni@example.cz', title='Vánoční tvoření pro dospělé')
        self.assertEqual(e['category'], 'tvoreni')
        self.assertEqual(e['audience'], 'dospělí')
        self.assertTrue(e['registration'])
        self.assertNotIn('@', json.dumps(e))
        self.assertEqual(parse('24. 12. 2026 0:00')['startTime'], None)
        self.assertTrue(parse('20. 11. 2026 10:00 – 22. 11. 2026 18:00')['notes'])
        with self.assertRaises(c.Review): parse('5. 12. 2026 17:00 a 6. 12. 2026 18:00')

    def test_jsonld_event_preferred_and_sanitized(self):
        c = collector()
        source = REGISTRY['sources'][0]
        url = source['seed_urls'][0]
        data = {'@context':'https://schema.org','@type':'Event','name':'Vánoční trhy','startDate':'2026-12-05T15:00:00+01:00','endDate':'2026-12-05T18:00:00+01:00','location':{'name':'Náměstí Plasy'}}
        e = c.parse_event('<script type="application/ld+json">'+json.dumps(data)+'</script>', source,url,REGISTRY['window'])
        self.assertEqual((e['date'],e['startTime'],e['endTime']),('2026-12-05','15:00','18:00'))
        self.assertEqual(e['category'],'trhy')
        html = '<h1>Vánoce info@example.cz</h1><div class="event-detail"><h2 class="action-date">5. 12. 2026 15:00</h2><div class="venue">Plasy /private/secret</div></div>'
        e = c.parse_event(html,source,url,REGISTRY['window'])
        self.assertNotIn('@',json.dumps(e))
        self.assertNotIn('/private/',json.dumps(e))
        with self.assertRaises(c.Review): c.parse_event(html,source,'javascript:bad',REGISTRY['window'])
        conflict = html.replace('</div></div>', '</div><p>Akce 6. 12. 2026 v 18:00</p></div>')
        with self.assertRaises(c.Review): c.parse_event(conflict,source,url,REGISTRY['window'])

    def test_jilemnice_programme_end_and_drupal_booking(self):
        c = collector()
        j = REGISTRY['sources'][3]
        e = c.parse_event((RESEARCH/'pilot-liberecky/jilemnice-tree.html').read_bytes(),j,j['seed_urls'][0],REGISTRY['window'])
        self.assertEqual(e['endTime'],'18:00')
        self.assertTrue(any('17:00' in n for n in e['notes']))
        k = REGISTRY['sources'][5]
        e = c.parse_event((RESEARCH/'pilot-jihomoravsky/fixtures/skc-svicny.html').read_bytes(),k,k['seed_urls'][1],REGISTRY['window'])
        self.assertTrue(e['registrationUrl'].startswith('https://docs.google.com/forms/'))
        self.assertIsNone(e['endTime']) # sister-site-only end is not silently imported

    def test_all_eighteen_actual_primary_details(self):
        c = collector()
        research = RESEARCH
        cases = []
        for f in json.loads((research / 'pilot-plzensky/verified-events.json').read_text()):
            s = REGISTRY['sources'][0 if f['key'].startswith('plasy') else 1]
            cases.append((s, f['url'], research / 'pilot-plzensky/fixtures' / (f['key']+'.html'), f['date'], f.get('time')))
        for f in json.loads((research / 'pilot-liberecky/verified-facts.json').read_text())['events']:
            if not f.get('in_scope'): continue
            s = LEGACY_SEMILY if f['source_id'] == 'cz-semily-calendar' else next(s for s in REGISTRY['sources'] if s['id'] == f['source_id'])
            cases.append((s, f['source_url'], research / 'pilot-liberecky' / f['raw_html'], f['date'], f['start_time']))
        for f in json.loads((research / 'pilot-jihomoravsky/verified-event-facts.json').read_text()):
            s = next(s for s in REGISTRY['sources'] if s['id'] == f['source_id'])
            key = f['id'].replace('kurim-', 'skc-')
            cases.append((s, f['source_url'], research / 'pilot-jihomoravsky/fixtures' / (key+'.html'), f['date'], f['start_time']))
        self.assertEqual(len(cases), 18)
        for s,u,p,d,t in cases:
            with self.subTest(file=p.name):
                e = c.parse_event(p.read_bytes(), s, u, REGISTRY['window'])
                self.assertEqual(e['date'], d)
                self.assertEqual(e['startTime'], t if t != '00:00' else None)
                self.assertTrue(e['title'])
                self.assertLessEqual(len(e['description']), 200)


class CollectionTests(unittest.TestCase):
    def test_incremental_discovery_publication_and_outage(self):
        c = collector()
        source = dict(REGISTRY['sources'][0])
        source['index_urls'] = ['https://www.plasy.cz/index']
        u = source['seed_urls'][0]
        new = u.replace('3900_1389', '9900_9989')
        page2 = 'https://www.plasy.cz/index?page=2'
        fixture = (RESEARCH / 'pilot-plzensky/fixtures/plasy_tree.html').read_bytes()
        pages = {source['index_urls'][0]: f'<a rel="next" href="{page2}">2</a>'.encode(), page2: f'<a href="{new}">Nové rozsvícení vánočního stromu</a>'.encode(), u: fixture, new: fixture}
        source['seed_urls'] = [u]
        class Fetcher:
            stats = {'requestCount': 0, 'http304': 0, 'cacheUnchanged': 0}
            def get(self, url):
                self.stats['requestCount'] += 1
                if url not in pages: raise OSError('secret@example.cz /private/secret')
                return pages[url]
        registry = dict(REGISTRY, sources=[source])
        with tempfile.TemporaryDirectory() as tmp:
            db, output = Path(tmp)/'events.sqlite', Path(tmp)/'public'
            r = c.collect(registry, db, output, {}, Fetcher())
            self.assertEqual(r['metrics']['eventsNew'], 2)
            self.assertEqual(r['metrics']['eventsPublished'], 1) # exact title/date/venue/town duplicate
            self.assertFalse(r['complete'])
            r = c.collect(registry, db, output, {}, Fetcher())
            self.assertEqual(r['metrics']['eventsUnchanged'], 2)
            pages[u] = fixture.replace(b'16:30', b'18:30')
            r = c.collect(registry, db, output, {}, Fetcher())
            self.assertEqual(r['metrics']['eventsChanged'], 1)
            self.assertEqual(r['metrics']['eventsNew'], 0)
            pages.clear()
            r = c.collect(registry, db, output, {}, Fetcher())
            self.assertEqual(r['sources'][0]['status'], 'error')
            self.assertEqual(r['metrics']['eventsPublished'], 2)
            self.assertIsNotNone(r['sources'][0]['lastSuccess'])
            self.assertNotIn('secret', json.dumps(r))
            public = json.loads((output/'events.json').read_text())
            self.assertEqual(public['schemaVersion'], 1)
            self.assertEqual(public['region'], 'Česko – sezonní výběr')
            self.assertEqual(len(public['events']), 2)
            import sqlite3
            con = sqlite3.connect(db)
            self.assertGreater(con.execute('select count(*) from observations').fetchone()[0], 0)
            self.assertGreater(con.execute('select count(*) from provenance').fetchone()[0], 0)
            con.close()

    def test_cli_help_and_offline_review(self):
        import subprocess, sys
        script = str(ROOT/'scripts/collector.py')
        help_result = subprocess.run([sys.executable, script, '--help'], capture_output=True, text=True)
        self.assertEqual(help_result.returncode,0)
        self.assertIn('--registry',help_result.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            source = dict(REGISTRY['sources'][0], seed_urls=REGISTRY['sources'][0]['seed_urls'][:1], index_urls=['https://www.plasy.cz/index'])
            (tmp/'registry.json').write_text(json.dumps(dict(REGISTRY,sources=[source])))
            (tmp/'index.html').write_text('<p>Žádný nový odkaz</p>')
            (tmp/'bad.html').write_text('<h1>Vánoce osobni@example.cz</h1><div class="event-detail">Datum jen na plakátu</div>')
            (tmp/'manifest.json').write_text(json.dumps({source['index_urls'][0]:'index.html',source['seed_urls'][0]:'bad.html'}))
            result = subprocess.run([sys.executable,script,'--registry',str(tmp/'registry.json'),'--db',str(tmp/'events.sqlite'),'--cache',str(tmp/'cache'),'--output',str(tmp/'public'),'--offline-fixtures',str(tmp/'manifest.json')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['metrics']['reviewCount'],1)
            review = (tmp/'public/review.json').read_text()
            self.assertNotIn('@',review)
            self.assertNotIn(str(tmp),review)
            self.assertEqual(json.loads((tmp/'public/events.json').read_text())['events'],[])

    def test_http_retries_limits_and_spacing(self):
        import time
        c = collector()
        calls = []
        def send(url, headers):
            calls.append((url,time.monotonic()))
            if url.endswith('/robots.txt'): return 200,{},b'User-agent: *\nDisallow:\n'
            if len([u for u,t in calls if u == url]) == 1: return 503,{},b''
            return 200,{},b'same'
        with tempfile.TemporaryDirectory() as tmp:
            http = c.HTTPClient(tmp,send=send,min_interval=0.01)
            url = 'https://www.plasy.cz/test'
            self.assertEqual(http.get(url),b'same')
            self.assertEqual(len(calls),3)
            self.assertGreaterEqual(calls[2][1]-calls[1][1],0.009)
            self.assertEqual(http.get(url),b'same')
            self.assertEqual(http.stats['cacheUnchanged'],1)
            http.send = lambda u,h: (200,{},b'x'*(2*1024*1024+1))
            with self.assertRaises(OSError): http.get(url)

    def test_discovery_boundaries_and_review_retention(self):
        c = collector()
        s = dict(REGISTRY['sources'][0],max_details=1)
        u = s['seed_urls'][0]
        index = s['index_urls'][0]
        new = u.replace('3900_1389','9999_9999')
        links = f'<a href="{new}">Vánoční novinka</a><a href="https://evil.example/vanocni">Vánoce</a><a href="{u}">Běžná schůze</a><a rel="next" href="{index}?page=2">2</a>'
        details, more = c.discover(links,index,s)
        self.assertEqual(details,[new])
        self.assertEqual(len(more),1)
        class Fetcher:
            stats = {}
            urls = []
            def get(self,url):
                self.urls.append(url)
                if url in s['index_urls']: return links.encode()
                return b'<h1>Vanocni novinka</h1><div class="event-detail">Only poster</div>'
        with tempfile.TemporaryDirectory() as tmp:
            f = Fetcher()
            out = c.collect(dict(REGISTRY,sources=[s]),Path(tmp)/'db',Path(tmp)/'out',{},f)
            self.assertEqual(len(f.urls),3) # two configured indices, one capped detail
            self.assertEqual(out['metrics']['reviewCount'],1)
            self.assertEqual(out['sources'][0]['status'],'partial')

    def test_database_write_failure_is_fatal(self):
        c = collector()
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'db'
            con = sqlite3.connect(path)
            con.execute('CREATE TABLE events(id TEXT PRIMARY KEY, source_id TEXT,url TEXT,fingerprint TEXT,payload TEXT,observed_at TEXT)')
            con.execute("CREATE TRIGGER fail BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'disk failure'); END")
            con.commit();con.close()
            s = dict(REGISTRY['sources'][0],index_urls=['https://www.plasy.cz/index'],seed_urls=REGISTRY['sources'][0]['seed_urls'][:1])
            body = (RESEARCH/'pilot-plzensky/fixtures/plasy_tree.html').read_bytes()
            class F:
                stats = {}
                def get(self,url): return body
            with self.assertRaises(sqlite3.Error): c.collect(dict(REGISTRY,sources=[s]),path,Path(tmp)/'out',{},F())

    def test_robots_crawl_delay_is_respected(self):
        import time
        c = collector()
        times = []
        def send(url,headers):
            times.append(time.monotonic())
            return (200,{},b'User-agent: *\nDisallow:\nCrawl-delay: 1\n') if url.endswith('/robots.txt') else (200,{},b'ok')
        with tempfile.TemporaryDirectory() as tmp:
            http = c.HTTPClient(tmp,send=send,min_interval=0)
            http.get('https://www.plasy.cz/test')
            self.assertGreaterEqual(times[1]-times[0],0.99)

    def test_http_cache_validators_304_hash_and_robots(self):
        c = collector()
        calls = []
        body = b'<h1>same bytes</h1>'
        def send(url, headers):
            calls.append((url, dict(headers)))
            if url.endswith('/robots.txt'):
                return 200, {}, b'User-agent: AdventCeskoPilot\nDisallow: /blocked\n'
            if 'If-None-Match' in headers:
                return 304, {}, b''
            return 200, {'ETag': '"abc"', 'Last-Modified': 'Thu, 12 Nov 2026 12:00:00 GMT'}, body
        with tempfile.TemporaryDirectory() as tmp:
            http = c.HTTPClient(tmp, send=send, min_interval=0)
            url = 'https://www.plasy.cz/test%2Dexact'
            self.assertEqual(http.get(url), body)
            self.assertEqual(http.get(url), body)
            self.assertEqual(http.stats['http304'], 1)
            self.assertEqual(calls[-1][1]['If-None-Match'], '"abc"')
            self.assertIn('If-Modified-Since', calls[-1][1])
            self.assertEqual(calls[-1][0], url)
            with self.assertRaises(OSError): http.get('https://www.plasy.cz/blocked')
            cached = json.loads(next(Path(tmp).glob('*.json')).read_text())
            self.assertEqual(cached['sha256'], c.digest(body))
            self.assertEqual(len(calls), 3)


if __name__ == '__main__':
    unittest.main()
