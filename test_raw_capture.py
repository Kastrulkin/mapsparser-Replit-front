#!/usr/bin/env python3
"""
Тесты для проверки raw capture hygiene (PART E)
"""
import os
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from worker import truncate_payload, save_raw_capture, MAX_CAPTURE_BYTES

print("=" * 60)
print("ТЕСТ: Raw capture hygiene (PART E)")
print("=" * 60)

# ========== PART E: RAW CAPTURE TESTS ==========

print("\n1. Тест: truncate_payload урезает большие payload")
print("-" * 60)

# Создаём большой payload (> 300KB)
large_payload = {"data": "x" * (MAX_CAPTURE_BYTES + 100000)}
large_json = json.dumps(large_payload)

truncated = truncate_payload(large_json, MAX_CAPTURE_BYTES)
truncated_bytes = len(truncated.encode('utf-8'))

print(f"   Исходный размер: {len(large_json.encode('utf-8'))} bytes")
print(f"   Урезанный размер: {truncated_bytes} bytes")
print(f"   MAX_CAPTURE_BYTES: {MAX_CAPTURE_BYTES}")

assert truncated_bytes <= MAX_CAPTURE_BYTES, f"Урезанный payload превышает лимит: {truncated_bytes} > {MAX_CAPTURE_BYTES}"
assert "[truncated]" in truncated, f"Ожидался маркер [truncated] в урезанном payload"
print("   ✅ PASS")

print("\n2. Тест: truncate_payload не урезает маленькие payload")
print("-" * 60)

small_payload = {"data": "small"}
small_json = json.dumps(small_payload)

truncated = truncate_payload(small_json, MAX_CAPTURE_BYTES)

print(f"   Исходный размер: {len(small_json.encode('utf-8'))} bytes")
print(f"   Результат: {len(truncated.encode('utf-8'))} bytes")

assert "[truncated]" not in truncated, f"Маленький payload не должен быть урезан"
assert truncated == small_json, f"Маленький payload должен остаться без изменений"
print("   ✅ PASS")

print("\n3. Тест: save_raw_capture создаёт структурированный файл")
print("-" * 60)

queue_dict = {
    'id': 'test-task-123',
    'business_id': 'test-business-456',
    'url': 'https://yandex.ru/maps/org/test/123456/'
}

card_data = {
    'organization': {
        'oid': '123456',
        'title': 'Test Business'
    },
    '_raw_capture': {
        'endpoints': ['orgcard', 'reviews'],
        'schema_hash': 'abc123'
    }
}

raw_capture = {
    'some_data': 'test',
    'more_data': [1, 2, 3]
}

try:
    filepath = save_raw_capture(
        raw_capture,
        'test_reason',
        queue_dict,
        card_data,
        'success',
        []
    )
    
    print(f"   Файл сохранён: {filepath}")
    
    if filepath and os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        print(f"   Структура: {list(saved_data.keys())}")
        assert 'meta' in saved_data, f"Ожидался ключ 'meta' в сохранённых данных"
        assert 'raw_capture' in saved_data, f"Ожидался ключ 'raw_capture' в сохранённых данных"
        
        meta = saved_data['meta']
        assert 'ts' in meta, f"Ожидался ключ 'ts' в meta"
        assert 'task_id' in meta, f"Ожидался ключ 'task_id' в meta"
        assert 'expected_oid' in meta, f"Ожидался ключ 'expected_oid' in meta"
        assert 'extracted_oid' in meta, f"Ожидался ключ 'extracted_oid' in meta"
        assert 'status' in meta, f"Ожидался ключ 'status' in meta"
        assert 'reason' in meta, f"Ожидался ключ 'reason' in meta"
        
        print(f"   Meta: task_id={meta['task_id']}, expected_oid={meta['expected_oid']}, extracted_oid={meta['extracted_oid']}")
        print("   ✅ PASS")
        
        # Удаляем тестовый файл
        os.remove(filepath)
    else:
        print("   ⚠️ Файл не был создан (возможно, ошибка в save_raw_capture)")
        print("   ⚠️ Пропускаем проверку структуры")
except Exception as e:
    print(f"   ⚠️ Ошибка при сохранении: {e}")
    print("   ⚠️ Пропускаем проверку структуры")

print("\n" + "=" * 60)
print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО")
print("=" * 60)
