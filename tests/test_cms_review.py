"""Release regressions from primary CMS HTML; portable factual fragments only."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/cms-review'
spec = importlib.util.spec_from_file_location('review_collector', ROOT / 'scripts/collector.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
REGISTRY = json.loads((ROOT / 'data/sources.json').read_text())
WINDOW = REGISTRY['window']


class CMSReviewTests(unittest.TestCase):
    def test_drupal_three_range_endpoints_are_held_for_review(self):
        source = next(s for s in REGISTRY['sources'] if s['adapter'] == 'drupal')
        html = (FIXTURES / 'kurim-stezka.html').read_text()
        html = html.replace('</span></div>', '<time datetime="2026-12-22T19:00:00+01:00">22/12</time></span></div>', 1)
        with self.assertRaises(c.Review):
            c.parse_event(html, source, source['seed_urls'][0], WINDOW)

    def test_public_validator_rejects_end_outside_season(self):
        spec = importlib.util.spec_from_file_location('review_validator', ROOT / 'scripts/validate_public.py')
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        source = next(s for s in REGISTRY['sources'] if s['town'] == 'Jilemnice')
        event = c.parse_event((FIXTURES / 'jilemnice-noid.html').read_bytes(), source,
                              source['seed_urls'][0], WINDOW)
        data = dict(schemaVersion=1, generatedAt=c.now(), season=2026, region='Česko', events=[event])
        for end in ('2026-12-25', '2027-12-22'):
            event['endDate'] = end
            with self.subTest(end=end), self.assertRaises(ValueError):
                validator.validate(data)

    def test_range_end_outside_window_is_held_not_truncated(self):
        source = next(s for s in REGISTRY['sources'] if s['adapter'] == 'drupal')
        html = (FIXTURES / 'kurim-stezka.html').read_text()
        for end in ('2026-12-25', '2027-12-22'):
            with self.subTest(end=end), self.assertRaises(c.Review):
                c.parse_event(html.replace('2026-12-22T', end + 'T'), source,
                              source['seed_urls'][0], WINDOW)

    def test_noid_price_preserves_source_range_not_just_cheaper_endpoint(self):
        source = next(s for s in REGISTRY['sources'] if s['town'] == 'Jilemnice')
        e = c.parse_event((FIXTURES / 'jilemnice-noid.html').read_bytes(), source,
                          source['seed_urls'][0], WINDOW)
        self.assertEqual(e['price'], '1390 – 990 Kč')

    def test_drupal_explicit_ranges_preserve_both_endpoint_times(self):
        source = next(s for s in REGISTRY['sources'] if s['adapter'] == 'drupal')
        for filename, start, end in [
            ('kurim-stezka.html', '2026-11-30', '2026-12-22'),
            ('kurim-krajka.html', '2026-12-02', '2026-12-21'),
        ]:
            with self.subTest(filename=filename):
                e = c.parse_event((FIXTURES / filename).read_bytes(), source,
                                  source['seed_urls'][0], WINDOW)
                self.assertEqual((e['date'], e['endDate'], e['startTime'], e['endTime']),
                                 (start, end, '09:00', '18:00'))
                self.assertTrue(any('nepřetržitého ani každodenního' in n for n in e['notes']))


if __name__ == '__main__':
    unittest.main()
