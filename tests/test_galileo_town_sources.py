"""Invariants for venue-restricted Galileo town calendars and concurrent host fetching."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import collector as c
from test_three_source_expansion import fragment, WINDOW

REGISTRY = json.loads((ROOT / 'data/sources.json').read_text())
LOCATIONS = json.loads((ROOT / 'data/locations.json').read_text())
NOTE = '{}: omezený sezónní výběr z oficiálního městského kalendáře; nejvýše dvě stránky a čtrnáct detailů, nikoli úplné městské ani krajské pokrytí.'
OBEC_NOTE = '{}: omezený sezónní výběr z oficiálního obecního kalendáře; nejvýše dvě stránky a osm detailů, nikoli úplné obecní ani krajské pokrytí.'
TOWN_SOURCES = [s for s in REGISTRY['sources'] if s['adapter'] == 'galileo' and s.get('coverage_note') in (NOTE.format(s['town']), OBEC_NOTE.format(s['town']))]


class GalileoTownSources(unittest.TestCase):
    def test_town_sources_are_bounded_seedless_and_located(self):
        self.assertGreaterEqual(len(TOWN_SOURCES), 40)
        towns = [s['town'] for s in REGISTRY['sources']]
        for source in TOWN_SOURCES:
            with self.subTest(source=source['id']):
                self.assertEqual(towns.count(source['town']), 1)
                village = source['coverage_note'] == OBEC_NOTE.format(source['town'])
                self.assertEqual((source.get('max_index_pages', 2), source.get('max_details', 14)), (2, 8 if village else 14))
                self.assertFalse(source['seed_urls'])
                self.assertTrue(source['allowed_venues'])
                self.assertEqual(LOCATIONS[source['town']]['precision'], 'town')
                self.assertTrue(source['url_regex'].startswith('^' + 'https://' + urlsplit(source['index_urls'][0]).hostname.replace('.', '\\.')))

    def test_only_allowed_venues_publish(self):
        for source in TOWN_SOURCES:
            url = source['detail_prefixes'][0] + 'vanocni-akce-9999_9999cs.html'
            with self.subTest(source=source['id']):
                event = c.parse_event(fragment('Rozsvícení vánočního stromu', '2026-11-29', source['allowed_venues'][0]), deepcopy(source), url, WINDOW)
                self.assertEqual((event['town'], event['region'], event['date']), (source['town'], source['region'], '2026-11-29'))
                with self.assertRaises(c.Review):
                    c.parse_event(fragment('Rozsvícení vánočního stromu', '2026-11-29', 'Neověřené místo v jiné obci'), deepcopy(source), url, WINDOW)


    def test_private_events_are_excluded(self):
        source = TOWN_SOURCES[0]
        url = source['detail_prefixes'][0] + 'vanocni-besidka-9999_9999cs.html'
        body = fragment('Vánoční besídka', '2026-12-19', source['allowed_venues'][0], text='soukromá akce')
        with self.assertRaises(c.Excluded):
            c.parse_event(body, deepcopy(source), url, WINDOW)
        c.parse_event(body.replace('soukromá akce', 'veřejná akce'), deepcopy(source), url, WINDOW)


class ConcurrentHosts(unittest.TestCase):
    def test_each_host_stays_on_one_thread_and_order_is_kept(self):
        base = TOWN_SOURCES[0]
        sources, pages = [], {}
        for n in range(6):
            host = f'https://obec{n}.example.cz/akce/'
            detail = f'{host}rozsviceni-stromu-{n}_1cs.html'
            sources.append(dict(base, id=f'test-{n}-calendar', town=f'Obec {n}', index_urls=[host], detail_prefixes=[host],
                                url_regex='^' + host.replace('.', '\\.') + r'[^/?#]+-\d+_\d+cs\.html$', allowed_venues=['Náměstí']))
            pages[host] = f'<a href="{detail}">Rozsvícení vánočního stromu</a>'.encode()
            pages[detail] = fragment('Rozsvícení vánočního stromu', '2026-11-29', 'Náměstí').encode()
        threads, lock = {}, threading.Lock()

        class Fetcher:
            stats = {}

            def get(self, url):
                with lock:
                    threads.setdefault(urlsplit(url).hostname, set()).add(threading.get_ident())
                return pages[url]

        with tempfile.TemporaryDirectory() as tmp:
            result = c.collect(dict(REGISTRY, sources=sources), Path(tmp) / 'db', Path(tmp) / 'out', {}, Fetcher())
        self.assertEqual([s['id'] for s in result['sources']], [s['id'] for s in sources])
        self.assertEqual([s['eventCount'] for s in result['sources']], [1] * 6)
        self.assertTrue(all(len(t) == 1 for t in threads.values()))


if __name__ == '__main__':
    unittest.main()
