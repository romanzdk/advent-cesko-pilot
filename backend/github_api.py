"""Private fixed-repository GitHub CLI transport. No shell, token extraction or credential copies."""
import json
import os
from pathlib import Path
import subprocess

REPO_PATH = "repos/romanzdk/advent-cesko-pilot/issues"
DEFAULT_GH = "/home/romanzdk/.local/bin/gh"


class GitHubUnavailable(Exception):
    pass


class GitHub:
    def __init__(self, executable=DEFAULT_GH, *, timeout=30, max_pages=100):
        if not Path(executable).is_absolute():
            raise ValueError("gh executable must be absolute")
        self.executable, self.timeout, self.max_pages = str(executable), timeout, max_pages
        # Existing gh auth is read only in this private child process. Never print captured stderr.
        self.environment = {key: value for key, value in os.environ.items()
                            if key in {"HOME", "GH_CONFIG_DIR", "GH_TOKEN", "GITHUB_TOKEN", "SSL_CERT_FILE", "SSL_CERT_DIR"}}
        self.environment.update({"PATH": "/usr/bin:/bin", "GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1", "GH_PAGER": "cat"})

    def _api(self, method, endpoint, payload=None):
        args = [self.executable, "api", "--hostname", "github.com", "--method", method, endpoint]
        data = None
        if payload is not None:
            args += ["--input", "-"]
            data = json.dumps(payload, ensure_ascii=False)
        try:
            completed = subprocess.run(args, input=data, text=True, capture_output=True,
                                       timeout=self.timeout, env=self.environment, check=False)
            if completed.returncode:
                raise GitHubUnavailable("GitHub unavailable")
            return json.loads(completed.stdout)
        except (OSError, subprocess.SubprocessError, ValueError):
            raise GitHubUnavailable("GitHub unavailable") from None

    def list_issues(self):
        issues = []
        for page in range(1, self.max_pages + 1):
            result = self._api("GET", REPO_PATH + "?state=all&per_page=100&page=" + str(page))
            if not isinstance(result, list) or any(not isinstance(issue, dict) for issue in result):
                raise GitHubUnavailable("Invalid enumeration")
            issues.extend(result)
            if len(result) < 100:
                return issues
        raise GitHubUnavailable("Enumeration incomplete")

    def create(self, title, body):
        return self._api("POST", REPO_PATH, {"title": title, "body": body, "labels": [], "assignees": []})

    def get(self, number):
        if type(number) is not int or number < 1:
            raise ValueError("invalid issue number")
        return self._api("GET", REPO_PATH + "/" + str(number))
