import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { RefreshCw, Play, Trash2, AlertTriangle, Sync } from 'lucide-react';
import { newAuth } from '../lib/auth_new';
import { useToast } from '../hooks/use-toast';

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
  updated_at?: string;
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
  const { toast } = useToast();

  const loadTasks = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const token = await newAuth.getToken();
      if (!token) {
        setError('Требуется авторизация');
        return;
      }
      
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
      const token = await newAuth.getToken();
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
  }, [filters.status, filters.task_type, filters.source]);

  const handleRestart = async (taskId: string) => {
    if (!confirm('Перезапустить эту задачу?')) return;
    
    try {
      const token = await newAuth.getToken();
      if (!token) return;
      
      const res = await fetch(`/api/admin/parsing/tasks/${taskId}/restart`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Ошибка перезапуска задачи');
      }
      
      toast({
        title: 'Успешно',
        description: 'Задача перезапущена',
      });
      
      await loadTasks();
      await loadStats();
    } catch (e: any) {
      toast({
        title: 'Ошибка',
        description: e.message || 'Ошибка перезапуска задачи',
        variant: 'destructive',
      });
    }
  };

  const handleDelete = async (taskId: string) => {
    if (!confirm('Удалить эту задачу из очереди?')) return;
    
    try {
      const token = await newAuth.getToken();
      if (!token) return;
      
      const res = await fetch(`/api/admin/parsing/tasks/${taskId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Ошибка удаления задачи');
      }
      
      toast({
        title: 'Успешно',
        description: 'Задача удалена',
      });
      
      await loadTasks();
      await loadStats();
    } catch (e: any) {
      toast({
        title: 'Ошибка',
        description: e.message || 'Ошибка удаления задачи',
        variant: 'destructive',
      });
    }
  };

  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { label: string; className: string }> = {
      'pending': { label: 'Ожидает', className: 'bg-yellow-50 text-yellow-800 border-yellow-200' },
      'processing': { label: 'Обработка', className: 'bg-blue-50 text-blue-800 border-blue-200' },
      'done': { label: 'Завершено', className: 'bg-green-50 text-green-800 border-green-200' },
      'error': { label: 'Ошибка', className: 'bg-red-50 text-red-800 border-red-200' },
      'captcha': { label: 'Капча', className: 'bg-orange-50 text-orange-800 border-orange-200' }
    };
    
    const config = statusConfig[status] || { label: status, className: 'bg-gray-50 text-gray-800 border-gray-200' };
    
    return (
      <Badge variant="outline" className={config.className}>
        {config.label}
      </Badge>
    );
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
          <h2 className="text-2xl font-bold text-foreground">Управление парсингом</h2>
          <p className="text-muted-foreground mt-1">Мониторинг и управление задачами парсинга</p>
        </div>
        <Button onClick={() => { loadTasks(); loadStats(); }} disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Обновить
        </Button>
      </div>

      {error && (
        <div className="bg-destructive/10 border border-destructive/20 text-destructive px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Статистика */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Всего задач</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_tasks}</div>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Ожидают</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-yellow-600">{stats.by_status?.pending || 0}</div>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Обрабатываются</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">{stats.by_status?.processing || 0}</div>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Зависшие</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">{stats.stuck_tasks_count || 0}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Предупреждение о зависших задачах */}
      {stats && stats.stuck_tasks_count > 0 && (
        <div className="bg-orange-50 dark:bg-orange-950 border border-orange-200 dark:border-orange-800 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-orange-600 dark:text-orange-400 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-orange-900 dark:text-orange-100 mb-1">
                Обнаружены зависшие задачи ({stats.stuck_tasks_count})
              </h3>
              <p className="text-sm text-orange-800 dark:text-orange-200">
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
              <label className="block text-sm font-medium text-foreground mb-1">Статус</label>
              <select
                value={filters.status}
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
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
              <label className="block text-sm font-medium text-foreground mb-1">Тип задачи</label>
              <select
                value={filters.task_type}
                onChange={(e) => setFilters({ ...filters, task_type: e.target.value })}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="">Все типы</option>
                <option value="parse_card">Парсинг карты</option>
                <option value="sync_yandex_business">Синхронизация Яндекс.Бизнес</option>
                <option value="parse_cabinet_fallback">Парсинг из кабинета</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Источник</label>
              <select
                value={filters.source}
                onChange={(e) => setFilters({ ...filters, source: e.target.value })}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
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
            <div className="text-center py-8 text-muted-foreground">Загрузка...</div>
          ) : tasks.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">Нет задач</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border">
                <thead className="bg-muted">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">ID</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Бизнес</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Тип</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Источник</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Статус</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">URL</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Создано</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Ошибка</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Действия</th>
                  </tr>
                </thead>
                <tbody className="bg-card divide-y divide-border">
                  {tasks.map((task) => (
                    <tr key={task.id} className="hover:bg-muted/50">
                      <td className="px-4 py-3 text-sm font-mono text-foreground">
                        {task.id.substring(0, 8)}...
                      </td>
                      <td className="px-4 py-3 text-sm text-foreground">
                        {task.business_name || task.business_id || '—'}
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {getTaskTypeLabel(task.task_type)}
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {task.source || '—'}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {getStatusBadge(task.status)}
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground max-w-xs truncate">
                        {task.url ? (
                          <a href={task.url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                            {task.url.substring(0, 40)}...
                          </a>
                        ) : '—'}
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {new Date(task.created_at).toLocaleString('ru-RU')}
                      </td>
                      <td className="px-4 py-3 text-sm text-destructive max-w-xs truncate" title={task.error_message}>
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
                          {task.task_type !== 'sync_yandex_business' && task.business_id && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleSwitchToSync(task.id, task.business_id)}
                              className="text-blue-600 hover:text-blue-700"
                              title="Переключить на синхронизацию с Яндекс.Бизнес"
                            >
                              <Sync className="w-4 h-4" />
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleDelete(task.id)}
                            className="text-destructive hover:text-destructive"
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
