#!/usr/bin/env python3
"""Host-side image/isolation proof. Never print container environment values."""
import argparse
import json
import os
import re
import subprocess


def validate_image_reference(image, digest):
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest or ""):
        raise ValueError("a complete sha256 manifest digest is required")
    repository, separator, pinned = str(image or "").rpartition("@")
    if separator != "@" or not re.fullmatch(r"[A-Za-z0-9._:/-]+", repository) or pinned != digest:
        raise ValueError("runner image must be repository@the-approved-sha256-digest")


def inspect(kind, name):
    result = subprocess.run(["docker", kind, "inspect", name], check=True, capture_output=True, text=True)
    values = json.loads(result.stdout)
    if not isinstance(values, list) or len(values) != 1:
        raise ValueError("expected one Docker resource")
    return values[0]


def verify_container(container, expected_image, digest, image_details, network_details):
    validate_image_reference(expected_image, digest)
    if not container.get("State", {}).get("Running"):
        raise ValueError("runner container is not running")
    if container.get("Image") != image_details.get("Id") or not any(value.endswith("@" + digest) for value in image_details.get("RepoDigests", [])):
        raise ValueError("actual container image differs from approved repository digest")
    configuration = container.get("Config", {})
    environment = dict(item.split("=", 1) for item in configuration.get("Env", []) if "=" in item)
    if environment.get("COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST") != digest:
        raise ValueError("transport digest differs from the inspected image")
    forbidden = {name for name in environment if name != "COMPILED_SCRIPT_RUNNER_SHARED_SECRET" and any(part in name for part in ("DATABASE", "POSTGRES", "API_KEY", "TOKEN", "PASSWORD", "SECRET"))}
    if forbidden:
        raise ValueError("unexpected credentials in runner environment")
    host = container.get("HostConfig", {})
    if not host.get("ReadonlyRootfs") or host.get("Privileged") or host.get("PortBindings"):
        raise ValueError("runner must have read-only root and no public ports or privileges")
    if any(mount.get("Type") != "tmpfs" for mount in container.get("Mounts", [])):
        raise ValueError("runner cannot mount host files or volumes")
    if not 0 < host.get("Memory", 0) <= 256 * 1024 * 1024 or not 0 < host.get("PidsLimit", 0) <= 32:
        raise ValueError("runner memory/PID limits are missing or too large")
    if not 0 < host.get("NanoCpus", 0) <= 1_000_000_000:
        raise ValueError("runner CPU limit is missing or too large")
    caps = {value.removeprefix("CAP_") for value in host.get("CapAdd", [])}
    drops = {value.removeprefix("CAP_") for value in host.get("CapDrop", [])}
    if caps - {"SETUID", "SETGID"} or "ALL" not in drops or "no-new-privileges:true" not in host.get("SecurityOpt", []):
        raise ValueError("runner capability restrictions are missing")
    attached = set(container.get("NetworkSettings", {}).get("Networks", {}))
    if not attached or attached != set(network_details) or not all(network_details[name].get("Internal") for name in attached):
        raise ValueError("runner must attach only to inspected internal networks")
    return {"status": "passed", "manifest_digest": digest, "container_image_id": container["Image"], "internal_networks": sorted(attached)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=os.getenv("COMPILED_SCRIPT_RUNNER_IMAGE", ""))
    parser.add_argument("--digest", default=os.getenv("COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST", ""))
    parser.add_argument("--container", help="Verify the live container after deploying the pinned image")
    args = parser.parse_args()
    validate_image_reference(args.image, args.digest)
    if not args.container:
        print(json.dumps({"status": "reference_valid", "image": args.image}))
        return
    container = inspect("container", args.container)
    networks = {name: inspect("network", name) for name in container.get("NetworkSettings", {}).get("Networks", {})}
    result = verify_container(container, args.image, args.digest, inspect("image", args.image), networks)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
