#!/usr/bin/env python3
"""
Тесты для проверки schema introspection (PART B)
"""
import os
import sys
from unittest.mock import Mock, MagicMock

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from worker import get_table_columns, ColumnsInfo, _detect_db_kind

print("=" * 60)
print("ТЕСТ: Schema introspection (PART B)")
print("=" * 60)

# ========== PART B: COLUMNS INFO CONTRACT TESTS ==========

print("\n1. Тест: get_table_columns возвращает ColumnsInfo (не None)")
print("-" * 60)

# Мокаем cursor для PostgreSQL
mock_cursor_pg = Mock()
mock_cursor_pg.fetchall.return_value = [
    {'column_name': 'id'},
    {'column_name': 'business_id'},
    {'column_name': 'url'}
]

# Мокаем _detect_db_kind
import worker
original_detect = worker._detect_db_kind
worker._detect_db_kind = lambda c: "postgres"

try:
    result = get_table_columns(mock_cursor_pg, "test_table")
    print(f"   Тип результата: {type(result)}")
    print(f"   ok: {result.ok}")
    print(f"   columns: {result.columns}")
    print(f"   source: {result.source}")
    print(f"   error: {result.error}")
    
    assert isinstance(result, ColumnsInfo), f"Ожидался ColumnsInfo, получен {type(result)}"
    assert result.ok == True, f"Ожидался ok=True, получен {result.ok}"
    assert "id" in result.columns, f"Ожидался 'id' в columns, получен {result.columns}"
    assert result.source == "information_schema", f"Ожидался source='information_schema', получен {result.source}"
    assert result.error is None, f"Ожидался error=None, получен {result.error}"
    print("   ✅ PASS")
finally:
    worker._detect_db_kind = original_detect

print("\n2. Тест: get_table_columns при ошибке возвращает ok=False")
print("-" * 60)

# Мокаем cursor с ошибкой
mock_cursor_error = Mock()
mock_cursor_error.execute.side_effect = Exception("Connection error")

worker._detect_db_kind = lambda c: "postgres"

try:
    result = get_table_columns(mock_cursor_error, "test_table")
    print(f"   ok: {result.ok}")
    print(f"   columns: {result.columns}")
    print(f"   source: {result.source}")
    print(f"   error: {result.error}")
    
    assert isinstance(result, ColumnsInfo), f"Ожидался ColumnsInfo, получен {type(result)}"
    assert result.ok == False, f"Ожидался ok=False, получен {result.ok}"
    assert result.columns == set(), f"Ожидался пустой set, получен {result.columns}"
    assert result.source == "error", f"Ожидался source='error', получен {result.source}"
    assert result.error is not None, f"Ожидался error не None, получен {result.error}"
    print("   ✅ PASS")
finally:
    worker._detect_db_kind = original_detect

print("\n3. Тест: get_table_columns для SQLite (PRAGMA)")
print("-" * 60)

# Мокаем cursor для SQLite
mock_cursor_sqlite = Mock()
mock_cursor_sqlite.fetchall.return_value = [
    (0, 'id', 'TEXT', 0, None, 0),
    (1, 'business_id', 'TEXT', 0, None, 0),
    (2, 'url', 'TEXT', 0, None, 0)
]

worker._detect_db_kind = lambda c: "sqlite"

try:
    result = get_table_columns(mock_cursor_sqlite, "test_table")
    print(f"   ok: {result.ok}")
    print(f"   columns: {result.columns}")
    print(f"   source: {result.source}")
    print(f"   error: {result.error}")
    
    assert isinstance(result, ColumnsInfo), f"Ожидался ColumnsInfo, получен {type(result)}"
    assert result.ok == True, f"Ожидался ok=True, получен {result.ok}"
    assert "id" in result.columns, f"Ожидался 'id' в columns, получен {result.columns}"
    assert result.source == "pragma", f"Ожидался source='pragma', получен {result.source}"
    print("   ✅ PASS")
finally:
    worker._detect_db_kind = original_detect

print("\n" + "=" * 60)
print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО")
print("=" * 60)
