"""Portable, curated semantic fragments; no network or private captures required."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/expansion-adapters'
spec = importlib.util.spec_from_file_location('expansion_collector', ROOT / 'scripts/collector.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
WINDOW = {'from': '2026-11-20', 'through': '2026-12-24'}


def source(adapter, town, venues):
    return {'id': adapter, 'adapter': adapter, 'town': town,
            'region': 'Kraj Vysočina', 'allowed_venues': venues}


def parse(html, s):
    return c.parse_event(html, s, 'https://example.cz/event/2026', WINDOW)


class ExpansionAdapterTests(unittest.TestCase):
    def test_seventeen_verified_portable_fragments(self):
        cases = json.loads((FIXTURES / 'verified-fragments.json').read_text())
        self.assertEqual(len(cases), 17)
        self.assertEqual(len({f['source']['id'] for f in cases}), 6)
        for f in cases:
            with self.subTest(url=f['url']):
                e = c.parse_event(f['html'], f['source'], f['url'], WINDOW)
                for key, expected in f['expected'].items():
                    self.assertEqual(e[key], expected, key)

    def test_humpolec_scoped_metadata_and_occurrences(self):
        html = (FIXTURES / 'humpolec.html').read_text()
        venue = '8SMIČKA - zóna pro umění, Kamarytova, Humpolec, Česko'
        s = source('humpolec', 'Humpolec', [venue])
        e = parse(html, s)
        self.assertEqual((e['date'], e['startTime'], e['endTime'], e['venue'], e['price']),
                         ('2026-12-12', '14:00', '15:30', venue, '88 Kč'))
        self.assertIsNone(parse(html.replace('od 14:00 do 15:30', 'od 14:00 do 00:00'), s)['endTime'])
        for old, new in [('12. 12. 2026', '12. 12.'), ('12. 12. 2026', '12. 12. 2026 - 13. 12. 2026'),
                         ('od 14:00 do 15:30', '17:00, 19:00'), ('od 14:00 do 15:30', 'od 17:00 a od 19:00'),
                         ('12. 12. 2026', '12. 12. 2026 , 12. 12. 2026'),
                         (venue, 'Kulturní dům, sousední obec')]:
            with self.subTest(new=new), self.assertRaises(c.Review):
                parse(html.replace(old, new), s)
        # Similar-event prices and booking language never leak into this article.
        clean = html.replace('88 Kč', '').replace('Vánoční dílna 5. 12. 2026', 'Rezervace 900 Kč 5. 12. 2026')
        self.assertIsNone(parse(clean, s)['price'])
        self.assertIsNone(parse(clean, s)['registration'])

    def test_telc_leading_date_and_labelled_clock(self):
        html = (FIXTURES / 'telc.html').read_text()
        s = source('telc', 'Telč', ['Panský dvůr Telč'])
        e = parse(html, s)
        self.assertEqual((e['title'], e['date'], e['startTime'], e['endTime'], e['venue']),
                         ('Adventní trhy na Panském dvoře Telč', '2026-11-21', '09:00', '17:00', 'Panský dvůr Telč'))
        concert = html.replace('9.00 – 17.00 hod.', 'v 17.00 hodin')
        self.assertEqual(parse(concert, s)['startTime'], '17:00')
        self.assertIsNone(parse(concert, s)['endTime'])
        self.assertIsNone(parse(html.replace('9.00 – 17.00 hod.', ''), s)['startTime'])
        for replacement in ['21.11. - 21.11.']:
            with self.subTest(date=replacement), self.assertRaises(c.Review):
                parse(html.replace('21.11.2026 - 21.11.2026', replacement), s)
        with self.assertRaises(c.Review):
            parse(html.replace('21. listopadu 2026', '22. listopadu 2026'), s)

    def test_itrebon_semantic_rows(self):
        html = (FIXTURES / 'itrebon.html').read_text()
        s = source('itrebon', 'Třeboň', ['Centrum města'])
        e = parse(html, s)
        self.assertEqual((e['title'], e['date'], e['startTime'], e['endTime'], e['venue']),
                         ('TŘEBOŇ PLNÁ ANDĚLŮ', '2026-11-28', '10:00', '19:00', 'Centrum města'))
        self.assertIsNone(e['endDate'])
        midnight = parse(html.replace('10:00 - 19:00', '00:00'), s)
        self.assertIsNone(midnight['startTime'])
        self.assertIsNone(midnight['endTime'])
        for date_text in ['28.11.', '28.11.2025', '28.11.2026 a 29.11.2026']:
            with self.subTest(date=date_text), self.assertRaises(c.Review):
                parse(html.replace('28.11.2026', date_text), s)

    def test_humpolec_preserves_labelled_price_variants(self):
        html = (FIXTURES / 'humpolec.html').read_text().replace('88 Kč', '200 Kč v předprodeji, 250 Kč na místě')
        s = source('humpolec', 'Humpolec', ['8SMIČKA - zóna pro umění, Kamarytova, Humpolec, Česko'])
        self.assertEqual(parse(html, s)['price'], '200 Kč v předprodeji, 250 Kč na místě')

    def test_galileo_holds_incomplete_narrative_exhibition_end(self):
        html = '<h1>Skleněné Vánoce aneb…</h1><div class="event-detail"><h2 class="action-date">29. 11. 2026 15:00</h2><div class="venue">Muzeum Českého krasu v Berouně</div><div class="lead">Výstava potrvá do 10. 1.</div></div>'
        with self.assertRaises(c.Review):
            parse(html, source('galileo', 'Beroun', ['Muzeum Českého krasu v Berouně']))

    def test_exact_optional_venue_guard(self):
        s = source('galileo', 'Beroun', ['Husovo náměstí'])
        template = '<h1>Adventní trh</h1><div class="event-detail"><h2 class="action-date">5. 12. 2026 10:00</h2><div class="venue">{}</div></div>'
        for venue in ['Hořovice', 'Husovo náměstí, sousední obec', '', 'Neznámé místo']:
            with self.subTest(venue=venue), self.assertRaises(c.Review):
                parse(template.format(venue), s)
        self.assertEqual(parse(template.format('Ｈusovo\u00a0 NÁMĚSTÍ'), s)['town'], 'Beroun')
        unguarded = dict(s)
        del unguarded['allowed_venues']
        self.assertEqual(parse(template.format('Neznámé místo'), unguarded)['town'], 'Beroun')
        with self.assertRaises(c.Review):
            parse(template.format('Husovo náměstí'), dict(s, allowed_venues=[]))


if __name__ == '__main__':
    unittest.main()
