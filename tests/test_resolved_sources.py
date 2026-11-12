"""Portable factual excerpts from verified primary captures; no private/network dependency."""
import copy
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from test_collector import collector, ROOT

FIX = ROOT / 'tests/fixtures/resolved'

def load(name):
    return json.loads((FIX / name).read_text())

class ResolvedSourcesTests(unittest.TestCase):
    def setUp(self):
        self.c = collector()
        self.registry = json.loads((ROOT/'data/sources.json').read_text())

    def test_policy_exclusions_clear_public_and_manual_review_without_hiding_unknown_geo(self):
        source = copy.deepcopy(self.registry['sources'][0])
        url = source['seed_urls'][0]
        source['seed_urls'] = [url]
        valid = '<h1>Vánoční trhy</h1><div class="event-detail"><div class="action-date">5. 12. 2026 17:00</div><div class="venue">Plasy</div></div>'
        pages = {u:b'' for u in source['index_urls']}
        pages[url] = valid
        class F:
            stats = {}
            def get(self,u): return pages[u]
        with tempfile.TemporaryDirectory() as tmp:
            db,out = Path(tmp)/'db',Path(tmp)/'out'
            def collect(): return self.c.collect(dict(self.registry,sources=[source]),db,out,{},F())
            self.assertEqual(collect()['metrics']['eventsPublished'],1)
            pages[url] = valid.replace('5. 12. 2026','5. 12. 2025')
            result = collect()
            self.assertEqual((result['metrics']['eventsPublished'],result['metrics']['reviewCount'],result['metrics']['excludedCount']),(0,0,1))
            self.assertEqual(result['sources'][0]['excludedCount'],1)
            self.assertIn('Programový výběr',result['sources'][0]['sourceNote'])
            pages[url] = valid.replace('class="venue">Plasy','class="venue">Babina')
            self.assertEqual(collect()['metrics']['reviewCount'],1)
            pages[url] = valid.replace('Vánoční trhy','Zájezd: vánoční trhy')
            result = collect()
            self.assertEqual((result['metrics']['reviewCount'],result['metrics']['excludedCount']),(0,1))
            with closing(sqlite3.connect(db)) as con:
                self.assertEqual(con.execute('select count(*) from exclusions').fetchone()[0],1)
            pages[url] = valid
            self.assertEqual(collect()['metrics']['excludedCount'],0)

    def test_structured_projection_honors_locality_status_and_prague_calendar(self):
        source = self.registry['sources'][2]
        f = load('kc-facts.json')[0]
        event = self.c.structured_event(self.c.DOM((FIX/f['file']).read_text()).root)
        def parse(value):
            return self.c.parse_event('<script type="application/ld+json">'+json.dumps(value)+'</script><footer>Vstup 999 Kč, zrušeno</footer>',source,f['url'],self.registry['window'])
        changed = copy.deepcopy(event)
        changed['location']['address']['addressLocality'] = 'Praha'
        with self.assertRaises(self.c.Review): parse(changed)
        changed = copy.deepcopy(event)
        changed.update(startDate='2026-12-02T23:30:00Z',eventStatus='https://schema.org/EventCancelled',description='Pouze pro členy; rezervace nutná.')
        result = parse(changed)
        self.assertEqual((result['date'],result['startTime']),('2026-12-03','00:30'))
        self.assertEqual(result['status'],'cancelled')
        self.assertEqual(result['audience'],'senioři / omezené zaměření')
        self.assertTrue(result['registration'])
        changed['description'] = 'Zveme členy, přátele společnosti a veřejnost.'
        self.assertEqual(parse(changed)['audience'],'všichni')
        changed['startDate'] = '2026-12-03'
        self.assertIsNone(parse(changed)['startTime'])

    def test_four_actual_kc_events_preserve_published_offer_variants(self):
        source = self.registry['sources'][2]
        facts = load('kc-facts.json')
        self.assertEqual(len(facts),4)
        expected = ['Základní vstupné: 990–1590 Kč',None,'Vstupné v předpodeji: 300 Kč; Vstupné na místě: 350 Kč','Základní vstupné: 80 Kč']
        for f,price in zip(facts,expected):
            with self.subTest(url=f['url']):
                body = (FIX/f['file']).read_text()
                e = self.c.parse_event(body+'<footer>Vstupné 9999 Kč, zrušeno, pouze pro členy</footer>',source,f['url'],self.registry['window'])
                self.assertEqual(e['price'],price)
                self.assertEqual(e['title'],f['title'])
                self.assertEqual((e['date'],e['startTime']), (f['start'][:10],f['start'][11:16]))
                self.assertEqual(e['venue'],f['venue'])
                self.assertIsNone(e['endTime'])
                self.assertEqual(e['status'],'confirmed')
                self.assertEqual(e['audience'],'všichni')
                self.assertNotIn('InStock',json.dumps(e))

    def test_changed_structured_detail_without_event_is_held_for_review(self):
        source = self.registry['sources'][2]
        with self.assertRaises(self.c.Review):
            self.c.parse_event('<h1>Vánoce</h1><main>Detail jen na plakátu</main>',source,source['seed_urls'][0],self.registry['window'])

    def test_kc_source_replaces_blocked_municipal_source_without_shrinking_budget(self):
        self.assertEqual(len(self.registry['sources']),6)
        self.assertEqual(len({s['region'] for s in self.registry['sources']}),3)
        s = self.registry['sources'][2]
        self.assertEqual(s['id'],'cz-semily-kcgolf')
        self.assertEqual((s['adapter'],s['max_details']),('structured',14))
        self.assertIn('robots.txt',s['coverage_note'])
        self.assertIn('KC Golf',s['coverage_note'])
        pages = {s['index_urls'][0]:b''}
        pages.update({f['url']:(FIX/f['file']).read_bytes() for f in load('kc-facts.json')})
        class F:
            stats = {}
            def get(self,url): return pages[url]
        with tempfile.TemporaryDirectory() as tmp:
            result = self.c.collect(dict(self.registry,sources=[s]),Path(tmp)/'db',Path(tmp)/'out',{},F())
            self.assertEqual(result['metrics']['eventsPublished'],4)
            self.assertEqual(result['sources'][0]['coverageNote'],s['coverage_note'])

    def test_mapping_is_invalidated_by_date_venue_or_source_identity_changes(self):
        f = load('plasy-facts.json')[1]
        source = copy.deepcopy(self.registry['sources'][0])
        body = (FIX/f['file']).read_text()
        for changed in [body.replace('27. 11.', '28. 11.'), body.replace('class="venue">Babina', 'class="venue">Plasy'), body.replace('class="venue">Babina', 'class="venue">Babina kulturní dům')]:
            with self.subTest(changed=changed), self.assertRaises(self.c.Review):
                self.c.parse_event(changed,source,f['url'],self.registry['window'])
        source['id'] = 'other-source'
        with self.assertRaises(self.c.Review):
            self.c.parse_event(body,source,f['url'],self.registry['window'])

    def test_changed_mapping_and_unknown_geography_are_not_policy_exclusions(self):
        f = load('plasy-facts.json')[1]
        source = self.registry['sources'][0]
        body = (FIX/f['file']).read_text().replace('27. 11. 2026','27. 11. 2025')
        for url in [f['url'],source['seed_urls'][0]]:
            with self.assertRaises(self.c.Review) as caught:
                self.c.parse_event(body,source,url,self.registry['window'])
            self.assertNotIsInstance(caught.exception,self.c.Excluded)

    def test_mapping_accepts_only_nfkc_whitespace_casefold_equivalence(self):
        f = load('plasy-facts.json')[2]
        source = self.registry['sources'][0]
        body = (FIX/f['file']).read_text()
        e = self.c.parse_event(body.replace('class="venue">Horní Hradiště','class="venue">  HORNÍ\u00a0 HRADIŠTĚ '),source,f['url'],self.registry['window'])
        self.assertEqual(e['town'],'Horní Hradiště')
        for venue in ['Horni Hradiste','Horní Hradiště II']:
            with self.assertRaises(self.c.Review):
                self.c.parse_event(body.replace('class="venue">Horní Hradiště','class="venue">'+venue),source,f['url'],self.registry['window'])

    def test_six_verified_plasy_localities_publish_with_their_own_centres(self):
        facts = load('plasy-facts.json')
        self.assertEqual(len(facts), 6)
        source = copy.deepcopy(self.registry['sources'][0])
        source['seed_urls'] = [e['url'] for e in facts]
        pages = {e['url']:(FIX/e['file']).read_bytes() for e in facts}
        pages.update({u:b'' for u in source['index_urls']})
        class F:
            stats = {}
            def get(self, url): return pages[url]
        locations = json.loads((ROOT/'data/locations.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            db, out = Path(tmp)/'db', Path(tmp)/'out'
            result = self.c.collect(dict(self.registry, sources=[source]), db, out, locations, F())
            self.assertEqual(result['metrics']['eventsPublished'], 6)
            events = {e['sourceUrl']:e for e in json.loads((out/'events.json').read_text())['events']}
            for f in facts:
                e = events[f['url']]
                self.assertEqual((e['town'],e['date'],e['startTime'],e['title']), (f['town'],f['date'],f['startTime'],f['title']))
                self.assertEqual(e['location'],locations[f['locationKey']])
                self.assertEqual(set(e['location']), {'lat','lon','precision','label','sourceUrl'})
                self.assertEqual(e['location']['precision'], 'town')
                self.assertIn('nikoli',e['location']['label'])
                self.assertTrue(any('Plas' in note and 'orientační' in note for note in e['notes']))
                self.assertNotIn('locationKey', e)
            with closing(sqlite3.connect(db)) as con:
                self.assertEqual(con.execute("select count(distinct event_id) from provenance where field='town'").fetchone()[0],6)
                self.assertEqual(con.execute("select count(*) from provenance where source_url like 'https://www.openstreetmap.org/%' and body_hash is not null").fetchone()[0],0)
