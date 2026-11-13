"""Durable SQLite outbox. Every acceptance is committed before HTTP acknowledgement."""
from contextlib import contextmanager
import fcntl
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import secrets
import sqlite3
import stat
import time

from .errors import APIError


def private_fd(path, flags=os.O_RDWR | os.O_CREAT):
    fd = os.open(path, flags | os.O_NOFOLLOW, 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.geteuid() or info.st_nlink != 1:
        os.close(fd)
        raise ValueError("state files must be private regular owner files")
    return fd


class Store:
    def __init__(self, state_dir, *, clock=time.time, minute_limit=10, day_limit=100):
        self.directory = Path(state_dir)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.geteuid():
            raise ValueError("state directory must be private and owner-controlled")
        self.path = self.directory / "outbox.sqlite3"
        self.clock = clock
        self.minute_limit, self.day_limit = minute_limit, day_limit
        with os.fdopen(private_fd(self.directory / "init.lock"), "r+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            key_path = self.directory / "challenge.key"
            try:
                fd = private_fd(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            except FileExistsError:
                pass
            else:
                with os.fdopen(fd, "wb") as f:
                    f.write(secrets.token_bytes(32))
                    f.flush()
                    os.fsync(f.fileno())
            with os.fdopen(private_fd(key_path, os.O_RDONLY), "rb") as f:
                self.key = f.read(33)
            if len(self.key) != 32:
                raise ValueError("invalid private challenge key")
            os.close(private_fd(self.path))
            with self.connection() as conn:
                conn.executescript('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, digest TEXT UNIQUE NOT NULL, payload TEXT NOT NULL,
                    status TEXT NOT NULL, created REAL NOT NULL, issue_url TEXT,
                    issue_title TEXT, issue_body TEXT, next_attempt REAL NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS aliases (
                    id TEXT PRIMARY KEY, digest TEXT NOT NULL, job_id TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS used_nonces (nonce TEXT PRIMARY KEY, expires REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS aliases_created ON aliases(created);
                ''')
            fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=3, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA synchronous=FULL")
        try:
            yield conn
        finally:
            conn.close()

    def challenge(self):
        text = float(self.clock()).hex() + "|" + secrets.token_hex(16)
        signature = hmac.new(self.key, text.encode(), hashlib.sha256).hexdigest()
        return text + "|" + signature

    def check_challenge(self, token):
        try:
            if not isinstance(token, str) or len(token) > 200:
                raise ValueError()
            issued, nonce, signature = token.split("|")
            expected = hmac.new(self.key, (issued + "|" + nonce).encode(), hashlib.sha256).hexdigest()
            timestamp = float.fromhex(issued)
            if (len(nonce) != 32 or not math.isfinite(timestamp)
                    or not hmac.compare_digest(signature, expected) or not 2 <= self.clock() - timestamp <= 1800):
                raise ValueError()
        except (ValueError, TypeError, OverflowError):
            raise APIError(400, "challenge", "Ověření vypršelo nebo není platné. Obnovte jej.") from None
        return nonce, timestamp + 1800

    @staticmethod
    def public(row):
        result = {"requestId": row["id"], "status": "uncertain" if row["status"] == "sending" else row["status"]}
        if row["issue_url"]:
            result["issueURL"] = row["issue_url"]
        return result

    def status(self, request_id):
        with self.connection() as conn:
            row = conn.execute("SELECT jobs.* FROM aliases JOIN jobs ON jobs.id=aliases.job_id WHERE aliases.id=?", (request_id,)).fetchone()
            if row is None:
                raise APIError(404, "not_found", "Podání nenalezeno.")
            return self.public(row)

    def retry(self, request_id, payload):
        """Read-only replay of an accepted alias; never accept a new ID here."""
        from .validation import validate
        with self.connection() as conn:
            existing = conn.execute("SELECT 1 FROM aliases WHERE id=?", (request_id,)).fetchone()
        if existing is None:
            return None
        # Canonical equality, not today's catalogue membership, decides a known-ID
        # retry. This synthetic identity is ONLY for normalization/comparison:
        # accept() still requires the exact durable digest before returning status.
        event_id = payload.get("eventId", "")
        replay_identity = {event_id: None} if isinstance(event_id, str) else {}
        canonical = validate(payload, replay_identity)
        return self.accept(request_id, canonical, None)

    def accept(self, request_id, payload, challenge):
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT * FROM aliases WHERE id=?", (request_id,)).fetchone()
            if existing:
                if existing["digest"] != digest:
                    raise APIError(409, "conflict", "Stejné ID již patří jinému podání.")
                row = conn.execute("SELECT * FROM jobs WHERE id=?", (existing["job_id"],)).fetchone()
                return 200, self.public(row)
            nonce, expires = self.check_challenge(challenge)
            if conn.execute("SELECT 1 FROM used_nonces WHERE nonce=?", (nonce,)).fetchone():
                raise APIError(400, "challenge", "Ověření již bylo použito. Obnovte jej.")
            now = self.clock()
            for period, limit in ((60, self.minute_limit), (86400, self.day_limit)):
                count = conn.execute("SELECT count(*) FROM aliases WHERE created>?", (now - period,)).fetchone()[0]
                if count >= limit:
                    raise APIError(429, "rate_limit", "Limit podání je vyčerpán. Zkuste to později.")
            row = conn.execute("SELECT * FROM jobs WHERE digest=?", (digest,)).fetchone()
            fresh = row is None
            if fresh:
                conn.execute("INSERT INTO jobs (id,digest,payload,status,created) VALUES (?,?,?,'pending',?)", (request_id, digest, encoded, self.clock()))
                row = conn.execute("SELECT * FROM jobs WHERE id=?", (request_id,)).fetchone()
            conn.execute("DELETE FROM used_nonces WHERE expires<?", (now,))
            conn.execute("INSERT INTO used_nonces VALUES (?,?)", (nonce, expires))
            conn.execute("INSERT INTO aliases VALUES (?,?,?,?)", (request_id, digest, row["id"], now))
            conn.commit()
            return (202 if fresh else 200), self.public(row)
