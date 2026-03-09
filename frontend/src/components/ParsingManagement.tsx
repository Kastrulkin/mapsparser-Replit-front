import React, { useState, useEffect, useCallback } from 'react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { RefreshCw, Play, Trash2, AlertTriangle, ArrowLeftRight, Copy, Loader2, ExternalLink, CircleSlash } from 'lucide-react';
import { newAuth } from '../lib/auth_new';
import { useToast } from '../hooks/use-toast';
import { useLanguage } from '../i18n/LanguageContext';

const TASKS_FETCH_LIMIT = 500;

interface ParsingTask {
  id: string;
  url?: string;
  user_id: string;
  business_id?: string;
  business_name?: string;
  task_type: string;
  account_id?: string;
  source?: string;
  status: 'pending' | 'processing' | 'completed' | 'error' | 'captcha' | 'paused';
  retry_after?: string;
  captcha_url?: string;
  captcha_session_id?: string;
  resume_requested?: boolean;
  error_message?: string;
  batch_id?: string;
  batch_kind?: string;
  network_id?: string;
  batch_seq?: number;
  paused_reason?: string;
  short_error_code?: string;
  short_error_message?: string;
  can_resume_batch?: boolean;
  can_open_captcha?: boolean;
  can_restart_task?: boolean;
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
  paused_batches_count?: number;
  paused_batches?: Array<{
    batch_id: string;
    tasks_count: number;
  }>;
  operator_summary?: {
    active_runs: number;
    action_required_count: number;
    captcha_waiting_count: number;
    error_count: number;
    completed_today: number;
  };
  captcha_queue?: Array<{
    task_id: string;
    business_id?: string;
    business_name?: string;
    url?: string;
    captcha_url?: string;
    captcha_session_id?: string;
    captcha_started_at?: string;
    retry_after?: string;
    resume_requested?: boolean;
    created_at?: string;
    is_expired?: boolean;
    short_error_message?: string;
  }>;
  recoverable_batches_count?: number;
  recoverable_batches?: Array<{
    batch_id: string;
    business_id?: string;
    business_name?: string;
    source?: string;
    tasks_count: number;
    paused_count: number;
    error_count: number;
    completed_count: number;
    pending_count: number;
    processing_count: number;
    captcha_count: number;
    current_seq?: number;
    first_failed_seq?: number;
    last_activity_at?: string;
    last_error_short?: string;
    last_error_code?: string;
    resume_available?: boolean;
  }>;
  network_batches?: Array<{
    batch_id: string;
    business_id?: string;
    business_name?: string;
    source?: string;
    tasks_count: number;
    completed_count: number;
    pending_count: number;
    processing_count: number;
    paused_count: number;
    error_count: number;
    captcha_count: number;
    current_seq?: number;
    first_failed_seq?: number;
    last_activity_at?: string;
    last_error_short?: string;
    last_error_code?: string;
    resume_available?: boolean;
    status: 'pending' | 'processing' | 'completed' | 'paused' | 'error' | 'captcha' | 'partial';
    status_label: string;
    progress_percent: number;
  }>;
}

export const ParsingManagement: React.FC = () => {
  const { t } = useLanguage();
  const [tasks, setTasks] = useState<ParsingTask[]>([]);
  const [tasksTotal, setTasksTotal] = useState(0);
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
        fetch(`/api/admin/parsing/tasks?status=${filters.status}&task_type=${filters.task_type}&source=${filters.source}&limit=${TASKS_FETCH_LIMIT}&offset=0`, { headers }),
        fetch(`/api/admin/parsing/stats?_t=${timestamp}`, { headers })
      ]);

      if (tasksRes.status === 401 || statsRes.status === 401) {
        setError("Ошибка авторизации. Попробуйте обновить страницу.");
        return;
      }

      const [tasksData, statsData] = await Promise.all([
        tasksRes.json().catch(() => ({})),
        statsRes.json().catch(() => ({}))
      ]);

      if (!tasksRes.ok) {
        console.error('Parsing tasks failed:', tasksRes.status, tasksRes.url, tasksData);
        throw new Error((tasksData as { error?: string })?.error || `HTTP ${tasksRes.status}`);
      }
      if (!statsRes.ok) {
        console.error('Parsing stats failed:', statsRes.status, statsRes.url, statsData);
        throw new Error((statsData as { error?: string })?.error || `HTTP ${statsRes.status}`);
      }

      if (tasksData.tasks) setTasks(tasksData.tasks);
      if (typeof tasksData.total === 'number') setTasksTotal(tasksData.total);
      else if ((tasksData as { error?: string }).error) throw new Error((tasksData as { error?: string }).error);

      if (statsData.success) setStats(statsData.stats);

      setError(null);
    } catch (e: any) {
      console.error('Ошибка загрузки данных:', e?.message, e);
      setError(e?.message || 'Ошибка загрузки данных');
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

  const handleOpenCaptcha = async (task: ParsingTask) => {
    try {
      const token = await newAuth.getToken();
      if (!token) return;

      const res = await fetch(`/api/admin/parsing/tasks/${task.id}/captcha/open`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Не удалось открыть CAPTCHA сессию');
      }

      const url = data.captcha_url || task.captcha_url || task.url;
      if (url) {
        window.open(url, '_blank', 'noopener,noreferrer');
      }

      toast({
        title: t.common.success,
        description: data.message || 'CAPTCHA открыта. Пройдите её и нажмите Продолжить.',
      });

      await loadData();
    } catch (e: any) {
      toast({
        title: t.common.error,
        description: e.message || 'Ошибка открытия CAPTCHA',
        variant: 'destructive',
      });
    }
  };

  const handleResumeCaptcha = async (taskId?: string) => {
    if (!taskId) {
      toast({
        title: t.common.error,
        description: 'Не удалось определить задачу',
        variant: 'destructive',
      });
      return;
    }

    if (!confirm('Подтвердите, что капча уже пройдена, и запросите продолжение парсинга.')) return;

    try {
      const token = await newAuth.getToken();
      if (!token) return;

      const res = await fetch(`/api/admin/parsing/tasks/${taskId}/captcha/resume`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Ошибка продолжения после капчи');
      }

      toast({
        title: t.common.success,
        description: data.message || 'Продолжение парсинга запрошено',
      });

      await loadData();
    } catch (e: any) {
      toast({
        title: t.common.error,
        description: e.message || 'Ошибка продолжения после капчи',
        variant: 'destructive',
      });
    }
  };

  const handleExpireCaptcha = async (taskId: string) => {
    if (!confirm('Сбросить CAPTCHA-сессию и перевести задачу в ошибку?')) return;
    try {
      const token = await newAuth.getToken();
      if (!token) return;
      const res = await fetch(`/api/admin/parsing/tasks/${taskId}/captcha/expire`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Ошибка сброса CAPTCHA-сессии');
      }
      toast({
        title: t.common.success,
        description: data.message || 'CAPTCHA-сессия сброшена',
      });
      await loadData();
    } catch (e: any) {
      toast({
        title: t.common.error,
        description: e.message || 'Ошибка сброса CAPTCHA-сессии',
        variant: 'destructive',
      });
    }
  };

  const handleResumeNetworkBatch = async (batchId?: string) => {
    if (!batchId) return;
    if (!confirm('Возобновить сетевой парсинг с места ошибки?')) return;
    try {
      const token = await newAuth.getToken();
      if (!token) return;
      const res = await fetch(`/api/admin/parsing/network-batches/${batchId}/resume`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Ошибка возобновления сетевого batch');
      }
      toast({
        title: t.common.success,
        description: data.message || 'Сетевой парсинг возобновлён',
      });
      await loadData();
    } catch (e: any) {
      toast({
        title: t.common.error,
        description: e.message || 'Не удалось возобновить сетевой парсинг',
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
      'captcha': { label: t.dashboard.parsing.status.captcha, className: 'bg-orange-50 text-orange-800 border-orange-200' },
      'paused': { label: 'Пауза (ошибка в сети)', className: 'bg-amber-50 text-amber-800 border-amber-200' },
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

  const getBatchStatusBadge = (status: string, label: string) => {
    const statusConfig: Record<string, string> = {
      pending: 'bg-yellow-50 text-yellow-800 border-yellow-200',
      processing: 'bg-blue-50 text-blue-800 border-blue-200',
      completed: 'bg-green-50 text-green-800 border-green-200',
      partial: 'bg-emerald-50 text-emerald-800 border-emerald-200',
      paused: 'bg-amber-50 text-amber-800 border-amber-200',
      captcha: 'bg-orange-50 text-orange-800 border-orange-200',
      error: 'bg-red-50 text-red-800 border-red-200',
    };

    return (
      <Badge variant="outline" className={statusConfig[status] || 'bg-gray-50 text-gray-800 border-gray-200'}>
        {label}
      </Badge>
    );
  };

  const summaryCards = stats?.operator_summary ? [
    { key: 'active', label: 'Активные запуски', value: stats.operator_summary.active_runs, filter: 'processing', className: 'text-blue-600' },
    { key: 'action', label: 'Требует действия', value: stats.operator_summary.action_required_count, className: 'text-amber-700' },
    { key: 'captcha', label: 'CAPTCHA', value: stats.operator_summary.captcha_waiting_count, filter: 'captcha', className: 'text-orange-600' },
    { key: 'error', label: 'Ошибки', value: stats.operator_summary.error_count, filter: 'error', className: 'text-red-600' },
    { key: 'done', label: 'Успешно сегодня', value: stats.operator_summary.completed_today, filter: 'completed', className: 'text-green-600' },
  ] : [];

  const actionItems = [
    ...((stats?.recoverable_batches || []).map((batch) => ({
      key: `batch-${batch.batch_id}`,
      title: batch.business_name || `Batch ${batch.batch_id.slice(0, 8)}`,
      subtitle: `Сетевой запуск • ${batch.source || 'источник не указан'}`,
      description: batch.last_error_short || 'Сеть можно продолжить с места сбоя',
      meta: `Прогресс: ${batch.completed_count}/${batch.tasks_count} • paused: ${batch.paused_count} • error: ${batch.error_count}`,
      actionLabel: 'Возобновить с места сбоя',
      onAction: () => handleResumeNetworkBatch(batch.batch_id),
    }))),
    ...((stats?.captcha_queue || []).map((captchaTask) => ({
      key: `captcha-${captchaTask.task_id}`,
      title: captchaTask.business_name || `Задача ${captchaTask.task_id.slice(0, 8)}`,
      subtitle: 'Нужна CAPTCHA',
      description: captchaTask.is_expired
        ? 'Сессия истекла. Откройте новую CAPTCHA и затем продолжите.'
        : (captchaTask.short_error_message || 'Пройдите CAPTCHA и продолжите парсинг'),
      meta: captchaTask.retry_after ? `Дедлайн: ${new Date(captchaTask.retry_after).toLocaleString('ru-RU')}` : 'Ожидает действия человека',
      actionLabel: 'Открыть CAPTCHA',
      onAction: () => {
        const linkedTask = tasks.find((task) => task.id === captchaTask.task_id);
        if (linkedTask) {
          void handleOpenCaptcha(linkedTask);
        }
      },
    }))),
  ];

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
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {error}
        </div>
      )}

      {stats && summaryCards.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {summaryCards.map((item) => (
            <Card
              key={item.key}
              className={item.filter ? 'cursor-pointer transition hover:border-primary/40 hover:shadow-sm' : ''}
              onClick={item.filter ? () => setFilters((prev) => ({ ...prev, status: item.filter || '' })) : undefined}
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">{item.label}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className={`text-2xl font-bold ${item.className}`}>{item.value}</div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {actionItems.length > 0 && (
        <Card className="border-amber-200 bg-amber-50/70">
          <CardHeader>
            <CardTitle>Требует действия</CardTitle>
            <p className="text-sm text-muted-foreground">
              Сначала решите эти задачи: они блокируют продолжение парсинга или требуют human-in-the-loop.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            {actionItems.map((item) => (
              <div key={item.key} className="flex flex-col gap-3 rounded-xl border border-amber-200 bg-white p-4 md:flex-row md:items-center md:justify-between">
                <div className="space-y-1">
                  <div className="text-sm font-semibold text-foreground">{item.title}</div>
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">{item.subtitle}</div>
                  <div className="text-sm text-foreground">{item.description}</div>
                  <div className="text-xs text-muted-foreground">{item.meta}</div>
                </div>
                <Button onClick={item.onAction} variant="outline" className="border-amber-300 text-amber-900 hover:bg-amber-100">
                  {item.actionLabel}
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
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

      {stats && (stats.network_batches || []).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Сетевые запуски</CardTitle>
            <p className="text-sm text-muted-foreground">
              Основной слой для управления сетевым парсингом: прогресс, точка сбоя и возобновление с места ошибки.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            {(stats.network_batches || []).map((batch) => (
              <div key={batch.batch_id} className="rounded-xl border border-border bg-card p-4 shadow-sm">
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-base font-semibold text-foreground">
                        {batch.business_name || `Batch ${batch.batch_id.slice(0, 8)}`}
                      </div>
                      {getBatchStatusBadge(batch.status, batch.status_label)}
                    </div>
                    <div className="text-xs text-muted-foreground space-y-1">
                      <div className="font-mono break-all">batch_id: {batch.batch_id}</div>
                      <div>
                        Источник: {batch.source || 'не указан'}
                        {batch.last_activity_at ? ` • Последняя активность: ${new Date(batch.last_activity_at).toLocaleString('ru-RU')}` : ''}
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {batch.resume_available ? (
                      <Button
                        variant="outline"
                        className="border-amber-300 text-amber-900 hover:bg-amber-50"
                        onClick={() => handleResumeNetworkBatch(batch.batch_id)}
                      >
                        Возобновить с места сбоя
                      </Button>
                    ) : null}
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">
                      Прогресс: {batch.completed_count}/{batch.tasks_count}
                      {typeof batch.current_seq === 'number' ? ` • текущая точка ${batch.current_seq}` : ''}
                      {typeof batch.first_failed_seq === 'number' ? ` • сбой на ${batch.first_failed_seq}` : ''}
                    </span>
                    <span className="font-medium text-foreground">{batch.progress_percent}%</span>
                  </div>
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${Math.max(0, Math.min(100, batch.progress_percent))}%` }}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-6">
                    <div className="rounded-lg bg-muted/50 px-3 py-2">
                      <div className="text-xs text-muted-foreground">Завершено</div>
                      <div className="font-semibold text-foreground">{batch.completed_count}</div>
                    </div>
                    <div className="rounded-lg bg-muted/50 px-3 py-2">
                      <div className="text-xs text-muted-foreground">В очереди</div>
                      <div className="font-semibold text-foreground">{batch.pending_count}</div>
                    </div>
                    <div className="rounded-lg bg-muted/50 px-3 py-2">
                      <div className="text-xs text-muted-foreground">В работе</div>
                      <div className="font-semibold text-foreground">{batch.processing_count}</div>
                    </div>
                    <div className="rounded-lg bg-muted/50 px-3 py-2">
                      <div className="text-xs text-muted-foreground">Пауза</div>
                      <div className="font-semibold text-foreground">{batch.paused_count}</div>
                    </div>
                    <div className="rounded-lg bg-muted/50 px-3 py-2">
                      <div className="text-xs text-muted-foreground">CAPTCHA</div>
                      <div className="font-semibold text-foreground">{batch.captcha_count}</div>
                    </div>
                    <div className="rounded-lg bg-muted/50 px-3 py-2">
                      <div className="text-xs text-muted-foreground">Ошибки</div>
                      <div className="font-semibold text-foreground">{batch.error_count}</div>
                    </div>
                  </div>
                  <div className="rounded-lg border border-dashed border-border px-3 py-2 text-sm text-muted-foreground">
                    {batch.last_error_short || 'Последняя ошибка не зафиксирована. Если запуск встал, откройте задачи ниже для точечной диагностики.'}
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
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
                <option value="paused">Пауза (ошибка в сети)</option>
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
          <p className="text-xs text-muted-foreground">
            Показано: {tasks.length} из {tasksTotal || tasks.length}
            {tasksTotal > TASKS_FETCH_LIMIT ? ` (лимит экрана ${TASKS_FETCH_LIMIT})` : ''}
          </p>
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
                        {task.batch_id ? (
                          <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                            <div className="font-mono break-all">batch: {task.batch_id}</div>
                            {typeof task.batch_seq === 'number' ? (
                              <div>seq: {task.batch_seq}</div>
                            ) : null}
                          </div>
                        ) : null}
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
                        {task.status === 'captcha' && task.captcha_url && (
                          <div className="mt-2 flex items-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-7 border-orange-200 bg-orange-50 px-2 text-xs text-orange-700 hover:bg-orange-100"
                              onClick={() => handleOpenCaptcha(task)}
                            >
                              <ExternalLink className="mr-1 h-3 w-3" />
                              Открыть CAPTCHA
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6"
                              onClick={() => {
                                navigator.clipboard.writeText(task.captcha_url || '');
                                toast({ title: "CAPTCHA URL copied", description: task.captcha_url, duration: 2500 });
                              }}
                              title="Copy CAPTCHA URL"
                            >
                              <Copy className="h-3 w-3" />
                            </Button>
                          </div>
                        )}
                        {task.status === 'captcha' && (
                          <div className="mt-1 text-xs text-orange-700 space-y-1">
                            {task.captcha_session_id ? (
                              <div className="break-all">session: {task.captcha_session_id}</div>
                            ) : (
                              <div>session: не создана</div>
                            )}
                            <div>resume_requested: {task.resume_requested ? 'yes' : 'no'}</div>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {new Date(task.created_at).toLocaleString('ru-RU')}
                        {task.retry_after && (
                          <div className="mt-1 text-xs text-amber-700">
                            retry_after: {new Date(task.retry_after).toLocaleString('ru-RU')}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm max-w-md" title={task.error_message}>
                        {task.short_error_message ? (
                          <div className="space-y-1">
                            <div className="font-medium text-foreground">{task.short_error_message}</div>
                            {task.short_error_code ? (
                              <div className="text-xs uppercase tracking-wide text-muted-foreground">{task.short_error_code}</div>
                            ) : null}
                          </div>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <div className="flex gap-2">
                          {((task.can_restart_task ?? (task.status === 'error' || task.status === 'captcha' || task.status === 'paused')) ||
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
                          {(task.can_open_captcha ?? task.status === 'captcha') && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleResumeCaptcha(task.id)}
                              className="text-orange-600 hover:text-orange-700"
                              title="Продолжить после капчи"
                            >
                              <Loader2 className="w-4 h-4" />
                            </Button>
                          )}
                          {(task.can_resume_batch ?? ((task.status === 'paused' || task.status === 'error') && !!task.batch_id)) && task.batch_id && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleResumeNetworkBatch(task.batch_id)}
                              className="text-amber-700 hover:text-amber-800"
                              title="Возобновить сеть с места сбоя"
                            >
                              <Play className="w-4 h-4" />
                            </Button>
                          )}
                          {task.status === 'captcha' && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleExpireCaptcha(task.id)}
                              className="text-red-600 hover:text-red-700"
                              title="Сбросить CAPTCHA-сессию"
                            >
                              <CircleSlash className="w-4 h-4" />
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
