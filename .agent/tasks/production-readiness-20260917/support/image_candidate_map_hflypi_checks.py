"""Synthetic controls for the content-free OCI candidate mapper."""

import gzip
import hashlib
import io
import json
from pathlib import Path
import runpy
import tarfile


MODULE = runpy.run_path(str(Path(__file__).with_name("image_candidate_map_hflypi.py")))
MAP = MODULE["map_archive"]
MAP_CONFIG = MODULE["map_config"]


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def tar_bytes(members):
    output = io.BytesIO()
    archive = tarfile.open(fileobj=output, mode="w")
    try:
        for name, content in members:
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            archive.addfile(entry, io.BytesIO(content))
    finally:
        archive.close()
    return output.getvalue()


def descriptor(content, media):
    return {"mediaType": media, "digest": "sha256:" + hashlib.sha256(content).hexdigest(), "size": len(content)}


def fixture(layer_members):
    blobs, layers, ids = {}, [], []
    for members in layer_members:
        raw = tar_bytes(members)
        compressed = gzip.compress(raw, mtime=0)
        item = descriptor(compressed, "application/vnd.oci.image.layer.v1.tar+gzip")
        blobs["blobs/" + item["digest"].replace(":", "/")] = compressed
        layers.append(item)
        ids.append("sha256:" + hashlib.sha256(raw).hexdigest())
    config = encoded({"architecture": "arm64", "os": "linux", "rootfs": {"type": "layers", "diff_ids": ids}})
    config_item = descriptor(config, "application/vnd.oci.image.config.v1+json")
    config_path = "blobs/" + config_item["digest"].replace(":", "/")
    blobs[config_path] = config
    manifest = encoded({"schemaVersion": 2, "config": config_item, "layers": layers})
    manifest_item = descriptor(manifest, "application/vnd.oci.image.manifest.v1+json")
    blobs["blobs/" + manifest_item["digest"].replace(":", "/")] = manifest
    rows = list(sorted(blobs.items())) + [("index.json", encoded({"schemaVersion": 2, "manifests": [{**manifest_item, "platform": {"architecture": "arm64", "os": "linux"}}]})), ("manifest.json", encoded([{ "Config": config_path, "Layers": ["blobs/" + item["digest"].replace(":", "/") for item in layers]}])), ("oci-layout", encoded({"imageLayoutVersion": "1.0.0"}))]
    return tar_bytes(rows), ids, layers


def candidate(blob, diff_id, path, line=1, occurrence=1):
    path_sha256 = hashlib.sha256(path.encode()).hexdigest()
    return {"candidate_id": f"candidate-{blob[-8:]}-{occurrence}", "kind": "layer", "blob": blob, "diff_id": diff_id, "path_sha256": path_sha256, "line": line, "rule_id": "generic-api-key", "finding_occurrence": occurrence}


def rejected(payload, ids, candidates):
    try:
        MAP(io.BytesIO(payload), ids, candidates)
    except (RuntimeError, ValueError, OSError, tarfile.TarError):
        return
    raise AssertionError("candidate mapper falsely passed invalid input")


def main():
    marker = b"synthetic-not-a-real-credential\n"
    changed_marker = b"synthetic-second-layer-value\n"
    payload, ids, layers = fixture([[("app/src/main.py", marker)], [("app/src/main.py", changed_marker)], [("usr/share/public-package/data.py", marker)]])
    first = candidate(layers[0]["digest"], ids[0], "app/src/main.py")
    second = candidate(layers[1]["digest"], ids[1], "app/src/main.py")
    third = candidate(layers[2]["digest"], ids[2], "usr/share/public-package/data.py")
    result = MAP(io.BytesIO(payload), ids, [first, second, third])
    mapped = {row["candidate_id"]: row for row in result["mapped_candidates"]}
    assert mapped[first["candidate_id"]]["normalized_path"] == "app/src/main.py"
    assert mapped[second["candidate_id"]]["whole_file_sha256"] == hashlib.sha256(changed_marker).hexdigest()
    assert mapped[third["candidate_id"]]["path_class"] == "system_or_dependency_path"
    assert mapped[first["candidate_id"]]["byte_count"] == len(marker)
    assert mapped[first["candidate_id"]]["whole_file_sha256"] == hashlib.sha256(marker).hexdigest()
    assert marker.decode() not in json.dumps(result)
    missing = candidate(layers[0]["digest"], ids[0], "app/src/missing.py")
    rejected(payload, ids, [missing])
    duplicate_payload, duplicate_ids, duplicate_layers = fixture([[("app/src/main.py", marker), ("app/src/main.py", marker)]])
    rejected(duplicate_payload, duplicate_ids, [candidate(duplicate_layers[0]["digest"], duplicate_ids[0], "app/src/main.py")])
    rejected(payload[:len(payload) // 2], ids, [first, second])
    config_candidate = {"candidate_id": "candidate-config", "kind": "config", "blob": "oci-config", "diff_id": "oci-config", "path_sha256": hashlib.sha256(b"oci-config").hexdigest(), "line": 1, "rule_id": "generic-api-key", "finding_occurrence": 1}
    config_rows = MAP_CONFIG({"architecture": "arm64"}, [config_candidate], "sha256:" + "a" * 64, 123)
    assert config_rows[0]["original_oci_config_blob"] == "sha256:" + "a" * 64
    assert config_rows[0]["original_oci_config_byte_count"] == 123
    assert config_rows[0]["mapping_scope"] == "whole_canonical_config_only"
    print("OCI candidate mapper controls: layer identity, same-path separate layers, missing, duplicate, truncation, hash and raw-value absence PASS")


if __name__ == "__main__":
    main()
