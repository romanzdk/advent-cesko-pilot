"""Strict durable ingestion of a public editorial selection (never a primary crawl)."""
from datetime import datetime
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from validate_public import FIELDS, validate, require, https

SNAPSHOT = Path(__file__).resolve().parents[1]/'data/reviewed-events.json'
ROOT_FIELDS = {'schemaVersion','generatedAt','season','region','events'}
REASON = 'Veřejný záznam neodpovídá schválenému schématu nebo rozsahu; vyžaduje kontrolu.'

def binding(event, sources):
    matches = [s for s in sources if re.fullmatch(s['url_regex'], event['sourceUrl'])]
    require(len(matches) == 1, 'Unregistered or ambiguous primary source')
    source = matches[0]
    require(source['adapter'] == 'reviewed-public', 'Not a reviewed source')
    require(urlsplit(event['sourceUrl']).hostname == source['primary_host'], 'Primary host mismatch')
    require(source['allowed_towns'].get(event['town']) == event['region'] == source['region'], 'Unregistered town/region')
    require(event['location'] is None or event['location'] in source['allowed_locations'].get(event['town'],[]), 'Unreviewed coordinates')
    require(not urlsplit(event['sourceUrl']).fragment or event['sourceUrl'] in source.get('allowed_fragment_urls',[]), 'Unreviewed fragment')
    return source

def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def store(con, event, sid, checked, metrics, feed_url, body_hash, origin):
    semantic = {k:v for k,v in event.items() if k != 'verifiedAt'}
    sha = fingerprint(semantic)
    old = con.execute('SELECT fingerprint FROM events WHERE id=?', (event['id'],)).fetchone()
    metrics['eventsNew' if not old else 'eventsUnchanged' if old[0] == sha else 'eventsChanged'] += 1
    con.execute('INSERT OR REPLACE INTO events VALUES (?,?,?,?,?,?)', (event['id'], sid, event['sourceUrl'], sha, json.dumps(event,ensure_ascii=False), checked))
    for field in FIELDS - {'id'}:
        # The primary page was not fetched: never attribute a feed hash/date to it.
        con.execute('INSERT INTO provenance(event_id,field,value,source_url,body_hash,observed_at) VALUES (?,?,?,?,?,?)',
                    (event['id'],field,json.dumps(event[field]),event['sourceUrl'],None,event['verifiedAt']))
    con.execute('INSERT INTO reviewed_provenance VALUES (?,?,?,?,?,?)',
                (event['id'],feed_url,body_hash,checked,event['verifiedAt'],origin))

def decode(raw, sources, registry, known):
    document = json.loads(raw)
    require(isinstance(document,dict) and set(document)==ROOT_FIELDS and document['schemaVersion']==1 and document['season']==registry['season'] and isinstance(document['events'],list), 'Invalid reviewed root')
    validate(dict(document,events=[]))
    ids = Counter(e['id'] for e in document['events'] if isinstance(e,dict) and isinstance(e.get('id'),str))
    records, bad = [], []
    for original in document['events']:
        try:
            require(isinstance(original,dict) and set(original) in (FIELDS,FIELDS-{'region'}), 'Invalid fields')
            event = dict(original)  # never mutate caller/feed objects
            if 'region' not in event:
                matches = [s for s in sources if re.fullmatch(s['url_regex'],event['sourceUrl'])]
                require(len(matches)==1, 'Unknown reviewed source')
                event['region'] = matches[0]['allowed_towns'].get(event['town'])
            owner = binding(event,sources)
            validate(dict(document,events=[event]), reviewed_ids={event['id']})
            require(ids[event['id']]==1, 'Duplicate reviewed ID')
            require(event['id'] not in known or known[event['id']][0]==owner['id'], 'ID changed source ownership')
            require(registry['window']['from'] <= event['date'] <= registry['window']['through'], 'Outside registry window')
            records.append((owner['id'],event))
        except (ValueError,TypeError,KeyError,OverflowError):
            # Never echo unvalidated titles, fields or URLs into public review.
            identity = known.get(original.get('id')) if isinstance(original,dict) and isinstance(original.get('id'),str) else None
            if identity and identity[0] in {s['id'] for s in sources}:
                bad.append(identity)
            else:
                owners = [s for s in sources if isinstance(original,dict) and isinstance(original.get('sourceUrl'),str) and re.fullmatch(s['url_regex'], original['sourceUrl'])]
                owner = owners[0] if len(owners)==1 else sources[0]
                bad.append((owner['id'],owner['index_urls'][0]))
    return document, records, bad

def refresh(con, registry, fetcher, checked, metrics, source_id=None, snapshot=None, feed=None):
    sources = [s for s in registry['sources'] if s['adapter'] == 'reviewed-public']
    selected = [s for s in sources if not source_id or s['id'] == source_id]
    if not selected:
        return
    con.executescript('''
        CREATE TABLE IF NOT EXISTS reviewed_state (source_id TEXT PRIMARY KEY, payload TEXT);
        CREATE TABLE IF NOT EXISTS reviewed_provenance (event_id TEXT, feed_url TEXT, body_hash TEXT, retrieved_at TEXT, evidence_at TEXT, origin TEXT);
    ''')
    if feed is not None:
        require(isinstance(feed,dict) and set(feed)=={'url'} and https(feed['url']) and not urlsplit(feed['url']).fragment, 'Invalid private feed configuration')
    url = feed['url'] if feed else None
    failed, body = False, None
    if url:
        try:
            body = fetcher.get(url)
        except OSError:
            failed = True
    known = {eid:(sid,u) for eid,sid,u in con.execute('SELECT id,source_id,url FROM events')}
    decoded = {}
    for source in selected:
        sid = source['id']
        row = con.execute('SELECT payload FROM reviewed_state WHERE source_id=?',(sid,)).fetchone()
        prior = json.loads(row[0]) if row else {}
        old = con.execute('SELECT payload FROM source_state WHERE id=?',(sid,)).fetchone()
        previous = json.loads(old[0]) if old else {}
        origin = 'feed' if body is not None else 'snapshot'
        active = body is not None or not prior
        raw = body if body is not None else Path(snapshot or SNAPSHOT).read_bytes() if active else None
        invalid_root = False
        if active:
            assert raw is not None
            sha = hashlib.sha256(raw).hexdigest()
            if sha not in decoded:
                try:
                    decoded[sha] = decode(raw,sources,registry,known)
                except (ValueError,TypeError,KeyError,UnicodeError,OverflowError):
                    decoded[sha] = None
            try:
                require(decoded[sha] is not None, 'Invalid reviewed root')
                document, records, bad = decoded[sha]
                if origin == 'feed':
                    stamp = datetime.fromisoformat(document['generatedAt'])
                    require(stamp.tzinfo is not None, 'Feed timestamp must include timezone')
                    if prior.get('acceptedAt'):
                        previous_stamp = datetime.fromisoformat(prior['acceptedAt'])
                        require(stamp >= previous_stamp, 'Stale feed replay')
                        require(stamp != previous_stamp or fingerprint(document) == prior.get('acceptedHash'), 'Changed feed reused timestamp')
            except (ValueError,TypeError,KeyError,UnicodeError,OverflowError):
                # Changed invalid content is not an outage: withdraw, do not restore fallback.
                document, records, bad = {}, [], [(s['id'],s['index_urls'][0]) for s in selected]
                invalid_root = True
            con.execute('DELETE FROM reviews WHERE source_id=?',(sid,))
            for owner,review_url in bad:
                if owner==sid:
                    con.execute('INSERT OR REPLACE INTO reviews VALUES (?,?,?,?,?)',(sid,review_url,'Veřejný záznam k ověření',REASON,checked))
            own_records = [e for owner,e in records if owner==sid]
            old_ids = {r[0] for r in con.execute('SELECT id FROM events WHERE source_id=?',(sid,))}
            new_ids = {e['id'] for e in own_records}
            for event_id in old_ids-new_ids:
                con.execute('DELETE FROM events WHERE source_id=? AND id=?',(sid,event_id))
            for event in own_records:
                store(con,event,sid,checked,metrics,url if origin=='feed' else None,sha,origin)
            prior = dict(prior,initialized=True,bodyHash=sha,origin=origin)
            if origin == 'feed' and not invalid_root:
                prior.update(acceptedAt=document['generatedAt'],acceptedHash=fingerprint(document))
            con.execute('INSERT OR REPLACE INTO reviewed_state VALUES (?,?)',(sid,json.dumps(prior)))
        else:
            metrics['eventsUnchanged'] += con.execute('SELECT count(*) FROM events WHERE source_id=?',(sid,)).fetchone()[0]
        count = con.execute('SELECT count(*) FROM events WHERE source_id=?',(sid,)).fetchone()[0]
        reviews = con.execute('SELECT count(*) FROM reviews WHERE source_id=?',(sid,)).fetchone()[0]
        state = dict(id=sid,town=source['town'],region=source['region'],url=source['index_urls'][0],adapter=source['adapter'],
                     coverageNote=source['coverage_note'],status='error' if failed or invalid_root else 'partial' if reviews or not url else 'ok',
                     lastChecked=checked if url else previous.get('lastChecked'),lastSuccess=checked if body is not None and not invalid_root else previous.get('lastSuccess'),
                     eventCount=count,reviewCount=reviews,excludedCount=0,
                     lastError='Přenos veřejného výběru se nepodařil; poslední dobrá data jsou zachována.' if failed else 'Změněný veřejný výběr není platný; dotčené záznamy byly staženy.' if invalid_root or reviews else None if url else 'Přenos veřejného výběru není nastaven; zachována schválená data.',
                     sourceNote='Časy kontroly zdroje označují kontrolu přenosu veřejného výběru, ne nové načtení pořadatelského webu; u akce zůstává původní datum ověření.')
        con.execute('INSERT OR REPLACE INTO source_state VALUES (?,?)',(sid,json.dumps(state,ensure_ascii=False)))
    con.commit()
