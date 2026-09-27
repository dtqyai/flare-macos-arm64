#!/usr/bin/env python3
"""Create a relocatable, ad-hoc-signed app and its corresponding source archive."""
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import struct
import subprocess
import tarfile
import tempfile
from verify import verify

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'
DIST = ROOT / 'dist'
APP = DIST / 'Flare.app'
MAC = APP / 'Contents/MacOS'
LIB = APP / 'Contents/Frameworks'
RES = APP / 'Contents/Resources'
PREFIX = WORK / 'prefix'
CONFIG = json.loads((ROOT / 'build-config.json').read_text())


def run(*args):
    return subprocess.check_output([str(a) for a in args], text=True).strip()


def source_archive(meta):
    with tempfile.TemporaryDirectory(dir=WORK) as td:
        staging = Path(td)
        # Full engine source, including build files, matches the exact binary revision.
        subprocess.run(['git', '-C', str(WORK / 'flare-engine'), 'archive',
                        '--format=tar', '--output=' + str(staging / 'flare-engine.tar'),
                        meta['engine_commit']], check=True)
        subprocess.run(['git', '-C', str(ROOT), 'archive', '--format=tar',
                        '--output=' + str(staging / 'builder.tar'),
                        meta['builder_commit']], check=True)
        shutil.copy2(DIST / 'BUILD-INFO.json', staging)
        shutil.copytree(WORK / 'dependencies', staging / 'dependencies',
                        ignore=lambda path, names: [n for n in names if not n.endswith('.tar.gz')])
        with tarfile.open(DIST / 'Flare-corresponding-source.tar.gz', 'w:gz') as tar:
            tar.add(staging, arcname='Flare-source')


def main():
    if APP.exists():
        raise SystemExit('dist/Flare.app already exists. Use a fresh output directory for a new build.')
    for path in (MAC, LIB, RES):
        path.mkdir(parents=True, exist_ok=True)
    shutil.copy2(WORK / 'build/flare/flare', MAC / 'flare')
    target = CONFIG['minimum_macos']
    run('clang', '-arch', 'arm64', '-mmacosx-version-min=' + target, '-O2',
        ROOT / 'scripts/launcher.c', '-o', MAC / 'FlareLauncher')
    shutil.copytree(WORK / 'flare-engine/mods/default', RES / 'mods/default')
    for mod in ('fantasycore', 'empyrean_campaign'):
        shutil.copytree(WORK / 'flare-game/mods' / mod, RES / 'mods' / mod)
    shutil.copy2(WORK / 'flare-engine/mods/mods.txt', RES / 'mods/mods.txt')
    for repo, names in [('flare-engine', ['COPYING', 'CREDITS.engine.txt', 'README.engine.md']),
                        ('flare-game', ['LICENSE.txt', 'CREDITS.txt', 'README.md'])]:
        for name in names:
            shutil.copy2(WORK / repo / name, RES / name)
    queue, sources = [MAC / 'flare'], {}
    while queue:
        src = queue.pop(0)
        external = src.resolve().is_relative_to(PREFIX.resolve())
        dst = LIB / src.name if external else src
        if external:
            if dst.name in sources:
                if sources[dst.name] != src.resolve():
                    raise RuntimeError('Conflicting library basename: ' + dst.name)
                continue
            sources[dst.name] = src.resolve()
            shutil.copy2(src.resolve(), dst)
            dst.chmod(0o755)
        deps = [line.strip().split(' (')[0] for line in run('otool', '-L', src).splitlines()[1:]]
        if external:
            run('install_name_tool', '-id', '@rpath/' + dst.name, dst)
            deps = deps[1:]
        for dep in deps:
            if dep.startswith(('/usr/lib/', '/System/Library/')):
                continue
            if dep.startswith(('@rpath/', '@loader_path/')):
                candidate = PREFIX / 'lib' / dep.split('/', 1)[1]
            else:
                candidate = Path(dep)
            if not candidate.is_file() or not candidate.resolve().is_relative_to(PREFIX.resolve()):
                raise RuntimeError(f'Unexpected external dependency: {src}: {dep}')
            queue.append(candidate)
            prefix = '@loader_path/' if external else '@executable_path/../Frameworks/'
            run('install_name_tool', '-change', dep, prefix + candidate.name, dst)
    dependencies = json.loads((ROOT / 'dependencies.json').read_text())
    for dep in dependencies:
        src = next(p for p in (WORK / 'dependencies' / dep['name']).iterdir() if p.is_dir())
        for file in src.rglob('*'):
            if file.is_file() and re.match(r'^(LICENSE|COPYING|COPYRIGHT|NOTICE|OFL|FTL)', file.name, re.I):
                dest = RES / 'Licenses' / dep['name'] / file.relative_to(src)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dest)
    version_source = (WORK / 'flare-engine/src/Version.cpp').read_text()
    match = re.search(r'Version VersionInfo::ENGINE\((\d+),\s*(\d+),\s*(\d+)\)', version_source)
    if not match:
        raise RuntimeError('Cannot determine engine version')
    version = '.'.join(match.groups())
    info = dict(CFBundleName='Flare', CFBundleDisplayName='Flare', CFBundleExecutable='FlareLauncher',
                CFBundleIdentifier='org.flarerpg.flare.unofficial.arm64', CFBundlePackageType='APPL',
                CFBundleShortVersionString=version, CFBundleVersion=version,
                CFBundleIconFile='Flare.icns', LSMinimumSystemVersion=target,
                LSArchitecturePriority=['arm64'], NSHighResolutionCapable=True)
    (APP / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
    icon_parts = []
    for kind, size in [('icp4', 16), ('icp5', 32), ('icp6', 64), ('ic07', 128),
                       ('ic08', 256), ('ic09', 512), ('ic10', 1024)]:
        png = WORK / f'icon-{size}.png'
        run('sips', '-z', size, size, WORK / 'flare-engine/distribution/flare_logo_icon.png', '--out', png)
        data = png.read_bytes()
        icon_parts.append(kind.encode() + struct.pack('>I', len(data) + 8) + data)
    body = b''.join(icon_parts)
    (RES / 'Flare.icns').write_bytes(b'icns' + struct.pack('>I', len(body) + 8) + body)
    meta = dict(CONFIG, engine_version=version,
                engine_commit=run('git', '-C', WORK / 'flare-engine', 'rev-parse', 'HEAD'),
                game_commit=run('git', '-C', WORK / 'flare-game', 'rev-parse', 'HEAD'),
                builder_commit=run('git', '-C', ROOT, 'rev-parse', 'HEAD'),
                dependencies=dependencies, libraries=sorted(sources),
                compiler=run('clang', '--version'), cmake=run('cmake', '--version').splitlines()[0],
                sdk=run('xcrun', '--show-sdk-version'), signing='ad-hoc, not notarized')
    text = json.dumps(meta, indent=2) + '\n'
    (RES / 'BUILD-INFO.json').write_text(text)
    (DIST / 'BUILD-INFO.json').write_text(text)
    for binary in list(LIB.iterdir()) + [MAC / 'flare', MAC / 'FlareLauncher']:
        run('codesign', '--force', '--sign', '-', binary)
    run('codesign', '--force', '--sign', '-', APP)
    verify(APP)
    # Real codec smoke uses the libraries inside the bundle, not build-prefix copies.
    run('python3', ROOT / 'scripts/smoke_codecs.py', APP)
    run('ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', APP, DIST / 'Flare-AppleSilicon.zip')
    source_archive(meta)
    files = ['Flare-AppleSilicon.zip', 'Flare-corresponding-source.tar.gz', 'BUILD-INFO.json']
    with (DIST / 'SHA256SUMS.txt').open('w') as checksums:
        for name in files:
            with (DIST / name).open('rb') as f:
                digest = hashlib.file_digest(f, 'sha256').hexdigest()
            checksums.write(f'{digest}  {name}\n')
    print('Packaged app, corresponding source, metadata and checksums in dist/')


if __name__ == '__main__':
    main()
