#!/usr/bin/env python3
"""Upload to a draft first; publish only after remote asset hashes agree."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from check_upstream import api, release_complete
from urllib.error import HTTPError


def run(*args):
    subprocess.run([str(x) for x in args], check=True)


def verify_hashes(directory):
    lines = (directory / 'SHA256SUMS.txt').read_text().splitlines()
    expected = {'Flare-AppleSilicon.zip', 'Flare-corresponding-source.tar.gz', 'BUILD-INFO.json'}
    pairs = [line.split('  ', 1) for line in lines]
    if {name for _, name in pairs} != expected or len(pairs) != len(expected):
        raise RuntimeError('Incomplete or unexpected checksum manifest')
    for digest, name in pairs:
        with (directory / name).open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() != digest:
                raise RuntimeError('Checksum mismatch: ' + name)


def main():
    repo, tag = os.environ['GITHUB_REPOSITORY'], os.environ['RELEASE_TAG']
    dist = Path('dist')
    verify_hashes(dist)
    metadata = json.loads((dist / 'BUILD-INFO.json').read_text())
    notes = dist / 'release-notes.md'
    notes.write_text(
        'Unofficial Apple Silicon build of Flare: Empyrean Campaign.\n\n'
        f"Engine: `{metadata['engine_commit']}`\n\nGame: `{metadata['game_commit']}`\n\n"
        f"Builder: `{metadata['builder_commit']}`\n\n"
        f"Requires macOS {metadata['minimum_macos']} or later. Download **Flare-AppleSilicon.zip**, "
        'extract it, then open Flare.app. Runtime libraries are included.\n\n'
        'This is an upstream master snapshot, not an official stable release. '
        'The app is ad-hoc signed and is not Apple-notarized. '
        'Architecture, dependencies, signatures and real PNG/Ogg/font loading are checked; '
        'full gameplay is not automatically tested.\n\n'
        'Corresponding engine/dependency sources and build scripts are attached. '
        'Game asset attribution and licenses are included in the app.\n')
    try:
        release = api(f'repos/{repo}/releases/tags/{tag}')
    except HTTPError as e:
        if e.code != 404:
            raise
        release = None
    if release and release_complete(release):
        print('This snapshot is already published; leaving it unchanged.')
        return
    if release and not release.get('draft'):
        raise RuntimeError('Existing public release is incomplete; refusing to replace its assets')
    if not release:
        run('gh', 'release', 'create', tag, '--repo', repo, '--draft', '--prerelease',
            '--target', metadata['builder_commit'], '--title', 'Flare Apple Silicon — ' + tag,
            '--notes-file', notes)
    names = ['Flare-AppleSilicon.zip', 'Flare-corresponding-source.tar.gz', 'BUILD-INFO.json', 'SHA256SUMS.txt']
    run('gh', 'release', 'upload', tag, '--repo', repo, '--clobber', *(dist / n for n in names))
    with tempfile.TemporaryDirectory() as td:
        run('gh', 'release', 'download', tag, '--repo', repo, '--dir', td)
        verify_hashes(Path(td))
        if (Path(td) / 'SHA256SUMS.txt').read_bytes() != (dist / 'SHA256SUMS.txt').read_bytes():
            raise RuntimeError('Remote checksum manifest does not match local manifest')
    run('gh', 'release', 'edit', tag, '--repo', repo, '--draft=false', '--prerelease', '--notes-file', notes)
    if not release_complete(api(f'repos/{repo}/releases/tags/{tag}')):
        raise RuntimeError('Published release verification failed')
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
        f.write(f'[Download Apple Silicon build](https://github.com/{repo}/releases/tag/{tag})\n')


if __name__ == '__main__':
    main()
