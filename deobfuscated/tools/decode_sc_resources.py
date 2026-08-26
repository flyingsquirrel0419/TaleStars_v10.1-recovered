#!/usr/bin/env python3
"""Decode embedded KTX textures from bundled SC resources."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from mb_sc_tools.codec import (
    decode_ktx_to_png,
    decode_legacy_texture,
    ASTC_BLOCKS,
    find_embedded_ktx,
    inspect_container,
    parse_legacy_texture_tag_stream,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--astcenc", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    decoded = []
    failures = []
    sources = sorted(root.glob("res/**/*.sc"))
    for source in sources:
        relative = source.relative_to(root)
        raw = source.read_bytes()
        destination = output / relative.with_suffix("")
        destination.mkdir(parents=True, exist_ok=True)
        try:
            container, payload = inspect_container(raw)
            textures = []
            hits = find_embedded_ktx(payload)
            for index, (offset, length, header) in enumerate(hits):
                name = f"{source.stem}_{index:03d}.png"
                decode_ktx_to_png(payload[offset : offset + length], destination / name, args.astcenc.resolve())
                textures.append(
                    {
                        "index": index,
                        "file": name,
                        "source": "embedded_ktx",
                        "offset": offset,
                        "length": length,
                        "width": header["width"],
                        "height": header["height"],
                        "gl_internal_format": header["glInternalFormat"],
                        "astc_block": ASTC_BLOCKS.get(header["glInternalFormat"]),
                    }
                )
            if not hits:
                for index, (offset, tag, pixel_code, width, height, tex_payload) in enumerate(parse_legacy_texture_tag_stream(payload)):
                    name = f"{source.stem}_{index:03d}.png"
                    decode_legacy_texture(tag, pixel_code, width, height, tex_payload, destination / name)
                    textures.append(
                        {
                            "index": index,
                            "file": name,
                            "source": "legacy_tag",
                            "offset": offset,
                            "tag": tag,
                            "pixel_code": pixel_code,
                            "width": width,
                            "height": height,
                        }
                    )
            record = {
                "source": relative.as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "container": container,
                "texture_count": len(textures),
                "textures": textures,
            }
            sidecar = destination / "data.json"
            sidecar.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            decoded.append(record)
        except Exception as error:
            failures.append({"source": relative.as_posix(), "error": f"{type(error).__name__}: {error}"})

    (output / "index.json").write_text(json.dumps({"decoded": decoded, "failures": failures}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sources": len(sources), "decoded": len(decoded), "failures": len(failures), "textures": sum(item["texture_count"] for item in decoded)}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
