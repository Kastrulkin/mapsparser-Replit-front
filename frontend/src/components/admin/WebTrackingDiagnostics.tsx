import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Database, Globe2, RefreshCw } from 'lucide-react';
import { Button } from '../ui/button';
import { newAuth } from '../../lib/auth_new';
import { DashboardCompactMetricsRow, DashboardEmptyState } from '../dashboard/DashboardPrimitives';

type TrackerDiagnostic = {
  public_tracker_id: string;
  business_id: string;
  business_name: string;
  allowed_domains: string[];
  enabled: boolean;
  tracking_enabled: boolean;
  first_event_at?: string | null;
  last_event_at?: string | null;
  last_tracker_version?: string | null;
  last_schema_version?: number | null;
  last_error_code?: string | null;
  last_error_at?: string | null;
  events_1h: number;
  events_24h: number;
};

type MaintenanceRun = {
  started_at: string;
  finished_at?: string | null;
  dry_run: boolean;
  status: string;
  aggregate_date?: string | null;
  metrics_rows: number;
  raw_events: number;
  aggregate_events: number;
  eligible_events: number;
  eligible_metrics: number;
  deleted_events: number;
  deleted_metrics: number;
  deleted_sessions: number;
  deleted_visitors: number;
  error_code?: string | null;
};

type WebTrackingHealth = {
  success: boolean;
  trackers: {
    trackers: number;
    active_trackers: number;
    active_last_24h: number;
    never_seen: number;
  };
  events: {
    events_1h: number;
    events_24h: number;
    trackers_24h: number;
    latest_ingested_at?: string | null;
  };
  storage: {
    events_total_bytes: number;
    events_table_bytes: number;
    events_indexes_bytes: number;
    metrics_total_bytes: number;
  };
  versions: Array<{ tracker_version: string; schema_version: number; events: number }>;
  tracker_diagnostics: TrackerDiagnostic[];
  maintenance: MaintenanceRun[];
  ingestion?: {
    available: boolean;
    window_minutes: number;
    requests: number;
    events_received: number;
    accepted: number;
    duplicates: number;
    rejected_requests: number;
    responses_2xx: number;
    responses_4xx: number;
    responses_5xx: number;
    p50_ms?: number | null;
    p95_ms?: number | null;
    p99_ms?: number | null;
  };
};

const numberValue = (value: number | undefined) => Number(value || 0);

const formatBytes = (value: number | undefined) => {
  const bytes = numberValue(value);
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} ГБ`;
};

const formatDateTime = (value?: string | null) => {
  if (!value) return 'нет данных';
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
};

const formatLatency = (value?: number | null) => {
  if (value == null) return '—';
  return value > 2500 ? '>2500 мс' : `${numberValue(value)} мс`;
};

export function WebTrackingDiagnostics() {
  const [health, setHealth] = useState<WebTrackingHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadHealth = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await newAuth.makeRequest('/admin/web-tracking/health');
      if (!response?.success) throw new Error(response?.error || 'Диагностика недоступна');
      setHealth(response);
    } catch (loadError: unknown) {
      setError(loadError instanceof Error ? loadError.message : 'Не удалось загрузить диагностику');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHealth();
  }, [loadHealth]);

  const failedRuns = useMemo(
    () => (health?.maintenance || []).filter((run) => run.status === 'failed').length,
    [health],
  );
  const trackersWithErrors = useMemo(
    () => (health?.tracker_diagnostics || []).filter((tracker) => tracker.last_error_code).length,
    [health],
  );
  const ingestionAttention = Boolean(
    health?.ingestion?.available
      && (numberValue(health.ingestion.responses_5xx) > 0 || numberValue(health.ingestion.p95_ms || 0) > 1000),
  );

  if (loading && !health) {
    return (
      <div className="flex min-h-56 items-center justify-center rounded-3xl bg-white shadow-sm ring-1 ring-black/5">
        <RefreshCw className="h-5 w-5 animate-spin text-slate-500" />
        <span className="ml-3 text-sm font-medium text-slate-600">Собираем безопасную диагностику…</span>
      </div>
    );
  }

  if (error && !health) {
    return (
      <DashboardEmptyState
        title="Диагностика web-tracking не загрузилась"
        description={error}
        action={<Button type="button" onClick={loadHealth} className="min-h-10 active:scale-[0.96] transition-transform">Повторить</Button>}
      />
    );
  }

  if (!health) return null;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-balance text-lg font-semibold text-slate-950">Приём событий и рост данных</h3>
          <p className="mt-1 max-w-3xl text-pretty text-sm leading-6 text-slate-600">
            Здесь видны только технические статусы и коды ошибок. Содержимое страниц и форм не показывается.
          </p>
        </div>
        <Button type="button" variant="outline" onClick={loadHealth} disabled={loading} className="min-h-10 active:scale-[0.96] transition-transform">
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Обновить
        </Button>
      </div>

      <DashboardCompactMetricsRow items={[
        { label: 'Активные tracker’ы', value: <span className="tabular-nums">{numberValue(health.trackers.active_trackers)}</span>, hint: `${numberValue(health.trackers.trackers)} всего`, tone: 'positive' },
        { label: 'События за час', value: <span className="tabular-nums">{numberValue(health.events.events_1h)}</span>, hint: `${numberValue(health.events.events_24h)} за 24 часа` },
        { label: 'Без первого события', value: <span className="tabular-nums">{numberValue(health.trackers.never_seen)}</span>, hint: 'Проверить установку', tone: numberValue(health.trackers.never_seen) ? 'warning' : 'default' },
        { label: 'Хранилище', value: <span className="tabular-nums">{formatBytes(health.storage.events_total_bytes + health.storage.metrics_total_bytes)}</span>, hint: `raw ${formatBytes(health.storage.events_total_bytes)} · aggregate ${formatBytes(health.storage.metrics_total_bytes)}` },
      ]} />

      {health.ingestion?.available ? (
        <DashboardCompactMetricsRow items={[
          { label: 'Запросы ingestion', value: <span className="tabular-nums">{numberValue(health.ingestion.requests)}</span>, hint: `за ${numberValue(health.ingestion.window_minutes)} минут` },
          { label: 'Принято событий', value: <span className="tabular-nums">{numberValue(health.ingestion.accepted)}</span>, hint: `${numberValue(health.ingestion.duplicates)} дубликатов`, tone: 'positive' },
          { label: 'Отклонено запросов', value: <span className="tabular-nums">{numberValue(health.ingestion.rejected_requests)}</span>, hint: `${numberValue(health.ingestion.responses_4xx)} ответов 4xx · ${numberValue(health.ingestion.responses_5xx)} ответов 5xx`, tone: numberValue(health.ingestion.responses_5xx) ? 'warning' : 'default' },
          { label: 'Latency p95', value: <span className="tabular-nums">{formatLatency(health.ingestion.p95_ms)}</span>, hint: `p50 ${formatLatency(health.ingestion.p50_ms)} · p99 ${formatLatency(health.ingestion.p99_ms)}`, tone: numberValue(health.ingestion.p95_ms || 0) > 1000 ? 'warning' : 'default' },
        ]} />
      ) : (
        <div className="flex items-start gap-3 rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-950 shadow-[0_0_0_1px_rgba(217,119,6,0.16),0_1px_2px_-1px_rgba(217,119,6,0.12)]">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          <p className="text-pretty leading-6">Shared ingestion-метрики недоступны. Перед продолжением rollout проверьте Redis и переменную <code>WEB_TRACKING_METRICS_REDIS_URL</code>.</p>
        </div>
      )}

      {(trackersWithErrors > 0 || failedRuns > 0 || ingestionAttention) ? (
        <div className="flex items-start gap-3 rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-950 shadow-[0_0_0_1px_rgba(217,119,6,0.16),0_1px_2px_-1px_rgba(217,119,6,0.12)]">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          <p className="text-pretty leading-6">
            Требуют проверки: <strong className="tabular-nums">{trackersWithErrors}</strong> tracker’ов с кодом ошибки, <strong className="tabular-nums">{failedRuns}</strong> неудачных maintenance-запусков и <strong>{ingestionAttention ? 'ingestion выше порога' : 'ingestion в норме'}</strong>.
          </p>
        </div>
      ) : (
        <div className="flex items-center gap-3 rounded-2xl bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-900 shadow-[0_0_0_1px_rgba(5,150,105,0.14),0_1px_2px_-1px_rgba(5,150,105,0.1)]">
          <CheckCircle2 className="h-5 w-5" />
          По последним кодам ошибок и maintenance-запускам вмешательство не требуется.
        </div>
      )}

      <div className="overflow-hidden rounded-3xl bg-white shadow-[0_0_0_1px_rgba(0,0,0,0.06),0_1px_2px_-1px_rgba(0,0,0,0.06),0_2px_4px_rgba(0,0,0,0.04)]">
        <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
          <Globe2 className="h-5 w-5 text-slate-500" />
          <div>
            <h4 className="text-balance font-semibold text-slate-950">Tracker’ы бизнесов</h4>
            <p className="text-pretty text-sm text-slate-500">Домены, версии, поток событий и последний безопасный код ошибки.</p>
          </div>
        </div>
        {health.tracker_diagnostics.length === 0 ? (
          <div className="p-5">
            <DashboardEmptyState title="Tracker’ы ещё не созданы" description="После включения пилота здесь появятся бизнесы и статус подключения." />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[1120px]">
              <div className="grid grid-cols-[minmax(220px,1.2fr)_minmax(220px,1fr)_150px_130px_160px_minmax(170px,0.8fr)] gap-3 border-b border-slate-100 bg-slate-50 px-5 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                <div>Бизнес / tracker</div><div>Домены</div><div>События</div><div>Версия</div><div>Последнее</div><div>Что проверить</div>
              </div>
              <div className="divide-y divide-slate-100">
                {health.tracker_diagnostics.map((tracker) => (
                  <div key={tracker.public_tracker_id} className="grid grid-cols-[minmax(220px,1.2fr)_minmax(220px,1fr)_150px_130px_160px_minmax(170px,0.8fr)] gap-3 px-5 py-4 text-sm">
                    <div className="min-w-0"><div className="truncate font-semibold text-slate-950">{tracker.business_name}</div><div className="mt-1 truncate font-mono text-xs text-slate-400">{tracker.public_tracker_id}</div></div>
                    <div className="text-pretty text-slate-600">{tracker.allowed_domains.join(', ') || 'не настроены'}</div>
                    <div className="tabular-nums text-slate-700"><strong>{numberValue(tracker.events_1h)}</strong> / час<div className="text-xs text-slate-500">{numberValue(tracker.events_24h)} / сутки</div></div>
                    <div className="tabular-nums text-slate-700">{tracker.last_tracker_version || '—'}<div className="text-xs text-slate-500">schema {tracker.last_schema_version || '—'}</div></div>
                    <div className="tabular-nums text-slate-600">{formatDateTime(tracker.last_event_at)}<div className="text-xs text-slate-400">первое: {formatDateTime(tracker.first_event_at)}</div></div>
                    <div>{tracker.last_error_code ? <span className="inline-flex rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800 ring-1 ring-amber-200">{tracker.last_error_code}</span> : <span className="text-emerald-700">Ошибок нет</span>}<div className="mt-1 text-xs tabular-nums text-slate-400">{tracker.last_error_code ? formatDateTime(tracker.last_error_at) : ''}</div></div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="overflow-hidden rounded-3xl bg-white shadow-[0_0_0_1px_rgba(0,0,0,0.06),0_1px_2px_-1px_rgba(0,0,0,0.06),0_2px_4px_rgba(0,0,0,0.04)]">
        <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4"><Database className="h-5 w-5 text-slate-500" /><div><h4 className="text-balance font-semibold text-slate-950">Агрегация и retention</h4><p className="text-pretty text-sm text-slate-500">Контрольная сумма, dry-run и ограниченные удаления.</p></div></div>
        <div className="divide-y divide-slate-100">
          {health.maintenance.slice(0, 8).map((run) => (
            <div key={`${run.started_at}-${run.aggregate_date || ''}`} className="grid gap-3 px-5 py-4 text-sm md:grid-cols-[170px_130px_minmax(220px,1fr)_minmax(190px,0.8fr)] md:items-center">
              <div className="tabular-nums text-slate-600">{formatDateTime(run.started_at)}<div className="text-xs text-slate-400">{run.aggregate_date || 'дата нет'}</div></div>
              <div><span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${run.status === 'completed' ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-rose-50 text-rose-700 ring-rose-200'}`}>{run.status === 'completed' ? (run.dry_run ? 'Dry-run' : 'Выполнено') : 'Ошибка'}</span></div>
              <div className="tabular-nums text-slate-700">raw / aggregate: <strong>{numberValue(run.raw_events)} / {numberValue(run.aggregate_events)}</strong><div className="text-xs text-slate-500">Строк агрегатов: {numberValue(run.metrics_rows)}</div></div>
              <div className="tabular-nums text-slate-600">Удалено: {numberValue(run.deleted_events)} events<div className="text-xs text-slate-500">{numberValue(run.deleted_sessions)} sessions · {numberValue(run.deleted_visitors)} visitors</div>{run.error_code ? <div className="mt-1 text-xs font-semibold text-rose-700">{run.error_code}</div> : null}</div>
            </div>
          ))}
          {health.maintenance.length === 0 ? <div className="px-5 py-8 text-center text-sm text-slate-500">Maintenance ещё не запускался. Первый запуск должен быть dry-run.</div> : null}
        </div>
      </div>
    </div>
  );
}
