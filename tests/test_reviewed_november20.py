"""Exact editorial bindings for two independently checked November 20 findings."""
import copy
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import reviewed_public

NEW_ID = 'e-0e0e431b8c528740'
EXISTING_ID = 'e-683c7a9a1c1174a4'
URL = 'https://zamekberchtold.cz/aktuality/kalendar-akci/'


class November20EditorialTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT/'data/sources.json').read_text())
        self.sources = self.registry['sources']  # Full registry, not reviewed-only subset.
        self.document = json.loads((ROOT/'data/reviewed-events.json').read_text())
        self.events = {e['id']: e for e in self.document['events']}

    def test_berchtold_has_one_exact_primary_binding_and_no_invented_point(self):
        self.assertIn(NEW_ID, self.events)
        event = self.events[NEW_ID]
        owner = reviewed_public.binding(event, self.sources)
        self.assertEqual(owner['id'], 'reviewed-berchtold-charity-2026')
        self.assertEqual([s['id'] for s in self.sources if re.fullmatch(s['url_regex'], URL)], [owner['id']])
        self.assertEqual(owner['allowed_towns'], {'Kunice–Vidovice': 'Středočeský kraj'})
        self.assertEqual(owner['allowed_locations'], {'Kunice–Vidovice': []})
        self.assertIsNone(event['location'])
        for change in [
            {'sourceUrl': URL+'?other=1'}, {'sourceUrl': URL+'#poster'},
            {'sourceUrl': URL+'other/'}, {'sourceUrl': URL.replace('zamekberchtold.cz', 'www.zamekberchtold.cz')},
            {'sourceUrl': URL.replace('/kalendar-akci/', '/jina-akce/')},
            {'town': 'Kunice'}, {'town': 'Struhařov'}, {'region': 'Hlavní město Praha'},
            {'location': {'lat': 49.9, 'lon': 14.6}},
        ]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                reviewed_public.binding(dict(event, **change), self.sources)

    def test_berchtold_retains_overall_end_programme_and_contact_free_registration(self):
        self.assertIn(NEW_ID, self.events)
        event = self.events[NEW_ID]
        self.assertEqual((event['date'], event['startTime'], event['endTime']), ('2026-12-12', '15:30', '17:00'))
        self.assertIn('Červený sál', event['venue'])
        self.assertEqual(event['registration'], 'Nutné předem pořadateli e-mailem ohlásit počet diváků; kontakt v pozvánce.')
        self.assertIsNone(event['registrationUrl'])
        notes = ' '.join(event['notes'])
        for value in ['16:50', 'Claireton Chorale', 'String Ladies', 'předání daru', '12.12.26.png']:
            self.assertIn(value, notes)
        self.assertNotIn('@', json.dumps(event))
        self.assertFalse(re.search(r'\+420|\b\d{3}[ -]\d{3}[ -]\d{3}\b', json.dumps(event)))
        self.assertEqual(event['audience'], 'všichni')

    def test_struharov_keeps_canonical_id_owner_url_and_unknown_fields(self):
        event = self.events[EXISTING_ID]
        self.assertEqual(reviewed_public.binding(event, self.sources)['id'], 'reviewed-www-struharov-cz')
        self.assertEqual(event['sourceUrl'], 'https://www.struharov.cz/zivot-v-obci/kalendar-akci/struharovske-peklo-u-frantiska-835_214cs.html')
        self.assertEqual((event['date'], event['startTime']), ('2026-12-05', '17:30'))
        for field in ['endDate', 'endTime', 'price', 'registration', 'registrationUrl', 'location']:
            self.assertIsNone(event[field])
        self.assertIn('s nadílkou', event['description'])
        self.assertIn('Mikuláš', event['description'])
        self.assertIn('přijít včas', event['description'])
        self.assertTrue(any('evt_image.php?img=5099&v=1795014611' in n for n in event['notes']))

    def test_full_snapshot_decodes_with_no_invalid_records(self):
        raw = json.dumps(self.document, ensure_ascii=False).encode()
        _, records, invalid = reviewed_public.decode(raw, self.sources, self.registry, {})
        self.assertEqual(invalid, [])
        self.assertEqual(len(records), len(self.events))
        self.assertEqual({e['id']: e for _, e in records}, self.events)
