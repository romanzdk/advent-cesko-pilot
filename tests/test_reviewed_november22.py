"""Primary-evidence facts for the November 22 editorial publication."""
from copy import deepcopy
from contextlib import closing
import json
from pathlib import Path
import re
import sys
import unittest
import sqlite3
import tempfile

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


class MappedPosazaviCorrection(unittest.TestCase):
    def test_exact_receipt_mapping_validates_and_changed_detail_withdraws_in_sqlite(self):
        import validate_public
        registry = json.loads((ROOT/'data/sources.json').read_text())
        registry['sources'] = [s for s in registry['sources'] if s['id'] in ('pysely-posazavi-calendar','cercany-posazavi-calendar')]
        source = next(s for s in registry['sources'] if s['id']=='pysely-posazavi-calendar')
        url, mapping = next(iter(source['event_locations'].items()))
        receipt = source['event_reviews'][url]
        obj = {'@type':'Event','name':receipt['expectedTitle'],
               'startDate':'2026-11-28T16:00:00+01:00', 'image':'https://example.cz/poster.png',
               'location':{'name':receipt['expectedVenue'],'address':{'addressLocality':'Pyšely'}}}
        body = '<h1>Kovářovice</h1><script type="application/ld+json">'+json.dumps(obj)+'</script>'
        receipt['contentHash'] = c.review_fingerprint(body,'posazavi')
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base/'detail.html').write_text(body)
            (base/'index.json').write_text(json.dumps({'Data':[{'Title':'Rozsvícení vánočního stromu','DetailUrl':url}]}))
            manifest = {u:'index.json' for u in source['index_urls']}
            manifest[url] = 'detail.html'
            (base/'manifest.json').write_text(json.dumps(manifest))
            client = c.FixtureClient(base/'manifest.json')
            c.collect(registry,base/'events.sqlite',base/'out',{'Pyšely':{'lat':49.8,'lon':14.6,'precision':'town','label':'Pyšely','sourceUrl':'https://www.openstreetmap.org/relation/441504'}},client,source_id=source['id'])
            self.assertEqual(validate_public.validate_directory(base/'out',registry),1)
            event = json.loads((base/'out/events.json').read_text())['events'][0]
            self.assertEqual(event['id'],'e-61ea2f4ecac214e47e22')
            self.assertEqual(event['town'],'Pyšely – Kovářovice')
            self.assertEqual(event['venue'],'Náves v Kovářovicích')
            self.assertIsNone(event['location'])
            import sync_published
            (base/'data').mkdir()
            (base/'data/sources.json').write_text(json.dumps(registry))
            (base/'private').mkdir()
            import shutil
            shutil.copytree(base/'out',base/'site')
            with closing(sqlite3.connect(base/'events.sqlite')) as src:
                dst=sqlite3.connect(base/'private/events.sqlite')
                src.backup(dst)
                dst.close()
            adoption=sync_published.adopt_published(base,'a'*40)
            self.assertEqual((adoption['inserted'],adoption['updated']),(0,0))
            for field,value in [('sourceId','foreign'),('sourceTown','Praha'),('sourceUrl',url+'?x=1'),('expectedDate','2026-11-29'),('expectedVenue','Foreign venue')]:
                invalid = deepcopy(registry)
                next(s for s in invalid['sources'] if s['id']==source['id'])['event_locations'][url][field] = value
                with self.subTest(field=field),self.assertRaises(ValueError):
                    validate_public.validate_directory(base/'out',invalid)
            (base/'detail.html').write_text(body.replace('poster.png','changed.png'))
            c.collect(registry,base/'events.sqlite',base/'out',{},client,source_id=source['id'])
            with closing(sqlite3.connect(base/'events.sqlite')) as con:
                self.assertEqual(con.execute('select count(*) from events').fetchone()[0],0)
                self.assertEqual(con.execute('select source_id,url from reviews').fetchall(),[(source['id'],url)])


if __name__ == '__main__':
    unittest.main()
