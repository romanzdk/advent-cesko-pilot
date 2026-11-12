"""Small semantic fragments only; offline deterministic review regressions."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('held_collector', ROOT / 'scripts/collector.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
WINDOW = {'from': '2026-11-20', 'through': '2026-12-24'}
URL = 'https://example.cz/event/1'


def source(adapter='galileo'):
    return dict(id='test', adapter=adapter, town='Telč', region='Kraj Vysočina', allowed_venues=['Panský dvůr Telč'])


def fragment(day='5. 12. 2026', venue='Panský dvůr Telč'):
    return f'<h1>Adventní program</h1><div class="event-detail"><div class="action-date">{day} 14:00</div><div class="venue">{venue}</div></div>'


class HeldReviewTests(unittest.TestCase):
    def test_outside_semantic_dates_precede_multidate_and_venue_review(self):
        for day in ['5. 12. 2025, 6. 12. 2025, 7. 12. 2025', '19. 11. 2026 – 5. 12. 2026', '5. 12. 2026 – 25. 12. 2026']:
            with self.subTest(day=day), self.assertRaises(c.Excluded):
                c.parse_event(fragment(day, 'Neověřené místo'), source(), URL, WINDOW)
        for day in ['31. 11. 2026', '5. 12.']:
            with self.subTest(day=day), self.assertRaises(c.Review) as caught:
                c.parse_event(fragment(day), source(), URL, WINDOW)
            self.assertNotIsInstance(caught.exception, c.Excluded)

    def test_explicit_range_is_date_range_not_clock_hyphen(self):
        fixtures = ROOT / 'tests/fixtures/expansion-adapters'
        html = (fixtures / 'itrebon.html').read_text().replace('28.11.2026', '3.12.2026 – 13.12.2026')
        s = dict(source('itrebon'), town='Třeboň', allowed_venues=['Centrum města'])
        e = c.parse_event(html, s, URL, WINDOW)
        self.assertEqual((e['date'], e['endDate']), ('2026-12-03', '2026-12-13'))
        with self.assertRaises(c.Review):
            c.parse_event(html.replace('3.12.2026 – 13.12.2026', '3.12.2026, 13.12.2026'), s, URL, WINDOW)
        html = (fixtures / 'telc.html').read_text().replace('21.11.2026 - 21.11.2026', '11.12.2026 - 12.12.2026').replace('21. listopadu 2026', '11. prosince 2026')
        e = c.parse_event(html, source('telc'), URL, WINDOW)
        self.assertEqual(e['endDate'], '2026-12-12')
        self.assertIsNone(e['startTime'])
        self.assertIsNone(e['endTime'])
        self.assertTrue(any('každodenního' in n for n in e['notes']))

    def test_review_fingerprint_uses_only_semantic_scope(self):
        for adapter, html, noise in [
            ('galileo', fragment(), '<footer>noise</footer>'),
            ('itrebon', '<div class="kalendarDetail">Vánoce 2026</div>', '<footer>noise</footer>'),
            ('telc', '<div class="clanek_levy_sloupec">Vánoce<strong>Organizátor akce</strong>private contact</div>', ''),
            ('humpolec', '<section id="content"><div class="container">Vánoce<div id="related">other event</div></div></section>', '')]:
            with self.subTest(adapter=adapter):
                fp = c.review_fingerprint(html, adapter)
                self.assertRegex(fp, r'^[0-9a-f]{64}$')
                changed = html.replace('private contact', 'different contact').replace('other event', 'changed related') + noise
                self.assertEqual(fp, c.review_fingerprint(changed, adapter))
                self.assertNotEqual(fp, c.review_fingerprint(html.replace('Vánoce', 'Advent').replace('14:00', '15:00'), adapter))

    def review_source(self, html, decision='accept', **changes):
        record = dict(sourceId='test', sourceUrl=URL, sourceTown='Telč', expectedTitle='Adventní program', expectedDate='2026-12-05', expectedEndDate=None, expectedVenue='Panský dvůr Telč', contentHash=c.review_fingerprint(html, 'galileo'), decision=decision, reason='Ověřený výběr.', overrides={})
        record.update(changes)
        return dict(source(), event_reviews={URL: record})

    def test_null_review_record_requires_review(self):
        with self.assertRaises(c.Review):
            c.parse_event(fragment(), dict(source(), event_reviews={URL: None}), URL, WINDOW)

    def test_invalid_review_containers_require_review(self):
        for metadata in [None, [], 'invalid']:
            with self.subTest(metadata=metadata), self.assertRaises(c.Review):
                c.parse_event(fragment(), dict(source(), event_reviews=metadata), URL, WINDOW)

    def test_bad_review_metadata_withdraws_previous_public_event(self):
        from contextlib import closing
        import sqlite3
        for metadata in [{URL: None}, None, [], 'invalid']:
            with self.subTest(metadata=metadata), tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp)
                index = 'https://example.cz/'
                s = dict(source(), index_urls=[index], seed_urls=[URL], url_regex=r'https://example.cz/event/.*')
                registry = dict(window=WINDOW, season=2026, sources=[s])
                (p/'index.html').write_text('<p>Index</p>')
                (p/'detail.html').write_text(fragment())
                (p/'manifest.json').write_text(json.dumps({index: 'index.html', URL: 'detail.html'}))
                client = c.FixtureClient(p/'manifest.json')
                first = c.collect(registry, p/'db', p/'out', {}, client)
                self.assertEqual(first['metrics']['eventsPublished'], 1)
                self.assertEqual(len(json.loads((p/'out/events.json').read_text())['events']), 1)
                s['event_reviews'] = metadata
                second = c.collect(registry, p/'db', p/'out', {}, client)
                self.assertEqual(second['metrics']['eventsPublished'], 0)
                self.assertEqual(second['metrics']['reviewCount'], 1)
                self.assertEqual(second['sources'][0]['status'], 'partial')
                self.assertIsNone(second['sources'][0]['lastError'])
                self.assertEqual(json.loads((p/'out/events.json').read_text())['events'], [])
                self.assertEqual(json.loads((p/'out/review.json').read_text())['candidates'][0]['url'], URL)
                with closing(sqlite3.connect(p/'db')) as con:
                    self.assertEqual(con.execute('SELECT count(*) FROM events').fetchone()[0], 0)
                    self.assertEqual(con.execute('SELECT url FROM reviews').fetchall(), [(URL,)])

    def test_review_preserves_programme_kind_and_booking_condition(self):
        html = fragment()
        s = self.review_source(html, overrides={'category': 'setkani', 'registration': 'Nutná registrace předem; kontakt u pořadatele.'})
        e = c.parse_event(html, s, URL, WINDOW)
        self.assertEqual(e['category'], 'setkani')
        self.assertEqual(e['registration'], 'Nutná registrace předem; kontakt u pořadatele.')
        s['event_reviews'][URL]['overrides']['category'] = 'unknown'
        with self.assertRaises(c.Review):
            c.parse_event(html, s, URL, WINDOW)

    def test_bound_review_decisions_before_venue_guard(self):
        html = fragment(venue='Cizí obec')
        s = self.review_source(html, 'exclude', expectedVenue='Cizí obec')
        with self.assertRaises(c.Excluded) as caught:
            c.parse_event(html, s, URL, WINDOW)
        self.assertEqual(str(caught.exception), 'Ověřený výběr.')
        for key, value in [('sourceId', 'wrong'), ('sourceUrl', URL+'2'), ('sourceTown', 'wrong'), ('expectedTitle', 'wrong'), ('expectedDate', '2026-12-06'), ('expectedEndDate', '2026-12-06'), ('expectedVenue', 'wrong'), ('contentHash', '0'*64)]:
            changed = self.review_source(html, 'exclude', expectedVenue='Cizí obec', **({key:value} if key != 'expectedVenue' else {}))
            if key == 'expectedVenue': changed['event_reviews'][URL][key] = value
            with self.subTest(key=key), self.assertRaises(c.Review) as caught:
                c.parse_event(html, changed, URL, WINDOW)
            self.assertNotIsInstance(caught.exception, c.Excluded)
        for decision in ['hold', 'accept']:
            with self.subTest(decision=decision), self.assertRaises(c.Review) as caught:
                c.parse_event(html, self.review_source(html, decision, expectedVenue='Cizí obec'), URL, WINDOW)
            self.assertNotIsInstance(caught.exception, c.Excluded)

    def test_verified_town_exception_is_exact_bound_and_per_event(self):
        html = fragment(venue='jiné')
        s = self.review_source(html, expectedVenue='jiné', verifiedTown='Telč')
        self.assertEqual(c.parse_event(html, s, URL, WINDOW)['venue'], 'jiné')
        for town in [None, '', 'telč', 'Telč ', 'Soběslav']:
            changed = self.review_source(html, expectedVenue='jiné', verifiedTown=town)
            with self.subTest(town=town), self.assertRaises(c.Review):
                c.parse_event(html, changed, URL, WINDOW)
        missing = self.review_source(html, expectedVenue='jiné')
        with self.assertRaises(c.Review):
            c.parse_event(html, missing, URL, WINDOW)
        with self.assertRaises(c.Review):
            c.parse_event(html, s, URL+'2', WINDOW)
        for key in ['sourceId', 'sourceUrl', 'sourceTown', 'expectedTitle', 'expectedDate', 'expectedEndDate', 'expectedVenue', 'contentHash']:
            changed = self.review_source(html, expectedVenue='jiné', verifiedTown='Telč')
            changed['event_reviews'][URL][key] = 'wrong'
            with self.subTest(key=key), self.assertRaises(c.Review):
                c.parse_event(html, changed, URL, WINDOW)
        for decision, exception in [('hold', c.Review), ('exclude', c.Excluded)]:
            with self.subTest(decision=decision), self.assertRaises(exception):
                c.parse_event(html, self.review_source(html, decision, expectedVenue='jiné', verifiedTown='Telč'), URL, WINDOW)
        self.assertEqual(c.parse_event(fragment(), self.review_source(fragment()), URL, WINDOW)['venue'], 'Panský dvůr Telč')

    def test_venue_override_is_sanitized_bounded_and_updates_description(self):
        html = fragment(venue='jiné')
        s = self.review_source(html, expectedVenue='jiné', verifiedTown='Telč', overrides={'venue': 'Park u altánu contact@example.cz /home/user/secret'})
        e = c.parse_event(html, s, URL, WINDOW)
        self.assertEqual(e['venue'], 'Park u altánu')
        self.assertEqual(e['description'], 'Adventní program. Park u altánu')
        for venue in [None, 12, [], '', '   ', 'x'*181, 'contact@example.cz /home/user/secret']:
            s['event_reviews'][URL]['overrides']['venue'] = venue
            with self.subTest(venue=venue), self.assertRaises(c.Review):
                c.parse_event(html, s, URL, WINDOW)
        s['event_reviews'][URL]['overrides']['venue'] = 'x'*180
        e = c.parse_event(html, s, URL, WINDOW)
        self.assertEqual(len(e['venue']), 180)
        self.assertEqual(e['description'], (e['title']+'. '+e['venue'])[:200])
        with self.assertRaises(c.Review):
            c.parse_event(html, self.review_source(html, expectedVenue='jiné', overrides={'venue':'Panský dvůr Telč'}), URL, WINDOW)

    def test_four_audiences_survive_collector_public_and_browser_validation(self):
        import subprocess
        validator_spec = importlib.util.spec_from_file_location('held_validator', ROOT/'scripts/validate_public.py')
        validator = importlib.util.module_from_spec(validator_spec)
        validator_spec.loader.exec_module(validator)
        app = (ROOT/'site/app.js').read_text()
        browser_validator = app[app.index('function validData(data) {'):app.index('\n}', app.index('function validData(data) {'))+2]
        for audience in ['všichni', 'dospělí', 'senioři / omezené zaměření', 'omezené zaměření']:
            with self.subTest(audience=audience):
                e = c.parse_event(fragment(), self.review_source(fragment(), overrides={'audience': audience}), URL, WINDOW)
                data = dict(schemaVersion=1, season=2026, generatedAt=e['verifiedAt'], region='Česko', events=[e])
                self.assertTrue(validator.validate(data))
                script = "const categories={setkani:'Setkání'};\n" + browser_validator + '\nif (!validData('+json.dumps(data)+')) process.exit(1);'
                result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
        data['events'][0]['audience'] = 'děti'
        with self.assertRaises(ValueError):
            validator.validate(data)
        script = "const categories={setkani:'Setkání'};\n" + browser_validator + '\nif (validData('+json.dumps(data)+')) process.exit(1);'
        self.assertEqual(subprocess.run(['node', '-e', script], capture_output=True).returncode, 0)

    def test_overrides_are_closed_typed_sanitized_and_status_safe(self):
        html = fragment()
        changes = dict(startTime=None, endTime=None, price='100 Kč contact@example.cz /home/user/secret', audience='senioři / omezené zaměření', notes=['Ověřte hodiny contact@example.cz /private/secret'])
        e = c.parse_event(html, self.review_source(html, overrides=changes), URL, WINDOW)
        self.assertIsNone(e['startTime'])
        self.assertEqual(e['status'], 'time-unconfirmed')
        self.assertEqual(e['price'], '100 Kč')
        self.assertEqual(e['audience'], changes['audience'])
        self.assertEqual(e['notes'][-1], 'Ověřte hodiny')
        html = fragment().replace('Adventní program', 'Adventní program zrušen')
        e = c.parse_event(html, self.review_source(html, expectedTitle='Adventní program zrušen', overrides={'startTime':'19:00'}), URL, WINDOW)
        self.assertEqual(e['status'], 'cancelled')
        for overrides in [{'date':'2026-12-06'}, {'startTime':'24:00'}, {'endTime':12}, {'price':[]}, {'audience':'děti'}, {'notes':'not a list'}, {'notes':[None]}]:
            with self.subTest(overrides=overrides), self.assertRaises(c.Review):
                c.parse_event(fragment(), self.review_source(fragment(), overrides=overrides), URL, WINDOW)

    def test_telc_review_queue_title_is_detail_h2(self):
        html = '<h1>Kalendář akcí</h1><div class="clanek_levy_sloupec">5.12.2026 - 5.12.2026<h2>Vánoční výstava</h2><strong>Organizátor akce</strong><strong>Místo konání</strong>Cizí obec<br></div>'
        s = dict(source('telc'), index_urls=['https://example.cz/'], url_regex=r'https://example.cz/event/.*', seed_urls=[URL])
        class Fetcher:
            stats = {}
            def get(self, url): return html if url == URL else ''
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            c.collect(dict(window=WINDOW, season=2026, sources=[s]), p/'db', p/'out', {}, Fetcher())
            candidates = json.loads((p/'out/review.json').read_text())['candidates']
        self.assertEqual(candidates[0]['title'], 'Vánoční výstava')

    def test_factual_ranges_keep_warning_and_telc_clock_unknown_after_review(self):
        for f in json.loads((ROOT/'tests/fixtures/expansion-adapters/held-ranges.json').read_text()):
            s = dict(source(f['adapter']), allowed_venues=[f['venue']])
            record = dict(sourceId=s['id'], sourceUrl=URL, sourceTown=s['town'], expectedTitle=f['title'], expectedDate=f['date'], expectedEndDate=f['endDate'], expectedVenue=f['venue'], contentHash=c.review_fingerprint(f['html'], f['adapter']), decision='accept', reason='Ověřeno.', overrides={'notes':['Denní hodiny ověřte.']})
            s['event_reviews'] = {URL: record}
            e = c.parse_event(f['html'], s, URL, WINDOW)
            self.assertEqual((e['date'], e['endDate']), (f['date'], f['endDate']))
            self.assertTrue(any('každodenního' in n for n in e['notes']))
            if f['adapter'] == 'telc':
                self.assertIsNone(e['startTime'])
                record['overrides']['startTime'] = '14:00'
                with self.assertRaises(c.Review):
                    c.parse_event(f['html'], s, URL, WINDOW)

    def test_itrebon_requires_exactly_two_complete_date_endpoints(self):
        html = (ROOT/'tests/fixtures/expansion-adapters/itrebon.html').read_text()
        s = dict(source('itrebon'), town='Třeboň', allowed_venues=['Centrum města'])
        for invalid in ['3.12.2026 - 13.12.', '3.12.2026 - 13.12.2026, 13.12.2026']:
            with self.subTest(invalid=invalid), self.assertRaises(c.Review):
                c.parse_event(html.replace('28.11.2026', invalid), s, URL, WINDOW)

    def test_telc_leading_range_accepts_en_dash(self):
        f = json.loads((ROOT/'tests/fixtures/expansion-adapters/held-ranges.json').read_text())[0]
        e = c.parse_event(f['html'].replace('11.12.2026 - 12.12.2026', '11.12.2026 – 12.12.2026'), dict(source('telc'), allowed_venues=[f['venue']]), URL, WINDOW)
        self.assertEqual(e['endDate'], '2026-12-12')

    def test_verified_clock_replaces_default_uncertainty_note(self):
        html = fragment().replace('14:00', '')
        e = c.parse_event(html, self.review_source(html, overrides={'startTime':'19:00'}), URL, WINDOW)
        self.assertEqual((e['startTime'], e['status']), ('19:00', 'confirmed'))
        self.assertFalse(any('Čas zahájení není potvrzen' in n for n in e['notes']))
        e = c.parse_event(fragment(), self.review_source(fragment(), overrides={'startTime':None}), URL, WINDOW)
        self.assertTrue(any('Čas zahájení není potvrzen' in n for n in e['notes']))


if __name__ == '__main__':
    unittest.main()
