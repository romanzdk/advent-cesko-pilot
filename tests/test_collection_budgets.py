"""Bounded discovery expansion: offline pages, real collector and SQLite."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('budget_collector', ROOT/'scripts/collector.py')
assert spec and spec.loader
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
REGISTRY = json.loads((ROOT/'data/sources.json').read_text())

class BudgetTests(unittest.TestCase):
    def run_collection(self, source):
        pages, requested = {}, []
        base = 'https://www.plasy.cz/list'
        for page in range(1,6):
            url = base if page==1 else base+f'?page={page}'
            links = []
            for number in range((page-1)*11,page*11):
                detail = f'https://www.plasy.cz/turista/kalendar-akci-v-plasich/vanoce-{number}_100cs.html'
                links.append(f'<a href="{detail}">Vánoční akce {number}</a>')
                pages[detail] = f'<h1>Vánoční akce {number}</h1><div class="event-detail"><div class="action-date">5. 12. 2026 17:00</div><div class="venue">Plasy</div></div>'.encode()
            pages[url] = (''.join(links)+f'<a rel="next" href="{base}?page={page+1}">Další</a>').encode()
        source = dict(source,index_urls=[base],seed_urls=[])
        class Fetcher:
            stats = {}
            def get(self,url):
                requested.append(url)
                return pages[url]
        with tempfile.TemporaryDirectory() as tmp:
            result = c.collect(dict(REGISTRY,sources=[source]),Path(tmp)/'db',Path(tmp)/'out',{},Fetcher())
        return result, requested

    def test_explicit_four_page_forty_detail_budget_is_effective(self):
        source = dict(REGISTRY['sources'][0], max_index_pages=4, max_details=40)
        result, requested = self.run_collection(source)
        self.assertEqual(result['metrics']['eventsNew'],40)
        self.assertEqual(len(requested),44)
        self.assertIn('4', result['coverageNote'])
        self.assertIn('40', result['coverageNote'])

    def test_invalid_budget_configuration_fails_before_fetch(self):
        for field,values in [('max_index_pages',[0,5,True,2.5,'4',None]),('max_details',[0,41,False,14.5,'40',None])]:
            for value in values:
                with self.subTest(field=field,value=value), self.assertRaises(ValueError):
                    self.run_collection(dict(REGISTRY['sources'][0], **{field:value}))

    def test_legacy_defaults_remain_two_pages_fourteen_details(self):
        source = dict(REGISTRY['sources'][0])
        source.pop('max_details',None)
        source.pop('max_index_pages',None)
        result,requested = self.run_collection(source)
        self.assertEqual(result['metrics']['eventsNew'],14)
        self.assertEqual(len(requested),16)

    def test_audited_clipped_sources_and_known_paginations_have_explicit_expanded_budgets(self):
        by_id = {s['id']:s for s in REGISTRY['sources']}
        for sid in ['telc-mesto','humpolec-mesto','hranice-kultura']:
            self.assertEqual(by_id[sid].get('max_details'),40)
        for sid in ['cz-jilemnice-calendar','horovice-mesto','trebon-iks','nejdek-mesto','praha16-radotin']:
            self.assertEqual(by_id[sid].get('max_index_pages'),4)

if __name__=='__main__':
    unittest.main()
