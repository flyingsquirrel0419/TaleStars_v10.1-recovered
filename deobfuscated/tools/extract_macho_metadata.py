#!/usr/bin/env python3
"""Extract non-destructive metadata from Mach-O binaries with LIEF."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import lief


def enum_value(value):
    return str(value)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def c_strings(data: bytes, minimum: int = 4, limit: int = 200) -> list[str]:
    values: list[str] = []
    current = bytearray()
    for byte in data:
        if 0x20 <= byte <= 0x7E:
            current.append(byte)
        else:
            if len(current) >= minimum:
                values.append(current.decode("ascii", errors="replace"))
                if len(values) >= limit:
                    break
            current.clear()
    if len(values) < limit and len(current) >= minimum:
        values.append(current.decode("ascii", errors="replace"))
    return values


def section_bytes(binary, section) -> bytes:
    try:
        return bytes(section.content)
    except Exception:
        return b""


def objc_names(binary) -> list[str]:
    names: list[str] = []
    for section in binary.sections:
        if section.name not in {"__objc_classname", "__objc_methname", "__objc_methtype"}:
            continue
        for value in c_strings(section_bytes(binary, section), minimum=2, limit=10000):
            if value not in names:
                names.append(value)
    return names


def metadata(root: Path, relative: str) -> dict:
    source = root / relative
    result = {
        "source": relative,
        "size": source.stat().st_size,
        "sha256": sha256(source),
        "parser": "LIEF Mach-O",
    }
    try:
        binary = lief.parse(str(source))
        if binary is None:
            raise RuntimeError("LIEF returned no binary")
        header = binary.header
        result["header"] = {
            "cpuType": enum_value(header.cpu_type),
            "cpuSubtype": enum_value(header.cpu_subtype),
            "fileType": enum_value(header.file_type),
            "flags": int(header.flags),
            "numberOfCommands": int(header.nb_cmds),
            "commandsSize": int(header.sizeof_cmds),
            "entrypoint": int(getattr(binary, "entrypoint", 0)),
            "imagebase": int(getattr(binary, "imagebase", 0)),
            "isPIE": bool(getattr(binary, "is_pie", False)),
        }
        result["libraries"] = [library.name for library in binary.libraries]
        sections = []
        for section in binary.sections:
            sections.append({
                "name": section.name,
                "size": int(section.size),
                "offset": int(section.offset),
                "virtualAddress": int(section.virtual_address),
                "type": enum_value(section.type),
                "segment": section.segment.name if section.segment else None,
            })
        result["sections"] = sections
        result["objcStrings"] = objc_names(binary)
        result["importedFunctions"] = sorted({item.name for item in binary.imported_functions if item.name})
        result["exportedFunctions"] = sorted({item.name for item in binary.exported_functions if item.name})
        symbols = []
        for symbol in binary.symbols:
            if not symbol.name and not symbol.value:
                continue
            symbols.append({
                "name": symbol.name,
                "value": int(symbol.value),
                "size": int(symbol.size),
                "type": enum_value(symbol.type),
                "external": bool(symbol.is_external),
                "origin": enum_value(symbol.origin),
            })
        result["symbols"] = symbols
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    output = Path(sys.argv[2] if len(sys.argv) > 2 else "deobfuscated/decoded/macho").resolve()
    manifest = json.loads((root / "deobfuscated/binary-manifest.json").read_text())
    sources = [item["path"] for item in manifest["files"] if item["kind"] == "Mach-O 64-bit"]
    index = {"parser": "LIEF Mach-O", "sources": [], "failures": []}
    for relative in sources:
        report = metadata(root, relative)
        destination = output / f"{relative}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        index["sources"].append({"source": relative, "output": str(destination.relative_to(root)), "error": report.get("error")})
        if "error" in report:
            index["failures"].append(relative)
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"sources": len(sources), "failures": len(index["failures"])}))
    return 0 if not index["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
