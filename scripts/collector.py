#!/usr/bin/env python3
"""Bounded, deterministic public-event collector (stdlib only)."""
import argparse
from datetime import datetime, timezone, date
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sqlite3
import time
import unicodedata
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser
import uuid
from zoneinfo import ZoneInfo


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def norm(text):
    return ' '.join(text.split())


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def exact_label(text):
    return norm(unicodedata.normalize('NFKC', text)).casefold()


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        if self.tag in ('script', 'style', 'noscript'):
            return ''
        return norm(' '.join(c.text() if isinstance(c, Node) else c for c in self.children))

    def find(self, tag=None, cls=None, id=None):
        return next(iter(self.all(tag, cls, id)), None)

    def all(self, tag=None, cls=None, id=None):
        out = []
        if (tag is None or self.tag == tag) and (cls is None or cls in self.attrs.get('class', '').split()) and (id is None or self.attrs.get('id') == id):
            out.append(self)
        for c in self.children:
            if isinstance(c, Node):
                out.extend(c.all(tag, cls, id))
        return out


class DOM(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
    def __init__(self, body):
        super().__init__(convert_charrefs=True)
        self.root = Node('document')
        self.stack = [self.root]
        if isinstance(body, bytes):
            encoding = re.search(br'charset=["\s]*([\w-]+)', body[:5000], re.I)
            body = body.decode(encoding.group(1).decode() if encoding else 'utf-8', errors='replace')
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs)
        self.stack[-1].children.append(n)
        if tag not in self.VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def txt(node):
    return node.text() if node else ''


class Review(ValueError):
    pass


class Excluded(Review):
    """Known policy exclusion, not an unresolved factual candidate."""
    pass


def parse_dates(text):
    pattern = r'(?<!\d)(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d{2})(?!\d)'
    found = []
    for m in re.finditer(pattern, text):
        try:
            d = date(int(m[3]), int(m[2]), int(m[1])).isoformat()
        except ValueError:
            raise Review('Neplatné datum v detailu.')
        found.append((d, m.end()))
    return found


def clean_public(text):
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '', text)
    text = re.sub(r'(?<!\w)/(?:home|private|tmp|workspace|var)/\S*', '', text)
    return norm(text)


def structured_event(root):
    candidates = []
    def walk(value):
        if isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, dict):
            types = value.get('@type', [])
            if 'Event' in ([types] if isinstance(types, str) else types):
                candidates.append(value)
            if '@graph' in value:
                walk(value['@graph'])
    for script in root.all('script'):
        if script.attrs.get('type') == 'application/ld+json':
            try:
                walk(json.loads(''.join(c for c in script.children if isinstance(c,str))))
            except (ValueError, TypeError):
                continue
    if len(candidates) > 1:
        raise Review('Strukturovaný detail obsahuje více událostí; ověřte jednotlivé termíny.')
    return candidates[0] if candidates else None


def structured_price(event):
    offers = event.get('offers', [])
    if isinstance(offers, dict):
        offers = [offers]
    prices = []
    for offer in offers:
        if not isinstance(offer, dict) or offer.get('priceCurrency') != 'CZK':
            continue
        values = [offer.get('lowPrice'), offer.get('highPrice')] if offer.get('@type') == 'AggregateOffer' else [offer.get('price')]
        if not all(re.fullmatch(r'\d+(?:\.\d+)?',str(v)) for v in values):
            continue
        amount = '–'.join(dict.fromkeys(str(v) for v in values)) + ' Kč'
        name = clean_public(str(offer.get('name','')))
        prices.append((name + ': ' if name else '') + amount)
    return '; '.join(prices) or None


def review_fingerprint(body, adapter):
    """SHA256 of whitespace-normalized semantic event text, never page chrome."""
    root = DOM(body).root
    scope = root.find(cls={'galileo': 'event-detail', 'itrebon': 'kalendarDetail', 'telc': 'clanek_levy_sloupec'}.get(adapter, '__unsupported__'))
    if adapter == 'humpolec':
        content = root.find('section', id='content')
        scope = content.find(cls='container') if content else None
    if scope is None:
        raise Review('Chybí sémantický rozsah ověřovaného detailu.')
    def semantic(node):
        if node.attrs.get('id') == 'related' and adapter == 'humpolec':
            return ''
        if node.tag in ('script', 'style', 'noscript'):
            return ''
        parts = []
        for child in node.children:
            if adapter == 'telc' and isinstance(child, Node) and child.tag == 'strong' and exact_label(txt(child)).rstrip(':') == 'organizátor akce':
                break
            parts.append(semantic(child) if isinstance(child, Node) else child)
        return norm(' '.join(parts))
    return digest(semantic(scope))


def parse_event(body, source, url, window):
    if not safe_url(url):
        raise Review('Neplatný odkaz zdroje.')
    root = DOM(body).root
    scope = root.find(cls='event-detail')
    title = txt(root.find('h1'))
    adapter = source['adapter']
    structured = structured_event(root)
    if adapter in ('hranice', 'visitzlin', 'lanskroun') and structured:
        raise Review('Nová strukturovaná data nesmějí obejít ověření označených polí; ověřte formát znovu.')
    wpem_price = None
    if adapter == 'wpem' and structured:
        # WP Event Manager uses a nonstandard capitalized Location and space-separated timestamps.
        structured = dict(structured)
        if not structured.get('startDate'):
            raise Review('Chybí strukturovaný začátek události.')
        if 'location' in structured and structured.get('Location') != structured['location']:
            raise Review('Rozporná strukturovaná místa události.')
        structured['location'] = structured.get('Location')
        for field in ('startDate', 'endDate'):
            value = structured.get(field)
            if value is not None:
                if not isinstance(value, str) or not re.fullmatch(r'20\d{2}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', value):
                    raise Review('Neplatné datum WP Event Manager.')
                structured[field] = value.replace(' ', 'T')
        # These canonical local ISO timestamps include both date and seconds.
        if structured.get('endDate') and structured['endDate'] < structured['startDate']:
            raise Review('Konec události předchází začátku; ověřte celý časový interval.')
        details = root.find(cls='wpem-event-details')
        prices = [txt(n) for n in details.children if isinstance(n, Node) and n.find(cls='wpem-icon-ticket')] if details else []
        if len(prices) > 1:
            raise Review('Nejednoznačné cenové pole události.')
        wpem_price = clean_public(prices[0]) if prices else None
        if wpem_price and len(wpem_price) > 180:
            raise Review('Cenový údaj je příliš dlouhý; ověřte všechny varianty bez zkrácení.')
    if adapter in ('structured', 'wpem') and not structured:
        raise Review('Chybí strukturovaný detail jedné události.')
    if structured:
        scope = Node('div')
        title = str(structured.get('name', ''))
        scope.children = [title, txt(DOM(str(structured.get('description',''))).root)]
        adapter = 'structured'
    venue = ''
    fields = {}
    if adapter == 'structured':
        date_text = ''
        for field in ('startDate','endDate'):
            value = structured.get(field)
            if not value:
                continue
            try:
                stamp = datetime.fromisoformat(value)
                if stamp.tzinfo:
                    stamp = stamp.astimezone(ZoneInfo('Europe/Prague'))
            except (ValueError, TypeError):
                raise Review('Neplatné strukturované datum.')
            date_text += (' – ' if date_text else '') + stamp.strftime('%d. %m. %Y') + (stamp.strftime(' %H:%M') if 'T' in value else '')
        place = structured.get('location', {})
        venue = place.get('name', '') if isinstance(place,dict) else str(place)
        address = place.get('address', {}) if isinstance(place,dict) else {}
        locality = address.get('addressLocality') if isinstance(address,dict) else None
        if locality and exact_label(str(locality)) != exact_label(source['town']):
            raise Review('Strukturovaná adresa neodpovídá obci zdroje; ověřte lokalitu.')
    elif adapter == 'lanskroun':
        tops = root.all(cls='festival-top__content')
        if len(tops) != 1:
            raise Review('Chybí jednoznačný festivalový detail.')
        top = tops[0]
        labels = top.all(cls='festival-top__datum-konani')
        headings = top.all('h1', cls='festival-top__nazev')
        summaries = top.all(cls='festival-top__kratky-popis')
        if len(labels) != 1 or len(headings) != 1 or len(summaries) != 1:
            raise Review('Nejednoznačná označená pole festivalu.')
        interval = re.fullmatch(r'(\d{1,2})\.\s*(\d{1,2})\.?\s*[-–]\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d{2})', txt(labels[0]))
        if not interval:
            raise Review('Festival vyžaduje úplný označený interval s výslovným společným rokem.')
        try:
            first = date(int(interval[5]), int(interval[2]), int(interval[1]))
            last = date(int(interval[5]), int(interval[4]), int(interval[3]))
        except ValueError:
            raise Review('Neplatné datum festivalového intervalu.')
        if last < first:
            raise Review('Obrácený festivalový interval.')
        # The year is explicit in this single labelled range, never borrowed from URL or page chrome.
        date_text = first.strftime('%d. %m. %Y') + ' – ' + last.strftime('%d. %m. %Y')
        summary = txt(summaries[0])
        if parse_dates(summary):
            raise Review('Další termín v označeném popisu festivalu vyžaduje ověření.')
        place = re.search(r'\bna (náměstí J\. M\. Marků)(?!\w)', summary)
        if not place:
            raise Review('Chybí ověřené místní náměstí v popisu festivalu.')
        if re.search(r'\bkc\b|vstup|zdarma|cen[ay]|dobrovoln|prispevk', fold(txt(headings[0]) + ' ' + summary)):
            raise Review('Nové cenové podmínky festivalu vyžadují ověření.')
        venue = place[1]
        title = txt(headings[0])
        scope = Node('article')
        scope.children = [headings[0], summaries[0]]
    elif adapter == 'galileo' and scope:
        date_node = scope.find(cls='event-action__date-start-text') or scope.find(cls='action-date')
        date_text = txt(date_node)
        venue = txt(scope.find(cls='event-action__venue-text') or scope.find(cls='venue'))
    elif adapter == 'itrebon':
        scope = root.find(cls='kalendarDetail')
        table = scope.find('table', cls='kal-info-detail') if scope else None
        fields = {}
        if table:
            for row in table.all('tr'):
                # The live CMS omits some closing tr tags: only direct cells belong to this row.
                cells = [n for n in row.children if isinstance(n, Node) and n.tag == 'td']
                if len(cells) == 2:
                    fields[txt(cells[0]).rstrip(':')] = txt(cells[1])
        date_text = fields.get('Datum konání akce', '') + ' ' + fields.get('Čas konání', '')
        venue = fields.get('Místo', '')
    elif adapter == 'telc':
        detail = root.find(cls='clanek_levy_sloupec')
        if detail is None:
            raise Review('Chybí tělo detailu události.')
        title = txt(detail.find('h2'))
        leading = norm(' '.join(n for n in detail.children[:next((i for i,n in enumerate(detail.children) if isinstance(n, Node)), len(detail.children))] if isinstance(n, str)))
        if not re.fullmatch(r'\d{1,2}\.\d{1,2}\.20\d{2}\s*[-–]\s*\d{1,2}\.\d{1,2}\.20\d{2}', leading):
            raise Review('Chybí úplný úvodní termín události.')
        scope = Node('article')
        for child in detail.children:
            if isinstance(child, Node) and child.tag == 'strong' and exact_label(txt(child)) == 'organizátor akce':
                break
            scope.children.append(child)
        # Venue is below organizer contacts, outside the narrative scope.
        for i, child in enumerate(detail.children):
            if isinstance(child, Node) and child.tag == 'strong' and exact_label(txt(child)).rstrip(':') == 'místo konání':
                parts = []
                for sibling in detail.children[i+1:]:
                    if isinstance(sibling, Node) and sibling.tag in ('br', 'div', 'strong'):
                        break
                    parts.append(txt(sibling) if isinstance(sibling, Node) else sibling)
                venue = norm(' '.join(parts))
        expected_dates = {d for d, pos in parse_dates(leading)}
        for m in re.finditer(r'(\d{1,2})\.\s*(listopadu|prosince)\s+(20\d{2})', txt(scope), re.I):
            try:
                narrative_date = date(int(m[3]), 11 if m[2].lower() == 'listopadu' else 12, int(m[1])).isoformat()
            except ValueError:
                raise Review('Neplatné datum v detailu.')
            if narrative_date not in expected_dates:
                raise Review('Rozporná data v těle události vyžadují ověření.')
        clock = re.search(r'(?<!\d)(\d{1,2})[.:]([0-5]\d)(?:\s*[-–]\s*(\d{1,2})[.:]([0-5]\d))?\s*hod(?:in)?\b', txt(scope), re.I)
        date_text = leading
        if clock:
            date_text += f' {clock[1]}:{clock[2]}' + (f' – {clock[3]}:{clock[4]}' if clock[3] else '')
    elif adapter == 'humpolec':
        detail = next((n for n in root.all('main', cls='event') if 'single' in n.attrs.get('class', '').split()), None)
        content = detail.find('section', id='content') if detail else None
        meta = content.find('aside', id='meta') if content else None
        items = meta.find(cls='meta-items') if meta else None
        if items is None:
            raise Review('Chybí časová a místní metadata události.')
        title = txt(detail.find('h1'))
        fields = {}
        for item in items.all('span'):
            label = item.attrs.get('aria-label')
            if label:
                if label in fields:
                    raise Review('Více výskytů časového nebo místního pole.')
                fields[label] = txt(item.find(cls='value'))
        day = fields.get('Kdy', '')
        if len(parse_dates(day)) != 1:
            raise Review('Více termínů nebo chybějící úplné datum události.')
        clock = fields.get('V kolik', '')
        if clock and not re.fullmatch(r'(?:od\s+)?\d{1,2}:[0-5]\d(?:\s+do\s+\d{1,2}:[0-5]\d)?', clock):
            raise Review('Více začátků nebo nejednoznačné hodiny události.')
        clock = re.sub(r'\s+do\s+00:00$', '', clock)
        date_text = day + ' ' + clock
        venue = fields.get('Místo', '')
        scope = Node('article')
        container = content.find(cls='container')
        if container is None:
            raise Review('Chybí tělo detailu události.')
        scope.children = [n for n in container.children if not isinstance(n, Node) or n.attrs.get('id') != 'related']
    elif adapter == 'visitzlin':
        detail = root.find('section', cls='site-event')
        if detail is None:
            raise Review('Chybí označený detail události.')
        scope = detail.find(cls='event')
        if scope is None:
            raise Review('Chybí označený detail události.')
        title = txt(detail.find('h2'))
        fields = {}
        for row in scope.all('p'):
            label = row.find('strong')
            key = txt(label).rstrip(':')
            if key in ('Datum', 'Místo', 'Vstupné', 'Čas'):
                if key in fields:
                    raise Review('Více výskytů časového nebo místního pole.')
                fields[key] = norm(' '.join(txt(n) if isinstance(n, Node) else n for n in row.children if n is not label))
        date_text = re.sub(r'\b(?:Po|Út|St|Čt|Pá|So|Ne)\s+', '', fields.get('Datum', ''))
        full_date = r'\d{1,2}\.\s*\d{1,2}\.\s*20\d{2}'
        if not re.fullmatch(full_date + r'(?:\s*[-–]\s*' + full_date + r')?', date_text):
            raise Review('Neúplný nebo nejednoznačný interval události.')
        clock = fields.get('Čas', '')
        if clock and not re.fullmatch(r'(?:[01]?\d|2[0-3])[.:][0-5]\d(?:\s*[-–]\s*(?:[01]?\d|2[0-3])[.:][0-5]\d)?', clock):
            raise Review('Více začátků nebo neplatné hodiny události.')
        if len({d for d, pos in parse_dates(date_text)}) == 1:
            date_text += ' ' + clock.replace('.', ':')
        venue = fields.get('Místo', '')
    elif adapter == 'hranice':
        detail = root.find('article', cls='akce-detail')
        if detail is None:
            raise Review('Chybí označený detail události.')
        title = txt(detail.find('h1'))
        fields = {}
        for row in detail.all('p'):
            label = row.find('span', cls='popisek')
            if label:
                key = txt(label)
                if key in fields:
                    raise Review('Více výskytů časového nebo místního pole.')
                fields[key] = norm(' '.join(txt(n) if isinstance(n, Node) else n for n in row.children if n is not label))
        day = fields.get('Kdy', '')
        # Occurrence lists and abbreviated ranges must not become a single opening day.
        if not re.fullmatch(r'(?:(?:Pondělí|Úterý|Středa|Čtvrtek|Pátek|Sobota|Neděle)\s+)?\d{1,2}\.\s*\d{1,2}\.\s*20\d{2}', day, re.I):
            raise Review('Chybí jediný úplný termín události.')
        clock = fields.get('Začátek', '')
        if clock and not re.fullmatch(r'(?:[01]?\d|2[0-3]):[0-5]\d', clock):
            raise Review('Více začátků nebo neplatné hodiny události.')
        date_text = day + ' ' + clock
        venue = fields.get('Kde', '')
        scope = Node('article')
        # Inclusive taxonomy tags (e.g. "pro seniory") are not entry restrictions.
        scope.children = [title]
        content = root.find(cls='akce-content')
        if content:
            scope.children.append(content)
    elif adapter == 'vismo':
        scope = root.find(id='akce')
        title = txt(root.find(id='zahlavi'))
        fields = {}
        if scope:
            for dl in scope.all('dl'):
                fields[txt(dl.find('dt')).rstrip(':')] = txt(dl.find('dd'))
        date_text = fields.get('Kdy', '')
        venue = fields.get('Kde', '')
    elif adapter == 'wordpress':
        scope = root.find(cls='entry-content') or root.find(cls='content__inner')
        title = txt(scope.find('h1')) if scope else title
        # Event dates come from article paragraphs/headings, never publication metadata.
        if scope and scope.find(cls='post__details'):
            article = Node('article')
            for child in scope.children:
                if isinstance(child, Node) and 'post__details' in child.attrs.get('class', '').split():
                    break
                article.children.append(child)
            scope = article
        date_text = txt(scope)
        venue_match = re.search(r'RAJHRAD\s*/\s*([^/]+)\s*/', date_text, re.I)
        venue = venue_match[1].strip() if venue_match else ''
    elif adapter == 'drupal':
        scope = root.find('main')
        title = txt(scope.find('h1')) if scope else title
        date_field = scope.find(cls='field--name-field-datetime-startend') if scope else None
        stamps = date_field.all('time') if date_field else ([scope.find('time')] if scope and scope.find('time') else [])
        if date_field and len(stamps) not in (1, 2):
            raise Review('Nejednoznačné krajní termíny události.')
        date_parts = []
        for stamp in stamps:
            m = re.fullmatch(r'(20\d{2})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):.*', stamp.attrs.get('datetime', ''))
            if not m:
                raise Review('Neplatné datum v časovém poli události.')
            date_parts.append(f'{m[3]}. {m[2]}. {m[1]} {m[4]}:{m[5]}')
        date_text = ' – '.join(date_parts)
        venue = txt(scope.find(cls='field--name-field-event-place')) if scope else ''
    else:
        raise Review('Nepodporovaný nebo neúplný detail události.')
    if scope is None:
        raise Review('Chybí tělo detailu události.')
    dates = parse_dates(date_text)
    if not dates:
        months = {'listopadu': 11, 'listopad': 11, 'prosince': 12, 'prosinec': 12}
        for m in re.finditer(r'(\d{1,2})\.\s*(listopadu|listopad|prosince|prosinec)\s+(20\d{2})', date_text, re.I):
            dates.append((date(int(m[3]), months[m[2].lower()], int(m[1])).isoformat(), m.end()))
    # Repeated date in article heading and paragraph is not a multi-day range.
    dates = list({d: (d, pos) for d,pos in dates}.values())
    if dates and not all(window['from'] <= d <= window['through'] for d, pos in dates):
        raise Excluded('Datum je mimo sledované období.')
    if adapter == 'itrebon' and re.search(r'[-–,]', fields.get('Datum konání akce', '')) and not re.fullmatch(r'\d{1,2}\.\s*\d{1,2}\.\s*20\d{2}\s*[-–]\s*\d{1,2}\.\s*\d{1,2}\.\s*20\d{2}', fields['Datum konání akce']):
        raise Review('Neúplný nebo nejednoznačný interval události.')
    if len(dates) > 1:
        explicit_range = adapter in ('itrebon', 'telc', 'visitzlin', 'lanskroun') and re.match(r'^\s*\d{1,2}\.\s*\d{1,2}\.\s*20\d{2}\s*[-–]\s*\d{1,2}\.\s*\d{1,2}\.\s*20\d{2}(?!\d)', date_text)
        if (not explicit_range and (adapter not in ('galileo', 'structured', 'drupal') or not re.search(r'\s[-–]\s', date_text))) or len(dates) > 2 or dates[1][0] < dates[0][0]:
            raise Review('Více různých dat vyžaduje ruční kontrolu.')
    narrative_nodes = [scope.find(cls=cls) for cls in ('lead','event-action-lead__body','event-text')]
    narrative_nodes.extend(n for n in scope.children if isinstance(n,Node) and n.tag == 'p')
    narrative = ' '.join(txt(n) for n in narrative_nodes if n)
    if adapter == 'galileo' and re.search(r'\bpotrva\s+do\s+\d{1,2}\.\s*\d{1,2}\.', fold(narrative)):
        raise Review('Popis uvádí další konec programu; ověřte úplný interval místo jediného dne.')
    if adapter == 'galileo' and any(d not in {x[0] for x in dates} for d,pos in parse_dates(narrative)):
        raise Review('Rozporná data v těle události vyžadují ověření.')
    if not dates:
        raise Review('V těle detailu chybí úplné datum s rokem.')
    times = re.findall(r'(?<!\d)([0-2]?\d):([0-5]\d)(?!\d)', date_text)
    if not times:
        hours = re.search(r'(?<!\d)(\d{1,2})\s*[-–]\s*(\d{1,2})\s*hod', date_text)
        if hours:
            times = [(hours[1], '00'), (hours[2], '00')]
        else:
            hour = re.search(r'(?<!\d)(\d{1,2})\s*hod', date_text)
            times = [(hour[1], '00')] if hour else []
    if any(int(h) >= 24 for h, m in times):
        raise Review('Neplatná hodina v detailu události.')
    times = [f'{int(h):02d}:{m}' for h, m in times]
    if adapter == 'telc' and len(dates) > 1:
        times = []
    start = times[0] if times and times[0] != '00:00' else None
    venue = re.sub(r'^Kde:\s*', '', venue)
    reviews = source.get('event_reviews', {})
    if not isinstance(reviews, dict):
        raise Review('Neplatný seznam ověřených rozhodnutí; ověřte znovu.')
    review = reviews.get(url)
    if url in reviews:
        identities = dict(sourceId=source.get('id'), sourceUrl=url, sourceTown=source['town'],
                          expectedTitle=clean_public(title)[:180], expectedDate=dates[0][0],
                          expectedEndDate=dates[-1][0] if len(dates) > 1 else None,
                          expectedVenue=clean_public(venue)[:180], contentHash=review_fingerprint(body, source['adapter']))
        if not isinstance(review, dict) or any(k not in review or review[k] != v for k, v in identities.items()) or review.get('decision') not in ('accept', 'exclude', 'hold') or not isinstance(review.get('reason'), str):
            raise Review('Ověřené rozhodnutí již neodpovídá detailu; ověřte znovu.')
        if review['decision'] == 'exclude':
            raise Excluded(clean_public(review['reason']))
        if review['decision'] == 'hold':
            raise Review(clean_public(review['reason']))
    verified_town = review is not None and review['decision'] == 'accept' and review.get('verifiedTown') == source['town']
    if 'allowed_venues' in source and exact_label(venue) not in {exact_label(v) for v in source['allowed_venues']} and not verified_town:
        raise Review('Místo konání není v ověřeném seznamu zdroje; ověřte lokalitu.')
    mapping = source.get('event_locations', {}).get(url)
    town = source['town']
    if mapping:
        if (mapping['sourceId'] != source.get('id') or mapping['sourceTown'] != source['town'] or mapping['sourceUrl'] != url
                or exact_label(mapping['expectedVenue']) != exact_label(venue)
                or mapping['expectedDate'] != dates[0][0]):
            raise Review('Ověřené mapování lokality již neodpovídá zdroji, místu nebo datu; ověřte znovu.')
        town = mapping['town']
    towns = ['Plasy', 'Černošín', 'Semily', 'Jilemnice', 'Rajhrad', 'Kuřim', 'Babina', 'Žebnice', 'Horní Hradiště', 'Nebřeziny']
    if not mapping and any(fold(t) in fold(venue) for t in towns if t != source['town']):
        raise Review('Místo konání neodpovídá obci zdroje; ověřte lokalitu.')

    text = fold(title + ' ' + txt(scope))
    title_key = fold(title)
    if re.search(r'\bzajezd\b|\bexkurze\b', title_key):
        raise Excluded('Zájezd / výjezd není součástí místního programového výběru.')
    category = next((cat for terms, cat in [('strom', 'strom'), ('mikulas', 'mikulas'), ('tvoren|diln|svicn|pranic', 'tvoreni'), ('jarmark|trh|vystav', 'trhy'), ('betlem', 'betlem')] if re.search(terms, title_key)), 'setkani')
    audience = 'senioři / omezené zaměření' if re.search(r'pro seniory|pouze pro cleny|jen pro cleny', text) and not re.search(r'verejnost|vsichni jsou zvani',text) else ('dospělí' if 'pro dospele' in text else 'všichni')
    booking_mentioned = re.search(r'rezervac|prihlasen', text) and not re.search(r'bez rezervac|neni nutn[ae] rezervac', text)
    registration = 'Pořadatel uvádí rezervace / přihlášení; podmínky ověřte přímo u něj.' if booking_mentioned else None
    price_match = re.search(r'\b\d+(?:\s*[-–]\s*\d+)?\s*Kč\b', txt(scope))
    price = price_match[0] if price_match else ('dobrovolné' if 'dobrovolne' in text else None)
    if adapter in ('humpolec', 'hranice', 'visitzlin'):
        price = clean_public(fields.get('Cena' if adapter == 'humpolec' else 'Vstupné', '')) or None
        if adapter == 'humpolec' and price:
            price = price[:180]
        elif price and len(price) > 180:
            raise Review('Cenový údaj je příliš dlouhý; ověřte všechny varianty bez zkrácení.')
    if structured:
        price = wpem_price if source['adapter'] == 'wpem' else structured_price(structured)
    notes = []
    if source['adapter'] == 'wpem' and structured:
        programme = clean_public(txt(DOM(str(structured.get('description', ''))).root))
        if programme:
            notes.append(programme[:500])
    if mapping:
        notes.append(f"{town} je část Plas; mapa ukazuje jen orientační střed místní části, nikoli přesné místo akce.")
    if len(dates) > 1:
        notes.append('Uvedeny jsou krajní termíny; nejde o potvrzení nepřetržitého ani každodenního otevření.')
    if 'predbezny' in text:
        notes.append('Pořadatel označuje program jako předběžný.')
    if not start:
        notes.append('Čas zahájení není potvrzen; půlnoc se nepovažuje za skutečný začátek.')
    if adapter == 'galileo' and len(times) == 1:
        programme = re.search(r'\bod\s+(\d{1,2}:[0-5]\d)\s+do\s+(\d{1,2}:[0-5]\d)', narrative, re.I)
        if programme and programme[1].zfill(5) == start:
            times.append(programme[2].zfill(5))
        lighting = re.search(r'rozsvítí\s+(?:se\s+)?v\s+(\d{1,2}:[0-5]\d)', narrative, re.I)
        if lighting:
            notes.append('Rozsvícení stromu je uvedeno v ' + lighting[1] + '; začátek se vztahuje k doprovodnému programu.')
    registration_url = None
    if registration:
        for a in scope.all('a'):
            href = a.attrs.get('href','')
            if safe_url(href) and (re.search(r'forms|rezerv|prihlas',href,re.I) or re.search(r'rezerv|prihlas',fold(a.text()))):
                registration_url = href
                break
    title = clean_public(title)[:180]
    venue = clean_public(venue)[:180]
    if not title:
        raise Review('Chybí název události.')
    event = {'id': 'e-' + digest(url)[:20], 'title': title, 'town': town, 'region': source['region'],
            'date': dates[0][0], 'endDate': dates[-1][0] if len(dates) > 1 else None,
            'startTime': start, 'endTime': times[1] if len(times) > 1 else None,
            'venue': venue or None, 'category': category, 'price': price, 'registration': registration,
            'registrationUrl': registration_url, 'description': f"{title}. {venue}"[:200], 'notes': notes,
            'audience': audience, 'status': 'cancelled' if (structured and str(structured.get('eventStatus','')).rstrip('/').split('/')[-1] == 'EventCancelled') or re.search(r'\bzrusen', text) else ('confirmed' if start else 'time-unconfirmed'),
            'verifiedAt': now(), 'sourceUrl': url, 'location': None}
    if review:
        overrides = review.get('overrides')
        if not isinstance(overrides, dict) or set(overrides) - {'startTime', 'endTime', 'price', 'audience', 'notes', 'venue', 'category', 'registration'}:
            raise Review('Neplatná pole ověřených úprav.')
        for key, value in overrides.items():
            if key in ('startTime', 'endTime'):
                valid = value is None or isinstance(value, str) and re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value)
            elif key == 'venue':
                valid = isinstance(value, str) and 0 < len(value) <= 180 and bool(clean_public(value))
            elif key == 'audience':
                valid = value in ('všichni', 'dospělí', 'senioři / omezené zaměření', 'omezené zaměření')
            elif key == 'category':
                valid = value in ('strom', 'mikulas', 'trhy', 'tvoreni', 'setkani', 'betlem')
            elif key == 'notes':
                valid = isinstance(value, list) and all(isinstance(n, str) for n in value)
            else:
                valid = value is None or isinstance(value, str)
            if not valid or (adapter == 'telc' and len(dates) > 1 and key in ('startTime', 'endTime') and value is not None):
                raise Review('Neplatný typ nebo hodnota ověřené úpravy.')
            if key == 'notes':
                event['notes'].extend(clean_public(n) for n in value)
            else:
                event[key] = clean_public(value) if key in ('price', 'venue', 'registration') and value is not None else value
        if 'venue' in overrides:
            event['description'] = f"{event['title']}. {event['venue']}"[:200]
        if 'startTime' in overrides:
            uncertainty = 'Čas zahájení není potvrzen; půlnoc se nepovažuje za skutečný začátek.'
            event['notes'] = [n for n in event['notes'] if n != uncertainty]
            if not event['startTime']:
                event['notes'].insert(0, uncertainty)
        if event['status'] != 'cancelled':
            event['status'] = 'confirmed' if event['startTime'] else 'time-unconfirmed'
    return event


KEYWORDS = re.compile(r'vanoc|vanoce|advent|mikulas|rozsvic|koled|betlem|jarmark', re.I)


def safe_url(url):
    try:
        p = urlsplit(url)
        return p.scheme == 'https' and bool(p.hostname) and not p.username and not p.password and not p.fragment
    except ValueError:
        return False


def same_host(a, b):
    return urlsplit(a).hostname == urlsplit(b).hostname


def discover(body, base, source):
    details, pagination = [], []
    for a in DOM(body).root.all('a'):
        url = urljoin(base, a.attrs.get('href', ''))
        if not safe_url(url) or not same_host(url, source['index_urls'][0]):
            continue
        label = a.text() + ' ' + a.attrs.get('title', '')
        if re.match(source['url_regex'], url) and KEYWORDS.search(fold(label)):
            details.append(url)
        if ('next' in a.attrs.get('rel', '').split() or re.search(r'(?:[?&](?:page|stranka)=\d+|/page/\d+/?)$', url)):
            pagination.append(url)
    return list(dict.fromkeys(details)), list(dict.fromkeys(pagination))


def json_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def collect(registry, db, output, locations, fetcher, source_id=None):
    started = time.monotonic()
    checked = now()
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.executescript('''
        CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, source_id TEXT, url TEXT, fingerprint TEXT, payload TEXT, observed_at TEXT);
        CREATE TABLE IF NOT EXISTS source_state (id TEXT PRIMARY KEY, payload TEXT);
        CREATE TABLE IF NOT EXISTS observations (id INTEGER PRIMARY KEY, source_id TEXT, url TEXT, body_hash TEXT, observed_at TEXT);
        CREATE TABLE IF NOT EXISTS provenance (id INTEGER PRIMARY KEY, event_id TEXT, field TEXT, value TEXT, source_url TEXT, body_hash TEXT, observed_at TEXT);
        CREATE TABLE IF NOT EXISTS reviews (source_id TEXT, url TEXT, title TEXT, reason TEXT, observed_at TEXT, PRIMARY KEY(source_id,url));
        CREATE TABLE IF NOT EXISTS exclusions (source_id TEXT, url TEXT, reason TEXT, observed_at TEXT, PRIMARY KEY(source_id,url));
    ''')
    metrics = dict(runId=str(uuid.uuid4()), durationSeconds=0, requestCount=0, http304=0, cacheUnchanged=0,
                   eventsNew=0, eventsChanged=0, eventsUnchanged=0, eventsPublished=0, reviewCount=0, excludedCount=0, aiCalls=0)
    for source in registry['sources']:
        if source_id and source['id'] != source_id:
            continue
        sid = source['id']
        old = con.execute('SELECT payload FROM source_state WHERE id=?', (sid,)).fetchone()
        previous = json.loads(old[0]) if old else {}
        failures, successful, review_count, excluded_count = 0, 0, 0, 0
        indices = list(dict.fromkeys(source['index_urls']))[:2]
        details = []
        i = 0
        while i < len(indices) and i < 2:
            index_url = indices[i]
            i += 1
            try:
                body = fetcher.get(index_url)
                successful += 1
                links, more = discover(body, index_url, source)
                details.extend(links)
                indices.extend(u for u in more if u not in indices)
            except Exception:
                failures += 1
        # Newly discovered details are prioritized; bootstrap is never the sole discovery mechanism.
        details.extend(source.get('seed_urls', []))
        # Retry known details after transient failures or disappearance from a bounded listing.
        details.extend(r[0] for r in con.execute('SELECT url FROM events WHERE source_id=? ORDER BY url', (sid,)))
        details = [u for u in dict.fromkeys(details) if safe_url(u) and same_host(u, source['index_urls'][0]) and re.match(source['url_regex'], u)]
        for url in details[:min(14, source.get('max_details', 14))]:
            title = 'Událost k ověření'
            try:
                body = fetcher.get(url)
                successful += 1
                body_hash = digest(body)
                con.execute('INSERT INTO observations(source_id,url,body_hash,observed_at) VALUES (?,?,?,?)', (sid,url,body_hash,checked))
                detail_root = DOM(body).root
                title_node = detail_root.find('h1')
                if source['adapter'] == 'telc':
                    detail = detail_root.find(cls='clanek_levy_sloupec')
                    title_node = detail.find('h2') if detail else None
                title = clean_public(txt(title_node))[:180] or title
                event = parse_event(body, source, url, registry['window'])
                mapping = source.get('event_locations', {}).get(url)
                location_key = mapping['locationKey'] if mapping else event['town']
                location = locations.get(location_key) if isinstance(locations, dict) else None
                if location and safe_url(location.get('sourceUrl', '')):
                    event['location'] = {k:location[k] for k in ('lat','lon','precision','label','sourceUrl')}
                semantic = {k:v for k,v in event.items() if k != 'verifiedAt'}
                fingerprint = digest(json.dumps(semantic, sort_keys=True, ensure_ascii=False))
                old_event = con.execute('SELECT fingerprint FROM events WHERE id=?', (event['id'],)).fetchone()
                kind = 'eventsNew' if not old_event else ('eventsUnchanged' if old_event[0] == fingerprint else 'eventsChanged')
                metrics[kind] += 1
                con.execute('INSERT OR REPLACE INTO events VALUES (?,?,?,?,?,?)', (event['id'],sid,url,fingerprint,json.dumps(event,ensure_ascii=False),checked))
                for field in ('date', 'startTime', 'endDate', 'endTime', 'venue', 'town', 'price', 'audience', 'status'):
                    con.execute('INSERT INTO provenance(event_id,field,value,source_url,body_hash,observed_at) VALUES (?,?,?,?,?,?)', (event['id'],field,json.dumps(event[field]),url,body_hash,checked))
                if mapping:
                    for support in mapping.get('supportingSourceUrls', []):
                        if safe_url(support):
                            con.execute('INSERT INTO provenance(event_id,field,value,source_url,body_hash,observed_at) VALUES (?,?,?,?,?,?)', (event['id'],'town',json.dumps(event['town']),support,body_hash if support == url else None,mapping['verifiedAt']))
                con.execute('DELETE FROM reviews WHERE source_id=? AND url=?', (sid,url))
                con.execute('DELETE FROM exclusions WHERE source_id=? AND url=?', (sid,url))
            except Excluded as exc:
                excluded_count += 1
                metrics['excludedCount'] += 1
                con.execute('DELETE FROM events WHERE source_id=? AND url=?', (sid,url))
                con.execute('DELETE FROM reviews WHERE source_id=? AND url=?', (sid,url))
                con.execute('INSERT OR REPLACE INTO exclusions VALUES (?,?,?,?)', (sid,url,str(exc),checked))
            except Review as exc:
                review_count += 1
                # A changed, ambiguous detail must not silently keep advertising prior facts.
                con.execute('DELETE FROM events WHERE source_id=? AND url=?', (sid,url))
                con.execute('DELETE FROM exclusions WHERE source_id=? AND url=?', (sid,url))
                con.execute('INSERT OR REPLACE INTO reviews VALUES (?,?,?,?,?)', (sid,url,title,str(exc),checked))
            except sqlite3.Error:
                con.rollback()
                con.close()
                raise
            except Exception:
                failures += 1
        review_count = con.execute('SELECT count(*) FROM reviews WHERE source_id=?', (sid,)).fetchone()[0]
        state = dict(id=sid, town=source['town'], region=source['region'], url=source['index_urls'][0], adapter=source['adapter'],
                     coverageNote=source.get('coverage_note',''),
                     excludedCount=excluded_count,
                     sourceNote='Programový výběr: pouze sledované období a místní akce; známé termíny mimo období a zájezdy se nezapočítávají do ruční kontroly.',
                     status='error' if failures and not successful else ('partial' if failures or review_count else 'ok'),
                     lastChecked=checked, lastSuccess=checked if successful and not failures else previous.get('lastSuccess'),
                     eventCount=con.execute('SELECT count(*) FROM events WHERE source_id=?', (sid,)).fetchone()[0], reviewCount=review_count,
                     lastError='Část zdroje se nepodařilo načíst; poslední dobrá data jsou zachována.' if failures else None)
        con.execute('INSERT OR REPLACE INTO source_state VALUES (?,?)', (sid,json.dumps(state,ensure_ascii=False)))
        con.commit()
    events, dedupe = [], set()
    allowed_ids = {s['id'] for s in registry['sources']}
    for sid, payload in con.execute('SELECT source_id,payload FROM events ORDER BY id'):
        if sid not in allowed_ids:
            continue
        event = json.loads(payload)
        if not registry['window']['from'] <= event['date'] <= registry['window']['through']:
            continue
        key = tuple(fold(event.get(k) or '') for k in ('town','venue','date','title','startTime'))
        # Never merge venue-less records or distinct source occurrences by title/date alone.
        if event['venue'] and key in dedupe:
            continue
        dedupe.add(key)
        events.append(event)
    events.sort(key=lambda e: (e['date'],e['startTime'] or '99:99',e['town'],e['title']))
    review = [dict(title=title,url=url,reason=reason) for sid,url,title,reason in con.execute('SELECT source_id,url,title,reason FROM reviews ORDER BY source_id,url') if sid in allowed_ids]
    states = {sid:json.loads(p) for sid,p in con.execute('SELECT id,payload FROM source_state')}
    metrics.update({k:fetcher.stats.get(k,0) for k in ('requestCount','http304','cacheUnchanged')})
    metrics.update(eventsPublished=len(events), reviewCount=len(review), durationSeconds=round(time.monotonic()-started,3))
    coverage = dict(generatedAt=checked, window=registry['window'], regions=list(dict.fromkeys(s['region'] for s in registry['sources'])),
                    sources=[states.get(s['id'], dict(id=s['id'],town=s['town'],region=s['region'],url=s['index_urls'][0],adapter=s['adapter'],status='partial',lastChecked=checked,lastSuccess=None,eventCount=0,reviewCount=0,lastError='Zdroj nebyl v tomto běhu kontrolován.')) for s in registry['sources']],
                    metrics=metrics, complete=False, coverageNote='Neúplný výběr obcí, nejvýše dvě stránky a 14 detailů na zdroj. Nejde o úplný soupis krajů.')
    output = Path(output)
    json_write(output/'events.json', dict(schemaVersion=1,generatedAt=checked,season=registry['season'],region='Česko – sezonní výběr',events=events))
    json_write(output/'coverage.json', coverage)
    json_write(output/'review.json', dict(generatedAt=checked,candidates=review))
    con.close()
    return coverage


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HTTPClient:
    MAX_BYTES = 2 * 1024 * 1024
    USER_AGENT = 'AdventCeskoPilot/1.0 (+https://github.com/romanzdk/advent-cesko-pilot)'

    def __init__(self, cache, send=None, min_interval=1.05):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.send = send or self._transport
        self.min_interval = min_interval
        self.last = {}
        self.robots = {}
        self.stats = dict(requestCount=0,http304=0,cacheUnchanged=0)
        self.opener = build_opener(NoRedirect())

    def _transport(self, url, headers):
        try:
            response = self.opener.open(Request(url, headers=headers), timeout=15)
        except HTTPError as exc:
            response = exc
        with response:
            body = response.read(self.MAX_BYTES + 1)
            if len(body) > self.MAX_BYTES:
                raise OSError('Response size limit')
            return response.status, dict(response.headers), body

    def _request(self, url, headers, robots=False):
        original = url
        for redirect in range(4):
            if not safe_url(url) or not same_host(original, url):
                raise OSError('Unsafe redirect')
            host = urlsplit(url).netloc
            policy = self.robots.get(host)
            delay = max(self.min_interval, (policy.crawl_delay('AdventCeskoPilot') or 0) if policy else 0)
            rate = policy.request_rate('AdventCeskoPilot') if policy else None
            if rate and rate.requests:
                delay = max(delay,rate.seconds/rate.requests)
            gap = delay - (time.monotonic() - self.last.get(host, 0))
            if gap > 0:
                time.sleep(gap)
            self.stats['requestCount'] += 1
            try:
                status, response_headers, body = self.send(url, headers)
            finally:
                self.last[host] = time.monotonic()
            if len(body) > self.MAX_BYTES:
                raise OSError('Response size limit')
            response_headers = {k.lower():v for k,v in response_headers.items()}
            if status in (301,302,303,307,308):
                url = urljoin(url, response_headers.get('location',''))
                if not robots and not self.robots[host].can_fetch('AdventCeskoPilot',url):
                    raise OSError('Robots disallows redirect')
                continue
            return status, response_headers, body
        raise OSError('Too many redirects')

    def _check_robots(self, url):
        p = urlsplit(url)
        host = p.netloc
        if host not in self.robots:
            status, headers, body = self._request(f'{p.scheme}://{host}/robots.txt', {'User-Agent':self.USER_AGENT}, robots=True)
            parser = RobotFileParser()
            if status in (404,410):
                parser.parse(['User-agent: *','Disallow:'])
            elif status == 200:
                parser.parse(body.decode('utf-8',errors='replace').splitlines())
            else:
                raise OSError('Robots unavailable')
            self.robots[host] = parser
        if not self.robots[host].can_fetch('AdventCeskoPilot',url):
            raise OSError('Robots disallows URL')

    def get(self, url):
        if not safe_url(url):
            raise OSError('Only safe HTTPS URLs allowed')
        self._check_robots(url)
        key = digest(url)
        meta_path, body_path = self.cache/(key+'.json'), self.cache/(key+'.body')
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        headers = {'User-Agent':self.USER_AGENT,'Accept':'text/html,application/xhtml+xml','Accept-Encoding':'identity'}
        if meta.get('etag'):
            headers['If-None-Match'] = meta['etag']
        if meta.get('lastModified'):
            headers['If-Modified-Since'] = meta['lastModified']
        for attempt in range(2):
            try:
                status, response_headers, body = self._request(url, headers)
                if status == 304:
                    body = body_path.read_bytes()
                    if digest(body) != meta.get('sha256'):
                        raise OSError('Cache integrity failure')
                    self.stats['http304'] += 1
                    self.stats['cacheUnchanged'] += 1
                    return body
                if status != 200:
                    raise OSError('HTTP failure')
                sha = digest(body)
                if sha == meta.get('sha256'):
                    self.stats['cacheUnchanged'] += 1
                else:
                    body_path.write_bytes(body)
                json_write(meta_path,dict(url=url,etag=response_headers.get('etag'),lastModified=response_headers.get('last-modified'),sha256=sha,checkedAt=now()))
                return body
            except (OSError,ValueError):
                if attempt:
                    raise
        raise OSError('Fetch failed')


class FixtureClient:
    """Offline URL→relative HTML path manifest; never falls back to the network."""
    def __init__(self, manifest):
        self.base = Path(manifest).resolve().parent
        self.mapping = json.loads(Path(manifest).read_text())
        self.stats = dict(requestCount=0,http304=0,cacheUnchanged=0)

    def get(self, url):
        path = self.mapping.get(url)
        if not path:
            raise OSError('Fixture not available')
        return (self.base/path).read_bytes()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', required=True)
    parser.add_argument('--db', required=True)
    parser.add_argument('--cache', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--locations', help='Optional JSON object keyed by town, containing public location records')
    parser.add_argument('--source-id', help='Collect a single registered source; retain other stored events')
    parser.add_argument('--offline-fixtures', metavar='MANIFEST', help='Offline JSON mapping exact source URLs to HTML paths relative to manifest')
    parser.add_argument('--project-url', help='Public project URL included in HTTP User-Agent')
    args = parser.parse_args(argv)
    try:
        registry = json.loads(Path(args.registry).read_text())
        if args.source_id and args.source_id not in {s['id'] for s in registry['sources']}:
            raise ValueError('Unknown source id')
        locations = json.loads(Path(args.locations).read_text()) if args.locations else {}
        client = FixtureClient(args.offline_fixtures) if args.offline_fixtures else HTTPClient(args.cache)
        if args.project_url:
            if not safe_url(args.project_url):
                raise ValueError('Unsafe project URL')
            client.USER_AGENT = 'AdventCeskoPilot/1.0 (+' + args.project_url + ')'
        result = collect(registry,args.db,args.output,locations,client,args.source_id)
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except Exception:
        print(json.dumps({'status':'fatal','error':'Sběr nelze spustit nebo uložit; ověřte konfiguraci a místní oprávnění.'},ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
