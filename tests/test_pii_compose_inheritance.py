"""Cached releases must keep fresh privacy policy and preserve business settings."""
import copy
import importlib.util
import json
from pathlib import Path
import stat

import pytest

SPEC = importlib.util.spec_from_file_location('pii_compose_inheritance', Path(__file__).parents[1] / 'scripts/ensure_pii_compose_inheritance.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def release():
    return {'name': 'synthetic-project', 'services': {'outreach-worker': {
        'image': 'synthetic-image:fixed', 'command': ['python', 'src/worker.py'],
        'environment': {'BUSINESS_SETTING': 'synthetic-sensitive-value', 'PII_PROTECTION_ENABLED': 'false',
                        'PII_RUNTIME_TRANSPORT': 'shared'},
        'volumes': [{'type': 'bind', 'source': '/synthetic/src', 'target': '/app/src', 'read_only': True},
                    {'type': 'bind', 'source': '/old/client.json', 'target': '/run/secrets/localos-pii-client.json'}],
        'networks': {'default': {}, 'localos-pii-private': {}}, 'stop_grace_period': '15m0s',
        'deploy': {'resources': {'limits': {'memory': '256m'}}}},
        'postgres': {'image': 'synthetic-postgres', 'environment': {'SYNTHETIC': 'unchanged'}}},
        'networks': {'default': {}, 'localos-pii-private': {'external': True}}}


def rendered(base):
    result = copy.deepcopy(base)
    for name in module.SERVICES:
        if name not in result['services']:
            continue
        service = result['services'][name]
        if 'extends' not in service:
            continue
        service.pop('extends')
        service.setdefault('environment', {}).update(module.ENV)
        service['volumes'] = [v for v in service.get('volumes', []) if v.get('target') not in module.FILES]
        service['volumes'] += [{'type': 'bind', 'source': src, 'target': dst, 'read_only': True,
                               'bind': {'create_host_path': False}} for dst, src in module.FILES.items()]
    return result


def test_cached_release_does_not_freeze_or_shadow_privacy_policy():
    original = release()
    saved = copy.deepcopy(original)
    candidate, names = module.inherit_policy(original, Path('/synthetic/policy.yml'))
    worker = candidate['services']['outreach-worker']
    assert names == ['outreach-worker']
    assert worker['extends'] == {'file': '/synthetic/policy.yml', 'service': 'outreach-worker'}
    assert not set(module.ENV).intersection(worker['environment'])
    assert all(v['target'] not in module.FILES for v in worker['volumes'])
    assert original == saved
    after = rendered(candidate)
    module.validate_rendering(original, after, names)
    assert after['services']['postgres'] == original['services']['postgres']
    assert after['services']['outreach-worker']['environment']['BUSINESS_SETTING'] == 'synthetic-sensitive-value'
    assert after['services']['outreach-worker']['stop_grace_period'] == '15m0s'


def test_repeated_normalization_is_idempotent():
    candidate, _ = module.inherit_policy(release(), Path('/synthetic/policy.yml'))
    again, _ = module.inherit_policy(candidate, Path('/synthetic/policy.yml'))
    assert candidate == again


@pytest.mark.parametrize('field,value', [('command', ['different']), ('image', 'different-image'),
                                         ('stop_grace_period', '1s'), ('networks', {'other': {}})])
def test_non_privacy_changes_refuse_release(field, value):
    before = release()
    candidate, names = module.inherit_policy(before, Path('/synthetic/policy.yml'))
    after = rendered(candidate)
    after['services']['outreach-worker'][field] = value
    pytest.raises(module.Refused, module.validate_rendering, before, after, names)


def test_secret_environment_change_is_refused():
    before = release()
    candidate, names = module.inherit_policy(before, Path('/synthetic/policy.yml'))
    after = rendered(candidate)
    after['services']['outreach-worker']['environment']['BUSINESS_SETTING'] = 'different'
    pytest.raises(module.Refused, module.validate_rendering, before, after, names)


def test_writable_or_auto_created_privacy_mount_is_refused():
    before = release()
    candidate, names = module.inherit_policy(before, Path('/synthetic/policy.yml'))
    after = rendered(candidate)
    after['services']['outreach-worker']['volumes'][-1]['read_only'] = False
    pytest.raises(module.Refused, module.validate_rendering, before, after, names)


def test_existing_unrelated_parent_cannot_be_overwritten():
    before = release()
    before['services']['outreach-worker']['extends'] = {'file': '/business/parent.yml', 'service': 'base'}
    pytest.raises(module.Refused, module.inherit_policy, before, Path('/synthetic/policy.yml'))


def test_private_release_permissions_and_symlink_are_checked(tmp_path):
    path = tmp_path/'release.json'
    path.write_text(json.dumps(release()))
    path.chmod(0o644)
    pytest.raises(module.Refused, module.private_json, path)
    path.chmod(0o600)
    assert module.private_json(path)[0] == release()
    link = tmp_path/'link.json'
    link.symlink_to(path)
    pytest.raises(module.Refused, module.private_json, link)


def test_dry_run_does_not_change_original(tmp_path, monkeypatch):
    source = tmp_path/'release.json';source.write_text(json.dumps(release()));source.chmod(0o600)
    policy = tmp_path/'policy.yml';policy.write_text('synthetic policy')
    original = source.read_bytes()
    monkeypatch.setattr(module, 'render', lambda p, root, project: rendered(json.loads(p.read_text())))
    result = module.update_release(source, tmp_path, policy, 'synthetic', False)
    assert result['before_protected'] is False and result['after_protected'] is True
    assert source.read_bytes() == original and list(tmp_path.glob('*.before-pii-*')) == []


def test_apply_preserves_exact_backup_and_secret_permissions(tmp_path, monkeypatch):
    source = tmp_path/'release.json';source.write_text(json.dumps(release()));source.chmod(0o600)
    policy = tmp_path/'policy.yml';policy.write_text('synthetic policy')
    original = source.read_bytes()
    monkeypatch.setattr(module, 'render', lambda p, root, project: rendered(json.loads(p.read_text())))
    result = module.update_release(source, tmp_path, policy, 'synthetic', True)
    assert Path(result['backup']).read_bytes() == original
    assert stat.S_IMODE(source.stat().st_mode) == 0o600
    assert stat.S_IMODE(Path(result['backup']).stat().st_mode) == 0o600
    assert json.loads(source.read_text())['services']['outreach-worker']['extends']['file'] == str(policy)


def test_failed_validation_leaves_release_untouched(tmp_path, monkeypatch):
    source = tmp_path/'release.json';source.write_text(json.dumps(release()));source.chmod(0o600)
    policy = tmp_path/'policy.yml';policy.write_text('synthetic policy')
    original = source.read_bytes()
    def invalid(p, root, project):
        result = rendered(json.loads(p.read_text()))
        if p != source:
            result['services']['postgres']['image'] = 'unexpected'
        return result
    monkeypatch.setattr(module, 'render', invalid)
    pytest.raises(module.Refused, module.update_release, source, tmp_path, policy, 'synthetic', True)
    assert source.read_bytes() == original and list(tmp_path.glob('*.before-pii-*')) == []
