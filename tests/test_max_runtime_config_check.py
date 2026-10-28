import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('max_runtime_check',Path(__file__).parents[1]/'scripts/check_max_runtime.py')
check=importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def test_detects_container_restart_without_environment_recreation():
    expected={'MAX_ENABLED':'true','MAX_BOT_TOKEN':'synthetic-token'}
    old={'MAX_ENABLED':'false','MAX_BOT_TOKEN':'synthetic-token'}
    assert check.mismatches(expected,check.fingerprint(old))==['MAX_ENABLED']


def test_credentials_are_compared_without_disclosing_values():
    expected={'MAX_ENABLED':'true','MAX_BOT_TOKEN':'synthetic-token'}
    result=check.fingerprint(expected)
    assert 'synthetic-token' not in repr(result)
    assert check.mismatches(expected,result)==[]
