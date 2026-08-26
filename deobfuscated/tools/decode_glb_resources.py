#!/usr/bin/env python3
"""Extract Supercell FLA2 JSON chunks from GLB resources."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--normalized-output", type=Path)
    parser.add_argument(
        "--converter", type=Path, default=Path("/tmp/supercell-flat-converter")
    )
    args = parser.parse_args()

    sys.path.insert(0, str(args.converter.resolve()))
    from lib.glTF import ObjectProcessor, glTF

    root = args.root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    normalized_output = args.normalized_output.resolve() if args.normalized_output else None
    if normalized_output:
        normalized_output.mkdir(parents=True, exist_ok=True)
    decoded = []
    failures = []

    for source in sorted(root.glob("res/**/*.glb")):
        relative = source.relative_to(root)
        destination = output / (relative.as_posix() + ".json")
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            raw = source.read_bytes()
            container = glTF()
            container.read(raw)
            chunks = []
            json_chunk = None
            for chunk in container.chunks:
                chunks.append({"type": chunk.name, "length": len(chunk.data)})
                if chunk.name == "FLA2":
                    chunk.deserialize_json()
                if chunk.name == "JSON":
                    json_chunk = chunk.data
            if json_chunk is None:
                raise ValueError("GLB has no FLA2 JSON chunk")

            destination.write_text(
                json.dumps(json_chunk, cls=ObjectProcessor, indent=2) + "\n",
                encoding="utf-8",
            )
            normalized = None
            if normalized_output:
                normalized_path = normalized_output / relative
                normalized_path.parent.mkdir(parents=True, exist_ok=True)
                normalized_path.write_bytes(container.write())
                normalized = normalized_path.relative_to(normalized_output).as_posix()
            decoded.append(
                {
                    "source": relative.as_posix(),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "output": destination.relative_to(output).as_posix(),
                    "normalizedOutput": normalized,
                    "chunks": chunks,
                    "counts": {
                        key: len(json_chunk.get(key, []))
                        for key in ("accessors", "bufferViews", "meshes", "nodes")
                    },
                }
            )
        except Exception as error:
            failures.append(
                {
                    "source": relative.as_posix(),
                    "error": f"{type(error).__name__}: {error}",
                }
            )

    index = {"decoded": decoded, "failures": failures}
    (output / "index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "sources": len(decoded) + len(failures),
                "decoded": len(decoded),
                "failures": len(failures),
            }
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
