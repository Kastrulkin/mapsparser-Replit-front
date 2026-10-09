import pytest
from services.business_settings_registry import normalize_patch, public_registry, patch_schema
from services.business_permissions import roles_allow


@pytest.mark.parametrize('patch',[{'owner_id':'someone'},{'is_superadmin':'true'},{'website':'javascript:alert(1)'},{'city':'https://example.ru'},{'timezone':'UTC+3'},{'currency':'123'},{'contact_email':'wrong'}])
def test_invalid_or_internal_settings_are_rejected(patch):
    with pytest.raises(ValueError):normalize_patch(patch)


def test_registry_and_tool_schema_have_identical_fields():
    assert {field['key'] for field in public_registry()}==set(patch_schema()['properties'])
    assert normalize_patch({'site':'example.ru'})=={'website':'https://example.ru'}


def test_master_does_not_inherit_legacy_member_writes():
    assert roles_allow(['master'],'work.facts.write')
    assert not roles_allow(['master'],'operations.write')
    assert roles_allow(['member'],'operations.write')
    assert roles_allow(['admin'],'operations.write')
    assert not roles_allow(['admin'],'team.manage')
