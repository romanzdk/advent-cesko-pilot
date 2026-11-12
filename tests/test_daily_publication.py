"""Seasonal publisher tests; all Git writes are temporary and local."""
import contextlib
from datetime import date
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('publish_daily', ROOT/'scripts/publish_daily.py')
try:
    pub = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pub)
except FileNotFoundError:
    pub = None


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, text=True,
                          capture_output=True).stdout.strip()


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.remote = self.base/'remote.git'
        self.repo = self.base/'checkout'
        subprocess.run(['git','init','--bare',str(self.remote)], check=True, capture_output=True)
        subprocess.run(['git','init','-b','main',str(self.repo)], check=True, capture_output=True)
        git(self.repo,'config','user.name','Publisher Test')
        git(self.repo,'config','user.email','test@example.invalid')
        (self.repo/'site').mkdir()
        (self.repo/'.gitignore').write_text('private/\n')
        for name in ['events','coverage','review']:
            (self.repo/f'site/{name}.json').write_text('{}\n')
        git(self.repo,'add','.')
        git(self.repo,'commit','-m','Initial')
        git(self.repo,'remote','add','origin',str(self.remote))
        git(self.repo,'push','origin','main')
        self.verified = []
        self.collected = 0

    def collect(self, root):
        self.collected += 1
        for name in ['events','coverage','review']:
            (root/f'site/{name}.json').write_text(json.dumps({'version': 2})+'\n')

    def verify(self, root, commit):
        self.assertEqual(git(self.remote,'rev-parse','refs/heads/main'),commit)
        self.verified.append(commit)

    def run_publish(self, **kwargs):
        return pub.publish(self.repo, today=date(2026,11,12), remote=str(self.remote),
                           collect=self.collect, validate=lambda path: True,
                           verify=self.verify, **kwargs)

    def test_preflight_preserves_dirty_staged_unknown_branch_remote_and_divergence(self):
        for case in ['dirty', 'staged', 'unknown', 'branch', 'remote', 'diverged']:
            with self.subTest(case=case):
                if case == 'dirty': (self.repo/'site/events.json').write_text('user edit')
                if case == 'staged':
                    (self.repo/'site/events.json').write_text('user edit')
                    git(self.repo,'add','site/events.json')
                if case == 'unknown': (self.repo/'secret.txt').write_text('do not touch')
                if case == 'branch': git(self.repo,'checkout','-b','other')
                if case == 'remote': git(self.repo,'remote','set-url','origin',str(self.base/'wrong.git'))
                if case == 'diverged': git(self.repo,'commit','--allow-empty','-m','foreign')
                before = git(self.repo,'status','--porcelain')
                with self.assertRaises(pub.PublicationError): self.run_publish()
                self.assertEqual(self.collected,0)
                self.assertEqual(git(self.repo,'status','--porcelain'),before)
                # Restore only this test-owned disposable fixture.
                git(self.repo,'reset','--hard',git(self.remote,'rev-parse','refs/heads/main'))
                git(self.repo,'clean','-fd')
                git(self.repo,'checkout','main')
                git(self.repo,'remote','set-url','origin',str(self.remote))

    def test_collector_unrelated_write_is_never_staged(self):
        original = self.collect
        def bad(root):
            original(root)
            (root/'unrelated.txt').write_text('keep')
        with patch.object(self,'collect',bad):
            with self.assertRaises(pub.PublicationError): self.run_publish()
        self.assertEqual(git(self.repo,'diff','--cached','--name-only'),'')
        self.assertTrue((self.repo/'unrelated.txt').exists())

    def test_additional_push_remote_is_rejected(self):
        git(self.repo,'config','--add','remote.origin.pushurl',str(self.remote))
        git(self.repo,'config','--add','remote.origin.pushurl',str(self.base/'other.git'))
        with self.assertRaises(pub.PublicationError): self.run_publish()
        self.assertEqual(self.collected,0)

    def test_remote_readback_mismatch_retains_pending_commit(self):
        original = pub.remote_head
        calls = []
        def head(root):
            calls.append(1)
            return original(root) if len(calls)==1 else '0'*40
        with patch.object(pub,'remote_head',side_effect=head):
            with self.assertRaisesRegex(pub.PublicationError,'remote-head'): self.run_publish()
        self.assertTrue((self.repo/'private/publish-state.json').exists())
        self.assertEqual(self.verified,[])
        self.assertEqual(self.run_publish(),'published')
        self.assertEqual(self.collected,1)

    def test_real_validator_accepts_existing_public_projection_before_local_push(self):
        import shutil
        def collect(root):
            for filename in pub.FILES: shutil.copyfile(ROOT/filename,root/filename)
        self.assertEqual(pub.publish(self.repo,today=date(2026,11,12),remote=str(self.remote),
                                    collect=collect,verify=self.verify),'published')

    def test_pending_state_cannot_authorize_foreign_head(self):
        with patch.object(self,'verify',side_effect=RuntimeError('CI failed')):
            with self.assertRaises(Exception): self.run_publish()
        git(self.repo,'commit','--allow-empty','-m','foreign')
        with self.assertRaisesRegex(pub.PublicationError,'pending-state'): self.run_publish()
        self.assertEqual(self.collected,1)

    def test_collector_failure_never_stages(self):
        with patch.object(self,'collect',side_effect=RuntimeError('secret-token')):
            with self.assertRaises(Exception): self.run_publish()
        self.assertEqual(git(self.repo,'diff','--cached','--name-only'),'')
        self.assertEqual(self.verified,[])

    def test_push_failure_retries_only_owned_commit_with_private_state(self):
        hook = self.remote/'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n'); hook.chmod(0o700)
        with self.assertRaises(Exception): self.run_publish()
        head = git(self.repo,'rev-parse','HEAD')
        state = self.repo/'private/publish-state.json'
        self.assertTrue(state.exists(), 'failed push must retain ownership fence')
        self.assertEqual(state.stat().st_mode & 0o777, 0o600)
        hook.unlink()
        self.assertEqual(self.run_publish(),'published')
        self.assertEqual(self.collected,1)
        self.assertEqual(git(self.repo,'rev-parse','HEAD'),head)
        self.assertFalse(state.exists())

    def test_failed_verification_retains_state_and_retry_does_not_collect(self):
        with patch.object(self,'verify',side_effect=RuntimeError('CI failed')):
            with self.assertRaises(Exception): self.run_publish()
        self.assertTrue((self.repo/'private/publish-state.json').exists())
        self.assertEqual(self.run_publish(),'published')
        self.assertEqual(self.collected,1)

    def test_lock_skips_without_subprocess(self):
        import fcntl
        (self.repo/'private').mkdir()
        with (self.repo/'private/publish.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with patch.object(pub.subprocess,'run',side_effect=AssertionError('busy')):
                self.assertEqual(self.run_publish(),'skipped')

    def test_validation_failure_never_stages_or_pushes(self):
        initial = git(self.remote,'rev-parse','refs/heads/main')
        with patch.object(pub,'validate_projection',side_effect=ValueError('invalid')):
            with self.assertRaises(Exception):
                pub.publish(self.repo,today=date(2026,11,12),remote=str(self.remote),
                            collect=self.collect,verify=self.verify)
        self.assertEqual(git(self.repo,'diff','--cached','--name-only'),'')
        self.assertEqual(git(self.remote,'rev-parse','refs/heads/main'),initial)

    def test_collect_validate_commit_push_readback_then_nochange(self):
        self.assertEqual(self.run_publish(), 'published')
        self.assertEqual(self.collected, 1)
        self.assertEqual(self.verified, [git(self.repo,'rev-parse','HEAD')])
        self.assertEqual(set(git(self.repo,'diff-tree','--no-commit-id','--name-only','-r','HEAD').splitlines()), set(pub.FILES))
        self.assertEqual(self.run_publish(), 'unchanged')
        self.assertEqual(len(self.verified), 1)
        self.assertEqual(git(self.repo,'status','--porcelain'), '')


class ProductionBoundaryTests(unittest.TestCase):
    def test_check_is_silent_inert_and_has_no_date_override(self):
        with patch.object(pub.subprocess,'run',side_effect=AssertionError('network/process')):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(pub.main(['--check']),0)
            self.assertEqual(output.getvalue(),'')
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): pub.main(['--date','2026-11-12'])

    def test_collector_exact_arguments_timeout_and_private_capture(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            root = Path(directory); (root/'private').mkdir()
            with patch.object(pub,'command',return_value='{"metrics":{}}') as run:
                pub.collect_projection(root)
            args = run.call_args.args[1]
            self.assertIn('--locations',args)
            self.assertIn('--registry',args)
            self.assertEqual(run.call_args.kwargs['timeout'],600)
            self.assertEqual((root/'private/collector-last.json').stat().st_mode & 0o777,0o600)

    def test_deploy_success_requires_actions_and_all_public_json(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            root=Path(directory); (root/'site').mkdir()
            for name in ['events','coverage','review']: (root/f'site/{name}.json').write_text('{}')
            class Response:
                def __enter__(self): return self
                def __exit__(self,*args): pass
                def read(self): return b'{}'
            with patch.object(pub,'command',return_value=json.dumps([{'headSha':'a'*40,'status':'completed','conclusion':'success'}])), patch.object(pub,'urlopen',return_value=Response()) as get:
                pub.verify_deployment(root,'a'*40)
                self.assertEqual(get.call_count,3)
            with patch.object(pub,'command',return_value=json.dumps([{'headSha':'a'*40,'status':'completed','conclusion':'failure'}])):
                with self.assertRaises(pub.PublicationError): pub.verify_deployment(root,'a'*40)


class SeasonTests(unittest.TestCase):
    def test_inclusive_season_and_inert_outside(self):
        self.assertIsNotNone(pub, 'publisher module must exist')
        for day, expected in [(date(2026,11,11),False),(date(2026,11,12),True),
                              (date(2026,12,24),True),(date(2026,12,25),False),
                              (date(2027,11,12),False)]:
            self.assertEqual(pub.in_season(day), expected)
        with patch.object(pub.subprocess, 'run', side_effect=AssertionError('subprocess outside season')):
            self.assertEqual(pub.publish(Path('/nonexistent'), today=date(2026,12,25)), 'skipped')
