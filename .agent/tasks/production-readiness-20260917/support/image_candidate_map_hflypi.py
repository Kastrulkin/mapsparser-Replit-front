"""Map redacted OCI credential candidates to bounded, content-free metadata.

The mapper reads one pinned image as a stream. It never extracts a layer,
runs a container, or preserves member bytes, credential values, or snippets.
"""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import signal
import shutil
import subprocess
import sys
import tarfile
import threading
import time


PRIVATE_PATH = Path(__file__).with_name("image_private_layers_hflypi.py")
PRIVATE = runpy.run_path(str(PRIVATE_PATH))
BLOB = PRIVATE["BLOB"]
CHUNK = PRIVATE["CHUNK"]
DOCKER = PRIVATE["DOCKER"]
ENV = PRIVATE["ENV"]
EVIDENCE = PRIVATE["EVIDENCE"]
IMAGE = PRIVATE["IMAGE"]
MAX_ARCHIVE = PRIVATE["MAX_ARCHIVE"]
MAX_JSON = PRIVATE["MAX_JSON"]
MAX_LAYER = PRIVATE["MAX_LAYER"]
MAX_TOTAL = PRIVATE["MAX_TOTAL"]
Meter = PRIVATE["Meter"]
Prefix = PRIVATE["Prefix"]
drain = PRIVATE["drain"]
normalized = PRIVATE["normalized"]
require = PRIVATE["require"]
small_bytes = PRIVATE["small_bytes"]
validate_graph = PRIVATE["validate_graph"]


CAPTURE = Path(__file__).parents[1] / "evidence" / "image-credentials-hflypi-20260922" / "image-credentials-v2.json"
CAPTURE_SHA256 = "02fa7241514f55ae81ce184f6df88733696eca17927169b771dc0f4c4229a95e"
MAX_CANDIDATES = 512
EXPORT_TIMEOUT = 180


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def kill_process_group(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGKILL)


def safe_path_class(name):
    parts = PurePosixPath(name).parts
    if parts[:2] == ("app", "src"):
        return "app_source"
    if parts[:2] == ("app", "tests"):
        return "app_tests"
    if parts[:2] in {("usr", "lib"), ("usr", "local"), ("usr", "share"), ("etc", "ssl"), ("etc", "ca-certificates")} or parts[:1] in {("lib",), ("lib64",), ("ms-playwright",)}:
        return "system_or_dependency_path"
    return "unclassified"


def candidate_id(kind, blob, diff_id, path_sha256, line, rule_id, occurrence):
    identity = "\x1f".join((kind, blob, diff_id, path_sha256, str(line), rule_id, str(occurrence)))
    return "candidate-" + hashlib.sha256(identity.encode()).hexdigest()[:24]


def capture_candidates(capture):
    require(digest(CAPTURE) == CAPTURE_SHA256, "credential capture hash mismatch")
    require(capture.get("image") == IMAGE and capture.get("status") == "findings_require_review", "unexpected credential capture")
    layers = capture.get("layers")
    config = capture.get("config_credential_findings")
    require(isinstance(layers, list) and len(layers) == 20 and isinstance(config, list), "unexpected credential capture layers")
    candidates = []
    occurrences = {}
    for layer in layers:
        blob = layer.get("blob")
        diff_id = layer.get("diff_id")
        findings = layer.get("credential_findings")
        require(isinstance(blob, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", blob) is not None, "invalid candidate blob")
        require(isinstance(diff_id, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", diff_id) is not None, "invalid candidate diff id")
        require(isinstance(findings, list), "invalid candidate findings")
        for finding in findings:
            path_sha256 = finding.get("path_sha256")
            line = finding.get("line")
            rule_id = finding.get("rule_id")
            require(isinstance(path_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", path_sha256) is not None, "invalid candidate path hash")
            require(isinstance(line, int) and line > 0, "invalid candidate line")
            require(isinstance(rule_id, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", rule_id) is not None, "invalid candidate rule")
            identity = ("layer", blob, diff_id, path_sha256, line, rule_id)
            occurrence = occurrences.get(identity, 0) + 1
            occurrences[identity] = occurrence
            candidates.append({"candidate_id": candidate_id(*identity, occurrence), "kind": "layer", "blob": blob, "diff_id": diff_id, "path_sha256": path_sha256, "line": line, "rule_id": rule_id, "finding_occurrence": occurrence})
    config_hash = hashlib.sha256(b"oci-config").hexdigest()
    for finding in config:
        path_sha256 = finding.get("path_sha256")
        line = finding.get("line")
        rule_id = finding.get("rule_id")
        require(path_sha256 == config_hash and isinstance(line, int) and line > 0 and isinstance(rule_id, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", rule_id) is not None, "invalid config candidate")
        identity = ("config", "oci-config", "oci-config", path_sha256, line, rule_id)
        occurrence = occurrences.get(identity, 0) + 1
        occurrences[identity] = occurrence
        candidates.append({"candidate_id": candidate_id(*identity, occurrence), "kind": "config", "blob": "oci-config", "diff_id": "oci-config", "path_sha256": path_sha256, "line": line, "rule_id": rule_id, "finding_occurrence": occurrence})
    require(len(candidates) == capture.get("finding_count") == 219 and len(candidates) <= MAX_CANDIDATES, "candidate count mismatch")
    return candidates


def hash_member(stream, size):
    content = Meter(stream, size)
    lines = 1
    while True:
        block = content.read(CHUNK)
        if not block:
            break
        lines += block.count(b"\n")
    require(content.count == size, "regular member truncated")
    return {"sha256": content.digest.hexdigest(), "bytes": content.count, "line_count": lines}


def map_layer(source, blob, expected_diff_id, candidates):
    layer = Meter(source, MAX_LAYER)
    archive = tarfile.open(fileobj=layer, mode="r|")
    matches = {}
    name_occurrences = {}
    entries = 0
    try:
        for entry in archive:
            entries += 1
            require(entries <= 500000, "layer member limit exceeded")
            name = normalized(entry.name)
            if entry.isreg():
                require(entry.sparse is None and 0 <= entry.size <= 1024**3, "unsupported regular layer member")
                path_sha256 = hashlib.sha256(name.encode()).hexdigest()
                if path_sha256 not in candidates:
                    stream = archive.extractfile(entry)
                    require(stream is not None, "regular member content unavailable")
                    content = Meter(stream, entry.size)
                    drain(content)
                    stream.close()
                    require(content.count == entry.size, "regular member truncated")
                    continue
                stream = archive.extractfile(entry)
                require(stream is not None, "regular member content unavailable")
                metadata = hash_member(stream, entry.size)
                stream.close()
                occurrence = name_occurrences.get(name, 0) + 1
                name_occurrences[name] = occurrence
                matches.setdefault(path_sha256, []).append({"path": name, "path_class": safe_path_class(name), "member_occurrence_index": occurrence, **metadata})
            else:
                require(entry.isdir() or entry.isdev() or entry.isfifo() or entry.issym() or entry.islnk(), "unsupported layer member kind")
    finally:
        archive.close()
    drain(layer)
    diff_id = "sha256:" + layer.digest.hexdigest()
    require(diff_id == expected_diff_id, "mapped layer diff id mismatch")
    mapped = []
    for path_sha256, candidate_rows in candidates.items():
        rows = matches.get(path_sha256, [])
        require(len(rows) == 1, "candidate member missing or ambiguous")
        row = rows[0]
        for candidate in candidate_rows:
            require(candidate["line"] <= row["line_count"], "candidate line outside mapped member")
            output = {**candidate, "whole_file_sha256": row["sha256"], "byte_count": row["bytes"], "member_occurrence_index": row["member_occurrence_index"], "path_class": row["path_class"]}
            if row["path_class"] != "unclassified":
                output["normalized_path"] = row["path"]
            mapped.append(output)
    return mapped, layer.count


def map_config(config, candidates, config_blob, original_raw_bytes):
    value = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    result = []
    for candidate in candidates:
        result.append({**candidate, "whole_file_sha256": hashlib.sha256(value).hexdigest(), "byte_count": len(value), "canonical_config_sha256": hashlib.sha256(value).hexdigest(), "canonical_config_byte_count": len(value), "original_oci_config_blob": config_blob, "original_oci_config_byte_count": original_raw_bytes, "member_occurrence_index": 1, "path_class": "oci_config", "normalized_path": "oci-config", "mapping_scope": "whole_canonical_config_only"})
    return result


def map_archive(source, expected_diff_ids, candidates):
    pending = {}
    config_candidates = []
    for candidate in candidates:
        if candidate["kind"] == "config":
            config_candidates.append(candidate)
        else:
            pending.setdefault((candidate["blob"], candidate["diff_id"]), {}).setdefault(candidate["path_sha256"], []).append(candidate)
    measured = Meter(source, MAX_ARCHIVE)
    archive = tarfile.open(fileobj=measured, mode="r|")
    seen, metadata, layers, sizes = set(), {}, {}, {}
    total = 0
    mapped = []
    try:
        for entry in archive:
            name = normalized(entry.name)
            require(name not in seen and len(seen) < 100, "duplicate or excessive OCI members")
            seen.add(name)
            if entry.isdir():
                require(name in {"blobs", "blobs/sha256"}, "unexpected OCI directory")
                continue
            require(entry.isreg() and entry.sparse is None, "nonregular OCI member")
            sizes[name] = entry.size
            match = BLOB.fullmatch(name)
            require(match is not None or name in {"index.json", "manifest.json", "oci-layout"}, "unexpected OCI member")
            content = Meter(archive.extractfile(entry), min(MAX_ARCHIVE, entry.size))
            prefix = content.read(2)
            if prefix == b"\x1f\x8b":
                require(match is not None, "nonblob gzip member")
                compressed = gzip.GzipFile(fileobj=Prefix(prefix, content), mode="rb")
                try:
                    blob = "sha256:" + match.group(1)
                    selected = next((key for key in pending if key[0] == blob), None)
                    if selected is None:
                        row = PRIVATE["scan_layer"](compressed)
                    else:
                        row_mapped, expanded_bytes = map_layer(compressed, blob, selected[1], pending[selected])
                        mapped.extend(row_mapped)
                        row = {"diff_id": selected[1], "uncompressed_bytes": expanded_bytes, "findings": []}
                finally:
                    compressed.close()
                drain(content)
                total += row["uncompressed_bytes"]
                require(total <= MAX_TOTAL, "total expanded image exceeds limit")
                layers[name] = {"compressed_bytes": content.count, **row}
            else:
                require(entry.size <= MAX_JSON, "unknown large non-gzip blob")
                metadata[name] = json.loads(prefix + small_bytes(content))
            require(content.count == entry.size, "OCI member truncated")
            if match is not None:
                require(content.digest.hexdigest() == match.group(1), "OCI content digest mismatch")
    finally:
        archive.close()
    drain(measured)
    require({"index.json", "manifest.json", "oci-layout"}.issubset(metadata), "required OCI metadata missing")
    ordered = validate_graph(metadata, layers, expected_diff_ids, sizes)
    manifest_path = "blobs/" + metadata["index.json"]["manifests"][0]["digest"].replace(":", "/")
    config_blob = metadata[manifest_path]["config"]["digest"]
    config_path = "blobs/" + config_blob.replace(":", "/")
    mapped.extend(map_config(metadata[config_path], config_candidates, config_blob, sizes[config_path]))
    require(len(mapped) == len(candidates) and len({row["candidate_id"] for row in mapped}) == len(candidates), "candidate mapping incomplete")
    return {"archive_bytes": measured.count, "archive_sha256": measured.digest.hexdigest(), "expanded_bytes": total, "mapped_candidates": sorted(mapped, key=lambda row: row["candidate_id"]), "layers": [{"blob": row["blob"], "diff_id": row["diff_id"]} for row in ordered]}


def inspect_image():
    result = subprocess.run(DOCKER + ["image", "inspect", IMAGE], env=ENV, capture_output=True, timeout=30, check=True)
    require(len(result.stdout) <= MAX_JSON, "inspect output exceeds limit")
    rows = json.loads(result.stdout)
    require(len(rows) == 1 and rows[0]["Id"] == IMAGE and rows[0]["Os"] == "linux" and rows[0]["Architecture"] == "arm64", "image identity mismatch")
    ids = rows[0]["RootFS"]["Layers"]
    require(len(ids) == 20 and len(set(ids)) == 20, "unexpected inspected layer list")
    return ids


def write_exclusive(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
        while payload:
            payload = payload[os.write(descriptor, payload):]
    finally:
        os.close(descriptor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    args = parser.parse_args()
    require(re.fullmatch(r"v[1-9][0-9]*", args.attempt) is not None, "invalid attempt")
    require(EVIDENCE.is_dir() and not EVIDENCE.is_symlink() and EVIDENCE.resolve(strict=True) == EVIDENCE, "noncanonical evidence directory")
    require(shutil.disk_usage(EVIDENCE).free >= 5 * 1024**3, "image stream requires 5 GiB start floor")
    destination = EVIDENCE / ("image-candidate-map-" + args.attempt + ".json")
    require(not destination.exists() and not destination.is_symlink(), "evidence already exists")
    before = {"mapper": digest(Path(__file__)), "private_layer_scanner": digest(PRIVATE_PATH)}
    result = {"attempt": args.attempt, "image": IMAGE, "input_capture_sha256": CAPTURE_SHA256, "scope": "content-free mapping of fixed redacted candidate identities across all historical layers and OCI config", "dependency_hashes_before": before}
    process = None
    timer = None
    expired = threading.Event()
    started = time.monotonic()
    try:
        capture = json.loads(CAPTURE.read_text())
        candidates = capture_candidates(capture)
        ids = inspect_image()
        process = subprocess.Popen(DOCKER + ["image", "save", "--platform", "linux/arm64", IMAGE], env=ENV, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
        timer = threading.Timer(EXPORT_TIMEOUT, lambda: (expired.set(), kill_process_group(process)))
        timer.start()
        result.update(map_archive(process.stdout, ids, candidates))
        require(process.wait(timeout=10) == 0 and not expired.is_set(), "image export failed or timed out")
        require(inspect_image() == ids, "image identity changed during mapping")
        result["status"] = "mapped"
    except BaseException:
        result["status"] = "failed"
        result["error_type"] = type(sys.exc_info()[1]).__name__
    finally:
        if timer is not None:
            timer.cancel()
        if process is not None:
            kill_process_group(process)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                result["status"] = "failed"
                result["error_type"] = "CleanupTimeout"
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        result["free_bytes_after"] = shutil.disk_usage(EVIDENCE).free
        result["dependency_hashes_after"] = {"mapper": digest(Path(__file__)), "private_layer_scanner": digest(PRIVATE_PATH)}
        if result["dependency_hashes_after"] != before:
            result["status"] = "failed"
            result["error_type"] = "DependencyHashChanged"
        write_exclusive(destination, result)
    return 0 if result["status"] == "mapped" else 1


if __name__ == "__main__":
    raise SystemExit(main())
