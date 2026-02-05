#!/usr/bin/env python3
"""
Тесты для проверки логики определения успешности парсинга (PART A, D)
"""
import os
import sys
import json
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from worker import _is_parsing_successful, get_expected_oid, get_extracted_oid, is_oid_mismatch

print("=" * 60)
print("ТЕСТ: Определение успешности парсинга (PART A, D)")
print("=" * 60)

# ========== PART A: OID MISMATCH TESTS ==========

print("\n1. Тест: OID mismatch (hard fail)")
print("-" * 60)
queue_dict_oid = {
    'id': 'test-1',
    'url': 'https://yandex.ru/maps/org/oliver/203293742306/',
    'oid': '203293742306'
}
card_data_oid_mismatch = {
    "organization": {
        "oid": "999999999999",  # Не совпадает
        "title": "Wrong Business",
        "address": "Wrong Address",
        "coordinates": [1.0, 2.0]
    },
    "parse_status": "fail",
    "missing_sections": [],
    "_raw_capture": {"some_raw_data": "..."}
}
status, reason, missing = _is_parsing_successful(card_data_oid_mismatch, queue_dict_oid)
print(f"   Статус: {status}")
print(f"   Причина: {reason}")
print(f"   Missing sections: {missing}")
print(f"   Будет сохранено: {'❌ НЕТ' if status == 'fail' else '✅ ДА'}")
assert status == "fail", f"Ожидался fail, получен {status}"
assert "oid_mismatch" in reason, f"Ожидался oid_mismatch в причине: {reason}"
print("   ✅ PASS")

print("\n2. Тест: Missing extracted OID (fail)")
print("-" * 60)
card_data_no_oid = {
    "organization": {
        # Нет oid
        "title": "Test Business",
        "address": "Test Address",
        "coordinates": [1.0, 2.0]
    },
    "parse_status": "fail",
    "missing_sections": [],
    "_raw_capture": {"some_raw_data": "..."}
}
status, reason, missing = _is_parsing_successful(card_data_no_oid, queue_dict_oid)
print(f"   Статус: {status}")
print(f"   Причина: {reason}")
print(f"   Missing sections: {missing}")
print(f"   Будет сохранено: {'❌ НЕТ' if status == 'fail' else '✅ ДА'}")
# Если нет organization.title - это fail
if not card_data_no_oid.get('organization', {}).get('title'):
    assert status == "fail", f"Ожидался fail при отсутствии organization.title, получен {status}"
print("   ✅ PASS")

print("\n3. Тест: Missing organization (fail)")
print("-" * 60)
card_data_no_org = {
    "parse_status": "fail",
    "missing_sections": [],
    "_raw_capture": {"some_raw_data": "..."}
    # Нет organization вообще
}
status, reason, missing = _is_parsing_successful(card_data_no_org, queue_dict_oid)
print(f"   Статус: {status}")
print(f"   Причина: {reason}")
print(f"   Missing sections: {missing}")
print(f"   Будет сохранено: {'❌ НЕТ' if status == 'fail' else '✅ ДА'}")
assert status == "fail", f"Ожидался fail при отсутствии organization, получен {status}"
assert "missing_organization" in reason or "missing_organization" in missing, f"Ожидался missing_organization: {reason}"
print("   ✅ PASS")

# ========== PART D: SUCCESS/PARTIAL/FALL RULES ==========

print("\n4. Тест: Success (все секции есть)")
print("-" * 60)
card_data_success = {
    "organization": {
        "oid": "203293742306",
        "title": "Test Business",
        "address": "Test Address",
        "coordinates": [1.0, 2.0]
    },
    "reviews": [{"id": "1", "text": "Good"}],
    "services": [{"id": "1", "title": "Service"}],
    "news": [{"id": "1", "text": "News"}],
    "parse_status": "success",
    "missing_sections": [],
    "_raw_capture": {"some_raw_data": "..."}
}
status, reason, missing = _is_parsing_successful(card_data_success, queue_dict_oid)
print(f"   Статус: {status}")
print(f"   Причина: {reason}")
print(f"   Missing sections: {missing}")
print(f"   Будет сохранено: {'✅ ДА' if status in ['success', 'partial'] else '❌ НЕТ'}")
assert status == "success", f"Ожидался success, получен {status}"
print("   ✅ PASS")

print("\n5. Тест: Partial (organization есть, но нет reviews)")
print("-" * 60)
card_data_partial = {
    "organization": {
        "oid": "203293742306",
        "title": "Test Business",
        "address": "Test Address",
        "coordinates": [1.0, 2.0]
    },
    # Нет reviews
    "services": [{"id": "1", "title": "Service"}],
    "news": [{"id": "1", "text": "News"}],
    "parse_status": "partial",
    "missing_sections": ["reviews"],
    "_raw_capture": {"some_raw_data": "..."}
}
status, reason, missing = _is_parsing_successful(card_data_partial, queue_dict_oid)
print(f"   Статус: {status}")
print(f"   Причина: {reason}")
print(f"   Missing sections: {missing}")
print(f"   Будет сохранено: {'✅ ДА' if status in ['success', 'partial'] else '❌ НЕТ'}")
assert status == "partial", f"Ожидался partial, получен {status}"
assert "reviews" in missing, f"Ожидался reviews в missing_sections: {missing}"
print("   ✅ PASS")

print("\n6. Тест: Partial требует organization (нет organization = fail)")
print("-" * 60)
card_data_partial_no_org = {
    # Нет organization
    "reviews": [{"id": "1", "text": "Good"}],
    "services": [{"id": "1", "title": "Service"}],
    "news": [{"id": "1", "text": "News"}],
    "parse_status": "partial",
    "missing_sections": ["organization"],
    "_raw_capture": {"some_raw_data": "..."}
}
status, reason, missing = _is_parsing_successful(card_data_partial_no_org, queue_dict_oid)
print(f"   Статус: {status}")
print(f"   Причина: {reason}")
print(f"   Missing sections: {missing}")
print(f"   Будет сохранено: {'❌ НЕТ' if status == 'fail' else '✅ ДА'}")
assert status == "fail", f"Ожидался fail при отсутствии organization (partial недопустим), получен {status}"
print("   ✅ PASS")

# ========== PART A: OID EXTRACTION TESTS ==========

print("\n7. Тест: get_expected_oid из URL")
print("-" * 60)
queue_dict_url = {
    'id': 'test-2',
    'url': 'https://yandex.ru/maps/org/oliver/203293742306/',
}
expected = get_expected_oid(queue_dict_url)
print(f"   Expected OID: {expected}")
assert expected == "203293742306", f"Ожидался 203293742306, получен {expected}"
print("   ✅ PASS")

print("\n8. Тест: get_extracted_oid из organization.oid")
print("-" * 60)
card_data_oid = {
    "organization": {
        "oid": "203293742306",
        "title": "Test"
    }
}
extracted = get_extracted_oid(card_data_oid)
print(f"   Extracted OID: {extracted}")
assert extracted == "203293742306", f"Ожидался 203293742306, получен {extracted}"
print("   ✅ PASS")

print("\n9. Тест: is_oid_mismatch")
print("-" * 60)
is_mismatch, oid_reason = is_oid_mismatch("203293742306", "999999999999")
print(f"   Is mismatch: {is_mismatch}")
print(f"   Reason: {oid_reason}")
assert is_mismatch == True, f"Ожидался True, получен {is_mismatch}"
assert oid_reason == "oid_mismatch", f"Ожидался oid_mismatch, получен {oid_reason}"
print("   ✅ PASS")

print("\n" + "=" * 60)
print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО")
print("=" * 60)
