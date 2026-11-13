# Anonymous feedback receiver and private outbox

## Scope and trust boundaries

Pure Python 3.12+ standard library; SQLite on a **local filesystem**. No GitHub account is needed by the submitter. Acceptance is not a claim that an issue has been posted. Only the separate worker can contact GitHub, always in `romanzdk/advent-cesko-pilot`; it exposes no listening socket. The receiver never imports the GitHub transport, invokes `gh`, opens its auth configuration, or extracts a token.

No source URL is resolved or fetched. No uploads, cookies, GPS, names, email/contact fields, client-IP/XFF persistence, calendar changes, collector changes, automatic map insertion, labels or assignees. User prose can still contain personal information: the UI must explicitly warn against this and require public GitHub consent; moderation remains necessary.

**Before public exposure:** the parent must verify filesystem/process isolation, not just environment-variable removal. Running both processes as the same host user without a mount namespace would still let a compromised receiver reach that user's credential files. The receiver needs only its code/runtime, a read-only fixed public catalogue and the writable spool. It must not see `gh`, its auth/configuration, a private HOME, other repositories or private service sockets. The shared spool is not a credential store. Worker validation protects the privileged outbound boundary against malformed spool contents, but cannot establish that a human really consented if the receiver itself is compromised.

## Run locally (instructions, not an installed service)

Working directory must be the parent's stable immutable backend release directory, not a disposable worktree. These are development/integration examples only; the parent owns the sandbox/service configuration. The catalogue path below is the actual daily publisher's current public catalogue and must be mounted via its containing public directory so atomic replacement stays visible. Reuse the live ledger without reset:

```sh
# Development/integration invocation; NOT a substitute for the deployment sandbox.
env -i PATH=/usr/bin:/bin HOME=/nonexistent PYTHONDONTWRITEBYTECODE=1 \
  /usr/bin/python3 -m backend.receiver \
  --state-dir /home/romanzdk/.local/share/advent-feedback \
  --catalogue /home/romanzdk/projects/advent-cesko-pilot/site/events.json \
  --origin https://kamnaadvent.cz --port 8789

# Separate PRIVATE process, using the existing gh login; never copy its token.
/usr/bin/python3 -m backend.worker \
  --state-dir /home/romanzdk/.local/share/advent-feedback \
  --catalogue /home/romanzdk/projects/advent-cesko-pilot/site/events.json \
  --gh /home/romanzdk/.local/bin/gh

# Bounded single batch, suitable for a private systemd timer:
/usr/bin/python3 -m backend.worker \
  --state-dir /home/romanzdk/.local/share/advent-feedback \
  --catalogue /home/romanzdk/projects/advent-cesko-pilot/site/events.json \
  --gh /home/romanzdk/.local/bin/gh --once
```

The receiver binds **only `127.0.0.1`**, default port **8789**. `--port 0` is supported for tests; its sole startup output gives the actual bound port. It has no credential arguments or environment lookup. `--origin` is repeatable and replaces the default exact origin `https://kamnaadvent.cz`; use localhost origins only in tests. There is no wildcard CORS and no `Access-Control-Allow-Credentials`.

The worker's trusted executable is `--gh`, then `ADVENT_FEEDBACK_GH`, then `/home/romanzdk/.local/bin/gh`; relative executable paths are rejected. Repository and GitHub host cannot be configured. The worker uses fixed `gh api --hostname github.com --method ...` argument arrays, JSON over stdin, no shell, no `gh auth token`. Existing auth remains in the private worker's normal gh environment/configuration. It strips debug/host/pager overrides and captures, never prints, subprocess output/errors. Empty labels and assignees are explicit. Worker `--once` outputs only a processed-job count, **not** a submitted-job count.

### Parent deployment checklist

- Provision the state directory owner-only (`0700`), on local persistent storage, accessible to both processes under the deployment's chosen UID/mount setup. The key, DB and locks are `0600`; unsafe existing state permissions/symlinks are rejected. Do not expose or serve the state directory.
- Use a receiver mount/root namespace with only required Python/runtime/code, the one read-only catalogue and one writable state directory. No credential files, `gh` executable, user home, repository `.git`, private map/calendar data or other apps. Read-only code/catalogue and `NoNewPrivileges`, restrictive capabilities, `UMask=0077`, bounded tasks/memory, and safe logs. Explicitly test denial of credential/private file and socket access inside the actual receiver namespace. Catalogue mounts must expose atomic pathname replacement (for example, a read-only mount of a directory containing only public catalogue data); a single-file bind mount can pin the old inode indefinitely even when the application reopens its path.
- Preserve loopback reachability from the reverse proxy; a private network namespace without deliberate plumbing would break that. Limit receiver egress independently where possible. The worker may make outbound GitHub requests but must not listen. Do not grant it arbitrary executable/repository settings from the HTTP API.
- Receiver and worker share the same SQLite DB with standard SQLite locking, not a network filesystem. Use restart-on-failure. SIGTERM/SIGKILL may leave `sending`; the next worker reconciles it. Worker uses a process lock to exclude concurrent senders. Do not delete lock files while processes are running.
- Health is intentionally minimal and does **not** prove worker/GitHub availability. Monitor queue age/status and disk capacity privately, never by publishing submitted text or tokens.
- Only the parent may expose the new HTTPS Funnel listener `https://hermes.dory-geological.ts.net:10000`, after independent security review and sandbox verification. Existing private Tailscale Serve listeners **443/8443/9443/10443 must remain untouched**. No listener/Funnel/systemd changes were made by backend implementation.
- Parent must test one explicitly marked real public issue and exact readback, then close the test issue. Offline tests are not a claim of live GitHub delivery.

## API

All responses are JSON, `Cache-Control: no-store`, no cookies or submitted-field echoes. Routes are exact; queries, arbitrary files and extra routes are not accepted. Supplied `Origin` must exactly match a configured origin; POST/OPTIONS require it. CORS is browser policy, not bot authentication.

| Request | Response |
| --- | --- |
| `GET /health` | `200 {"ok":true}` |
| `GET /api/challenge` | `200 {"challenge":"opaque-signed-token"}` |
| `POST /api/submissions` | New job `202`, existing ID or canonical duplicate `200`, `{requestId,status,issueURL?,message?}` |
| `GET /api/submissions/<uuid>` | `200 {requestId,status,issueURL?,message?}`, or `404 {error,message}` |
| `OPTIONS` on API routes | Exact-origin/method/header preflight; GET, POST, OPTIONS; Content-Type only |

Statuses are `pending`, `submitted`, `failed`, `uncertain`. Internal durable `sending` is exposed as `uncertain`. Only a verified `submitted` record includes `issueURL`, exactly `https://github.com/romanzdk/advent-cesko-pilot/issues/N`. Status reads reveal no input fields or internal paths. Optional messages may be absent.

POST fields (unknown names rejected):

- `mode`: `event`, `tip`, `error`.
- `requestId`: canonical UUID, generated by `crypto.randomUUID()` and reused for retry of an identical proposal.
- `challenge`: signed challenge; fetch lazily when opening the form. `website`: empty honeypot. `consent`: strictly boolean `true`, explicitly confirming **public GitHub posting** and avoiding personal data.
- All 16 public form fields are supported: `title` ≤100, `town` ≤100, `venue` ≤200, `region`, `category`, `date`, `endDate`, `startTime`, `endTime`, `price` ≤200, `registration` ≤500, `registrationURL` ≤800, `audience` ≤200, `description` ≤1000, `notes` ≤1000, `sourceURL` ≤800. All are strings; omitted optional strings default empty except the six extensions described below. Notice **API `sourceURL` / `registrationURL`**, versus catalogue **`sourceUrl` / `registrationUrl`**.
- `region`: empty or exactly one of Hlavní město Praha, Jihočeský kraj, Jihomoravský kraj, Karlovarský kraj, Kraj Vysočina, Královéhradecký kraj, Liberecký kraj, Moravskoslezský kraj, Olomoucký kraj, Pardubický kraj, Plzeňský kraj, Středočeský kraj, Ústecký kraj, Zlínský kraj. `category`: empty or exactly `strom`, `mikulas`, `trhy`, `tvoreni`, `setkani`, `betlem`. Nonempty enum values must match literally; surrounding whitespace is not repaired.
- `date`, `endDate`: ISO civil dates or empty. `dateUnknown`: boolean, default false. Optional `startTime`, `endTime`: HH:MM or empty. Missing time stays unknown, not fabricated or implicitly all-day.
- `eventId`, `errorKind`: error mode only. Error kinds: `date`, `time`, `venue`, `cancelled`, `other`.

Event: title, town, public HTTP(S) source, plus date or explicit unknown-date flag. Tip: at least town, source or description. Error: existing catalogue ID, error kind, description, optional correction source. Event identity and current public form/status/verification context are rendered from the fixed public catalogue with its fixed `https://kamnaadvent.cz/#akce=<eventId>` permalink; nonempty browser-supplied error-context fields, including extensions, are rejected. Dates must be real ISO dates. Start is inclusive **20 November–24 December 2026**; end must be no earlier than start and no later than **31 December 2026**. A time needs a known start date; **end time alone is accepted without inventing start time**. When both times are known, same-day end must not precede start; overnight ordering needs an explicit later end date. Unknown date cannot carry any dates/times.

Source and registration URL validation rejects credentials, controls/whitespace, non-HTTP(S), local/private/reserved IPs, ambiguous numeric hosts and local/reserved hostname suffixes. It is **syntactic/offline**, not DNS verification: an otherwise public-looking domain may resolve privately or change later. The backend never dereferences it. Unicode/control input is constrained; description, registration conditions and notes permit tabs/newlines. Price, audience, registration conditions and all other visitor values remain unverified proposals, not new curated source facts.

Errors have `{error,message}` with Czech-safe, non-echoed messages. `400` `validation` keeps form values; `400` `challenge` permits safely refreshing the challenge. `409` `conflict`: same ID, different canonical proposal. `429` `rate_limit`: retry later. `503` `unavailable`: retain values and retry the same ID/payload, since a response can be lost after commit. HTTP framing errors also use JSON: malformed/duplicate JSON keys `400`, oversized body `413`, unsupported content type/encoding `415`, foreign origins `403`, unknown route `404`, disallowed method `405`.

Canonicalization preserves the original legacy fields/defaults, trims ordinary field boundaries and hashes the sorted normalized proposal. New optional extensions `region`, `category`, `registration`, `registrationURL`, `audience`, `notes` are **absent from canonical JSON when empty or omitted**; nonempty extensions participate in the digest. This preserves durable legacy payload bytes/hashes, same-ID retries and canonical deduplication without changing the schema or resetting state. Rendering uses optional lookups so old records stay readable. Transport fields challenge, honeypot and requestId are excluded. Same ID/payload retries neither reconsume the challenge nor count again. A recorded alias is checked before reading the current catalogue: a structurally valid, consented proposal must still match its durable canonical digest exactly. This returns its current status even if the referenced event has since been removed or the catalogue is unavailable; changed canonical content conflicts. The shortcut never creates a job/alias and never applies to an unknown ID. A new ID with a duplicate canonical proposal maps to the existing job and **returns its true requestId/status**; poll that returned ID. The new alias still needs current catalogue validation, a fresh valid challenge and counts as an acceptance against caps. Changing the payload behind any recorded alias conflicts.

Every new acceptance reopens the fixed authoritative catalogue pathname, so atomic daily replacements, including added and removed IDs, are visible without receiver restart. There is no stale-snapshot fallback: a missing, unreadable or malformed catalogue returns safe `503 unavailable` before challenge consumption or acceptance. Even a duplicate proposal under an unrecorded ID must pass this check; it cannot claim an existing job's status after its event was removed.

## Durability, bot limits, and outbound safety

- HMAC-SHA256 challenge using a locally generated private 32-byte key (`challenge.key`, 0600), random nonce, minimum age **2 seconds**, maximum age **30 minutes**, one use. Issuance itself is stateless; used nonces expire from the spool. Accepted identical-ID retries remain safe after challenge expiry.
- Durable global sliding-window caps: **10 acceptances/60 seconds, 100/86400 seconds**, across all clients. No claimed IP/XFF throttling. New UUID aliases also consume a cap, preventing unlimited dedupe-ledger growth by alias flooding. Nonce use, caps, dedupe and queue insert commit in one `BEGIN IMMEDIATE` transaction before acceptance is returned.
- Default body maximum **16 KiB**, at most **8** active request handlers, socket read timeout **5 seconds**, total connection deadline **10 seconds** (including headers/slow drips). No chunked/compressed request bodies, ambiguous content lengths, duplicate JSON keys, nonfinite JSON numbers or arbitrary file serving. Stdlib HTTP parser also bounds header/line sizes. Deploy behind the hardened HTTPS proxy, not directly on the Internet.
- These are **basic bot protections**, not strong anti-spam, identity verification or denial-of-service protection. Attackers can obtain fresh challenges and exhaust global capacity. Reverse-proxy/network controls, moderation and private queue/disk monitoring remain required.
- Private worker independently validates every **pending/pre-send** proposal against the explicitly supplied current local catalogue, reopening it before processing each pending job. A removed event fails validation before remote calls; an unavailable catalogue leaves pending work durable with backoff rather than treating an infrastructure outage as invalid input. Input is rendered as literal dynamically fenced text; mentions become fullwidth `＠`, user marker-like HTML is neutralized. Trusted notice: anonymous, unverified, pending manual review; never automatic map publication. Pending jobs ignore any saved title/body columns and must validate/render afresh; those columns cannot bypass validation or supply create content.
- Intended title/body and `sending` commit **before** create. A unique final body marker `<!-- advent-feedback:UUID -->` identifies each job. The worker enumerates all issue states via the repository REST endpoint (not eventually indexed search), then always reads the exact issue number and compares intended title, full body, number and fixed repository URL before marking submitted.
- A timeout, ambiguous create, process death or failed post-create read becomes `uncertain`. Restart reconciles `sending`/`uncertain` exact markers using only the original durable title/body snapshot for GET comparison, **without reading or validating against the current catalogue**. Thus deletion, renaming or unavailability of the referenced event cannot trap an already-created issue. Saved intent is never used as create input on this path: reconciliation performs only list/GET calls. Missing original intent remains uncertain without reconstruction. Multiple markers, mismatch or failed reads cannot establish success or absence. **Uncertain jobs are never automatically recreated, even after an empty successful listing.** This intentionally favors no duplicate public issues over delivery liveness. A crash just before remote create can therefore require private manual resolution.
- Pending preflight read failure stays pending with a 60-second retry delay, without creation. Already uncertain states remain uncertain with the same backoff. `failed` is used only for pre-send invalid queued input; remote failures are conservatively uncertain. No public message includes raw transport/provider errors.
- Enumeration is bounded to 100 pages × 100 issues; an incomplete scan fails closed and leaves the queue durable. A very large repository needs an operator-reviewed reconciliation strategy, never a blind retry.
- Ledger and intent are retained; do not delete/reset state or restore an old live outbox as a shortcut to retry. Old backups can forget an already issued remote write. Backups contain public proposals and operational metadata, not gh credentials, and must remain private. Key rotation invalidates outstanding challenges. Schema is initial v1; no migration from experimental schemas is promised.

## Verification

Current extension work used observed RED→GREEN slices: all-field HTTP submission returned `400` before extension support; a literal old canonical payload in real SQLite returned `409` on same-ID replay before blank extension omission; schema tests exposed oversized title, unknown/whitespace enum, unsafe registration URL and spoofed error-context acceptance; end-time-only submission was rejected and early-start/overlong-end dates were accepted before date/time fixes; current error rendering lacked the map permalink and extended catalogue context. Each targeted regression then passed. The backend suite also runs in the existing `python:3.12-slim` image with networking disabled, read-only repository/root and scratch-only writable state; this verifies runtime compatibility, not production isolation or live GitHub delivery. Tests use the active Python executable for both CLI subprocesses and the offline fake `gh`.

```sh
/usr/bin/python3 -m unittest discover -s tests -v
/usr/bin/python3 -m unittest discover -s tests -p test_feedback_backend.py -v
/usr/bin/python3 -m backend.receiver --help
/usr/bin/python3 -m backend.worker --help
```

Backend tests generate a minimal **public catalogue fixture** and fresh **real SQLite** state in temporary scratch directories; they do not read the project's production catalogue or private repository data. They exercise actual loopback HTTP, both real CLI processes, a local fake `gh` executable with fixed argv capture (no remote writes), crash/reconciliation boundaries including real worker **SIGKILL after simulated provider commit**, exact readback, idempotence/dedupe, validation/URL/season checks, honeypot/signatures/expiry, durable caps, CORS/body framing/size, concurrency/timeouts, worker exclusion and unsafe state rejection. The provider doubles are explicitly offline fixtures, not claimed GitHub execution.

Observed vertical RED→GREEN examples: missing health receiver → one passing real HTTP test; challenge route `404` → durable submission tests green; validation module absent → valid/invalid modes and rendering green; early challenge wrongly accepted / cap arguments absent → age/one-use/durable caps green; HTTP boundary limit arguments absent → bounded HTTP green; crash recovery left status uncertain instead of submitted and lock did not exclude → restart/lock tests green; found-marker read failure incorrectly returned pending → fixed durable uncertainty; unsafe 0755 state was accepted → private state rejection green. Final test count is reported by the execution output, not inferred here.

Catalogue lifecycle regressions were also observed before their fixes: an atomically added error-report event returned `400` rather than `202`; malformed replacement catalogues disconnected HTTP instead of returning safe `503`; a same-ID accepted error retry returned `400` after event removal instead of its existing status. Each targeted regression then passed after its corresponding change. Real local worker SIGKILL after the fake provider committed an error issue left it trapped `uncertain` after event removal, and restart exited unavailable when the catalogue disappeared; both now reconcile through the exact created issue GET with one POST total. The rename case already passed before this change and remains a preservation test for original title/body. Additional guards verify alias/digest boundaries, mismatched readback, missing original intent, pending validation and no saved-intent create bypass. These are offline tests only.
