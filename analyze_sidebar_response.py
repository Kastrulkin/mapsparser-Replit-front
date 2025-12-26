#!/usr/bin/env python3
"""
Скрипт для анализа ответа sidebar и поиска эндпоинтов для новостей/публикаций.
"""

import json
import re
import sys
from pathlib import Path

def read_file_content(file_path: str) -> str:
    """Читает содержимое файла, поддерживает .txt, .docx и другие форматы."""
    path = Path(file_path)
    
    # Пробуем прочитать как текстовый файл
    if path.suffix.lower() == '.docx':
        try:
            # Пробуем использовать python-docx
            from docx import Document
            doc = Document(file_path)
            content = '\n'.join([para.text for para in doc.paragraphs])
            print(f"✅ Файл .docx прочитан через python-docx")
            return content
        except ImportError:
            print("⚠️ python-docx не установлен, пробуем прочитать как zip...")
            # .docx это zip архив, пробуем извлечь text
            try:
                import zipfile
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    # Ищем document.xml в архиве
                    if 'word/document.xml' in zip_ref.namelist():
                        xml_content = zip_ref.read('word/document.xml').decode('utf-8')
                        # Простое извлечение текста из XML (удаляем теги)
                        content = re.sub(r'<[^>]+>', '', xml_content)
                        print(f"✅ Файл .docx прочитан как zip архив")
                        return content
            except Exception as e:
                print(f"⚠️ Не удалось прочитать .docx: {e}")
                print("💡 Установите python-docx: pip install python-docx")
                return None
        except Exception as e:
            print(f"❌ Ошибка при чтении .docx: {e}")
            return None
    else:
        # Обычный текстовый файл
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Пробуем другие кодировки
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception as e:
                print(f"❌ Ошибка при чтении файла: {e}")
                return None

def analyze_sidebar_response(file_path: str):
    """Анализирует файл с ответом sidebar и ищет эндпоинты и структуру данных."""
    
    print(f"📖 Читаю файл: {file_path}")
    
    content = read_file_content(file_path)
    if content is None:
        return
    
    if not content:
        print(f"⚠️ Файл пуст или не удалось прочитать содержимое")
        return
    
    print(f"✅ Файл прочитан, размер: {len(content)} символов\n")
    
    # 1. Ищем API endpoints для постов/новостей
    print("=" * 80)
    print("1️⃣ ПОИСК API ENDPOINTS ДЛЯ ПОСТОВ/НОВОСТЕЙ")
    print("=" * 80)
    
    endpoint_patterns = [
        (r'["\']https?://[^"\']*/(?:api|sprav|business)[^"\']*/(?:posts|news|publications|публикац|новост)[^"\']*["\']', "Полные URL с posts/news/publications"),
        (r'["\']/api/[^"\']*/(?:posts|news|publications)[^"\']*["\']', "Относительные пути /api/..."),
        (r'["\']/sprav/[^"\']*/(?:posts|news|publications)[^"\']*["\']', "Относительные пути /sprav/..."),
        (r'["\']/business/[^"\']*/(?:posts|news|publications)[^"\']*["\']', "Относительные пути /business/..."),
        (r'url["\']?\s*[:=]\s*["\']([^"\']*/(?:posts|news|publications)[^"\']*)["\']', "Ключ url с posts/news"),
        (r'endpoint["\']?\s*[:=]\s*["\']([^"\']*/(?:posts|news|publications)[^"\']*)["\']', "Ключ endpoint"),
        (r'apiUrl["\']?\s*[:=]\s*["\']([^"\']*/(?:posts|news|publications)[^"\']*)["\']', "Ключ apiUrl"),
        (r'fetch\(["\']([^"\']*/(?:posts|news|publications)[^"\']*)["\']', "fetch() вызовы"),
        (r'axios\.(?:get|post)\(["\']([^"\']*/(?:posts|news|publications)[^"\']*)["\']', "axios вызовы"),
    ]
    
    all_endpoints = []
    for pattern, description in endpoint_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            print(f"\n✅ {description}:")
            for match in matches[:10]:  # Первые 10
                endpoint = match if isinstance(match, str) else match[0] if match else ""
                if endpoint:
                    print(f"   - {endpoint}")
                    all_endpoints.append(endpoint)
    
    if not all_endpoints:
        print("\n⚠️ Не найдено явных endpoints для posts/news/publications")
    
    # 2. Ищем все URL, связанные с API
    print("\n" + "=" * 80)
    print("2️⃣ ПОИСК ВСЕХ URL, СВЯЗАННЫХ С API/SPRAV/BUSINESS")
    print("=" * 80)
    
    all_urls = re.findall(r'https?://[^\s"\'<>)]+', content[:50000])  # Первые 50k символов
    api_related_urls = [url for url in all_urls if any(word in url.lower() for word in ['api', 'sprav', 'business', 'yandex.ru'])]
    
    # Фильтруем уникальные и связанные с постами
    unique_api_urls = []
    seen = set()
    for url in api_related_urls:
        if url not in seen and len(url) < 500:  # Игнорируем слишком длинные
            seen.add(url)
            unique_api_urls.append(url)
    
    print(f"\n📊 Найдено {len(unique_api_urls)} уникальных URL, связанных с API")
    print("Первые 20:")
    for url in unique_api_urls[:20]:
        print(f"   - {url[:150]}")
    
    # 3. Ищем структуру данных с постами
    print("\n" + "=" * 80)
    print("3️⃣ ПОИСК СТРУКТУРЫ ДАННЫХ С ПОСТАМИ")
    print("=" * 80)
    
    # Ищем JSON объекты с ключами posts/publications/news
    json_patterns = [
        (r'["\']posts["\']\s*:\s*\[', "Ключ 'posts' с массивом"),
        (r'["\']publications["\']\s*:\s*\[', "Ключ 'publications' с массивом"),
        (r'["\']news["\']\s*:\s*\[', "Ключ 'news' с массивом"),
        (r'["\']публикации["\']\s*:\s*\[', "Ключ 'публикации' с массивом"),
        (r'["\']новости["\']\s*:\s*\[', "Ключ 'новости' с массивом"),
    ]
    
    for pattern, description in json_patterns:
        matches = list(re.finditer(pattern, content, re.IGNORECASE))
        if matches:
            print(f"\n✅ {description}: найдено {len(matches)} вхождений")
            for i, match in enumerate(matches[:3]):  # Первые 3
                start = max(0, match.start() - 100)
                end = min(len(content), match.end() + 500)
                context = content[start:end]
                print(f"\n   Вхождение #{i+1} (позиция {match.start()}):")
                print(f"   {context[:400]}...")
    
    # 4. Ищем window.__INITIAL__ и подобные структуры
    print("\n" + "=" * 80)
    print("4️⃣ ПОИСК WINDOW.__INITIAL__ И ПОДОБНЫХ СТРУКТУР")
    print("=" * 80)
    
    initial_patterns = [
        r'window\.__INITIAL__',
        r'window\.__INITIAL_STATE__',
        r'window\.__DATA__',
        r'__INITIAL__',
        r'const\s+STATE\s*=',
    ]
    
    for pattern in initial_patterns:
        matches = list(re.finditer(pattern, content, re.IGNORECASE))
        if matches:
            print(f"\n✅ Найдено '{pattern}': {len(matches)} вхождений")
            for i, match in enumerate(matches[:2]):  # Первые 2
                start = max(0, match.start() - 50)
                end = min(len(content), match.end() + 200)
                context = content[start:end]
                print(f"   Вхождение #{i+1}: {context[:300]}...")
    
    # 5. Ищем ключи, связанные с постами в JSON
    print("\n" + "=" * 80)
    print("5️⃣ ПОИСК КЛЮЧЕЙ, СВЯЗАННЫХ С ПОСТАМИ В JSON")
    print("=" * 80)
    
    post_key_patterns = [
        r'["\'](?:posts|publications|news|публикации|новости)["\']',
        r'["\'][^"\']*(?:post|publication|news|публикац|новост)[^"\']*["\']',
    ]
    
    found_keys = set()
    for pattern in post_key_patterns:
        matches = re.findall(pattern, content[:100000], re.IGNORECASE)  # Первые 100k
        found_keys.update(matches)
    
    if found_keys:
        print(f"\n✅ Найдено {len(found_keys)} уникальных ключей, связанных с постами:")
        for key in sorted(found_keys)[:20]:
            print(f"   - {key}")
    else:
        print("\n⚠️ Не найдено ключей, связанных с постами")
    
    # 6. Пробуем распарсить как JSON (если это JSON)
    print("\n" + "=" * 80)
    print("6️⃣ ПОПЫТКА ПАРСИНГА КАК JSON")
    print("=" * 80)
    
    try:
        data = json.loads(content)
        print("✅ Файл является валидным JSON!")
        print(f"   Тип корневого элемента: {type(data).__name__}")
        
        if isinstance(data, dict):
            print(f"   Ключи верхнего уровня: {list(data.keys())[:20]}")
            
            # Ищем посты рекурсивно
            def find_posts_keys(obj, path="", depth=0, max_depth=5):
                if depth > max_depth:
                    return []
                keys = []
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if any(word in key.lower() for word in ['post', 'publication', 'news', 'публикац', 'новост']):
                            keys.append(f"{path}.{key}" if path else key)
                        if isinstance(value, (dict, list)):
                            keys.extend(find_posts_keys(value, f"{path}.{key}" if path else key, depth + 1, max_depth))
                elif isinstance(obj, list) and obj:
                    if isinstance(obj[0], (dict, list)):
                        keys.extend(find_posts_keys(obj[0], f"{path}[0]", depth + 1, max_depth))
                return keys
            
            post_keys = find_posts_keys(data)
            if post_keys:
                print(f"\n   ✅ Найдены ключи, связанные с постами:")
                for key in post_keys[:15]:
                    print(f"      - {key}")
        
    except json.JSONDecodeError:
        print("⚠️ Файл не является валидным JSON (возможно, это HTML/JavaScript)")
    
    # 7. Ищем упоминания конкретных endpoints из документации
    print("\n" + "=" * 80)
    print("7️⃣ ПОИСК ИЗВЕСТНЫХ ENDPOINTS")
    print("=" * 80)
    
    known_endpoints = [
        '/api/company/',
        '/sprav/api/company/',
        '/business/server-components/',
        'price-lists',
        'posts',
        'publications',
        'news',
    ]
    
    for endpoint in known_endpoints:
        matches = list(re.finditer(re.escape(endpoint), content, re.IGNORECASE))
        if matches:
            print(f"\n✅ Найдено '{endpoint}': {len(matches)} вхождений")
            for i, match in enumerate(matches[:2]):
                start = max(0, match.start() - 100)
                end = min(len(content), match.end() + 200)
                context = content[start:end]
                print(f"   Вхождение #{i+1}: {context[:300]}...")
    
    print("\n" + "=" * 80)
    print("✅ АНАЛИЗ ЗАВЕРШЕН")
    print("=" * 80)
    print("\n💡 РЕКОМЕНДАЦИИ:")
    print("1. Если найдены endpoints - попробуйте их в браузере/Postman")
    print("2. Если найдены ключи 'posts'/'publications' - проверьте структуру JSON")
    print("3. Если файл HTML/JS - ищите window.__INITIAL__ или подобные структуры")
    print("4. Сохраните найденные endpoints для использования в парсере")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python analyze_sidebar_response.py <путь_к_файлу>")
        print("\nПример:")
        print("  python analyze_sidebar_response.py sidebar_response.txt")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if not Path(file_path).exists():
        print(f"❌ Файл не найден: {file_path}")
        sys.exit(1)
    
    analyze_sidebar_response(file_path)

