#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { toObject } = require("/tmp/flatbuffers-js/node_modules/flatbuffers/js/flexbuffers.js");

const root = path.resolve(process.argv[2] || ".");
const source = path.resolve(process.argv[3] || "res/csv_client/particle_emitters.json.flex");
const output = path.resolve(process.argv[4] || "deobfuscated/decoded/particle_emitters.json");
const raw = fs.readFileSync(source);
const arrayBuffer = raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength);
const value = toObject(arrayBuffer);
fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, JSON.stringify(value, null, 2) + "\n");
const record = {
  source: path.relative(root, source),
  output: path.relative(root, output),
  bytes: raw.length,
  sha256: crypto.createHash("sha256").update(raw).digest("hex"),
  topLevelEntries: value && typeof value === "object" ? Object.keys(value).length : null,
  outputBytes: fs.statSync(output).size,
};
fs.writeFileSync(`${output}.meta.json`, JSON.stringify(record, null, 2) + "\n");
console.log(JSON.stringify(record));
