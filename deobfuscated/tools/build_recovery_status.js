#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const root = path.resolve(process.argv[2] || ".");
const manifest = JSON.parse(fs.readFileSync(path.join(root, "deobfuscated/binary-manifest.json")));
const statuses = [];

function exists(relative) {
  return fs.existsSync(path.join(root, relative));
}

for (const file of manifest.files) {
  const source = file.path;
  const ext = path.extname(source).toLowerCase();
  let status = "preserved-original";
  let outputs = [];
  if (source === "Frameworks/Tale.framework/build.js") {
    status = "javascript-recovered";
    outputs = ["deobfuscated/build.pretty.js", "deobfuscated/agent.js", "deobfuscated/decoder.js"];
  } else if (source === "Frameworks/App.framework/flutter_assets/NOTICES.Z") {
    status = "decompressed-text";
    outputs = ["deobfuscated/resources/NOTICES"];
  } else if (ext === ".glb") {
    status = "standard-glb-and-json";
    outputs = [`deobfuscated/decoded/glb-standard/${source}`, `deobfuscated/decoded/glb-json/${source}.json`];
  } else if (ext === ".sctx") {
    status = "decoded-texture-and-png";
    const base = source.replace(/\.sctx$/i, "");
    outputs = [`deobfuscated/decoded/sctx/${base}.json`, `deobfuscated/decoded/sctx/${base}.png`];
  } else if (ext === ".sc") {
    status = "decoded-container-and-textures";
    outputs = [`deobfuscated/decoded/sc/${source.replace(/\.sc$/i, "")}/data.json`];
  } else if (file.kind === "Apple binary plist") {
    status = "xml-plist";
    outputs = [`deobfuscated/compiled/plist/${source}.xml`];
  } else if (ext === ".flex") {
    status = "decoded-json";
    outputs = ["deobfuscated/decoded/particle_emitters.json"];
  } else if (ext === ".nib" || ext === ".car") {
    status = "searchable-strings";
    outputs = [`deobfuscated/decoded/compiled-strings/${source}.strings.txt`];
  } else if (exists(`deobfuscated/source/${source}`)) {
    status = "readable-source-copy";
    outputs = [`deobfuscated/source/${source}`];
  }
  statuses.push({
    source,
    size: file.size,
    sha256: file.sha256,
    kind: file.kind,
    status,
    outputs,
    outputsPresent: outputs.length === 0 || outputs.every(exists),
  });
}

const counts = {};
for (const item of statuses) counts[item.status] = (counts[item.status] || 0) + 1;
const result = {
  generatedAt: "2026-08-26",
  originalFileCount: statuses.length,
  outputRoot: "deobfuscated",
  counts,
  missingOutputs: statuses.filter((item) => !item.outputsPresent).map((item) => item.source),
  files: statuses,
};
fs.writeFileSync(path.join(root, "deobfuscated/recovery-status.json"), JSON.stringify(result, null, 2) + "\n");
console.log(JSON.stringify({ files: statuses.length, counts, missingOutputs: result.missingOutputs.length }));
