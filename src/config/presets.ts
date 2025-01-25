// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2024, Tiny Tapeout LTD
// Author: Uri Shaked

export const presets = [
  {
    name: 'Hello World',
    baseUrl: 'https://tt.rebel-lion.uk/tt06-tinyqv/',
    files: [{ offset: 0, name: 'hello.bin' }],
  },
  {
    name: 'Micropython',
    baseUrl: 'https://tt.rebel-lion.uk/tt06-tinyqv/',
    files: [{ offset: 0, name: 'micropython20250107.bin' }],
  },
  {
    name: 'Coremark',
    baseUrl: 'https://tt.rebel-lion.uk/tt06-tinyqv/',
    files: [{ offset: 0, name: 'coremark.bin' }],
  },
  {
    name: 'Digits of Pi',
    baseUrl: 'https://tt.rebel-lion.uk/tt06-tinyqv/',
    files: [{ offset: 0, name: 'pidigits.bin' }],
  },
];
