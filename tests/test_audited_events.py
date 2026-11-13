"""Exact-content editorial receipts; all collection is offline and temporary."""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import collector as c
import validate_public as v

URL = 'https://example.cz/event/1'
INDEX = 'https://example.cz/'
WINDOW = {'from': '2026-11-20', 'through': '2026-12-24'}
STAMP = '2026-11-12T10:20:30+00:00'
TITLE = 'Adventní program'
BODY = '<h1>Adventní program</h1><div class="event-detail"><div class="action-date">17. 12. 2026, 19. 12. 2026</div><div class="venue">Semily</div><p>Dva samostatné termíny.</p></div>'


def occurrence(key='dec17', day='2026-12-17') -> dict[str, Any]:
    return dict(occurrenceKey=key, title=TITLE, town='Semily', venue='Náměstí Semily',
                date=day, endDate=None, startTime='17:00', endTime='18:00', category='setkani',
                price=None, registration=None, registrationUrl=None, description='Dva samostatné termíny.',
                notes=[], audience='všichni', location=None, allowExtendedEnd=False)


def source() -> dict[str, Any]:
    receipt = dict(sourceId='test', sourceTown='Telč', sourceUrl=URL, expectedTitle=TITLE,
                   contentHash=c.digest(TITLE + ' 17. 12. 2026, 19. 12. 2026 Semily Dva samostatné termíny.'),
                   decision='accept', reason='Ověřené samostatné termíny pořadatele.', verifiedAt=STAMP,
                   events=[occurrence(), occurrence('dec19', '2026-12-19')])
    return dict(id='test', town='Telč', region='Kraj Vysočina', adapter='galileo',
                index_urls=[INDEX], seed_urls=[URL], url_regex=r'https://example\.cz/event/\d+',
                allowed_venues=['Panský dvůr Telč'], audited_events={URL: receipt})


class Offline:
    stats = {}

    def __init__(self, body=BODY):
        self.body = body
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        return self.body.encode() if url == URL else f'<a href="{URL}">Adventní program</a>'.encode()


class AuditedEventsTests(unittest.TestCase):
    def test_explicit_occurrences_precede_adapter_guards(self):
        s = source()
        try:
            events = c.parse_event(BODY, s, URL, WINDOW)
        except c.Review as exc:
            self.fail(f'Audited explicit occurrences must precede date/venue guards: {exc}')
        self.assertIsInstance(events, list)
        self.assertEqual([e['date'] for e in events], ['2026-12-17', '2026-12-19'])
        self.assertEqual([e['endDate'] for e in events], [None, None])
        self.assertEqual({e['town'] for e in events}, {'Semily'})
        self.assertEqual({e['region'] for e in events}, {'Kraj Vysočina'})
        self.assertEqual({e['verifiedAt'] for e in events}, {STAMP})
        self.assertTrue(v.validate(dict(schemaVersion=1, season=2026, region='Česko', generatedAt=STAMP, events=events)))
        s['audited_events'][URL]['events'].reverse()
        reordered = c.parse_event(BODY, s, URL, WINDOW)
        self.assertEqual({e['date']: e['id'] for e in events}, {e['date']: e['id'] for e in reordered})
        production = json.loads((ROOT / 'site/events.json').read_text())['events']
        self.assertFalse({e['id'] for e in events} & {e['id'] for e in production})

    def test_receipts_are_closed_typed_and_identity_bound(self):
        variants = [None, [], '', 12, {URL: None}, {URL: []}, {URL: {}}]
        for field, value in [('sourceId', 'other'), ('sourceTown', 'Semily'), ('sourceUrl', URL + '2'),
                             ('expectedTitle', 'other'), ('contentHash', '0' * 64), ('contentHash', None),
                             ('decision', 'maybe'), ('reason', ''), ('reason', 'x' * 501),
                             ('reason', 'Kontakt osoba@example.cz'), ('verifiedAt', 'yesterday'),
                             ('verifiedAt', None), ('verifiedAt', '2026-11-12'), ('events', None),
                             ('events', []), ('events', [occurrence()] * 17), ('unexpected', True)]:
            changed = source()['audited_events']
            changed[URL][field] = value
            variants.append(changed)
        for key in source()['audited_events'][URL]:
            changed = source()['audited_events']
            del changed[URL][key]
            variants.append(changed)
        for metadata in variants:
            with self.subTest(metadata=metadata):
                with self.assertRaises(c.Review) as caught:
                    c.parse_event(BODY, dict(source(), audited_events=metadata), URL, WINDOW)
                self.assertNotIsInstance(caught.exception, c.Excluded)
        for change in [dict(index_urls=['https://elsewhere.cz/']), dict(url_regex=r'https://example.cz/not-an-event'), dict(adapter='structured')]:
            with self.subTest(change=change), self.assertRaises(c.Review):
                c.parse_event(BODY, dict(source(), **change), URL, WINDOW)

    def test_fingerprints_bind_semantic_heading_text_and_assets_not_chrome(self):
        samples = {
            'galileo': '<h1>Advent</h1><div class="event-detail">Termín <a href="/info">program</a><img src="/poster.jpg"></div>',
            'humpolec': '<main class="single event"><h1>Advent</h1><section id="content"><div class="container">Termín <img src="/poster.jpg"><div id="related">related</div></div></section></main>',
            'hranice': '<article class="akce-detail"><h1>Advent</h1>Termín</article><div class="akce-content">Program <img src="/poster.jpg"></div>',
            'telc': '<div class="clanek_levy_sloupec">Termín<h2>Advent</h2><img src="/poster.jpg"><strong>Organizátor akce</strong>contact</div>',
            'visitzlin': '<h1>Advent</h1><section class="site-event"><h2>Advent</h2><div class="event">Termín <img src="/poster.jpg"></div></section>'}
        for adapter, body in samples.items():
            with self.subTest(adapter=adapter):
                fp = c.audited_events.fingerprint(body, adapter)
                self.assertRegex(fp, r'^[0-9a-f]{64}$')
                ignored = body.replace('>related<', '>new related<').replace('contact', 'new contact') + '<footer>noise</footer>'
                ignored = ignored.replace('Termín', '  Termín \n <script>noise</script><style>noise</style>')
                self.assertEqual(fp, c.audited_events.fingerprint(ignored, adapter))
                for token in ['Advent', 'Termín', '/poster.jpg']:
                    self.assertNotEqual(fp, c.audited_events.fingerprint(body.replace(token, token + '-changed'), adapter))
                if adapter == 'galileo':
                    self.assertNotEqual(fp, c.audited_events.fingerprint(body.replace('/info', '/new'), adapter))
        for adapter, body in [('galileo', '<h1>Advent</h1>'), ('galileo', '<div class="event-detail">Termín</div>'),
                              ('hranice', '<article class="akce-detail"><h1>Advent</h1>Termín</article>'),
                              ('humpolec', '<h1>Advent</h1><section id="content"></section>'),
                              ('wordpress', '<h1>Advent</h1><main>Termín</main>'),
                              ('telc', '<div class="clanek_levy_sloupec">Termín</div>'),
                              ('visitzlin', '<h1>Advent</h1><main>Termín</main>')]:
            with self.subTest(adapter=adapter, body=body), self.assertRaises(c.audited_events.AuditError):
                c.audited_events.fingerprint(body, adapter)

    def test_occurrences_are_closed_public_facts_with_ordered_times(self):
        changes = [('occurrenceKey', ''), ('occurrenceKey', 'a/b'), ('occurrenceKey', ' a'),
                   ('occurrenceKey', ['key']), ('occurrenceKey', 'x' * 49),
                   ('allowExtendedEnd', 1), ('allowExtendedEnd', None), ('endTime', '16:59'),
                   ('title', 'x' * 181), ('town', ' '), ('description', 'x' * 201),
                   ('price', 'Kontakt +420 777 123 456'), ('notes', ['osoba@example.cz']),
                   ('registrationUrl', 'https://127.0.0.1/secret'), ('registrationUrl', 'javascript:bad'),
                   ('location', {'lat': 50, 'lon': 15}), ('attendees', []), ('sourceUrl', URL),
                   ('location', dict(lat=50, lon=15, precision='town', label='Semily', sourceUrl='https://evil.cz/'))]
        for key, value in changes:
            s = source()
            s['audited_events'][URL]['events'][1][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(c.Review):
                c.parse_event(BODY, s, URL, WINDOW)
        for key in occurrence():
            s = source()
            del s['audited_events'][URL]['events'][1][key]
            with self.subTest(missing=key), self.assertRaises(c.Review):
                c.parse_event(BODY, s, URL, WINDOW)
        s = source()
        s['audited_events'][URL]['events'][1]['occurrenceKey'] = 'dec17'
        with self.assertRaises(c.Review):
            c.parse_event(BODY, s, URL, WINDOW)
        s = source()
        s['audited_events'][URL]['events'][1].update(endDate='2026-12-20', endTime='16:00')
        self.assertEqual(c.parse_event(BODY, s, URL, WINDOW)[1]['endTime'], '16:00')

    def test_extended_end_is_explicit_occurrence_scoped_and_never_2027(self):
        s = source()
        fact = s['audited_events'][URL]['events'][0]
        fact.update(endDate='2026-12-27', allowExtendedEnd=True)
        self.assertEqual(c.parse_event(BODY, s, URL, WINDOW)[0]['endDate'], '2026-12-27')
        for changes in [dict(allowExtendedEnd=False), dict(endDate='2027-01-01'),
                        dict(date='2026-11-19'), dict(date='2026-12-25')]:
            changed = deepcopy(s)
            changed['audited_events'][URL]['events'][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(c.Review):
                c.parse_event(BODY, changed, URL, WINDOW)
        with self.assertRaises(c.Review):
            c.parse_event(BODY, s, URL, dict(WINDOW, through='2026-12-16'))

    def collect(self, p, s, fetcher=None, locations=None):
        result = c.collect(dict(window=WINDOW, season=2026, sources=[s]), p/'db', p/'out',
                           locations or {}, fetcher or Offline())
        return result, json.loads((p/'out/events.json').read_text())['events']

    def test_sqlite_refresh_reorder_removal_and_provenance_are_per_occurrence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, s, client = Path(tmp), source(), Offline()
            result, first = self.collect(p, s, client)
            self.assertEqual(result['metrics']['eventsPublished'], 2)
            ids = {e['date']: e['id'] for e in first}
            self.assertEqual(client.calls, [INDEX, URL])
            self.assertTrue(all(e['verifiedAt'] == STAMP for e in first))
            self.assertTrue(all(e['location'] is None for e in first))
            s['audited_events'][URL]['events'].reverse()
            result, reordered = self.collect(p, s)
            self.assertEqual(result['metrics']['eventsUnchanged'], 2)
            self.assertEqual(ids, {e['date']: e['id'] for e in reordered})
            s['audited_events'][URL]['events'].pop()
            s['audited_events'][URL]['events'][0]['title'] = 'Adventní program – změněný název'
            result, remaining = self.collect(p, s)
            self.assertEqual([e['id'] for e in remaining], [ids['2026-12-19']])
            with closing(sqlite3.connect(p/'db')) as con:
                self.assertEqual(con.execute('SELECT id FROM events').fetchall(), [(ids['2026-12-19'],)])
                fields = {r[0] for r in con.execute('SELECT DISTINCT field FROM provenance WHERE event_id=?', (remaining[0]['id'],))}
                self.assertEqual(fields, v.FIELDS)
                self.assertEqual({r[0] for r in con.execute('SELECT DISTINCT body_hash FROM provenance')}, {c.digest(BODY)})
                self.assertNotEqual(con.execute('SELECT observed_at FROM events').fetchone()[0], STAMP)
                self.assertTrue(con.execute('SELECT count(*) FROM observations').fetchone()[0] >= 3)
            self.assertEqual(result['metrics']['eventsChanged'], 1)
            result, again = self.collect(p, s)
            self.assertEqual([e['id'] for e in again], [ids['2026-12-19']])
            self.assertEqual(result['metrics']['eventsUnchanged'], 1)

    def test_audited_location_is_not_replaced_by_normal_mapping(self):
        s = source()
        s['audited_events'][URL]['events'] = [occurrence()]
        s['event_locations'] = {URL: {'locationKey': 'wrong'}}
        location = dict(lat=50.6, lon=15.3, precision='town', label='Semily', sourceUrl='https://www.openstreetmap.org/relation/438971')
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            _, events = self.collect(p, s, locations={'Semily': location, 'wrong': location})
            self.assertEqual(len(events), 1)
            self.assertIsNone(events[0]['location'])
            s['audited_events'][URL]['events'][0]['location'] = location
            _, events = self.collect(p, s, locations={'Semily': dict(location, lat=49), 'wrong': dict(location, lat=49)})
            self.assertEqual(events[0]['location'], location)

    def test_directory_accepts_only_exact_receipt_public_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, s = Path(tmp), source()
            _, events = self.collect(p, s)
            registry = dict(window=WINDOW, season=2026, sources=[s])
            self.assertEqual(v.validate_directory(p/'out', registry), 2)
            file = p/'out/events.json'
            original = json.loads(file.read_text())
            changes = dict(id='e-imposter', title='Jiný název', town='Telč', region='Zlínský kraj',
                           venue='Jiné místo', date='2026-12-18', endDate='2026-12-18', startTime='16:00',
                           endTime='19:00', category='trhy', price='100 Kč', registration='Nutná rezervace.',
                           registrationUrl='https://example.cz/registration', description='Jiný popis.',
                           notes=['Další poznámka.'], audience='dospělí', status='cancelled',
                           verifiedAt='2026-11-13T11:00:00+00:00', sourceUrl=URL + '2',
                           location=dict(lat=50, lon=15, precision='town', label='Telč', sourceUrl='https://www.openstreetmap.org/relation/1'))
            self.assertEqual(set(changes), v.FIELDS)
            for field, value in changes.items():
                changed = deepcopy(original)
                changed['events'][0][field] = value
                file.write_text(json.dumps(changed))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    v.validate_directory(p/'out', registry)
            file.write_text(json.dumps(original))
            for field, value in [('sourceId', 'wrong'), ('sourceTown', 'wrong'), ('sourceUrl', URL+'2')]:
                bad = deepcopy(registry)
                bad['sources'][0]['audited_events'][URL][field] = value
                with self.subTest(binding=field), self.assertRaises(ValueError):
                    v.validate_directory(p/'out', bad)

    def test_directory_extension_whitelist_comes_from_generated_ids_not_published_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, s = Path(tmp), source()
            s['audited_events'][URL]['events'][0].update(endDate='2026-12-27', allowExtendedEnd=True)
            self.collect(p, s)
            registry = dict(window=WINDOW, season=2026, sources=[s])
            self.assertEqual(v.validate_directory(p/'out', registry), 2)
            file = p/'out/events.json'
            original = json.loads(file.read_text())
            for field, value in [('id', 'e-forged'), ('endDate', '2027-01-01')]:
                changed = deepcopy(original)
                changed['events'][0][field] = value
                file.write_text(json.dumps(changed))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    v.validate_directory(p/'out', registry)
            changed = deepcopy(original)
            changed['events'][1]['endDate'] = '2026-12-27'
            file.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                v.validate_directory(p/'out', registry)

    def test_directory_rejects_removed_receipt_even_for_same_town(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, s = Path(tmp), source()
            for fact in s['audited_events'][URL]['events']:
                fact['town'] = 'Telč'
            self.collect(p, s)
            registry = dict(window=WINDOW, season=2026, sources=[s])
            self.assertEqual(v.validate_directory(p/'out', registry), 2)
            s.pop('audited_events')
            with self.assertRaises(ValueError):
                v.validate_directory(p/'out', registry)

    def test_changes_and_malformed_receipts_withdraw_all_published_occurrences(self):
        for change in ['heading', 'text', 'poster', 'receipt-title', 'receipt-hash', 'null-map', 'null-record', 'bad-second']:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                p, s = Path(tmp), source()
                body = BODY.replace('</p>', '<img src="/poster.jpg"></p>')
                s['audited_events'][URL]['contentHash'] = c.audited_events.fingerprint(body, 'galileo')
                _, first = self.collect(p, s, Offline(body))
                self.assertEqual(len(first), 2)
                if change == 'heading':
                    body = body.replace('<h1>Adventní program', '<h1>Nový adventní program')
                elif change == 'text':
                    body = body.replace('Dva samostatné', 'Tři samostatné')
                elif change == 'poster':
                    body = body.replace('/poster.jpg', '/poster2.jpg')
                elif change == 'receipt-title':
                    s['audited_events'][URL]['expectedTitle'] = 'Jiný titulek'
                elif change == 'receipt-hash':
                    s['audited_events'][URL]['contentHash'] = '0' * 64
                elif change == 'null-map':
                    s['audited_events'] = None
                elif change == 'null-record':
                    s['audited_events'][URL] = None
                elif change == 'bad-second':
                    s['audited_events'][URL]['events'][1]['attendees'] = ['osoba@example.cz']
                result, events = self.collect(p, s, Offline(body))
                self.assertEqual(events, [])
                self.assertEqual(result['metrics']['reviewCount'], 1)
                self.assertEqual(result['metrics']['eventsNew'], 0)
                self.assertEqual(result['metrics']['eventsChanged'], 0)
                self.assertEqual(result['sources'][0]['status'], 'partial')
                self.assertIsNone(result['sources'][0]['lastError'])
                with closing(sqlite3.connect(p/'db')) as con:
                    self.assertEqual(con.execute('SELECT count(*) FROM events').fetchone()[0], 0)
                    self.assertEqual(con.execute('SELECT count(*) FROM provenance').fetchone()[0], 2 * len(v.FIELDS))
                review = json.loads((p/'out/review.json').read_text())
                self.assertEqual(review['candidates'][0]['url'], URL)
                self.assertNotIn('@', json.dumps(review))

    def test_atomic_invalid_second_occurrence_never_writes_first(self):
        from unittest.mock import patch
        for kind in ['receipt', 'parser-list', 'tuple']:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                p, s = Path(tmp), source()
                if kind == 'receipt':
                    s['audited_events'][URL]['events'][1]['startTime'] = '24:00'
                    result, events = self.collect(p, s)
                else:
                    parsed = c.parse_event(BODY, s, URL, WINDOW)
                    del s['audited_events']
                    if kind == 'parser-list':
                        parsed[1]['location'] = {'lat': 0}
                    else:
                        parsed = tuple(parsed)
                    with patch.object(c, 'parse_event', return_value=parsed):
                        result, events = self.collect(p, s)
                self.assertEqual(events, [])
                self.assertEqual(result['metrics']['reviewCount'], 1)
                with closing(sqlite3.connect(p/'db')) as con:
                    self.assertEqual(con.execute('SELECT count(*) FROM events').fetchone()[0], 0)
                    self.assertEqual(con.execute('SELECT count(*) FROM provenance').fetchone()[0], 0)

    def test_hold_and_exclude_are_closed_and_content_bound(self):
        for decision in ['hold', 'exclude']:
            with self.subTest(decision=decision), tempfile.TemporaryDirectory() as tmp:
                p, s = Path(tmp), source()
                self.collect(p, s)
                s['audited_events'][URL].update(decision=decision, events=[])
                result, events = self.collect(p, s)
                self.assertEqual(events, [])
                self.assertEqual(result['metrics']['reviewCount'], int(decision == 'hold'))
                self.assertEqual(result['metrics']['excludedCount'], int(decision == 'exclude'))
                s['audited_events'][URL]['events'] = [occurrence()]
                with self.assertRaises(c.Review) as caught:
                    c.parse_event(BODY, s, URL, WINDOW)
                self.assertNotIsInstance(caught.exception, c.Excluded)
                s['audited_events'][URL]['events'] = []
                s['audited_events'][URL]['expectedTitle'] = 'Jiný titulek'
                with self.assertRaises(c.Review) as caught:
                    c.parse_event(BODY, s, URL, WINDOW)
                self.assertNotIsInstance(caught.exception, c.Excluded)

    def test_default_single_event_parser_and_transport_outage_are_unchanged(self):
        s = source()
        del s['audited_events']
        body = BODY.replace('17. 12. 2026, 19. 12. 2026', '17. 12. 2026 17:00').replace('Semily', 'Panský dvůr Telč')
        event = c.parse_event(body, s, URL, WINDOW)
        self.assertIsInstance(event, dict)
        self.assertEqual(event['id'], 'e-' + c.digest(URL)[:20])
        with tempfile.TemporaryDirectory() as tmp:
            p, s = Path(tmp), source()
            _, first = self.collect(p, s)
            class Outage(Offline):
                def get(self, url):
                    raise OSError('Unavailable')
            result, last_good = self.collect(p, s, Outage())
            self.assertEqual(last_good, first)
            self.assertEqual(result['sources'][0]['status'], 'error')

    def test_percent_encoded_phone_contacts_fail_closed_in_public_text(self):
        from urllib.parse import quote
        raw = 'Kontakt +420 777 123 456'
        for depth in [1, 2, 16]:
            encoded = raw
            for _ in range(depth):
                encoded = quote(encoded, safe='')
            for field in ['reason', 'expectedTitle', 'title', 'town', 'venue', 'price',
                          'registration', 'description', 'notes', 'location']:
                s = source()
                receipt = s['audited_events'][URL]
                if field in ['reason', 'expectedTitle']:
                    receipt[field] = encoded
                elif field == 'notes':
                    receipt['events'][0][field] = [encoded]
                elif field == 'location':
                    receipt['events'][0][field] = dict(lat=50, lon=15, precision='town',
                        label=encoded, sourceUrl='https://www.openstreetmap.org/relation/777123456')
                else:
                    receipt['events'][0][field] = encoded
                with self.subTest(depth=depth, field=field), self.assertRaises(c.audited_events.AuditError):
                    c.audited_events.resolve(s, URL, WINDOW)
        with tempfile.TemporaryDirectory() as tmp:
            p, s = Path(tmp), source()
            self.collect(p, s)
            s['audited_events'][URL]['events'][0]['description'] = quote(raw, safe='')
            result, events = self.collect(p, s)
            self.assertEqual(events, [])
            self.assertEqual(result['metrics']['reviewCount'], 1)

    def test_unsupported_embedded_event_content_requires_new_review(self):
        embeds = ['<iframe srcdoc="Changed date and venue"></iframe>',
                  '<iframe src="https://elsewhere.cz/program"></iframe>',
                  '<frame src="https://elsewhere.cz/program">',
                  '<object data="https://elsewhere.cz/program"></object>',
                  '<embed src="https://elsewhere.cz/program">']
        for embed in embeds:
            body = BODY.replace('</div>', embed + '</div>', 1)
            with self.subTest(embed=embed), self.assertRaises(c.audited_events.AuditError):
                c.audited_events.fingerprint(body, 'galileo')
        with tempfile.TemporaryDirectory() as tmp:
            p, s = Path(tmp), source()
            self.collect(p, s)
            body = BODY.replace('</div>', embeds[0] + '</div>', 1)
            result, events = self.collect(p, s, Offline(body))
            self.assertEqual(events, [])
            self.assertEqual(result['metrics']['reviewCount'], 1)

    def test_bounded_receipt_text_rejects_padding_and_phone_contacts(self):
        for field, value in [('reason', ' ' * 501 + 'Ověřeno.'), ('expectedTitle', ' ' * 181 + TITLE),
                             ('reason', 'Kontakt +420 777 123 456')]:
            s = source()
            s['audited_events'][URL][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(c.audited_events.AuditError):
                c.audited_events.resolve(s, URL, WINDOW)
        s = source()
        s['audited_events'][URL]['events'][0]['location'] = dict(lat=50, lon=15, precision='town',
            label='Semily', sourceUrl='https://www.openstreetmap.org/relation/777123456')
        self.assertEqual(len(c.parse_event(BODY, s, URL, WINDOW)), 2)

    def test_directory_preserves_valueerror_contract_for_malformed_public_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, s = Path(tmp), source()
            for fact in s['audited_events'][URL]['events']:
                fact['town'] = 'Telč'
            self.collect(p, s)
            s.pop('audited_events')
            registry = dict(window=WINDOW, season=2026, sources=[s])
            file = p/'out/events.json'
            original = json.loads(file.read_text())
            for changed_event in [dict(original['events'][0], id=123),
                                  {k: value for k, value in original['events'][0].items() if k != 'id'}]:
                changed = deepcopy(original)
                changed['events'][0] = changed_event
                file.write_text(json.dumps(changed))
                with self.subTest(event=changed_event), self.assertRaises(ValueError):
                    v.validate_directory(p/'out', registry)


if __name__ == '__main__':
    unittest.main()
