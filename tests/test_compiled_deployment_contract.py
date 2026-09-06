import copy

import pytest

from scripts.check_compiled_runner_deployment import validate_image_reference, verify_container

DIGEST = "sha256:" + "a" * 64
IMAGE = "registry.example/localos-runner@" + DIGEST


def test_production_runner_reference_cannot_be_a_tag_or_independent_digest():
    validate_image_reference(IMAGE, DIGEST)
    for image, digest in [("runner:latest", DIGEST), (IMAGE, "sha256:" + "b" * 64), ("", DIGEST), ("runner@sha256:a", "sha256:a")]:
        with pytest.raises(ValueError):
            validate_image_reference(image, digest)


def configuration():
    return {"Image": "sha256:actual-config", "State": {"Running": True},
        "Config": {"Env": ["COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST=" + DIGEST, "COMPILED_SCRIPT_RUNNER_SHARED_SECRET=only-transport"]},
        "HostConfig": {"ReadonlyRootfs": True, "Privileged": False, "PortBindings": {}, "Memory": 268435456, "PidsLimit": 32, "NanoCpus": 500000000, "CapAdd": ["SETUID", "SETGID"], "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges:true"]},
        "Mounts": [{"Type": "tmpfs"}], "NetworkSettings": {"Networks": {"compiled_internal": {}}}}


def test_image_inspection_rejects_self_asserted_digest_and_exposed_runtime():
    container = configuration()
    image = {"Id": container["Image"], "RepoDigests": [IMAGE]}
    networks = {"compiled_internal": {"Internal": True}}
    assert verify_container(container, IMAGE, DIGEST, image, networks)["status"] == "passed"
    changed = copy.deepcopy(container)
    changed["Image"] = "sha256:unapproved"
    with pytest.raises(ValueError):
        verify_container(changed, IMAGE, DIGEST, image, networks)
    changed = copy.deepcopy(container)
    changed["Config"]["Env"].append("DATABASE_URL=must-not-be-printed")
    with pytest.raises(ValueError):
        verify_container(changed, IMAGE, DIGEST, image, networks)
    with pytest.raises(ValueError):
        verify_container(container, IMAGE, DIGEST, image, {"compiled_internal": {"Internal": False}})
