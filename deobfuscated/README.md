# Recovered sources

This directory contains non-destructive, human-readable recoveries from the
`Tale Stars` iOS application bundle.

## JavaScript

`build.pretty.js` is the JavaScript payload from
`Frameworks/Tale.framework/build.js` after removing its 13-byte wrapper header
and trailing QuickJS serialization bytes, then formatting the valid JavaScript
with Prettier. The original identifiers and control-flow flattening are kept
so the file remains traceable to the shipped payload.

`agent.js` is the readable behavior recovered from the executed payload. The
observed Node execution path calls `console.log` once with `THE BLACKWHALE`.
`decoder.js` documents the printable-ASCII string decoder used by the payload.
`runtime/decoded-strings.json` records strings captured during execution.

## Text resources

`source/` contains readable text resources copied with their original bundle
paths. JSON files are parsed and pretty-printed; CSV, UI, HTML, CSS, shader,
strings, XML, and JavaScript files are copied as text. `resources/NOTICES` is
the decompressed form of Flutter's `NOTICES.Z`.

## Compiled resources

`binary-manifest.json` inventories every original file with its size, SHA-256,
detected format, and available container metadata. `compiled/plist/` contains
XML conversions of all 74 binary property lists.

`recovery-status.json` is the per-file completion ledger for all 19,941
original paths; it records the recovery mode, source hash, output paths, and
whether every expected output exists.

`decoded/sctx/` contains PNG previews and metadata for all 2,000 SCTX texture
containers. `decoded/sc/` contains metadata for all 275 SC containers and 383
decoded texture previews. `decoded/glb-json/` contains readable JSON extracted
from all 7,390 Supercell FLA2 model chunks, while `decoded/glb-standard/`
contains the same models rewritten as standard glTF 2.0 GLB files.

`decoded/particle_emitters.json` is the FlexBuffers-to-JSON recovery of the
particle emitter database. `decoded/compiled-strings/` contains searchable
ASCII and UTF-16 strings extracted from NIB and asset-catalog binaries.

`decoded/si-svg/` contains SVG reconstructions of all 112 ScalableImage `.si`
vector assets, including paths, groups, colors, gradients, text, and embedded
images where present.

`decoded/macho/` contains LIEF reports for all 56 Mach-O files, including
headers, load-linked libraries, sections, imports, symbols, and Objective-C
metadata. `decoded/opaque/opaque-analysis.json` records bounded forensic
metadata for every file still detected as an unknown binary. Standard font,
MP4, ICU, and Flutter manifest metadata is under `decoded/standard/` and
`decoded/flutter/`.

## Recovery boundary

Some files remain compiled or packaged artifacts: Mach-O executables and
frameworks, compiled Flutter manifests, fonts, OGG audio, and ECC blobs. Their
exact type, size, and path are recorded in `manifest.json` and
`binary-manifest.json`; format-specific metadata is added under `decoded/` as
it becomes available. The ECC blobs are encrypted and cannot be converted to
source or plaintext without their runtime key.

The remaining opaque set is limited to three ECC payloads under `res/ecc/`,
`res/badge/default.edges`, `res/sfx/robotwin_atk_01.ogg.sfk`, the encrypted
`res/tale/csv_logic/transactions.csv`, and one hashed binary text resource.
Their hashes, entropy, headers, and bounded string evidence are recorded in
`decoded/opaque/opaque-analysis.json`; no bytes were discarded or replaced.

All files in this directory are derived artifacts. The shipped app bundle was
not overwritten.
