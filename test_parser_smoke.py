#!/usr/bin/env python3
"""
Smoke test для парсера Яндекс.Карт (PART G)
Запускает парсинг 3 раза подряд, печатает диагностику, сохраняет артефакты при fail
"""
import sys
import os
sys.path.append('src')

from parser_interception import parse_yandex_card
import json

def test_parser_smoke(url: str, num_runs: int = 3):
    """Smoke test парсера с несколькими запусками"""
    print("=" * 80)
    print("🔍 SMOKE TEST: Парсер Яндекс.Карт (PART G)")
    print("=" * 80)
    print(f"URL: {url}")
    print(f"Количество запусков: {num_runs}\n")
    
    results = []
    
    for run_num in range(num_runs):
        print(f"\n{'='*80}")
        print(f"ЗАПУСК #{run_num + 1}")
        print(f"{'='*80}\n")
        
        try:
            result = parse_yandex_card(url)
            results.append(result)
            
            # Извлекаем ключевые данные
            expected_oid = result.get('expected_oid', 'unknown')
            extracted_oid = result.get('oid', 'unknown')
            parse_status = result.get('parse_status', 'unknown')
            missing_sections = result.get('missing_sections', [])
            
            # Диагностическая информация из _raw_capture
            raw_capture = result.get('_raw_capture', {})
            net = raw_capture.get('net', {})
            source_endpoints = raw_capture.get('source_endpoints', [])
            
            got_orgcard = 'orgcard' in source_endpoints or 'tycoon' in source_endpoints or 'location-info' in source_endpoints
            endpoints = source_endpoints
            domains = net.get('domains', {})
            failed_requests_count = len(net.get('failed_requests', []))
            console_errors_count = len(net.get('console_errors', []))
            
            # Выводим диагностику
            print(f"📊 ДИАГНОСТИКА (запуск #{run_num + 1}):")
            print(f"   got_orgcard: {got_orgcard}")
            print(f"   endpoints: {endpoints}")
            print(f"   domains: {list(domains.keys())[:10]}")  # Первые 10 доменов
            print(f"   failed_requests_count: {failed_requests_count}")
            print(f"   console_errors_count: {console_errors_count}")
            print(f"   extracted_oid: {extracted_oid}")
            print(f"   parse_status: {parse_status}")
            print(f"   missing_sections: {missing_sections}")
            
            if parse_status == 'fail':
                print(f"\n❌ FAIL (запуск #{run_num + 1})")
                # Печатаем первые 10 response URLs
                responses = net.get('responses', [])
                print(f"   Первые 10 response URLs:")
                for i, resp in enumerate(responses[:10]):
                    print(f"     {i+1}. {resp.get('url', 'N/A')[:100]}")
                
                # Сохраняем артефакты
                try:
                    import os
                    debug_dir = 'debug_data/test_smoke_fail'
                    os.makedirs(debug_dir, exist_ok=True)
                    artifact_file = f"{debug_dir}/run{run_num + 1}_fail.json"
                    with open(artifact_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            'run_num': run_num + 1,
                            'url': url,
                            'result': result,
                            'net_telemetry': net
                        }, f, ensure_ascii=False, indent=2)
                    print(f"   💾 Артефакты сохранены: {artifact_file}")
                except Exception as e:
                    print(f"   ⚠️ Не удалось сохранить артефакты: {e}")
            else:
                print(f"\n✅ SUCCESS (запуск #{run_num + 1})")
                
        except Exception as e:
            print(f"\n❌ EXCEPTION (запуск #{run_num + 1}): {e}")
            import traceback
            traceback.print_exc()
            results.append({'error': str(e), 'run_num': run_num + 1})
    
    # Итоговая статистика
    print(f"\n{'='*80}")
    print("ИТОГОВАЯ СТАТИСТИКА")
    print(f"{'='*80}\n")
    
    success_count = sum(1 for r in results if r.get('parse_status') == 'success')
    partial_count = sum(1 for r in results if r.get('parse_status') == 'partial')
    fail_count = sum(1 for r in results if r.get('parse_status') == 'fail' or 'error' in r)
    
    print(f"   Success: {success_count}/{num_runs}")
    print(f"   Partial: {partial_count}/{num_runs}")
    print(f"   Fail: {fail_count}/{num_runs}")
    
    # Проверяем стабильность
    if success_count == num_runs:
        print(f"\n✅ ВСЕ ЗАПУСКИ УСПЕШНЫ")
        return True
    elif success_count + partial_count == num_runs:
        print(f"\n⚠️ ВСЕ ЗАПУСКИ УСПЕШНЫ ИЛИ PARTIAL")
        return True
    else:
        print(f"\n❌ ЕСТЬ FAIL ЗАПУСКИ")
        return False

if __name__ == "__main__":
    # Тестовый URL для "Оливер"
    test_url = "https://yandex.com/maps/org/oliver/203293742306/?ll=30.219413%2C59.987283&z=13"
    
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
    
    success = test_parser_smoke(test_url, num_runs=3)
    sys.exit(0 if success else 1)
