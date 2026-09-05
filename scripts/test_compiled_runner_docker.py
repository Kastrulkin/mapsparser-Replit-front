#!/usr/bin/env python3
"""Destructive only to resources named localos-compiled-it-* created here."""
import hashlib
import hmac
import json
import secrets
import subprocess
import sys
import time


ROOT = __file__.rsplit("/scripts/", 1)[0]
IMAGE = "localos-compiled-it:latest"
NETWORK = ""
GATEWAY = ""
SECRET = "i" * 32


def command(args, *, input_text=None, check=True):
    completed = subprocess.run(args, cwd=ROOT, input=input_text, text=True, capture_output=True)
    if check and completed.returncode:
        raise RuntimeError("command failed: %s\n%s" % (" ".join(args), completed.stderr))
    return completed


def artifact(source, fixtures, digest, *, output_schema=None):
    manifest = {
        "kind": "localos.python_transform.v1",
        "input_schema": {"type": "object", "properties": {"number": {"type": "integer"}}, "required": []},
        "output_schema": output_schema or {"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"]},
        "runtime_version": "python-3.12-restricted-v1",
        "dependencies": [],
        "runner_image_digest": digest,
    }
    canonical = json.dumps({"source": source.replace("\r\n", "\n"), "manifest": manifest, "fixtures": fixtures}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {"source": source, "manifest": manifest, "fixtures": fixtures, "artifact_hash": "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()}


CLIENT = r'''
import hashlib,hmac,http.client,json,os,secrets,sys,time
secret=os.environ['SECRET']; payload=json.loads(sys.stdin.read()); raw=json.dumps(payload,separators=(',',':')).encode()
timestamp=str(int(time.time())); nonce=os.environ.get('NONCE',secrets.token_urlsafe(18)); signature=os.environ.get('SIGNATURE') or hmac.new(secret.encode(),timestamp.encode()+b'.'+nonce.encode()+b'.'+raw,hashlib.sha256).hexdigest()
c=http.client.HTTPConnection(os.environ['GATEWAY'],8091,timeout=5); c.request('POST','/v1/run',raw,{'Content-Type':'application/json','X-Compiled-Timestamp':timestamp,'X-Compiled-Nonce':nonce,'X-Compiled-Signature':signature}); r=c.getresponse(); print(json.dumps({'status':r.status,'body':r.read().decode(),'headers':dict(r.getheaders()),'nonce':nonce}))
'''


def request(value, *, nonce=None, signature=None):
    env = ["-e", "SECRET=" + SECRET, "-e", "GATEWAY=" + GATEWAY]
    if nonce:
        env += ["-e", "NONCE=" + nonce]
    if signature:
        env += ["-e", "SIGNATURE=" + signature]
    completed = command(["docker", "run", "--rm", "-i", "--network", NETWORK, *env, "python:3.12-slim", "python", "-I", "-S", "-c", CLIENT], input_text=json.dumps(value), check=False)
    if completed.returncode:
        raise RuntimeError(completed.stderr)
    return json.loads(completed.stdout)


def expect_failure(source, label, digest, *, output_schema=None):
    value = artifact(source, [], digest, output_schema=output_schema)
    response = request({**value, "input": {}})
    if response["status"] != 422:
        raise AssertionError(label + " did not return an explicit execution rejection: " + str(response["status"]))


def main():
    global NETWORK, GATEWAY
    suffix = secrets.token_hex(6)
    NETWORK = "localos-compiled-it-net-" + suffix
    GATEWAY = "localos-compiled-it-gateway-" + suffix
    created_network = False
    created_gateway = False
    try:
        command(["docker", "build", "-t", IMAGE, "docker/compiled-script-runner"])
        image_id = command(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"]).stdout.strip()
        digest = image_id
        command(["docker", "network", "create", "--internal", NETWORK])
        created_network = True
        command([
            "docker", "run", "-d", "--name", GATEWAY, "--network", NETWORK, "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=8m", "--cap-drop", "ALL", "--cap-add", "SETUID", "--cap-add", "SETGID",
            "--security-opt", "no-new-privileges:true", "--pids-limit", "32", "--memory", "128m", "--cpus", "0.50",
            "-e", "COMPILED_SCRIPT_RUNNER_SHARED_SECRET=" + SECRET, "-e", "COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST=" + digest, image_id,
        ])
        created_gateway = True
        time.sleep(1)
        fixtures = [{"input": {"number": 1}, "expected": {"value": 8}, "source": "user"}, {"input": {"number": 2}, "expected": {"value": 9}, "source": "generator"}]
        good = artifact("def process(input_payload):\n    return {'value': input_payload.get('number', 0) + 7}\n", fixtures, digest)
        first = request({**good, "input": {"number": 3}})
        if first["status"] != 200 or json.loads(first["body"])["value"] != 10:
            raise AssertionError("actual signed source did not execute")
        for fixture in fixtures:
            outcome = request({**good, "input": fixture["input"]})
            if outcome["status"] != 200 or {key: value for key, value in json.loads(outcome["body"]).items() if key not in {"artifact_hash", "runtime_ai_calls", "external_effects"}} != fixture["expected"]:
                raise AssertionError("fixture mismatch was not visible")
        wrong = fixtures[:1] + [{"input": {"number": 2}, "expected": {"value": 99}, "source": "user"}]
        if json.loads(request({**good, "input": wrong[1]["input"]})["body"])["value"] == wrong[1]["expected"]["value"]:
            raise AssertionError("wrong expectation did not differ from actual source")
        bad_signature = request({**good, "input": {}}, signature="0" * 64)
        if bad_signature["status"] != 401:
            raise AssertionError("bad signature accepted")
        replay_nonce = "replay-proof"
        if request({**good, "input": {}}, nonce=replay_nonce)["status"] != 200 or request({**good, "input": {}}, nonce=replay_nonce)["status"] != 401:
            raise AssertionError("nonce replay was not rejected")
        changed = dict(good); changed["source"] = "def process(input_payload):\n    return {'value': 1}\n"
        if request({**changed, "input": {}})["status"] != 422:
            raise AssertionError("modified source/hash accepted")
        expect_failure("def process(input_payload):\n    while True:\n        pass\n", "timeout", digest)
        expect_failure("import socket\ndef process(input_payload):\n    return {}\n", "network import", digest)
        expect_failure("def process(input_payload):\n    return {'x': open('/proc/1/environ').read()}\n", "proc secret", digest)
        expect_failure("def process(input_payload):\n    return {'x': 'a' * 2000000}\n", "output limit", digest)
        expect_failure("def process(input_payload):\n    return {'value': 'wrong'}\n", "output schema", digest)
        expect_failure("def process(input_payload):\n    return {}\n", "required output field", digest)
        expect_failure("def process(input_payload):\n    return {'value': 3}\n", "output enum", digest,
            output_schema={"type":"object", "properties":{"value":{"type":"integer","enum":[1,2]}}, "required":["value"]})
        expect_failure("def process(input_payload):\n    return {'value': 11}\n", "output maximum", digest,
            output_schema={"type":"object", "properties":{"value":{"type":"integer","maximum":10}}, "required":["value"]})
        set_program = artifact("def process(input_payload):\n    return {'value': ','.join(set(['north','south','east','west']))}\n", [], digest,
            output_schema={"type":"object", "properties":{"value":{"type":"string"}}, "required":["value"]})
        repeated = [request({**set_program,"input":{}}) for _attempt in range(3)]
        if any(item["status"] != 200 for item in repeated) or len({json.loads(item["body"])["value"] for item in repeated}) != 1:
            raise AssertionError("same source/input used an uncontrolled hash seed")
        final = request({**good, "input": {"number": 4}})
        if final["status"] != 200 or json.loads(final["body"])["value"] != 11:
            raise AssertionError("gateway did not recover after rejected jobs")
        print(json.dumps({"status": "passed", "image_id": image_id, "gateway": GATEWAY, "fixtures": len(fixtures)}))
    finally:
        if created_gateway:
            command(["docker", "rm", "-f", GATEWAY], check=False)
        if created_network:
            command(["docker", "network", "rm", NETWORK], check=False)


if __name__ == "__main__":
    main()
