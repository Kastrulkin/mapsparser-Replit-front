# Задача: Подвкладки карт и переименование Прогресс → Дашборд

**Дата:** 2025-01-06  
**Приоритет:** Высокий  
**Исполнитель:** Кодер

---

## Проблемы

1. **Подвкладки в "Работа с картами"** - нужно создавать подвкладки по сервисам карт (Яндекс, Google, 2ГИС)
2. **Переименование "Прогресс" → "Дашборд"** - переименовать и улучшить функционал
3. **Статус парсинга в Дашборде** - после запуска парсинга статус должен появляться в блоке "Парсинг карт"

---

## Проблема 1: Подвкладки в "Работа с картами"

### Анализ

**Текущая ситуация:**
- В "Информации о бизнесе" пользователь добавляет ссылки на карты
- Ссылки сохраняются в таблице `BusinessMapLinks` с полем `map_type`
- В "Работа с картами" (`CardOverviewPage.tsx`) нет подвкладок

**Требование:**
- Определять сервис карт по ссылке (Яндекс, Google, 2ГИС и т.д.)
- Создавать подвкладки с названием сервиса
- Показывать данные для каждого сервиса отдельно

### Решение

**Файл:** `frontend/src/pages/dashboard/CardOverviewPage.tsx`

**1. Определение типа карты по URL:**

```typescript
const detectMapType = (url: string): string => {
  if (!url) return 'unknown';
  
  const urlLower = url.toLowerCase();
  
  if (urlLower.includes('yandex.ru') || urlLower.includes('yandex.com')) {
    return 'yandex';
  }
  if (urlLower.includes('google.com/maps') || urlLower.includes('google.ru/maps')) {
    return 'google';
  }
  if (urlLower.includes('2gis.ru') || urlLower.includes('2gis.com')) {
    return '2gis';
  }
  
  return 'unknown';
};
```

**2. Загрузка ссылок на карты:**

```typescript
const [mapLinks, setMapLinks] = useState<Array<{url: string, mapType: string}>>([]);
const [activeMapTab, setActiveMapTab] = useState<string | null>(null);

useEffect(() => {
  const loadMapLinks = async () => {
    if (!currentBusinessId) return;
    
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/client-info?business_id=${currentBusinessId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      
      if (data.success && data.mapLinks) {
        const links = data.mapLinks.map((link: any) => ({
          url: link.url,
          mapType: link.map_type || detectMapType(link.url)
        }));
        setMapLinks(links);
        
        // Устанавливаем первую вкладку активной
        if (links.length > 0 && !activeMapTab) {
          setActiveMapTab(links[0].mapType);
        }
      }
    } catch (e) {
      console.error('Ошибка загрузки ссылок на карты:', e);
    }
  };
  
  loadMapLinks();
}, [currentBusinessId]);
```

**3. UI с подвкладками:**

```tsx
{/* Подвкладки по сервисам карт */}
{mapLinks.length > 0 && (
  <div className="mb-6">
    <div className="border-b border-gray-200">
      <nav className="flex space-x-8" aria-label="Tabs">
        {mapLinks.map((link, index) => {
          const mapTypeLabel = {
            'yandex': 'Яндекс',
            'google': 'Google',
            '2gis': '2ГИС',
            'unknown': 'Другая карта'
          }[link.mapType] || 'Другая карта';
          
          return (
            <button
              key={index}
              onClick={() => setActiveMapTab(link.mapType)}
              className={`
                py-4 px-1 border-b-2 font-medium text-sm
                ${activeMapTab === link.mapType
                  ? 'border-orange-500 text-orange-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
            >
              {mapTypeLabel}
            </button>
          );
        })}
      </nav>
    </div>
    
    {/* Контент для активной вкладки */}
    {activeMapTab && (
      <div className="mt-6">
        {/* Здесь контент для выбранного сервиса карт */}
        {/* Услуги, отзывы, новости для этого сервиса */}
      </div>
    )}
  </div>
)}
```

**4. Фильтрация данных по сервису:**

```typescript
// Фильтруем услуги, отзывы, новости по активному сервису
const filteredServices = userServices.filter(/* фильтр по mapType */);
const filteredReviews = externalReviews.filter(/* фильтр по source */);
const filteredPosts = externalPosts.filter(/* фильтр по source */);
```

---

## Проблема 2: Переименование "Прогресс" → "Дашборд"

### Анализ

**Текущая ситуация:**
- Страница называется "Прогресс" (`ProgressPage.tsx`)
- Маршрут: `/dashboard/progress`
- Компоненты: `ProgressTracker`, `MapRecommendations`, `MapParseTable`

**Требование:**
- Переименовать в "Дашборд"
- Собирать данные с нескольких карт по выбранному бизнесу
- Показывать прогресс изменений (отзывы, рейтинг, посетители)
- Ориентироваться на `frontend-design.mdc` для UI/UX

### Решение

**1. Переименование файла и компонента:**

```bash
# Переименовать файл
mv frontend/src/pages/dashboard/ProgressPage.tsx frontend/src/pages/dashboard/DashboardPage.tsx
```

**2. Обновление компонента:**

**Файл:** `frontend/src/pages/dashboard/DashboardPage.tsx`

```tsx
import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import ProgressTracker from '@/components/ProgressTracker';
import MapParseTable from '@/components/MapParseTable';
import MapRecommendations from '@/components/MapRecommendations';

export const DashboardPage = () => {
  const { user, currentBusinessId } = useOutletContext<any>();
  const [mapLinks, setMapLinks] = useState<Array<{url: string, mapType: string}>>([]);
  const [aggregatedStats, setAggregatedStats] = useState<any>(null);

  // Загружаем ссылки на карты
  useEffect(() => {
    // ... код загрузки mapLinks ...
  }, [currentBusinessId]);

  // Загружаем агрегированную статистику со всех карт
  useEffect(() => {
    const loadAggregatedStats = async () => {
      if (!currentBusinessId) return;
      
      try {
        const token = localStorage.getItem('auth_token');
        const res = await fetch(`${window.location.origin}/api/business/${currentBusinessId}/dashboard/stats`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await res.json();
        
        if (data.success) {
          setAggregatedStats(data.stats);
        }
      } catch (e) {
        console.error('Ошибка загрузки статистики:', e);
      }
    };
    
    loadAggregatedStats();
  }, [currentBusinessId]);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Дашборд</h1>
          <p className="text-gray-600 mt-1">Отслеживайте прогресс изменений на картах</p>
        </div>
      </div>

      {/* Агрегированная статистика со всех карт */}
      {aggregatedStats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-sm text-gray-600">Общий рейтинг</div>
            <div className="text-2xl font-bold text-gray-900">{aggregatedStats.avgRating?.toFixed(1) || '—'}</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-sm text-gray-600">Всего отзывов</div>
            <div className="text-2xl font-bold text-gray-900">{aggregatedStats.totalReviews || 0}</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-sm text-gray-600">Просмотры</div>
            <div className="text-2xl font-bold text-gray-900">{aggregatedStats.totalViews || 0}</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-sm text-gray-600">Клики</div>
            <div className="text-2xl font-bold text-gray-900">{aggregatedStats.totalClicks || 0}</div>
          </div>
        </div>
      )}

      {/* Графики прогресса */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold mb-4">Прогресс изменений</h2>
        {/* Графики с данными за последние 30 дней */}
      </div>

      <ProgressTracker businessId={currentBusinessId} />
      <MapRecommendations businessId={currentBusinessId} />
      <MapParseTable businessId={currentBusinessId} />
    </div>
  );
};
```

**3. Обновление маршрута:**

**Файл:** `frontend/src/App.tsx`

```tsx
import { DashboardPage } from "./pages/dashboard/DashboardPage";

// ...
<Route path="dashboard" element={<DashboardLayout />}>
  <Route index element={<Navigate to="/dashboard/dashboard" replace />} />
  <Route path="profile" element={<ProfilePage />} />
  <Route path="card" element={<CardOverviewPage />} />
  <Route path="dashboard" element={<DashboardPage />} />
  {/* Старый маршрут для обратной совместимости */}
  <Route path="progress" element={<Navigate to="/dashboard/dashboard" replace />} />
  {/* ... остальные маршруты ... */}
</Route>
```

**4. Backend endpoint для агрегированной статистики:**

**Файл:** `src/main.py`

```python
@app.route('/api/business/<business_id>/dashboard/stats', methods=['GET'])
def get_dashboard_stats(business_id):
    """Получить агрегированную статистику со всех карт"""
    # ... проверка авторизации ...
    
    # Получаем все ссылки на карты
    cursor.execute("""
        SELECT map_type, url FROM BusinessMapLinks WHERE business_id = ?
    """, (business_id,))
    map_links = cursor.fetchall()
    
    # Получаем статистику из ExternalBusinessStats для всех источников
    cursor.execute("""
        SELECT 
            source,
            SUM(views_total) as total_views,
            SUM(clicks_total) as total_clicks,
            AVG(rating) as avg_rating,
            SUM(reviews_total) as total_reviews
        FROM ExternalBusinessStats
        WHERE business_id = ?
        GROUP BY source
    """, (business_id,))
    stats_by_source = cursor.fetchall()
    
    # Агрегируем данные
    aggregated = {
        'avgRating': 0,
        'totalReviews': 0,
        'totalViews': 0,
        'totalClicks': 0,
        'bySource': {}
    }
    
    for row in stats_by_source:
        source = row[0]
        aggregated['bySource'][source] = {
            'views': row[1] or 0,
            'clicks': row[2] or 0,
            'rating': row[3] or 0,
            'reviews': row[4] or 0
        }
        aggregated['totalViews'] += row[1] or 0
        aggregated['totalClicks'] += row[2] or 0
        aggregated['totalReviews'] += row[4] or 0
    
    # Вычисляем средний рейтинг
    ratings = [s['rating'] for s in aggregated['bySource'].values() if s['rating'] > 0]
    if ratings:
        aggregated['avgRating'] = sum(ratings) / len(ratings)
    
    return jsonify({"success": True, "stats": aggregated})
```

---

## Проблема 3: Статус парсинга в Дашборде

### Анализ

**Текущая ситуация:**
- Парсинг запускается из `CardOverviewPage.tsx`
- Статус парсинга должен отображаться в `MapParseTable` в Дашборде
- Сейчас функционал не работает

**Требование:**
- После запуска парсинга статус должен появляться в блоке "Парсинг карт" в Дашборде
- Показывать статус в реальном времени (queued, processing, done, error)

### Решение

**1. Обновление MapParseTable для отображения статуса:**

**Файл:** `frontend/src/components/MapParseTable.tsx`

```tsx
const MapParseTable: React.FC<MapParseTableProps> = ({ businessId }) => {
  const [parseStatus, setParseStatus] = useState<Record<string, string>>({});
  
  // Проверяем статус парсинга для каждой ссылки на карту
  useEffect(() => {
    const checkParseStatus = async () => {
      if (!businessId) return;
      
      try {
        const token = localStorage.getItem('auth_token');
        
        // Получаем ссылки на карты
        const linksRes = await fetch(`${window.location.origin}/api/client-info?business_id=${businessId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        const linksData = await linksRes.json();
        
        if (linksData.success && linksData.mapLinks) {
          const statuses: Record<string, string> = {};
          
          // Проверяем статус для каждой ссылки
          for (const link of linksData.mapLinks) {
            const statusRes = await fetch(`${window.location.origin}/api/map-parse/status?url=${encodeURIComponent(link.url)}`, {
              headers: { 'Authorization': `Bearer ${token}` }
            });
            const statusData = await statusRes.json();
            
            if (statusData.success) {
              statuses[link.url] = statusData.status || 'idle';
            }
          }
          
          setParseStatus(statuses);
        }
      } catch (e) {
        console.error('Ошибка проверки статуса парсинга:', e);
      }
    };
    
    checkParseStatus();
    
    // Проверяем каждые 3 секунды, если есть активные парсинги
    const interval = setInterval(() => {
      const hasActive = Object.values(parseStatus).some(s => s === 'queued' || s === 'processing');
      if (hasActive) {
        checkParseStatus();
      }
    }, 3000);
    
    return () => clearInterval(interval);
  }, [businessId, parseStatus]);
  
  const getStatusBadge = (status: string) => {
    const badges = {
      'queued': <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-xs">В очереди</span>,
      'processing': <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">Обработка</span>,
      'done': <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs">Завершено</span>,
      'error': <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs">Ошибка</span>,
      'captcha': <span className="px-2 py-1 bg-orange-100 text-orange-800 rounded text-xs">Капча</span>
    };
    return badges[status as keyof typeof badges] || <span className="px-2 py-1 bg-gray-100 text-gray-800 rounded text-xs">Неизвестно</span>;
  };
  
  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      {/* ... существующий код ... */}
      
      {/* Добавляем колонку со статусом */}
      <th className="px-3 py-2 border-b text-left">Статус</th>
      
      {/* В таблице */}
      <td className="px-3 py-2 border-b">
        {getStatusBadge(parseStatus[item.url] || 'idle')}
      </td>
    </div>
  );
};
```

**2. Backend endpoint для статуса парсинга:**

**Файл:** `src/main.py`

```python
@app.route('/api/map-parse/status', methods=['GET'])
def get_map_parse_status():
    """Получить статус парсинга по URL"""
    # ... проверка авторизации ...
    
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "URL обязателен"}), 400
    
    # Ищем последнюю задачу парсинга для этого URL
    cursor.execute("""
        SELECT status, error_message, created_at
        FROM ParseQueue
        WHERE url = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (url,))
    
    row = cursor.fetchone()
    if row:
        return jsonify({
            "success": True,
            "status": row[0],
            "error": row[1],
            "created_at": row[2]
        })
    else:
        return jsonify({
            "success": True,
            "status": "idle"
        })
```

---

## Порядок выполнения

1. **Подвкладки в "Работа с картами"**
   - Добавить определение типа карты по URL
   - Загрузить ссылки на карты
   - Создать UI с подвкладками
   - Фильтровать данные по активной вкладке

2. **Переименование "Прогресс" → "Дашборд"**
   - Переименовать файл и компонент
   - Обновить маршруты
   - Добавить агрегированную статистику
   - Создать backend endpoint для статистики

3. **Статус парсинга в Дашборде**
   - Обновить MapParseTable для отображения статуса
   - Создать backend endpoint для статуса
   - Добавить автоматическое обновление статуса

---

## Чеклист для кодера

### Подвкладки в "Работа с картами"
- [ ] Добавить функцию `detectMapType()` в `CardOverviewPage.tsx`
- [ ] Загрузить ссылки на карты из API
- [ ] Создать UI с подвкладками (Tabs)
- [ ] Фильтровать услуги, отзывы, новости по активной вкладке
- [ ] Протестировать переключение между вкладками

### Переименование "Прогресс" → "Дашборд"
- [ ] Переименовать `ProgressPage.tsx` → `DashboardPage.tsx`
- [ ] Обновить импорты в `App.tsx`
- [ ] Обновить маршруты (добавить редирект со старого)
- [ ] Создать backend endpoint `/api/business/<id>/dashboard/stats`
- [ ] Добавить агрегированную статистику в UI
- [ ] Добавить графики прогресса (опционально, по дизайну)

### Статус парсинга в Дашборде
- [ ] Обновить `MapParseTable.tsx` для отображения статуса
- [ ] Создать backend endpoint `/api/map-parse/status`
- [ ] Добавить автоматическое обновление статуса (polling)
- [ ] Добавить визуальные индикаторы статуса (badges)
- [ ] Протестировать отображение статуса

---

## Важные замечания

1. **Определение типа карты:**
   - Использовать URL для определения типа
   - Сохранять `map_type` в `BusinessMapLinks` при сохранении
   - Иметь fallback для неизвестных типов

2. **Агрегированная статистика:**
   - Собирать данные из `ExternalBusinessStats` для всех источников
   - Вычислять средние значения и суммы
   - Показывать разбивку по источникам

3. **Статус парсинга:**
   - Проверять статус из `ParseQueue`
   - Обновлять статус в реальном времени (polling)
   - Показывать понятные индикаторы статуса

---

## Ожидаемый результат

**После выполнения:**
- В "Работа с картами" есть подвкладки по сервисам карт
- Страница "Прогресс" переименована в "Дашборд"
- Дашборд показывает агрегированную статистику со всех карт
- Статус парсинга отображается в блоке "Парсинг карт" в Дашборде
- Статус обновляется в реальном времени

