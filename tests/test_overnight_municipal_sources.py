"""Portable factual checks for two municipal calendars; captures stay private."""
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


class OvernightMunicipalSources(unittest.TestCase):
    def source(self, source_id):
        matches = [s for s in json.loads((ROOT / 'data/sources.json').read_text())['sources'] if s['id'] == source_id]
        self.assertEqual(len(matches), 1, f'Missing approved source {source_id}')
        return deepcopy(matches[0])

    def reviewed(self, source_id, needle):
        source = self.source(source_id)
        url = next(u for u in source['event_reviews'] if needle in u)
        r = source['event_reviews'][url]
        body = fragment(r['expectedTitle'], r['expectedDate'], r['expectedVenue'], r['expectedEndDate'])
        r['contentHash'] = c.review_fingerprint(body, 'galileo')
        return c.parse_event(body, source, url, WINDOW), source, url, body

    def test_bounded_live_sources_use_existing_adapter(self):
        for source_id, town in [('dobroslavice-obec', 'Dobroslavice'), ('horni-lhota-obec', 'Horní Lhota')]:
            s = self.source(source_id)
            self.assertEqual((s['town'], s['region'], s['adapter']), (town, 'Moravskoslezský kraj', 'galileo'))
            self.assertEqual(s.get('max_index_pages', 2), 2)
            self.assertEqual(s.get('max_details', 14), 14)
            self.assertFalse(s['seed_urls'])
            self.assertTrue(s['allowed_venues'])


    def test_dobroslavice_poster_venue_and_public_conditions(self):
        event, _, _, _ = self.reviewed('dobroslavice-obec', 'rozsviceni-vanocniho-stromu-v-dobroslavicich')
        self.assertEqual(event['venue'], 'Autobusová zastávka v Dobroslavicích')
        self.assertIn('Hrníčky', ' '.join(event['notes']))
        event, _, _, _ = self.reviewed('dobroslavice-obec', 'tvoreni-adventnich-vencu')
        self.assertEqual(event['category'], 'tvoreni')
        self.assertIn('Materiál', ' '.join(event['notes']))
        self.assertIsNone(event['price'])

    def test_foreign_ostrava_programme_is_excluded(self):
        with self.assertRaises(c.Excluded):
            self.reviewed('dobroslavice-obec', 'advent-plny-kridleni')

    def test_duplicate_horni_lhota_tree_invitation_is_excluded(self):
        with self.assertRaises(c.Excluded):
            self.reviewed('horni-lhota-obec', 'rozsviceni-vanocniho-stromu-879')

    def test_jarmark_price_is_for_ride_not_admission(self):
        event, _, _, _ = self.reviewed('horni-lhota-obec', 'adventni-jarmark')
        self.assertEqual(event['venue'], 'Prostranství za obecním domem')
        self.assertIn('Jízda', event['price'])
        self.assertIn('vstupné na jarmark neuvedeno', event['price'])
        self.assertIn('16:30 živý Betlém', ' '.join(event['notes']))
        self.assertEqual(event['category'], 'trhy')

    def test_workshop_receipt_preserves_children_prices_booking_and_venues(self):
        source = self.source('horni-lhota-obec')
        url, receipt = next(iter(source['audited_events'].items()))
        fact = receipt['events'][0]
        body = fragment(receipt['expectedTitle'], fact['date'], '')
        receipt['contentHash'] = a.fingerprint(body, 'galileo')
        event = c.parse_event(body, source, url, WINDOW)
        self.assertEqual((event['date'], event['startTime'], event['endTime']), ('2026-12-06', '14:30', None))
        self.assertEqual(event['audience'], 'všichni')
        self.assertEqual(event['category'], 'tvoreni')
        self.assertIn('Děti: dílny zdarma', event['price'])
        self.assertIn('mikulášský balíček 100 Kč', event['price'])
        self.assertIn('29. 11. 2026', event['registration'])
        self.assertIn('tělocvična', event['venue'])
        self.assertIn('17:30', ' '.join(event['notes']))
        with self.assertRaises(c.Review):
            c.parse_event(body.replace('Veřejný adventní program.', 'Změněný program.'), source, url, WINDOW)

    def test_new_venue_or_changed_review_fails_closed(self):
        _, source, url, body = self.reviewed('horni-lhota-obec', 'adventni-jarmark')
        with self.assertRaises(c.Review):
            c.parse_event(body.replace('Veřejný adventní program.', 'Změněný program.'), source, url, WINDOW)
        new_url = source['detail_prefixes'][0] + 'vanocni-akce-9999_9999cs.html'
        with self.assertRaises(c.Review):
            c.parse_event(fragment('Vánoční akce', '2026-12-05', 'Ostrava-Poruba'), source, new_url, WINDOW)


if __name__ == '__main__':
    unittest.main()
