#!/usr/bin/env python3
"""Проверка логов worker и статуса задач"""
import os
import subprocess

log_file = "/tmp/seo_worker.out"

print("=" * 60)
print("ПРОВЕРКА ЛОГОВ WORKER")
print("=" * 60)

# Проверяем, существует ли файл
if os.path.exists(log_file):
    size = os.path.getsize(log_file)
    print(f"✅ Файл логов существует: {log_file}")
    print(f"   Размер: {size} байт")
    
    if size > 0:
        print("\n📄 Последние 50 строк логов:")
        print("-" * 60)
        try:
            result = subprocess.run(
                ["tail", "-50", log_file],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.stdout:
                print(result.stdout)
            else:
                print("(файл пустой или нет вывода)")
        except Exception as e:
            print(f"❌ Ошибка чтения логов: {e}")
    else:
        print("⚠️ Файл логов пустой!")
else:
    print(f"❌ Файл логов не существует: {log_file}")

# Проверяем процессы worker
print("\n" + "=" * 60)
print("ПРОВЕРКА ПРОЦЕССОВ WORKER")
print("=" * 60)

try:
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True,
        text=True,
        timeout=5
    )
    worker_processes = [line for line in result.stdout.split('\n') if 'worker.py' in line and 'grep' not in line]
    
    if worker_processes:
        print(f"✅ Найдено процессов worker: {len(worker_processes)}")
        for proc in worker_processes:
            print(f"   {proc}")
    else:
        print("❌ Процессы worker не найдены!")
except Exception as e:
    print(f"❌ Ошибка проверки процессов: {e}")

print("\n" + "=" * 60)

