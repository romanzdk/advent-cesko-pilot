"""Posázaví regional calendar: JSON search listing per town, JSON-LD details checked against the source town."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import collector as c

WINDOW = {'from': '2026-11-20', 'through': '2026-12-24'}
REGISTRY = json.loads((ROOT / 'data/sources.json').read_text())
LOCATIONS = json.loads((ROOT / 'data/locations.json').read_text())
POSAZAVI = [s for s in REGISTRY['sources'] if s['adapter'] == 'posazavi']
DETAIL = 'https://tourist.posazavi.com/cz/kalendar-akci/46640-rozsviceni-vanocniho-stromu.html'


def detail(locality='Bystřice', venue='Ješutovo náměstí', start='2026-11-28T15:00:00+01:00'):
    event = {'@context': 'https://schema.org', '@type': 'Event', 'name': 'Rozsvícení vánočního stromu', 'startDate': start,
             'location': {'@type': 'Place', 'name': venue, 'address': {'@type': 'PostalAddress', 'addressLocality': locality}}}
    return f'<h1>Rozsvícení vánočního stromu</h1><script type="application/ld+json">{json.dumps(event, ensure_ascii=False)}</script>'


class PosazaviAdapter(unittest.TestCase):
    def source(self):
        return deepcopy(next(s for s in POSAZAVI if s['town'] == 'Bystřice'))

    def test_registered_sources_are_bounded_seedless_and_located(self):
        self.assertGreaterEqual(len(POSAZAVI), 10)
        towns = [s['town'] for s in REGISTRY['sources']]
        for s in POSAZAVI:
            with self.subTest(source=s['id']):
                self.assertEqual(towns.count(s['town']), 1)
                self.assertFalse(s['seed_urls'])
                self.assertLessEqual(s['max_index_pages'], 8)
                self.assertEqual(len(s['index_urls']), s['max_index_pages'])
                self.assertTrue(all(u.startswith('https://tourist.posazavi.com/Json/Search/Event.ashx?CityId=') for u in s['index_urls']))
                self.assertEqual(LOCATIONS[s['town']]['precision'], 'town')

    def test_listing_keeps_only_seasonal_same_host_details(self):
        body = json.dumps({'Data': [
            {'Title': 'Rozsvícení vánočního stromu', 'DetailUrl': '/cz/kalendar-akci/46640-rozsviceni-vanocniho-stromu.html'},
            {'Title': 'Hospodský kvíz', 'DetailUrl': '/cz/kalendar-akci/46275-hospodsky-kviz.html'},
            {'Title': 'Adventní koncert', 'DetailUrl': 'https://jinde.example.cz/cz/kalendar-akci/1-adventni-koncert.html'}]})
        source = self.source()
        self.assertEqual(c.discover(body, source['index_urls'][0], source), ([DETAIL], []))

    def test_matching_locality_publishes(self):
        event = c.parse_event(detail(), self.source(), DETAIL, WINDOW)
        self.assertEqual((event['town'], event['date'], event['startTime'], event['venue']), ('Bystřice', '2026-11-28', '15:00', 'Ješutovo náměstí'))

    def test_other_locality_missing_locality_or_venue_is_held(self):
        for page in (detail(locality='Bystřice - Líšno'), detail(locality=''), detail(venue='')):
            with self.subTest(page=page), self.assertRaises(c.Review):
                c.parse_event(page, self.source(), DETAIL, WINDOW)

    def test_missing_structured_data_is_held(self):
        with self.assertRaises(c.Review):
            c.parse_event('<h1>Rozsvícení vánočního stromu</h1><p>28. 11. 2026 15:00</p>', self.source(), DETAIL, WINDOW)

    def test_page_budget_ceiling_is_adapter_specific(self):
        registry = dict(REGISTRY, sources=[dict(self.source(), max_index_pages=9)])
        with self.assertRaises(ValueError):
            c.collect(registry, '/nonexistent/db', '/nonexistent/out', {}, None)
        galileo = next(s for s in REGISTRY['sources'] if s['adapter'] == 'galileo')
        with self.assertRaises(ValueError):
            c.collect(dict(REGISTRY, sources=[dict(galileo, max_index_pages=5)]), '/nonexistent/db', '/nonexistent/out', {}, None)


if __name__ == '__main__':
    unittest.main()
