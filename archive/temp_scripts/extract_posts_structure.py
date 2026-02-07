#!/usr/bin/env python3
"""
Скрипт для извлечения структуры постов из ответа sidebar.
"""

import json
import re
import sys
import zipfile
from pathlib import Path

def read_docx(file_path: str) -> str:
    """Читает .docx файл как текст."""
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        if 'word/document.xml' in zip_ref.namelist():
            xml_content = zip_ref.read('word/document.xml').decode('utf-8')
            text = re.sub(r'<[^>]+>', ' ', xml_content)
            text = re.sub(r'\s+', ' ', text)
            return text
    return None

def extract_json_structure(content: str):
    """Извлекает JSON структуры из контента."""
    
    # Ищем window.__INITIAL__.sidebar (приоритет)
    patterns = [
        (r'window\.__INITIAL__\s*=\s*window\.__INITIAL__\s*\|\|\s*\{\};\s*window\.__INITIAL__\.sidebar\s*=\s*({.+?});', "window.__INITIAL__.sidebar (многострочное)", True),
        (r'window\.__INITIAL__\.sidebar\s*=\s*({.+?});', "window.__INITIAL__.sidebar", True),
        (r'window\.__INITIAL__\s*=\s*({.+?});', "window.__INITIAL__", False),
        (r'const\s+STATE\s*=\s*({.+?});', "const STATE", False),
    ]
    
    for pattern, name, is_sidebar in patterns:
        matches = list(re.finditer(pattern, content, re.DOTALL))
        if matches:
            print(f"\n{'='*80}")
            print(f"✅ Найдено '{name}': {len(matches)} вхождений")
            print(f"{'='*80}")
            
            for i, match in enumerate(matches[:1]):  # Только первое вхождение для sidebar
                json_str = match.group(1)
                print(f"\n   Вхождение #{i+1} (позиция {match.start()}, длина: {len(json_str)}):")
                
                # Пробуем распарсить
                try:
                    # Балансируем скобки
                    bracket_count = 0
                    json_end = 0
                    in_string = False
                    escape_next = False
                    
                    for j, char in enumerate(json_str):
                        if escape_next:
                            escape_next = False
                            continue
                        if char == '\\':
                            escape_next = True
                            continue
                        if char == '"' and not escape_next:
                            in_string = not in_string
                            continue
                        if not in_string:
                            if char == '{':
                                bracket_count += 1
                            elif char == '}':
                                bracket_count -= 1
                                if bracket_count == 0:
                                    json_end = j + 1
                                    break
                    
                    if json_end > 0:
                        balanced_json = json_str[:json_end]
                        data = json.loads(balanced_json)
                        
                        print(f"   ✅ Успешно распарсен JSON")
                        print(f"   📊 Тип: {type(data).__name__}")
                        
                        if isinstance(data, dict):
                            print(f"   📋 Ключи верхнего уровня: {list(data.keys())[:20]}")
                            
                            # Ищем посты
                            def find_posts(obj, path="", depth=0, max_depth=5):
                                results = []
                                if depth > max_depth:
                                    return results
                                
                                if isinstance(obj, dict):
                                    for key, value in obj.items():
                                        if any(word in key.lower() for word in ['post', 'publication', 'news', 'публикац', 'новост']):
                                            full_path = f"{path}.{key}" if path else key
                                            if isinstance(value, list):
                                                results.append((full_path, len(value), "list"))
                                            elif isinstance(value, dict):
                                                results.append((full_path, list(value.keys())[:5], "dict"))
                                            else:
                                                results.append((full_path, type(value).__name__, "other"))
                                        
                                        if isinstance(value, (dict, list)):
                                            results.extend(find_posts(value, f"{path}.{key}" if path else key, depth + 1, max_depth))
                                
                                elif isinstance(obj, list) and obj:
                                    if isinstance(obj[0], dict):
                                        # Проверяем, похож ли на список постов
                                        first = obj[0]
                                        post_fields = ['title', 'text', 'content', 'published_at', 'created_at', 'date', 'id']
                                        if any(field in first for field in post_fields):
                                            results.append((path, len(obj), "posts_list"))
                                    
                                    if isinstance(obj[0], (dict, list)):
                                        results.extend(find_posts(obj[0], f"{path}[0]", depth + 1, max_depth))
                                
                                return results
                            
                            posts_locations = find_posts(data)
                            if posts_locations:
                                print(f"\n   🔍 Найдены структуры, связанные с постами:")
                                for path, info, ptype in posts_locations[:15]:
                                    print(f"      - {path}: {info} ({ptype})")
                                
                                # Показываем пример первого найденного поста
                                if is_sidebar:
                                    def get_first_post(obj, path=""):
                                        if isinstance(obj, dict):
                                            for key, value in obj.items():
                                                if any(word in key.lower() for word in ['post', 'publication', 'news', 'публикац', 'новост']):
                                                    if isinstance(value, list) and value:
                                                        return value[0]
                                                if isinstance(value, (dict, list)):
                                                    result = get_first_post(value, f"{path}.{key}" if path else key)
                                                    if result:
                                                        return result
                                        elif isinstance(obj, list) and obj:
                                            if isinstance(obj[0], dict):
                                                post_fields = ['title', 'text', 'content', 'published_at']
                                                if any(field in obj[0] for field in post_fields):
                                                    return obj[0]
                                            return get_first_post(obj[0], f"{path}[0]")
                                        return None
                                    
                                    first_post = get_first_post(data)
                                    if first_post:
                                        print(f"\n   📄 Пример первого поста:")
                                        print(f"   {json.dumps(first_post, ensure_ascii=False, indent=2)[:1000]}")
                            else:
                                print(f"\n   ⚠️ Не найдено явных структур с постами")
                                
                                # Показываем структуру для анализа
                                if is_sidebar:
                                    print(f"\n   📝 Полная структура sidebar (первые 3000 символов JSON):")
                                    json_preview = json.dumps(data, ensure_ascii=False, indent=2)[:3000]
                                    print(f"   {json_preview}...")
                                else:
                                    print(f"\n   📝 Структура данных (первые 2000 символов JSON):")
                                    json_preview = json.dumps(data, ensure_ascii=False, indent=2)[:2000]
                                    print(f"   {json_preview}...")
                        
                except Exception as e:
                    print(f"   ⚠️ Ошибка при парсинге: {e}")
                    print(f"   📝 Первые 500 символов JSON строки:")
                    print(f"   {json_str[:500]}...")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python3 extract_posts_structure.py <путь_к_файлу>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if not Path(file_path).exists():
        print(f"❌ Файл не найден: {file_path}")
        sys.exit(1)
    
    print(f"📖 Читаю файл: {file_path}")
    
    if file_path.endswith('.docx'):
        content = read_docx(file_path)
    else:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    
    if not content:
        print("❌ Не удалось прочитать файл")
        sys.exit(1)
    
    print(f"✅ Файл прочитан, размер: {len(content)} символов\n")
    
    extract_json_structure(content)

