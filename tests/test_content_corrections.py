"""Portable source-content regressions using small, curated factual fragments.

These are deliberately reduced semantic HTML, NOT captured source pages. Only
contentHash is rebound to each fragment when exercising the real source config;
all identities, decisions and typed overrides come from data/sources.json.
Production hashes below were independently read from the audited private captures;
CI never needs those captures, and fragment hashes must never enter production.
"""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('content_corrections_collector', ROOT / 'scripts/collector.py')
assert spec is not None and spec.loader is not None
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
REGISTRY = json.loads((ROOT / 'data/sources.json').read_text())
WINDOW = REGISTRY['window']
PRAHA_URL = 'https://www.praha22.cz/volny-cas/prehled-akci-1/vazani-adventnich-vencu-7533_3591cs.html'
HUMPOLEC_URL = 'https://humpolec.cz/akce/vanocni-dilna-ozdoby-balici-papir/'
TELC_URL = 'https://www.telc.eu/kalendar/4258'

# Curated fact fragment: dates, venue, activity and no-reservation statement.
PRAHA = '''<h1>Vázání adventních věnců</h1><div class="event-detail">
<h2 class="action-date">26. 11. 2026 0:00 – 28. 11. 2026 23:59</h2>
<div class="venue">Fara - vchod přes dvůr</div>
<p>Možnost vázat adventní věnce. Rezervace není nutná.</p></div>'''


# Curated fact fragment: labelled metadata and the complete suitability invitation.
HUMPOLEC = '''<main class="event single"><h1>Vánoční dílna #OZDOBY &amp; BALICÍ PAPÍR</h1>
<section id="content"><div class="container"><aside id="meta"><div class="meta-items">
<span aria-label="Kdy"><span class="value">5. 12. 2026</span></span>
<span aria-label="V kolik"><span class="value">od 14:00 do 15:30</span></span>
<span aria-label="Cena"><span class="value">88 Kč</span></span>
<span aria-label="Místo"><span class="value">8SMIČKA - zóna pro umění, Kamarytova, Humpolec, Česko</span></span>
</div></aside><p>Ke společnému tvoření zveme rodiče i prarodiče!
Dílna je vhodná pro děti od 5 let.</p></div></section></main>'''


# Curated fact fragment: exact narrative time and upper-square tee-pee location.
TELC = '''<div class="clanek_levy_sloupec">23.12.2026 - 23.12.2026
<h2>Betlémské světlo</h2><p>23. prosince 2026 od 15.00 do 17.30</p>
<p>V horní části telčského náměstí bude stát tee-pee.</p>
<strong>Organizátor akce</strong> Junák
<strong>Místo konání:</strong> náměstí Zachariáše z Hradce<br></div>'''


CASES = (
    ('praha22-uhrineves', PRAHA_URL, PRAHA, 'Vázání adventních věnců',
     '2026-11-26', '2026-11-28', 'Fara - vchod přes dvůr',
     '00fc95b6acb1934aef041ae2576706f27082152987a1ab6b6fb1fe5f658e4b6f'),
    ('humpolec-mesto', HUMPOLEC_URL, HUMPOLEC, 'Vánoční dílna #OZDOBY & BALICÍ PAPÍR',
     '2026-12-05', None, '8SMIČKA - zóna pro umění, Kamarytova, Humpolec, Česko',
     '45be7fa34d41e27b3d2ecd2eb996546a3c916b7a488a5eccab7f08395a66a2be'),
    ('telc-mesto', TELC_URL, TELC, 'Betlémské světlo',
     '2026-12-23', None, 'náměstí Zachariáše z Hradce',
     '0637694f398ce8abcb354b4b0b78e0c493fc06a7d4f3cc3d7ecd8d579f3baa4b'),
)


def source(source_id):
    return copy.deepcopy(next(s for s in REGISTRY['sources'] if s['id'] == source_id))


def fragment_source(source_id, url, html):
    s = source(source_id)
    review = s.get('event_reviews', {}).get(url)
    if review is not None:
        review['contentHash'] = c.review_fingerprint(html, s['adapter'])
    return s


class ContentCorrectionTests(unittest.TestCase):
    def test_praha_wreath_making_without_reservation_retains_unknown_hours(self):
        s = fragment_source('praha22-uhrineves', PRAHA_URL, PRAHA)
        event = c.parse_event(PRAHA, s, PRAHA_URL, WINDOW)
        self.assertEqual((event['registration'], event['category']), (None, 'tvoreni'))
        self.assertEqual((event['date'], event['endDate'], event['startTime'], event['endTime']),
                         ('2026-11-26', '2026-11-28', None, None))
        self.assertEqual(event['status'], 'time-unconfirmed')
        self.assertIn('Čas zahájení není potvrzen; půlnoc se nepovažuje za skutečný začátek.', event['notes'])
        self.assertIn('Uvedeny jsou krajní termíny; nejde o potvrzení nepřetržitého ani každodenního otevření.', event['notes'])
        self.assertIn('Rozmezí 26.–28. listopadu označuje krajní dny; denní otevírací hodiny nejsou uvedeny. Rezervace není nutná; vlastní zahradnické nůžky jsou doporučené.', event['notes'])


    def test_humpolec_family_suitability_is_not_a_mandatory_age_limit(self):
        s = fragment_source('humpolec-mesto', HUMPOLEC_URL, HUMPOLEC)
        event = c.parse_event(HUMPOLEC, s, HUMPOLEC_URL, WINDOW)
        self.assertIn('Dílna je vhodná pro děti od 5 let; ke společnému tvoření jsou zváni rodiče i prarodiče.', event['notes'])
        self.assertEqual(event['audience'], 'všichni')
        self.assertEqual((event['date'], event['startTime'], event['endTime'], event['price']),
                         ('2026-12-05', '14:00', '15:30', '88 Kč'))
        self.assertEqual(event['status'], 'confirmed')
        self.assertEqual(event['category'], 'tvoreni')
        self.assertIsNone(event['registration'])


    def test_telc_narrative_hours_are_confirmed_with_precise_location(self):
        s = fragment_source('telc-mesto', TELC_URL, TELC)
        event = c.parse_event(TELC, s, TELC_URL, WINDOW)
        self.assertEqual((event['date'], event['startTime'], event['endTime'], event['status']),
                         ('2026-12-23', '15:00', '17:30', 'confirmed'))
        self.assertIn('Betlémské světlo bude k dispozici v tee-pee v horní části telčského náměstí.', event['notes'])
        self.assertFalse(any('Čas zahájení není potvrzen' in n for n in event['notes']))
        self.assertEqual(event['venue'], 'náměstí Zachariáše z Hradce')
        self.assertEqual(event['category'], 'betlem')
        self.assertIsNone(event['price'])
        self.assertIsNone(event['registration'])


    def test_reviews_retain_exact_capture_identity_not_fixture_fingerprint(self):
        for sid, url, html, title, day, end, venue, content_hash in CASES:
            with self.subTest(url=url):
                s = source(sid)
                review = s['event_reviews'][url]
                expected = dict(sourceId=sid, sourceUrl=url, sourceTown=s['town'],
                                expectedTitle=title, expectedDate=day, expectedEndDate=end,
                                expectedVenue=venue, contentHash=content_hash, decision='accept')
                self.assertEqual({k: review[k] for k in expected}, expected)
                self.assertIn(url, review['supportingSourceUrls'])
                self.assertNotEqual(content_hash, c.review_fingerprint(html, s['adapter']))
                with self.assertRaises(c.Review):
                    c.parse_event(html, s, url, WINDOW)

    def test_changed_semantic_body_and_review_identity_still_fail_closed(self):
        for sid, url, html, *_ in CASES:
            with self.subTest(url=url):
                s = fragment_source(sid, url, html)
                # Change facts inside every supported adapter's semantic scope.
                altered = html.replace('</p>', ' Změněný obsah události.</p>', 1)
                with self.assertRaises(c.Review):
                    c.parse_event(altered, s, url, WINDOW)
                for key in ('sourceId', 'sourceUrl', 'sourceTown', 'expectedTitle',
                            'expectedDate', 'expectedEndDate', 'expectedVenue'):
                    bad = copy.deepcopy(s)
                    bad['event_reviews'][url][key] = 'mismatched identity'
                    with self.subTest(field=key), self.assertRaises(c.Review):
                        c.parse_event(html, bad, url, WINDOW)

    def test_overrides_do_not_leak_to_another_event_url(self):
        for sid, url, html, *_ in CASES:
            with self.subTest(url=url):
                s = fragment_source(sid, url, html)
                other_url = url + '?unreviewed=1'
                event = c.parse_event(html, s, other_url, WINDOW)
                if sid == 'praha22-uhrineves':
                    self.assertIsNotNone(event['registration'])
                    self.assertEqual(event['category'], 'setkani')
                elif sid == 'humpolec-mesto':
                    self.assertEqual(event['notes'], [])
                else:
                    self.assertIsNone(event['startTime'])
                    self.assertEqual(event['status'], 'time-unconfirmed')


if __name__ == '__main__':
    unittest.main()
