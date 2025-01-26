// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2024, Tiny Tapeout LTD
// Author: Uri Shaked

export const presets = [
  {
    name: 'Hello World',
    source: 'https://github.com/MichaelBell/tinyQV-projects/blob/main/hello/main.c',
    baseUrl: 'https://tt.rebel-lion.uk/tt06-tinyqv/',
    files: [{ offset: 0, name: 'hello.bin' }],
  },
  {
    name: 'Micropython',
    source:
      'https://github.com/MichaelBell/micropython/tree/tinyQV/ports/tinyQV#using-tinyqv-micropython',
    baseUrl: 'https://tt.rebel-lion.uk/tt06-tinyqv/',
    files: [{ offset: 0, name: 'micropython20250126.bin' }],
  },
  {
    name: 'Coremark',
    source: 'https://github.com/MichaelBell/coremark',
    baseUrl: 'https://tt.rebel-lion.uk/tt06-tinyqv/',
    files: [{ offset: 0, name: 'coremark.bin' }],
  },
  {
    name: 'Digits of Pi',
    source: 'https://github.com/BrunoLevy/TinyPrograms/blob/main/pi.c',
    baseUrl: 'https://tt.rebel-lion.uk/tt06-tinyqv/',
    files: [{ offset: 0, name: 'pidigits.bin' }],
  },
];
