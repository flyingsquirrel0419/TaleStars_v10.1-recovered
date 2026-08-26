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
  } else if (ext === ".si") {
    status = "svg-vector-recovery";
    const basename = path.basename(source).replace(/\.si$/i, ".svg");
    outputs = [`deobfuscated/decoded/si-svg/${basename}`];
  } else if (file.kind === "Mach-O 64-bit") {
    status = "macho-metadata";
    outputs = [`deobfuscated/decoded/macho/${source}.json`];
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
  } else if (source === "Frameworks/App.framework/flutter_assets/AssetManifest.bin") {
    status = "flutter-manifest-paired-json";
    outputs = ["deobfuscated/decoded/flutter/AssetManifest.bin.json"];
  } else if (source === "res/ecc/laser.text.ecc") {
    status = "mach-o-section-recovery";
    outputs = ["deobfuscated/decoded/recovered-sections/res/ecc/laser.text.section.bin"];
  } else if (source === "res/ecc/laser.const.ecc") {
    status = "mach-o-section-recovery";
    outputs = ["deobfuscated/decoded/recovered-sections/res/ecc/laser.const.section.bin"];
  } else if (source === "res/ecc/laser.cstring.ecc") {
    status = "mach-o-section-recovery";
    outputs = ["deobfuscated/decoded/recovered-sections/res/ecc/laser.cstring.section.bin"];
  } else if (source === "res/badge/default.edges") {
    status = "structured-binary-metadata";
    outputs = ["deobfuscated/decoded/opaque/res/badge/default.edges.json"];
  } else if (source === "res/sfx/robotwin_atk_01.ogg.sfk") {
    status = "structured-binary-metadata";
    outputs = ["deobfuscated/decoded/opaque/res/sfx/robotwin_atk_01.ogg.sfk.json"];
  } else if (ext === ".ttf" || ext === ".otf") {
    status = "standard-font-metadata";
    outputs = ["deobfuscated/decoded/standard/standard-asset-metadata.json"];
  } else if (ext === ".mp4") {
    status = "standard-mp4-metadata";
    outputs = ["deobfuscated/decoded/standard/standard-asset-metadata.json"];
  } else if (source.endsWith("Frameworks/Flutter.framework/icudtl.dat")) {
    status = "icu-data-metadata";
    outputs = ["deobfuscated/decoded/standard/standard-asset-metadata.json"];
  } else if (file.kind === "unknown binary") {
    status = "opaque-binary-analysis";
    outputs = ["deobfuscated/decoded/opaque/opaque-analysis.json"];
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
