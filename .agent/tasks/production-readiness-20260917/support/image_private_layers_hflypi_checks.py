"""In-memory positive and negative controls; no Docker or file extraction."""

import gzip
import hashlib
import io
import json
from pathlib import Path
import runpy
import tarfile


MODULE = runpy.run_path(str(Path(__file__).with_name("image_private_layers_hflypi.py")))
SCAN = MODULE["scan_archive"]


def tar_bytes(members):
    output = io.BytesIO()
    archive = tarfile.open(fileobj=output, mode="w")
    try:
        for name, content in members:
            entry = tarfile.TarInfo(name)
            if isinstance(content, tuple):
                entry.type = tarfile.SYMTYPE
                entry.linkname = content[0]
                archive.addfile(entry)
            else:
                entry.size = len(content)
                archive.addfile(entry, io.BytesIO(content))
    finally:
        archive.close()
    return output.getvalue()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def descriptor(content, media):
    return {"mediaType": media, "digest": "sha256:" + hashlib.sha256(content).hexdigest(), "size": len(content)}


def fixture(layer_members, mutate=None):
    blobs, layers, ids = {}, [], []
    for members in layer_members:
        raw = tar_bytes(members)
        compressed = gzip.compress(raw, mtime=0)
        desc = descriptor(compressed, "application/vnd.oci.image.layer.v1.tar+gzip")
        name = "blobs/" + desc["digest"].replace(":", "/")
        blobs[name] = compressed
        layers.append(desc)
        ids.append("sha256:" + hashlib.sha256(raw).hexdigest())
    config = encoded({"architecture": "arm64", "os": "linux", "rootfs": {"type": "layers", "diff_ids": ids}})
    config_desc = descriptor(config, "application/vnd.oci.image.config.v1+json")
    config_path = "blobs/" + config_desc["digest"].replace(":", "/")
    blobs[config_path] = config
    manifest = encoded({"schemaVersion": 2, "config": config_desc, "layers": layers})
    manifest_desc = descriptor(manifest, "application/vnd.oci.image.manifest.v1+json")
    blobs["blobs/" + manifest_desc["digest"].replace(":", "/")] = manifest
    members = list(sorted(blobs.items()))
    members += [
        ("index.json", encoded({"schemaVersion": 2, "manifests": [{**manifest_desc, "platform": {"architecture": "arm64", "os": "linux"}}]})),
        ("manifest.json", encoded([{"Config": config_path, "Layers": ["blobs/" + d["digest"].replace(":", "/") for d in layers]}])),
        ("oci-layout", encoded({"imageLayoutVersion": "1.0.0"})),
    ]
    if mutate:
        mutate(members)
    return tar_bytes(members), ids


def rejected(payload, ids):
    try:
        SCAN(io.BytesIO(payload), ids)
    except (ValueError, KeyError, tarfile.TarError, EOFError):
        return
    raise AssertionError("invalid image accepted")


def main():
    clean, ids = fixture([[('app/main.py', b'print(1)\n'), ('app/.env.example', b'sample')]])
    result = SCAN(io.BytesIO(clean), ids)
    assert result["finding_count"] == 0 and len(result["layers"]) == 1
    assert result["layers"][0]["regular_files"] == 2
    assert result["layers"][0]["regular_bytes"] == 15
    require = MODULE["require"]
    for name in ("app/.env", "app/tmp-google-docs-one/response.json", "app/.git/config", "app/backups/db.dump"):
        data, expected = fixture([[(name, b'private')]])
        assert SCAN(io.BytesIO(data), expected)["finding_count"] == 1
    layers, expected = fixture([[('app/.env', b'private')], [('app/.wh..env', b'')]])
    result = SCAN(io.BytesIO(layers), expected)
    assert result["finding_count"] == 1 and result["layers"][1]["whiteouts"] == 1
    linked, expected = fixture([[('app/private-link', ('/app/.env',))]])
    assert SCAN(io.BytesIO(linked), expected)["finding_count"] == 1
    original = SCAN.__globals__["PRIVATE_DIGEST"]
    SCAN.__globals__["PRIVATE_DIGEST"] = hashlib.sha256(b'private-response').hexdigest()
    try:
        renamed, expected = fixture([[('usr/share/renamed', b'private-response')]])
        result = SCAN(io.BytesIO(renamed), expected)
        assert result["finding_count"] == 1
        assert result["layers"][0]["findings"][0]["reasons"] == ["known_private_response_digest"]
    finally:
        SCAN.__globals__["PRIVATE_DIGEST"] = original
    rejected(clean, ['sha256:' + '0' * 64])
    rejected(clean, [])
    for name in ('../outside', '/absolute'):
        invalid, expected = fixture([[(name, b'bad')]])
        rejected(invalid, expected)
    duplicate, expected = fixture([[('app/main.py', b'ok')]], lambda rows: rows.append(rows[-1]))
    rejected(duplicate, expected)
    unreferenced, expected = fixture([[('app/main.py', b'ok')]], lambda rows: rows.append(('unknown', b'{}')))
    rejected(unreferenced, expected)
    missing, expected = fixture([[('app/main.py', b'ok')]], lambda rows: rows.pop(0))
    rejected(missing, expected)
    def wrong_digest(rows):
        index = next(i for i, row in enumerate(rows) if row[0].startswith('blobs/') and row[1][:2] == b'\x1f\x8b')
        name, content = rows[index]
        rows[index] = ('blobs/sha256/' + '0' * 64, content)
    invalid, expected = fixture([[('app/main.py', b'ok')]], wrong_digest)
    rejected(invalid, expected)
    def wrong_size(rows):
        index = next(i for i, row in enumerate(rows) if row[0] == 'index.json')
        value = json.loads(rows[index][1])
        value['manifests'][0]['size'] += 1
        rows[index] = ('index.json', encoded(value))
    invalid, expected = fixture([[('app/main.py', b'ok')]], wrong_size)
    rejected(invalid, expected)
    def wrong_order(rows):
        index = next(i for i, row in enumerate(rows) if row[0] == 'manifest.json')
        value = json.loads(rows[index][1])
        value[0]['Layers'].reverse()
        rows[index] = ('manifest.json', encoded(value))
    invalid, expected = fixture([[('app/main.py', b'one')], [('app/other.py', b'two')]], wrong_order)
    rejected(invalid, expected)
    try:
        MODULE['drain'](MODULE['Meter'](io.BytesIO(b'too large'), 2))
    except ValueError:
        pass
    else:
        raise AssertionError('byte limit was not enforced')
    require(MODULE["private_path"]('app/debug_data/log.txt'), 'private path control failed')
    print('OCI all-layer controls: clean, four private families, deleted lower layer, link, renamed digest, identity/order/missing/duplicate/traversal rejection PASS')


if __name__ == "__main__":
    main()
