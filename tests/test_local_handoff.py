"""Portable contracts for the canonical local editorial handoff."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import collector as c
import reviewed_public as rp
import validate_public as v

SCHOOL = 'https://www.zus-popo.net/wp-content/uploads/2026/10/VANOCNI-AKCE-2026.jpg'
WORKSHOP = 'https://www.radejoviceobec.cz/aktualne/kalendar-akci/vanocni-atelier-betlemy-1017_141cs.html'
CONCERT = 'https://www.radejoviceobec.cz/aktualne/kalendar-akci/vanocni-koncert-1019_142cs.html'
PLAN = 'https://www.radejoviceobec.cz/evt_file.php?file=2326&original=Listy+4_2026.pdf'


class LocalHandoff(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / 'data/sources.json').read_text())
        self.snapshot = json.loads((ROOT / 'data/reviewed-events.json').read_text())
        self.events = {e['id']: e for e in self.snapshot['events']}
        self.sources = self.registry['sources']

    def test_new_towns_have_exact_approved_binding_without_invented_points(self):
        for url, town in [(SCHOOL, 'Kostelec u Křížků'),
                          ('https://www.facebook.com/groups/103557059678141/posts/29544867108453746/', 'Lensedly')]:
            rows = [e for e in self.events.values() if e['sourceUrl'] == url and e['town'] == town]
            self.assertEqual(len(rows), 1)
            self.assertIsNone(rows[0]['location'])
            self.assertEqual(rp.binding(rows[0], self.sources)['adapter'], 'reviewed-public')

    def test_municipal_urls_keep_their_single_original_live_owner(self):
        import re
        for url in [WORKSHOP, CONCERT]:
            owners = [s for s in self.sources if re.fullmatch(s['url_regex'], url)]
            self.assertEqual([s['id'] for s in owners], ['radejovice-obec-calendar'])
            self.assertFalse(any(e['sourceUrl'] == url for e in self.events.values()))
        owners = [s for s in self.sources if re.fullmatch(s['url_regex'], PLAN)]
        self.assertEqual(len(owners), 1)
        self.assertEqual(owners[0]['adapter'], 'reviewed-public')
        self.assertFalse(re.fullmatch(owners[0]['url_regex'], PLAN + '&extra=1'))

    def test_verified_public_clock_does_not_follow_calendar_archive_date_only(self):
        for event_id, clock in [('e-bf84417b4fd765bb', '17:00'),
                                ('e-fe2188cf907d5a69', '17:00'),
                                ('e-6791dd58fe264edc', '14:00'),
                                ('e-3db839caa99515e9', '14:00'),
                                ('e-f5959f2305ed486e', '16:30')]:
            self.assertEqual(self.events[event_id]['startTime'], clock)
            self.assertEqual(self.events[event_id]['status'], 'confirmed')
        self.assertIn('300 Kč', self.events['e-fe2188cf907d5a69']['registration'])
        self.assertIsNone(self.events['e-fe2188cf907d5a69']['price'])
        self.assertIsNone(self.events['e-f5959f2305ed486e']['venue'])
        self.assertIn('srazu', self.events['e-f5959f2305ed486e']['description'])

    def test_prices_registration_and_midnight_boundary_are_preserved(self):
        row = self.events['e-7802484334ca4a2f']
        self.assertEqual((row['date'], row['startTime'], row['endDate'], row['endTime']),
                         ('2026-12-11', '20:00', '2026-12-12', '02:00'))
        self.assertIn('290', row['price']); self.assertIn('350', row['price'])
        row = self.events['e-4eb551f1ca26af1a']
        self.assertEqual(row['price'], '100 Kč/dítě')
        self.assertIn('SMS', row['registration'])

    def test_all_snapshot_records_bind_uniquely_and_reject_scope_drift(self):
        v.validate(self.snapshot, set(self.events))
        identities = set()
        for row in self.events.values():
            source = rp.binding(row, self.sources)
            identity = (row['sourceUrl'], row['date'], row['town'], row['startTime'])
            self.assertNotIn(identity, identities); identities.add(identity)
            altered = deepcopy(row); altered['town'] = 'Neschválená obec'
            with self.assertRaises(ValueError): rp.binding(altered, self.sources)
            self.assertEqual(source['region'], row['region'])

    def test_foreign_locality_notice_does_not_call_olesky_a_part_of_plasy(self):
        from test_three_source_expansion import fragment
        body = fragment('Vánoční koncert', '2026-12-18',
                        'kostel Narození Panny Marie').replace('15:30 - 18:00', '18:00').encode()
        # Deliberately synthetic portable fragment; it is not live source evidence.
        source = {'id': 'fixture-radejovice', 'town': 'Radějovice', 'region': 'Středočeský kraj',
                  'adapter': 'galileo', 'event_locations': {CONCERT: {
                      'sourceId': 'fixture-radejovice', 'sourceTown': 'Radějovice', 'sourceUrl': CONCERT,
                      'expectedVenue': 'kostel Narození Panny Marie', 'expectedDate': '2026-12-18',
                      'town': 'Olešky', 'locationKey': 'intentionally-unmapped'}}}
        event = c.parse_event(body, source, CONCERT, self.registry['window'])
        self.assertEqual(event['town'], 'Olešky')
        self.assertNotIn('Plas', ' '.join(event['notes']))
        self.assertIsNone(event['location'])
        self.assertEqual(event['id'], 'e-' + hashlib.sha256(CONCERT.encode()).hexdigest()[:20])


if __name__ == '__main__':
    unittest.main()
