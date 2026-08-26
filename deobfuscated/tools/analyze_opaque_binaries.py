#!/usr/bin/env python3
"""Record bounded, non-destructive evidence for files without a decoded format."""

from __future__ import annotations

import hashlib
import json
import math
import struct
import sys
from pathlib import Path


MAGICS = {
    b"bplist00": "Apple binary plist",
    b"glTF": "glTF binary",
    b"OggS": "Ogg container",
    b"SFPK": "SFPK sidecar/index",
    b"\x1f\x8b\x08": "gzip",
    b"\x89PNG\r\n\x1a\n": "PNG",
    b"PK\x03\x04": "ZIP archive",
    b"\x0d\xfe\xee\x02": "Flutter AssetManifest binary",
    b"\xb0\xb0\x1e\x07": "ScalableImage (.si)",
}


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    size = len(data)
    return -sum((count / size) * math.log2(count / size) for count in counts if count)


def strings_ascii(data: bytes, minimum: int = 4, limit: int = 64) -> list[str]:
    output: list[str] = []
    current = bytearray()
    for byte in data:
        if 0x20 <= byte <= 0x7E:
            current.append(byte)
        else:
            if len(current) >= minimum:
                output.append(current.decode("ascii", errors="replace"))
                if len(output) >= limit:
                    return output
            current.clear()
    if len(current) >= minimum and len(output) < limit:
        output.append(current.decode("ascii", errors="replace"))
    return output


def strings_utf16le(data: bytes, minimum: int = 4, limit: int = 64) -> list[str]:
    output: list[str] = []
    current: list[int] = []
    for offset in range(0, len(data) - 1, 2):
        value = data[offset] | (data[offset + 1] << 8)
        if 0x20 <= value <= 0x7E:
            current.append(value)
        else:
            if len(current) >= minimum:
                output.append("".join(chr(item) for item in current))
                if len(output) >= limit:
                    return output
            current.clear()
    if len(current) >= minimum and len(output) < limit:
        output.append("".join(chr(item) for item in current))
    return output


def classify(path: str, head: bytes) -> str:
    if path.endswith(".ecc"):
        return "ECC-like encrypted resource"
    if path.endswith(".edges"):
        return "opaque edge/geometry resource"
    if path.endswith(".sfk"):
        return "SFPK audio sidecar/index"
    for magic, name in MAGICS.items():
        if head.startswith(magic):
            return name
    if head.startswith(b"<?xml") or head.startswith(b"<plist"):
        return "XML text"
    return "unidentified binary/text"


def embedded_signatures(data: bytes) -> list[dict]:
    signatures = [
        (b"glTF", "glTF", 4),
        (b"OggS", "Ogg", 4),
        (b"\x89PNG\r\n\x1a\n", "PNG", 8),
        (b"bplist00", "bplist", 8),
        (b"PK\x03\x04", "ZIP", 4),
        (b"SFPK", "SFPK", 4),
        (b"\xb0\xb0\x1e\x07", "SI", 4),
    ]
    found = []
    for magic, name, start in signatures:
        offset = data.find(magic, start)
        if offset >= 0:
            found.append({"format": name, "offset": offset})
    return found


def analyze(root: Path, relative: str) -> dict:
    source = root / relative
    data = source.read_bytes()
    sample = data[: min(len(data), 1024 * 1024)]
    record = {
        "source": relative,
        "size": len(data),
        "sha256": hash_file(source),
        "classification": classify(relative, data[:16]),
        "headerHex": data[:64].hex(),
        "sampleEntropyBitsPerByte": round(entropy(sample), 6),
        "asciiStrings": strings_ascii(sample),
        "utf16leStrings": strings_utf16le(sample),
        "embeddedSignaturesInSample": embedded_signatures(sample),
    }
    if relative.endswith(".ecc") and len(data) >= 16:
        section_offset, version, section_size, flags = struct.unpack("<4I", data[:16])
        record["littleEndianHeaderWords"] = [section_offset, version, section_size, flags]
        record["sectionFileOffset"] = section_offset
        record["sectionSize"] = section_size
        record["payloadSize"] = len(data) - 16
        record["payloadToSectionRatio"] = round((len(data) - 16) / section_size, 8) if section_size else None
        record["note"] = "Header identifies a Mach-O section; payload is high-entropy and remains encrypted/packed without the runtime key and decoder."
        record["payloadOffset"] = 16
    if relative.endswith(".sfk") and len(data) >= 64:
        record["littleEndianHeaderWords"] = list(struct.unpack("<16I", data[:64]))
        record["tableOffset"] = 64
        record["tableBytes"] = len(data) - 64
        companion = relative[:-4]
        record["companionAudio"] = companion if (root / companion).exists() else None
    if relative.endswith(".edges"):
        usable = len(data) - (len(data) % 2)
        record["uint16LittleEndian"] = list(struct.unpack(f"<{usable // 2}H", data[:usable]))
        record["wordCount"] = usable // 2
    return record


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    output = Path(sys.argv[2] if len(sys.argv) > 2 else "deobfuscated/decoded/opaque").resolve()
    manifest = json.loads((root / "deobfuscated/binary-manifest.json").read_text())
    sources = [item["path"] for item in manifest["files"] if item["kind"] == "unknown binary"]
    records = [analyze(root, source) for source in sources]
    result = {
        "generatedAt": "2026-08-26",
        "sampleLimitBytes": 1024 * 1024,
        "sourceCount": len(records),
        "records": records,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "opaque-analysis.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"sources": len(records), "output": str((output / 'opaque-analysis.json').relative_to(root))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
