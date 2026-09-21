"""Read every layer of one pinned local OCI image; never extract or run it.

Scope: private artifact path families and one known private response digest.
This is not a general credential scanner or a claim of secret-free layers.
"""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import shutil
import subprocess
import sys
import threading
import time


IMAGE = "sha256:9d6edac8b6948e239c0bab54564f92f829e5b9dfc93f3ca0626060ffb4e60853"
DOCKER = ["/Applications/Docker.app/Contents/Resources/bin/docker", "--context", "desktop-linux"]
ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "DOCKER_CONFIG": "/Users/alexdemyanov/.docker"}
EVIDENCE = Path("/private/tmp/localos-readiness-20260921.hfLYPi/native/evidence")
PRIVATE_DIGEST = "d1eb5d1c82278fad2d673ffc8111a934b8cf3037c6c5439c5baf2d05895274c2"
BLOB = re.compile(r"blobs/sha256/([0-9a-f]{64})")
CHUNK = 1024 * 1024
MAX_ARCHIVE = 2 * 1024**3
MAX_LAYER = 3 * 1024**3
MAX_TOTAL = 8 * 1024**3
MAX_JSON = 2 * 1024**2


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Meter:
    def __init__(self, source, limit):
        self.source = source
        self.limit = limit
        self.count = 0
        self.digest = hashlib.sha256()

    def read(self, size=-1):
        require(0 <= size <= CHUNK, "unbounded stream read")
        value = self.source.read(size)
        self.count += len(value)
        require(self.count <= self.limit, "stream byte limit exceeded")
        self.digest.update(value)
        return value


class Prefix:
    def __init__(self, prefix, source):
        self.prefix = prefix
        self.source = source

    def read(self, size=-1):
        require(0 <= size <= CHUNK, "unbounded prefix read")
        head, self.prefix = self.prefix[:size], self.prefix[size:]
        return head + self.source.read(size - len(head))


def drain(source):
    while source.read(CHUNK):
        pass


def small_bytes(source, limit=MAX_JSON):
    parts = []
    length = 0
    while True:
        value = source.read(min(CHUNK, limit + 1 - length))
        if not value:
            return b"".join(parts)
        parts.append(value)
        length += len(value)
        require(length <= limit, "metadata exceeds limit")


def normalized(name):
    require(isinstance(name, str) and len(name) <= 8192, "invalid member name")
    path = PurePosixPath(name)
    require(not path.is_absolute() and ".." not in path.parts, "unsafe layer member path")
    return str(path)


def private_path(name):
    parts = PurePosixPath(name).parts
    if parts[:1] != ("app",):
        return False
    forbidden = {".git", ".agent", "db_backups", "backups", "release-backups", ".release-backups", "deploy-backups", ".deploy-backups", ".deploy", ".deploy-staging", "debug_data"}
    return any(part in forbidden or part.startswith("tmp-google-docs-") or (part != ".env.example" and (part == ".env" or part.startswith(".env."))) for part in parts[1:])


def scan_layer(source):
    import tarfile
    layer = Meter(source, MAX_LAYER)
    archive = tarfile.open(fileobj=layer, mode="r|")
    counts = {"entries": 0, "regular_files": 0, "regular_bytes": 0, "links": 0, "whiteouts": 0}
    findings = []
    try:
        for entry in archive:
            counts["entries"] += 1
            require(counts["entries"] <= 500000, "layer member limit exceeded")
            name = normalized(entry.name)
            if PurePosixPath(name).name.startswith(".wh."):
                counts["whiteouts"] += 1
            if entry.isreg():
                require(entry.sparse is None, "sparse layer member unsupported")
                require(0 <= entry.size <= 1024**3, "layer file exceeds limit")
                stream = archive.extractfile(entry)
                require(stream is not None, "regular member content unavailable")
                content = Meter(stream, entry.size)
                drain(content)
                stream.close()
                require(content.count == entry.size, "regular member truncated")
                counts["regular_files"] += 1
                counts["regular_bytes"] += content.count
                reasons = []
                if content.digest.hexdigest() == PRIVATE_DIGEST:
                    reasons.append("known_private_response_digest")
                if private_path(name):
                    reasons.append("private_artifact_path_family")
                if reasons:
                    findings.append({"path_sha256": hashlib.sha256(name.encode()).hexdigest(), "bytes": entry.size, "reasons": reasons})
            elif entry.issym() or entry.islnk():
                counts["links"] += 1
                if private_path(name) or private_path(entry.linkname.lstrip("/")):
                    findings.append({"path_sha256": hashlib.sha256(name.encode()).hexdigest(), "reasons": ["private_artifact_link"]})
            else:
                require(entry.isdir() or entry.isdev() or entry.isfifo(), "unsupported layer member kind")
    finally:
        archive.close()
    drain(layer)
    return {**counts, "uncompressed_bytes": layer.count, "diff_id": "sha256:" + layer.digest.hexdigest(), "findings": findings}


def validate_graph(metadata, layers, expected_diff_ids, sizes):
    index = metadata["index.json"]
    require(metadata["oci-layout"] == {"imageLayoutVersion": "1.0.0"}, "unsupported OCI layout")
    require(index.get("schemaVersion") == 2 and len(index.get("manifests", [])) == 1, "ambiguous OCI index")
    descriptor = index["manifests"][0]
    require(descriptor.get("platform") == {"architecture": "arm64", "os": "linux"}, "wrong exported platform")
    manifest_path = "blobs/" + descriptor["digest"].replace(":", "/")
    require(descriptor.get("mediaType") == "application/vnd.oci.image.manifest.v1+json" and descriptor.get("size") == sizes[manifest_path], "invalid manifest descriptor")
    manifest = metadata[manifest_path]
    require(manifest.get("schemaVersion") == 2, "invalid OCI manifest")
    config_path = "blobs/" + manifest["config"]["digest"].replace(":", "/")
    require(manifest["config"].get("mediaType") == "application/vnd.oci.image.config.v1+json" and manifest["config"].get("size") == sizes[config_path], "invalid config descriptor")
    config = metadata[config_path]
    require(config.get("architecture") == "arm64" and config.get("os") == "linux", "wrong image config platform")
    require(config.get("rootfs", {}).get("type") == "layers" and config["rootfs"].get("diff_ids") == expected_diff_ids, "image rootfs differs from inspected identity")
    descriptors = manifest.get("layers", [])
    require(len(descriptors) == len(expected_diff_ids), "image layer count mismatch")
    ordered = []
    for descriptor, diff_id in zip(descriptors, expected_diff_ids):
        name = "blobs/" + descriptor["digest"].replace(":", "/")
        row = layers[name]
        require(descriptor.get("mediaType") == "application/vnd.oci.image.layer.v1.tar+gzip", "unsupported layer encoding")
        require(row["compressed_bytes"] == descriptor["size"] and row["diff_id"] == diff_id, "layer descriptor or diff-id mismatch")
        ordered.append({"blob": descriptor["digest"], **row})
    legacy = metadata["manifest.json"]
    require(len(legacy) == 1 and legacy[0].get("Config") == config_path, "Docker config descriptor mismatch")
    require(legacy[0].get("Layers") == ["blobs/" + row["blob"].replace(":", "/") for row in ordered], "Docker layer ordering mismatch")
    require(set(layers) == set(legacy[0]["Layers"]), "unreferenced or missing layers")
    require(set(metadata) == {"index.json", "manifest.json", "oci-layout", manifest_path, config_path}, "unreferenced image metadata")
    return ordered


def scan_archive(source, expected_diff_ids):
    import tarfile
    measured = Meter(source, MAX_ARCHIVE)
    archive = tarfile.open(fileobj=measured, mode="r|")
    seen, metadata, layers, sizes = set(), {}, {}, {}
    total = 0
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
                    row = scan_layer(compressed)
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
    ordered = validate_graph(metadata, layers, expected_diff_ids, sizes)
    return {"archive_bytes": measured.count, "archive_sha256": measured.digest.hexdigest(), "expanded_bytes": total, "layers": ordered, "finding_count": sum(len(row["findings"]) for row in ordered)}


def inspect_image():
    result = subprocess.run(DOCKER + ["image", "inspect", IMAGE], env=ENV, capture_output=True, timeout=30, check=True)
    require(len(result.stdout) <= MAX_JSON, "inspect output exceeds limit")
    rows = json.loads(result.stdout)
    require(len(rows) == 1 and rows[0]["Id"] == IMAGE and rows[0]["Os"] == "linux" and rows[0]["Architecture"] == "arm64", "image identity mismatch")
    ids = rows[0]["RootFS"]["Layers"]
    require(len(ids) == 20 and len(set(ids)) == 20, "unexpected inspected layer list")
    return ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    args = parser.parse_args()
    require(re.fullmatch(r"v[1-9][0-9]*", args.attempt) is not None, "invalid attempt")
    require(EVIDENCE.is_dir() and not EVIDENCE.is_symlink() and EVIDENCE.resolve(strict=True) == EVIDENCE, "noncanonical evidence directory")
    require(shutil.disk_usage(EVIDENCE).free >= 5 * 1024**3, "image stream requires 5 GiB start floor")
    destination = EVIDENCE / ("image-private-layers-" + args.attempt + ".json")
    require(not destination.exists() and not destination.is_symlink(), "evidence already exists")
    started = time.monotonic()
    result = {"image": IMAGE, "attempt": args.attempt, "scope": "all-layer-private-path-families-and-one-known-file-digest", "general_secret_scan": False}
    process = None
    timer = None
    expired = threading.Event()
    try:
        ids = inspect_image()
        process = subprocess.Popen(DOCKER + ["image", "save", "--platform", "linux/arm64", IMAGE], env=ENV, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
        def timeout():
            expired.set()
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
        timer = threading.Timer(180, timeout)
        timer.start()
        result.update(scan_archive(process.stdout, ids))
        require(process.wait(timeout=10) == 0 and not expired.is_set(), "image export failed or timed out")
        require(inspect_image() == ids, "image identity changed during scan")
        result["status"] = "passed" if result["finding_count"] == 0 else "findings_require_review"
    except BaseException:
        result["status"] = "failed"
        result["error_type"] = type(sys.exception()).__name__
        result["error"] = str(sys.exception())[:500]
    finally:
        if timer is not None:
            timer.cancel()
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        result["free_bytes_after"] = shutil.disk_usage(EVIDENCE).free
        result["controller_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            payload = (json.dumps(result, indent=2) + "\n").encode()
            while payload:
                count = os.write(descriptor, payload)
                payload = payload[count:]
        finally:
            os.close(descriptor)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
