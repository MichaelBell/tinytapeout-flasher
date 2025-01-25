# TinyQV Programmer for TT06

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

TinyQV Programmer lets you connect to a [Tiny Tapeout](https://www.tinytapeout.com) 06 Demo Board and flash a binary file to the SPI Flash memory in the QSPI Pmod.  The QSPI Pmod has to be connected to the BIDIR (uio) Pmod port on the Tiny Tapeout board.

You can then interact with the program running on the TinyQV Risc-V SoC in the console. 

## Local Development

### Prerequisites

- [Node.js](https://nodejs.org/en/) (v18 or later) and npm (usually comes with Node.js)

### Instructions

1. Clone the repository
2. Run `npm install` to install dependencies
3. Run `npm start` to start the development server
4. Open [http://localhost:5173](http://localhost:5173) in your browser

Enjoy!

## License

Tiny Tapeout Flasher is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for more details.
