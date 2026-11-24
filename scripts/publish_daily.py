"""Fail-closed, no-LLM seasonal publication. Success is intentionally silent."""
from datetime import date, datetime
from pathlib import Path
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


def in_season(day):
    return date(2026, 11, 12) <= day <= date(2026, 12, 24)


REMOTE = 'https://github.com/romanzdk/kam-na-advent.git'
PUBLIC = 'https://romanzdk.github.io/kam-na-advent/'
FILES = ('site/events.json', 'site/coverage.json', 'site/review.json')


def runtime_code():
    return hashlib.sha256(b''.join(p.name.encode()+p.read_bytes()
        for p in sorted(Path(__file__).parent.glob('*.py')))).hexdigest()


LOADED_CODE = runtime_code()


class PublicationError(RuntimeError):
    pass


def command(root, args, timeout=60):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GH_PROMPT_DISABLED='1')
    return subprocess.run(args, cwd=root, env=env, timeout=timeout, check=True,
                          capture_output=True, text=True).stdout.rstrip('\n')


def git(root, *args):
    return command(root, ['git', *args])


def remote_head(root):
    result = git(root, 'ls-remote', '--exit-code', 'origin', 'refs/heads/main').split()
    if len(result) != 2 or result[1] != 'refs/heads/main':
        raise PublicationError('remote-head')
    return result[0]


def atomic_private(path, data):
    tmp = path.with_suffix('.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(data, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def validate_projection(path):
    spec = importlib.util.spec_from_file_location('public_validator', Path(__file__).with_name('validate_public.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_directory(path, Path(path).parent/'data/sources.json')


def sync_preflight(root, head, upstream, verify):
    if runtime_code() != LOADED_CODE:
        raise PublicationError('reload-required')
    spec = importlib.util.spec_from_file_location('published_sync', Path(__file__).with_name('sync_published.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    baseline = module.documents(root)
    baseline['_commit'] = head
    fence = root/'private/published-base.json'
    if fence.exists():
        saved = json.loads(fence.read_text())
        if set(saved)!={'base'} or not re.fullmatch(r'[0-9a-f]{40}',saved['base']):
            raise PublicationError('sync-baseline')
        try:
            git(root, 'merge-base', '--is-ancestor', saved['base'], head)
            baseline = {Path(f).stem:json.loads(git(root,'show',saved['base']+':'+f)) for f in FILES}
            baseline['_commit'] = saved['base']
        except (subprocess.CalledProcessError,ValueError):
            raise PublicationError('sync-baseline') from None
    if upstream != head:
        git(root, 'fetch', 'origin', 'refs/heads/main')
        if git(root, 'rev-parse', 'FETCH_HEAD') != upstream:
            raise PublicationError('remote-head')
        try:
            git(root, 'merge-base', '--is-ancestor', head, upstream)
        except subprocess.CalledProcessError:
            raise PublicationError('divergence') from None
        changed_code = git(root, 'diff', '--name-only', head, upstream, '--', 'scripts')
        if not fence.exists():
            atomic_private(fence, {'base':head})
        git(root, 'merge', '--ff-only', upstream)
        if changed_code:
            raise PublicationError('reload-required')
    verify(root, upstream)
    if remote_head(root) != upstream or git(root, 'rev-parse', 'HEAD') != upstream:
        raise PublicationError('remote-head')
    if runtime_code() != LOADED_CODE:
        raise PublicationError('reload-required')
    if git(root, 'status', '--porcelain', '--untracked-files=all'):
        raise PublicationError('dirty-checkout')
    try:
        module.adopt_published(root, upstream, baseline=baseline)
    except module.SyncError as error:
        raise PublicationError(str(error)) from None
    fence.unlink(missing_ok=True)


def publish(root, *, today=None, remote=REMOTE, collect=None, validate=None, verify=None, reviewed_only=False):
    """Dependency overrides are for local tests only; the CLI exposes none."""
    if not in_season(today or datetime.now(ZoneInfo('Europe/Prague')).date()):
        return 'skipped'
    root = Path(root).resolve()
    private = root/'private'
    private.mkdir(mode=0o700, exist_ok=True)
    with (private/'publish.lock').open('a') as lock:
        os.fchmod(lock.fileno(), 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 'skipped'
        return _locked(root, remote, collect or collect_projection, validate or validate_projection,
                       verify or verify_deployment, reviewed_only=reviewed_only)


def _locked(root, remote, collect, validate, verify, *, reviewed_only=False):
    if git(root, 'branch', '--show-current') != 'main':
        raise PublicationError('branch')
    if git(root, 'remote', 'get-url', '--all', 'origin') != remote or git(root, 'remote', 'get-url', '--push', '--all', 'origin') != remote:
        raise PublicationError('remote')
    if git(root, 'status', '--porcelain', '--untracked-files=all'):
        raise PublicationError('dirty-checkout')
    head = git(root, 'rev-parse', 'HEAD')
    state = root/'private/publish-state.json'
    upstream = remote_head(root)
    if state.exists():
        pending = json.loads(state.read_text())
        if (set(pending) != {'head', 'base', 'remote'} or pending['head'] != head or
                pending['remote'] != remote or upstream not in (pending['base'], head) or
                git(root, 'rev-parse', 'HEAD^') != pending['base'] or
                not set(git(root, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').splitlines()) <= set(FILES)):
            raise PublicationError('pending-state')
        validate(root/'site')
        return _deliver(root, head, state, verify, upstream != head)
    sync_preflight(root, head, upstream, verify)
    base = upstream
    if reviewed_only:
        collect(root, reviewed_only=True)
    else:
        collect(root)
    changed = git(root, 'status', '--porcelain', '--untracked-files=all').splitlines()
    if any(line[:3] != ' M ' or line[3:] not in FILES for line in changed):
        raise PublicationError('collector-scope')
    validate(root/'site')
    if not git(root, 'status', '--porcelain'):
        return 'unchanged'
    git(root, 'add', '--', *FILES)
    git(root, 'commit', '-m', 'Update validated seasonal public data')
    head = git(root, 'rev-parse', 'HEAD')
    atomic_private(state, {'head': head, 'base': base, 'remote': remote})
    return _deliver(root, head, state, verify, True)


def _deliver(root, head, state, verify, push):
    if push:
        git(root, 'push', 'origin', 'HEAD:refs/heads/main')
    if remote_head(root) != head:
        raise PublicationError('remote-head')
    verify(root, head)
    # Only our fenced, deployment-verified delivery may acknowledge removals.
    atomic_private(root/'private/published-owned.json', {'head':head})
    state.unlink()
    return 'published'


def collect_projection(root, *, reviewed_only=False):
    settings = root/'private/reviewed-feed.json'
    feed_args = ['--reviewed-feed-config',str(settings)] if settings.exists() else []
    mode_args = ['--reviewed-only'] if reviewed_only else []
    output = command(root, [sys.executable, str(Path(__file__).with_name('collector.py')),
        '--registry', str(root/'data/sources.json'), '--db', str(root/'private/events.sqlite'),
        '--cache', str(root/'private/http-cache'), '--output', str(root/'site'),
        '--locations', str(root/'data/locations.json'), *feed_args, *mode_args], timeout=1800)
    atomic_private(root/'private/collector-last.json', json.loads(output))


def verify_deployment(root, head):
    """Require this commit's successful Pages workflow, then compare all public JSON."""
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        remaining = max(1, deadline - time.monotonic())
        runs = json.loads(command(root, ['gh', 'run', 'list', '--repo',
            'romanzdk/kam-na-advent', '--workflow', 'deploy.yml', '--commit', head,
            '--limit', '10', '--json', 'headSha,status,conclusion'], timeout=min(30, remaining)))
        matching = [run for run in runs if run['headSha'] == head]
        if matching and matching[0]['status'] == 'completed':
            if matching[0]['conclusion'] != 'success':
                raise PublicationError('pages-ci')
            try:
                for filename in FILES:
                    request = Request(PUBLIC + Path(filename).name + '?commit=' + head,
                                      headers={'Cache-Control':'no-cache'})
                    with urlopen(request, timeout=max(1, min(15, deadline-time.monotonic()))) as response:
                        actual = json.loads(response.read())
                    if actual != json.loads((root/filename).read_text()):
                        raise ValueError('public JSON mismatch')
                return
            except (OSError, ValueError):
                pass
        time.sleep(max(0, min(3, deadline-time.monotonic())))
    raise PublicationError('pages-readback-timeout')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', '--self-test', action='store_true', help='Read-only local readiness check; no Git/network/mutation')
    parser.add_argument('--reviewed-only', action='store_true', help='Refresh only reviewed public records; publish the full stored catalogue without a live-source crawl')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    if args.check:
        for filename in ('collector.py', 'validate_public.py', 'sync_published.py'):
            if not Path(__file__).with_name(filename).is_file():
                print(f'Chyba denní aktualizace (pripravenost): {PUBLIC}')
                return 1
        return 0
    try:
        if args.reviewed_only:
            publish(root, reviewed_only=True)
        else:
            publish(root)
        return 0
    except Exception as error:
        if (isinstance(error, PublicationError) and str(error) == 'reload-required'
                and os.environ.get('_ADVENT_PUBLISHER_RELOADED') != '1'):
            # The lock has unwound. Restart exactly once so code installed by a
            # fast-forward is loaded before any adoption/collection can run.
            arguments = list(sys.argv[1:] if argv is None else argv)
            try:
                os.execve(sys.executable, [sys.executable, str(Path(__file__).resolve()), *arguments],
                          dict(os.environ, _ADVENT_PUBLISHER_RELOADED='1'))
            except OSError:
                pass  # Keep the controlled error below; never loop on a failed exec.
        stage = str(error) if isinstance(error, PublicationError) else 'aktualizace'
        # Only controlled stage identifiers reach scheduler stdout; never subprocess output.
        if stage not in {'branch','remote','dirty-checkout','divergence','collector-scope',
                         'pending-state','remote-head','pages-ci','pages-readback-timeout',
                         'reload-required','sync-baseline','sync-schema','sync-validation','sync-owner',
                         'sync-conflict','sync-projection','sync-state-conflict','sync-review-owner',
                         'sync-review-conflict','sync-review-projection','sync-removal',
                         'sync-reviewed-snapshot','sync-reviewed-stale'}:
            stage = 'aktualizace'
        try:
            private = root/'private'; private.mkdir(mode=0o700, exist_ok=True)
            atomic_private(private/'publish-error.json', {'stage':stage, 'type':type(error).__name__,
                'at':datetime.now(ZoneInfo('Europe/Prague')).isoformat()})
        except OSError:
            pass
        print(f'Chyba denní aktualizace ({stage}): {PUBLIC}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
