#!/usr/bin/env python3
"""Fail on foreign architecture, nonportable dylibs, or incomplete bundles."""
import json
from pathlib import Path
import plistlib
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def output(*args):
    return subprocess.check_output([str(a) for a in args], text=True).strip()


def version_tuple(s):
    return tuple(int(n) for n in s.split('.')) + (0,) * (3 - len(s.split('.')))


def verify(app):
    app = app.resolve()
    contents = app / 'Contents'
    info = plistlib.loads((contents / 'Info.plist').read_bytes())
    target = info['LSMinimumSystemVersion']
    binaries = list((contents / 'MacOS').iterdir()) + list((contents / 'Frameworks').glob('*.dylib'))
    if len(binaries) < 6:
        raise RuntimeError('Missing executable or bundled dependencies')
    for binary in binaries:
        if output('lipo', '-archs', binary) != 'arm64':
            raise RuntimeError(f'Not exclusively arm64: {binary}')
        commands = output('otool', '-l', binary)
        versions = re.findall(r'^\s*(?:minos|version) (\d+\.\d+(?:\.\d+)?)\s*$', commands, re.M)
        if not versions or any(version_tuple(v) > version_tuple(target) for v in versions):
            raise RuntimeError(f'OS target exceeds {target}: {binary}: {versions}')
        deps = [line.strip().split(' (')[0] for line in output('otool', '-L', binary).splitlines()[1:]]
        if binary.suffix == '.dylib':
            deps = deps[1:]
        for dep in deps:
            if dep.startswith(('/usr/lib/', '/System/Library/')):
                continue
            if dep.startswith('@loader_path/'):
                resolved = binary.parent / dep.removeprefix('@loader_path/')
            elif dep.startswith('@executable_path/'):
                resolved = contents / 'MacOS' / dep.removeprefix('@executable_path/')
            else:
                raise RuntimeError(f'Nonportable dependency: {binary}: {dep}')
            if not resolved.resolve().is_relative_to(app) or not resolved.is_file():
                raise RuntimeError(f'Missing bundle dependency: {dep}')
    resources = contents / 'Resources'
    for mod in ('default', 'fantasycore', 'empyrean_campaign'):
        if not (resources / 'mods' / mod / 'engine').is_dir():
            raise RuntimeError(f'Missing mod: {mod}')
    for file in ('COPYING', 'LICENSE.txt', 'BUILD-INFO.json', 'Flare.icns'):
        if not (resources / file).is_file():
            raise RuntimeError(f'Missing resource: {file}')
    output('codesign', '--verify', '--deep', '--strict', app)
    # Exercise the relocated binary and its dynamic-loader closure.
    version = subprocess.run([str(contents / 'MacOS/FlareLauncher'), '--version'],
                             capture_output=True, text=True, check=True)
    if 'Flare ' not in version.stdout + version.stderr:
        raise RuntimeError('Version smoke did not run')
    print(f'PASS: {len(binaries)} arm64 binaries, macOS {target}, portable dependencies and signature')


if __name__ == '__main__':
    verify(ROOT / 'dist/Flare.app')
