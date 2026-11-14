"""City event portals parsed through schema.org JSON-LD: slug discovery, own-event choice, town check, bare midnight."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import collector as c

WINDOW = {'from': '2026-11-20', 'through': '2026-12-24'}
URL = 'https://akce.example.cz/akce/adventni-koncert-1/'
SOURCE = dict(id='test-city-portal', town='Plzeň', region='Plzeňský kraj', adapter='structured', index_urls=['https://akce.example.cz/'],
              url_regex=r'^https://akce\.example\.cz/akce/[^/?#]+/$', slug_keywords=True, town_in_address=True)


def page(*events):
    return '<h1>Akce</h1>' + ''.join(f'<script type="application/ld+json">{json.dumps(e, ensure_ascii=False)}</script>' for e in events)


def event(url=URL, kind='MusicEvent', start='2026-12-06T18:30:00+01:00', venue='Parkhotel Plzeň', address=None):
    place = {'@type': 'Place', 'name': venue}
    if address is not None:
        place['address'] = address
    return {'@context': 'https://schema.org', '@type': kind, 'name': 'Adventní koncert', 'url': url, 'startDate': start, 'location': place}


class CityPortals(unittest.TestCase):
    def parse(self, body, source=SOURCE):
        return c.parse_event(body, dict(source), URL, WINDOW)

    def test_slug_keywords_find_generic_detail_links_only_when_enabled(self):
        listing = '<a href="/akce/adventni-koncert-1/">Přejít na detail</a><a href="/akce/hospodsky-kviz-2/">Přejít na detail</a>'
        self.assertEqual(c.discover(listing, SOURCE['index_urls'][0], SOURCE)[0], [URL])
        self.assertEqual(c.discover(listing, SOURCE['index_urls'][0], dict(SOURCE, slug_keywords=False))[0], [])

    def test_event_subtype_publishes_with_local_time(self):
        e = self.parse(page(event()))
        self.assertEqual((e['date'], e['startTime'], e['venue']), ('2026-12-06', '18:30', 'Parkhotel Plzeň'))

    def test_related_events_on_the_page_do_not_block_its_own_event(self):
        other = event(url='https://akce.example.cz/akce/jina-akce-2/', venue='Jiné místo, Plzeň')
        self.assertEqual(self.parse(page(other, event()))['venue'], 'Parkhotel Plzeň')
        with self.assertRaises(c.Review):
            self.parse(page(other, event(url='https://akce.example.cz/akce/treti-3/')))

    def test_venue_or_address_must_name_the_city(self):
        self.assertEqual(self.parse(page(event(venue='Betlémská kaple', address={'streetAddress': 'Prokopova 16, Plzeň'})))['town'], 'Plzeň')
        for venue, address in (('Klenčí pod Čerchovem', None), ('Betlémská kaple', None), ('', {'streetAddress': 'Plzeň'})):
            with self.subTest(venue=venue), self.assertRaises(c.Review):
                self.parse(page(event(venue=venue, address=address)))

    def test_bare_utc_midnight_is_a_date_without_time(self):
        e = self.parse(page(event(start='2026-11-27T00:00:00+00:00')))
        self.assertEqual((e['date'], e['startTime']), ('2026-11-27', None))


if __name__ == '__main__':
    unittest.main()
