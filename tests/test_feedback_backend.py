"""Backend-only tests: generated public catalogue, real SQLite and loopback HTTP."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="advent-backend-test-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.catalogue = self.base / "site" / "events.json"
        self.catalogue.parent.mkdir()
        self.catalogue.write_text(json.dumps({"events": [{"id": "public-1", "title": "Trh", "town": "Praha", "date": "2026-12-01", "sourceUrl": "https://praha.eu/trh"}]}))
        self.now = [1800000000.0]

    def server(self, **kwargs):
        from backend.receiver import make_server
        server = make_server(state_dir=self.base / "state", catalogue=self.catalogue,
                             host="127.0.0.1", port=0, origins={"https://kamnaadvent.cz"},
                             clock=lambda: self.now[0], **kwargs)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.url = "http://127.0.0.1:" + str(server.server_address[1])
        return server

    def request(self, path, payload=None, origin="https://kamnaadvent.cz", method=None, headers=None):
        data = None if payload is None else json.dumps(payload).encode()
        h = {"Origin": origin}
        if data is not None:
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        req = urllib.request.Request(self.url + path, data=data, headers=h, method=method)
        try:
            response = urllib.request.urlopen(req, timeout=4)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, dict(response.headers), json.loads(response.read())

    def payload(self, **updates):
        import uuid
        code, _, challenge = self.request("/api/challenge")
        self.assertEqual(code, 200)
        self.now[0] += 2
        body = {"mode": "tip", "requestId": str(uuid.uuid4()), "challenge": challenge["challenge"],
                "website": "", "consent": True, "town": "Praha", "description": "Trh na náměstí"}
        body.update(updates)
        return body

    def test_submission_is_durable_idempotent_and_private(self):
        import stat
        import sqlite3
        server = self.server()
        payload = self.payload()
        code, _, result = self.request("/api/submissions", payload)
        self.assertEqual((code, result), (202, {"requestId": payload["requestId"], "status": "pending"}))
        self.assertEqual(self.request("/api/submissions", payload)[0], 200)
        # New Store instance proves committed SQLite durability, not an in-memory queue.
        from backend.store import Store
        reopened = Store(self.base / "state", clock=lambda: self.now[0])
        self.assertEqual(reopened.status(payload["requestId"]), result)
        code, _, polled = self.request("/api/submissions/" + payload["requestId"])
        self.assertEqual((code, polled), (200, result))
        self.assertNotIn("description", polled)
        changed = dict(payload, description="Jiná akce")
        self.assertEqual(self.request("/api/submissions", changed)[0], 409)
        duplicate = self.payload()
        self.assertEqual(self.request("/api/submissions", duplicate)[2], result)
        self.assertEqual(stat.S_IMODE((self.base / "state" / "challenge.key").stat().st_mode), 0o600)
        with sqlite3.connect(self.base / "state" / "outbox.sqlite3") as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM jobs").fetchone()[0], 1)

    def replace_catalogue(self, events):
        replacement = self.catalogue.with_suffix(".new")
        replacement.write_text(json.dumps({"events": events}))
        replacement.replace(self.catalogue)

    def test_receiver_refreshes_catalogue_after_atomic_addition_and_removal(self):
        self.server()
        self.replace_catalogue([{"id": "public-new", "title": "Nový trh"}])
        report = self.payload(mode="error", town="", eventId="public-new", errorKind="date")
        self.assertEqual(self.request("/api/submissions", report)[0], 202)
        removed = self.payload(mode="error", town="", eventId="public-1", errorKind="date")
        code, _, result = self.request("/api/submissions", removed)
        self.assertEqual((code, result["error"]), (400, "validation"))
        from backend.store import Store
        with Store(self.base / "state").connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM jobs").fetchone()[0], 1)

    def test_receiver_catalogue_failures_return_safe_503_without_stale_acceptance(self):
        self.server()
        report = self.payload(mode="error", town="", eventId="public-1", errorKind="date")
        broken = [None, "{", "[]", "{}", '{"events": null}', '{"events": [{}]}',
                  '{"events": [{"id": []}]}', '{"events": [{"id": "x"}, {"id": "x"}]}']
        for content in broken:
            with self.subTest(content=content):
                if content is None:
                    self.catalogue.unlink()
                else:
                    self.catalogue.write_text(content)
                code, _, result = self.request("/api/submissions", report)
                self.assertEqual((code, result["error"]), (503, "unavailable"))
                self.assertNotIn(str(self.catalogue), json.dumps(result))
        # An unavailable catalogue did not consume the challenge or create a job.
        self.replace_catalogue([{"id": "public-1", "title": "Obnovený trh"}])
        self.assertEqual(self.request("/api/submissions", report)[0], 202)

    def test_accepted_error_retries_survive_removed_or_unreadable_catalogue_only_for_same_alias_and_payload(self):
        import uuid
        from backend.store import Store
        self.server()
        report = self.payload(mode="error", town="", eventId="public-1", errorKind="date")
        self.assertEqual(self.request("/api/submissions", report)[0], 202)
        alias = self.payload(mode="error", town="", eventId="public-1", errorKind="date")
        self.assertEqual(self.request("/api/submissions", alias)[0], 200)
        self.replace_catalogue([])
        self.now[0] += 1801
        expected = {"requestId": report["requestId"], "status": "pending"}
        for retry in (report, alias):
            code, _, result = self.request("/api/submissions", retry)
            self.assertEqual((code, result), (200, expected))
        # A new ID is a new acceptance: removal must still invalidate the report.
        new_id = str(uuid.uuid4())
        self.assertEqual(self.request("/api/submissions", dict(report, requestId=new_id))[0], 400)
        for change in ({"description": "Different repair"}, {"eventId": "arbitrary-new-id"}):
            self.assertEqual(self.request("/api/submissions", dict(report, **change))[0], 409)
        for change in ({"consent": False}, {"website": "bot"}, {"unexpected": "x"}):
            self.assertEqual(self.request("/api/submissions", dict(report, **change))[0], 400)
        self.catalogue.unlink()
        store = Store(self.base / "state", clock=lambda: self.now[0])
        with store.connection() as conn:
            conn.execute("UPDATE jobs SET status='submitted',issue_url=? WHERE id=?",
                         ("https://github.com/romanzdk/advent-cesko-pilot/issues/7", report["requestId"]))
        expected = store.status(report["requestId"])
        for retry in (report, alias):
            code, _, result = self.request("/api/submissions", retry)
            self.assertEqual((code, result), (200, expected))
        self.assertEqual(self.request("/api/submissions", dict(report, requestId=new_id))[0], 503)
        self.assertEqual(self.request("/api/submissions/" + new_id)[0], 404)
        with store.connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM jobs").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM aliases").fetchone()[0], 2)

    def test_validation_modes_dates_urls_types_and_catalogue_identity(self):
        from backend.validation import load_catalogue, validate, render_issue
        from backend.errors import APIError
        catalogue = load_catalogue(self.catalogue)
        event = {"mode": "event", "consent": True, "title": "Advent", "town": "Praha",
                 "sourceURL": "https://praha.eu/program", "date": "2026-12-01"}
        self.assertEqual(validate(event, catalogue)["date"], "2026-12-01")
        unknown = dict(event, date="", dateUnknown=True)
        self.assertEqual(validate(unknown, catalogue)["startTime"], "")
        self.assertEqual(validate({"mode": "tip", "consent": True, "description": "Prověřte trh"}, catalogue)["mode"], "tip")
        error = {"mode": "error", "consent": True, "eventId": "public-1", "errorKind": "date", "description": "Jiný termín"}
        valid_error = validate(error, catalogue)
        title, body = render_issue(valid_error, catalogue, "123e4567-e89b-42d3-a456-426614174000")
        self.assertIn("Trh", body)
        self.assertIn("https://praha.eu/trh", body)
        self.assertIn("<!-- advent-feedback:123e4567-e89b-42d3-a456-426614174000 -->", body)
        bad = [dict(event, consent=False), dict(event, consent=1), dict(event, unexpected="x"),
               dict(event, title=""), dict(event, title="a" * 141), dict(event, town=3),
               dict(event, date="2026-02-30"), dict(event, date="2026-11-19"),
               dict(event, date="2026-12-25"), dict(event, endDate="2026-11-30"),
               dict(event, date=""), dict(event, dateUnknown="true"),
               dict(event, startTime="24:00"), dict(event, startTime="10:00", endTime="09:00"),
               dict(event, date="", dateUnknown=True, startTime="12:00"),
               dict(event, eventId="public-1"), dict(error, eventId="absent"),
               dict(error, title="Spoofed title"), dict(error, errorKind="location"),
               {"mode": "tip", "consent": True}, dict(event, description="a" * 1001)]
        urls = ["file:///etc/passwd", "https://user:pass@example.org/a", "http://127.0.0.1/",
                "http://[::1]/", "http://10.0.0.1/", "http://192.168.0.1/", "http://169.254.169.254/",
                "http://localhost/", "http://x.local/", "http://internal/", "http://2130706433/",
                "http://0177.0.0.1/", "http://0x7f000001/", "https://example.org/\u000a", "http://[::ffff:127.0.0.1]/"]
        bad += [dict(event, sourceURL=url) for url in urls]
        for item in bad:
            with self.subTest(item=item), self.assertRaises(APIError):
                validate(item, catalogue)
        attack = dict(event, title="＠safe @romanzdk", description="```\n@everyone\n<!-- advent-feedback:spoof -->\n```")
        title, body = render_issue(validate(attack, catalogue), catalogue, "123e4567-e89b-42d3-a456-426614174000")
        self.assertNotIn("@", title + body)
        self.assertTrue(body.endswith("<!-- advent-feedback:123e4567-e89b-42d3-a456-426614174000 -->"))
        self.server()
        invalid = self.payload(consent=False)
        code, _, response = self.request("/api/submissions", invalid)
        self.assertEqual((code, response["error"]), (400, "validation"))

    def test_error_identifiers_reject_padding_without_repairing_human_text(self):
        from backend.errors import APIError
        from backend.validation import load_catalogue, validate
        catalogue = load_catalogue(self.catalogue)
        report = {"mode": "error", "consent": True, "eventId": "public-1",
                  "errorKind": "date", "description": "  Jiný termín  "}
        self.assertEqual(validate(report, catalogue)["description"], "Jiný termín")
        for key in ("eventId", "errorKind"):
            for padded in (" " + report[key], report[key] + " ", "\u00a0" + report[key] + "\u00a0"):
                with self.subTest(key=key, value=padded):
                    with self.assertRaises(APIError) as caught:
                        validate(dict(report, **{key: padded}), catalogue)
                    self.assertEqual((caught.exception.code, caught.exception.error), (400, "validation"))

    def test_http_error_identifiers_reject_padding_before_acceptance(self):
        from backend.store import Store
        self.server()
        for key, value in (("eventId", "public-1"), ("errorKind", "date")):
            for padded in (" " + value, value + " ", "\u00a0" + value + "\u00a0"):
                with self.subTest(key=key, value=padded):
                    report = self.payload(mode="error", town="", eventId="public-1", errorKind="date")
                    report[key] = padded
                    code, _, result = self.request("/api/submissions", report)
                    self.assertEqual((code, result.get("error")), (400, "validation"))
        with Store(self.base / "state").connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM jobs").fetchone()[0], 0)
        report = self.payload(mode="error", town="", eventId="public-1", errorKind="date")
        self.assertEqual(self.request("/api/submissions", report)[0], 202)

    def test_all_full_form_fields_roundtrip_receiver_and_worker(self):
        from backend.store import Store
        from backend.worker import Worker
        self.server()
        fields = dict(title="Advent", town="Praha", venue="Náměstí", region="Hlavní město Praha",
                      category="trhy", date="2026-12-01", endDate="2026-12-02", startTime="17:00",
                      endTime="16:00", price="Dle pořadatele", registration="Předem\nza podmínek pořadatele",
                      registrationURL="https://praha.eu/registrace", audience="Rodiny", description="Program",
                      notes="Neověřená poznámka\nDruhý řádek", sourceURL="https://praha.eu/program")
        payload = self.payload(mode="event", **fields)
        code, _, response = self.request("/api/submissions", payload)
        self.assertEqual(code, 202, response)
        store = Store(self.base / "state", clock=lambda: self.now[0])
        remote = FakeGitHub()
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(payload["requestId"])["status"], "submitted")
        body = remote.issues[0]["body"]
        for key, value in fields.items():
            self.assertIn(key + ": " + value, body)
        self.assertIn("neověřené", body)

    def test_real_sqlite_legacy_canonical_hash_empty_extensions_and_retry_never_repost(self):
        import hashlib
        import uuid
        from backend.store import Store
        from backend.worker import Worker
        from backend.validation import validate, load_catalogue
        self.server()
        store = Store(self.base / "state", clock=lambda: self.now[0])
        # Literal output of the OLD validator, not generated by today's implementation.
        legacy = {"mode": "tip", "consent": True, "dateUnknown": False,
                  "title": "", "town": "Praha", "venue": "", "date": "", "endDate": "",
                  "startTime": "", "endTime": "", "price": "", "sourceURL": "",
                  "description": "Trh na náměstí", "eventId": "", "errorKind": ""}
        request_id = str(uuid.uuid4())
        token = store.challenge()
        self.now[0] += 2
        store.accept(request_id, legacy, token)
        encoded = json.dumps(legacy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        remote = FakeGitHub()
        Worker(store, self.catalogue, remote).run_once()
        expected = store.status(request_id)
        self.assertEqual(expected["status"], "submitted")
        self.now[0] += 1801
        self.catalogue.unlink()  # Accepted retry cannot depend on current catalogue.
        extension_blanks = dict(region="", category="", registration="  ", registrationURL="", audience="", notes="\n")
        for extensions in ({}, extension_blanks):
            payload = dict(legacy, requestId=request_id, challenge=token, website="", **extensions)
            code, _, result = self.request("/api/submissions", payload)
            self.assertEqual((code, result), (200, expected))
            self.assertEqual(validate(payload, {}), legacy)
        self.replace_catalogue([])
        duplicate = self.payload(**extension_blanks)
        self.assertEqual(self.request("/api/submissions", duplicate)[2], expected)
        Worker(Store(store.directory, clock=lambda: self.now[0]), self.catalogue, remote).run_once()
        self.assertEqual(remote.created, 1)
        with store.connection() as conn:
            row = conn.execute("SELECT digest,payload FROM jobs WHERE id=?", (request_id,)).fetchone()
            self.assertEqual(tuple(row), (digest, encoded))
            self.assertEqual(conn.execute("SELECT count(*) FROM jobs").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM aliases").fetchone()[0], 2)

    def test_full_field_schema_limits_enums_and_independent_receiver_worker_rejection(self):
        from backend.errors import APIError
        from backend.store import Store
        from backend.worker import Worker
        from backend.validation import validate, load_catalogue
        catalogue = load_catalogue(self.catalogue)
        proposal = {"mode": "event", "consent": True, "title": "Advent", "town": "Praha",
                    "date": "2026-12-01", "sourceURL": "https://praha.eu/program"}
        regions = ['Hlavní město Praha', 'Jihočeský kraj', 'Jihomoravský kraj', 'Karlovarský kraj',
                   'Kraj Vysočina', 'Královéhradecký kraj', 'Liberecký kraj', 'Moravskoslezský kraj',
                   'Olomoucký kraj', 'Pardubický kraj', 'Plzeňský kraj', 'Středočeský kraj',
                   'Ústecký kraj', 'Zlínský kraj']
        for region in regions:
            self.assertEqual(validate(dict(proposal, region=region), catalogue)["region"], region)
        for category in ("strom", "mikulas", "trhy", "tvoreni", "setkani", "betlem"):
            self.assertEqual(validate(dict(proposal, category=category), catalogue)["category"], category)
        limits = dict(title=100, town=100, venue=200, price=200, registration=500,
                      registrationURL=800, audience=200, description=1000, notes=1000, sourceURL=800)
        bad = []
        for key, limit in limits.items():
            prefix = "https://praha.eu/" if key.endswith("URL") else ""
            maximum = prefix + "a" * (limit - len(prefix))
            self.assertEqual(validate(dict(proposal, **{key: maximum}), catalogue)[key], maximum)
            bad.append(dict(proposal, **{key: maximum + "a"}))
            bad.append(dict(proposal, **{key: 1}))
        for key in ("region", "category"):
            for value in ("not-in-enum", " " + (regions[0] if key == "region" else "trhy"), [], None):
                bad.append(dict(proposal, **{key: value}))
        for key in ("registrationURL", "sourceURL"):
            for value in ("http://127.0.0.1/x", "https://user:secret@praha.eu/", "javascript:alert(1)", "https://praha.eu/\n"):
                bad.append(dict(proposal, **{key: value}))
        for key in ("registration", "notes", "audience"):
            bad.append(dict(proposal, **{key: "Hidden\u0000text"}))
        for key in ("region", "category", "registration", "registrationURL", "audience", "notes"):
            context = {"mode": "error", "consent": True, "eventId": "public-1", "errorKind": "other",
                       "description": "Oprava", key: {"region": regions[0], "category": "trhy",
                                                   "registrationURL": "https://praha.eu/"}.get(key, "Spoofed")}
            bad.append(context)
        self.server()
        for index, item in enumerate(bad):
            with self.subTest(index=index, fields=item):
                with self.assertRaises(APIError):
                    validate(item, catalogue)
                payload = self.payload(**item)
                self.assertEqual(self.request("/api/submissions", payload)[0], 400)
                store, request_id = self.queued("invalid-fields-" + str(index))
                with store.connection() as conn:
                    conn.execute("UPDATE jobs SET payload=? WHERE id=?", (json.dumps(item), request_id))
                remote = FakeGitHub()
                Worker(store, self.catalogue, remote).run_once()
                self.assertEqual(store.status(request_id)["status"], "failed")
                self.assertEqual(remote.calls, [])

    def test_current_form_date_time_semantics_without_fabricated_start(self):
        from backend.errors import APIError
        from backend.validation import validate, load_catalogue
        from backend.worker import Worker
        proposal = {"mode": "event", "consent": True, "title": "Advent", "town": "Praha",
                    "date": "2026-12-01", "sourceURL": "https://praha.eu/program"}
        catalogue = load_catalogue(self.catalogue)
        try:
            end_only = validate(dict(proposal, endTime="18:00"), catalogue)
        except APIError:
            self.fail("Known-date endTime alone must be accepted without inventing startTime")
        self.assertEqual((end_only["startTime"], end_only["endTime"]), ("", "18:00"))
        store, request_id = self.queued(payload=end_only)
        remote = FakeGitHub()
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(request_id)["status"], "submitted")
        self.assertNotIn("startTime:", remote.issues[0]["body"])
        self.assertIn("endTime: 18:00", remote.issues[0]["body"])
        for updates in ({"date": "2026-11-20", "endDate": "2026-12-31"},
                        {"date": "2026-12-24"}, {"startTime": "18:00", "endTime": "18:00"},
                        {"startTime": "23:00", "endTime": "01:00", "endDate": "2026-12-02"},
                        {"date": "", "dateUnknown": True}):
            validate(dict(proposal, **updates), catalogue)
        invalid: list[dict[str, object]] = [{"date": "2026-11-19", "endDate": "2026-12-01"},
                   {"endDate": "2027-01-01"}, {"date": "2026-12-25"}, {"endDate": "2026-11-30"},
                   {"date": "2026-02-30"}, {"date": "2026-12-1"},
                   {"date": "", "endTime": "18:00"}, {"startTime": "24:00"},
                   {"startTime": "18:00", "endTime": "17:59"},
                   {"startTime": "18:00", "endTime": "17:59", "endDate": "2026-12-01"}]
        for key in ("date", "endDate", "startTime", "endTime"):
            invalid.append({"date": "", "dateUnknown": True, key: {"date": "2026-12-01", "endDate": "2026-12-02",
                                                                   "startTime": "17:00", "endTime": "18:00"}[key]})
        for updates in invalid:
            with self.subTest(updates=updates), self.assertRaises(APIError):
                validate(dict(proposal, **updates), catalogue)

    def test_error_issue_uses_current_complete_catalogue_context_and_safe_permalink(self):
        from backend.validation import validate, load_catalogue
        from backend.worker import Worker
        report = {"mode": "error", "consent": True, "eventId": "public-1", "errorKind": "venue",
                  "description": "```\n@everyone <!-- advent-feedback:spoof -->\n```", "sourceURL": "https://praha.eu/correction"}
        store, request_id = self.queued(payload=report)
        event = {"id": "public-1", "title": "Aktuální @title", "town": "Praha", "venue": "Nové místo",
                 "region": "Hlavní město Praha", "category": "trhy", "date": "2026-12-03", "endDate": "2026-12-04",
                 "startTime": "12:00", "endTime": "15:00", "price": "Návrh ceny", "registration": "Neověřené podmínky",
                 "registrationUrl": "https://praha.eu/registrace", "audience": "všichni", "description": "Aktuální popis",
                 "notes": "Aktuální poznámky", "sourceUrl": "https://praha.eu/current", "status": "published",
                 "verifiedAt": "2026-11-12"}
        self.replace_catalogue([event])
        remote = FakeGitHub()
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(request_id)["status"], "submitted")
        body = remote.issues[0]["body"]
        self.assertIn("https://kamnaadvent.cz/#akce=public-1", body)
        for key, value in event.items():
            self.assertIn(key + ": " + value.replace("@", "＠"), body)
        self.assertNotIn("@", body)
        self.assertEqual(body.count("<!-- advent-feedback:"), 1)
        self.assertTrue(body.endswith("<!-- advent-feedback:" + request_id + " -->"))
        self.assertIn("neověřené", body)
        # No full browser context can replace the authoritative snapshot.
        from backend.errors import APIError
        with self.assertRaises(APIError):
            validate(dict(report, title="Fabricated"), load_catalogue(self.catalogue))

    def test_signed_challenge_age_expiry_one_use_honeypot_and_restart(self):
        import uuid
        self.server()
        first = self.payload()
        self.now[0] -= 2
        self.assertEqual(self.request("/api/submissions", first)[2]["error"], "challenge")
        self.now[0] += 2
        tampered = dict(first, challenge=first["challenge"] + "x")
        self.assertEqual(self.request("/api/submissions", tampered)[2]["error"], "challenge")
        self.assertEqual(self.request("/api/submissions", dict(first, website="bot"))[0], 400)
        self.assertEqual(self.request("/api/submissions", first)[0], 202)
        replay = dict(first, requestId=str(uuid.uuid4()), description="Different payload")
        self.assertEqual(self.request("/api/submissions", replay)[2]["error"], "challenge")
        expired = self.payload(description="Expired token")
        self.now[0] += 1801
        self.assertEqual(self.request("/api/submissions", expired)[2]["error"], "challenge")
        # Identical committed request may retry with an expired challenge, without a new cap.
        self.assertEqual(self.request("/api/submissions", first)[0], 200)
        from backend.store import Store
        reopened = Store(self.base / "state", clock=lambda: self.now[0])
        self.assertEqual(reopened.status(first["requestId"])["status"], "pending")
        code, _, missing = self.request("/api/submissions", {k: v for k, v in first.items() if k != "challenge"})
        self.assertEqual(code, 400)

    def test_global_rate_caps_are_durable_and_retry_does_not_consume(self):
        self.server(minute_limit=2, day_limit=3)
        first = self.payload(description="one")
        second = self.payload(description="two")
        self.assertEqual(self.request("/api/submissions", first)[0], 202)
        self.assertEqual(self.request("/api/submissions", first)[0], 200)
        self.assertEqual(self.request("/api/submissions", second)[0], 202)
        third = self.payload(description="three")
        self.assertEqual(self.request("/api/submissions", third)[0], 429)
        self.now[0] += 61
        self.assertEqual(self.request("/api/submissions", third)[0], 202)
        self.now[0] += 61
        fourth = self.payload(description="four")
        self.assertEqual(self.request("/api/submissions", fourth)[0], 429)
        from backend.store import Store
        from backend.errors import APIError
        from backend.validation import validate, load_catalogue
        reopened = Store(self.base / "state", clock=lambda: self.now[0], minute_limit=2, day_limit=3)
        with self.assertRaises(APIError) as caught:
            reopened.accept(fourth["requestId"], validate(fourth, load_catalogue(self.catalogue)), fourth["challenge"])
        self.assertEqual(caught.exception.code, 429)

    def test_http_boundary_rejects_foreign_origins_bad_json_routes_and_sizes(self):
        import http.client
        self.server(max_body=2048)
        code, headers, _ = self.request("/api/challenge", origin="https://evil.example")
        self.assertEqual(code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        for path in ("/", "/site/events.json", "/../backend/receiver.py", "/health?secret=x"):
            self.assertEqual(self.request(path)[0], 404)
            self.assertEqual(self.request(path, {})[0], 404)
        code, headers, _ = self.request("/api/submissions", method="OPTIONS", headers={"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        self.assertEqual(code, 200)
        self.assertEqual(headers["Access-Control-Allow-Methods"], "GET, POST, OPTIONS")
        self.assertNotIn("Access-Control-Allow-Credentials", headers)
        self.assertEqual(self.request("/api/submissions", method="OPTIONS", headers={"Access-Control-Request-Method": "DELETE"})[0], 403)
        host, port = "127.0.0.1", int(self.url.rsplit(":", 1)[1])
        cases = [(b"{", {"Content-Type": "application/json"}, 400),
                 (b'{"mode":"tip","mode":"event"}', {"Content-Type": "application/json"}, 400),
                 (b"[]", {"Content-Type": "application/json"}, 400),
                 (b"{}", {"Content-Type": "text/plain"}, 415),
                 (b"x" * 2049, {"Content-Type": "application/json"}, 413),
                 (b"{}", {"Content-Type": "application/json", "Content-Encoding": "gzip"}, 415)]
        for data, extra, expected in cases:
            with self.subTest(expected=expected, extra=extra):
                conn = http.client.HTTPConnection(host, port, timeout=3)
                conn.request("POST", "/api/submissions", data, {"Origin": "https://kamnaadvent.cz", **extra})
                response = conn.getresponse()
                self.assertEqual(response.status, expected)
                self.assertIn("error", json.loads(response.read()))
                conn.close()
        self.assertEqual(self.request("/health", method="DELETE")[0], 405)

    def test_http_slow_read_and_concurrency_are_bounded(self):
        import socket
        import time
        self.server(max_concurrency=1, read_timeout=0.2, request_timeout=0.5)
        port = int(self.url.rsplit(":", 1)[1])
        slow = socket.create_connection(("127.0.0.1", port), timeout=2)
        self.addCleanup(slow.close)
        slow.sendall(b"POST /api/submissions HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\nContent-Type: application/json\r\nOrigin: https://kamnaadvent.cz\r\n\r\n{")
        time.sleep(0.05)
        self.assertEqual(self.request("/health")[0], 503)
        time.sleep(0.6)
        self.assertEqual(self.request("/health")[0], 200)

    def test_worker_posts_then_exact_readback_before_submitted(self):
        from backend.store import Store
        from backend.worker import Worker
        self.server()
        payload = self.payload()
        self.assertEqual(self.request("/api/submissions", payload)[0], 202)
        store = Store(self.base / "state", clock=lambda: self.now[0])
        remote = FakeGitHub()
        worker = Worker(store, self.catalogue, remote)
        self.assertEqual(worker.run_once(), 1)
        status = self.request("/api/submissions/" + payload["requestId"])[2]
        self.assertEqual(status, {"requestId": payload["requestId"], "status": "submitted", "issueURL": "https://github.com/romanzdk/advent-cesko-pilot/issues/1"})
        self.assertEqual(remote.calls, ["list", "create", "get:1"])
        self.assertEqual(worker.run_once(), 0)
        self.assertEqual(remote.created, 1)
        self.assertIn("Anonymní", remote.issues[0]["body"])

    def queued(self, label="worker-state", payload=None):
        import uuid
        from backend.store import Store
        from backend.validation import load_catalogue, validate
        store = Store(self.base / label, clock=lambda: self.now[0])
        token = store.challenge()
        self.now[0] += 2
        request_id = str(uuid.uuid4())
        proposal = payload if payload is not None else {"mode": "tip", "consent": True, "town": "Praha"}
        store.accept(request_id, validate(proposal, load_catalogue(self.catalogue)), token)
        return store, request_id

    def test_worker_crash_after_create_reconciles_saved_exact_body_without_repost(self):
        from backend.worker import Worker
        from backend.store import Store
        store, request_id = self.queued()
        remote = FakeGitHub()
        create = remote.create
        def crash(title, body):
            create(title, body)
            raise SystemExit("simulated power loss after remote write")
        remote.create = crash
        with self.assertRaises(SystemExit):
            Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(request_id)["status"], "uncertain")
        remote.create = create
        reopened = Store(store.directory, clock=lambda: self.now[0])
        Worker(reopened, self.catalogue, remote).run_once()
        self.assertEqual(reopened.status(request_id)["status"], "submitted")
        self.assertEqual(remote.created, 1)

    def test_worker_uncertainty_never_replays_even_on_empty_or_failed_reads(self):
        from backend.worker import Worker
        store, request_id = self.queued()
        remote = FakeGitHub()
        real_get, real_list = remote.get, remote.list_issues
        def unavailable(*args):
            raise OSError("simulated provider outage")
        remote.get = unavailable
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(request_id)["status"], "uncertain")
        remote.get = real_get
        for list_method in (unavailable, lambda: []):
            self.now[0] += 61
            remote.list_issues = list_method
            Worker(store, self.catalogue, remote).run_once()
            self.assertEqual(store.status(request_id)["status"], "uncertain")
            self.assertEqual(remote.created, 1)
        self.now[0] += 61
        remote.list_issues = real_list
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(request_id)["status"], "submitted")
        self.assertEqual(remote.created, 1)

    def test_worker_crash_before_remote_create_stays_uncertain_not_blind_retried(self):
        from backend.worker import Worker
        store, request_id = self.queued()
        remote = FakeGitHub()
        create = remote.create
        def crash(*args):
            raise SystemExit("simulated crash after sending journal, before remote")
        remote.create = crash
        with self.assertRaises(SystemExit):
            Worker(store, self.catalogue, remote).run_once()
        remote.create = create
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(request_id)["status"], "uncertain")
        self.assertEqual(remote.created, 0)

    def test_worker_readback_mismatch_and_invalid_queue_fail_closed(self):
        from backend.worker import Worker
        store, request_id = self.queued()
        remote = FakeGitHub()
        get = remote.get
        remote.get = lambda n: dict(get(n), title="Different remote title")
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(request_id)["status"], "uncertain")
        self.assertNotIn("issueURL", store.status(request_id))
        invalid_store, invalid_id = self.queued("invalid-state")
        with invalid_store.connection() as conn:
            conn.execute("UPDATE jobs SET payload=? WHERE id=?", (json.dumps({"mode": "tip", "consent": False}), invalid_id))
        untouched = FakeGitHub()
        Worker(invalid_store, self.catalogue, untouched).run_once()
        self.assertEqual(invalid_store.status(invalid_id)["status"], "failed")
        self.assertEqual(untouched.calls, [])

    def test_worker_lock_prevents_concurrent_sender(self):
        import fcntl
        from backend.worker import Worker
        store, request_id = self.queued()
        remote = FakeGitHub()
        with open(store.directory / "worker.lock", "w") as lock:
            (store.directory / "worker.lock").chmod(0o600)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(Worker(store, self.catalogue, remote).run_once(), 0)
        self.assertEqual(remote.calls, [])
        self.assertEqual(Worker(store, self.catalogue, remote).run_once(), 1)
        self.assertEqual(store.status(request_id)["status"], "submitted")

    def test_worker_found_marker_read_failure_never_becomes_new_create(self):
        from backend.worker import Worker
        from backend.validation import load_catalogue, render_issue
        store, request_id = self.queued()
        remote = FakeGitHub()
        with store.connection() as conn:
            payload = json.loads(conn.execute("SELECT payload FROM jobs WHERE id=?", (request_id,)).fetchone()[0])
        title, body = render_issue(payload, load_catalogue(self.catalogue), request_id)
        remote.create(title, body)  # A previously visible issue is positive evidence of a remote effect.
        def unavailable(*args):
            raise OSError("readback unavailable")
        remote.get = unavailable
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(request_id)["status"], "uncertain")
        self.now[0] += 61
        remote.list_issues = lambda: []
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(remote.created, 1)

    def fake_gh(self):
        script = self.base / "fake-gh"
        script.write_text('#!' + sys.executable + '\n' + '''import json, pathlib, sys, os
base = pathlib.Path(__file__).parent
args = sys.argv[1:]
method = args[args.index("--method") + 1]
endpoint = args[args.index("--method") + 2]
state = base / "remote-issues.json"
issues = json.loads(state.read_text()) if state.exists() else []
data = json.load(sys.stdin) if "--input" in args else None
with (base / "gh-calls.jsonl").open("a") as f:
    f.write(json.dumps({"args": args, "input": data, "debug": os.environ.get("GH_DEBUG")}) + "\\n")
if method == "POST":
    issue = dict(data, number=len(issues)+1, html_url="https://github.com/romanzdk/advent-cesko-pilot/issues/" + str(len(issues)+1))
    issues.append(issue)
    state.write_text(json.dumps(issues))
    trigger = base / "kill-after-create"
    if trigger.exists():
        trigger.unlink()
        os.kill(os.getppid(), 9)  # Kill real worker process after durable simulated remote write.
    print(json.dumps(issue))
elif "?" in endpoint:
    print(json.dumps(issues))
else:
    print(json.dumps(issues[int(endpoint.rsplit("/", 1)[1])-1]))
''')
        script.chmod(0o700)
        return script

    def test_worker_cli_uses_fixed_gh_argv_and_private_subprocess_transport(self):
        import os
        import subprocess
        store, request_id = self.queued()
        script = self.fake_gh()
        result = subprocess.run([sys.executable, "-m", "backend.worker", "--state-dir", str(store.directory),
                                 "--catalogue", str(self.catalogue), "--gh", str(script), "--once"],
                                cwd=ROOT, env={**os.environ, "GH_DEBUG": "must-not-propagate", "GH_HOST": "evil.invalid"},
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(store.status(request_id)["status"], "submitted")
        calls = [json.loads(line) for line in (self.base / "gh-calls.jsonl").read_text().splitlines()]
        self.assertEqual(len(calls), 3)
        for call in calls:
            self.assertEqual(call["args"][:3], ["api", "--hostname", "github.com"])
            self.assertTrue(call["args"][5].startswith("repos/romanzdk/advent-cesko-pilot/issues"))
            self.assertIsNone(call["debug"])
        self.assertEqual(calls[1]["input"]["labels"], [])
        self.assertEqual(calls[1]["input"]["assignees"], [])
        self.assertNotIn("Anonymní", result.stdout + result.stderr)
        self.assertNotIn("must-not-propagate", result.stdout + result.stderr)

    def test_receiver_cli_is_runnable_and_serves_only_loopback(self):
        import select
        import subprocess
        process = subprocess.Popen([sys.executable, "-m", "backend.receiver", "--state-dir", str(self.base / "cli-state"),
                                    "--catalogue", str(self.catalogue), "--port", "0"], cwd=ROOT,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def stop():
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=4)
        self.addCleanup(stop)
        self.assertTrue(select.select([process.stdout], [], [], 4)[0], "receiver did not announce its bound socket")
        startup = json.loads(process.stdout.readline())
        self.assertEqual(startup["listening"], "127.0.0.1")
        self.url = "http://127.0.0.1:" + str(startup["port"])
        self.assertEqual(self.request("/health")[2], {"ok": True})
        self.assertFalse((self.base / "gh-calls.jsonl").exists())

    def test_state_rejects_unsafe_existing_permissions_and_symlinks(self):
        from backend.store import Store
        unsafe = self.base / "unsafe"
        unsafe.mkdir(mode=0o755)
        with self.assertRaises((ValueError, OSError)):
            Store(unsafe)
        safe = self.base / "safe"
        Store(safe)
        key = safe / "challenge.key"
        key.chmod(0o644)
        with self.assertRaises((ValueError, OSError)):
            Store(safe)
        key.chmod(0o600)
        db = safe / "outbox.sqlite3"
        db.unlink()
        db.symlink_to(self.catalogue)
        with self.assertRaises((ValueError, OSError)):
            Store(safe)

    def test_worker_cli_sigkill_after_provider_write_reconciles_on_restart(self):
        import os
        import subprocess
        store, request_id = self.queued()
        script = self.fake_gh()
        (self.base / "kill-after-create").touch()
        command = [sys.executable, "-m", "backend.worker", "--state-dir", str(store.directory),
                   "--catalogue", str(self.catalogue), "--gh", str(script), "--once"]
        first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(first.returncode, -9)
        self.assertEqual(store.status(request_id)["status"], "uncertain")
        second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(store.status(request_id)["status"], "submitted")
        self.assertEqual(len(json.loads((self.base / "remote-issues.json").read_text())), 1)
        calls = [json.loads(line) for line in (self.base / "gh-calls.jsonl").read_text().splitlines()]
        self.assertEqual(sum(call["args"][4] == "POST" for call in calls), 1)

    def assert_error_crash_reconciles_after_catalogue_change(self, change):
        import subprocess
        store, request_id = self.queued(payload={"mode": "error", "consent": True, "eventId": "public-1",
                                                 "errorKind": "date", "description": "Prosím opravit termín"})
        script = self.fake_gh()
        remote_state = self.base / "remote-issues.json"
        remote_state.write_text(json.dumps([{"number": 1, "title": "Unrelated", "body": "Unrelated issue",
                                           "html_url": "https://github.com/romanzdk/advent-cesko-pilot/issues/1"}]))
        (self.base / "kill-after-create").touch()
        command = [sys.executable, "-m", "backend.worker", "--state-dir", str(store.directory),
                   "--catalogue", str(self.catalogue), "--gh", str(script), "--once"]
        first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(first.returncode, -9)
        with store.connection() as conn:
            original = dict(conn.execute("SELECT * FROM jobs WHERE id=?", (request_id,)).fetchone())
        self.assertEqual(original["status"], "sending")
        self.assertIn("title: Trh", original["issue_body"])
        if change == "removed":
            self.replace_catalogue([])
        elif change == "renamed":
            self.replace_catalogue([{"id": "public-1", "title": "Přejmenovaný trh", "town": "Brno"}])
        else:
            self.catalogue.unlink()
        second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(store.status(request_id), {"requestId": request_id, "status": "submitted",
                         "issueURL": "https://github.com/romanzdk/advent-cesko-pilot/issues/2"})
        issues = json.loads(remote_state.read_text())
        self.assertEqual(len(issues), 2)
        self.assertEqual((issues[1]["title"], issues[1]["body"]), (original["issue_title"], original["issue_body"]))
        calls = [json.loads(line) for line in (self.base / "gh-calls.jsonl").read_text().splitlines()]
        self.assertEqual([call["args"][4] for call in calls], ["GET", "POST", "GET", "GET"])
        self.assertEqual(calls[-1]["args"][5], "repos/romanzdk/advent-cesko-pilot/issues/2")

    def test_worker_error_postcreate_crash_reconciles_after_event_removal(self):
        self.assert_error_crash_reconciles_after_catalogue_change("removed")

    def test_worker_error_postcreate_crash_reconciles_original_intent_after_event_rename(self):
        self.assert_error_crash_reconciles_after_catalogue_change("renamed")

    def test_worker_error_postcreate_crash_reconciles_without_readable_catalogue(self):
        self.assert_error_crash_reconciles_after_catalogue_change("unreadable")

    def test_worker_removed_event_uncertain_readback_mismatch_never_reposts(self):
        from backend.worker import Worker
        store, request_id = self.queued(payload={"mode": "error", "consent": True, "eventId": "public-1",
                                                 "errorKind": "date", "description": "Oprava data"})
        remote = FakeGitHub()
        original_get = remote.get
        remote.get = lambda number: dict(original_get(number), body="Changed remote body")
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(request_id)["status"], "uncertain")
        self.replace_catalogue([])
        self.now[0] += 61
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(request_id)["status"], "uncertain")
        self.assertNotIn("issueURL", store.status(request_id))
        self.assertEqual(remote.calls, ["list", "create", "get:1", "list", "get:1"])
        remote.get = original_get
        self.now[0] += 61
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(request_id)["status"], "submitted")
        self.assertEqual(remote.created, 1)

    def test_worker_uncertain_missing_original_intent_never_reconstructs_or_creates(self):
        from backend.worker import Worker
        for status in ("sending", "uncertain"):
            for missing in ("issue_title", "issue_body"):
                with self.subTest(status=status, missing=missing):
                    store, request_id = self.queued(status + "-" + missing)
                    with store.connection() as conn:
                        conn.execute("UPDATE jobs SET status=?,issue_title='forged',issue_body='forged' WHERE id=?",
                                     (status, request_id))
                        conn.execute("UPDATE jobs SET " + missing + "=NULL WHERE id=?", (request_id,))
                    remote = FakeGitHub()
                    Worker(store, self.catalogue, remote).run_once()
                    self.assertEqual(store.status(request_id)["status"], "uncertain")
                    self.assertEqual(remote.calls, [])

    def test_worker_pending_removed_event_cannot_use_saved_intent_to_bypass_validation(self):
        from backend.worker import Worker
        store, request_id = self.queued(payload={"mode": "error", "consent": True, "eventId": "public-1",
                                                 "errorKind": "date", "description": "Oprava data"})
        self.replace_catalogue([])
        with store.connection() as conn:
            conn.execute("UPDATE jobs SET issue_title=?,issue_body=? WHERE id=?",
                         ("@everyone forged", "@everyone forged", request_id))
        remote = FakeGitHub()
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(request_id)["status"], "failed")
        self.assertEqual(remote.calls, [])

    def test_worker_unreadable_catalogue_keeps_pending_until_authoritative_validation(self):
        from backend.worker import Worker
        store, request_id = self.queued()
        self.catalogue.unlink()
        remote = FakeGitHub()
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(request_id)["status"], "pending")
        self.assertEqual(remote.calls, [])
        self.replace_catalogue([])
        self.now[0] += 61
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(request_id)["status"], "submitted")
        self.assertEqual(remote.calls, ["list", "create", "get:1"])

    def test_failed_preflight_read_preserves_pending_and_never_creates(self):
        from backend.worker import Worker
        store, request_id = self.queued()
        remote = FakeGitHub()
        def unavailable():
            raise OSError("read failed: cannot infer absence")
        remote.list_issues = unavailable
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(request_id)["status"], "pending")
        self.assertEqual(remote.created, 0)

    def test_pending_job_cannot_override_worker_rendering_with_stored_intent(self):
        from backend.worker import Worker
        store, request_id = self.queued()
        with store.connection() as conn:
            conn.execute("UPDATE jobs SET issue_title=?,issue_body=? WHERE id=?",
                         ("@everyone untrusted title", "@everyone untrusted body", request_id))
        remote = FakeGitHub()
        Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(store.status(request_id)["status"], "submitted")
        self.assertNotIn("@", remote.issues[0]["title"] + remote.issues[0]["body"])
        self.assertIn("<!-- advent-feedback:" + request_id + " -->", remote.issues[0]["body"])

    def test_worker_rejects_symlink_lock_before_remote_calls(self):
        from backend.worker import Worker
        store, request_id = self.queued()
        (store.directory / "worker.lock").symlink_to(self.catalogue)
        remote = FakeGitHub()
        with self.assertRaises((ValueError, OSError)):
            Worker(store, self.catalogue, remote).run_once()
        self.assertEqual(remote.calls, [])

    def test_health_is_minimal_json_over_real_http(self):
        self.server()
        code, headers, body = self.request("/health")
        self.assertEqual((code, body), (200, {"ok": True}))
        self.assertEqual(headers["Access-Control-Allow-Origin"], "https://kamnaadvent.cz")
        self.assertEqual(headers["Cache-Control"], "no-store")


class FakeGitHub:
    """Explicit offline test double; no actual GitHub calls or credentials."""
    def __init__(self):
        self.issues = []
        self.calls = []
        self.created = 0

    def list_issues(self):
        self.calls.append("list")
        return list(self.issues)

    def create(self, title, body):
        self.calls.append("create")
        self.created += 1
        issue = {"number": self.created, "title": title, "body": body,
                 "html_url": "https://github.com/romanzdk/advent-cesko-pilot/issues/" + str(self.created)}
        self.issues.append(issue)
        return issue

    def get(self, number):
        self.calls.append("get:" + str(number))
        return dict(self.issues[number - 1])


if __name__ == "__main__":
    unittest.main()
