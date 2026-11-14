"""Narrow town CMS adapters (Anawe, JEvents, ostravainfo) and HTML robustness."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import collector as c

WINDOW = {'from': '2026-11-20', 'through': '2026-12-24'}


def src(adapter, town, **extra):
    return dict(id=f'test-{adapter}', town=town, region='Středočeský kraj', adapter=adapter, index_urls=['https://www.example.cz/kalendar/'], **extra)


def anawe(days, clocks=(), venue='Kostel sv. Jiljí'):
    term = ''.join(f'<span class="dk-dat">{d}</span>' for d in days) + ''.join(f'<span class="dk-cas">{t}</span>' for t in clocks)
    return (f'<div class="Kat-detail"><h1>Adventní koncert</h1><div class="Kal-info-box"><div class="Kal-termin-odo"><span class="nad">Termín</span>'
            f'<div class="pod">{term}</div></div><div class="Kal-misto"><span class="nad">Místo</span><span class="pod">{venue}</span></div></div>'
            f'<div class="text"><p>Vstupné dobrovolné.</p></div></div>')


def jevents(when, place='<span><strong>Místo: </strong>Kostel sv. Jakuba</span>'):
    return (f'<div id="jevents"><h3>Adventní koncert</h3><div class="ev_detail"><span> {when} </span></div>'
            f'<div class="ev_detail">{place}</div><div class="ev_description"><p>Koncert.</p></div></div>')


def ostrava(*items):
    lis = ''.join(f'<li>{i}</li>' for i in items)
    return f'<div class="akce-detail"><h2>Vánoční koncert</h2><ul class="akce-info">{lis}</ul><p>Koncert.</p></div>'


class TownCmsAdapters(unittest.TestCase):
    def test_valueless_class_attribute_does_not_break_parsing(self):
        root = c.DOM('<div class><span class="x">a</span></div>').root
        self.assertEqual(c.txt(root.find(cls='x')), 'a')

    def test_anawe_single_day_with_time_and_range(self):
        s = src('anawe', 'Vlašim')
        e = c.parse_event(anawe(['6.12.2026'], ['17:00']), dict(s), 'https://www.example.cz/kalendar-akci/adventni-koncert', WINDOW)
        self.assertEqual((e['date'], e['startTime'], e['venue']), ('2026-12-06', '17:00', 'Kostel sv. Jiljí'))
        e = c.parse_event(anawe(['13.12.2026', '22.12.2026']), dict(s), 'https://www.example.cz/kalendar-akci/betlemy', WINDOW)
        self.assertEqual((e['date'], e['endDate']), ('2026-12-13', '2026-12-22'))
        with self.assertRaises(c.Review):
            c.parse_event(anawe([]), dict(s), 'https://www.example.cz/kalendar-akci/x', WINDOW)

    def test_jevents_requires_one_date_and_one_place(self):
        s = src('jevents', 'Mnichovo Hradiště')
        e = c.parse_event(jevents('06.12.2026 (Ne) 18:00'), dict(s), 'https://www.example.cz/kalendar/advent/2026-12-06', WINDOW)
        self.assertEqual((e['date'], e['startTime'], e['venue']), ('2026-12-06', '18:00', 'Kostel sv. Jakuba'))
        for body in (jevents('6. prosince'), jevents('06.12.2026 (Ne)', place='<span></span>')):
            with self.subTest(body=body[:60]), self.assertRaises(c.Review):
                c.parse_event(body, dict(s), 'https://www.example.cz/kalendar/advent/2026-12-06', WINDOW)

    def test_ostravainfo_dates_and_places_outside_ostrava(self):
        s = src('ostravainfo', 'Ostrava')
        url = 'https://www.ostravainfo.cz/cz/akce/185982-vanocni-koncert.html'
        e = c.parse_event(ostrava('20. prosince 2026', '18:00', 'Zámek Poruba'), dict(s), url, WINDOW)
        self.assertEqual((e['date'], e['startTime'], e['venue']), ('2026-12-20', '18:00', 'Zámek Poruba'))
        e = c.parse_event(ostrava('4. prosince 2026', '18:00', 'Husův sbor, Ostrava - Stará Bělá'), dict(s), url, WINDOW)
        self.assertEqual(e['town'], 'Ostrava')
        with self.assertRaises(c.Review):
            c.parse_event(ostrava('6. prosince 2026', '17:00', 'Kostel Narození Panny Marie, Orlová'), dict(s), url, WINDOW)
        with self.assertRaises(c.Excluded):
            c.parse_event(ostrava('21. listopadu 2026 - 06. ledna 2027', 'Město Ostrava (různá místa)'), dict(s), url, WINDOW)

    def test_ostravainfo_discovery_uses_bare_event_urls(self):
        s = src('ostravainfo', 'Ostrava', url_regex=r'^https://www\.ostravainfo\.cz/cz/akce/\d+-[^/?#]+\.html$')
        listing = ('<a href="https://www.ostravainfo.cz/cz/akce/adventni-akce/184845-ostravske-vanoce-2026.html">Ostravské Vánoce</a>'
                   '<a href="https://www.ostravainfo.cz/cz/akce/hudba/1-jazz.html">Jazz</a>')
        self.assertEqual(c.discover(listing, 'https://www.ostravainfo.cz/cz/akce/', s)[0],
                         ['https://www.ostravainfo.cz/cz/akce/184845-ostravske-vanoce-2026.html'])


class RegionalListings(unittest.TestCase):
    def visittrebic(self, day_block, start='15:30'):
        return (f'<h1 class="h1_clanek_akce">Vánoční náměstí</h1><div class="obal_datum_akce">{day_block}</div><div class="obsah_akce">'
                f'<div class="polozka_parametry"><div class="polozka_parametry_nazev">Místo události:</div><div class="polozka_parametry_hodnota">Karlovo náměstí</div></div>'
                f'<div class="polozka_parametry"><div class="polozka_parametry_nazev">Čas od:</div><div class="polozka_parametry_hodnota">{start}</div></div></div>')

    def test_visittrebic_single_day_range_and_unknown_start(self):
        s = src('visittrebic', 'Třebíč')
        url = 'https://kalendar.visittrebic.eu/kalendar/vanocni-namesti/'
        one = '<span class="datum_akce_den">23<span>.</span></span><span class="datum_akce_mesic">11</span><span class="datum_akce_rok">2026</span>'
        e = c.parse_event(self.visittrebic(one), dict(s), url, WINDOW)
        self.assertEqual((e['date'], e['startTime'], e['venue']), ('2026-11-23', '15:30', 'Karlovo náměstí'))
        self.assertIsNone(c.parse_event(self.visittrebic(one, start='00:00'), dict(s), url, WINDOW)['startTime'])
        span = ('<span class="datum_akce_den">04<span>.</span></span><span class="datum_akce_mesic">12 2026</span><span>-</span>'
                '<span class="datum_akce_den">22<span>.</span></span><span class="datum_akce_mesic">12 2026</span>')
        e = c.parse_event(self.visittrebic(span), dict(s), url, WINDOW)
        self.assertEqual((e['date'], e['endDate'], e['startTime']), ('2026-12-04', '2026-12-22', None))

    def test_kudyznudy_listing_keeps_only_cards_of_the_source_town(self):
        s = src('kudyznudy', 'Kutná Hora', url_regex=r'^https://www\.kudyznudy\.cz/akce/[^/?#]+$')
        card = lambda slug, title, town: (f'<div class="item one-fourth"><h3><a href="/akce/{slug}">{title}</a></h3>'
                                          f'<div class="location"><span>{town}, Středočeský kraj</span></div></div>')
        listing = (card('vanocni-trhy-v-kutne-hore', 'Adventní trhy v Kutné Hoře', 'Kutná Hora')
                   + card('advent-v-caslavi', 'Advent v Čáslavi', 'Čáslav') + card('hudebni-vecer', 'Hudební večer', 'Kutná Hora'))
        self.assertEqual(c.discover(listing, 'https://www.kudyznudy.cz/kalendar-akci?mesto=533955', s)[0],
                         ['https://www.kudyznudy.cz/akce/vanocni-trhy-v-kutne-hore'])


if __name__ == '__main__':
    unittest.main()
