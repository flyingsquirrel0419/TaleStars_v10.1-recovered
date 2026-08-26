#!/usr/bin/env python3
"""Make searchable text sidecars for opaque NIB and asset-catalog binaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


ASCII_RE = re.compile(rb"[\x20-\x7e]{4,}")
UTF16_RE = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")


def extract(raw: bytes) -> list[tuple[int, str]]:
    found: dict[tuple[int, str], None] = {}
    for match in ASCII_RE.finditer(raw):
        found[(match.start(), match.group().decode("ascii"))] = None
    for match in UTF16_RE.finditer(raw):
        try:
            value = match.group().decode("utf-16le").rstrip("\x00")
        except UnicodeDecodeError:
            continue
        if value:
            found[(match.start(), value)] = None
    return sorted(found)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for extension in ("nib", "car"):
        for source in sorted(root.glob(f"**/*.{extension}")):
            if source.is_relative_to(output):
                continue
            if not source.is_file():
                continue
            relative = source.relative_to(root)
            destination = output / (relative.as_posix() + ".strings.txt")
            destination.parent.mkdir(parents=True, exist_ok=True)
            strings = extract(source.read_bytes())
            lines = [f"# source: {relative.as_posix()}", f"# strings: {len(strings)}", ""]
            lines.extend(f"0x{offset:08x}\t{value}" for offset, value in strings)
            destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
            records.append({"source": relative.as_posix(), "output": destination.relative_to(output).as_posix(), "strings": len(strings)})
    (output / "index.json").write_text(
        json.dumps({"files": records}, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"files": len(records), "strings": sum(item["strings"] for item in records)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
