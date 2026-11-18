"""Published-state adoption: disposable real Git/SQLite, never production writes."""

from contextlib import closing
from datetime import date

import io
import json
import os
from pathlib import Path

import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import collector
import publish_daily as pub
import sync_published as sync

STAMP = '2026-11-12T10:00:00+01:00'

def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True,
                          text=True, capture_output=True).stdout.strip()

def fixture(root):
    source = dict(id='town-a', town='Obec A', region='Středočeský kraj', adapter='galileo',
                  index_urls=['https://town.example.cz/events/'],
                  url_regex=r'https://town\.example\.cz/events/[^/?#]+')
    registry = dict(season=2026, window={'from':'2026-11-20','through':'2026-12-24'}, sources=[source])
    event = dict(id='e-first', title='Vánoční trhy', town=source['town'], region=source['region'],
                 venue='Náměstí', date='2026-11-28', endDate=None, startTime='16:30', endTime=None,
                 category='trhy', price=None, registration=None, registrationUrl=None,
                 description='Vánoční trhy', notes=[], audience='všichni', status='confirmed',
                 verifiedAt=STAMP, sourceUrl=source['index_urls'][0]+'first', location=None)
    (root/'data').mkdir(exist_ok=True)
    (root/'data/sources.json').write_text(json.dumps(registry))
    (root/'private').mkdir(exist_ok=True)
    class Offline:
        stats = {}
        def get(self, url): raise AssertionError('no HTTP')
    collector.collect(registry, root/'private/events.sqlite', root/'site', {}, Offline(), reviewed_only=True)
    return registry, event

def write_projection(root, registry, events, candidates=()):
    data = dict(schemaVersion=1, season=2026, generatedAt=STAMP, region='Česko', events=events)
    coverage = dict(generatedAt=STAMP, complete=False, window=registry['window'],
                    regions=list(dict.fromkeys(s['region'] for s in registry['sources'])),
                    metrics=dict(eventsPublished=len(events), reviewCount=len(candidates)),
                    sources=[dict(id=s['id'], town=s['town'], region=s['region'],
                                  url=s['index_urls'][0], status='ok', lastChecked=STAMP,
                                  lastSuccess=STAMP) for s in registry['sources']])
    docs = {'events':data, 'coverage':coverage, 'review':dict(generatedAt=STAMP,candidates=list(candidates))}
    for name, document in docs.items():
        (root/f'site/{name}.json').write_text(json.dumps(document, ensure_ascii=False)+'\n')
    return docs

def store(root, event, sid='town-a'):
    with closing(sqlite3.connect(root/'private/events.sqlite')) as con, con:
        sha = collector.digest(json.dumps({k:v for k,v in event.items() if k!='verifiedAt'}, sort_keys=True, ensure_ascii=False))
        con.execute('INSERT INTO events VALUES (?,?,?,?,?,?)',
                    (event['id'],sid,event['sourceUrl'],sha,json.dumps(event),STAMP))

class RuntimeSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base/'runtime'; self.root.mkdir()
        self.registry, self.first = fixture(self.root)
        self.second = dict(self.first, id='e-second', title='Mikuláš', sourceUrl='https://town.example.cz/events/second')
        self.docs = write_projection(self.root, self.registry, [self.first])
        store(self.root, self.first)
        git(self.root,'init','-b','main')
        git(self.root,'config','user.name','Test'); git(self.root,'config','user.email','test@example.invalid')
        (self.root/'.gitignore').write_text('private/\n')
        git(self.root,'add','.'); git(self.root,'commit','-m','Initial')
        self.remote = self.base/'remote.git'
        subprocess.run(['git','init','--bare',str(self.remote)],check=True,capture_output=True)
        git(self.root,'remote','add','origin',str(self.remote)); git(self.root,'push','origin','main')
        self.foreign = self.base/'foreign'
        subprocess.run(['git','clone','--branch','main',str(self.remote),str(self.foreign)],check=True,capture_output=True)
        git(self.foreign,'config','user.name','Other'); git(self.foreign,'config','user.email','other@example.invalid')

    def advance(self, events=None):
        write_projection(self.foreign, self.registry, events or [self.first,self.second])
        git(self.foreign,'add','.'); git(self.foreign,'commit','-m','Approved public additions')
        git(self.foreign,'push','origin','main')
        return git(self.foreign,'rev-parse','HEAD')

    def rows(self, table='events'):
        with closing(sqlite3.connect(self.root/'private/events.sqlite')) as con:
            return con.execute('SELECT * FROM '+table).fetchall()

    def test_unowned_published_review_is_quarantined_without_blocking_valid_events(self):
        candidate = dict(url='https://unknown.example.cz/unassigned', title='K ověření', reason='Ověřit vlastníka')
        write_projection(self.root,self.registry,[self.first,self.second],[candidate])
        result = sync.adopt_published(self.root,git(self.root,'rev-parse','HEAD'),baseline=self.docs)
        self.assertEqual(result['inserted'],1)
        self.assertEqual(self.rows('reviews'),[])
        self.assertEqual(self.rows('published_orphan_reviews')[0][:3],
                         (candidate['url'],candidate['title'],candidate['reason']))
        with closing(sqlite3.connect(self.root/'private/events.sqlite')) as con:
            self.assertEqual(collector.projected_reviews(con, {'town-a'}), [candidate])
        self.assertEqual(len(self.rows()),2)

    def test_live_verified_detail_clears_an_unassigned_hold_without_publishing_it(self):
        url = self.first['sourceUrl']
        with closing(sqlite3.connect(self.root/'private/events.sqlite')) as con, con:
            con.execute('CREATE TABLE published_orphan_reviews (url TEXT, title TEXT, reason TEXT, published_commit TEXT, PRIMARY KEY(url,title,reason))')
            con.execute('INSERT INTO published_orphan_reviews VALUES (?,?,?,?)',
                        (url,'Old hold','Ověřit vlastníka','a'*40))
        from test_three_source_expansion import fragment
        body = fragment('Vánoční trhy','2026-11-28','Náměstí').encode()
        class ActualDetail:
            stats = {}
            def get(self, value):
                return body if value == url else b'<html></html>'
        collector.collect(self.registry,self.root/'private/events.sqlite',self.root/'preview',{},ActualDetail())
        self.assertEqual(json.loads((self.root/'preview/review.json').read_text())['candidates'],[])
        self.assertEqual(self.rows('published_orphan_reviews'),[])

    def test_adoption_records_honest_provenance_state_and_is_idempotent(self):
        write_projection(self.root,self.registry,[self.first,self.second],
                         [dict(url='https://town.example.cz/events/held',title='Held',reason='Ověřit')])
        result = sync.adopt_published(self.root,git(self.root,'rev-parse','HEAD'),baseline=self.docs)
        self.assertEqual(result['inserted'],1)
        self.assertEqual(self.rows('observations'),[])
        self.assertEqual(self.rows('provenance'),[])
        self.assertEqual(len(self.rows('published_adoptions')),1)
        self.assertEqual(json.loads(self.rows('source_state')[0][1]),sync.documents(self.root)['coverage']['sources'][0])
        self.assertEqual(self.rows('reviews')[0][:4],('town-a','https://town.example.cz/events/held','Held','Ověřit'))
        self.assertEqual(json.loads(next(r[4] for r in self.rows() if r[0]=='e-second'))['verifiedAt'],STAMP)
        before = {t:self.rows(t) for t in ('events','source_state','reviews','published_adoptions','published_sync')}
        self.assertEqual(sync.adopt_published(self.root,git(self.root,'rev-parse','HEAD'))['inserted'],0)
        self.assertEqual({t:self.rows(t) for t in before},before)

    def test_known_published_revision_uses_checkpoint_after_restart(self):
        sync.adopt_published(self.root,git(self.root,'rev-parse','HEAD'))
        changed = dict(self.first,title='Opravené trhy',verifiedAt='2026-11-13T10:00:00+01:00')
        write_projection(self.root,self.registry,[changed,self.second])
        result = sync.adopt_published(self.root,'a'*40)
        self.assertEqual(result['updated'],1)
        self.assertEqual(json.loads(next(r[4] for r in self.rows() if r[0]=='e-first')),changed)
        self.assertEqual(self.rows('observations'),[])

    def test_shared_url_review_uses_existing_ownership_and_event_town(self):
        other = dict(self.registry['sources'][0],id='town-b',town='Obec B')
        self.registry['sources'].append(other)
        (self.root/'data/sources.json').write_text(json.dumps(self.registry))
        candidate = dict(url='https://town.example.cz/events/held',title='Held',reason='Ověřit')
        with closing(sqlite3.connect(self.root/'private/events.sqlite')) as con, con:
            con.execute('INSERT INTO reviews VALUES (?,?,?,?,?)',('town-b',candidate['url'],candidate['title'],candidate['reason'],STAMP))
        second = dict(self.second,town='Obec B')
        write_projection(self.root,self.registry,[self.first,second],[candidate])
        sync.adopt_published(self.root,'a'*40,baseline=self.docs)
        self.assertEqual(next(r[1] for r in self.rows() if r[0]=='e-second'),'town-b')
        self.assertEqual(self.rows('reviews')[0][0],'town-b')
        unknown = dict(candidate,url='https://town.example.cz/events/unknown')
        write_projection(self.root,self.registry,[self.first,second],[candidate,unknown])
        before = self.rows()
        self.assertEqual(sync.adopt_published(self.root,'b'*40)['inserted'],0)
        self.assertEqual(self.rows(),before)
        self.assertEqual(self.rows('published_orphan_reviews')[0][:3],
                         (unknown['url'],unknown['title'],unknown['reason']))
        self.assertEqual(self.rows('reviews')[0][0],'town-b')

    def test_unpublished_private_state_conflict_rolls_back_whole_adoption(self):
        private = dict(self.docs['coverage']['sources'][0],lastChecked='2026-11-18T10:00:00+01:00')
        with closing(sqlite3.connect(self.root/'private/events.sqlite')) as con, con:
            con.execute('INSERT OR REPLACE INTO source_state VALUES (?,?)',('town-a',json.dumps(private)))
        write_projection(self.root,self.registry,[self.first,self.second])
        before = self.rows()
        with self.assertRaisesRegex(sync.SyncError,'sync-state-conflict'):
            sync.adopt_published(self.root,'a'*40,baseline=self.docs)
        self.assertEqual(self.rows(),before)
        self.assertEqual(json.loads(self.rows('source_state')[0][1]),private)
        with closing(sqlite3.connect(self.root/'private/events.sqlite')) as con:
            self.assertIsNone(con.execute("SELECT name FROM sqlite_master WHERE name='published_sync'").fetchone())

    def test_approved_reviewed_snapshot_has_explicit_checkpoint_without_primary_claims(self):
        source = dict(self.registry['sources'][0],id='editorial',adapter='reviewed-public',
                      index_urls=['https://reviewed.example.cz/'],url_regex=r'https://reviewed\.example\.cz/.*',
                      primary_host='reviewed.example.cz',allowed_towns={'Obec A':'Středočeský kraj'},
                      allowed_locations={},coverage_note='Redakční výběr')
        self.registry['sources'].append(source)
        (self.root/'data/sources.json').write_text(json.dumps(self.registry))
        reviewed = dict(self.second,sourceUrl='https://reviewed.example.cz/second')
        snapshot = dict(self.docs['events'],events=[reviewed])
        (self.root/'data/reviewed-events.json').write_text(json.dumps(snapshot))
        prior = dict(initialized=True,origin='feed',acceptedAt=STAMP,acceptedHash='old',bodyHash='old')
        with closing(sqlite3.connect(self.root/'private/events.sqlite')) as con, con:
            con.execute('CREATE TABLE reviewed_state (source_id TEXT PRIMARY KEY,payload TEXT)')
            con.execute('INSERT INTO reviewed_state VALUES (?,?)',('editorial',json.dumps(prior)))
        write_projection(self.root,self.registry,[self.first,reviewed])
        sync.adopt_published(self.root,'a'*40,baseline=self.docs)
        state = json.loads(self.rows('reviewed_state')[0][1])
        import reviewed_public
        self.assertEqual(state['acceptedAt'],STAMP)
        self.assertEqual(state['acceptedHash'],reviewed_public.fingerprint(snapshot))
        self.assertEqual(state['publishedCommit'],'a'*40)
        self.assertEqual(self.rows('observations'),[])
        self.assertEqual(self.rows('provenance'),[])
        # The normal collector still refuses changed same-stamp feeds.
        class ChangedFeed:
            def get(self,url):
                return json.dumps(dict(snapshot,events=[dict(reviewed,title='Unapproved')])).encode()
        with closing(sqlite3.connect(self.root/'private/events.sqlite')) as con:
            metrics = dict(eventsNew=0,eventsChanged=0,eventsUnchanged=0)
            reviewed_public.refresh(con,self.registry,ChangedFeed(),STAMP,metrics,
                                    snapshot=self.root/'data/reviewed-events.json',feed={'url':'https://owned.example.cz/feed'})
            self.assertIsNone(con.execute('SELECT id FROM events WHERE id=?',(reviewed['id'],)).fetchone())
            self.assertEqual(json.loads(con.execute('SELECT payload FROM reviewed_state').fetchone()[0])['acceptedHash'],state['acceptedHash'])

    def editorial_fixture(self):
        source = dict(self.registry['sources'][0],id='editorial',adapter='reviewed-public',
                      index_urls=['https://reviewed.example.cz/'],url_regex=r'https://reviewed\.example\.cz/.*',
                      primary_host='reviewed.example.cz',allowed_towns={'Obec A':'Středočeský kraj'},
                      allowed_locations={},coverage_note='Redakční výběr')
        self.registry['sources'].append(source)
        (self.root/'data/sources.json').write_text(json.dumps(self.registry))
        reviewed = dict(self.second,sourceUrl='https://reviewed.example.cz/second')
        snapshot = dict(self.docs['events'],events=[reviewed])
        (self.root/'data/reviewed-events.json').write_text(json.dumps(snapshot))
        write_projection(self.root,self.registry,[self.first,reviewed])
        git(self.root,'add','.'); git(self.root,'commit','-m','Approved reviewed bootstrap')
        git(self.root,'push','origin','main')
        git(self.foreign,'pull','--ff-only','origin','main')
        return reviewed, snapshot

    def publish_reviewed_feed(self, feed):
        class Feed:
            stats = {}
            def get(self,url):
                return json.dumps(feed).encode()
        def collect(root):
            with patch.object(collector,'now',return_value=feed['generatedAt']):
                collector.collect(self.registry,root/'private/events.sqlite',root/'site',{},Feed(),
                                  reviewed_snapshot=root/'data/reviewed-events.json',
                                  reviewed_feed={'url':'https://owned.example.cz/feed'},reviewed_only=True)
        self.assertEqual(pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                                    collect=collect,verify=lambda *a:None),'published')
        return json.loads(self.rows('reviewed_state')[0][1])

    def test_legacy_87_row_checkpoint_bootstraps_172_public_rows_and_55_reviewed_states(self):
        import reviewed_public
        sources = []
        for i in range(55):
            host = f'editorial-{i}.example.cz'
            sources.append(dict(self.registry['sources'][0],id=f'editorial-{i}',adapter='reviewed-public',
                                index_urls=[f'https://{host}/'],url_regex=rf'https://editorial-{i}\.example\.cz/.*',
                                primary_host=host,allowed_towns={'Obec A':'Středočeský kraj'},
                                allowed_locations={},coverage_note='Redakční výběr'))
        self.registry['sources'].extend(sources)
        (self.root/'data/sources.json').write_text(json.dumps(self.registry))
        records = [dict(self.second,id=f'e-reviewed-{i}',title=f'Redakční akce {i}',
                        sourceUrl=f'https://editorial-{i % 55}.example.cz/event-{i}') for i in range(171)]
        snapshot = dict(self.docs['events'],events=records)
        (self.root/'data/reviewed-events.json').write_text(json.dumps(snapshot))
        for i,event in enumerate(records[:86]):
            store(self.root,event,sid=f'editorial-{i % 55}')
        legacy = write_projection(self.root,self.registry,[self.first,*records[:86]])
        with closing(sqlite3.connect(self.root/'private/events.sqlite')) as con, con:
            con.execute('CREATE TABLE published_sync (id INTEGER PRIMARY KEY,payload TEXT)')
            con.execute('INSERT INTO published_sync VALUES (1,?)',(json.dumps(legacy),))
        self.assertEqual(len(self.rows()),87)
        write_projection(self.root,self.registry,[self.first,*records])
        result = sync.adopt_published(self.root,'a'*40,baseline=self.docs)
        self.assertEqual(result['inserted'],85)
        self.assertEqual(len(self.rows()),172)
        states = {sid:json.loads(payload) for sid,payload in self.rows('reviewed_state')}
        self.assertEqual(set(states),{s['id'] for s in sources})
        self.assertEqual(len(states),55)
        self.assertTrue(all(s['initialized'] and s['acceptedHash']==reviewed_public.fingerprint(snapshot)
                            for s in states.values()))
        self.assertEqual(self.rows('provenance'),[])
        self.assertEqual(sync.adopt_published(self.root,'a'*40)['inserted'],0)

    def test_published_live_reviewed_revision_survives_next_preflight(self):
        reviewed, snapshot = self.editorial_fixture()
        fresh = dict(snapshot,generatedAt='2026-11-13T10:00:00+01:00',
                     events=[dict(reviewed,title='Živě opravený výběr')])
        accepted = self.publish_reviewed_feed(fresh)
        self.assertEqual(accepted['origin'],'feed')
        self.assertEqual(pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                                    collect=lambda root:None,verify=lambda *a:None),'unchanged')
        state = json.loads(self.rows('reviewed_state')[0][1])
        for field in ('acceptedAt','acceptedHash','bodyHash','origin'):
            self.assertEqual(state[field],accepted[field])
        self.assertEqual(json.loads(next(r[4] for r in self.rows() if r[0]==reviewed['id'])),fresh['events'][0])

    def test_time_only_reviewed_feed_keeps_newer_revision_across_preflight(self):
        _, snapshot = self.editorial_fixture()
        fresh = dict(snapshot,generatedAt='2026-11-13T10:00:00+01:00')
        accepted = self.publish_reviewed_feed(fresh)
        self.assertEqual(pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                                    collect=lambda root:None,verify=lambda *a:None),'unchanged')
        state = json.loads(self.rows('reviewed_state')[0][1])
        for field in ('acceptedAt','acceptedHash','bodyHash'):
            self.assertEqual(state[field],accepted[field])
        import reviewed_public
        saved = json.loads(self.rows('published_sync')[0][1])
        self.assertEqual(saved['_reviewedSnapshotHash'],reviewed_public.fingerprint(snapshot))
        self.assertNotEqual(saved['_reviewedSnapshotHash'],accepted['acceptedHash'])

    def test_external_code_only_commit_keeps_published_live_reviewed_revision(self):
        reviewed, snapshot = self.editorial_fixture()
        fresh = dict(snapshot,generatedAt='2026-11-13T10:00:00+01:00',
                     events=[dict(reviewed,title='Živě opravený výběr')])
        accepted = self.publish_reviewed_feed(fresh)
        pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                    collect=lambda root:None,verify=lambda *a:None)
        git(self.foreign,'pull','--ff-only','origin','main')
        (self.foreign/'scripts').mkdir()
        (self.foreign/'scripts/editorial_note.py').write_text('# code-only update\n')
        git(self.foreign,'add','.'); git(self.foreign,'commit','-m','Code only')
        git(self.foreign,'push','origin','main')
        with self.assertRaisesRegex(pub.PublicationError,'reload-required'):
            pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                        collect=lambda root:self.fail('stale code collected'),verify=lambda *a:None)
        head = git(self.root,'rev-parse','HEAD')
        self.assertNotEqual(json.loads((self.root/'private/published-owned.json').read_text())['head'],head)
        self.assertEqual(pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                                    collect=lambda root:None,verify=lambda *a:None),'unchanged')
        state = json.loads(self.rows('reviewed_state')[0][1])
        self.assertEqual(state['publishedCommit'],head)
        for field in ('acceptedAt','acceptedHash','bodyHash'):
            self.assertEqual(state[field],accepted[field])

    def test_code_only_update_immediately_after_native_delivery_uses_owned_baseline(self):
        reviewed, snapshot = self.editorial_fixture()
        fresh = dict(snapshot,generatedAt='2026-11-13T10:00:00+01:00',
                     events=[dict(reviewed,title='Živě opravený výběr')])
        accepted = self.publish_reviewed_feed(fresh)
        # No intervening adoption has checkpointed this live catalogue yet.
        git(self.foreign,'pull','--ff-only','origin','main')
        (self.foreign/'scripts').mkdir()
        (self.foreign/'scripts/editorial_note.py').write_text('# code-only update\n')
        git(self.foreign,'add','.'); git(self.foreign,'commit','-m','Code only after native delivery')
        git(self.foreign,'push','origin','main')
        with self.assertRaisesRegex(pub.PublicationError,'reload-required'):
            pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                        collect=lambda root:self.fail('stale code collected'),verify=lambda *a:None)
        self.assertEqual(pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                                    collect=lambda root:None,verify=lambda *a:None),'unchanged')
        state = json.loads(self.rows('reviewed_state')[0][1])
        for field in ('acceptedAt','acceptedHash','bodyHash'):
            self.assertEqual(state[field],accepted[field])

    def test_changed_editorial_snapshot_still_requires_exact_public_match(self):
        reviewed, snapshot = self.editorial_fixture()
        fresh = dict(snapshot,generatedAt='2026-11-13T10:00:00+01:00',
                     events=[dict(reviewed,title='Živě opravený výběr')])
        self.publish_reviewed_feed(fresh)
        pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                    collect=lambda root:None,verify=lambda *a:None)
        git(self.foreign,'pull','--ff-only','origin','main')
        changed = dict(fresh,generatedAt='2026-11-14T10:00:00+01:00',
                       events=[dict(reviewed,title='Nový neschválený obsah')])
        (self.foreign/'data/reviewed-events.json').write_text(json.dumps(changed))
        git(self.foreign,'add','.'); git(self.foreign,'commit','-m','Changed editorial snapshot')
        git(self.foreign,'push','origin','main')
        before = {t:self.rows(t) for t in ('events','reviewed_state','published_sync')}
        with self.assertRaisesRegex(pub.PublicationError,'sync-reviewed-snapshot'):
            pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                        collect=lambda root:self.fail('mismatched snapshot collected'),verify=lambda *a:None)
        self.assertEqual({t:self.rows(t) for t in before},before)
        # Publishing the matching catalogue allows strict new-snapshot adoption.
        write_projection(self.foreign,self.registry,[self.first,*changed['events']])
        git(self.foreign,'add','.'); git(self.foreign,'commit','-m','Matching editorial publication')
        git(self.foreign,'push','origin','main')
        self.assertEqual(pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                                    collect=lambda root:None,verify=lambda *a:None),'unchanged')
        import reviewed_public
        state = json.loads(self.rows('reviewed_state')[0][1])
        self.assertEqual(state['acceptedAt'],changed['generatedAt'])
        self.assertEqual(state['acceptedHash'],reviewed_public.fingerprint(changed))
        self.assertEqual(json.loads(self.rows('published_sync')[0][1])['_reviewedSnapshotHash'],
                         reviewed_public.fingerprint(changed))
        self.assertEqual(pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                                    collect=lambda root:None,verify=lambda *a:None),'unchanged')

    def test_unproven_private_feed_state_does_not_override_bootstrap_stale_guard(self):
        _, snapshot = self.editorial_fixture()
        import reviewed_public
        newer = dict(snapshot,generatedAt='2026-11-13T10:00:00+01:00')
        prior = dict(initialized=True,origin='feed',acceptedAt=newer['generatedAt'],
                     acceptedHash=reviewed_public.fingerprint(newer),bodyHash='a'*64)
        with closing(sqlite3.connect(self.root/'private/events.sqlite')) as con, con:
            con.execute('CREATE TABLE reviewed_state (source_id TEXT PRIMARY KEY,payload TEXT)')
            con.execute('INSERT INTO reviewed_state VALUES (?,?)',('editorial',json.dumps(prior)))
        before = self.rows()
        with self.assertRaisesRegex(pub.PublicationError,'sync-reviewed-stale'):
            pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                        collect=lambda root:self.fail('unproven state collected'),verify=lambda *a:None)
        self.assertEqual(self.rows(),before)
        self.assertEqual(json.loads(self.rows('reviewed_state')[0][1]),prior)

    def test_unchanged_bootstrap_does_not_trust_unpublished_feed_catalogue(self):
        reviewed, snapshot = self.editorial_fixture()
        sync.adopt_published(self.root,git(self.root,'rev-parse','HEAD'),baseline=self.docs)
        changed = dict(reviewed,title='Soukromá změna')
        fresh = dict(snapshot,generatedAt='2026-11-13T10:00:00+01:00',events=[changed])
        class Feed:
            stats = {}
            def get(self,url): return json.dumps(fresh).encode()
        collector.collect(self.registry,self.root/'private/events.sqlite',self.root/'site',{},Feed(),
                          reviewed_snapshot=self.root/'data/reviewed-events.json',
                          reviewed_feed={'url':'https://owned.example.cz/feed'},reviewed_only=True)
        # There is accepted feed state, but neither an owned delivery nor a
        # saved public catalogue proves this changed projection was published.
        before = {t:self.rows(t) for t in ('events','reviewed_state','published_sync')}
        with self.assertRaisesRegex(sync.SyncError,'sync-reviewed-snapshot'):
            sync.adopt_published(self.root,'b'*40,baseline=sync.documents(self.root))
        self.assertEqual({t:self.rows(t) for t in before},before)

    def test_old_private_feed_state_cannot_claim_newer_owned_publication(self):
        reviewed, snapshot = self.editorial_fixture()
        older = dict(snapshot,generatedAt='2026-11-13T10:00:00+01:00',
                     events=[dict(reviewed,title='První živá oprava')])
        prior = self.publish_reviewed_feed(older)
        fresh = dict(older,generatedAt='2026-11-14T10:00:00+01:00',
                     events=[dict(reviewed,title='Druhá živá oprava')])
        self.publish_reviewed_feed(fresh)
        with closing(sqlite3.connect(self.root/'private/events.sqlite')) as con, con:
            con.execute('UPDATE reviewed_state SET payload=? WHERE source_id=?',(json.dumps(prior),'editorial'))
        before = {t:self.rows(t) for t in ('events','reviewed_state','published_sync')}
        with self.assertRaisesRegex(pub.PublicationError,'sync-reviewed-snapshot'):
            pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                        collect=lambda root:self.fail('conflicting state collected'),verify=lambda *a:None)
        self.assertEqual({t:self.rows(t) for t in before},before)

    def test_removed_published_source_fails_even_if_old_rows_would_be_filtered(self):
        replacement = dict(self.registry['sources'][0],id='town-b',town='Obec B',
                           index_urls=['https://other.example.cz/events/'],url_regex=r'https://other\.example\.cz/events/.*')
        narrowed = dict(self.registry,sources=[replacement])
        (self.root/'data/sources.json').write_text(json.dumps(narrowed))
        second = dict(self.second,town='Obec B',sourceUrl='https://other.example.cz/events/second')
        write_projection(self.root,narrowed,[second])
        before = self.rows()
        with self.assertRaisesRegex(sync.SyncError,'sync-removal'):
            sync.adopt_published(self.root,'a'*40,baseline=self.docs)
        self.assertEqual(self.rows(),before)

    def test_unpublished_review_conflict_is_not_silently_ignored(self):
        candidate = dict(url='https://town.example.cz/events/held',title='Held',reason='Ověřit')
        with closing(sqlite3.connect(self.root/'private/events.sqlite')) as con, con:
            con.execute('INSERT INTO reviews VALUES (?,?,?,?,?)',('town-a',candidate['url'],'Private','Private',STAMP))
        write_projection(self.root,self.registry,[self.first,self.second],[candidate])
        before = self.rows()
        with self.assertRaisesRegex(sync.SyncError,'sync-review-conflict'):
            sync.adopt_published(self.root,'a'*40,baseline=self.docs)
        self.assertEqual(self.rows(),before)
        self.assertEqual(self.rows('reviews')[0][2],'Private')

    def test_pulled_code_requires_reload_before_db_write_or_collection(self):
        (self.foreign/'scripts').mkdir()
        (self.foreign/'scripts/parser.py').write_text('# changed runtime code\n')
        head = self.advance()
        before = self.rows()
        with self.assertRaisesRegex(pub.PublicationError,'reload-required'):
            pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                        collect=lambda root:self.fail('stale-code collection'),verify=lambda *a:None)
        self.assertEqual(git(self.root,'rev-parse','HEAD'),head)
        self.assertEqual(self.rows(),before)

    def test_remote_advancing_during_verification_blocks_all_db_writes(self):
        self.advance()
        before = self.rows()
        def verify(*args):
            self.advance([self.first,self.second,dict(self.second,id='e-third',title='Třetí')])
        with self.assertRaisesRegex(pub.PublicationError,'remote-head'):
            pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                        collect=lambda root:self.fail('raced collection'),verify=verify)
        self.assertEqual(self.rows(),before)

    def test_failed_readback_then_restart_retains_pre_pull_revision_baseline(self):
        changed = dict(self.first,title='Schválená oprava')
        self.advance([changed,self.second])
        with self.assertRaisesRegex(RuntimeError,'readback'):
            pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                        collect=lambda root:self.fail('unverified collection'),
                        verify=lambda *a:(_ for _ in ()).throw(RuntimeError('readback')))
        self.assertEqual(len(self.rows()),1)
        self.assertEqual(pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                                    collect=lambda root:None,verify=lambda *a:None),'unchanged')
        self.assertEqual(json.loads(next(r[4] for r in self.rows() if r[0]=='e-first')),changed)
        self.assertFalse((self.root/'private/published-base.json').exists())

    def test_incompatible_sqlite_schema_blocks_before_backup_or_writes(self):
        with closing(sqlite3.connect(self.root/'private/events.sqlite')) as con, con:
            con.execute('ALTER TABLE events ADD COLUMN unexpected TEXT')
        before = self.rows()
        with self.assertRaisesRegex(sync.SyncError,'sync-schema'):
            sync.adopt_published(self.root,'a'*40)
        self.assertEqual(self.rows(),before)
        self.assertFalse((self.root/'private/runtime-sync').exists())

    def test_owner_conflict_and_unpublished_event_revision_preserve_existing_facts(self):
        for sid,payload,stage in [('wrong',self.first,'sync-owner'),
                                  ('town-a',dict(self.first,title='Private change'),'sync-conflict')]:
            with self.subTest(stage=stage):
                with closing(sqlite3.connect(self.root/'private/events.sqlite')) as con, con:
                    con.execute('UPDATE events SET source_id=?,payload=? WHERE id=?',(sid,json.dumps(payload),self.first['id']))
                before = self.rows()
                with self.assertRaisesRegex(sync.SyncError,stage):
                    sync.adopt_published(self.root,'a'*40,baseline=self.docs)
                self.assertEqual(self.rows(),before)

    def test_duplicate_extra_is_preserved_but_unsuppressed_extra_blocks(self):
        duplicate = dict(self.first,id='e-zzz-duplicate')
        store(self.root,duplicate)
        sync.adopt_published(self.root,'a'*40)
        self.assertEqual(len(self.rows()),2)
        extra = dict(self.second,id='e-zzz-extra')
        store(self.root,extra)
        before = self.rows()
        with self.assertRaisesRegex(sync.SyncError,'sync-projection'):
            sync.adopt_published(self.root,'b'*40)
        self.assertEqual(self.rows(),before)

    def test_pending_delivery_never_enters_sync_preflight(self):
        changed = dict(self.first,title='Owned change')
        def collect(root):
            write_projection(root,self.registry,[changed])
        def verify(root,head):
            if head!=git(self.foreign,'rev-parse','HEAD'):
                raise RuntimeError('delivery retry')
        with self.assertRaisesRegex(RuntimeError,'delivery retry'):
            pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),collect=collect,verify=verify)
        with patch.object(pub,'sync_preflight',side_effect=AssertionError('retry must not sync')), \
                patch.object(pub,'collect_projection',side_effect=AssertionError('retry must not collect')):
            self.assertEqual(pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),verify=lambda *a:None),'published')

    def test_dirty_checkout_never_fetches_verifies_or_adopts(self):
        self.advance()
        (self.root/'site/events.json').write_text('private edit')
        before = self.rows()
        with patch.object(pub,'sync_preflight',side_effect=AssertionError('dirty sync')):
            with self.assertRaisesRegex(pub.PublicationError,'dirty-checkout'):
                pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote))
        self.assertEqual(self.rows(),before)
        self.assertEqual((self.root/'site/events.json').read_text(),'private edit')

    def test_invalid_published_projection_blocks_before_backup(self):
        document = sync.documents(self.root)['events']
        document['events'][0]['town'] = 'Unknown'
        (self.root/'site/events.json').write_text(json.dumps(document))
        before = self.rows()
        with self.assertRaisesRegex(sync.SyncError,'sync-validation'):
            sync.adopt_published(self.root,'a'*40)
        self.assertEqual(self.rows(),before)
        self.assertFalse((self.root/'private/runtime-sync').exists())

    def test_current_process_with_changed_loaded_code_requires_reload(self):
        with patch.object(pub,'runtime_code',return_value='changed-after-import',create=True):
            with self.assertRaisesRegex(pub.PublicationError,'reload-required'):
                pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                            collect=lambda root:self.fail('stale code'),verify=lambda *a:None)
        self.assertEqual(len(self.rows()),1)

    def test_cli_reports_controlled_sync_stage_without_private_details(self):
        from contextlib import redirect_stdout
        with patch.object(pub,'__file__',str(self.root/'scripts/publish_daily.py')), \
                patch.object(pub,'publish',side_effect=pub.PublicationError('reload-required')), \
                patch.dict(os.environ,{'_ADVENT_PUBLISHER_RELOADED':'1'}), \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(pub.main([]),1)
        self.assertIn('(reload-required)',output.getvalue())
        self.assertEqual(json.loads((self.root/'private/publish-error.json').read_text())['stage'],'reload-required')

    def test_verified_owned_removal_does_not_poison_next_preflight(self):
        def collect(root):
            with closing(sqlite3.connect(root/'private/events.sqlite')) as con, con:
                con.execute('DELETE FROM events WHERE id=?',(self.first['id'],))
            write_projection(root,self.registry,[])
        self.assertEqual(pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                                    collect=collect,verify=lambda *a:None),'published')
        # A foreign addition may arrive before another local preflight.
        git(self.foreign,'pull','--ff-only','origin','main')
        self.advance([self.second])
        self.assertEqual(pub.publish(self.root,today=date(2026,11,12),remote=str(self.remote),
                                    collect=lambda root:None,verify=lambda *a:None),'unchanged')

    def test_remote_approved_addition_is_adopted_before_collection(self):
        head = self.advance()
        before = self.rows()
        verified = []
        def verify(root, commit):
            self.assertEqual(commit, head); verified.append(commit)
            self.assertEqual(len(self.rows()),1, 'verification must precede DB writes')
        def collect(root):
            self.assertEqual({r[0] for r in self.rows()}, {'e-first','e-second'})
        result = pub.publish(self.root, today=date(2026,11,12), remote=str(self.remote),
                             collect=collect, verify=verify)
        self.assertEqual(result,'unchanged')
        self.assertEqual(verified,[head])
        self.assertIn(before[0],self.rows(), 'existing facts and timestamps must be unchanged')
        self.assertEqual(git(self.root,'rev-parse','HEAD'),head)
        self.assertEqual(git(self.root,'status','--porcelain'),'')
        self.assertEqual((self.root/'site/events.json').read_bytes(),(self.foreign/'site/events.json').read_bytes())
        self.assertEqual(len(list((self.root/'private/runtime-sync').glob('*.sqlite'))),1)
