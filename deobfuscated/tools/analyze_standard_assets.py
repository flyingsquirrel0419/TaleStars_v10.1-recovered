#!/usr/bin/env python3
"""Extract metadata from standard font, MP4, and ICU data assets."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atoms(data: bytes, limit: int = 100) -> list[dict]:
    result = []
    offset = 0
    while offset + 8 <= len(data) and len(result) < limit:
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8].decode("latin1")
        header = 8
        if size == 1 and offset + 16 <= len(data):
            size = struct.unpack(">Q", data[offset + 8 : offset + 16])[0]
            header = 16
        if size == 0:
            size = len(data) - offset
        if size < header or offset + size > len(data):
            break
        result.append({"offset": offset, "size": size, "type": kind})
        offset += size
    return result


def font_metadata(path: Path) -> dict:
    command = ["fc-scan", "--format=%{family}\n%{style}\n%{fullname}\n%{fontversion}\n%{weight}\n", str(path)]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    lines = completed.stdout.splitlines()
    return {
        "family": lines[0] if len(lines) > 0 else None,
        "style": lines[1] if len(lines) > 1 else None,
        "fullname": lines[2] if len(lines) > 2 else None,
        "fontVersion": lines[3] if len(lines) > 3 else None,
        "weight": lines[4] if len(lines) > 4 else None,
        "fcScanError": completed.stderr.strip() or None,
    }


def record(root: Path, relative: str) -> dict:
    path = root / relative
    data = path.read_bytes()
    item = {"source": relative, "size": len(data), "sha256": sha256(path)}
    if path.suffix.lower() in {".ttf", ".otf"}:
        item["format"] = "OpenType/TrueType font"
        item["font"] = font_metadata(path)
    elif path.suffix.lower() == ".mp4":
        item["format"] = "ISO Base Media / MP4"
        item["atoms"] = atoms(data)
    elif relative.endswith("icudtl.dat"):
        item["format"] = "ICU data archive"
        item["headerHex"] = data[:64].hex()
        item["headerWordsBigEndian"] = list(struct.unpack(">4I", data[:16])) if len(data) >= 16 else []
    return item


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    output = Path(sys.argv[2] if len(sys.argv) > 2 else "deobfuscated/decoded/standard").resolve()
    manifest = json.loads((root / "deobfuscated/binary-manifest.json").read_text())
    sources = []
    for item in manifest["files"]:
        path = item["path"]
        if Path(path).suffix.lower() in {".ttf", ".otf", ".mp4"} or path.endswith("icudtl.dat"):
            sources.append(path)
    result = {"generatedAt": "2026-08-26", "sourceCount": len(sources), "records": [record(root, path) for path in sources]}
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "standard-asset-metadata.json"
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"sources": len(sources), "output": str(destination.relative_to(root))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
