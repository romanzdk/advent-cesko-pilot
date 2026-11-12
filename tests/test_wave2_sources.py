"""Wave2: primary fragments, isolated SQLite, no private/ dependency or network."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/national-sources'
spec = importlib.util.spec_from_file_location('wave2_collector', ROOT / 'scripts/collector.py')
assert spec is not None and spec.loader is not None
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
REGISTRY = json.loads((ROOT / 'data/sources.json').read_text())


class Wave2SourcesTests(unittest.TestCase):
    def test_wave2_registry_seedless_discovery_and_field_provenance(self):
        cases = json.loads((FIXTURES / 'wave2-galileo.json').read_text())
        cases.append(dict(sourceId='lanskroun-kultura', url='https://www.kclanskroun.cz/festival/adventni-lanskroun/',
                          html=(FIXTURES / 'lanskroun.html').read_text(),
                          expected=dict(town='Lanškroun', region='Pardubický kraj', date='2026-11-29',
                                        endDate='2026-12-20', startTime=None, endTime=None,
                                        venue='náměstí J. M. Marků', price=None)))
        for case in cases:
            with self.subTest(source=case['sourceId']), tempfile.TemporaryDirectory() as tmp:
                source = next((s for s in REGISTRY['sources'] if s['id'] == case['sourceId']), None)
                self.assertIsNotNone(source, 'Verified wave2 source must be registered')
                assert source is not None
                self.assertEqual(source['seed_urls'], [])
                self.assertLessEqual(len(source['index_urls']), 2)
                self.assertEqual(source['max_details'], 14)
                path = Path(tmp)
                (path / 'index.html').write_text(f'<a href="{case["url"]}">Adventní program</a>')
                (path / 'detail.html').write_text(case['html'])
                (path / 'manifest.json').write_text(json.dumps({source['index_urls'][0]: 'index.html', case['url']: 'detail.html'}))
                result = c.collect(dict(REGISTRY, sources=[source]), path / 'db', path / 'out', {}, c.FixtureClient(path / 'manifest.json'))
                self.assertEqual(result['metrics']['eventsPublished'], 1)
                self.assertFalse(result['complete'])
                event = json.loads((path / 'out/events.json').read_text())['events'][0]
                for key, expected in case['expected'].items():
                    self.assertEqual(event[key], expected, key)
                self.assertEqual(event['sourceUrl'], case['url'])
                with self.assertRaises(c.Review):
                    c.parse_event(case['html'].replace(case['expected']['venue'], 'Neověřená obec'), source, case['url'], REGISTRY['window'])

    def test_lanskroun_explicit_shared_year_range_is_not_single_end_day(self):
        html = (FIXTURES / 'lanskroun.html').read_text()
        source = dict(id='lanskroun-kultura', adapter='lanskroun', town='Lanškroun',
                      region='Pardubický kraj', allowed_venues=['náměstí J. M. Marků'])
        url = 'https://www.kclanskroun.cz/festival/adventni-lanskroun/'
        event = c.parse_event(html, source, url, REGISTRY['window'])
        self.assertEqual((event['date'], event['endDate'], event['venue']),
                         ('2026-11-29', '2026-12-20', 'náměstí J. M. Marků'))
        self.assertIsNone(event['startTime'])
        self.assertIsNone(event['endTime'])
        self.assertIsNone(event['price'])
        self.assertTrue(any('nepřetržitého' in note for note in event['notes']))
        for old, new in [('29. 11 - 20. 12. 2026', '29. 11 - 20. 12.'),
                         ('29. 11 - 20. 12. 2026', '29. 11. 2026, 20. 12. 2026'),
                         ('29. 11 - 20. 12. 2026', '29. 12 - 20. 11. 2026'),
                         ('29. 11 - 20. 12. 2026', '31. 11 - 20. 12. 2026'),
                         ('29. 11 - 20. 12. 2026', '29. 11. 2026 - 20. 12. 2027'),
                         ('na náměstí J. M. Marků', 'v sousední obci'),
                         ('kulturnímu programu', 'vstupné 100 Kč; kulturnímu programu'),
                         ('kulturnímu programu', 'Příspěvky jsou dobrovolné; kulturnímu programu'),
                         ('Adventní Lanškroun</h1>', 'Adventní Lanškroun — vstupné 100 Kč</h1>'),
                         ('kulturnímu programu', 'Akce se koná 30. 11. 2026 – 19. 12. 2026; kulturnímu programu')]:
            with self.subTest(value=new), self.assertRaises(c.Review):
                c.parse_event(html.replace(old, new), source, url, REGISTRY['window'])
        with self.assertRaises(c.Excluded):
            c.parse_event(html.replace('20. 12. 2026', '25. 12. 2026'), source, url, REGISTRY['window'])
        with self.assertRaises(c.Review):
            c.parse_event(html + '<script type="application/ld+json">{"@type":"Event","name":"Advent","startDate":"2026-11-29"}</script>',
                          source, url, REGISTRY['window'])
        with self.assertRaises(c.Review):
            c.parse_event(html.replace('</h1>', '</h1><div class="festival-top__datum-konani">1. 12 - 2. 12. 2026</div>'),
                          source, url, REGISTRY['window'])


if __name__ == '__main__':
    unittest.main()
