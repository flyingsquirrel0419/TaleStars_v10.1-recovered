"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const root = path.resolve(__dirname, "../..");
const outputRoot = path.join(root, "deobfuscated");

function walk(directory, prefix = "") {
  const files = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const relative = path.join(prefix, entry.name);
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...walk(full, relative));
    else if (entry.isFile()) files.push(relative);
  }
  return files;
}

function u32(buffer, offset) {
  return buffer.readUInt32LE(offset);
}

function asciiStrings(buffer, minimum = 4, limit = 200) {
  const strings = [];
  let start = -1;
  for (let index = 0; index < buffer.length; index += 1) {
    const byte = buffer[index];
    const printable = byte >= 0x20 && byte <= 0x7e;
    if (printable && start < 0) start = index;
    if ((!printable || index === buffer.length - 1) && start >= 0) {
      const end = printable && index === buffer.length - 1 ? index + 1 : index;
      if (end - start >= minimum) strings.push(buffer.toString("ascii", start, end));
      start = -1;
      if (strings.length >= limit) break;
    }
  }
  return strings;
}

function hashFile(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

function classifyMagic(buffer) {
  if (buffer.subarray(0, 4).equals(Buffer.from("glTF"))) return "glTF binary v2";
  if (buffer.subarray(0, 2).equals(Buffer.from("SC"))) return "Supercell SC resource";
  if (buffer.subarray(8, 12).equals(Buffer.from("SCTX"))) return "Supercell SCTX texture";
  if (buffer.subarray(0, 8).equals(Buffer.from("bplist00"))) return "Apple binary plist";
  if (buffer.subarray(0, 8).equals(Buffer.from("\x89PNG\r\n\x1a\n", "binary"))) return "PNG";
  if (buffer.subarray(0, 4).equals(Buffer.from("OggS"))) return "Ogg container";
  if (buffer.subarray(0, 4).equals(Buffer.from("\x00asm", "binary"))) return "WebAssembly";
  if (buffer.subarray(0, 4).equals(Buffer.from("PK\x03\x04", "binary"))) return "ZIP archive";
  if (buffer.readUInt32LE(0) === 0xfeedfacf || buffer.readUInt32BE(0) === 0xfeedfacf) return "Mach-O 64-bit";
  if (buffer.readUInt32LE(0) === 0xcffaedfe || buffer.readUInt32BE(0) === 0xcffaedfe) return "Mach-O 64-bit swapped";
  if (buffer.readUInt32BE(0) === 0xcafebabe || buffer.readUInt32LE(0) === 0xbebafeca) return "Mach-O fat binary";
  if (buffer.subarray(0, 4).equals(Buffer.from("RIFF"))) return "RIFF container";
  if (buffer.subarray(0, 4).equals(Buffer.from("ftyp"))) return "ISO base media";
  if (buffer.subarray(0, 4).equals(Buffer.from("\x1f\x8b\x08\x00", "binary"))) return "gzip";
  return "unknown binary";
}

function glbMetadata(buffer) {
  if (buffer.length < 12 || !buffer.subarray(0, 4).equals(Buffer.from("glTF"))) return null;
  const chunks = [];
  let offset = 12;
  while (offset + 8 <= buffer.length) {
    const length = u32(buffer, offset);
    const type = buffer.toString("ascii", offset + 4, offset + 8);
    chunks.push({ offset, length, type });
    if (length < 0 || offset + 8 + length > buffer.length) break;
    offset += 8 + length;
  }
  return { version: u32(buffer, 4), declaredLength: u32(buffer, 8), chunks };
}

function pngMetadata(buffer) {
  if (!buffer.subarray(0, 8).equals(Buffer.from("\x89PNG\r\n\x1a\n", "binary")) || buffer.length < 24) return null;
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20), colorType: buffer[25] };
}

function oggMetadata(buffer) {
  if (!buffer.subarray(0, 4).equals(Buffer.from("OggS"))) return null;
  let offset = 0;
  let pages = 0;
  let lastGranule = null;
  let codec = "unknown";
  while (offset + 27 <= buffer.length && buffer.subarray(offset, offset + 4).equals(Buffer.from("OggS"))) {
    const segmentCount = buffer[offset + 26];
    const tableEnd = offset + 27 + segmentCount;
    if (tableEnd > buffer.length) break;
    const payloadLength = buffer.subarray(offset + 27, tableEnd).reduce((sum, value) => sum + value, 0);
    const payloadStart = tableEnd;
    const payloadEnd = payloadStart + payloadLength;
    if (payloadEnd > buffer.length) break;
    const payload = buffer.subarray(payloadStart, payloadEnd);
    if (payload.includes(Buffer.from("OpusHead"))) codec = "Opus";
    if (payload.includes(Buffer.from("vorbis"))) codec = "Vorbis";
    lastGranule = buffer.readBigInt64LE(offset + 6).toString();
    pages += 1;
    offset = payloadEnd;
  }
  return { pages, codec, lastGranule };
}

function headerMetadata(buffer, kind) {
  const metadata = { kind, magic: buffer.subarray(0, 16).toString("hex") };
  if (kind === "Supercell SC resource" && buffer.length >= 16) {
    metadata.version = buffer.readUInt16LE(2);
    metadata.headerWords = buffer.readUInt32LE(4);
  }
  if (kind === "Supercell SCTX texture" && buffer.length >= 16) {
    metadata.headerSize = u32(buffer, 0);
    metadata.containerVersion = u32(buffer, 4);
  }
  if (kind === "unknown binary" && buffer.length >= 16) {
    metadata.littleEndianWords = [u32(buffer, 0), u32(buffer, 4), u32(buffer, 8), u32(buffer, 12)];
  }
  return metadata;
}

const originals = walk(root).filter((file) => !file.startsWith(`deobfuscated${path.sep}`));
const records = [];
const stringLines = [];
for (const relative of originals) {
  const full = path.join(root, relative);
  const size = fs.statSync(full).size;
  const sampleSize = Math.min(size, 1024 * 1024);
  const descriptor = fs.openSync(full, "r");
  const head = Buffer.alloc(sampleSize);
  fs.readSync(descriptor, head, 0, sampleSize, 0);
  fs.closeSync(descriptor);
  const kind = classifyMagic(head);
  const record = { path: relative, size, sha256: hashFile(full), kind };
  Object.assign(record, headerMetadata(head, kind));
  if (kind === "glTF binary v2") record.glb = glbMetadata(head);
  if (kind === "PNG") record.png = pngMetadata(head);
  if (kind === "Ogg container") record.ogg = oggMetadata(head);
  const strings = asciiStrings(head);
  if (strings.length > 0) {
    record.asciiStringCountInSample = strings.length;
    if (["Supercell SC resource", "Supercell SCTX texture", "glTF binary v2", "Mach-O 64-bit", "Mach-O fat binary", "unknown binary"].includes(kind)) {
      stringLines.push(`${relative}\t${strings.join("\t")}`);
    }
  }
  records.push(record);
}

records.sort((a, b) => a.path.localeCompare(b.path));
fs.writeFileSync(path.join(outputRoot, "binary-manifest.json"), JSON.stringify({ generatedAt: "2026-08-26", files: records }, null, 2) + "\n");
fs.writeFileSync(path.join(outputRoot, "binary-strings.tsv"), stringLines.join("\n") + "\n");
console.log(JSON.stringify({ files: records.length, stringRecords: stringLines.length }));
