"""Freeze PUBLIC offline reference assets without copying them into the build.
No UGC/uploads, credentials or account state are read. This is not a runtime manifest.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def glb_summary(path: Path) -> dict:
    size = path.stat().st_size
    with path.open("rb") as handle:
        header = handle.read(20)
        if len(header) != 20:
            raise ValueError("Truncated GLB")
        magic, version, declared, json_length, chunk_type = struct.unpack("<4s4I", header)
        if magic != b"glTF" or version != 2 or declared != size or chunk_type != 0x4E4F534A:
            raise ValueError("Invalid GLB v2 envelope")
        if json_length > 64 * 1024 * 1024 or json_length + 20 > size or json_length % 4:
            raise ValueError("Invalid or oversized GLB JSON")
        document = json.loads(handle.read(json_length).decode("utf-8"))
    accessors = document.get("accessors", [])
    mesh_triangles = []
    for mesh in document.get("meshes", []):
        triangles = 0
        for primitive in mesh.get("primitives", []):
            if primitive.get("mode", 4) != 4:
                raise ValueError("Only triangle-list references are accepted for this inventory")
            accessor_index = primitive.get("indices", primitive.get("attributes", {}).get("POSITION"))
            if not isinstance(accessor_index, int) or not 0 <= accessor_index < len(accessors):
                raise ValueError("Primitive has invalid accessor")
            count = accessors[accessor_index].get("count", -1)
            if not isinstance(count, int) or count < 0 or count % 3:
                raise ValueError("Triangle-list element count must be divisible by three")
            triangles += count // 3
        mesh_triangles.append(triangles)
    references = []
    for node in document.get("nodes", []):
        if "mesh" in node:
            index = node["mesh"]
            if not isinstance(index, int) or not 0 <= index < len(mesh_triangles):
                raise ValueError("Invalid node mesh")
            references.append(mesh_triangles[index])
    external = [item.get("uri") for category in ("buffers", "images")
                for item in document.get(category, []) if item.get("uri") and
                not item["uri"].startswith("data:")]
    if external:
        raise ValueError("External references must be resolved before freezing offline assets")
    return {"bytes": size, "sha256": sha256_file(path),
            "unique_mesh_triangles": sum(mesh_triangles),
            "all_node_referenced_triangles": sum(references),
            "nodes": len(document.get("nodes", [])), "meshes": len(mesh_triangles),
            "materials": len(document.get("materials", [])),
            "images": len(document.get("images", [])),
            "note": "Counts all nodes, not only the active scene; geometry integrity not revalidated here."}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project = args.source_project.resolve()
    root = project / "art/cloud-meadow-cinematic-v1"
    references = sorted((root / "client-staging").glob("*.glb"))
    if not references:
        raise ValueError("No public meadow client-staging GLBs found")
    entries = []
    for path in references:
        # Do not follow a source symlink outside the authorized project.
        path.resolve().relative_to(project)
        entries.append({"source": path.relative_to(project).as_posix(), **glb_summary(path)})
    anchors = []
    for relative in ("art/cloud-meadow-cinematic-v1/cloud-meadow-master.blend",
                     "art/cloud-meadow-cinematic-v1/build-report.json", "static/data/farm-layout.json"):
        path = project / relative
        path.resolve().relative_to(project)
        if not path.is_file():
            raise ValueError("Required source missing: " + relative)
        anchors.append({"source": relative, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    result = {"schema_version": 1, "purpose": "P0 public source reference freeze",
              "runtime_ready": False, "engine_import_tested": False,
              "map_version_migration_tested": False, "references": entries, "anchors": anchors,
              "total_reference_bytes": sum(item["bytes"] for item in entries),
              "pending": ["Blender runtime mesh/instance/LOD preparation", "PBR material conversion",
                          "coordinate anchors", "collision/navigation", "Shipping import",
                          "GPU timing, VRAM and visual acceptance"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(entries), "reference_mib": round(result["total_reference_bytes"] / 2**20, 1),
                      "runtime_ready": False, "report": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
