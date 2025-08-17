#!/usr/bin/env python3
"""
Скрипт для очистки проекта от ненужных файлов
"""

import os
import shutil
import glob

def cleanup_project():
    """Очищаем проект от ненужных файлов"""
    
    print("🧹 Начинаем очистку проекта...")
    
    # Список файлов для удаления
    files_to_delete = [
        # Временные тестовые файлы
        "view_enjoy_studio_report.py",
        "check_enjoy_studio_data.py", 
        "find_enjoy_studio_vps.py",
        "find_enjoy_studio_report.py",
        "test_parser_logic.py",
        "test_parser_fixes.py",
        
        # Тестовые файлы моделей
        "test_found_models.py",
        "test_full_analysis.py",
        "test_working_models.py",
        "test_specific_qwen_models.py",
        "test_qwen3_models.py",
        "test_official_mcp.py",
        "test_rubert_model.py",
        "test_russian_models.py",
        "test_available_models.py",
        "test_ai_analysis_only.py",
        "test_updated_analysis.py",
        "test_dataforseo_integration.py",
        "test_mcp_models.py",
        "test_report_endpoints.py",
        "test_final.py",
        "test_full_pipeline.py",
        "test_huggingface.py",
        
        # Файлы поиска моделей
        "find_russian_models.py",
        "find_best_seo_models.py",
        "find_best_models.py",
        "find_text_generation_models.py",
        
        # Временные файлы пользователей
        "check_auth_users.py",
        "fix_user_reports.py",
        "check_gmail_user.py",
        "debug_dashboard_data.py",
        "update_user_id.py",
        "update_user_data.py",
        "update_user_data_final.py",
        "test_user_data.py",
        "fix_user_email.py",
        "fix_encoding.py",
        "fix_report_path.py",
        "check_user_by_email.py",
        "create_report_file.py",
        "check_reports.py",
        "check_rls_policies.py",
        "check_queue.py",
        "check_report_details.py",
        "create_user_with_auth_id.py",
        "check_user_complete.py",
        "check_user_profile.py",
        "check_user_reports.py",
        "add_yandex_url_field.py",
        "update_users_fixed.py",
        "check_table_schema.py",
        
        # Системные файлы
        ".DS_Store",
        "index.html",
        
        # SQL файлы
        "update_user_data_final.sql",
        "update_user_with_report.sql",
        "update_users_simple.sql",
        "add_yandex_url_migration.sql",
        
        # Shell скрипты
        "run_update.sh",
        "run_check.sh",
        "update-nginx.sh",
        
        # Временные файлы
        "EmailYandexForm.tsx"
    ]
    
    # Удаляем файлы
    deleted_count = 0
    for file_path in files_to_delete:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"🗑️ Удалён: {file_path}")
                deleted_count += 1
            except Exception as e:
                print(f"❌ Ошибка удаления {file_path}: {e}")
        else:
            print(f"⚠️ Файл не найден: {file_path}")
    
    # Очищаем папку attached_assets
    print("\n🧹 Очищаем папку attached_assets...")
    attached_dir = "attached_assets"
    if os.path.exists(attached_dir):
        # Удаляем все файлы с временными метками
        patterns_to_delete = [
            "save_to_supabase_*.py",
            "utils_*.py",
            "parser_*.py",
            "report_*.py",
            "main_*.py",
            "analyzer_*.py",
            "Pasted-*.txt",
            "Снимок экрана*.png"
        ]
        
        for pattern in patterns_to_delete:
            files = glob.glob(os.path.join(attached_dir, pattern))
            for file_path in files:
                try:
                    os.remove(file_path)
                    print(f"🗑️ Удалён: {file_path}")
                    deleted_count += 1
                except Exception as e:
                    print(f"❌ Ошибка удаления {file_path}: {e}")
    
    # Очищаем папку .cursor если она пустая
    cursor_dir = ".cursor"
    if os.path.exists(cursor_dir) and not os.listdir(cursor_dir):
        try:
            os.rmdir(cursor_dir)
            print(f"🗑️ Удалена пустая папка: {cursor_dir}")
        except Exception as e:
            print(f"❌ Ошибка удаления папки {cursor_dir}: {e}")
    
    print(f"\n✅ Очистка завершена! Удалено файлов: {deleted_count}")
    
    # Показываем оставшиеся важные файлы
    print("\n📁 Оставшиеся важные файлы:")
    important_files = [
        "src/",
        "frontend/",
        "supabase/",
        "data/",
        "requirements.txt",
        "README.md",
        "ИНСТРУКЦИЯ_ПО_ЗАПУСКУ.md",
        "VPS_UPDATE.md",
        "web_server.py",
        "web_server_fixed.py",
        "seo-worker.service",
        "seo-download.service",
        "nginx-config.conf"
    ]
    
    for file_path in important_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")

if __name__ == "__main__":
    cleanup_project() 