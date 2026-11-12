# Deterministic event collector

Stdlib-only Python 3; no package installation or AI calls.

```sh
python -m unittest discover -s tests -v
python scripts/collector.py --help
python scripts/collector.py --registry data/sources.json --db private/events.sqlite --cache private/http-cache --output site --locations data/locations.json --project-url https://YOUR-PUBLIC-PROJECT-URL/
```

The parent owns `site/` and must execute publication/live passes. This implementation was exercised only against isolated temporary output and `private/evidence/collector-offline/public/`.

`--locations` accepts a JSON object keyed by exact town name, each value a public location record `{lat,lon,precision,label,sourceUrl}`. Omit the argument to leave locations null. `--source-id ID` refreshes one source while retaining stored others. Fatal setup/storage errors return 1; source outages produce coverage errors/partial status, preserve last good events and return 0.

`--offline-fixtures MANIFEST.json` accepts an object mapping **exact source URLs** to HTML paths relative to the manifest. Missing fixtures are honest source fetch failures; there is no network fallback. Existing real-fixture manifest and two executed passes are in `private/evidence/collector-offline/`.

## Behavior

- At most two index pages and 14 detail URLs per source. Actual same-host links are filtered by configured regex plus seasonal link label/title; newly discovered links precede bootstrap seeds. Stored detail URLs are retried within the same cap. Percent escapes remain unmodified.
- HTTPS only, robots checked per host, 1.05-second completion-to-next-request interval, 15-second timeout, 2 MiB response limit, at most two attempts per content GET. Same-host bounded redirects only. Cache metadata retains validators, exact original URL and SHA-256; 304 reuses hash-verified original bytes.
- Real JSON-LD Event is preferred; other JSON-LD types are ignored. Galileo date/venue selectors are scoped to `.event-detail`; Vismo to `#akce`/`#zahlavi`; Drupal to `main time[datetime]`; WordPress to article content, including observed Rajhrad `.content__inner` template with publication footer removed.
- Explicit event-body year is required. Missing, old, ambiguous, or conflicting dates enter review. Midnight placeholders remain unknown. Multi-day bounds carry a Czech non-continuous-opening note. Jilemnice programme start/end and separate lighting time are distinguished. Kuřim sister-site-only end times are deliberately **not** imported from the primary SKC detail.
- Known contradictory town/subvillage venue labels enter review. This is not a general geocoder; manual checks remain necessary for newly encountered neighboring towns.
- Descriptions are short title/venue metadata, not copied article prose. Public text is stripped of emails/local paths. Reviews expose only sanitized title, source URL and fixed Czech reason; errors never expose raw exceptions.
- SQLite stores stable URL-based identity, timestamp-free semantic fingerprints, raw-body hash observations and per-field provenance. Removed/unfetchable pages do not imply cancellation. Successfully fetched ambiguous revisions are withheld rather than keeping stale public dates; prior field observations remain privately preserved.
- Coverage always declares `complete:false` with an explicit Czech pilot limitation. Counts of stored source events may exceed cross-source/alias-deduplicated public count. Dedupe requires matching town, venue, date, title and start time; venue-less events are never merged.

## Known limits

No poster OCR, attachment extraction, Facebook, login, RSS date inference or AI fallback. RSS is not required for these six HTML-based sources. Bounded discovery is intentionally incomplete. HTML/template changes go to review, not guessed schedules. Test real-fixture cases require the existing private research captures. Set `--project-url` to the actual pilot URL before live collection; the default User-Agent contact points to the intended repository URL, not a verified deployed site.
