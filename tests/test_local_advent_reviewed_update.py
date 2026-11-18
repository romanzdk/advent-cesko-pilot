"""Portable primary-factual receipts for the 18 November local Advent review.

Facts transcribed from the linked primary documents, not captured page HTML.
The reviewed feed is editorial transport, not a parser for those documents.
"""
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import reviewed_public
import validate_public

KURYR = 'https://www.maks-ricany.cz/prilohyarchiv/11963/kuryr-2026-11.pdf'
HLASKA = 'https://www.senohraby.cz/modules/file_storage/download.php?file=c06d18de%7C764'
RYBOVKY = 'https://www.rybovky.cz/2026/11/08/terminy-2026/'
LOUNOVICE = 'https://www.lounovice.cz/aktuality/aktuality-1/pozvanka-na-adventni-akce-978cs.html'

# ID, town, date, start, end, primary document (PDF page fragments are explicit).
FACTS = [
    ('e-39b9abf0c13d1c73', 'Mukařov', '2026-12-13', '19:00', None,
     'https://www.mukarov.cz/zivot-v-obci/akce-obce/adventni-koncert-spiritual-kvartet-2026'),
    ('e-096c02c02a7bdfba', 'Říčany', '2026-11-23', '14:00', '17:00', KURYR + '#page=14'),
    ('e-110e5d971533b042', 'Senohraby', '2026-11-28', '16:30', None, HLASKA + '#page=1'),
    ('e-a5e935841c99d16d', 'Senohraby', '2026-11-28', None, None, HLASKA + '#page=12'),
    ('e-6a8e66c63a4c2026', 'Říčany', '2026-11-29', '09:30', None, KURYR + '#page=62'),
    ('e-cb79abeaa78ab473', 'Říčany', '2026-11-29', '17:00', None, KURYR + '#page=17'),
    ('e-df813aac82c7766c', 'Říčany', '2026-12-02', '16:00', None, KURYR + '#page=12'),
    ('e-ff24dadea4bc2683', 'Říčany', '2026-12-06', '17:00', None, KURYR + '#page=17'),
    ('e-eddd36503c947eb5', 'Říčany', '2026-12-09', '18:00', None, KURYR + '#page=17'),
    ('e-c613e8bf00e51511', 'Říčany', '2026-12-13', '14:00', None, KURYR + '#page=17'),
    ('e-49b64568725cca48', 'Ondřejov', '2026-12-19', '18:00', None, RYBOVKY),
    ('e-d24f8b70955c6bad', 'Říčany', '2026-12-20', '17:00', None, KURYR + '#page=17'),
    ('e-782a8431a6aa8106', 'Říčany', '2026-12-23', '17:00', None, KURYR + '#page=16'),
    ('e-9bde7f6532006ae0', 'Louňovice', '2026-11-29', '14:00', None, LOUNOVICE),
]
NEW_SOURCES = {
    'reviewed-maks-ricany-kuryr-2026-11': ('Říčany', [KURYR + '#page=' + p for p in ['12', '14', '16', '17', '62']]),
    'reviewed-senohraby-hlaska-2026-11': ('Senohraby', [HLASKA + '#page=1', HLASKA + '#page=12']),
    'reviewed-rybovky-2026-ondrejov': ('Ondřejov', [RYBOVKY]),
    'reviewed-lounovice-advent-2026': ('Louňovice', [LOUNOVICE]),
}


class LocalAdventReviewedUpdate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / 'data/sources.json').read_text())
        cls.sources = cls.registry['sources']
        cls.document = json.loads((ROOT / 'data/reviewed-events.json').read_text())
        cls.events = {e['id']: e for e in cls.document['events']}

    def test_primary_factual_dates_clocks_and_null_coordinates(self):
        for eid, town, day, start, end, url in FACTS:
            with self.subTest(id=eid):
                self.assertTrue(eid in self.events, f'Missing reviewed ID: {eid}')
                e = self.events[eid]
                self.assertEqual((e['town'], e['date'], e['startTime'], e['endTime'], e['sourceUrl']),
                                 (town, day, start, end, url))
                self.assertIsNone(e['endDate'])
                self.assertIsNone(e['location'])
                owners = [s for s in self.sources if re.fullmatch(s['url_regex'], url)]
                self.assertEqual(len(owners), 1)
                self.assertEqual(reviewed_public.binding(e, self.sources)['id'], owners[0]['id'])
                validate_public.validate(dict(self.document, events=[e]), reviewed_ids={eid})

    def test_new_bindings_are_exact_document_town_region_and_null_location(self):
        by_id = {s['id']: s for s in self.sources}
        for sid, (town, urls) in NEW_SOURCES.items():
            with self.subTest(source=sid):
                self.assertTrue(sid in by_id, f'Missing reviewed source: {sid}')
                s = by_id[sid]
                self.assertEqual(s['allowed_towns'], {town: 'Středočeský kraj'})
                self.assertEqual(s['allowed_locations'], {town: []})
                for url in urls:
                    event = dict(next(iter(self.events.values())), sourceUrl=url, town=town,
                                 region='Středočeský kraj', location=None)
                    self.assertEqual(reviewed_public.binding(event, self.sources)['id'], sid)
                    for change in [dict(town='Jiná obec'), dict(region='Praha'),
                                   dict(location={'lat': 50, 'lon': 14}),
                                   dict(sourceUrl=url.replace('https://', 'https://other.')),
                                   dict(sourceUrl=url + '&unapproved=1'),
                                   dict(sourceUrl=url.split('#')[0] + '#page=999')]:
                        with self.subTest(change=change), self.assertRaises(ValueError):
                            reviewed_public.binding(dict(event, **change), self.sources)
                # A separate PDF owner must never swallow a municipal HTML detail
                # or another issue/document on the same host.
                for url in [s['index_urls'][0].split('/')[0] + '//' + s['primary_host'] + '/kalendar/akce.html',
                            urls[0].replace('2026-11', '2026-12'),
                            urls[0].replace('c06d18de', 'different')]:
                    if url in urls:
                        continue
                    self.assertIsNone(re.fullmatch(s['url_regex'], url))

    def test_lounovice_is_one_combined_afternoon_and_retains_venue_disagreement(self):
        e = self.events.get('e-9bde7f6532006ae0')
        self.assertIsNotNone(e)
        assert e is not None
        self.assertIn('17:00', e['description'])
        text = ' '.join([e['venue'], *e['notes']])
        self.assertIn('Kamenický skanzen', text)
        self.assertIn('Horní náves', text)
        self.assertIn('evt_image.php?img=1667', ' '.join(e['notes']))
        self.assertIn('evt_image.php?img=1668', ' '.join(e['notes']))
        self.assertEqual(sum(x['sourceUrl'] == LOUNOVICE for x in self.events.values()), 1)
        self.assertIsNone(e['price'])
        self.assertIsNone(e['registration'])

    def test_audience_capacity_and_separate_programme_times_are_not_invented(self):
        self.assertTrue('e-096c02c02a7bdfba' in self.events)
        self.assertEqual(self.events['e-096c02c02a7bdfba']['audience'], 'senioři / omezené zaměření')
        self.assertEqual(self.events['e-096c02c02a7bdfba']['price'], 'Zdarma')
        self.assertIn('16:00', self.events['e-110e5d971533b042']['description'])
        self.assertIn('18:00', self.events['e-a5e935841c99d16d']['description'])
        self.assertIn('390 Kč', self.events['e-39b9abf0c13d1c73']['price'])
        # No false one-day January exhibition or next-day-midnight normalization.
        self.assertFalse(any('rybovky.cz' in e['sourceUrl'] and e['date'] != '2026-12-19'
                             for e in self.events.values()))
        self.assertFalse(any(e['town'] == 'Říčany' and 'ze šustí' not in e['title']
                             and 'výstava betlém' in e['title'].casefold()
                             and e['date'] == '2026-12-13' for e in self.events.values()))

    def test_three_updates_keep_canonical_owners_and_supplementary_sources(self):
        wreath = self.events['e-2a25cd0b98ed6aba']
        kunice = self.events['e-4f15af21f62bd966']
        museum = self.events['e-d01bbc0c574b613c']
        self.assertIn('6 volných z 15', wreath['registration'])
        self.assertNotIn('8 volných', wreath['registration'])
        self.assertIn('chvojí', wreath['description'])
        self.assertIn('Hrnečky', kunice['description'])
        self.assertIn('MŠ a ZŠ Kunice', kunice['description'])
        self.assertIn('1 místo', museum['registration'])
        self.assertNotIn('2 místa', museum['description'])
        self.assertIn('Dostupnost se může změnit', museum['registration'])
        self.assertEqual(wreath['sourceUrl'], 'https://lodicka.webooker.eu/flutter/#/events')
        self.assertEqual(kunice['sourceUrl'], 'https://www.kunice.cz/nase-obec/kalendar-akci/rozsviceni-vanocniho-stromu-1603_299cs.html')
        self.assertEqual(museum['sourceUrl'], 'https://muzeumricany.cz/akce-udalost/betlemy-ze-susti-2026/')
        self.assertIn('evt_image.php?img=11336', ' '.join(kunice['notes']))
        self.assertIn(museum['registrationUrl'], ' '.join(museum['notes']))
        self.assertEqual(wreath['verifiedAt'], '2026-11-18T09:43:38+01:00')
        self.assertEqual(kunice['verifiedAt'], '2026-11-18T09:43:38+01:00')
        self.assertEqual(museum['verifiedAt'], '2026-11-18T11:39:36.398335+00:00')
        for event, sid in [(wreath, 'reviewed-lodicka-webooker-eu'),
                           (kunice, 'reviewed-www-kunice-cz'), (museum, 'reviewed-muzeumricany-cz')]:
            self.assertEqual(reviewed_public.binding(event, self.sources)['id'], sid)

    def test_committed_public_directory_matches_verified_feed_transfer(self):
        count = validate_public.validate_directory(ROOT / 'site', self.registry)
        self.assertEqual(count, len(json.loads((ROOT / 'site/events.json').read_text())['events']))
        coverage = json.loads((ROOT / 'site/coverage.json').read_text())
        for source in coverage['sources']:
            if source['id'] in NEW_SOURCES:
                expected = sum(reviewed_public.binding(event, self.sources)['id'] == source['id']
                               for event in self.events.values())
                self.assertEqual(source['status'], 'ok')
                self.assertEqual(source['eventCount'], expected)
                self.assertIsNone(source['lastError'])
                self.assertIsNotNone(source['lastSuccess'])
                self.assertIsNotNone(source['lastChecked'])


if __name__ == '__main__':
    unittest.main()
