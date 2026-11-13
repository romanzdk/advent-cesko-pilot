"""DRE (as4u Public4u) event detail adapter: labelled date field only, everything unclear goes to review."""
from copy import deepcopy
from html import escape
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

WINDOW = {'from': '2026-11-20', 'through': '2026-12-24'}
REGISTRY = json.loads((ROOT / 'data/sources.json').read_text())
LOCATIONS = json.loads((ROOT / 'data/locations.json').read_text())
DRE = [s for s in REGISTRY['sources'] if s['adapter'] == 'dre']


def page(title, when, venue, extra=''):
    return (f'<h1 class="zahlavi_nadpis">Město</h1><h1 class="nadpis_clanku x">{escape(title)}</h1>'
            f'<table class="kratky_popis_akce"><tr><th>Místo konání:</th><td>{escape(venue)}, Zobrazit na mapě</td></tr>'
            f'<tr><th>Datum konání:</th><td>{escape(when)}</td></tr>{extra}</table>')


class DreAdapter(unittest.TestCase):
    def source(self):
        return deepcopy(DRE[0])

    def url(self, source):
        return f"https://{urlsplit(source['index_urls'][0]).hostname}/dre-cs/99999-vanocni-akce.html"

    def parse(self, when, venue=None):
        s = self.source()
        return c.parse_event(page('Rozsvícení vánočního stromu', when, venue or s['allowed_venues'][0]), s, self.url(s), WINDOW)

    def test_registered_sources_are_bounded_and_located(self):
        self.assertGreaterEqual(len(DRE), 10)
        for s in DRE:
            with self.subTest(source=s['id']):
                self.assertTrue(s['allowed_venues'])
                self.assertFalse(s['seed_urls'])
                self.assertLessEqual(len(s['index_urls']), s.get('max_index_pages', 2))
                self.assertEqual(LOCATIONS[s['town']]['precision'], 'town')

    def test_single_day_with_start_and_end(self):
        event = self.parse('12.12.2026 od 10:00 do 17:00 hodin')
        self.assertEqual((event['date'], event['endDate'], event['startTime'], event['endTime']), ('2026-12-12', None, '10:00', '17:00'))
        self.assertEqual(event['category'], 'strom')
        self.assertNotIn('Zobrazit na mapě', event['venue'])

    def test_day_without_time_is_time_unconfirmed(self):
        event = self.parse('5.12.2026')
        self.assertEqual((event['startTime'], event['status']), (None, 'time-unconfirmed'))

    def test_explicit_span_inside_window(self):
        event = self.parse('29.11.2026 až 24.12.2026')
        self.assertEqual((event['date'], event['endDate'], event['startTime']), ('2026-11-29', '2026-12-24', None))

    def test_span_beyond_window_is_excluded(self):
        with self.assertRaises(c.Excluded):
            self.parse('26.11.2026 až 10.1.2027')

    def test_several_occurrences_are_held(self):
        with self.assertRaises(c.Review):
            self.parse('28.11.2026 od 15:00 do 18:0029.11.2026 až 3.1.2027')

    def test_unknown_venue_is_held(self):
        with self.assertRaises(c.Review):
            self.parse('5.12.2026 od 16:00 hodin', 'Sousední obec, kaple')

    def test_added_structured_event_is_held(self):
        s = self.source()
        body = '<script type="application/ld+json">{"@type":"Event","name":"X","startDate":"2026-12-05T16:00"}</script>' + page('X', '5.12.2026', s['allowed_venues'][0])
        with self.assertRaises(c.Review):
            c.parse_event(body, s, self.url(s), WINDOW)

    def test_dre_hosts_share_one_fetch_thread(self):
        threads, lock = {}, threading.Lock()
        sources, pages = [], {}
        for n in range(4):
            host = f'https://dre{n}.example.cz'
            listing = f'{host}/redakce/index.php?subakce=events'
            detail = f'{host}/dre-cs/{n}1-rozsviceni.html'
            sources.append(dict(DRE[0], id=f'dre-{n}', town=f'Obec {n}', index_urls=[listing],
                                url_regex='^' + host.replace('.', '\\.') + r'/dre-cs/\d+-[^/?#]+\.html$', allowed_venues=['Náměstí']))
            pages[listing] = f'<a href="{detail}">Rozsvícení vánočního stromu</a>'.encode()
            pages[detail] = page('Rozsvícení vánočního stromu', '29.11.2026 od 16:00 hodin', 'Náměstí').encode()

        class Fetcher:
            stats = {}

            def get(self, url):
                with lock:
                    threads.setdefault(threading.get_ident(), set()).add(urlsplit(url).hostname)
                return pages[url]

        with tempfile.TemporaryDirectory() as tmp:
            result = c.collect(dict(REGISTRY, sources=sources), Path(tmp) / 'db', Path(tmp) / 'out', {}, Fetcher())
        self.assertEqual([s['eventCount'] for s in result['sources']], [1] * 4)
        self.assertEqual(len(threads), 1)


if __name__ == '__main__':
    unittest.main()
