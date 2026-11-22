"""Primary-evidence facts for the November 22 editorial publication."""
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import reviewed_public
import collector as c


class November22Facts(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT/'data/sources.json').read_text())
        self.feed = json.loads((ROOT/'data/reviewed-events.json').read_text())
        self.events = {e['id']: e for e in self.feed['events']}

    def test_conflicting_losbates_hours_are_unknown_not_a_reschedule(self):
        event = self.events['e-c2348a901e9c9a4c']
        self.assertEqual(event['date'], '2026-11-30')
        self.assertIsNone(event['startTime'])
        self.assertIsNone(event['endTime'])
        self.assertEqual(event['status'], 'time-unconfirmed')
        notes = ' '.join(event['notes'])
        for fact in ('16:00–19:00', '17:00', 'https://zslosbates.edupage.org/calendar/'):
            self.assertIn(fact, notes)

    def test_pancharti_does_not_invent_an_age_restriction(self):
        self.assertEqual(self.events['e-227c4d83ce5745ed']['audience'], 'všichni')

    def test_borova_separates_programme_start_from_lighting(self):
        event = self.events['e-bb4c321bbaaa07b6']
        self.assertEqual(event['startTime'], '15:00')
        self.assertEqual(event['venue'], 'Náves u kapličky, Borová Lhota')
        self.assertIn('16:30', event['description'])

    def test_exact_new_primary_bindings_and_unknown_coordinates(self):
        selected = [e for e in self.feed['events'] if e['sourceUrl'] in (
            'https://todelamja.webooker.eu/flutter/#/events',
            'https://static.posazavi.com/Pictures/RelatedEventImages/2026/10/26/40146.jpeg',
            'https://static.posazavi.com/Pictures/RelatedEventImages/2026/11/3/40293.png',
            'https://zamekkostelec.cz/kalendar-akci-na-rok-2026/',
            'https://www.lsteni-zlenice.cz/evt_file.php?file=2294')]
        self.assertEqual(len(selected), 7)
        for event in selected:
            self.assertIsNone(event['location'])
            owner = reviewed_public.binding(event, self.registry['sources'])
            self.assertEqual([s['id'] for s in self.registry['sources'] if re.fullmatch(s['url_regex'],event['sourceUrl'])], [owner['id']])
            for change in (dict(sourceUrl=event['sourceUrl']+'?other=1'), dict(sourceUrl=event['sourceUrl']+'#other'),
                           dict(town='Praha'), dict(location={'lat':50,'lon':14})):
                with self.subTest(event=event['id'], change=change), self.assertRaises(ValueError):
                    reviewed_public.binding(dict(event, **change), self.registry['sources'])
        exhibition = [e for e in selected if e['town']=='Pyšely']
        self.assertEqual(sorted(e['date'] for e in exhibition), ['2026-12-06','2026-12-13','2026-12-20'])
        for event in exhibition:
            self.assertEqual(event['startTime'], '16:00')
            self.assertIsNone(event['endDate'])
            self.assertEqual(event['price'], 'Vstup zdarma')
            self.assertEqual(event['category'], 'setkani')
        for event in selected:
            if event['town'] in ('Lštění','Kostelec nad Černými lesy'):
                self.assertIsNone(event['startTime'])
                self.assertIsNone(event['endTime'])
        bethlehem = next(e for e in selected if e['town']=='Lštění')
        self.assertIn('14:00–17:00', ' '.join(bethlehem['notes']))

    def test_live_corrections_keep_owners_and_canonical_ids_out_of_feed(self):
        for sid, suffix, facts in (
            ('pysely-posazavi-calendar','46827-vanocni-vystava.html', {'venue':'Informační centrum a knihovna Pyšely, Náměstí T. G. Masaryka 4','price':'Vstup zdarma','category':'setkani'}),
            ('pysely-posazavi-calendar','46903-slavnostni-rozsviceni-vanocniho-stromu-na-navsi-v-kovarovicich.html', {'venue':'Náves v Kovářovicích'}),
            ('cercany-posazavi-calendar','46883-slavnosti-dobra-a-radosti-treti-adventni-setkani.html', {'endTime':'15:00','venue':'Hospic Dobrého Pastýře a Centrum Péče Čerčany, Sokolská 584'})):
            source = next(s for s in self.registry['sources'] if s['id']==sid)
            url = 'https://tourist.posazavi.com/cz/kalendar-akci/'+suffix
            receipt = source.get('event_reviews',{}).get(url)
            self.assertIsNotNone(receipt)
            for field,value in facts.items():
                self.assertEqual(receipt['overrides'][field], value)
            self.assertFalse(any(e['sourceUrl']==url for e in self.feed['events']))
        mapping = next(s for s in self.registry['sources'] if s['id']=='pysely-posazavi-calendar')['event_locations']
        self.assertEqual(next(iter(mapping.values()))['town'], 'Pyšely – Kovářovice')


if __name__ == '__main__':
    unittest.main()
