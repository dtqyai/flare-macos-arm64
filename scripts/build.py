#!/usr/bin/env python3
"""Build pinned dependencies and the checked-out Flare engine on Apple Silicon."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'
PREFIX = WORK / 'prefix'
CONFIG = json.loads((ROOT / 'build-config.json').read_text())


def run(*args):
    subprocess.run([str(x) for x in args], check=True)


def cmake(source, name, options, install=True):
    build = WORK / 'build' / name
    run('cmake', '-S', source, '-B', build,
        '-DCMAKE_POLICY_VERSION_MINIMUM=3.5',
        '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_OSX_ARCHITECTURES=arm64',
        '-DCMAKE_OSX_DEPLOYMENT_TARGET=' + CONFIG['minimum_macos'],
        '-DCMAKE_INSTALL_PREFIX=' + str(PREFIX),
        '-DCMAKE_PREFIX_PATH=' + str(PREFIX),
        '-DCMAKE_IGNORE_PREFIX_PATH=/opt/homebrew;/usr/local',
        '-DCMAKE_INSTALL_NAME_DIR=@rpath',
        '-DCMAKE_INSTALL_RPATH=@loader_path',
        '-DBUILD_SHARED_LIBS=ON', *options)
    run('cmake', '--build', build, '--parallel', str(min(os.cpu_count() or 3, 8)))
    if install:
        run('cmake', '--install', build)


def main():
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise SystemExit('Build requires a native Apple Silicon macOS machine.')
    deps = json.loads((ROOT / 'dependencies.json').read_text())
    archives = WORK / 'dependencies'
    archives.mkdir(parents=True, exist_ok=True)
    options = {
        'SDL': ['-DSDL_SHARED=ON', '-DSDL_STATIC=OFF', '-DSDL_TEST=OFF', '-DSDL_TESTS=OFF'],
        'SDL_image': ['-DSDL2IMAGE_SAMPLES=OFF', '-DSDL2IMAGE_TESTS=OFF',
                      '-DSDL2IMAGE_VENDORED=OFF', '-DSDL2IMAGE_BACKEND_STB=ON',
                      '-DSDL2IMAGE_BACKEND_IMAGEIO=OFF', '-DSDL2IMAGE_AVIF=OFF',
                      '-DSDL2IMAGE_JXL=OFF', '-DSDL2IMAGE_TIF=OFF', '-DSDL2IMAGE_WEBP=OFF'],
        'SDL_mixer': ['-DSDL2MIXER_SAMPLES=OFF', '-DSDL2MIXER_VENDORED=OFF',
                      '-DSDL2MIXER_VORBIS=STB', '-DSDL2MIXER_MOD=OFF',
                      '-DSDL2MIXER_MIDI=OFF', '-DSDL2MIXER_OPUS=OFF',
                      '-DSDL2MIXER_WAVPACK=OFF', '-DSDL2MIXER_GME=OFF', '-DSDL2MIXER_CMD=OFF'],
        'freetype': ['-DFT_DISABLE_ZLIB=ON', '-DFT_DISABLE_BZIP2=ON',
                     '-DFT_DISABLE_PNG=ON', '-DFT_DISABLE_HARFBUZZ=ON', '-DFT_DISABLE_BROTLI=ON'],
        'SDL_ttf': ['-DSDL2TTF_SAMPLES=OFF', '-DSDL2TTF_VENDORED=OFF', '-DSDL2TTF_HARFBUZZ=OFF'],
    }
    for dep in deps:
        archive = archives / (dep['name'] + '.tar.gz')
        if not archive.exists():
            temporary = archive.with_suffix('.download')
            run('curl', '--fail', '--location', '--retry', '3', dep['url'], '-o', temporary)
            temporary.rename(archive)
        with archive.open('rb') as f:
            actual = hashlib.file_digest(f, 'sha256').hexdigest()
        if actual != dep['sha256']:
            raise SystemExit(f"Checksum mismatch for {dep['name']}; remove {archive} and retry.")
        destination = archives / dep['name']
        destination.mkdir(exist_ok=True)
        with tarfile.open(archive) as tar:
            tar.extractall(destination, filter='data')
        sources = [p for p in destination.iterdir() if p.is_dir()]
        if len(sources) != 1:
            raise SystemExit(f'Expected one source directory in {destination}')
        cmake(sources[0], dep['name'], options[dep['name']])
    cmake(WORK / 'flare-engine', 'flare', [], install=False)


if __name__ == '__main__':
    main()
