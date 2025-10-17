#!/usr/bin/env python3
"""
Обновление популярных запросов из CSV файлов Wordstat
"""

import os
import sys
import csv
import json
from datetime import datetime
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__))))

def load_csv_data(csv_file_path: str) -> list:
    """Загрузка данных из CSV файла"""
    data = []
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                if 'Формулировка' in row and 'Число запросов' in row:
                    query = row['Формулировка'].strip()
                    shows = int(row['Число запросов'].replace(',', '')) if row['Число запросов'] else 0
                    if query and shows > 0:
                        data.append({
                            'query': query,
                            'shows': shows
                        })
    except Exception as e:
        print(f"Ошибка загрузки {csv_file_path}: {e}")
    return data

def categorize_queries(queries_data: list) -> dict:
    """Категоризация запросов по типам услуг"""
    categories = {
        'Стрижки и укладки': [],
        'Окрашивание': [],
        'Маникюр и педикюр': [],
        'Массаж и СПА': [],
        'Брови и ресницы': [],
        'Барбершоп': [],
        'Другие услуги': []
    }
    
    # Ключевые слова для категоризации
    category_keywords = {
        'Стрижки и укладки': ['стрижка', 'укладка', 'прическа', 'волосы', 'парикмахер', 'боб', 'каре', 'пикси'],
        'Окрашивание': ['окрашивание', 'покраска', 'мелирование', 'колорирование', 'тонирование', 'блондирование', 'балаяж', 'шатуш'],
        'Маникюр и педикюр': ['маникюр', 'педикюр', 'ногти', 'гель-лак', 'шеллак', 'наращивание', 'френч'],
        'Массаж и СПА': ['массаж', 'спа', 'обертывание', 'пилинг', 'антицеллюлитный', 'релакс', 'ароматерапия'],
        'Брови и ресницы': ['брови', 'ресницы', 'коррекция бровей', 'наращивание ресниц', 'ламинирование'],
        'Барбершоп': ['барбершоп', 'мужская стрижка', 'борода', 'усы', 'бритье', 'стрижка под машинку']
    }
    
    for item in queries_data:
        query = item['query'].lower()
        shows = item['shows']
        
        categorized = False
        for category, keywords in category_keywords.items():
            if any(keyword in query for keyword in keywords):
                categories[category].append({
                    'query': item['query'],
                    'shows': shows
                })
                categorized = True
                break
        
        if not categorized:
            categories['Другие услуги'].append({
                'query': item['query'],
                'shows': shows
            })
    
    # Сортируем по количеству показов
    for category in categories:
        categories[category].sort(key=lambda x: x['shows'], reverse=True)
    
    return categories

def save_queries_to_file(categorized_queries: dict, file_path: str):
    """Сохранение запросов в файл"""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("# Популярные запросы с количеством показов (обновлено из CSV)\n\n")
        
        for category, queries in categorized_queries.items():
            if queries:
                f.write(f"## {category}:\n")
                for item in queries[:50]:  # Топ 50 по категории
                    f.write(f"- {item['query']} ({item['shows']:,} показов/месяц)\n")
                f.write("\n")
        
        f.write(f"\n*Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}*\n")

def main():
    """Основная функция обновления"""
    print("🔄 Обновление популярных запросов из CSV файлов...")
    
    # Пути к CSV файлам (если они есть в Downloads)
    csv_files = [
        "/Users/alexdemyanov/Downloads/wordstat_top_queries (1).csv",
        "/Users/alexdemyanov/Downloads/wordstat_top_queries (2).csv",
        "/Users/alexdemyanov/Downloads/wordstat_top_queries (3).csv",
        "/Users/alexdemyanov/Downloads/wordstat_top_queries (4).csv",
        "/Users/alexdemyanov/Downloads/wordstat_top_queries (5).csv",
        "/Users/alexdemyanov/Downloads/wordstat_top_queries (6).csv",
        "/Users/alexdemyanov/Downloads/wordstat_top_queries.csv",
        "/Users/alexdemyanov/Downloads/wordstat_similar_queries.csv"
    ]
    
    all_queries = []
    
    # Загружаем данные из всех CSV файлов
    for csv_file in csv_files:
        if os.path.exists(csv_file):
            print(f"📁 Загружаем данные из {os.path.basename(csv_file)}...")
            data = load_csv_data(csv_file)
            all_queries.extend(data)
            print(f"   Загружено {len(data)} запросов")
        else:
            print(f"⚠️  Файл не найден: {csv_file}")
    
    if not all_queries:
        print("❌ Не найдено CSV файлов с данными")
        return False
    
    print(f"\n📊 Всего загружено {len(all_queries)} запросов")
    
    # Удаляем дубликаты
    unique_queries = {}
    for item in all_queries:
        query = item['query']
        if query not in unique_queries or unique_queries[query]['shows'] < item['shows']:
            unique_queries[query] = item
    
    print(f"📈 Уникальных запросов: {len(unique_queries)}")
    
    # Категоризируем запросы
    print("\n🏷️  Категоризация запросов...")
    categorized_queries = categorize_queries(list(unique_queries.values()))
    
    # Показываем статистику по категориям
    for category, queries in categorized_queries.items():
        if queries:
            total_shows = sum(q['shows'] for q in queries)
            print(f"   {category}: {len(queries)} запросов, {total_shows:,} показов")
    
    # Сохраняем в файл
    prompts_dir = Path(__file__).parent.parent / "prompts"
    file_path = prompts_dir / "popular_queries_with_clicks.txt"
    
    save_queries_to_file(categorized_queries, str(file_path))
    
    print(f"\n✅ Данные сохранены в {file_path}")
    
    # Сохраняем метаданные
    metadata = {
        'last_update': datetime.now().isoformat(),
        'total_queries': len(unique_queries),
        'categories': {cat: len(queries) for cat, queries in categorized_queries.items()},
        'source': 'CSV files'
    }
    
    metadata_path = prompts_dir / "wordstat_metadata.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    print(f"📋 Метаданные сохранены в {metadata_path}")
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 Обновление завершено успешно!")
    else:
        print("\n💥 Обновление завершилось с ошибками")
        sys.exit(1)
