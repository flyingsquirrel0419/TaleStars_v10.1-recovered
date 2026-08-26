#!/usr/bin/env python3
"""Convert every embedded Apple binary plist or nib archive to readable XML."""

from pathlib import Path
import json
import plistlib


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "deobfuscated" / "compiled" / "plist"
OUTPUT.mkdir(parents=True, exist_ok=True)

converted = []
failed = []
for source in ROOT.rglob("*"):
    if not source.is_file() or "deobfuscated" in source.parts:
        continue
    raw = source.read_bytes()
    if not raw.startswith(b"bplist00"):
        continue
    relative = source.relative_to(ROOT)
    target = OUTPUT / relative.with_suffix(relative.suffix + ".xml")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        value = plistlib.loads(raw)
        with target.open("wb") as stream:
            plistlib.dump(value, stream, fmt=plistlib.FMT_XML, sort_keys=False)
        converted.append({"source": relative.as_posix(), "output": target.relative_to(ROOT).as_posix()})
    except Exception as error:  # Keep a machine-readable record of unsupported archives.
        failed.append({"source": relative.as_posix(), "error": str(error)})

(OUTPUT / "index.json").write_text(
    json.dumps({"converted": converted, "failed": failed}, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps({"converted": len(converted), "failed": len(failed)}))
