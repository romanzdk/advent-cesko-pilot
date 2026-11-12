# Frontend verification

Run from the repository root (Node 22+ recommended):

```sh
npm install --prefix tests-ui --no-save --package-lock=false
node --test tests-ui/helpers.test.mjs tests-ui/ui.test.mjs
```

`npm test --prefix tests-ui` is equivalent. Playwright is pinned to 1.58.2 in this directory, not the parent package. A compatible Chromium must be installed. On supported Linux environments, `tests-ui/node_modules/.bin/playwright install chromium` installs one. Alternatively set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` to an existing Chromium/headless-shell binary. Tests also discover existing cached Playwright headless shells if the pinned revision is missing.

## Isolation and scope

- Tests create a private browser and ephemeral loopback HTTP server, with contexts closed in `finally` and browser/server closed in the test teardown.
- The server reads only an explicit static-asset allowlist. It **never reads `site/events.json`**. Event responses are intercepted from synthetic inline fixtures; `example.cz` links are intentionally fictitious test content and are not followed.
- Tests exercise `/advent-mnichovice/` and `/`, MIME `nosniff`, a same-origin script CSP, keyboard interaction, 393/320/900/1440px widths, enlarged type, local download streams, map/library failures and HTTP/data failures.
- OSM tile requests are deliberately blocked. Leaflet itself, marker grouping, popups, keyboard selection, filtered marker updates and attribution are real browser behavior. This proves graceful degraded mode, **not live map-tile availability**.
- Browser timezone is deliberately America/Los_Angeles; Prague dates are explicit. No shared CDP, credentials, geocoding or deployment is involved.
- Screenshots `desktop-fixture.png` and `mobile-fixture.png` contain synthetic display events, not a verified event programme. The final screenshot test regenerates them.

## Observed vertical RED → GREEN cycles

Each behavior slice was tested and observed failing before its implementation; the complete suite was rerun after each green:

| Slice | Actual initial failure | Green behavior |
| --- | --- | --- |
| Default chronological season | `filterEvents` undefined | Dates sorted; unknown times after published times; original input untouched |
| Combined filters | Search still returned the unrelated event | Accent-insensitive search, town/type filters, overlapping multiday dates |
| Honest programme times | `timeLabel` undefined | Unknown start, published start and published range distinguished |
| Safe links / shared places | `safeHttps` undefined | HTTPS/no-credentials links; valid coordinates grouped |
| Calendar serialization | `eventIcs` undefined | Prague VTIMEZONE, CRLF/UTF-8 folding, escaped text, explicit estimated duration and unknown-time notes |
| Rendered season guide | `.event-card` missing | Ordered cards, metadata, audiences, sources and literal malicious text |
| Interactive filters | Result count never changed | Search/type/town/date combinations, empty state, reset, Prague weekend |
| Responsive composition | Mobile map incorrectly visible | Desktop split view, mobile tabs, 44px actions, no horizontal scroll |
| Real Leaflet integration | No map markers | Shared-place popups, keyboard activation, selected-card focus and filtered markers |
| Download/navigation | No download event | Downloaded chosen single-event ICS and precision-aware navigation |
| Loading/error recovery | No `.load-error` for unsupported schema | Busy/empty/error states, retry, HTTP failure and library-failure list fallback |
| Mobile polish | Input fonts were `12.8px` | 16px fields, single-line wordmark, keyboard skip link and touch-sized tablet reset |
| Overnight end | `DTEND` was on the start day before `DTSTART` | Published early-morning end exported on the following date |
| Default mobile select labels | `period` clipped at 393px | More room for the date preset, compact select padding, single-column filters on 320px screens |

Final execution: `npm test --prefix tests-ui` returned **16 tests, 16 pass, 0 fail, 0 skipped**. `node --check site/app.js` and `node --check site/helpers.js` also passed.

The first calendar implementation required a test correction to unfold RFC line continuations before matching semantic text; the 75-byte physical-line assertion remains separate. Prague midnight/DST boundary assertions supplement the filter slice. Screenshot/lazy-map checks verify the completed surface without adding production behavior.

## Design check

Primary surface: **Explore**. Warm paper/forest palette, Georgia editorial headings, deliberately compact humanist sans metadata, list rules instead of SaaS tiles, no external font or analytics. Visual audit found and fixed mobile wordmark wrapping and undersized input type. Anti-template check: no gradients, feature grid, accent rails, glass, oversized statistics, icon toppers or centered marketing hero.

## Remaining integration boundary

The parent task supplies the public schema-v1 `events.json`, validates real source accuracy and deploys the static `site/` directory. The frontend rejects malformed/duplicate essential event records, inserts event content through DOM text nodes, and accepts only credential-free HTTPS outbound URLs. No service worker is registered.
