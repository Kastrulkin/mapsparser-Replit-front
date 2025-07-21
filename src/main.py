
#!/usr/bin/env python3
"""
Главный модуль для парсинга и анализа карточек Яндекс.Карт
"""
import asyncio
import json
import sys
from pathlib import Path

# Добавляем папку src в путь для импорта модулей
sys.path.append(str(Path(__file__).parent))

from parser import parse_yandex_card
from analyzer import analyze_card
from report import generate_html_report
from save_to_supabase import save_card_to_supabase


async def process_card(url: str, save_to_db: bool = True) -> dict:
    """
    Обрабатывает одну карточку: парсит, анализирует и сохраняет результаты
    """
    print(f"🔍 Начинаем обработку карточки: {url}")
    
    # Шаг 1: Парсинг карточки
    print("📊 Парсинг данных карточки...")
    card_data = await parse_yandex_card(url)
    
    if not card_data:
        print("❌ Ошибка при парсинге карточки")
        return None
    
    title = card_data.get('overview', {}).get('title', 'Неизвестная организация')
    print(f"✅ Парсинг завершен: {title}")
    
    # Шаг 2: Анализ данных
    print("🔬 Анализ данных карточки...")
    analysis = analyze_card(card_data)
    print("✅ Анализ завершен")
    
    # Шаг 3: Генерация HTML-отчета
    print("📄 Генерация HTML-отчета...")
    report_path = generate_html_report(card_data, analysis)
    print(f"✅ Отчет сохранен: {report_path}")
    
    # Шаг 4: Сохранение в Supabase (опционально)
    if save_to_db:
        print("💾 Сохранение в базу данных...")
        try:
            save_card_to_supabase(card_data)
            print("✅ Данные сохранены в Supabase")
        except Exception as e:
            print(f"⚠️ Ошибка при сохранении в базу: {e}")
    
    return {
        'card_data': card_data,
        'analysis': analysis,
        'report_path': report_path
    }


async def process_multiple_cards(urls: list, save_to_db: bool = True) -> list:
    """
    Обрабатывает множество карточек
    """
    results = []
    
    print(f"🚀 Начинаем обработку {len(urls)} карточек")
    
    for i, url in enumerate(urls, 1):
        print(f"\n--- Карточка {i}/{len(urls)} ---")
        try:
            result = await process_card(url, save_to_db)
            if result:
                results.append(result)
                print(f"✅ Карточка {i} обработана успешно")
            else:
                print(f"❌ Ошибка при обработке карточки {i}")
        except Exception as e:
            print(f"❌ Критическая ошибка при обработке карточки {i}: {e}")
            continue
    
    print(f"\n🎉 Обработка завершена! Успешно обработано: {len(results)}/{len(urls)} карточек")
    return results


def main():
    """
    Главная функция
    """
    print("🌟 Yandex Maps Card Parser & Analyzer v1.0")
    print("=" * 50)
    
    # Проверяем аргументы командной строки
    if len(sys.argv) < 2:
        print("❌ Не указан URL для парсинга")
        print("Использование: python main.py <URL1> [URL2] [URL3] ...")
        print("Пример: python main.py https://yandex.ru/maps/org/...")
        return
    
    # Получаем URLs из аргументов
    urls = sys.argv[1:]
    
    # Валидируем URLs
    valid_urls = []
    for url in urls:
        if 'yandex.ru/maps/org/' in url or 'yandex.com/maps/org/' in url:
            valid_urls.append(url)
        else:
            print(f"⚠️ Пропускаем некорректный URL: {url}")
    
    if not valid_urls:
        print("❌ Не найдено валидных URLs для обработки")
        return
    
    try:
        # Запускаем обработку
        if len(valid_urls) == 1:
            # Одна карточка
            result = asyncio.run(process_card(valid_urls[0]))
            if result:
                print(f"\n📊 Результаты анализа:")
                print(f"   • Рейтинг: {result['card_data'].get('overview', {}).get('rating', 'Н/Д')}")
                print(f"   • Количество отзывов: {result['card_data'].get('overview', {}).get('reviews_count', 'Н/Д')}")
                print(f"   • Категории: {len(result['card_data'].get('categories_full', []))}")
                print(f"   • Отчет: {result['report_path']}")
        else:
            # Множество карточек
            results = asyncio.run(process_multiple_cards(valid_urls))
            if results:
                print(f"\n📊 Сводные результаты:")
                total_reviews = sum(r['card_data'].get('overview', {}).get('reviews_count', 0) or 0 for r in results)
                avg_rating = sum(float(r['card_data'].get('overview', {}).get('rating', 0) or 0) for r in results) / len(results)
                print(f"   • Всего отзывов: {total_reviews}")
                print(f"   • Средний рейтинг: {avg_rating:.1f}")
                print(f"   • Сгенерированных отчетов: {len(results)}")
    
    except KeyboardInterrupt:
        print("\n\n⏹️ Обработка прервана пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
