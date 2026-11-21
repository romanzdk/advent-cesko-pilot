"""Primary organizer poster receipt; no invented price, booking or coordinates."""
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import reviewed_public

POSTER = 'https://centrum-pecka.cz/wp-content/uploads/2026_VANOCE_fb-1024x577.jpg'
OWNER = 'reviewed-centrum-pecka-cz'


class PeckaNovember21(unittest.TestCase):
    def test_one_exact_poster_event_with_existing_owner_and_unknown_conditions(self):
        registry = json.loads((ROOT / 'data/sources.json').read_text())
        feed = json.loads((ROOT / 'data/reviewed-events.json').read_text())
        events = [e for e in feed['events'] if e['sourceUrl'] == POSTER]
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual((e['title'], e['town'], e['date'], e['startTime'], e['endTime'], e['venue']),
                         ('Kostelecké trhy adventní', 'Kostelec nad Černými lesy', '2026-12-12', '09:00', '16:00',
                          'Náměstí Smiřických, Kostelec nad Černými lesy'))
        self.assertEqual(e['category'], 'trhy')
        self.assertEqual(e['status'], 'confirmed')
        for key in ('location', 'endDate', 'price', 'registration', 'registrationUrl'):
            self.assertIsNone(e[key])
        self.assertIn('řemeslné produkty', e['description'])
        self.assertIn('https://centrum-pecka.cz/', ' '.join(e['notes']))
        self.assertEqual(reviewed_public.binding(e, registry['sources'])['id'], OWNER)
        self.assertEqual([s['id'] for s in registry['sources'] if re.fullmatch(s['url_regex'], POSTER)], [OWNER])
        s = next(s for s in registry['sources'] if s['id'] == OWNER)
        self.assertEqual(s['allowed_towns'], {e['town']: 'Středočeský kraj'})
        self.assertEqual(s['allowed_locations'], {e['town']: []})
        self.assertEqual(s['index_urls'], [POSTER])
        for change in [dict(sourceUrl=POSTER + '?other=1'), dict(sourceUrl=POSTER + '#copy'),
                       dict(sourceUrl=POSTER.replace('centrum-pecka.cz', 'foreign.cz')),
                       dict(sourceUrl='https://centrum-pecka.cz/'),
                       dict(sourceUrl=POSTER.replace('2026_', '2025_')),
                       dict(town='Pecka'), dict(region='Královéhradecký kraj'),
                       dict(location={'lat': 49.9947827, 'lon': 14.8608657})]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                reviewed_public.binding(dict(e, **change), registry['sources'])


if __name__ == '__main__':
    unittest.main()
