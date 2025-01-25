// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2024, Tiny Tapeout LTD
// Author: Uri Shaked

import { createStore } from 'solid-js/store';
import { LineBreakTransformer } from '~/utils/LineBreakTransformer';
import ttRunTinyQV from './run_tinyqv.py?raw';

export interface ILogEntry {
  sent: boolean;
  text: string;
}

export type TerminalListener = (data: string) => void;

const MAX_LOG_ENTRIES = 1000;

export class TTBoardDevice extends EventTarget {
  private reader?: ReadableStreamDefaultReader<string>;
  private terminalReader?: ReadableStreamDefaultReader<string>;
  private readableStreamClosed?: Promise<void>;
  private writableStreamClosed?: Promise<void>;
  private writer?: WritableStreamDefaultWriter<string>;
  private binaryWriter?: WritableStreamDefaultWriter<Uint8Array>;

  private terminalDetachedPromise? = Promise.resolve();
  private terminalDetachedResolve?: () => void;
  get terminalDetached() {
    return this.terminalDetachedPromise;
  }

  readonly data;
  private terminalListener: TerminalListener | null = null;
  private setData;

  constructor(readonly port: SerialPort) {
    super();
    const [data, setData] = createStore({
      boot: false,
      version: null as string | null,
      flashId: null as string | null,
      logs: [] as ILogEntry[],
    });
    this.data = data;
    this.setData = setData;
  }

  async writeText(data: string) {
    if (this.binaryWriter) {
      this.binaryWriter.releaseLock();
      this.binaryWriter = undefined;
    }
    if (!this.writer) {
      const textEncoderStream = new TextEncoderStream();
      this.writer = textEncoderStream.writable.getWriter();
      this.writableStreamClosed = textEncoderStream.readable.pipeTo(this.port.writable);
    }
    await this.writer.write(data);
  }

  async writeBinary(data: Uint8Array) {
    if (this.writer) {
      await this.writer?.close();
      await this.writableStreamClosed;
      this.writer = undefined;
    }
    if (!this.binaryWriter) {
      this.binaryWriter = this.port.writable.getWriter();
    }
    await this.binaryWriter.write(data);
  }

  async attachTerminal(listener: TerminalListener) {
    this.terminalDetachedPromise = new Promise((resolve) => {
      this.terminalDetachedResolve = resolve;
    });
    this.terminalListener = listener;
  }

  async detachTerminal() {
    this.terminalListener = null;
    await this.writeText('\x03\x03'); // Send Ctrl+C twice to stop any running program.
    await this.writeText('\x01'); // Send Ctrl+A to enter RAW REPL mode.
    this.terminalDetachedResolve?.();
  }

  async terminalWrite(data: string) {
    await this.writeText(data);
  }

  private addLogEntry(entry: ILogEntry) {
    const newLogs = [...this.data.logs, entry];
    if (newLogs.length > MAX_LOG_ENTRIES) {
      newLogs.shift();
    }
    this.setData('logs', newLogs);
  }

  async sendCommand(command: string, log = true) {
    if (log) {
      this.addLogEntry({ text: command, sent: true });
    }
    await this.writeText(`${command}\x04`);
  }

  addLineListener(listener: (line: string) => void) {
    const abortController = new AbortController();
    this.addEventListener(
      'line',
      (e) => {
        listener((e as CustomEvent<string>).detail.trim());
      },
      { signal: abortController.signal },
    );
    return abortController;
  }

  async waitUntil(condition: (line: string) => boolean) {
    return new Promise<string>((resolve) => {
      const lineListener = this.addLineListener((line) => {
        if (condition(line)) {
          lineListener.abort();
          resolve(line);
        }
      });
    });
  }

  private processInput(line: string) {
    if (line.startsWith('BOOT: ')) {
      this.setData('boot', true);
      return;
    }

    this.dispatchEvent(new CustomEvent('line', { detail: line }));

    const [name, value] = line.split(/=(.+)/);
    switch (name) {
      case 'tt.sdk_version':
        this.setData('version', value.replace(/^release_v/, ''));
        break;

      case 'tt.flash_id':
        this.setData('flashId', value);
        break;
    }
  }

  async start() {
    void this.run();

    const textEncoderStream = new TextEncoderStream();
    this.writer = textEncoderStream.writable.getWriter();
    this.writableStreamClosed = textEncoderStream.readable.pipeTo(this.port.writable);

    // The following sequence tries to ensure clean reboot:
    // Send Ctrl+C twice to stop any running program,
    // followed by Ctrl+B to exit RAW REPL mode (if it was entered),
    // and finally Ctrl+D to soft reset the board.
    await this.writeText('\x03\x03\x02');
    await this.writeText('\x04');

    await this.waitUntil((line) => line.startsWith('MPY: soft reboot'));
    await new Promise((f) => setTimeout(f, 100));

    await this.writeText('\x03\x03');

    await this.writeText('\x01'); // Send Ctrl+A to enter RAW REPL mode.
    await this.writeText(ttRunTinyQV + '\x04'); // Send the run_tinyqv.py script and execute it.
  }

  async programFlash(
    offset: number,
    data: ArrayBufferLike,
    onProgress?: (written: number, total: number) => void,
  ) {
    const lineListener = this.addLineListener((line) => {
      if (line.startsWith('flash_prog=')) {
        const value = line.slice(11);
        if (value === 'ok') {
          onProgress?.(data.byteLength, data.byteLength);
        } else {
          const lastAddress = parseInt(value, 16);
          onProgress?.(lastAddress - offset, data.byteLength);
        }
      }
    });
    const waitForFlashProg = () => this.waitUntil((line) => line.startsWith('flash_prog='));

    try {
      const sectorSize = 4096;
      const fileData = new Uint8Array(data);
      const startOffset = `0x${offset.toString(16)}`;
      const flashProgPromise = waitForFlashProg();
      await this.sendCommand(`program_flash(${startOffset})`);
      await flashProgPromise;
      for (let i = 0; i < fileData.length; i += sectorSize) {
        // measured transport speed: 92kb/sec
        const sectorData = fileData.slice(i, i + sectorSize);
        await this.writeBinary(new TextEncoder().encode(`${sectorData.length}\r\n`));
        await this.writeBinary(sectorData);
        const response = await waitForFlashProg();
      }
      await this.writeBinary(new TextEncoder().encode(`0\r\n`));
      const response = await waitForFlashProg();

      await this.sendCommand(`run()`);
      await this.waitUntil((line) => line.startsWith('design='));
    } finally {
      lineListener.abort();
    }
  }

  private async run() {
    const { port } = this;

    function cleanupRawREPL(value: string) {
      /* eslint-disable no-control-regex */
      return (
        value
          // Remove the OK responses:
          .replace(/^(\x04+>OK)+\x04*/, '')
          // Remove ANSI escape codes:
          .replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '')
      );
      /* eslint-enable no-control-regex */
    }

    while (port.readable) {
      const textDecoder = new TextDecoderStream();
      this.readableStreamClosed = port.readable.pipeTo(textDecoder.writable);
      const [stream1, stream2] = textDecoder.readable.tee();
      this.reader = stream1
        .pipeThrough(new TransformStream(new LineBreakTransformer()))
        .getReader();

      this.terminalReader = stream2.getReader();
      this.processTerminalStream(this.terminalReader);

      try {
        // eslint-disable-next-line no-constant-condition
        while (true) {
          const { value, done } = await this.reader.read();
          if (done) {
            this.reader.releaseLock();
            return;
          }
          if (value && !this.terminalListener) {
            const cleanValue = cleanupRawREPL(value);
            this.processInput(cleanValue);
            this.addLogEntry({ text: cleanValue, sent: false });
          }
        }
      } catch (error) {
        console.error('SerialReader error:', error);
        this.dispatchEvent(new Event('close'));
      } finally {
        this.reader.releaseLock();
      }
    }
  }

  async processTerminalStream(reader: ReadableStreamDefaultReader<string>) {
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        reader.releaseLock();
        return;
      }
      if (value) {
        if (this.terminalListener) {
          this.terminalListener(value);
        }
      }
    }
  }

  async close() {
    await this.reader?.cancel();
    await this.terminalReader?.cancel();
    await this.readableStreamClosed?.catch(() => {});

    try {
      await this.writeText('\x03\x03\x02'); // Stop any running code and exit the RAW REPL mode.
    } catch (e) {
      console.warn('Failed to exit RAW REPL mode:', e);
    }

    await this.writer?.close();
    await this.writableStreamClosed?.catch(() => {});
    if (this.binaryWriter) {
      await this.binaryWriter.close();
    }

    await this.port.close();
    this.dispatchEvent(new Event('close'));
  }
}
