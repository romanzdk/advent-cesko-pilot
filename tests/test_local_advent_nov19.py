"""Factual editorial receipts, 19 November: no production network in tests."""
import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import reviewed_public
import validate_public

FACTS = {
    'e-683c7a9a1c1174a4': ('Struhařov', '2026-12-05', '17:30', None, 'reviewed-www-struharov-cz'),
    'e-d7e32ec4d5dfef31': ('Louňovice', '2026-12-19', '17:30', None, 'reviewed-lounovice-december-2026'),
    'e-81e0c2a1addb44e1': ('Louňovice', '2026-12-23', '16:00', '17:00', 'reviewed-lounovice-december-2026'),
    'e-223a99d529e3deaf': ('Senohraby', '2026-12-19', '18:30', None, 'reviewed-senohraby-concert-2026'),
}

class LocalAdventNovember19(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads((ROOT / 'data/reviewed-events.json').read_text())
        cls.events = {e['id']: e for e in cls.document['events']}
        cls.registry = json.loads((ROOT / 'data/sources.json').read_text())

    def test_verified_dates_times_and_one_owner_across_full_registry(self):
        for eid, (town, day, start, end, sid) in FACTS.items():
            with self.subTest(id=eid):
                e = self.events[eid]
                self.assertEqual((e['town'], e['date'], e['startTime'], e['endTime']), (town, day, start, end))
                self.assertIsNone(e['location'])
                self.assertIsNone(e['price'])
                self.assertIsNone(e['registration'])
                self.assertEqual(reviewed_public.binding(e, self.registry['sources'])['id'], sid)
                validate_public.validate(dict(self.document, events=[e]), reviewed_ids={eid})
                self.assertEqual(len([s for s in self.registry['sources'] if re.fullmatch(s['url_regex'], e['sourceUrl'])]), 1)

    def test_new_exact_bindings_refuse_foreign_host_town_and_coordinates(self):
        for eid, (_, _, _, _, sid) in FACTS.items():
            if sid == 'reviewed-www-struharov-cz':
                continue  # Existing broad source unchanged.
            e = self.events[eid]
            for change in [dict(town='Praha'), dict(region='Praha'), dict(location={'lat': 50, 'lon': 14}),
                           dict(sourceUrl=e['sourceUrl'] + '?other=1'),
                           dict(sourceUrl=e['sourceUrl'].replace('https://www.', 'https://foreign.')),
                           dict(sourceUrl=e['sourceUrl'].replace('.html', '-other.html'))]:
                with self.subTest(id=eid, change=change), self.assertRaises(ValueError):
                    reviewed_public.binding(dict(e, **change), self.registry['sources'])

    def test_existing_vsechromy_end_is_not_an_invented_start(self):
        e = self.events['e-1bd34273dbf18531']
        self.assertIsNone(e['startTime'])
        self.assertEqual(e['endTime'], '18:00')
        self.assertEqual(e['status'], 'time-unconfirmed')
        self.assertEqual(reviewed_public.binding(e, self.registry['sources'])['id'], 'reviewed-www-rclodicka-eu')
        self.assertIn('15:00', ' '.join(e['notes']))
        self.assertIn('16:00', ' '.join(e['notes']))
        self.assertNotIn('nebyl zveřejněn', ' '.join(e['notes']))
        self.assertIn('30', e['registration'])
        self.assertIn('40', e['registration'])

    def test_poster_backed_devil_program_and_no_hotel_guest_restriction(self):
        # November 20: the linked municipal poster now verifies these facts.
        event = self.events['e-683c7a9a1c1174a4']
        self.assertIn('s nadílkou', event['description'])
        self.assertIn('Mikuláš', event['description'])
        self.assertTrue(any('evt_image.php?img=5099&v=1795014611' in note for note in event['notes']))
        self.assertIsNone(event['price'])
        self.assertIsNone(event['registration'])
        self.assertIn('pro veřejnost', self.events['e-223a99d529e3deaf']['description'])
        self.assertIn('na zvoničce', self.events['e-d7e32ec4d5dfef31']['venue'])

if __name__ == '__main__':
    unittest.main()
