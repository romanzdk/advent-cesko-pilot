"""Adopt verified published facts, never pretend a primary page was fetched.

Caller must hold publish.lock and verify the commit's deployed JSON before calling.
No collection, network, public-file writes or destructive reconciliation occurs here.
"""
from datetime import datetime, timezone
from contextlib import closing
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import uuid

SCRIPT_DIR = str(Path(__file__).resolve().parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import collector
import validate_public


class SyncError(RuntimeError):
    pass


def require(ok, stage):
    if not ok:
        raise SyncError(stage)


def documents(root):
    return {name: json.loads((root/f'site/{name}.json').read_text())
            for name in ('events', 'coverage', 'review')}


def projected_events(con, registry):
    """Exact collector.collect stored-row filtering/de-duplication contract."""
    allowed = {s['id'] for s in registry['sources']}
    events, dedupe = [], set()
    for sid, payload in con.execute('SELECT source_id,payload FROM events ORDER BY id'):
        if sid not in allowed:
            continue
        event = json.loads(payload)
        if not registry['window']['from'] <= event['date'] <= registry['window']['through']:
            continue
        key = tuple(collector.fold(event.get(k) or '') for k in ('town','venue','date','title','startTime'))
        if event['venue'] and key in dedupe:
            continue
        dedupe.add(key)
        events.append(event)
    events.sort(key=lambda e: (e['date'],e['startTime'] or '99:99',e['town'],e['title']))
    return events


def checkpoint_reviewed(con, root, registry, docs, commit, projection_sha, *, checkpoint=None, owned=False):
    sources = [s for s in registry['sources'] if s.get('adapter')=='reviewed-public']
    if not sources:
        return
    import reviewed_public
    raw = (root/'data/reviewed-events.json').read_bytes()
    known = {eid:(sid,url) for eid,sid,url in con.execute('SELECT id,source_id,url FROM events')}
    snapshot, records, bad = reviewed_public.decode(raw,sources,registry,known)
    snapshot_hash = reviewed_public.fingerprint(snapshot)
    reviewed_ids = {s['id'] for s in sources}
    expected = {e['id']:e for e in docs['events']['events'] if known[e['id']][0] in reviewed_ids}
    saved = checkpoint or {}
    unchanged = saved.get('_reviewedSnapshotHash') == snapshot_hash
    published = {e['id']:e for e in saved.get('events',{}).get('events',[])
                 if known.get(e['id'],(None,))[0] in reviewed_ids}
    saved_sha = reviewed_public.fingerprint({k:saved[k] for k in ('events','coverage','review')}) if saved else None
    # Only a verified owned delivery or the exact saved public catalogue can
    # outrank an unchanged bootstrap. A new editorial snapshot stays strict.
    require(not bad and (unchanged or {e['id']:e for _,e in records}==expected), 'sync-reviewed-snapshot')
    con.execute('CREATE TABLE IF NOT EXISTS reviewed_state (source_id TEXT PRIMARY KEY,payload TEXT)')
    latest = None
    for source in sources:
        row = con.execute('SELECT payload FROM reviewed_state WHERE source_id=?',(source['id'],)).fetchone()
        prior = json.loads(row[0]) if row else {}
        stamp = datetime.fromisoformat(snapshot['generatedAt'])
        require(stamp.tzinfo is not None, 'sync-reviewed-stale')
        proven = owned or (published==expected and prior.get('publishedProjectionSHA')==saved_sha
                           and prior.get('publishedCommit')==saved.get('_commit'))
        preserve = (unchanged and proven and prior.get('initialized') and prior.get('origin')=='feed'
                    and prior.get('acceptedHash')!=snapshot_hash
                    and prior.get('acceptedAt') and datetime.fromisoformat(prior['acceptedAt'])>=stamp
                    and all(re.fullmatch(r'[0-9a-f]{64}',prior.get(k,'')) for k in ('acceptedHash','bodyHash')))
        if preserve:
            # An owned HEAD proves publication, not that an arbitrary older
            # private feed checkpoint describes it. Bind nonempty sources to
            # the latest native feed receipts before retaining their revision.
            own_ids = [eid for eid in expected if known[eid][0]==source['id']]
            if latest is None:
                has_receipts = con.execute("SELECT name FROM sqlite_master WHERE name='reviewed_provenance'").fetchone()
                latest = dict((eid,(body_hash,origin)) for eid,body_hash,origin in con.execute(
                    'SELECT event_id,body_hash,origin FROM reviewed_provenance WHERE rowid IN '
                    '(SELECT MAX(rowid) FROM reviewed_provenance GROUP BY event_id)')) if has_receipts else {}
            require(all(latest.get(eid)==(prior['bodyHash'],'feed') for eid in own_ids), 'sync-reviewed-snapshot')
            state = dict(prior,publishedCommit=commit,publishedProjectionSHA=projection_sha)
        else:
            own_snapshot = {e['id']:e for sid,e in records if sid==source['id']}
            own_public = {eid:e for eid,e in expected.items() if known[eid][0]==source['id']}
            require(own_snapshot==own_public, 'sync-reviewed-snapshot')
            require(not prior.get('acceptedAt') or stamp>=datetime.fromisoformat(prior['acceptedAt']), 'sync-reviewed-stale')
            state = dict(prior,initialized=True,origin=prior.get('origin','snapshot'),
                         bodyHash=hashlib.sha256(raw).hexdigest(),acceptedAt=snapshot['generatedAt'],
                         acceptedHash=snapshot_hash,publishedCommit=commit,
                         publishedProjectionSHA=projection_sha)
        if state!=prior:
            con.execute('INSERT INTO reviewed_state VALUES (?,?) ON CONFLICT(source_id) DO UPDATE SET payload=excluded.payload',(source['id'],json.dumps(state)))
    return snapshot_hash


def adopt_published(root, commit, *, baseline=None):
    """Under publisher lock, adopt an already deployment-verified commit into SQLite.

    baseline is the pre-fast-forward {events,coverage,review} document mapping;
    publisher supplies optional _commit to recognize its own verified deliveries.
    Returns counts/backup path only; errors are controlled stage identifiers.
    """
    root = Path(root)
    try:
        registry = json.loads((root/'data/sources.json').read_text())
        validate_public.validate_directory(root/'site', registry)
        docs = documents(root)
    except (ValueError,KeyError,TypeError,OSError):
        raise SyncError('sync-validation') from None
    sources = registry['sources']
    patterns = {s['id']: re.compile(s['url_regex']) for s in sources}
    db = root/'private/events.sqlite'
    require(db.is_file(), 'sync-schema')
    con = sqlite3.connect(db)
    try:
        schema = {'events':'id source_id url fingerprint payload observed_at',
                  'source_state':'id payload','reviews':'source_id url title reason observed_at'}
        for table, columns in schema.items():
            require([r[1] for r in con.execute('PRAGMA table_info('+table+')')]==columns.split(), 'sync-schema')
        backup_dir = root/'private/runtime-sync'
        backup_dir.mkdir(mode=0o700, exist_ok=True)
        backup_dir.chmod(0o700)
        backup = backup_dir/(uuid.uuid4().hex+'.sqlite')
        backup.touch(mode=0o600, exist_ok=False)
        with closing(sqlite3.connect(backup)) as saved:
            con.backup(saved)
        backup.chmod(0o600)
        con.execute('BEGIN IMMEDIATE')
        con.execute('CREATE TABLE IF NOT EXISTS published_adoptions (event_id TEXT, published_commit TEXT, projection_sha TEXT, adopted_at TEXT, PRIMARY KEY(event_id,published_commit,projection_sha))')
        con.execute('CREATE TABLE IF NOT EXISTS published_sync (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT)')
        con.execute('CREATE TABLE IF NOT EXISTS published_orphan_reviews (url TEXT, title TEXT, reason TEXT, published_commit TEXT, PRIMARY KEY(url,title,reason))')
        projection_sha = hashlib.sha256(json.dumps(docs,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        adopted_at = datetime.now(timezone.utc).isoformat()
        checkpoint = con.execute('SELECT payload FROM published_sync WHERE id=1').fetchone()
        saved = json.loads(checkpoint[0]) if checkpoint else None
        previous = [p for p in (baseline,saved) if p]
        known_events = [{e['id']:e for e in p['events']['events']} for p in previous]
        published_ids = {e['id'] for e in docs['events']['events']}
        owned = root/'private/published-owned.json'
        owned_head = json.loads(owned.read_text()).get('head') if owned.exists() else None
        removal_baselines = known_events
        if baseline and owned_head and owned_head==baseline.get('_commit'):
            # A verified owned delivery supersedes an older sync checkpoint.
            removal_baselines = [{e['id']:e for e in baseline['events']['events']}]
        require(owned_head==commit or all(set(known)<=published_ids for known in removal_baselines), 'sync-removal')
        inserted = updated = 0
        for event in docs['events']['events']:
            matches = [s for s in sources if patterns[s['id']].fullmatch(event['sourceUrl'])]
            if len(matches)>1:
                matches = [s for s in matches if s['town']==event['town']]
            require(len(matches)==1, 'sync-owner')
            sid = matches[0]['id']
            row = con.execute('SELECT source_id,payload FROM events WHERE id=?',(event['id'],)).fetchone()
            if row:
                require(row[0]==sid, 'sync-owner')
                old = json.loads(row[1])
                if old==event:
                    continue
                require(any(known.get(event['id'])==old for known in known_events), 'sync-conflict')
            semantic = {k:v for k,v in event.items() if k!='verifiedAt'}
            sha = collector.digest(json.dumps(semantic, sort_keys=True, ensure_ascii=False))
            con.execute('INSERT INTO events VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET source_id=excluded.source_id,url=excluded.url,fingerprint=excluded.fingerprint,payload=excluded.payload,observed_at=excluded.observed_at',
                        (event['id'],sid,event['sourceUrl'],sha,json.dumps(event,ensure_ascii=False),event['verifiedAt']))
            con.execute('INSERT INTO published_adoptions VALUES (?,?,?,?)',
                        (event['id'],commit,projection_sha,adopted_at))
            inserted += not bool(row)
            updated += bool(row)
        require({e['id']:e for e in projected_events(con,registry)} ==
                {e['id']:e for e in docs['events']['events']}, 'sync-projection')
        for state in docs['coverage']['sources']:
            row = con.execute('SELECT payload FROM source_state WHERE id=?',(state['id'],)).fetchone()
            if row:
                old = json.loads(row[0])
                require(old==state or any(old==s for p in previous for s in p['coverage']['sources']
                                         if s['id']==state['id']), 'sync-state-conflict')
                if old==state:
                    continue
            con.execute('INSERT INTO source_state VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                        (state['id'],json.dumps(state,ensure_ascii=False)))
        for candidate in docs['review']['candidates']:
            owners = [s['id'] for s in sources if patterns[s['id']].fullmatch(candidate['url'])]
            if len(owners)>1:
                owners = [sid for (sid,) in con.execute(
                    'SELECT source_id FROM reviews WHERE url=? AND title=? AND reason=?',
                    (candidate['url'],candidate['title'],candidate['reason'])) if sid in owners]
            if not owners:
                # A published hold is not an accepted event. Preserve it in an
                # explicitly unowned queue rather than guessing a source or
                # blocking adoption of independently validated public events.
                con.execute('INSERT OR IGNORE INTO published_orphan_reviews VALUES (?,?,?,?)',
                            (candidate['url'],candidate['title'],candidate['reason'],commit))
                continue
            for sid in owners:
                con.execute('DELETE FROM published_orphan_reviews WHERE url=? AND title=? AND reason=?',
                            (candidate['url'],candidate['title'],candidate['reason']))
                row = con.execute('SELECT title,reason FROM reviews WHERE source_id=? AND url=?',(sid,candidate['url'])).fetchone()
                if row:
                    old = dict(url=candidate['url'],title=row[0],reason=row[1])
                    require(old==candidate or any(old in p['review']['candidates'] for p in previous), 'sync-review-conflict')
                    if old==candidate:
                        continue
                con.execute('INSERT INTO reviews VALUES (?,?,?,?,?) ON CONFLICT(source_id,url) DO UPDATE SET title=excluded.title,reason=excluded.reason,observed_at=excluded.observed_at',
                            (sid,candidate['url'],candidate['title'],candidate['reason'],docs['review']['generatedAt']))
        actual_reviews = collector.projected_reviews(con, patterns)
        canonical = lambda items: Counter(json.dumps(item,sort_keys=True,ensure_ascii=False) for item in items)
        require(canonical(actual_reviews)==canonical(docs['review']['candidates']), 'sync-review-projection')
        owned_public = owned_head==commit or bool(owned_head and baseline and owned_head==baseline.get('_commit')
                                                 and all(docs[name]==baseline[name] for name in docs))
        snapshot_hash = checkpoint_reviewed(con,root,registry,docs,commit,projection_sha,
                                            checkpoint=saved,owned=owned_public)
        saved = dict(docs,_commit=commit,_reviewedSnapshotHash=snapshot_hash)
        con.execute('INSERT INTO published_sync VALUES (1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(json.dumps(saved,ensure_ascii=False),))
        con.commit()
        return dict(inserted=inserted, updated=updated, backup=str(backup))
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
