"""Portable primary-source fragments; isolated SQLite and no network fallback."""
import copy
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/national-sources'
spec = importlib.util.spec_from_file_location('national_collector', ROOT / 'scripts/collector.py')
assert spec is not None and spec.loader is not None
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
REGISTRY = json.loads((ROOT / 'data/sources.json').read_text())
WINDOW = REGISTRY['window']


class NationalSourceTests(unittest.TestCase):
    def test_hranice_inclusive_audience_tags_are_not_access_restrictions(self):
        html = (FIXTURES / 'hranice.html').read_text().replace('</article>',
            '<p><span class="popisek">Štítky</span>pro děti, pro rodiny, pro seniory</p></article>')
        source = dict(adapter='hranice', town='Hranice', region='Olomoucký kraj', allowed_venues=['Evangelický kostel'])
        url = 'https://kultura-hranice.cz/akce/adventni-koncert-s-zaves-2/'
        self.assertEqual(c.parse_event(html, source, url, WINDOW)['audience'], 'všichni')
        restricted = html.replace('Adventní koncert s Žaves se koná', 'Pouze pro členy. Adventní koncert s Žaves se koná')
        self.assertEqual(c.parse_event(restricted, source, url, WINDOW)['audience'], 'senioři / omezené zaměření')

    def test_jsonld_cannot_bypass_new_html_adapter_interval_guards(self):
        for adapter, town, region, fixture, venue in [
            ('hranice', 'Hranice', 'Olomoucký kraj', 'hranice.html', 'Evangelický kostel'),
            ('visitzlin', 'Zlín', 'Zlínský kraj', 'visitzlin.html', 'náměstí Míru, Zlín'),
        ]:
            with self.subTest(adapter=adapter):
                event = dict(**{'@type': 'Event'}, name='Adventní program', startDate='2026-12-01T17:00:00',
                             location=dict(name=venue, address=dict(addressLocality=town)))
                html = (FIXTURES / fixture).read_text() + '<script type="application/ld+json">' + json.dumps(event) + '</script>'
                source = dict(adapter=adapter, town=town, region=region, allowed_venues=[venue])
                with self.assertRaises(c.Review):
                    c.parse_event(html, source, 'https://example.cz/advent', WINDOW)

    def test_new_adapters_hold_long_prices_instead_of_losing_variants(self):
        for adapter, town, region, fixture, venue, old_price in [
            ('hranice', 'Hranice', 'Olomoucký kraj', 'hranice.html', 'Evangelický kostel', 'dobrovolné'),
            ('visitzlin', 'Zlín', 'Zlínský kraj', 'visitzlin.html', 'náměstí Míru, Zlín', 'zdarma'),
            ('wpem', 'Ústí nad Labem', 'Ústecký kraj', 'wpem.html', 'Brněnská 1000/1a, 400 01 Ústí nad Labem',
             'Cena workshopů: od 200 Kč (materiál je v ceně)'),
        ]:
            with self.subTest(adapter=adapter):
                # Synthetic length-boundary mutation, not claimed as a published tariff.
                html = (FIXTURES / fixture).read_text().replace(old_price, 'Cenová varianta: 100 Kč; ' * 12)
                source = dict(adapter=adapter, town=town, region=region, allowed_venues=[venue])
                with self.assertRaises(c.Review):
                    c.parse_event(html, source, 'https://example.cz/advent', WINDOW)

    def test_visitzlin_labelled_clock_and_multiday_opening_hours(self):
        html = (FIXTURES / 'visitzlin.html').read_text().replace('<p><strong>Místo:', '<p><strong>Čas:</strong> 14.00–16.30</p><p><strong>Místo:')
        source = dict(adapter='visitzlin', town='Zlín', region='Zlínský kraj', allowed_venues=['náměstí Míru, Zlín'])
        url = 'https://visitzlin.eu/kalendar-akci/adventni-zlin-2026'
        single = html.replace('23.12.2026', '27.11.2026')
        event = c.parse_event(single, source, url, WINDOW)
        self.assertEqual((event['startTime'], event['endTime']), ('14:00', '16:30'))
        self.assertIsNone(c.parse_event(html, source, url, WINDOW)['startTime'])
        for clock in ['17.00, 19.00', '29.00', '14.00–25.00']:
            with self.subTest(clock=clock), self.assertRaises(c.Review):
                c.parse_event(single.replace('14.00–16.30', clock), source, url, WINDOW)

    def test_new_towns_have_sourced_approximate_centres(self):
        locations = json.loads((ROOT / 'data/locations.json').read_text())
        for town in ['Nejdek', 'Dobruška', 'Hranice', 'Ústí nad Labem', 'Zlín']:
            with self.subTest(town=town):
                self.assertIn(town, locations)
                location = locations[town]
                self.assertEqual(location['precision'], 'town')
                self.assertIn('nikoli přesné', location['label'])
                self.assertRegex(location['sourceUrl'], r'^https://www\.openstreetmap\.org/relation/\d+$')

    def test_new_adapters_are_registered_and_collect_seedless_details(self):
        cases = [
            ('hranice-kultura', 'hranice.html', 'https://kultura-hranice.cz/akce/adventni-koncert-s-zaves-2/', '2026-12-12'),
            ('usti-muzeum', 'wpem.html', 'https://www.muzeumusti.cz/kalendar-akci/advent-v-muzeu-6/', '2026-11-28'),
            ('zlin-tic', 'visitzlin.html', 'https://visitzlin.eu/kalendar-akci/adventni-zlin-2026', '2026-11-27'),
        ]
        for sid, fixture, url, expected_date in cases:
            with self.subTest(source=sid), tempfile.TemporaryDirectory() as tmp:
                source = next((s for s in REGISTRY['sources'] if s['id'] == sid), None)
                self.assertIsNotNone(source, 'Verified national source is not registered')
                assert source is not None
                self.assertEqual(source['seed_urls'], [])
                path = Path(tmp)
                (path / 'index.html').write_text(f'<a href="{url}">Adventní program</a>')
                (path / 'detail.html').write_bytes((FIXTURES / fixture).read_bytes())
                (path / 'manifest.json').write_text(json.dumps({source['index_urls'][0]: 'index.html', url: 'detail.html'}))
                result = c.collect(dict(REGISTRY, sources=[source]), path / 'db', path / 'out', {}, c.FixtureClient(path / 'manifest.json'))
                self.assertEqual(result['metrics']['eventsPublished'], 1)
                self.assertFalse(result['complete'])
                self.assertEqual(json.loads((path / 'out/events.json').read_text())['events'][0]['date'], expected_date)

    def test_visitzlin_uses_labelled_interval_not_other_programme_dates(self):
        html = (FIXTURES / 'visitzlin.html').read_text()
        source = dict(id='zlin-tic', adapter='visitzlin', town='Zlín', region='Zlínský kraj',
                      allowed_venues=['náměstí Míru, Zlín'])
        url = 'https://visitzlin.eu/kalendar-akci/adventni-zlin-2026'
        event = c.parse_event(html, source, url, WINDOW)
        self.assertEqual((event['date'], event['endDate'], event['startTime'], event['price']),
                         ('2026-11-27', '2026-12-23', None, 'zdarma'))
        self.assertIsNone(event['endTime'])
        self.assertTrue(any('nepřetržitého' in n for n in event['notes']))
        for old, new in [('27.11.2026', '27.11.'), ('náměstí Míru, Zlín', 'Neznámá obec'),
                         (' - St 23.12.2026', ', St 23.12.2026')]:
            with self.subTest(value=new), self.assertRaises(c.Review):
                c.parse_event(html.replace(old, new), source, url, WINDOW)
        with self.assertRaises(c.Excluded):
            c.parse_event(html.replace('23.12.2026', '03.01.2027'), source, url, WINDOW)

    def test_wpem_preserves_published_clock_place_and_complete_price_label(self):
        html = (FIXTURES / 'wpem.html').read_text()
        source = dict(id='usti-muzeum', adapter='wpem', town='Ústí nad Labem', region='Ústecký kraj',
                      allowed_venues=['Brněnská 1000/1a, 400 01 Ústí nad Labem'])
        url = 'https://www.muzeumusti.cz/kalendar-akci/advent-v-muzeu-6/'
        event = c.parse_event(html, source, url, WINDOW)
        self.assertEqual((event['date'], event['startTime'], event['endTime'], event['venue'], event['price']),
                         ('2026-11-28', '10:00', '16:00', source['allowed_venues'][0],
                          'Cena workshopů: od 200 Kč (materiál je v ceně)'))
        self.assertTrue(event['registration'])
        self.assertTrue(any('od 4 let' in note for note in event['notes']))
        for old, new in [('2026-11-28', '11-28'), ('Ústí nad Labem', 'Jiná obec'),
                         ('"Location"', '"MissingLocation"'), ('10:00:00', '29:00:00'),
                         ('"startDate"', '"missingStart"'), ('16:00:00', '09:00:00')]:
            with self.subTest(value=new), self.assertRaises(c.Review):
                c.parse_event(html.replace(old, new), source, url, WINDOW)

    def test_hranice_labelled_fields_and_ambiguous_occurrences(self):
        html = (FIXTURES / 'hranice.html').read_text()
        source = dict(id='hranice-kultura', adapter='hranice', town='Hranice', region='Olomoucký kraj',
                      allowed_venues=['Evangelický kostel'])
        url = 'https://kultura-hranice.cz/akce/adventni-koncert-s-zaves-2/'
        event = c.parse_event(html, source, url, WINDOW)
        self.assertEqual((event['date'], event['startTime'], event['endTime'], event['venue'], event['price']),
                         ('2026-12-12', '17:00', None, 'Evangelický kostel', 'dobrovolné'))
        self.assertIsNone(event['registration'])
        for old, new in [('12. 12. 2026', '12. 12.'), ('17:00', '17:00, 19:00'),
                         ('17:00', '29:00'), ('Evangelický kostel', 'Jiná obec'),
                         ('12. 12. 2026', '12. 12. 2026, 13. 12. 2026'), ('Sobota', 'Do')]:
            with self.subTest(value=new), self.assertRaises(c.Review):
                c.parse_event(html.replace(old, new), source, url, WINDOW)
        with self.assertRaises(c.Excluded):
            c.parse_event(html.replace('12. 12. 2026', '25. 12. 2026'), source, url, WINDOW)

    def test_galileo_sources_discover_without_seeds_and_keep_provenance(self):
        cases = json.loads((FIXTURES / 'galileo.json').read_text())
        for case in cases:
            with self.subTest(source=case['sourceId']), tempfile.TemporaryDirectory() as tmp:
                source = next((s for s in REGISTRY['sources'] if s['id'] == case['sourceId']), None)
                self.assertIsNotNone(source, 'Verified national source is not registered')
                source = copy.deepcopy(source)
                assert source is not None
                source['seed_urls'] = []
                source['index_urls'] = source['index_urls'][:1]
                path = Path(tmp)
                (path / 'detail.html').write_text(case['html'])
                # Only the linked listing supplies this detail; bootstrap cannot mask a discovery failure.
                (path / 'index.html').write_text(f'<a href="{case["url"]}">Vánoční program</a>')
                (path / 'manifest.json').write_text(json.dumps({source['index_urls'][0]: 'index.html', case['url']: 'detail.html'}))
                result = c.collect(dict(REGISTRY, sources=[source]), path / 'events.sqlite', path / 'out', {}, c.FixtureClient(path / 'manifest.json'))
                self.assertEqual(result['metrics']['eventsPublished'], 1)
                self.assertFalse(result['complete'])
                event = json.loads((path / 'out/events.json').read_text())['events'][0]
                for key, expected in case['expected'].items():
                    self.assertEqual(event[key], expected, key)
                with closing(sqlite3.connect(path / 'events.sqlite')) as con:
                    evidence = con.execute('SELECT source_url,body_hash FROM provenance WHERE field="date"').fetchall()
                self.assertEqual(evidence, [(case['url'], c.digest(case['html']))])
                for old, new in [(case['expected']['venue'], 'Neověřené místo'), ('2026', '')]:
                    with self.subTest(change=new), self.assertRaises(c.Review):
                        c.parse_event(case['html'].replace(old, new), source, case['url'], WINDOW)


if __name__ == '__main__':
    unittest.main()
