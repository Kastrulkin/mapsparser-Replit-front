import React, { useState, useEffect, useCallback } from 'react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { RefreshCw, Play, Trash2, AlertTriangle, ArrowLeftRight, Copy, Loader2 } from 'lucide-react'; // Force rebuild
import { newAuth } from '../lib/auth_new';
import { useToast } from '../hooks/use-toast';
import { useLanguage } from '@/i18n/LanguageContext';

interface ParsingTask {
  id: string;
  url?: string;
  user_id: string;
  business_id?: string;
  business_name?: string;
  task_type: string;
  account_id?: string;
  source?: string;
  status: 'pending' | 'processing' | 'completed' | 'error' | 'captcha';
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
  const { t } = useLanguage();
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



  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const token = await newAuth.getToken();
      if (!token) return;

      const headers = { 'Authorization': `Bearer ${token}` };
      const timestamp = Date.now();

      // Parallel data fetching to eliminate waterfall
      const [tasksRes, statsRes] = await Promise.all([
        fetch(`/api/admin/parsing/tasks?status=${filters.status}&task_type=${filters.task_type}&source=${filters.source}`, { headers }),
        fetch(`/api/admin/parsing/stats?_t=${timestamp}`, { headers })
      ]);

      if (tasksRes.status === 401 || statsRes.status === 401) {
        setError("Ошибка авторизации. Попробуйте обновить страницу.");
        return;
      }

      const [tasksData, statsData] = await Promise.all([
        tasksRes.json(),
        statsRes.json()
      ]);

      if (tasksData.tasks) setTasks(tasksData.tasks);
      else if (tasksData.error) throw new Error(tasksData.error);

      if (statsData.success) setStats(statsData.stats);

      setError(null);
    } catch (e: any) {
      console.error('Ошибка загрузки данных:', e);
      setError(e.message || 'Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  }, [filters.status, filters.task_type, filters.source]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Aliases for backward compatibility
  const loadTasks = loadData;
  const loadStats = loadData;

  const handleRestart = async (taskId: string) => {
    if (!confirm(t.dashboard.parsing.actions.restartConfirm)) return;

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
        title: t.common.success,
        description: t.dashboard.parsing.actions.successRestart,
      });

      await loadTasks();
      await loadStats();
    } catch (e: any) {
      toast({
        title: t.common.error,
        description: e.message || 'Ошибка перезапуска задачи',
        variant: 'destructive',
      });
    }
  };

  const handleDelete = async (taskId: string) => {
    if (!confirm(t.dashboard.parsing.actions.deleteConfirm)) return;

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
        title: t.common.success,
        description: t.dashboard.parsing.actions.successDelete,
      });

      await loadTasks();
      await loadStats();
    } catch (e: any) {
      toast({
        title: t.common.error,
        description: e.message || 'Ошибка удаления задачи',
        variant: 'destructive',
      });
    }
  };

  const handleSwitchToSync = async (taskId: string, businessId?: string) => {
    if (!confirm(t.dashboard.parsing.actions.switchToSyncConfirm)) return;

    try {
      const token = await newAuth.getToken();
      if (!token) return;

      const res = await fetch(`/api/admin/parsing/tasks/${taskId}/switch-to-sync`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || data.message || 'Ошибка переключения задачи');
      }

      toast({
        title: t.common.success,
        description: t.dashboard.parsing.actions.successSwitch,
      });

      await loadTasks();
      await loadStats();
    } catch (e: any) {
      toast({
        title: t.common.error,
        description: e.message || 'Ошибка переключения задачи',
        variant: 'destructive',
      });
    }
  };

  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { label: string; className: string }> = {
      'pending': { label: t.dashboard.parsing.status.pending, className: 'bg-yellow-50 text-yellow-800 border-yellow-200' },
      'processing': { label: t.dashboard.parsing.status.processing, className: 'bg-blue-50 text-blue-800 border-blue-200' },
      'completed': { label: t.dashboard.parsing.status.completed, className: 'bg-green-50 text-green-800 border-green-200' },
      'error': { label: t.dashboard.parsing.status.error, className: 'bg-red-50 text-red-800 border-red-200' },
      'captcha': { label: t.dashboard.parsing.status.captcha, className: 'bg-orange-50 text-orange-800 border-orange-200' }
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
      'parse_card': t.dashboard.parsing.type.parse_card,
      'sync_yandex_business': t.dashboard.parsing.type.sync_yandex_business,
      'parse_cabinet_fallback': t.dashboard.parsing.type.parse_cabinet_fallback,
      'deep_parsing': 'Глубокий парсинг'
    };
    return labels[taskType] || taskType;
  };

  return (
    <div className="space-y-6">
      {/* Заголовок с кнопкой обновления */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-foreground">{t.dashboard.parsing.title}</h2>
          <p className="text-muted-foreground mt-1">{t.dashboard.parsing.subtitle}</p>
        </div>
        <Button onClick={() => { loadTasks(); loadStats(); }} disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          {t.dashboard.parsing.refresh}
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
              <CardTitle className="text-sm font-medium text-muted-foreground">{t.dashboard.parsing.stats.total}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_tasks}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{t.dashboard.parsing.stats.pending}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-yellow-600">{stats.by_status?.pending || 0}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{t.dashboard.parsing.stats.processing}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">{stats.by_status?.processing || 0}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{t.dashboard.parsing.stats.stuck}</CardTitle>
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
                {t.dashboard.parsing.stats.stuckWarning} ({stats.stuck_tasks_count})
              </h3>
              <p className="text-sm text-orange-800 dark:text-orange-200">
                {t.dashboard.parsing.stats.stuckDesc}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Фильтры */}
      <Card>
        <CardHeader>
          <CardTitle>{t.dashboard.parsing.filters.title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">{t.dashboard.parsing.filters.status}</label>
              <select
                value={filters.status}
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="">{t.dashboard.parsing.filters.statusAll}</option>
                <option value="pending">{t.dashboard.parsing.status.pending}</option>
                <option value="processing">{t.dashboard.parsing.status.processing}</option>
                <option value="completed">{t.dashboard.parsing.status.completed}</option>
                <option value="error">{t.dashboard.parsing.status.error}</option>
                <option value="captcha">{t.dashboard.parsing.status.captcha}</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-1">{t.dashboard.parsing.filters.type}</label>
              <select
                value={filters.task_type}
                onChange={(e) => setFilters({ ...filters, task_type: e.target.value })}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="">{t.dashboard.parsing.filters.typeAll}</option>
                <option value="parse_card">{t.dashboard.parsing.type.parse_card}</option>
                <option value="sync_yandex_business">{t.dashboard.parsing.type.sync_yandex_business}</option>
                <option value="parse_cabinet_fallback">{t.dashboard.parsing.type.parse_cabinet_fallback}</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-1">{t.dashboard.parsing.filters.source}</label>
              <select
                value={filters.source}
                onChange={(e) => setFilters({ ...filters, source: e.target.value })}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="">{t.dashboard.parsing.filters.sourceAll}</option>
                <option value="yandex_maps">{t.dashboard.parsing.source.yandex_maps}</option>
                <option value="yandex_business">{t.dashboard.parsing.source.yandex_business}</option>
                <option value="google_business">{t.dashboard.parsing.source.google_business}</option>
                <option value="2gis">{t.dashboard.parsing.source['2gis']}</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Список задач */}
      <Card>
        <CardHeader>
          <CardTitle>{t.dashboard.parsing.table.title}</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-muted-foreground">{t.dashboard.parsing.table.loading}</div>
          ) : tasks.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">{t.dashboard.parsing.table.noTasks}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border">
                <thead className="bg-muted">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">{t.dashboard.parsing.table.id}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">{t.dashboard.parsing.table.business}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">{t.dashboard.parsing.table.type}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">{t.dashboard.parsing.table.source}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">{t.dashboard.parsing.table.status}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">{t.dashboard.parsing.table.url}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">{t.dashboard.parsing.table.created}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">{t.dashboard.parsing.table.error}</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">{t.dashboard.parsing.table.actions}</th>
                  </tr>
                </thead>
                <tbody className="bg-card divide-y divide-border">
                  {tasks.map((task) => (
                    <tr key={task.id} className="hover:bg-muted/50">
                      <td className="px-4 py-3 text-sm font-mono text-foreground">
                        <div className="flex items-center gap-2 group">
                          <code className="bg-muted px-1.5 py-0.5 rounded text-xs select-all">
                            {task.id}
                          </code>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                            onClick={() => {
                              navigator.clipboard.writeText(task.id);
                              toast({ title: "ID copied", description: task.id, duration: 2000 });
                            }}
                            title="Copy ID"
                          >
                            <Copy className="h-3 w-3" />
                          </Button>
                        </div>
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
                                title={t.dashboard.parsing.actions.restart}
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
                              title={t.dashboard.parsing.actions.switchToSync}
                            >
                              <ArrowLeftRight className="w-4 h-4" />
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleDelete(task.id)}
                            className="text-destructive hover:text-destructive"
                            title={t.dashboard.parsing.actions.delete}
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
