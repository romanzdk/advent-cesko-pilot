# Verified factual excerpts (offline)

These are minimal reconstructions of event HTML fields / JSON-LD Event metadata, not full downloaded pages. Tests never need private captures or network access.

- `plasy-facts.json`: six official Plasy event URLs, exact primary titles (including **v Babiné**), dates/times, canonical localities, intended location keys and SHA-256 of the original research captures. `plasy-*.html` contains only their title, date, venue and a short factual programme excerpt.
- `kc-facts.json`: four KC Golf primary URLs, title/start/venue and original-capture SHA-256. `kc-*.html` preserves the published Event JSON-LD including named CZK Offers/AggregateOffer. Availability metadata is retained as parser input only; the collector must not assert ticket inventory.
- Evidence was captured and checked on 2026-11-12. Offline verification also checked all ten full private captures against those recorded hashes. Private raw captures are deliberately not dependencies of these tests.
- Approximate locality coordinates and public OSM references live in `data/locations.json`; they are not exact event venues.
- `../legacy-semily-source.json` is the former municipal Vismo source definition, used solely to keep the historical 18-detail parser regression portable. It is not a configured/live source and does not authorize fetching blocked municipal pages.
