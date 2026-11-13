"""Closed, exact-content-bound editorial receipts for normally discovered URLs.

No fetching occurs here. ``resolve`` returns None for a normal URL, otherwise
(decision, reason, public_events, extended_end_ids). Omitting body performs only
registry/receipt validation, for checking a public projection without HTTP.
"""
import hashlib
import json
import re
from datetime import datetime
from urllib.parse import unquote, urlsplit

import validate_public


class AuditError(ValueError):
    """A receipt needs a new human review, not an outage retry."""


def _detail(body, adapter):
    # Lazy import avoids a collector/module initialization cycle.
    from collector import DOM, Node, norm, exact_label
    root = DOM(body).root
    heading, scopes = None, []
    if adapter == 'galileo':
        heading, scopes = root.find('h1'), [root.find(cls='event-detail')]
    elif adapter == 'humpolec':
        detail = root.find('main', cls='event')
        content = detail.find('section', id='content') if detail else None
        heading = detail.find('h1') if detail else None
        scopes = [content.find(cls='container') if content else None]
    elif adapter == 'hranice':
        detail = root.find('article', cls='akce-detail')
        heading = detail.find('h1') if detail else None
        scopes = [detail, root.find(cls='akce-content')]
    elif adapter == 'telc':
        detail = root.find(cls='clanek_levy_sloupec')
        heading, scopes = detail.find('h2') if detail else None, [detail]
    elif adapter == 'visitzlin':
        detail = root.find('section', cls='site-event')
        heading = detail.find('h2') if detail else None
        scopes = [detail.find(cls='event') if detail else None]
        # Some installations also repeat the actual title in the image header.
        if root.find('h1'):
            scopes.append(root.find('h1'))
    if heading is None or not heading.text() or not scopes or any(n is None for n in scopes):
        raise AuditError('Chybí sémantický rozsah ověřovaného detailu.')
    stopped = False

    def semantic(node):
        nonlocal stopped
        if stopped or node.tag in ('script', 'style', 'noscript', 'nav', 'footer'):
            return ''
        if node.tag in ('iframe', 'frame', 'object', 'embed'):
            raise AuditError('Vložený obsah nelze bezpečně ověřit z detailu; ověřte znovu.')
        if adapter == 'humpolec' and node.attrs.get('id') == 'related':
            return ''
        if adapter == 'telc' and node.tag == 'strong' and exact_label(node.text()).rstrip(':') == 'organizátor akce':
            stopped = True
            return ''
        parts = [f'{key}={node.attrs[key]}' for key in ('href', 'src', 'srcset', 'data-src', 'data-srcset', 'poster', 'alt') if key in node.attrs]
        for child in node.children:
            if stopped:
                break
            parts.append(semantic(child) if isinstance(child, Node) else child)
        return norm(' '.join(parts))

    text = norm(' '.join(semantic(n) for n in scopes))
    if not text:
        raise AuditError('Chybí sémantický obsah ověřovaného detailu.')
    title = heading.text()
    return title, hashlib.sha256(norm(title + ' ' + text).encode()).hexdigest()


def fingerprint(body, adapter):
    """SHA256 of normalized semantic event detail including its actual heading."""
    return _detail(body, adapter)[1]


def occurrence_id(url, key):
    """Namespaced, length-delimited identity, independent of facts/list position."""
    encoded = json.dumps([url, key], ensure_ascii=False, separators=(',', ':'))
    return 'e-audit-' + hashlib.sha256(encoded.encode()).hexdigest()[:32]


RECEIPT_FIELDS = set('sourceId sourceTown sourceUrl expectedTitle contentHash decision reason verifiedAt events'.split())
ADAPTERS = {'galileo', 'humpolec', 'hranice', 'telc', 'visitzlin'}
FACT_FIELDS = (validate_public.FIELDS - {'id', 'region', 'status', 'verifiedAt', 'sourceUrl'}) | {'occurrenceKey', 'allowExtendedEnd'}
PHONE = re.compile(r'(?<!\d)(?:\+420[\s.-]*)?[2-9]\d{2}[\s.-]*\d{3}[\s.-]*\d{3}(?!\d)')


def _phone_free(data):
    # Decode to a bounded fixed point, as the shared privacy validator does.
    # Check public text only: numeric OSM/ticket URL identifiers are not contacts.
    text = json.dumps(data, ensure_ascii=False)
    for depth in range(17):
        decoded = unquote(text)
        if decoded == text:
            return not PHONE.search(text)
        validate_public.require(depth < 16, 'Excessive percent encoding')
        text = decoded
    return False


def resolve(source, url, window, body=None):
    try:
        return _resolve(source, url, window, body)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, re.error) as exc:
        raise AuditError('Neplatné nebo změněné ověřené rozhodnutí; ověřte znovu.') from exc


def _resolve(source, url, window, body):
    require = validate_public.require
    records = source.get('audited_events', {})
    require(isinstance(records, dict), 'Invalid receipt map')
    if url not in records:
        return None
    record = records[url]
    require(isinstance(record, dict) and set(record) == RECEIPT_FIELDS, 'Invalid receipt fields')
    require(source['adapter'] in ADAPTERS, 'Unsupported receipt adapter')
    require(validate_public.https(url) and not urlsplit(url).fragment
            and urlsplit(url).hostname == urlsplit(source['index_urls'][0]).hostname
            and re.fullmatch(source['url_regex'], url), 'Unbound receipt URL')
    require(record['sourceId'] == source['id'] and record['sourceTown'] == source['town']
            and record['sourceUrl'] == url, 'Unbound source identity')
    require(isinstance(record['expectedTitle'], str) and record['expectedTitle'].strip() and len(record['expectedTitle']) <= 180,
            'Invalid expected title')
    require(isinstance(record['contentHash'], str) and re.fullmatch(r'[0-9a-f]{64}', record['contentHash']),
            'Invalid content hash')
    require(record['decision'] in ('accept', 'exclude', 'hold'), 'Invalid decision')
    require(isinstance(record['reason'], str) and record['reason'].strip() and len(record['reason']) <= 500, 'Invalid reason')
    require(_phone_free([record['reason'], record['expectedTitle']]), 'Private phone contact')
    require(isinstance(record['verifiedAt'], str) and datetime.fromisoformat(record['verifiedAt']).tzinfo is not None,
            'Verification must be a timezone-aware timestamp')
    require(isinstance(record['events'], list) and (1 <= len(record['events']) <= 16
            if record['decision'] == 'accept' else not record['events']), 'Invalid occurrence count')
    validate_public.validate_privacy(record)
    if body is not None:
        title, content_hash = _detail(body, source['adapter'])
        if record['expectedTitle'] != title or record['contentHash'] != content_hash:
            raise AuditError('Ověřené rozhodnutí již neodpovídá detailu; ověřte znovu.')
    events, extended = [], set()
    for fact in record['events']:
        require(isinstance(fact, dict) and set(fact) == FACT_FIELDS, 'Invalid occurrence fields')
        require(isinstance(fact['occurrenceKey'], str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,47}', fact['occurrenceKey']),
                'Invalid literal occurrence key')
        require(type(fact['allowExtendedEnd']) is bool, 'Invalid extended-end flag')
        for field in ('title', 'town'):
            require(isinstance(fact[field], str) and 0 < len(fact[field].strip()) <= 180, 'Invalid public title/town')
        require(fact['venue'] is None or isinstance(fact['venue'], str) and 0 < len(fact['venue'].strip()) <= 180,
                'Invalid venue')
        require(isinstance(fact['description'], str) and len(fact['description']) <= 200, 'Invalid description')
        require(isinstance(fact['date'], str) and window['from'] <= fact['date'] <= window['through'], 'Start outside registry window')
        require(fact['endDate'] is None or fact['endDate'] <= ('2026-12-31' if fact['allowExtendedEnd'] else window['through']),
                'End outside registry window')
        if fact['startTime'] and fact['endTime'] and fact['endDate'] in (None, fact['date']):
            require(fact['startTime'] <= fact['endTime'], 'Reversed same-day time interval')
        if fact['location'] is not None:
            require(urlsplit(fact['location']['sourceUrl']).hostname in ('openstreetmap.org', 'www.openstreetmap.org'),
                    'Unreviewed map provenance')
        # Public receipts may describe booking, but must not publish contact details.
        public_text = [fact[k] for k in ('title', 'town', 'venue', 'description', 'notes', 'price', 'registration')]
        if fact['location'] is not None:
            public_text.append(fact['location']['label'])
        require(_phone_free(public_text), 'Private phone contact')
        event = {k: v for k, v in fact.items() if k not in ('occurrenceKey', 'allowExtendedEnd')}
        event.update(id=occurrence_id(url, fact['occurrenceKey']), region=source['region'],
                     sourceUrl=url, verifiedAt=record['verifiedAt'],
                     status='confirmed' if fact['startTime'] else 'time-unconfirmed')
        events.append(event)
        if fact['allowExtendedEnd']:
            extended.add(event['id'])
    validate_public.validate(dict(schemaVersion=1, generatedAt=record['verifiedAt'], season=2026,
                                  region='Česko', events=events), extended)
    return record['decision'], record['reason'], events, extended
