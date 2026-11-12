"""Fail-closed validation of the public seasonal event projection."""
from datetime import date, datetime, time
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

FIELDS=set('id title town region venue date endDate startTime endTime category price registration registrationUrl description notes audience status verifiedAt sourceUrl location'.split())
REGIONS={'Hlavní město Praha','Středočeský kraj','Jihočeský kraj','Plzeňský kraj',
         'Karlovarský kraj','Ústecký kraj','Liberecký kraj','Královéhradecký kraj',
         'Pardubický kraj','Kraj Vysočina','Jihomoravský kraj','Olomoucký kraj',
         'Zlínský kraj','Moravskoslezský kraj'}
PRIVATE=re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|/(?:home|private|tmp|workspace)/|calendar_id|event_id|responseStatus|sendUpdates|attendees|\.hermes/')

def require(ok,message):
    if not ok: raise ValueError(message)

def https(value):
    try:
        p=urlsplit(value)
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.hostname=='localhost':return False
        try:return ipaddress.ip_address(p.hostname).is_global
        except ValueError:return '.' in p.hostname and not p.hostname.endswith(('.local','.internal'))
    except (ValueError,TypeError):return False

def validate(data):
    require(isinstance(data,dict) and set(data)=={'schemaVersion','generatedAt','season','region','events'},'Unexpected public root fields')
    require(data['schemaVersion']==1 and data['season']==2026,'Unsupported season/schema')
    require(isinstance(data['events'],list),'Events must be a list')
    datetime.fromisoformat(data['generatedAt'])
    require(not PRIVATE.search(json.dumps(data,ensure_ascii=False)),'Private metadata detected')
    ids=set()
    for e in data['events']:
        require(isinstance(e,dict) and set(e)==FIELDS,'Unexpected public event fields')
        require(isinstance(e['id'],str) and re.fullmatch(r'e-[a-zA-Z0-9_-]+',e['id']) and e['id'] not in ids,'Invalid/duplicate public ID');ids.add(e['id'])
        require(isinstance(e['title'],str) and bool(e['title']) and isinstance(e['town'],str) and bool(e['town']),'Missing title/town')
        require(e['region'] in REGIONS,'Unknown region')
        start=date.fromisoformat(e['date']);require(date(2026,11,20)<=start<=date(2026,12,24),'Date outside seasonal window')
        if e['endDate']:require(start<=date.fromisoformat(e['endDate'])<=date(2026,12,24),'End outside seasonal window or before start')
        for field in ['startTime','endTime']:
            if e[field]:
                require(isinstance(e[field],str) and re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',e[field]),'Invalid published time');time.fromisoformat(e[field])
        for field in ['venue','price','registration','registrationUrl']:
            require(e[field] is None or isinstance(e[field],str),'Invalid optional text')
        require(e['category'] in ['strom','mikulas','trhy','tvoreni','setkani','betlem'],'Bad category')
        require(e['audience'] in ['všichni','dospělí','senioři / omezené zaměření','omezené zaměření'],'Bad audience')
        require(e['status'] in ['confirmed','time-unconfirmed','cancelled'],'Bad status')
        require(https(e['sourceUrl']) and (e['registrationUrl'] is None or https(e['registrationUrl'])),'Unsafe public URL')
        require(isinstance(e['description'],str) and len(e['description'])<=200,'Invalid/overlong description')
        require(isinstance(e['notes'],list) and all(isinstance(n,str) for n in e['notes']),'Bad notes')
        datetime.fromisoformat(e['verifiedAt'])
        loc=e['location']
        if loc is not None:
            require(isinstance(loc,dict) and set(loc)=={'lat','lon','precision','label','sourceUrl'},'Bad location fields')
            require(type(loc['lat']) in (int,float) and type(loc['lon']) in (int,float) and 48.5<loc['lat']<51.2 and 12<loc['lon']<19,'Location outside Czechia')
            require(loc['precision'] in ['town','venue'] and isinstance(loc['label'],str) and https(loc['sourceUrl']),'Location provenance missing')
    return True

def validate_directory(path, registry=None):
    if registry is None:registry=Path(__file__).resolve().parents[1]/'data/sources.json'
    if isinstance(registry,(str,Path)):registry=json.loads(Path(registry).read_text())
    sources=registry['sources'];regions={s['region'] for s in sources}
    by_id={s['id']:s for s in sources}
    require(bool(sources) and len(by_id)==len(sources) and regions<=REGIONS,'Invalid registry scope')
    path=Path(path);data=json.loads((path/'events.json').read_text());validate(data)
    coverage=json.loads((path/'coverage.json').read_text());review=json.loads((path/'review.json').read_text())
    window=registry['window'];start=date.fromisoformat(window['from']);end=date.fromisoformat(window['through'])
    require(registry['season']==data['season']==2026 and date(2026,11,20)<=start<=end<=date(2026,12,24),'Invalid registry season/window')
    require(coverage['window']==window,'Coverage window disagrees with registry')
    require(all(start<=date.fromisoformat(e['date'])<=date.fromisoformat(e['endDate'] or e['date'])<=end
                for e in data['events']),'Event outside registry window')
    for document in [coverage,review]:require(not PRIVATE.search(json.dumps(document,ensure_ascii=False)),'Private metadata detected')
    require(coverage['complete'] is False,'Selection must not claim complete coverage')
    require(coverage['metrics']['eventsPublished']==len(data['events']),'Inconsistent published count')
    require(coverage['metrics']['reviewCount']==len(review['candidates']),'Inconsistent review count')
    require(len(coverage['sources'])==len(sources) and {s['id'] for s in coverage['sources']}==set(by_id)
            and len(coverage['regions'])==len(regions) and set(coverage['regions'])==regions,'Inconsistent source scope')
    for source in coverage['sources']:
        expected=by_id[source['id']]
        require(source['region']==expected['region'] and source['town']==expected['town']
                and source['url']==expected['index_urls'][0],'Source identity disagrees with registry')
        require(source['status'] in ['ok','partial','error'] and https(source['url']),'Invalid source status/URL')
    for event in data['events']:
        matches=[s for s in sources if re.fullmatch(s['url_regex'],event['sourceUrl'])]
        require(len(matches)==1,'Event URL must identify one registered source')
        source=matches[0]
        require(event['region']==source['region'],'Event region disagrees with source')
        mapping=source.get('event_locations',{}).get(event['sourceUrl'])
        town=source['town']
        if mapping:
            require(mapping['sourceId']==source['id'] and mapping['sourceTown']==source['town']
                    and mapping['sourceUrl']==event['sourceUrl'] and mapping['expectedDate']==event['date']
                    and mapping['expectedVenue']==event['venue'],'Invalid event location override')
            town=mapping['town']
        require(event['town']==town,'Event town disagrees with source')
    for candidate in review['candidates']:
        require(set(candidate)=={'title','url','reason'} and https(candidate['url']),'Invalid review projection')
    return len(data['events'])

if __name__=='__main__':
    print(f'Public projection validated: {validate_directory(sys.argv[1])} events')
