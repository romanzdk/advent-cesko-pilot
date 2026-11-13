"""Portable regression for exact review11 decisions; primary evidence stays private."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import collector as c
import audited_events as a
from test_three_source_expansion import fragment, WINDOW

class Review11(unittest.TestCase):
    def sources(self):
        return {s['id']:deepcopy(s) for s in json.loads((ROOT/'data/sources.json').read_text())['sources']}

    def test_all_original11_urls_have_closed_single_occurrence_decisions(self):
        sources=self.sources()
        ck=sources['cerveny-kostelec-ckzije'];nejdek=sources['nejdek-mesto']
        urls=[ck['detail_prefixes'][0]+suffix for suffix in [
            'adventni-koncerty-koletovy-hornicke-hudby-384_62cs.html',
            'adventni-koncerty-koletovy-hornicke-hudby-384_63cs.html',
            *[f'adventni-nedele-ve-lhote-457_{number}cs.html' for number in range(124,129)],
            'mikulasska-besidka-na-bohdasine-439_108cs.html',
            'mikulasska-nadilka-ve-lhote-438_107cs.html',
            'tajemstvi-pohadkovych-vanoc-s-mdo-a-family-bandem-446_113cs.html']]
        urls.append('https://www.nejdek.cz/aktivity/kultura/kalendar-akci/adventni-bohosluzba-2441_1246cs.html')
        self.assertEqual(len(set(urls)),11)
        for url in urls:
            with self.subTest(url=url):
                source=nejdek if 'nejdek.cz' in url else ck
                self.assertIn(url,source.get('audited_events',{}),'Missing closed review11 receipt')
                receipt=source['audited_events'][url]
                self.assertEqual(receipt['decision'],'accept')
                self.assertEqual(len(receipt['events']),1)
                self.assertNotIn(url,source.get('event_reviews',{}))

    def test_lhota_cycle_keeps_five_dates_and_program_specific_categories(self):
        source=self.sources()['cerveny-kostelec-ckzije']
        pairs=[]
        for url,receipt in source.get('audited_events',{}).items():
            if 'adventni-nedele-ve-lhote-' in url:
                fact=receipt['events'][0]
                pairs.append((fact['date'],fact['startTime'],fact['category']))
        self.assertEqual(sorted(pairs),[
            ('2026-11-29','16:00','strom'),('2026-12-06','16:00','mikulas'),
            ('2026-12-13','16:00','setkani'),('2026-12-20','16:00','setkani'),
            ('2026-12-24','11:00','setkani')])

    def test_receipts_keep_real_localities_and_reject_changed_content(self):
        for source_id in ['cerveny-kostelec-ckzije','nejdek-mesto']:
            source=self.sources()[source_id]
            for url,receipt in source.get('audited_events',{}).items():
                if source_id=='nejdek-mesto' and '/adventni-bohosluzba-' not in url:
                    continue
                fact=receipt['events'][0]
                body=fragment(receipt['expectedTitle'],fact['date'],fact['venue'],fact['endDate'])
                receipt['contentHash']=a.fingerprint(body,'galileo')
                event=c.parse_event(body,source,url,WINDOW)
                self.assertIsNone(event['endTime'])
                self.assertEqual(event['location']['precision'],'town')
                self.assertNotEqual(event['town'],'Červený Kostelec')
                self.assertIn('nikoli přesné',' '.join(event['notes']))
                if event['town']!='Nejdek':
                    self.assertIn(event['town'],event['location']['label'])
                with self.subTest(url=url),self.assertRaises(c.Review):
                    c.parse_event(body.replace('Veřejný adventní program.','Změněný program.'),source,url,WINDOW)

    def test_optional_private_gift_deadline_is_not_general_registration(self):
        source=self.sources()['cerveny-kostelec-ckzije']
        url=next(u for u in source['audited_events'] if '/mikulasska-nadilka-ve-lhote-' in u)
        fact=source['audited_events'][url]['events'][0]
        self.assertIn('Pouze při předávání soukromých dárků',fact['registration'])
        self.assertIn('2. prosince 2026',fact['registration'])
        self.assertIsNone(fact['endTime'])
        self.assertIn('18:00 není oznámený konec',' '.join(fact['notes']))

if __name__=='__main__':unittest.main()
