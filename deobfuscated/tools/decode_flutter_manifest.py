#!/usr/bin/env python3
"""Pair Flutter's compiled AssetManifest.bin with its shipped JSON manifest."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    assets = root / "Frameworks/App.framework/flutter_assets"
    binary = assets / "AssetManifest.bin"
    companion = assets / "AssetManifest.json"
    manifest = json.loads(companion.read_text())
    result = {
        "format": "Flutter AssetManifest.bin with shipped JSON companion",
        "source": "Frameworks/App.framework/flutter_assets/AssetManifest.bin",
        "sourceSize": binary.stat().st_size,
        "sourceSha256": sha256(binary),
        "magicHex": binary.read_bytes()[:4].hex(),
        "jsonCompanion": "Frameworks/App.framework/flutter_assets/AssetManifest.json",
        "jsonCompanionSha256": sha256(companion),
        "assetCount": len(manifest),
        "assets": manifest,
        "note": "The JSON companion is the readable manifest shipped beside the compiled binary; the binary is preserved unchanged.",
    }
    output = root / "deobfuscated/decoded/flutter/AssetManifest.bin.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"assetCount": len(manifest), "output": str(output.relative_to(root))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
