"use strict";

const PRINTABLE_ASCII_SIZE = 0x5f;
const PRINTABLE_ASCII_OFFSET = 0x20;
const UINT32_INCREMENT = 0x9e3779b9;

/** Decode one printable-ASCII string from the payload's packed string table. */
function decodePackedString(seed, table, offset, length) {
  let decoded = "";

  for (let index = 0; index < length; index += 1) {
    seed = (seed + UINT32_INCREMENT) | 0;
    const key = ((seed ^ (seed >>> 13)) % PRINTABLE_ASCII_SIZE + PRINTABLE_ASCII_SIZE) % PRINTABLE_ASCII_SIZE;
    const encodedCode = table.charCodeAt(offset + index) - PRINTABLE_ASCII_OFFSET;
    const decodedCode = ((encodedCode - key) % PRINTABLE_ASCII_SIZE + PRINTABLE_ASCII_SIZE) % PRINTABLE_ASCII_SIZE;
    decoded += String.fromCharCode(decodedCode + PRINTABLE_ASCII_OFFSET);
  }

  return decoded;
}

module.exports = { decodePackedString };
