"""November 21 editorial deltas and strict Posázaví correction binding."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import collector as c


def page(end=None, image='https://example.cz/poster.png'):
    event = {'@context': 'https://schema.org', '@type': 'Event',
             'name': 'Vánoční tržiště ve prospěch Hospic Dobrého Pastýře',
             'startDate': '2026-11-29T13:00:00+01:00', 'image': image,
             'location': {'@type': 'Place', 'name': 'Kulturní dům Čerčany',
                          'address': {'@type': 'PostalAddress', 'addressLocality': 'Čerčany'}}}
    if end:
        event['endDate'] = end
    return '<h1>Vánoční tržiště</h1><script type="application/ld+json">' + json.dumps(event, ensure_ascii=False) + '</script>'


import sqlite3
import tempfile
import re
import reviewed_public

MARKET_URL = 'https://tourist.posazavi.com/cz/kalendar-akci/46727-vanocni-trziste-ve-prospech-hospic-dobreho-pastyre.html'
NEW_FACTS = {
    'e-b1af12e0a050d855': ('Přestavlky u Čerčan', '2026-11-22', None, None, 'reviewed-prestavlky-advent-2026'),
    'e-05a4eaf823581eb1': ('Přestavlky u Čerčan', '2026-11-28', '16:00', None, 'reviewed-prestavlky-advent-2026'),
    'e-510740de107f7398': ('Lštění', '2026-11-28', '16:00', '19:00', 'reviewed-lsteni-advent-2026'),
    'e-bb4c321bbaaa07b6': ('Borová Lhota (Pyšely)', '2026-11-28', '15:00', None, 'reviewed-borova-lhota-2026'),
    'e-12735559062e1155': ('Lštění', '2026-11-29', '14:00', '16:00', 'reviewed-lsteni-advent-2026'),
    'e-3993e134c57ca543': ('Čerčany', '2026-12-05', '20:00', None, 'reviewed-cercany-bessoni-2026'),
}


class November21EditorialFacts(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / 'data/sources.json').read_text())
        self.sources = self.registry['sources']
        self.feed = json.loads((ROOT / 'data/reviewed-events.json').read_text())
        self.events = {e['id']: e for e in self.feed['events']}

    def test_exact_primary_town_bindings_null_points_and_factual_clocks(self):
        for eid, facts in NEW_FACTS.items():
            e = self.events[eid]
            town, day, start, end, owner = facts
            self.assertEqual((e['town'], e['date'], e['startTime'], e['endTime']), (town, day, start, end))
            self.assertIsNone(e['location'])
            self.assertIsNone(e['endDate'])
            self.assertEqual(reviewed_public.binding(e, self.sources)['id'], owner)
            self.assertEqual([s['id'] for s in self.sources if re.fullmatch(s['url_regex'], e['sourceUrl'])], [owner])
            for change in [dict(sourceUrl=e['sourceUrl']+'?other=1'), dict(sourceUrl=e['sourceUrl']+'#poster'),
                           dict(sourceUrl=e['sourceUrl'].replace('https://www.', 'https://foreign.')),
                           dict(sourceUrl=e['sourceUrl'].replace('.html', '-unapproved.html')),
                           dict(town='Praha'), dict(region='Hlavní město Praha'), dict(location={'lat': 50, 'lon': 14})]:
                with self.subTest(id=eid, change=change), self.assertRaises(ValueError):
                    reviewed_public.binding(dict(e, **change), self.sources)
        _, records, invalid = reviewed_public.decode(json.dumps(self.feed, ensure_ascii=False).encode(), self.sources, self.registry, {})
        self.assertEqual(invalid, [])
        self.assertEqual({e['id']: e for _, e in records}, self.events)

    def test_unknowns_volatility_and_programme_times_remain_explicit(self):
        trail = self.events['e-b1af12e0a050d855']
        self.assertIn('celý týden', trail['description'])
        self.assertIn('konečné datum', ' '.join(trail['notes']))
        self.assertIsNone(trail['venue'])
        self.assertEqual(trail['status'], 'time-unconfirmed')
        self.assertIn('17:00', self.events['e-510740de107f7398']['description'])
        self.assertIsNone(self.events['e-bb4c321bbaaa07b6']['price'])
        self.assertIn('Vstupné dobrovolné', self.events['e-12735559062e1155']['price'])
        self.assertIn('povinnost rezervace', self.events['e-12735559062e1155']['registration'])
        self.assertIn('nejsou zaručeny', self.events['e-3993e134c57ca543']['description'])
        for eid in NEW_FACTS:
            self.assertNotIn('@', json.dumps(self.events[eid]))
        wreath = self.events['e-2a25cd0b98ed6aba']
        self.assertIn('4 volná z 15', wreath['registration'])
        self.assertIn('21.11.2026', wreath['registration'])
        self.assertEqual(wreath['verifiedAt'], '2026-11-21T08:32:42.733562+00:00')
        tree = self.events['e-c03f5e83a5330fbf']
        self.assertEqual((tree['startTime'], tree['endTime']), ('16:00', '19:00'))
        self.assertEqual(reviewed_public.binding(tree, self.sources)['id'], 'reviewed-www-chocerady-cz')
        self.assertIn('17:00', tree['description'])
        self.assertIn('orientační', ' '.join(tree['notes']))
        self.assertTrue(any('file=5598' in n for n in tree['notes']))
        self.assertNotIn('e-aacd4dfa028ba519431c', self.events)

    def test_municipal_live_owner_is_not_shadowed_by_reviewed_cercany(self):
        matches = [s['id'] for s in self.sources if re.fullmatch(s['url_regex'], MARKET_URL) and s['town']=='Čerčany']
        self.assertEqual(matches, ['cercany-posazavi-calendar'])
        source = next(s for s in self.sources if s['id']==matches[0])
        receipt = source['event_reviews'][MARKET_URL]
        self.assertEqual(receipt['expectedVenue'], 'Kulturní dům Čerčany')
        self.assertEqual(receipt['overrides']['endTime'], '18:00')
        self.assertIn('16:00', ' '.join(receipt['overrides']['notes']))


class PosazaviReviewBinding(unittest.TestCase):
    def test_real_sqlite_changed_payload_withdraws_only_bound_event(self):
        registry = json.loads((ROOT / 'data/sources.json').read_text())
        source = deepcopy(next(s for s in registry['sources'] if s['id']=='cercany-posazavi-calendar'))
        original = page()
        source['event_reviews'][MARKET_URL]['contentHash'] = c.review_fingerprint(original, 'posazavi')
        registry['sources'] = [source]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base/'detail.html').write_text(original)
            for i in range(len(source['index_urls'])):
                (base/f'index{i}.json').write_text(json.dumps({'Data': [{'Title': 'Vánoční tržiště', 'DetailUrl': MARKET_URL}]}))
            manifest = {u:f'index{i}.json' for i,u in enumerate(source['index_urls'])}
            manifest[MARKET_URL] = 'detail.html'
            (base/'manifest.json').write_text(json.dumps(manifest))
            client = c.FixtureClient(base/'manifest.json')
            c.collect(registry,base/'events.sqlite',base/'out',{},client)
            con = sqlite3.connect(base/'events.sqlite')
            payload = json.loads(con.execute('SELECT payload FROM events WHERE id=?',('e-aacd4dfa028ba519431c',)).fetchone()[0])
            self.assertEqual(payload['endTime'], '18:00')
            self.assertEqual(payload['venue'], 'Kulturní dům, Sokolská 28, Čerčany')
            self.assertEqual(con.execute('SELECT source_id FROM events').fetchone()[0], source['id'])
            con.close()
            (base/'detail.html').write_text(page(image='https://example.cz/changed-poster.png'))
            c.collect(registry,base/'events.sqlite',base/'out',{},client)
            con = sqlite3.connect(base/'events.sqlite')
            self.assertEqual(con.execute('SELECT count(*) FROM events').fetchone()[0], 0)
            self.assertEqual(con.execute('SELECT source_id,url FROM reviews').fetchall(), [(source['id'],MARKET_URL)])
            self.assertIn('již neodpovídá', con.execute('SELECT reason FROM reviews').fetchone()[0])
            con.close()

    def test_identity_hash_and_fact_mismatches_reject_correction(self):
        registry = json.loads((ROOT / 'data/sources.json').read_text())
        source = deepcopy(next(s for s in registry['sources'] if s['id']=='cercany-posazavi-calendar'))
        source['event_reviews'][MARKET_URL]['contentHash'] = c.review_fingerprint(page(), 'posazavi')
        for field,value in [('sourceId','foreign'),('sourceTown','Praha'),('sourceUrl',MARKET_URL+'?x=1'),
                            ('expectedTitle','Different'),('expectedDate','2026-11-28'),
                            ('expectedEndDate','2026-11-30'),('expectedVenue','Different'),('contentHash','0'*64)]:
            changed = deepcopy(source)
            changed['event_reviews'][MARKET_URL][field]=value
            with self.subTest(field=field), self.assertRaises(c.Review):
                c.parse_event(page(), changed, MARKET_URL, registry['window'])

    def test_exact_structured_payload_changes_invalidate_fingerprint(self):
        original = page()
        fingerprint = c.review_fingerprint(original, 'posazavi')
        self.assertEqual(fingerprint, c.review_fingerprint('<nav>Different chrome</nav>' + original, 'posazavi'))
        for changed in [page(end='2026-11-29T16:00:00+01:00'),
                        page(image='https://example.cz/replaced.png'),
                        original.replace('13:00:00', '14:00:00'),
                        original.replace('Čerčany', 'Praha'),
                        original.replace('<h1>Vánoční tržiště</h1>', '<h1>Jiný nadpis</h1>')]:
            self.assertNotEqual(fingerprint, c.review_fingerprint(changed, 'posazavi'))
        for invalid in ['<h1>No Event</h1>', original + original, original.replace('<h1>', '<p>').replace('</h1>', '</p>')]:
            with self.assertRaises(c.Review):
                c.review_fingerprint(invalid, 'posazavi')
