// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2024, Tiny Tapeout LTD
// Author: Uri Shaked

export const presets = [
  {
    name: 'Hello World',
    source: 'https://github.com/MichaelBell/tinyQV-projects/blob/main/hello/main.c',
    baseUrl: 'https://tt.rebel-lion.uk/ttsky25a-tinyqv/',
    files: [{ offset: 0, name: 'hello.bin' }],
  },
  {
    name: 'Micropython',
    source:
      'https://github.com/MichaelBell/micropython/tree/tinyqv-sky25a/ports/tinyQV#using-tinyqv-micropython',
    baseUrl: 'https://tt.rebel-lion.uk/ttsky25a-tinyqv/',
    files: [{ offset: 0, name: 'micropython20260728.bin' }],
  },
  {
    name: 'Coremark',
    source: 'https://github.com/MichaelBell/coremark',
    baseUrl: 'https://tt.rebel-lion.uk/ttsky25a-tinyqv/',
    files: [{ offset: 0, name: 'coremark.bin' }],
  },
];
