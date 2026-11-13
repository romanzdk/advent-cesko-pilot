"""Private outbox worker. Never imported by the credential-free receiver."""
import fcntl
import json
import os
import re

from .errors import APIError
from .store import private_fd
from .validation import load_catalogue, render_issue, validate

REPO = "romanzdk/advent-cesko-pilot"
ISSUE_URL = re.compile(r"https://github\.com/romanzdk/advent-cesko-pilot/issues/([1-9][0-9]*)\Z")


class Worker:
    def __init__(self, store, catalogue, github):
        self.store, self.catalogue, self.github = store, catalogue, github

    def update(self, request_id, status, *, url=None):
        with self.store.connection() as conn:
            conn.execute("UPDATE jobs SET status=?,issue_url=?,next_attempt=? WHERE id=?",
                         (status, url, self.store.clock() + 60, request_id))

    def run_once(self):
        fd = private_fd(self.store.directory / "worker.lock")
        with os.fdopen(fd, "w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return 0
            with self.store.connection() as conn:
                rows = conn.execute("SELECT * FROM jobs WHERE status IN ('pending','sending','uncertain') AND next_attempt<=? ORDER BY next_attempt,created LIMIT 25", (self.store.clock(),)).fetchall()
            for row in rows:
                self.process(row)
            return len(rows)

    def process(self, row):
        request_id = row["id"]
        uncertain = row["status"] in {"sending", "uncertain"}
        if uncertain:
            # Reconciliation is read-only remote work against the journalled
            # original intent, not a new submission against today's catalogue.
            # Missing intent cannot safely be reconstructed after catalogue drift.
            title, body = row["issue_title"], row["issue_body"]
            self.update(request_id, "uncertain")
            if not isinstance(title, str) or not title or not isinstance(body, str) or not body:
                return
        else:
            try:
                events = load_catalogue(self.catalogue)
            except (OSError, ValueError, TypeError, KeyError):
                self.update(request_id, "pending")
                return
            try:
                payload = validate(json.loads(row["payload"]), events)
                title, body = render_issue(payload, events, request_id)
            except (APIError, ValueError, TypeError):
                self.update(request_id, "failed")
                return
        try:
            issues = self.github.list_issues()  # Complete successful enumeration or raise; never search-index absence.
            marker = "<!-- advent-feedback:" + request_id + " -->"
            found = [issue for issue in issues if marker in (issue.get("body") or "")]
            if len(found) > 1:
                self.update(request_id, "uncertain")
                return
            if not found and uncertain:
                # Empty reads cannot rule out eventual visibility or a late accepted request.
                self.update(request_id, "uncertain")
                return
            if found:
                uncertain = True
                with self.store.connection() as conn:
                    conn.execute("UPDATE jobs SET status='uncertain',issue_title=?,issue_body=? WHERE id=?", (title, body, request_id))
                target = found[0]
            else:
                with self.store.connection() as conn:
                    conn.execute("UPDATE jobs SET status='sending',issue_title=?,issue_body=? WHERE id=?", (title, body, request_id))
                uncertain = True  # Any subsequent exception may follow a remote write.
                target = self.github.create(title, body)
            number = target.get("number")
            if type(number) is not int or number < 1:
                raise ValueError("invalid issue number")
            verified = self.github.get(number)  # Exact target readback is mandatory.
            url = verified.get("html_url", "")
            if (verified.get("number") != number or verified.get("title") != title or verified.get("body") != body
                    or not isinstance(url, str) or not ISSUE_URL.fullmatch(url)
                    or url != "https://github.com/" + REPO + "/issues/" + str(number)
                    or "pull_request" in verified):
                self.update(request_id, "uncertain")
                return
            self.update(request_id, "submitted", url=url)
        except Exception:
            # Never print subprocess errors, returned data, auth information or user input.
            self.update(request_id, "uncertain" if uncertain else "pending")


def main(argv=None):
    import argparse
    import sys
    import time
    from .github_api import DEFAULT_GH, GitHub
    from .store import Store
    parser = argparse.ArgumentParser(description="Private fixed-repository outbox worker (no listener)")
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--catalogue", required=True, help="Fixed local site/events.json")
    parser.add_argument("--gh", default=os.environ.get("ADVENT_FEEDBACK_GH", DEFAULT_GH), help="Absolute trusted gh executable")
    parser.add_argument("--once", action="store_true", help="Drain one bounded batch then exit")
    args = parser.parse_args(argv)
    try:
        worker = Worker(Store(args.state_dir), args.catalogue, GitHub(args.gh))
        while True:
            processed = worker.run_once()
            if args.once:
                print(json.dumps({"processed": processed}), flush=True)
                return 0
            time.sleep(5)
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("Worker unavailable; queue retained.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
