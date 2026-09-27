#!/usr/bin/env python3
"""Resolve both upstream heads, and skip only a fully published matching build."""
import json
import os
import re
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def api(path):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'flare-macos-builder'}
    if os.environ.get('GH_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GH_TOKEN']
    with urlopen(Request('https://api.github.com/' + path, headers=headers), timeout=30) as r:
        return json.load(r)


def valid_sha(value):
    if not re.fullmatch(r'[0-9a-f]{40}', value):
        raise ValueError('Expected a full Git commit SHA')
    return value


def release_complete(release):
    expected = {'Flare-AppleSilicon.zip', 'Flare-corresponding-source.tar.gz',
                'BUILD-INFO.json', 'SHA256SUMS.txt'}
    uploaded = {a['name'] for a in release.get('assets', [])
                if a.get('state') == 'uploaded' and a.get('size', 0) > 0}
    return not release.get('draft', True) and expected <= uploaded


def main():
    repo = os.environ['GITHUB_REPOSITORY']
    engine = valid_sha(api('repos/flareteam/flare-engine/commits/master')['sha'])
    game = valid_sha(api('repos/flareteam/flare-game/commits/master')['sha'])
    builder = valid_sha(subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip())
    tag = f'build-{engine[:12]}-{game[:12]}-{builder[:12]}'
    build = True
    try:
        build = not release_complete(api(f'repos/{repo}/releases/tags/{tag}'))
    except HTTPError as e:
        if e.code != 404:
            raise
    values = dict(engine=engine, game=game, tag=tag, build=str(build).lower())
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        for key, value in values.items():
            f.write(f'{key}={value}\n')
    print(json.dumps(values, indent=2))
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
        f.write(f'Engine: `{engine}`\n\nGame: `{game}`\n\n')
        f.write('New build required.\n' if build else f'Already built: [{tag}](https://github.com/{repo}/releases/tag/{tag}).\n')


if __name__ == '__main__':
    main()
