import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_upstream
import publish
NAMES = ['Flare-AppleSilicon.zip', 'Flare-corresponding-source.tar.gz', 'BUILD-INFO.json', 'SHA256SUMS.txt']

def release(draft=False):
    return {'draft': draft, 'assets': [{'name': n, 'state': 'uploaded', 'size': 1} for n in NAMES]}

class ReleaseStateTests(unittest.TestCase):
    def test_complete_public_release_skips(self):
        self.assertTrue(check_upstream.release_complete(release()))
    def test_draft_is_retryable(self):
        self.assertFalse(check_upstream.release_complete(release(draft=True)))
    def test_missing_source_does_not_count_as_success(self):
        r = release(); r['assets'].pop(1)
        self.assertFalse(check_upstream.release_complete(r))
    def test_empty_or_pending_asset_does_not_count_as_success(self):
        for key, value in [('size', 0), ('state', 'new')]:
            r = release(); r['assets'][0][key] = value
            self.assertFalse(check_upstream.release_complete(r))
    def test_sha_must_be_full_hash(self):
        self.assertEqual(check_upstream.valid_sha('a' * 40), 'a' * 40)
        for value in ['main', 'a' * 39, 'a' * 40 + '\nbuild=false']:
            with self.assertRaises(ValueError): check_upstream.valid_sha(value)
    def check_main(self, final):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            env = {'GITHUB_REPOSITORY': 'owner/repo', 'GITHUB_OUTPUT': str(p/'out'), 'GITHUB_STEP_SUMMARY': str(p/'summary')}
            with patch.dict(os.environ, env), patch.object(check_upstream, 'api', side_effect=[{'sha': 'a'*40}, {'sha': 'b'*40}, final]), patch.object(check_upstream.subprocess, 'check_output', return_value='c'*40):
                check_upstream.main()
            return (p/'out').read_text()
    def test_api_not_found_builds(self):
        result = self.check_main(HTTPError('test', 404, 'not found', {}, None))
        self.assertIn('build=true', result)
        self.assertIn('tag=build-aaaaaaaaaaaa-bbbbbbbbbbbb-cccccccccccc', result)
    def test_api_forbidden_is_not_treated_as_missing(self):
        with self.assertRaises(HTTPError): self.check_main(HTTPError('test', 403, 'forbidden', {}, None))
    def test_published_snapshot_skips_in_main(self):
        self.assertIn('build=false', self.check_main(release()))

class ChecksumTests(unittest.TestCase):
    def test_corruption_and_missing_manifest_entries_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td); lines = []
            for name in NAMES[:-1]:
                (p/name).write_bytes(b'fixture-' + name.encode())
                digest = hashlib.sha256((p/name).read_bytes()).hexdigest()
                lines.append(f'{digest}  {name}\n')
            (p/'SHA256SUMS.txt').write_text(''.join(lines))
            publish.verify_hashes(p)
            (p/NAMES[0]).write_bytes(b'corrupt')
            with self.assertRaisesRegex(RuntimeError, 'Checksum mismatch'): publish.verify_hashes(p)
            (p/'SHA256SUMS.txt').write_text(''.join(lines[1:]))
            with self.assertRaisesRegex(RuntimeError, 'Incomplete'): publish.verify_hashes(p)
    def test_manifest_path_traversal_rejected_before_file_access(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td); (p/'SHA256SUMS.txt').write_text('a'*64 + '  ../../other\n')
            with self.assertRaisesRegex(RuntimeError, 'Incomplete'): publish.verify_hashes(p)

if __name__ == '__main__': unittest.main()
