"""Exercise publication control flow with fake Git/GitHub commands; no writes."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
git() {
  printf 'git %s\n' "$*" >> "$CALL_LOG"
  if [[ "$1" == diff ]]; then return "$DIFF_STATUS"; fi
  if [[ "$1" == commit && "$FAIL_COMMIT" == 1 ]]; then return 17; fi
}
gh() {
  printf 'gh %s\n' "$*" >> "$CALL_LOG"
  if [[ "$1 $2" == 'pr create' ]]; then
    printf 'https://github.com/example/project/pull/1\n'
  fi
}
export -f git gh
source .github/scripts/publish-generated.sh
'''


class GeneratedPublicationTests(unittest.TestCase):
    def run_publication(self, diff_status, fail_commit=False):
        bash = shutil.which('bash')
        if os.name == 'nt':
            bash = 'C:/Program Files/Git/bin/bash.exe'
        self.assertTrue(bash and Path(bash).exists(), 'Bash is required for workflow verification')
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / 'calls.txt'
            env = dict(os.environ, GH_REPO='example/project', BASE_BRANCH='main',
                       UPDATE_KIND='snapshot', GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='2',
                       DIFF_STATUS=str(diff_status), FAIL_COMMIT=str(int(fail_commit)),
                       CALL_LOG=log.as_posix())
            result = subprocess.run([bash, '-c', HARNESS], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=15)
            calls = log.read_text() if log.exists() else ''
            return result, calls

    def test_no_changes_do_not_push_or_open_pr(self):
        result, calls = self.run_publication(0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls.strip(), 'git diff --cached --quiet')

    def test_updates_use_a_unique_branch_dispatch_and_gated_auto_merge(self):
        result, calls = self.run_publication(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('git push origin HEAD:refs/heads/automation/snapshot-123-2', calls)
        self.assertIn('gh pr create --repo example/project --base main', calls)
        self.assertIn('gh workflow run engineering.yml --repo example/project --ref automation/snapshot-123-2', calls)
        self.assertIn('--auto --squash', calls)
        self.assertNotIn('HEAD:main', calls)
        self.assertLess(calls.index('gh workflow run'), calls.index('gh pr merge'))

    def test_diff_failure_cannot_publish(self):
        result, calls = self.run_publication(128)
        self.assertEqual(result.returncode, 128)
        self.assertNotIn('push', calls)
        self.assertNotIn('gh ', calls)

    def test_commit_failure_cannot_push_or_merge(self):
        result, calls = self.run_publication(1, fail_commit=True)
        self.assertEqual(result.returncode, 17)
        self.assertNotIn('push', calls)
        self.assertNotIn('gh ', calls)
