#!/usr/bin/env python3
"""
Отладка генерации отчёта
"""
import sys
import os
import traceback

# Добавляем путь к src в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_report_generation():
    """Тестируем генерацию отчёта с отладкой"""
    print("=== Тест генерации отчёта ===")
    
    try:
        from report import generate_html_report
        
        # Тестовые данные
        card_data = {
            'title': 'Look Me',
            'address': 'Лиговский просп., 83Б, Санкт-Петербург',
            'phone': '+7 (939) 406-54-96',
            'rating': '4.5',
            'reviews_count': 293,
            'categories': ['Салон красоты', 'Ногтевая студия', 'Парикмахерская'],
            'hours': 'Пн-Вс: 10:00–21:00',
            'photos': [],
            'reviews': [],
            'news': [],
            'products': [],
            'overview': {},
            'features_full': {'bool': [], 'valued': [], 'prices': [], 'categories': []}
        }
        
        analysis_data = {
            'score': 100,
            'recommendations': ['Создайте официальный сайт', 'Добавьте фотографии'],
            'ai_analysis': {'generated_text': 'Отличный рейтинг показывает высокое качество услуг'}
        }
        
        print("Запускаем генерацию отчёта...")
        print(f"card_data типы: {[(k, type(v)) for k, v in card_data.items()]}")
        print(f"analysis_data типы: {[(k, type(v)) for k, v in analysis_data.items()]}")
        
        # Проверяем проблемные поля
        for key, value in card_data.items():
            if callable(value):
                print(f"⚠️ Поле {key} является функцией: {value}")
                card_data[key] = []  # Заменяем на пустой список
        
        result_path = generate_html_report(card_data, analysis_data)
        print(f"✅ Отчёт сгенерирован: {result_path}")
        
        # Проверяем, что файл существует
        if os.path.exists(result_path):
            print("✅ Файл отчёта создан")
            file_size = os.path.getsize(result_path)
            print(f"📄 Размер файла: {file_size} байт")
        else:
            print("❌ Файл отчёта не найден")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка генерации отчёта: {e}")
        traceback.print_exc()
        return False

def test_template_rendering():
    """Тестируем рендеринг шаблона"""
    print("\n=== Тест рендеринга шаблона ===")
    
    try:
        from jinja2 import Environment, FileSystemLoader
        import os
        
        # Загружаем шаблон
        env = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), 'src', 'templates')))
        template = env.get_template('report_template.html')
        
        # Простые тестовые данные
        card_data = {
            'title': 'Тест',
            'address': 'Тестовый адрес',
            'phone': '+7 (999) 123-45-67',
            'rating': '4.5',
            'reviews_count': 100,
            'categories': ['Салон красоты'],
            'hours': 'Пн-Пт: 10:00–20:00',
            'photos': [],
            'reviews': [],
            'news': [],
            'products': [],
            'overview': {},
            'features_full': {'bool': [], 'valued': [], 'prices': [], 'categories': []}
        }
        
        analysis_data = {
            'score': 85,
            'recommendations': ['Рекомендация 1', 'Рекомендация 2'],
            'ai_analysis': {'generated_text': 'Тестовый анализ'}
        }
        
        print("Рендерим шаблон...")
        html = template.render(card=card_data, analysis=analysis_data, competitor=None)
        
        print(f"✅ Шаблон отрендерен, размер: {len(html)} символов")
        
        # Сохраняем тестовый файл
        test_path = os.path.join(os.path.dirname(__file__), 'test_report.html')
        with open(test_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✅ Тестовый отчёт сохранён: {test_path}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка рендеринга шаблона: {e}")
        traceback.print_exc()
        return False

def main():
    """Основная функция отладки"""
    print("🔍 Отладка генерации отчёта")
    print("=" * 50)
    
    # Тест 1: Рендеринг шаблона
    template_ok = test_template_rendering()
    
    # Тест 2: Генерация отчёта
    report_ok = test_report_generation()
    
    print("\n" + "=" * 50)
    print("📊 РЕЗУЛЬТАТЫ ОТЛАДКИ:")
    print(f"Шаблон: {'✅ OK' if template_ok else '❌ FAIL'}")
    print(f"Отчёт: {'✅ OK' if report_ok else '❌ FAIL'}")
    
    if template_ok and report_ok:
        print("\n🎉 Генерация отчёта работает!")
    else:
        print("\n⚠️ Есть проблемы с генерацией отчёта")

if __name__ == "__main__":
    main()
