#!/usr/bin/env python3
"""Keep cached Compose releases linked to the current Operator privacy profile.

Run on the VPS from /opt/seo-app. JSON releases contain secrets: never print them.
--apply only updates configuration; recreation is an explicit, separate step.
"""
import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time

SERVICES = ('app', 'worker', 'operator-worker', 'outreach-worker', 'telegram-bot')
ENV = {
    'PII_PROTECTION_ENABLED': 'true',
    'PII_PROTECTION_SCOPE': 'operator_text',
    'PII_ACTIVATION_REQUIRED': 'true',
    'PII_ACTIVATION_CONFIG_FILE': '/run/secrets/localos-pii-activation.json',
    'PII_RUNTIME_TRANSPORT': 'shared',
    'PII_RUNTIME_CONFIG_FILE': '/run/secrets/localos-pii-client.json',
}
FILES = {
    '/run/secrets/localos-pii-client.json': '/etc/localos/pii/client.json',
    '/run/secrets/localos-pii-activation.json': '/etc/localos/pii/activation.json',
}


class Refused(RuntimeError):
    pass


def inherit_policy(config, policy):
    result = copy.deepcopy(config)
    selected = [name for name in SERVICES if name in result.get('services', {})]
    if not selected:
        raise Refused('NO_PROTECTED_SERVICES')
    for name in selected:
        service = result['services'][name]
        parent = {'file': str(policy), 'service': name}
        if service.get('extends') not in (None, parent):
            raise Refused('UNRELATED_INHERITANCE')
        environment = service.get('environment', {})
        if not isinstance(environment, dict):
            raise Refused('EXPECTED_RENDERED_ENVIRONMENT')
        for key in ENV:
            environment.pop(key, None)
        if environment:
            service['environment'] = environment
        else:
            service.pop('environment', None)
        mounts = service.get('volumes', [])
        if any(not isinstance(mount, dict) for mount in mounts):
            raise Refused('EXPECTED_RENDERED_MOUNTS')
        service['volumes'] = [mount for mount in mounts if mount.get('target') not in FILES]
        service['extends'] = parent
    return result, selected


def without_privacy(config, selected):
    result = copy.deepcopy(config)
    for name in selected:
        service = result['services'][name]
        for key in ENV:
            service.get('environment', {}).pop(key, None)
        if not service.get('environment'):
            service.pop('environment', None)
        service['volumes'] = [mount for mount in service.get('volumes', []) if mount.get('target') not in FILES]
        service['volumes'].sort(key=lambda mount: mount.get('target', ''))
    return result


def protected(config, selected):
    for name in selected:
        service = config['services'][name]
        if any(service.get('environment', {}).get(k) != value for k, value in ENV.items()):
            return False
        mounts = {mount.get('target'): mount for mount in service.get('volumes', [])}
        for target, source in FILES.items():
            mount = mounts.get(target, {})
            if (mount.get('type') != 'bind' or mount.get('source') != source
                    or mount.get('read_only') is not True
                    or mount.get('bind', {}).get('create_host_path') is not False):
                return False
        if 'localos-pii-private' not in service.get('networks', {}):
            return False
    return True


def validate_rendering(before, after, selected):
    if without_privacy(before, selected) != without_privacy(after, selected):
        raise Refused('NON_PRIVACY_CONFIGURATION_DRIFT')
    if not protected(after, selected):
        raise Refused('PRIVACY_PROFILE_INVALID')


def private_json(path):
    if path.is_symlink():
        raise Refused('SYMLINK_RELEASE')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > 8 * 1024 * 1024:
            raise Refused('UNSAFE_RELEASE_PERMISSIONS')
        content = b''
        while True:
            part = os.read(fd, 65536)
            if not part:
                break
            content += part
    finally:
        os.close(fd)
    try:
        value = json.loads(content)
    except (ValueError, UnicodeError):
        raise Refused('INVALID_RELEASE_JSON') from None
    return value, content


def write_all(fd, content):
    remaining = memoryview(content)
    while remaining:
        count = os.write(fd, remaining)
        if count <= 0:
            raise Refused('PRIVATE_FILE_WRITE_FAILED')
        remaining = remaining[count:]


def render(path, root, project):
    command = ['docker', 'compose', '--project-directory', str(path.parent),
               '--project-name', project, '-f', str(path), 'config', '--format', 'json']
    p = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=40)
    if p.returncode:
        raise Refused('COMPOSE_RENDER_FAILED')
    return json.loads(p.stdout)


def update_release(path, root, policy, project, apply=False):
    if not path.is_absolute() or not path.resolve().is_relative_to(root.resolve()):
        raise Refused('RELEASE_OUTSIDE_PROJECT')
    if not policy.is_file() or not policy.is_absolute():
        raise Refused('POLICY_FILE_REQUIRED')
    config, original = private_json(path)
    candidate, selected = inherit_policy(config, policy)
    before = render(path, root, project)
    fd, temporary_name = tempfile.mkstemp(prefix='.pii-candidate-', suffix='.json', dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        write_all(fd, (json.dumps(candidate, ensure_ascii=False, indent=2) + '\n').encode())
        os.fsync(fd)
        os.close(fd)
        fd = None
        after = render(temporary, root, project)
        validate_rendering(before, after, selected)
        result = {'status': 'validated', 'services': selected, 'before_protected': protected(before, selected),
                  'after_protected': True, 'non_privacy_preserved': True, 'changed': candidate != config,
                  'source': str(path), 'policy': str(policy),
                  'policy_sha256': hashlib.sha256(policy.read_bytes()).hexdigest()}
        if apply and candidate != config:
            if path.read_bytes() != original:
                raise Refused('RELEASE_CHANGED_DURING_VALIDATION')
            backup = path.with_name(path.stem + '.before-pii-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '.json')
            backup_fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                write_all(backup_fd, original)
                os.fsync(backup_fd)
            finally:
                os.close(backup_fd)
            metadata = path.stat()
            os.chmod(temporary, stat.S_IMODE(metadata.st_mode))
            os.chown(temporary, metadata.st_uid, metadata.st_gid)
            os.replace(temporary, path)
            result.update({'status': 'updated', 'backup': str(backup)})
        return result
    finally:
        if fd is not None:
            os.close(fd)
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compose-file', required=True, type=Path)
    parser.add_argument('--project-dir', type=Path, default=Path('/opt/seo-app'))
    parser.add_argument('--project-name', default='seo-app')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = args.project_dir.resolve()
    policy = root / 'docker/pii-runtime/compose.client.fragment.yml'
    try:
        if args.apply and os.geteuid() != 0:
            raise Refused('ROOT_REQUIRED_FOR_APPLY')
        if not args.compose_file.is_absolute() or not args.compose_file.resolve().is_relative_to(root):
            raise Refused('RELEASE_OUTSIDE_PROJECT')
        lock_path = args.compose_file.with_suffix('.pii.lock')
        lock_fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = update_release(args.compose_file, root, policy, args.project_name, args.apply)
        finally:
            os.close(lock_fd)
        print(json.dumps(result))
        return 0
    except Refused as error:
        print(json.dumps({'status': 'refused', 'reason': str(error)}))
        return 1
    except Exception:
        print(json.dumps({'status': 'refused', 'reason': 'CONFIGURATION_CHECK_FAILED'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
