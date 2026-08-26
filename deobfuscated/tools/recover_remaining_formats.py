#!/usr/bin/env python3
"""Recover deterministic section and metadata views for the last opaque formats."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "deobfuscated/decoded"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def recover_ecc_sections() -> list[dict]:
    executable = (ROOT / "laser").read_bytes()
    records = []
    for name in ("text", "const", "cstring"):
        source = ROOT / f"res/ecc/laser.{name}.ecc"
        section_offset, version, section_size, flags = struct.unpack(
            "<4I", source.read_bytes()[:16]
        )
        section = executable[section_offset : section_offset + section_size]
        if len(section) != section_size:
            raise ValueError(f"section is truncated: {name}")
        output = OUTPUT / "recovered-sections/res/ecc" / f"laser.{name}.section.bin"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(section)
        records.append(
            {
                "source": source.relative_to(ROOT).as_posix(),
                "output": output.relative_to(ROOT).as_posix(),
                "headerWords": [section_offset, version, section_size, flags],
                "sourceSha256": sha256_file(source),
                "outputSha256": sha256_file(output),
                "recovery": "Mach-O section extraction at the offset and size declared by the ECC header",
            }
        )
    return records


def recover_edges_metadata() -> dict:
    source = ROOT / "res/badge/default.edges"
    data = source.read_bytes()
    usable = len(data) - (len(data) % 2)
    words = list(struct.unpack(f"<{usable // 2}H", data[:usable]))
    return {
        "source": source.relative_to(ROOT).as_posix(),
        "sourceSize": len(data),
        "sourceSha256": sha256_file(source),
        "format": "opaque little-endian UInt16 geometry/edge data",
        "wordCount": len(words),
        "trailingBytes": data[usable:].hex(),
        "words": words,
        "associatedTextures": [
            path.relative_to(ROOT).as_posix()
            for path in sorted((ROOT / "res/badge").glob("default_*.png"))
        ],
        "note": "The word stream is preserved exactly; no public schema was found for this Supercell edge asset.",
    }


def recover_sfk_metadata() -> dict:
    source = ROOT / "res/sfx/robotwin_atk_01.ogg.sfk"
    data = source.read_bytes()
    companion = ROOT / "res/sfx/robotwin_atk_01.ogg"
    return {
        "source": source.relative_to(ROOT).as_posix(),
        "sourceSize": len(data),
        "sourceSha256": sha256_file(source),
        "format": "Sound Forge SFPK peak-data sidecar",
        "headerWords": list(struct.unpack("<16I", data[:64])),
        "tableOffset": 64,
        "tableBytes": len(data) - 64,
        "tableHex": data[64:].hex(),
        "companionAudio": companion.relative_to(ROOT).as_posix(),
        "companionAudioSha256": sha256_file(companion),
        "note": "This sidecar contains waveform peak/index data, not additional audio samples.",
    }


def main() -> None:
    section_records = recover_ecc_sections()
    edges_output = OUTPUT / "opaque/res/badge/default.edges.json"
    edges_output.parent.mkdir(parents=True, exist_ok=True)
    edges_output.write_text(json.dumps(recover_edges_metadata(), indent=2) + "\n")

    sfk_output = OUTPUT / "opaque/res/sfx/robotwin_atk_01.ogg.sfk.json"
    sfk_output.parent.mkdir(parents=True, exist_ok=True)
    sfk_output.write_text(json.dumps(recover_sfk_metadata(), indent=2) + "\n")

    print(
        json.dumps(
            {
                "eccSections": len(section_records),
                "edgesMetadata": edges_output.relative_to(ROOT).as_posix(),
                "sfkMetadata": sfk_output.relative_to(ROOT).as_posix(),
            }
        )
    )


if __name__ == "__main__":
    main()
