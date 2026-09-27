#!/usr/bin/env python3
"""Decode real PNG, Ogg and font resources using only bundled libraries."""
import ctypes as C
from pathlib import Path
import os
import sys


def main():
    app = Path(sys.argv[1]).resolve()
    lib = app / 'Contents/Frameworks'
    resources = app / 'Contents/Resources/mods'
    def load(name):
        matches = sorted(lib.glob(name))
        if len(matches) != 1:
            raise RuntimeError(f'Expected exactly one {name}, got {matches}')
        return C.CDLL(str(matches[0]))
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    sdl = load('libSDL2-*.dylib')
    img = load('libSDL2_image-*.dylib')
    mix = load('libSDL2_mixer-*.dylib')
    ttf = load('libSDL2_ttf-*.dylib')
    sdl.SDL_GetError.restype = C.c_char_p
    def check(value, label):
        if not value:
            raise RuntimeError(f'{label}: {sdl.SDL_GetError()}')
    check(sdl.SDL_Init(0x10) == 0, 'SDL_Init audio')
    check(mix.Mix_OpenAudio(44100, 0x8010, 2, 1024) == 0, 'Open dummy audio')
    img.IMG_Load.argtypes = [C.c_char_p]
    img.IMG_Load.restype = C.c_void_p
    sdl.SDL_FreeSurface.argtypes = [C.c_void_p]
    png = next(resources.rglob('*.png'))
    surface = img.IMG_Load(str(png).encode())
    check(surface, 'PNG decode')
    sdl.SDL_FreeSurface(surface)
    check(mix.Mix_Init(0x10) & 0x10, 'Ogg decoder init')
    mix.Mix_LoadMUS.argtypes = [C.c_char_p]
    mix.Mix_LoadMUS.restype = C.c_void_p
    mix.Mix_FreeMusic.argtypes = [C.c_void_p]
    music = mix.Mix_LoadMUS(str(next(resources.rglob('*.ogg'))).encode())
    check(music, 'Ogg load')
    mix.Mix_FreeMusic(music)
    check(ttf.TTF_Init() == 0, 'TTF_Init')
    ttf.TTF_OpenFont.argtypes = [C.c_char_p, C.c_int]
    ttf.TTF_OpenFont.restype = C.c_void_p
    ttf.TTF_CloseFont.argtypes = [C.c_void_p]
    font = ttf.TTF_OpenFont(str(next(resources.rglob('*.ttf'))).encode(), 18)
    check(font, 'Font load')
    ttf.TTF_CloseFont(font)
    ttf.TTF_Quit()
    mix.Mix_CloseAudio()
    mix.Mix_Quit()
    img.IMG_Quit()
    sdl.SDL_Quit()
    print('PASS: bundled SDL libraries load real PNG, Ogg and TTF game resources')


if __name__ == '__main__':
    main()
