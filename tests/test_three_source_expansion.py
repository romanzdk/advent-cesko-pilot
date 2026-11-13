"""Portable factual fragments; full live HTML/poster evidence stays private."""
from copy import deepcopy
from html import escape
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import collector as c
import audited_events as a

WINDOW={'from':'2026-11-20','through':'2026-12-24'}
IDS={'cz-zatec-calendar','cz-hlinsko-calendar','ludgerovice-obec'}

def day(iso):
    year,month,date=iso.split('-')
    return f'{date}. {month}. {year}'

def fragment(title,date,venue,end=None,text='Veřejný adventní program.'):
    dates=day(date)+(f' – {day(end)}' if end else '')
    return f'<h1>{escape(title)}</h1><div class="event-detail"><span class="action-date">{dates} 15:30 - 18:00</span><span class="venue">{escape(venue)}</span><p>{escape(text)}</p></div>'

class ThreeSourceExpansion(unittest.TestCase):
    def source(self,id):
        sources=json.loads((ROOT/'data/sources.json').read_text())['sources']
        matches=[s for s in sources if s['id']==id]
        self.assertEqual(len(matches),1,f'Missing approved source {id}')
        return deepcopy(matches[0])

    def reviewed(self,s,url):
        review=s['event_reviews'][url]
        body=fragment(review['expectedTitle'],review['expectedDate'],review['expectedVenue'],review['expectedEndDate'])
        review['contentHash']=c.review_fingerprint(body,'galileo')
        return c.parse_event(body,s,url,WINDOW),body

    def test_only_existing_galileo_adapter_and_narrow_measured_budgets(self):
        for id,town,region,maximum in [('cz-zatec-calendar','Žatec','Ústecký kraj',20),('cz-hlinsko-calendar','Hlinsko','Pardubický kraj',14),('ludgerovice-obec','Ludgeřovice','Moravskoslezský kraj',14)]:
            with self.subTest(id=id):
                s=self.source(id);self.assertEqual((s['adapter'],s['town'],s['region']),('galileo',town,region))
                self.assertEqual(s.get('max_index_pages',2),2);self.assertEqual(s.get('max_details',14),maximum)
                self.assertTrue(s['allowed_venues']);self.assertTrue(any(word in s['coverage_note'].lower() for word in ['neúplný','nejde o úplné','omezený']))

    def test_complete_lucie_bila_price_and_booking_not_truncated_to_800(self):
        s=self.source('ludgerovice-obec');url=next(u for u in s['event_reviews'] if 'bile-vanoce-lucie-bile' in u)
        event,_=self.reviewed(s,url);self.assertEqual(event['price'],'1 800 Kč / 1 400 Kč');self.assertIn('nejvýše 6',event['registration'])

    def test_duplicate_zatec_announcements_are_excluded_not_double_counted(self):
        s=self.source('cz-zatec-calendar');urls=[u for u in s['event_reviews'] if 'advent-ve-dvore-sv-jakuba' in u];self.assertEqual(len(urls),3)
        for url in urls:
            with self.subTest(url=url),self.assertRaises(c.Excluded):self.reviewed(s,url)

    def test_zatec_markets_use_market_filter_for_all_three_dates(self):
        s=self.source('cz-zatec-calendar');urls=[u for u in s['event_reviews'] if 'advent-u-svateho-jakuba' in u];self.assertEqual(len(urls),3)
        for url in urls:
            event,_=self.reviewed(s,url);self.assertEqual(event['category'],'trhy')

    def test_conflicting_zatec_hours_are_unknown_not_silently_selected(self):
        s=self.source('cz-zatec-calendar')
        for prefix,field in [('rozsviceni-vanocniho-stromu','endTime'),('mikulasska-nadilka','startTime')]:
            url=next(u for u in s['event_reviews'] if '/'+prefix+'-' in u);event,_=self.reviewed(s,url)
            self.assertIsNone(event[field]);self.assertTrue(any('rozpor' in n.lower() for n in event['notes']))

    def test_hlinsko_daily_fair_keeps_distinct_daily_hours_without_continuous_interval(self):
        s=self.source('cz-hlinsko-calendar');url=next(u for u in s['event_reviews'] if 'adventni-jarmark-na-zs-resslova' in u)
        event,_=self.reviewed(s,url);self.assertEqual((event['startTime'],event['endTime']),(None,None));self.assertEqual((event['date'],event['endDate']),('2026-11-25','2026-11-27'))
        text=' '.join(event['notes']);self.assertIn('15:30–18:00',text);self.assertIn('8:00–17:00',text);self.assertIn('8:00–11:00',text)

    def test_scoped_suburb_geography_never_borrows_wrong_municipal_centre(self):
        for id,needle,town in [('cz-hlinsko-calendar','Blatno','Hlinsko-Blatno'),('ludgerovice-obec','Vrablovci','Ludgeřovice-Vrablovec')]:
            s=self.source(id);url=next(u for u,r in s['audited_events'].items() if needle.replace('Vrablovci','Vrablovec') in r['events'][0]['town'])
            record=s['audited_events'][url];fact=record['events'][0];body=fragment(record['expectedTitle'],fact['date'],fact['venue']);record['contentHash']=a.fingerprint(body,'galileo')
            event=c.parse_event(body,s,url,WINDOW);self.assertEqual(event['town'],town);self.assertNotIn('část Plas',' '.join(event['notes']))
            if event['location']:self.assertIn(needle.replace('Vrablovci','Vrablovec'),event['location']['label'])
            with self.assertRaises(c.Review):c.parse_event(body.replace('Veřejný adventní program.','Změněný veřejný program.'),s,url,WINDOW)

    def test_review_changes_return_to_review_and_new_venues_stay_held(self):
        s=self.source('ludgerovice-obec');url=next(u for u in s['event_reviews'] if 'bile-vanoce-lucie-bile' in u);_,body=self.reviewed(s,url)
        with self.assertRaises(c.Review):c.parse_event(body.replace('Veřejný adventní program.','Jiný program.'),s,url,WINDOW)
        s=self.source('cz-zatec-calendar');url=s['index_urls'][0]+'vanocni-akce-9999_9999cs4903.html'
        with self.assertRaises(c.Review):c.parse_event(fragment('Vánoční akce','2026-12-05','Neověřené místo'),s,url,WINDOW)

if __name__=='__main__':unittest.main()
