#!/usr/bin/env python3
"""Decode bundled SCTX textures to readable JSON metadata and PNG previews."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from mb_sc_tools.sctx import (
    _decode_texture_to_png,
    _read_main_payload,
    parse_sctx_metadata,
)


def metadata_dict(source: Path, raw: bytes, meta) -> dict:
    return {
        "source": source.as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "kind": "sctx",
        "type": meta.type_name,
        "type_enum": meta.pixel_type,
        "width": meta.width,
        "height": meta.height,
        "mip_count": meta.levels_count,
        "compressed": meta.use_compression,
        "use_padding": meta.use_padding,
        "flags": meta.flags,
        "texture_length": meta.texture_length,
        "root_chunk_length": meta.root_chunk_length,
        "mipmaps_chunk_length": meta.mipmaps_chunk_length,
        "data_offset": meta.data_offset,
        "streaming_ids": meta.streaming_ids,
        "mip_levels": [
            {
                "index": item.index,
                "width": item.width,
                "height": item.height,
                "offset": item.offset,
                "length": item.length,
                "hash_hex": item.hash_hex,
            }
            for item in meta.mip_levels
        ],
        "streaming_textures": [
            {
                "index": item.index,
                "type": item.type_name,
                "type_enum": item.type_enum,
                "width": item.width,
                "height": item.height,
            }
            for item in meta.streaming_textures
        ],
    }


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
    sources = sorted(root.glob("res/**/*.sctx"))
    for source in sources:
        relative = source.relative_to(root)
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = source.read_bytes()
        try:
            meta = parse_sctx_metadata(raw)
            payload = _read_main_payload(raw, meta)
            preview = destination.with_suffix(".png")
            first_level = payload[: meta.mip_levels[0].length]
            _decode_texture_to_png(
                first_level,
                meta.width,
                meta.height,
                meta.pixel_type,
                preview,
                args.astcenc.resolve(),
            )
            record = metadata_dict(relative, raw, meta)
            record["preview"] = preview.relative_to(output).as_posix()
            record["streaming_previews"] = []
            for texture in meta.streaming_textures:
                variant = destination.with_name(f"{destination.stem}.variant_{texture.index}.png")
                _decode_texture_to_png(
                    texture.data,
                    texture.width,
                    texture.height,
                    texture.type_enum,
                    variant,
                    args.astcenc.resolve(),
                )
                record["streaming_previews"].append(variant.relative_to(output).as_posix())
            destination.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            decoded.append(record)
        except Exception as error:
            failures.append({"source": relative.as_posix(), "error": f"{type(error).__name__}: {error}"})

    index = {"decoded": decoded, "failures": failures}
    (output / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sources": len(sources), "decoded": len(decoded), "failures": len(failures)}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
