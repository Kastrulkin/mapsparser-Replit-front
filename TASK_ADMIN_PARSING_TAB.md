# Задача: Вкладка "Парсинг" в административной панели

**Дата:** 2025-01-06  
**Приоритет:** Высокий  
**Исполнитель:** Кодер

---

## Цель

Добавить в административную панель "Базич" (`AdminPage.tsx`) новую вкладку "Парсинг" для мониторинга и управления задачами парсинга. Администратор должен видеть:
- Запущенные парсеры и их статусы
- Список задач из ParseQueue с детальной информацией
- Возможность перезапустить зависшие задачи
- Обновление статусов по кнопке (без постоянного polling)

---

## Текущее состояние

**ParseQueue структура:**
- `id` - ID задачи
- `url` - URL для парсинга (для parse_card)
- `user_id` - ID пользователя
- `business_id` - ID бизнеса
- `task_type` - тип задачи ('parse_card', 'sync_yandex_business', 'parse_cabinet_fallback')
- `account_id` - ID аккаунта (для sync задач)
- `source` - источник ('yandex_maps', 'yandex_business', 'google_business', '2gis')
- `status` - статус ('pending', 'processing', 'done', 'error', 'captcha')
- `retry_after` - время повторной попытки (для captcha)
- `error_message` - сообщение об ошибке
- `created_at` - время создания
- `updated_at` - время последнего обновления

**Статусы задач:**
- `pending` - ожидает обработки
- `processing` - обрабатывается
- `done` - завершена успешно
- `error` - ошибка
- `captcha` - обнаружена капча

---

## Архитектура решения

### 1. Backend API эндпоинты

**Файл:** `src/main.py` или `src/api/admin_api.py` (создать Blueprint)

**Эндпоинт 1: Получить список задач парсинга**

```python
@app.route('/api/admin/parsing/tasks', methods=['GET'])
def get_parsing_tasks():
    """
    Получить список задач парсинга для администратора
    
    Query параметры:
    - status: фильтр по статусу (pending, processing, done, error, captcha)
    - task_type: фильтр по типу задачи
    - source: фильтр по источнику
    - limit: количество задач (по умолчанию 50)
    - offset: смещение для пагинации
    
    Returns:
    - tasks: список задач с детальной информацией
    - total: общее количество задач
    - stats: статистика по статусам
    """
    # Проверка авторизации и прав суперадмина
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Требуется авторизация"}), 401
    
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    if not user_data:
        return jsonify({"error": "Недействительный токен"}), 401
    
    # Проверка прав суперадмина
    if not user_data.get('is_superadmin'):
        return jsonify({"error": "Требуются права администратора"}), 403
    
    # Получаем параметры фильтрации
    status_filter = request.args.get('status')
    task_type_filter = request.args.get('task_type')
    source_filter = request.args.get('source')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    # Формируем WHERE условия
    where_conditions = []
    params = []
    
    if status_filter:
        where_conditions.append("status = ?")
        params.append(status_filter)
    
    if task_type_filter:
        where_conditions.append("task_type = ?")
        params.append(task_type_filter)
    
    if source_filter:
        where_conditions.append("source = ?")
        params.append(source_filter)
    
    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
    
    # Получаем задачи
    cursor.execute(f"""
        SELECT 
            id, url, user_id, business_id, task_type, account_id, source,
            status, retry_after, error_message, created_at, updated_at
        FROM ParseQueue
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """, params + [limit, offset])
    
    rows = cursor.fetchall()
    
    # Получаем общее количество
    cursor.execute(f"""
        SELECT COUNT(*) FROM ParseQueue WHERE {where_clause}
    """, params)
    total = cursor.fetchone()[0]
    
    # Получаем статистику по статусам
    cursor.execute("""
        SELECT 
            status,
            COUNT(*) as count
        FROM ParseQueue
        GROUP BY status
    """)
    status_stats = {row[0]: row[1] for row in cursor.fetchall()}
    
    # Получаем информацию о бизнесах для отображения
    tasks = []
    for row in rows:
        task_dict = {
            'id': row[0],
            'url': row[1],
            'user_id': row[2],
            'business_id': row[3],
            'task_type': row[4] or 'parse_card',
            'account_id': row[5],
            'source': row[6],
            'status': row[7],
            'retry_after': row[8],
            'error_message': row[9],
            'created_at': row[10],
            'updated_at': row[11]
        }
        
        # Получаем название бизнеса
        if task_dict['business_id']:
            cursor.execute("SELECT name FROM Businesses WHERE id = ?", (task_dict['business_id'],))
            business_row = cursor.fetchone()
            task_dict['business_name'] = business_row[0] if business_row else None
        else:
            task_dict['business_name'] = None
        
        tasks.append(task_dict)
    
    db.close()
    
    return jsonify({
        "success": True,
        "tasks": tasks,
        "total": total,
        "stats": status_stats
    })
```

**Эндпоинт 2: Перезапустить задачу**

```python
@app.route('/api/admin/parsing/tasks/<task_id>/restart', methods=['POST'])
def restart_parsing_task(task_id):
    """
    Перезапустить задачу парсинга (сбросить статус на pending)
    
    Args:
        task_id: ID задачи из ParseQueue
    
    Returns:
        success: True/False
    """
    # Проверка авторизации и прав суперадмина
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Требуется авторизация"}), 401
    
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    if not user_data:
        return jsonify({"error": "Недействительный токен"}), 401
    
    if not user_data.get('is_superadmin'):
        return jsonify({"error": "Требуются права администратора"}), 403
    
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    # Проверяем, существует ли задача
    cursor.execute("SELECT id, status FROM ParseQueue WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    
    if not task:
        db.close()
        return jsonify({"error": "Задача не найдена"}), 404
    
    current_status = task[1]
    
    # Перезапускаем задачу (сбрасываем статус на pending)
    cursor.execute("""
        UPDATE ParseQueue
        SET status = 'pending',
            error_message = NULL,
            retry_after = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (task_id,))
    
    db.conn.commit()
    db.close()
    
    return jsonify({
        "success": True,
        "message": f"Задача перезапущена (был статус: {current_status})"
    })
```

**Эндпоинт 3: Удалить задачу**

```python
@app.route('/api/admin/parsing/tasks/<task_id>', methods=['DELETE'])
def delete_parsing_task(task_id):
    """
    Удалить задачу из очереди
    
    Args:
        task_id: ID задачи из ParseQueue
    
    Returns:
        success: True/False
    """
    # Проверка авторизации и прав суперадмина
    # ... аналогично restart_parsing_task ...
    
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    cursor.execute("DELETE FROM ParseQueue WHERE id = ?", (task_id,))
    db.conn.commit()
    db.close()
    
    return jsonify({"success": True, "message": "Задача удалена"})
```

**Эндпоинт 4: Получить статистику парсинга**

```python
@app.route('/api/admin/parsing/stats', methods=['GET'])
def get_parsing_stats():
    """
    Получить общую статистику парсинга
    
    Returns:
        - total_tasks: общее количество задач
        - by_status: разбивка по статусам
        - by_task_type: разбивка по типам задач
        - by_source: разбивка по источникам
        - stuck_tasks: задачи в статусе processing более 30 минут
    """
    # Проверка авторизации и прав суперадмина
    # ... аналогично get_parsing_tasks ...
    
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    # Общая статистика
    cursor.execute("SELECT COUNT(*) FROM ParseQueue")
    total_tasks = cursor.fetchone()[0]
    
    # По статусам
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM ParseQueue
        GROUP BY status
    """)
    by_status = {row[0]: row[1] for row in cursor.fetchall()}
    
    # По типам задач
    cursor.execute("""
        SELECT task_type, COUNT(*) as count
        FROM ParseQueue
        GROUP BY task_type
    """)
    by_task_type = {row[0] or 'parse_card': row[1] for row in cursor.fetchall()}
    
    # По источникам
    cursor.execute("""
        SELECT source, COUNT(*) as count
        FROM ParseQueue
        WHERE source IS NOT NULL
        GROUP BY source
    """)
    by_source = {row[0]: row[1] for row in cursor.fetchall()}
    
    # Зависшие задачи (processing более 30 минут)
    cursor.execute("""
        SELECT id, business_id, task_type, created_at, updated_at
        FROM ParseQueue
        WHERE status = 'processing'
          AND updated_at < datetime('now', '-30 minutes')
    """)
    stuck_tasks = []
    for row in cursor.fetchall():
        stuck_tasks.append({
            'id': row[0],
            'business_id': row[1],
            'task_type': row[2],
            'created_at': row[3],
            'updated_at': row[4]
        })
    
    db.close()
    
    return jsonify({
        "success": True,
        "stats": {
            "total_tasks": total_tasks,
            "by_status": by_status,
            "by_task_type": by_task_type,
            "by_source": by_source,
            "stuck_tasks_count": len(stuck_tasks),
            "stuck_tasks": stuck_tasks
        }
    })
```

---

### 2. Frontend компонент

**Файл:** `frontend/src/components/ParsingManagement.tsx` (создать)

```tsx
import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { RefreshCw, Play, Trash2, AlertTriangle } from 'lucide-react';
import { newAuth } from '@/lib/auth_new';

interface ParsingTask {
  id: string;
  url?: string;
  user_id: string;
  business_id?: string;
  business_name?: string;
  task_type: string;
  account_id?: string;
  source?: string;
  status: 'pending' | 'processing' | 'done' | 'error' | 'captcha';
  retry_after?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

interface ParsingStats {
  total_tasks: number;
  by_status: Record<string, number>;
  by_task_type: Record<string, number>;
  by_source: Record<string, number>;
  stuck_tasks_count: number;
  stuck_tasks: Array<{
    id: string;
    business_id?: string;
    task_type: string;
    created_at: string;
    updated_at: string;
  }>;
}

export const ParsingManagement: React.FC = () => {
  const [tasks, setTasks] = useState<ParsingTask[]>([]);
  const [stats, setStats] = useState<ParsingStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    status: '',
    task_type: '',
    source: ''
  });

  const loadTasks = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const token = newAuth.getToken();
      if (!token) return;
      
      const params = new URLSearchParams();
      if (filters.status) params.append('status', filters.status);
      if (filters.task_type) params.append('task_type', filters.task_type);
      if (filters.source) params.append('source', filters.source);
      params.append('limit', '50');
      
      const res = await fetch(`/api/admin/parsing/tasks?${params.toString()}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Ошибка загрузки задач');
      }
      
      setTasks(data.tasks || []);
    } catch (e: any) {
      setError(e.message || 'Ошибка загрузки задач');
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const token = newAuth.getToken();
      if (!token) return;
      
      const res = await fetch('/api/admin/parsing/stats', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      const data = await res.json();
      if (data.success) {
        setStats(data.stats);
      }
    } catch (e) {
      console.error('Ошибка загрузки статистики:', e);
    }
  };

  useEffect(() => {
    loadTasks();
    loadStats();
  }, [filters]);

  const handleRestart = async (taskId: string) => {
    if (!confirm('Перезапустить эту задачу?')) return;
    
    try {
      const token = newAuth.getToken();
      if (!token) return;
      
      const res = await fetch(`/api/admin/parsing/tasks/${taskId}/restart`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Ошибка перезапуска задачи');
      }
      
      // Обновляем список задач
      await loadTasks();
      await loadStats();
    } catch (e: any) {
      setError(e.message || 'Ошибка перезапуска задачи');
    }
  };

  const handleDelete = async (taskId: string) => {
    if (!confirm('Удалить эту задачу из очереди?')) return;
    
    try {
      const token = newAuth.getToken();
      if (!token) return;
      
      const res = await fetch(`/api/admin/parsing/tasks/${taskId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Ошибка удаления задачи');
      }
      
      // Обновляем список задач
      await loadTasks();
      await loadStats();
    } catch (e: any) {
      setError(e.message || 'Ошибка удаления задачи');
    }
  };

  const getStatusBadge = (status: string) => {
    const badges = {
      'pending': <Badge variant="outline" className="bg-yellow-50 text-yellow-800">Ожидает</Badge>,
      'processing': <Badge variant="outline" className="bg-blue-50 text-blue-800">Обработка</Badge>,
      'done': <Badge variant="outline" className="bg-green-50 text-green-800">Завершено</Badge>,
      'error': <Badge variant="outline" className="bg-red-50 text-red-800">Ошибка</Badge>,
      'captcha': <Badge variant="outline" className="bg-orange-50 text-orange-800">Капча</Badge>
    };
    return badges[status as keyof typeof badges] || <Badge variant="outline">{status}</Badge>;
  };

  const getTaskTypeLabel = (taskType: string) => {
    const labels: Record<string, string> = {
      'parse_card': 'Парсинг карты',
      'sync_yandex_business': 'Синхронизация Яндекс.Бизнес',
      'parse_cabinet_fallback': 'Парсинг из кабинета (fallback)'
    };
    return labels[taskType] || taskType;
  };

  return (
    <div className="space-y-6">
      {/* Заголовок с кнопкой обновления */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Управление парсингом</h2>
          <p className="text-gray-600 mt-1">Мониторинг и управление задачами парсинга</p>
        </div>
        <Button onClick={() => { loadTasks(); loadStats(); }} disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Обновить
        </Button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* Статистика */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Всего задач</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_tasks}</div>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Ожидают</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-yellow-600">{stats.by_status.pending || 0}</div>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Обрабатываются</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">{stats.by_status.processing || 0}</div>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Зависшие</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">{stats.stuck_tasks_count}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Предупреждение о зависших задачах */}
      {stats && stats.stuck_tasks_count > 0 && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-orange-600 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-orange-900 mb-1">
                Обнаружены зависшие задачи ({stats.stuck_tasks_count})
              </h3>
              <p className="text-sm text-orange-800">
                Задачи в статусе "processing" более 30 минут. Рекомендуется перезапустить их.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Фильтры */}
      <Card>
        <CardHeader>
          <CardTitle>Фильтры</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Статус</label>
              <select
                value={filters.status}
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                className="w-full rounded-md border border-gray-300 px-3 py-2"
              >
                <option value="">Все статусы</option>
                <option value="pending">Ожидает</option>
                <option value="processing">Обработка</option>
                <option value="done">Завершено</option>
                <option value="error">Ошибка</option>
                <option value="captcha">Капча</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Тип задачи</label>
              <select
                value={filters.task_type}
                onChange={(e) => setFilters({ ...filters, task_type: e.target.value })}
                className="w-full rounded-md border border-gray-300 px-3 py-2"
              >
                <option value="">Все типы</option>
                <option value="parse_card">Парсинг карты</option>
                <option value="sync_yandex_business">Синхронизация Яндекс.Бизнес</option>
                <option value="parse_cabinet_fallback">Парсинг из кабинета</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Источник</label>
              <select
                value={filters.source}
                onChange={(e) => setFilters({ ...filters, source: e.target.value })}
                className="w-full rounded-md border border-gray-300 px-3 py-2"
              >
                <option value="">Все источники</option>
                <option value="yandex_maps">Яндекс.Карты</option>
                <option value="yandex_business">Яндекс.Бизнес</option>
                <option value="google_business">Google Business</option>
                <option value="2gis">2ГИС</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Список задач */}
      <Card>
        <CardHeader>
          <CardTitle>Задачи парсинга</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-gray-500">Загрузка...</div>
          ) : tasks.length === 0 ? (
            <div className="text-center py-8 text-gray-500">Нет задач</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Бизнес</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Тип</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Источник</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">URL</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Создано</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Обновлено</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ошибка</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Действия</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {tasks.map((task) => (
                    <tr key={task.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-mono text-gray-900">
                        {task.id.substring(0, 8)}...
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {task.business_name || task.business_id || '—'}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {getTaskTypeLabel(task.task_type)}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {task.source || '—'}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {getStatusBadge(task.status)}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600 max-w-xs truncate">
                        {task.url ? (
                          <a href={task.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                            {task.url}
                          </a>
                        ) : '—'}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {new Date(task.created_at).toLocaleString('ru-RU')}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {new Date(task.updated_at).toLocaleString('ru-RU')}
                      </td>
                      <td className="px-4 py-3 text-sm text-red-600 max-w-xs truncate" title={task.error_message}>
                        {task.error_message || '—'}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <div className="flex gap-2">
                          {(task.status === 'error' || task.status === 'captcha' || 
                            (task.status === 'processing' && stats?.stuck_tasks.some(st => st.id === task.id))) && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleRestart(task.id)}
                              title="Перезапустить задачу"
                            >
                              <Play className="w-4 h-4" />
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleDelete(task.id)}
                            className="text-red-600 hover:text-red-700"
                            title="Удалить задачу"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
```

---

### 3. Интеграция в AdminPage

**Файл:** `frontend/src/pages/dashboard/AdminPage.tsx`

**Добавить вкладку "Парсинг":**

```tsx
// В начале файла
import { ParsingManagement } from '../../components/ParsingManagement';

// В состоянии
const [activeTab, setActiveTab] = useState<'businesses' | 'agents' | 'tokens' | 'growth' | 'prompts' | 'proxies' | 'parsing'>('businesses');

// В JSX с вкладками
<div className="border-b border-gray-200">
  <nav className="flex space-x-8" aria-label="Tabs">
    <button
      onClick={() => setActiveTab('businesses')}
      className={activeTab === 'businesses' ? 'border-b-2 border-primary text-primary' : 'text-gray-500 hover:text-gray-700'}
    >
      Бизнесы
    </button>
    {/* ... другие вкладки ... */}
    <button
      onClick={() => setActiveTab('parsing')}
      className={activeTab === 'parsing' ? 'border-b-2 border-primary text-primary' : 'text-gray-500 hover:text-gray-700'}
    >
      Парсинг
    </button>
  </nav>
</div>

// В контенте вкладок
{activeTab === 'parsing' && <ParsingManagement />}
```

---

## Порядок выполнения

1. **Backend API эндпоинты**
   - Создать эндпоинт `/api/admin/parsing/tasks` для получения списка задач
   - Создать эндпоинт `/api/admin/parsing/tasks/<id>/restart` для перезапуска
   - Создать эндпоинт `/api/admin/parsing/tasks/<id>` (DELETE) для удаления
   - Создать эндпоинт `/api/admin/parsing/stats` для статистики

2. **Frontend компонент**
   - Создать `ParsingManagement.tsx` компонент
   - Реализовать загрузку задач и статистики
   - Реализовать фильтры по статусу, типу, источнику
   - Реализовать кнопки перезапуска и удаления
   - Добавить визуальные индикаторы статусов

3. **Интеграция в AdminPage**
   - Добавить вкладку "Парсинг" в навигацию
   - Подключить компонент `ParsingManagement`

---

## Чеклист для кодера

### Backend
- [ ] Создать эндпоинт `/api/admin/parsing/tasks` (GET) с фильтрацией
- [ ] Создать эндпоинт `/api/admin/parsing/tasks/<id>/restart` (POST)
- [ ] Создать эндпоинт `/api/admin/parsing/tasks/<id>` (DELETE)
- [ ] Создать эндпоинт `/api/admin/parsing/stats` (GET)
- [ ] Добавить проверку прав суперадмина во все эндпоинты
- [ ] Протестировать все эндпоинты

### Frontend
- [ ] Создать компонент `ParsingManagement.tsx`
- [ ] Реализовать загрузку задач и статистики
- [ ] Реализовать фильтры (статус, тип, источник)
- [ ] Реализовать кнопку "Обновить" (без автоматического polling)
- [ ] Реализовать кнопки перезапуска и удаления задач
- [ ] Добавить визуальные индикаторы статусов (badges)
- [ ] Показывать предупреждение о зависших задачах
- [ ] Добавить вкладку "Парсинг" в `AdminPage.tsx`
- [ ] Протестировать UI

---

## Важные замечания

1. **Обновление статусов:**
   - Статусы обновляются по кнопке "Обновить" (без постоянного polling)
   - Пользователь сам решает, когда обновить данные

2. **Зависшие задачи:**
   - Задачи в статусе "processing" более 30 минут считаются зависшими
   - Показывать предупреждение и возможность массового перезапуска

3. **Безопасность:**
   - Все эндпоинты доступны только суперадмину
   - Проверять права доступа перед каждым действием

4. **UX:**
   - Показывать понятные статусы с цветовыми индикаторами
   - Показывать название бизнеса вместо ID
   - Обрезать длинные URL и error_message с tooltip

---

## Ожидаемый результат

**После выполнения:**
- В административной панели есть вкладка "Парсинг"
- Администратор видит все задачи парсинга с детальной информацией
- Можно фильтровать задачи по статусу, типу, источнику
- Можно перезапустить зависшие или ошибочные задачи
- Можно удалить задачи из очереди
- Статистика показывает общее состояние парсинга
- Предупреждение о зависших задачах
- Обновление статусов по кнопке (без постоянного polling)

