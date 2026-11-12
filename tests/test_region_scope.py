"""Portable registry-bound publication gates; no live data writes or network."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('scope_validator', ROOT/'scripts/validate_public.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

REGIONS = ['Plzeňský kraj', 'Liberecký kraj', 'Jihomoravský kraj', 'Středočeský kraj', 'Jihočeský kraj', 'Kraj Vysočina']

def documents():
    sources = [dict(id=f'source-{i}', town=f'Obec {i}', region=region,
                    index_urls=[f'https://source{i}.example.cz/program/'],
                    url_regex=rf'^https://source{i}\.example\.cz/program/[^/?#]+$')
               for i, region in enumerate(REGIONS * 2)]
    registry = dict(season=2026, window=dict(**{'from': '2026-11-20', 'through': '2026-12-24'}), sources=sources)
    events = [dict(id=f'e-{i}', title='Vánoční trhy', town=s['town'], region=s['region'], venue=None,
                   date='2026-11-28', endDate=None, startTime='16:30', endTime=None, category='trhy',
                   price=None, registration=None, registrationUrl=None, description='Vánoční trhy', notes=[],
                   audience='všichni', status='confirmed', verifiedAt='2026-11-12T12:00:00+00:00',
                   sourceUrl=s['index_urls'][0]+'trhy', location=None) for i, s in enumerate(sources)]
    data = dict(schemaVersion=1, season=2026, generatedAt=events[0]['verifiedAt'], region='Česko', events=events)
    coverage = dict(complete=False, window=registry['window'], regions=REGIONS,
                    metrics=dict(eventsPublished=len(events), reviewCount=0),
                    sources=[dict(id=s['id'], town=s['town'], region=s['region'], url=s['index_urls'][0], status='ok') for s in sources])
    return registry, data, coverage, dict(candidates=[])

class RegionScopeTests(unittest.TestCase):
    def check_directory(self, registry, data, coverage, review):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            for name, document in [('events', data), ('coverage', coverage), ('review', review)]:
                (path/f'{name}.json').write_text(json.dumps(document))
            return v.validate_directory(path, registry=registry)

    def test_directory_derives_six_region_scope_from_registry(self):
        self.assertEqual(self.check_directory(*documents()), 12)
        registry, data, coverage, review = documents()
        registry['sources'] = registry['sources'][:3]
        data['events'] = data['events'][:3]
        coverage['sources'] = coverage['sources'][:3]
        coverage['regions'] = REGIONS[:3]
        coverage['metrics']['eventsPublished'] = 3
        self.assertEqual(self.check_directory(registry, data, coverage, review), 3)

    def test_coverage_identity_is_bound_to_registry(self):
        for field, value in [('id', 'unregistered'), ('id', 'source-1'), ('region', 'Liberecký kraj'),
                             ('town', 'Jiná obec'), ('url', 'https://other.example.cz/')]:
            docs = documents()
            docs[2]['sources'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.check_directory(*docs)
        docs = documents()
        docs[0]['sources'][0]['id'] = 'source-1'
        with self.assertRaises(ValueError):self.check_directory(*docs)

    def test_event_provenance_requires_matching_source_town_and_region(self):
        for field, value in [('region', 'Liberecký kraj'), ('town', 'Obec 1'),
                             ('sourceUrl', 'https://unregistered.example.cz/trhy'),
                             ('sourceUrl', 'https://source1.example.cz/program/trhy')]:
            docs = documents()
            docs[1]['events'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):self.check_directory(*docs)
        docs = documents()
        url = docs[1]['events'][0]['sourceUrl']
        docs[0]['sources'][0]['event_locations'] = {url: dict(town='Nebřeziny', sourceId='source-0',
            sourceTown='Obec 0', sourceUrl=url, expectedDate='2026-11-28', expectedVenue='Nebřeziny')}
        docs[1]['events'][0].update(town='Nebřeziny', venue='Nebřeziny')
        self.assertEqual(self.check_directory(*docs), 12)
        docs[0]['sources'][0]['event_locations'][url]['sourceId'] = 'source-1'
        with self.assertRaises(ValueError):self.check_directory(*docs)

    def test_registry_window_and_season_govern_projection(self):
        for change in ['season', 'narrow', 'wide', 'coverage']:
            docs = documents()
            if change == 'season':docs[0]['season'] = 2027
            if change == 'narrow':docs[0]['window'] = {'from': '2026-12-01', 'through': '2026-12-24'}
            if change == 'wide':docs[0]['window'] = {'from': '2026-11-01', 'through': '2026-12-24'}
            if change == 'coverage':docs[2]['window'] = {'from': '2026-11-21', 'through': '2026-12-24'}
            with self.subTest(change=change), self.assertRaises(ValueError):self.check_directory(*docs)

    def test_canonical_czech_regions_not_arbitrary_names(self):
        _, data, _, _ = documents()
        self.assertTrue(v.validate(data))
        for region in ['Atlantida', 'Vysočina', 'Stredocesky kraj', '']:
            bad = copy.deepcopy(data)
            bad['events'][0]['region'] = region
            with self.subTest(region=region), self.assertRaises(ValueError):
                v.validate(bad)
