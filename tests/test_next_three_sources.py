"""Portable factual regressions; full primary captures remain private."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import collector as c
import audited_events as a
from test_three_source_expansion import fragment, WINDOW

SOURCES = {
    'kraslice-mesto': ('Kraslice', 'Karlovarský kraj', 14),
    'cerveny-kostelec-ckzije': ('Červený Kostelec', 'Královéhradecký kraj', 18),
    'cz-nove-mesto-nad-metuji-calendar': ('Nové Město nad Metují', 'Královéhradecký kraj', 14),
}

class NextThreeSources(unittest.TestCase):
    def source(self, source_id):
        matches = [s for s in json.loads((ROOT / 'data/sources.json').read_text())['sources'] if s['id'] == source_id]
        self.assertEqual(len(matches), 1, f'Missing approved source {source_id}')
        return deepcopy(matches[0])

    def reviewed(self, source, needle, clock='15:30 - 18:00'):
        url = next(u for u in source['event_reviews'] if needle in u)
        receipt = source['event_reviews'][url]
        body = fragment(receipt['expectedTitle'], receipt['expectedDate'], receipt['expectedVenue'], receipt['expectedEndDate']).replace('15:30 - 18:00', clock)
        receipt['contentHash'] = c.review_fingerprint(body, 'galileo')
        return c.parse_event(body, source, url, WINDOW), body, url

    def test_compatible_sources_have_measured_budgets_and_honest_scope(self):
        for source_id, (town, region, maximum) in SOURCES.items():
            with self.subTest(source_id=source_id):
                source = self.source(source_id)
                self.assertEqual((source['adapter'], source['town'], source['region']), ('galileo', town, region))
                self.assertEqual(source.get('max_index_pages', 2), 2)
                self.assertEqual(source.get('max_details', 14), maximum)
                self.assertTrue(source['allowed_venues'])
                self.assertIn('omezen', source['coverage_note'].lower())
                self.assertFalse(source['seed_urls'])

    def test_exhibitions_are_not_markets_or_tree_lighting(self):
        source = self.source('kraslice-mesto')
        opening, _, _ = self.reviewed(source, 'vernisaz-vystavy')
        self.assertEqual(opening['category'], 'setkani')
        url = next(u for u in source['audited_events'] if '/vanocni-vystava-' in u)
        receipt = source['audited_events'][url]
        fact = receipt['events'][0]
        body = fragment(receipt['expectedTitle'], fact['date'], fact['venue'], fact['endDate'])
        receipt['contentHash'] = a.fingerprint(body, 'galileo')
        event = c.parse_event(body, source, url, WINDOW)
        self.assertEqual(event['category'], 'setkani')
        self.assertEqual((event['startTime'], event['endTime']), (None, None))
        self.assertNotIn('Čas zahájení není potvrzen', ' '.join(event['notes']))
        self.assertIn('10:00–17:00', ' '.join(event['notes']))
        self.assertIn('10:00–12:00', ' '.join(event['notes']))
        with self.assertRaises(c.Review):
            c.parse_event(body.replace('Veřejný adventní program.', 'Změněný program.'), source, url, WINDOW)

    def test_conflicting_kraslice_starts_remain_unknown(self):
        source = self.source('kraslice-mesto')
        for needle in ['prvni-advent', 'druhy-advent']:
            event, _, _ = self.reviewed(source, needle)
            self.assertEqual((event['startTime'], event['endTime']), (None, None))
            self.assertIn('15:30', ' '.join(event['notes']))

    def test_foreign_towns_and_parts_remain_held(self):
        source = self.source('cerveny-kostelec-ckzije')
        holds = [u for u, r in source['event_reviews'].items() if r['decision'] == 'hold']
        self.assertEqual(len(holds), 10)
        for url in holds:
            with self.subTest(url=url), self.assertRaises(c.Review):
                self.reviewed(source, url)
        url = source['detail_prefixes'][0] + 'vanocni-akce-9999_9999cs.html'
        with self.assertRaises(c.Review):
            c.parse_event(fragment('Vánoční akce', '2026-12-05', 'Neověřené místo'), source, url, WINDOW)

    def test_ck_price_variants_and_school_audience_are_preserved(self):
        source = self.source('cerveny-kostelec-ckzije')
        concert, _, _ = self.reviewed(source, 'vanocni-koncert-junior')
        self.assertIn('210 Kč', concert['price'])
        self.assertIn('150 Kč', concert['price'])
        self.assertIn('50%', concert['price'])
        theatre, _, _ = self.reviewed(source, 'pujdem-spolu-do-betlema', clock='10:45')
        self.assertEqual(theatre['category'], 'setkani')
        self.assertEqual(theatre['audience'], 'omezené zaměření')
        self.assertIn('omezená kapacita', ' '.join(theatre['notes']))
        self.assertIsNone(theatre['endTime'])

    def test_nove_mesto_conflicting_umbrella_hours_not_selected(self):
        source = self.source('cz-nove-mesto-nad-metuji-calendar')
        event, _, _ = self.reviewed(source, '1-adventni-nedele')
        self.assertEqual((event['startTime'], event['endTime']), (None, None))
        self.assertEqual(event['category'], 'trhy')
        self.assertIn('17:00', ' '.join(event['notes']))

    def test_changed_reviewed_details_are_withdrawn(self):
        for source_id, needle in [('cerveny-kostelec-ckzije', 'vanocni-koncert-junior'), ('cz-nove-mesto-nad-metuji-calendar', '1-adventni-nedele')]:
            source = self.source(source_id)
            _, body, url = self.reviewed(source, needle)
            with self.assertRaises(c.Review):
                c.parse_event(body.replace('Veřejný adventní program.', 'Jiný veřejný program.'), source, url, WINDOW)

if __name__ == '__main__':
    unittest.main()
