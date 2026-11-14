"""Portable reviewed projection lifecycle tests: real SQLite, no live network."""
import copy
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/f'{name}.py')
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class Feed:
    stats = {}
    def __init__(self, data=None):
        self.data = data
        self.urls = []
    def get(self, url):
        self.urls.append(url)
        if self.data is None:
            raise OSError('unavailable secret@example.cz /private/config')
        return json.dumps(self.data, ensure_ascii=False).encode()

class ReviewedTests(unittest.TestCase):
    def setUp(self):
        self.c = module('collector')
        self.snapshot = json.loads((ROOT/'data/reviewed-events.json').read_text())
        registry = json.loads((ROOT/'data/sources.json').read_text())
        self.registry = dict(registry, sources=[s for s in registry['sources'] if s['adapter']=='reviewed-public'])
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name)/'events.sqlite'
        self.out = Path(self.tmp.name)/'out'
    def collect(self, feed=None, **kwargs):
        return self.c.collect(self.registry, self.db, self.out, {}, feed or Feed(), **kwargs)
    def feed_data(self, **changes):
        data = copy.deepcopy(self.snapshot)
        for event in data['events']:
            event.pop('region')  # actual owned public feed does not carry event regions
        data.update(changes)
        return data
    def events(self):
        return json.loads((self.out/'events.json').read_text())['events']
    def test_reviewed_only_refresh_preserves_live_records_state_and_review_without_fetching(self):
        live = copy.deepcopy(json.loads((ROOT/'data/sources.json').read_text())['sources'][0])
        live['seed_urls'] = live['seed_urls'][:1]
        self.registry['sources'].append(live)
        detail = (ROOT/'tests/fixtures/research/pilot-plzensky/fixtures/plasy_tree.html').read_bytes()
        settings = {'url':'https://owned.example.cz/events.json'}
        original = self.feed_data()
        class MixedFeed(Feed):
            def get(self, url):
                if url == settings['url']:
                    return super().get(url)
                self.urls.append(url)
                return detail if url in live['seed_urls'] else b'<html></html>'
        first = MixedFeed(original)
        self.collect(first, reviewed_feed=settings)
        self.assertIn(live['index_urls'][0], first.urls)  # default is still full collection
        self.assertIn(live['seed_urls'][0], first.urls)
        before = {e['id']:e for e in self.events()}
        self.assertEqual(len(before), len(original['events'])+1)
        with closing(sqlite3.connect(self.db)) as con:
            con.execute('INSERT INTO reviews VALUES (?,?,?,?,?)',
                        (live['id'],live['index_urls'][0],'Ke kontrole','Nejasný termín','2026-11-12T10:00:00+01:00'))
            con.commit()
            stored = {table:con.execute(f'SELECT * FROM {table} WHERE source_id=?',(live['id'],)).fetchall()
                      for table in ('events','reviews','observations','exclusions')}
            state = con.execute('SELECT payload FROM source_state WHERE id=?',(live['id'],)).fetchone()
            provenance = con.execute('SELECT * FROM provenance').fetchall()
        revised = self.feed_data(generatedAt='2026-11-13T11:00:00+01:00')
        removed = revised['events'].pop(0)['id']
        revised['events'][0]['title'] = 'Vánoční program – aktualizace'
        feed = Feed(revised)
        result = self.collect(feed, reviewed_feed=settings, reviewed_only=True)
        self.assertEqual(feed.urls, [settings['url']])
        expected = dict(before)
        expected.pop(removed)
        changed = revised['events'][0]
        expected[changed['id']] = dict(changed, region='Středočeský kraj')
        self.assertEqual({e['id']:e for e in self.events()}, expected)
        self.assertEqual(len(result['sources']), len(self.registry['sources']))
        self.assertIn('Ke kontrole', (self.out/'review.json').read_text())
        with closing(sqlite3.connect(self.db)) as con:
            for table, rows in stored.items():
                self.assertEqual(con.execute(f'SELECT * FROM {table} WHERE source_id=?',(live['id'],)).fetchall(), rows)
            self.assertEqual(con.execute('SELECT payload FROM source_state WHERE id=?',(live['id'],)).fetchone(), state)
            self.assertEqual(con.execute('SELECT * FROM provenance').fetchall()[:len(provenance)], provenance)
        failed = Feed()
        self.collect(failed, reviewed_feed=settings, reviewed_only=True)
        self.assertEqual(failed.urls, [settings['url']])
        self.assertEqual({e['id']:e for e in self.events()}, expected)
        unconfigured = Feed()
        self.collect(unconfigured, reviewed_only=True)
        self.assertEqual(unconfigured.urls, [])
        self.assertEqual({e['id']:e for e in self.events()}, expected)
        self.assertEqual(module('validate_public').validate_directory(self.out,self.registry), len(expected))

    def test_collector_cli_forwards_reviewed_only_and_defaults_to_full(self):
        from contextlib import redirect_stdout
        import io
        from unittest.mock import patch
        path = Path(self.tmp.name)/'registry.json'
        path.write_text(json.dumps(self.registry))
        args = ['--registry',str(path),'--db',str(self.db),
                '--cache',str(self.db.parent/'cache'),'--output',str(self.out)]
        for extra, expected in [([],False),(['--reviewed-only'],True)]:
            with self.subTest(extra=extra), patch.object(self.c,'HTTPClient'), \
                    patch.object(self.c,'collect',return_value={}) as collect, redirect_stdout(io.StringIO()):
                self.assertEqual(self.c.main(args+extra),0)
                self.assertEqual(collect.call_args.kwargs.get('reviewed_only',False),expected)

    def test_four_new_reviewed_groups_bind_only_exact_host_town_and_approved_location(self):
        expected = [
            ('www.zus-popo.net','Velké Popovice',{'lat':49.9224718,'lon':14.6390582,
             'precision':'town','label':'Velké Popovice','sourceUrl':'https://www.openstreetmap.org/relation/437951'}),
            ('www.osadaladvi.cz','Ládví',None),
            ('www.strancice.cz','Strančice',None),
            ('www.krestanskevanoce.cz','Hrusice',{'lat':49.9114356,'lon':14.7395227,
             'precision':'town','label':'Hrusice','sourceUrl':'https://www.openstreetmap.org/relation/437181'}),
        ]
        sources = self.registry['sources']
        for host,town,location in expected:
            with self.subTest(host=host):
                matches = [s for s in sources if s['primary_host']==host]
                self.assertEqual(len(matches),1)
                source = matches[0]
                self.assertEqual(source['allowed_towns'],{town:'Středočeský kraj'})
                self.assertEqual(source['allowed_locations'],{town:[location] if location else []})
                event = dict(self.snapshot['events'][0],sourceUrl=f'https://{host}/program',
                             town=town,region='Středočeský kraj',location=location)
                self.assertEqual(self.c.reviewed_public.binding(event,sources)['id'],source['id'])
                for change in [{'town':'Jiná obec'}, {'sourceUrl':f'https://other.{host}/program'},
                               {'location':dict(location or {},lat=50.5)}, {'region':'Plzeňský kraj'}]:
                    with self.subTest(change=change), self.assertRaises(ValueError):
                        self.c.reviewed_public.binding(dict(event,**change),sources)

    def test_jevany_reviewed_group_is_bound_to_municipal_calendar_and_null_location(self):
        sources = self.registry['sources']
        source = next(s for s in sources if s['id'] == 'reviewed-www-obecjevany-cz')
        self.assertEqual(source['allowed_towns'], {'Jevany': 'Středočeský kraj'})
        self.assertEqual(source['allowed_locations'], {'Jevany': []})
        event = dict(self.snapshot['events'][0], town='Jevany', region='Středočeský kraj',
                     location=None, sourceUrl='https://www.obecjevany.cz/aktuality-1/kalendar-akci/mikulasska-besidka-1904_200cs.html')
        self.assertEqual(self.c.reviewed_public.binding(event, sources)['id'], source['id'])
        for change in [{'town': 'Říčany'}, {'region': 'Praha'},
                       {'location': self.snapshot['events'][0]['location']},
                       {'sourceUrl': event['sourceUrl'].replace('www.obecjevany.cz', 'other.obecjevany.cz')},
                       {'sourceUrl': 'https://www.obecjevany.cz/aktuality-1/novinky/pozvanka.html'}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.c.reviewed_public.binding(dict(event, **change), sources)

    def test_snapshot_survives_daily_recollection_without_invented_verification(self):
        first = self.collect()
        self.assertEqual(len(self.events()), 51)
        self.assertEqual({e['id']:e for e in self.events()}, {e['id']:e for e in self.snapshot['events']})
        second = self.collect()
        self.assertEqual(second['metrics']['eventsPublished'], 51)
        self.assertTrue(all(s['status']=='partial' and s['lastSuccess'] is None for s in first['sources']))
        with closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(con.execute('SELECT count(*) FROM events').fetchone()[0], 51)
            self.assertGreater(con.execute('SELECT count(*) FROM provenance').fetchone()[0], 51)
        self.assertEqual(module('validate_public').validate_directory(self.out, self.registry), 51)

    def test_successful_feed_removal_is_durable_even_after_feed_outage_or_config_loss(self):
        self.collect()
        data = self.feed_data(generatedAt='2026-11-13T11:00:00+01:00')
        removed = data['events'].pop(0)['id']
        feed = Feed(data)
        result = self.collect(feed, reviewed_feed={'url':'https://owned.example.cz/events.json'})
        self.assertEqual(len(feed.urls), 1)
        self.assertEqual(len(self.events()), 50)
        self.assertNotIn(removed, {e['id'] for e in self.events()})
        self.assertTrue(all(s['status']=='ok' and s['lastSuccess'] for s in result['sources']))
        self.collect(Feed(), reviewed_feed={'url':'https://owned.example.cz/events.json'})
        self.assertEqual(len(self.events()), 50)
        self.collect()
        self.assertEqual(len(self.events()), 50)
        self.assertEqual(module('validate_public').validate_directory(self.out, self.registry), 50)

    def test_invalid_changed_record_withdraws_only_affected_id_and_never_leaks_private_fields(self):
        settings = {'url':'https://owned.example.cz/events.json'}
        self.collect(Feed(self.feed_data()), reviewed_feed=settings)
        data = self.feed_data(generatedAt='2026-11-13T11:00:00+01:00')
        bad = data['events'][0]
        bad['attendees'] = [{'email':'secret@example.cz'}]
        result = self.collect(Feed(data), reviewed_feed=settings)
        self.assertEqual(len(self.events()), 50)
        self.assertNotIn(bad['id'], {e['id'] for e in self.events()})
        self.assertEqual(result['metrics']['reviewCount'], 1)
        self.assertTrue(any(s['status']=='partial' for s in result['sources']))
        for name in ['events','coverage','review']:
            text = (self.out/f'{name}.json').read_text()
            self.assertNotIn('secret', text)
            self.assertNotIn('attendees', text)
            self.assertNotIn('owned.example', text)
        self.collect(Feed(), reviewed_feed=settings)
        self.assertEqual(len(self.events()), 50)
        self.collect()
        self.assertEqual(len(self.events()), 50)
        self.assertEqual(module('validate_public').validate_directory(self.out, self.registry), 50)

    def assert_encoded_description_is_withdrawn(self, description):
        settings = {'url':'https://owned.example.cz/events.json'}
        self.collect(Feed(self.feed_data()), reviewed_feed=settings)
        before = {e['id']:e for e in self.events()}
        data = self.feed_data(generatedAt='2026-11-13T11:00:00+01:00')
        bad = data['events'][0]
        bad['description'] = description
        result = self.collect(Feed(data), reviewed_feed=settings)
        before.pop(bad['id'])
        self.assertEqual({e['id']:e for e in self.events()}, before)
        self.assertEqual(result['metrics']['reviewCount'], 1)
        with closing(sqlite3.connect(self.db)) as con:
            self.assertIsNone(con.execute('SELECT id FROM events WHERE id=?', (bad['id'],)).fetchone())
            self.assertEqual(con.execute('SELECT count(*) FROM events').fetchone()[0], 50)
        for name in ['events','coverage','review']:
            self.assertNotIn(description, (self.out/f'{name}.json').read_text())
        self.assertEqual(module('validate_public').validate_directory(self.out, self.registry), 50)
        self.collect(Feed(), reviewed_feed=settings)
        self.collect()
        self.assertEqual({e['id']:e for e in self.events()}, before)
        self.assertEqual(module('validate_public').validate_directory(self.out, self.registry), 50)

    def test_triple_encoded_contact_is_withdrawn_through_feed_lifecycle(self):
        self.assert_encoded_description_is_withdrawn('contact%252540example.cz')

    def test_very_deep_encoding_is_withdrawn_through_feed_lifecycle(self):
        # No private token underneath: exhausting the decoding bound must itself reject.
        self.assert_encoded_description_is_withdrawn('Sleva %' + '25' * 64)

    def test_ordinary_and_directory_validation_reject_nested_privacy_or_excessive_encoding(self):
        self.collect()
        validator = module('validate_public')
        path = self.out/'events.json'
        original = json.loads(path.read_text())
        for description in ['contact%252540example.cz',
                            'contact%' + '25' * 64 + '40example.cz',
                            'Sleva %' + '25' * 64]:
            with self.subTest(description=description):
                data = copy.deepcopy(original)
                data['events'][0]['description'] = description
                ordinary = dict(data, events=[dict(data['events'][0], endDate=None)])
                with self.subTest(route='ordinary'), self.assertRaises(ValueError):
                    validator.validate(ordinary)
                path.write_text(json.dumps(data, ensure_ascii=False))
                with self.subTest(route='directory'), self.assertRaises(ValueError):
                    validator.validate_directory(self.out, self.registry)
        path.write_text(json.dumps(original, ensure_ascii=False))

    def test_coverage_and_review_use_the_same_nested_privacy_guard(self):
        self.collect()
        validator = module('validate_public')
        for name in ['coverage','review']:
            path = self.out/f'{name}.json'
            original = json.loads(path.read_text())
            for value in ['contact%252540example.cz', 'Sleva %' + '25' * 64]:
                with self.subTest(document=name, value=value):
                    data = copy.deepcopy(original)
                    if name == 'coverage':
                        data['sources'][0]['sourceNote'] = value
                    else:
                        data['candidates'].append({'title':'Ke kontrole',
                                                   'url':self.registry['sources'][0]['index_urls'][0],
                                                   'reason':value})
                        coverage_path = self.out/'coverage.json'
                        coverage = json.loads(coverage_path.read_text())
                        coverage['metrics']['reviewCount'] = len(data['candidates'])
                        coverage_path.write_text(json.dumps(coverage, ensure_ascii=False))
                    path.write_text(json.dumps(data, ensure_ascii=False))
                    with self.assertRaises(ValueError):
                        validator.validate_directory(self.out, self.registry)
            path.write_text(json.dumps(original, ensure_ascii=False))

    def test_safe_encoded_urls_and_stable_percent_are_preserved(self):
        validator = module('validate_public')
        event = dict(self.snapshot['events'][0], endDate=None,
                     description='Sleva 25%25; doslovné % a %zz.',
                     registrationUrl='https://public.example.cz/V%C3%A1noce%20a%2520trhy?discount=25%25')
        data = dict(self.snapshot, events=[event])
        original = copy.deepcopy(data)
        self.assertTrue(validator.validate(data))
        self.assertEqual(data, original)

    def test_unreviewed_coordinates_are_withdrawn_not_silently_accepted(self):
        data = self.feed_data()
        data['events'][0]['location']['lat'] = 50.5
        result = self.collect(Feed(data), reviewed_feed={'url':'https://owned.example.cz/events.json'})
        self.assertEqual(len(self.events()), 50)
        self.assertEqual(result['metrics']['reviewCount'], 1)

    def test_older_feed_cannot_resurrect_removed_records_and_high_water_survives_rejection(self):
        settings = {'url':'https://owned.example.cz/events.json'}
        latest = self.feed_data(generatedAt='2026-11-14T10:00:00+01:00')
        latest['events'].pop(0)
        self.collect(Feed(latest), reviewed_feed=settings)
        stale = self.feed_data(generatedAt='2026-11-13T10:00:00+01:00')
        for _ in range(2):
            result = self.collect(Feed(stale), reviewed_feed=settings)
            self.assertEqual(self.events(), [])
            self.assertTrue(all(s['status']=='error' for s in result['sources']))
        # A fresh valid projection repairs the withdrawn feed; fallback cannot.
        self.collect()
        self.assertEqual(self.events(), [])
        self.collect(Feed(latest), reviewed_feed=settings)
        self.assertEqual(len(self.events()), 50)

    def test_duplicate_ids_withdraw_both_candidates_without_dropping_unrelated_records(self):
        data = self.feed_data()
        duplicate = copy.deepcopy(data['events'][0])
        duplicate['title'] = 'Jiná vánoční akce'
        data['events'].append(duplicate)
        result = self.collect(Feed(data), reviewed_feed={'url':'https://owned.example.cz/events.json'})
        self.assertEqual(len(self.events()), 50)
        self.assertNotIn(duplicate['id'], {e['id'] for e in self.events()})
        self.assertEqual(result['metrics']['reviewCount'], 1)

    def test_cli_refreshes_owned_feed_offline_and_publisher_passes_private_settings(self):
        import subprocess
        import sys
        from unittest.mock import patch
        tmp = Path(self.tmp.name)
        settings = tmp/'private/reviewed-feed.json'
        settings.parent.mkdir()
        settings.write_text(json.dumps({'url':'https://owned.example.cz/events.json'}))
        (tmp/'registry.json').write_text(json.dumps(self.registry))
        (tmp/'feed.json').write_text(json.dumps(self.feed_data()))
        (tmp/'manifest.json').write_text(json.dumps({'https://owned.example.cz/events.json':'feed.json'}))
        cmd = [sys.executable,str(ROOT/'scripts/collector.py'),'--registry',str(tmp/'registry.json'),
               '--db',str(self.db),'--cache',str(tmp/'cache'),'--output',str(self.out),
               '--reviewed-feed-config',str(settings),'--offline-fixtures',str(tmp/'manifest.json')]
        result = subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)['metrics']['eventsPublished'],51)
        self.assertEqual(module('validate_public').validate_directory(self.out,self.registry),51)
        pub = module('publish_daily')
        calls = []
        def command(root,args,timeout=60):
            calls.append((args,timeout))
            return '{}'
        with patch.object(pub,'command',side_effect=command):
            pub.collect_projection(tmp)
        args,timeout = calls[0]
        self.assertEqual(timeout,1800)
        self.assertEqual(args[args.index('--reviewed-feed-config')+1],str(settings))

    def test_strict_reviewed_values_are_fail_closed_per_record(self):
        for field,value in [('town','Neznámá obec'),('region','Plzeňský kraj'),
                            ('sourceUrl','https://unregistered.example.cz/akce'),
                            ('sourceUrl',self.snapshot['events'][0]['sourceUrl']+'#unreviewed'),
                            ('startTime',False),('endDate',[]),
                            ('notes',['calendarId: private-token']),
                            ('description','contact%40example.cz')]:
            with self.subTest(field=field,value=value):
                data = self.feed_data()
                data['events'][0][field] = value
                # Separate portable DB for each independent schema case.
                case = Path(self.tmp.name)/str(abs(hash((field,str(value)))))
                result = self.c.collect(self.registry,case/'db',case/'out',{},Feed(data),reviewed_feed={'url':'https://owned.example.cz/events.json'})
                events = json.loads((case/'out/events.json').read_text())['events']
                self.assertEqual(len(events),50)
                self.assertGreaterEqual(result['metrics']['reviewCount'],1)

    def test_root_privacy_failure_withdraws_all_and_empty_feed_never_bootstraps_again(self):
        settings = {'url':'https://owned.example.cz/events.json'}
        self.collect(Feed(self.feed_data()),reviewed_feed=settings)
        data = self.feed_data(generatedAt='2026-11-13T10:00:00+01:00')
        data['calendarId'] = 'secret@example.cz'
        result = self.collect(Feed(data),reviewed_feed=settings)
        self.assertEqual(self.events(),[])
        self.assertTrue(all(s['status']=='error' for s in result['sources']))
        self.collect()
        self.assertEqual(self.events(),[])
        data.pop('calendarId')
        data['events'] = []
        result = self.collect(Feed(data),reviewed_feed=settings)
        self.assertEqual(self.events(),[])
        self.assertTrue(all(s['status']=='ok' for s in result['sources']))
        self.collect(Feed(),reviewed_feed=settings)
        self.assertEqual(self.events(),[])
        self.assertEqual(module('validate_public').validate_directory(self.out,self.registry),0)

    def test_identical_replay_preserves_evidence_dates_but_changed_same_timestamp_fails_closed(self):
        data = self.feed_data()
        original = copy.deepcopy(data)
        settings = {'url':'https://owned.example.cz/events.json'}
        self.collect(Feed(data),reviewed_feed=settings)
        result = self.collect(Feed(data),reviewed_feed=settings)
        self.assertEqual(result['metrics']['eventsUnchanged'],51)
        self.assertEqual(data,original)
        self.assertEqual({e['id']:e['verifiedAt'] for e in self.events()}, {e['id']:e['verifiedAt'] for e in data['events']})
        with closing(sqlite3.connect(self.db)) as con:
            primary = con.execute('SELECT body_hash,observed_at FROM provenance WHERE event_id=?',(data['events'][0]['id'],)).fetchall()
            self.assertTrue(all(h is None and stamp==data['events'][0]['verifiedAt'] for h,stamp in primary))
            transfer = con.execute('SELECT feed_url,body_hash,evidence_at,origin FROM reviewed_provenance').fetchall()
            self.assertTrue(all(url==settings['url'] and len(h)==64 and origin=='feed' for url,h,at,origin in transfer))
        data['events'].pop(0)
        self.collect(Feed(data),reviewed_feed=settings)
        self.assertEqual(self.events(),[])

    def test_reviewed_database_failure_is_fatal_and_releases_transaction(self):
        with closing(sqlite3.connect(self.db)) as con:
            con.execute('CREATE TABLE events(id TEXT PRIMARY KEY,source_id TEXT,url TEXT,fingerprint TEXT,payload TEXT,observed_at TEXT)')
            con.execute("CREATE TRIGGER fail BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'disk failure'); END")
            con.commit()
        with self.assertRaises(sqlite3.Error):
            self.collect()
        self.assertFalse((self.out/'events.json').exists())
        with closing(sqlite3.connect(self.db,timeout=0.01)) as con:
            con.execute('DROP TRIGGER fail')
            con.commit()
        self.collect()
        self.assertEqual(len(self.events()),51)

    def test_existing_unrelated_id_cannot_be_overwritten_and_collision_is_reviewed(self):
        self.collect()
        legacy = dict(self.snapshot['events'][0],id='e-existing-legacy')
        with closing(sqlite3.connect(self.db)) as con:
            con.execute('INSERT INTO events VALUES (?,?,?,?,?,?)',(legacy['id'],'legacy-source','https://legacy.example.cz/akce','legacy-fingerprint',json.dumps(legacy),'2026-11-12'))
            con.commit()
        data = self.feed_data()
        data['events'][0]['id'] = legacy['id']
        result = self.collect(Feed(data),reviewed_feed={'url':'https://owned.example.cz/events.json'})
        self.assertEqual(len(self.events()),50)
        self.assertEqual(result['metrics']['reviewCount'],1)
        with closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(con.execute('SELECT source_id,fingerprint FROM events WHERE id=?',(legacy['id'],)).fetchone(),('legacy-source','legacy-fingerprint'))

if __name__ == '__main__':
    unittest.main()
