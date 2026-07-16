import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  BookOpen,
  Check,
  Clock3,
  ExternalLink,
  Pause,
  Play,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';
import { newAuth } from '../lib/auth_new';

type ViewId = 'signals' | 'sources' | 'runs' | 'privacy';

interface KnowledgeSummary {
  sources_total?: number;
  sources_active?: number;
  sources_candidate?: number;
  documents_total?: number;
  assertions_total?: number;
  claims_active?: number;
  privacy_pending?: number;
  updated_at?: string;
}

interface KnowledgeOverview {
  enabled?: boolean;
  summary?: KnowledgeSummary;
}

interface KnowledgeSignal {
  assertion_id: string;
  concept_type: string;
  label: string;
  confidence?: number | string;
  evidence_id: string;
  excerpt?: string;
  observed_at?: string;
  permalink?: string;
  source_title?: string;
  source_role?: string;
  allowed_uses?: string[];
}

interface KnowledgeSource {
  id: string;
  title: string;
  source_role: string;
  visibility: string;
  status: string;
  documents_count?: number;
  canonical_url?: string;
  allowed_uses?: string[];
  last_collected_at?: string;
}

interface KnowledgeRun {
  id: string;
  run_type: string;
  status: string;
  source_title?: string;
  document_count?: number;
  processed_count?: number;
  failed_count?: number;
  input_tokens?: number;
  output_tokens?: number;
  created_at?: string;
}

interface PrivacyCandidate {
  review_id: string;
  title: string;
  statement_text: string;
  evidence_level: string;
  sample_businesses: number;
  limitations_json?: string[];
}

const viewOptions: Array<{ id: ViewId; label: string }> = [
  { id: 'signals', label: 'Сигналы' },
  { id: 'sources', label: 'Источники' },
  { id: 'runs', label: 'Обновления' },
  { id: 'privacy', label: 'Общие выводы' },
];

const signalFilters = [
  { value: '', label: 'Все' },
  { value: 'pain', label: 'Боли' },
  { value: 'practice', label: 'Практики' },
  { value: 'format', label: 'Контент' },
  { value: 'sales_angle', label: 'Продажи' },
  { value: 'service', label: 'Услуги' },
];

const useLabels: Record<string, string> = {
  market: 'Рынок',
  outreach: 'Аутрич',
  localos_content: 'Контент LocalOS',
  client_content: 'Контент клиента',
  industry_recommendations: 'Рекомендации',
  shared_learning: 'Общее обучение',
};

const roleLabels: Record<string, string> = {
  expert: 'Эксперт',
  salon: 'Салон',
  vendor: 'Сервис',
  community: 'Сообщество',
  service: 'Источник данных',
  competitor: 'Конкурент',
  unknown: 'Роль не проверена',
};

const statusLabels: Record<string, string> = {
  candidate: 'Нужно решение',
  active: 'Отслеживается',
  paused: 'На паузе',
  completed: 'Завершено',
  partial: 'Часть данных',
  failed: 'Ошибка',
  blocked: 'Остановлено правилами',
  running: 'Выполняется',
  queued: 'В очереди',
};

const formatNumber = (value?: number) => new Intl.NumberFormat('ru-RU').format(value || 0);

const formatDate = (value?: string) => {
  if (!value) return 'дата не указана';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'дата не указана';
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }).format(date);
};

const authGet = async (endpoint: string) => newAuth.makeRequest(endpoint);

export const KnowledgeMarketOverview: React.FC = () => {
  const [activeView, setActiveView] = useState<ViewId>('signals');
  const [overview, setOverview] = useState<KnowledgeOverview | null>(null);
  const [signals, setSignals] = useState<KnowledgeSignal[]>([]);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [runs, setRuns] = useState<KnowledgeRun[]>([]);
  const [privacy, setPrivacy] = useState<PrivacyCandidate[]>([]);
  const [signalFilter, setSignalFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [savingId, setSavingId] = useState('');

  const loadOverview = useCallback(async () => {
    const response = await authGet('/admin/knowledge/overview');
    setOverview(response.data || null);
  }, []);

  const loadActiveView = useCallback(async () => {
    if (activeView === 'signals') {
      const query = new URLSearchParams({ industry: 'beauty', limit: '80' });
      if (signalFilter) query.set('concept_type', signalFilter);
      const response = await authGet(`/admin/knowledge/signals?${query.toString()}`);
      setSignals(Array.isArray(response.items) ? response.items : []);
      return;
    }
    if (activeView === 'sources') {
      const response = await authGet('/admin/knowledge/sources');
      setSources(Array.isArray(response.items) ? response.items : []);
      return;
    }
    if (activeView === 'runs') {
      const response = await authGet('/admin/knowledge/runs?limit=80');
      setRuns(Array.isArray(response.items) ? response.items : []);
      return;
    }
    const response = await authGet('/admin/knowledge/privacy-candidates');
    setPrivacy(Array.isArray(response.items) ? response.items : []);
  }, [activeView, signalFilter]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      await Promise.all([loadOverview(), loadActiveView()]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить знания рынка');
    } finally {
      setLoading(false);
    }
  }, [loadActiveView, loadOverview]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const decideSource = async (source: KnowledgeSource, status: 'active' | 'paused') => {
    setSavingId(source.id);
    setError('');
    try {
      await newAuth.makeRequest(`/admin/knowledge/sources/${source.id}/decision`, {
        method: 'POST',
        body: JSON.stringify({ status, source_role: source.source_role }),
      });
      await Promise.all([loadOverview(), loadActiveView()]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить решение');
    } finally {
      setSavingId('');
    }
  };

  const updateSourceRole = (sourceId: string, sourceRole: string) => {
    setSources((current) => current.map((source) => (
      source.id === sourceId ? { ...source, source_role: sourceRole } : source
    )));
  };

  const decidePrivacy = async (candidate: PrivacyCandidate, decision: 'approved' | 'rejected') => {
    setSavingId(candidate.review_id);
    setError('');
    try {
      await newAuth.makeRequest(`/admin/knowledge/privacy-candidates/${candidate.review_id}/decision`, {
        method: 'POST',
        body: JSON.stringify({ decision }),
      });
      await Promise.all([loadOverview(), loadActiveView()]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить решение');
    } finally {
      setSavingId('');
    }
  };

  const summary = overview?.summary || {};

  return (
    <div className="min-h-[480px] bg-slate-50/60 p-4 sm:p-6">
      <div className="space-y-5">
        {!overview?.enabled && !loading ? (
          <div className="flex items-start gap-3 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-900 shadow-[inset_0_0_0_1px_rgba(217,119,6,0.18)]">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Слой знаний пока выключен</p>
              <p className="mt-1 text-amber-800">Можно проверить импорт и источники. Пользовательские подсказки появятся после включения флага.</p>
            </div>
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[
            { label: 'Источники', value: summary.sources_total, hint: `${formatNumber(summary.sources_active)} отслеживаются` },
            { label: 'Документы', value: summary.documents_total, hint: 'Сообщения, услуги и аудиты' },
            { label: 'Факты и сигналы', value: summary.assertions_total, hint: 'Со ссылкой на доказательство' },
            { label: 'Нужны решения', value: (summary.sources_candidate || 0) + (summary.privacy_pending || 0), hint: 'Источники и общие выводы' },
          ].map((metric) => (
            <div key={metric.label} className="rounded-lg bg-white px-4 py-4 shadow-[0_1px_2px_rgba(15,23,42,0.05),0_0_0_1px_rgba(148,163,184,0.18)]">
              <p className="text-xs font-semibold uppercase text-slate-500">{metric.label}</p>
              <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-950">{formatNumber(metric.value)}</p>
              <p className="mt-1 text-xs text-slate-500">{metric.hint}</p>
            </div>
          ))}
        </div>

        <div className="flex flex-col gap-3 border-b border-slate-200 pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-1 overflow-x-auto rounded-lg bg-slate-100 p-1">
            {viewOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => setActiveView(option.id)}
                className={`min-h-10 whitespace-nowrap rounded-md px-4 text-sm font-semibold transition-colors active:scale-[0.96] ${
                  activeView === option.id ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-600 hover:text-slate-950'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={loading}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md px-3 text-sm font-semibold text-slate-600 transition-colors hover:bg-white hover:text-slate-950 disabled:opacity-50 active:scale-[0.96]"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Обновить
          </button>
        </div>

        {error ? (
          <div className="flex items-center justify-between gap-3 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-800 shadow-[inset_0_0_0_1px_rgba(225,29,72,0.16)]">
            <span>{error}</span>
            <button type="button" onClick={() => void refresh()} className="min-h-10 shrink-0 rounded-md px-3 font-semibold hover:bg-rose-100">
              Повторить
            </button>
          </div>
        ) : null}

        {activeView === 'signals' ? (
          <section aria-labelledby="knowledge-signals-title">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h3 id="knowledge-signals-title" className="text-lg font-semibold text-slate-950">Что сейчас видно на рынке</h3>
                <p className="mt-1 text-sm text-slate-600">Только выводы, у которых сохранены источник, дата и разрешённое применение.</p>
              </div>
              <select
                value={signalFilter}
                onChange={(event) => setSignalFilter(event.target.value)}
                className="h-11 rounded-md bg-white px-3 text-sm font-medium text-slate-800 shadow-[0_0_0_1px_rgba(148,163,184,0.35)] outline-none focus:shadow-[0_0_0_3px_rgba(14,165,233,0.16)]"
                aria-label="Тип сигнала"
              >
                {signalFilters.map((filter) => <option key={filter.value} value={filter.value}>{filter.label}</option>)}
              </select>
            </div>
            <div className="divide-y divide-slate-200 rounded-lg bg-white shadow-[0_1px_3px_rgba(15,23,42,0.06),0_0_0_1px_rgba(148,163,184,0.18)]">
              {!loading && signals.length === 0 ? (
                <div className="px-5 py-12 text-center">
                  <BookOpen className="mx-auto h-7 w-7 text-slate-400" />
                  <p className="mt-3 font-semibold text-slate-800">Подтверждённых сигналов пока нет</p>
                  <p className="mt-1 text-sm text-slate-500">Сначала импортируйте корпус и подтвердите источники.</p>
                </div>
              ) : signals.map((signal) => (
                <article key={`${signal.assertion_id}:${signal.evidence_id}`} className="grid gap-3 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_220px] lg:items-start">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded bg-sky-50 px-2 py-1 text-xs font-semibold text-sky-700">{signal.label}</span>
                      <span className="text-xs text-slate-500">{roleLabels[signal.source_role || 'unknown'] || signal.source_role}</span>
                      <span className="text-xs tabular-nums text-slate-500">доверие {Math.round(Number(signal.confidence || 0) * 100)}%</span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-700 [text-wrap:pretty]">{signal.excerpt || 'Короткое доказательство не сохранено.'}</p>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {(signal.allowed_uses || []).map((use) => (
                        <span key={use} className="rounded bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-600">{useLabels[use] || use}</span>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center justify-between gap-3 lg:block lg:text-right">
                    <div>
                      <p className="text-sm font-medium text-slate-700">{signal.source_title || 'Источник'}</p>
                      <p className="mt-1 text-xs text-slate-500">{formatDate(signal.observed_at)}</p>
                    </div>
                    {signal.permalink ? (
                      <a href={signal.permalink} target="_blank" rel="noreferrer" className="mt-0 inline-flex min-h-10 items-center gap-2 rounded-md px-3 text-sm font-semibold text-sky-700 hover:bg-sky-50 lg:mt-2">
                        Источник <ExternalLink className="h-4 w-4" />
                      </a>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        {activeView === 'sources' ? (
          <section aria-labelledby="knowledge-sources-title">
            <h3 id="knowledge-sources-title" className="text-lg font-semibold text-slate-950">Какие источники можно использовать</h3>
            <p className="mt-1 text-sm text-slate-600">Новые Telegram-каналы не отслеживаются, пока администратор не проверит их роль и применение.</p>
            <div className="mt-4 divide-y divide-slate-200 rounded-lg bg-white shadow-[0_1px_3px_rgba(15,23,42,0.06),0_0_0_1px_rgba(148,163,184,0.18)]">
              {!loading && sources.length === 0 ? <div className="px-5 py-12 text-center text-sm text-slate-500">Источники ещё не импортированы.</div> : sources.map((source) => (
                <div key={source.id} className="grid gap-4 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_190px_180px] lg:items-center">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate font-semibold text-slate-900">{source.title}</p>
                      <span className={`rounded px-2 py-1 text-xs font-semibold ${source.status === 'active' ? 'bg-emerald-50 text-emerald-700' : source.status === 'candidate' ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>
                        {statusLabels[source.status] || source.status}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-slate-600">{roleLabels[source.source_role] || source.source_role} · {formatNumber(source.documents_count)} документов · {source.visibility === 'public' ? 'публичный' : 'только внутренний'}</p>
                  </div>
                  <div className="space-y-2 text-sm text-slate-600">
                    <label className="block text-xs font-semibold uppercase text-slate-500" htmlFor={`source-role-${source.id}`}>Роль источника</label>
                    <select
                      id={`source-role-${source.id}`}
                      value={source.source_role}
                      onChange={(event) => updateSourceRole(source.id, event.target.value)}
                      disabled={source.status === 'active'}
                      className="h-10 w-full rounded-md bg-white px-2 text-sm text-slate-800 shadow-[0_0_0_1px_rgba(148,163,184,0.35)] outline-none disabled:bg-slate-50"
                    >
                      {Object.entries(roleLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                    <p className="text-xs text-slate-500">Проверено: {formatDate(source.last_collected_at)}</p>
                  </div>
                  <div className="flex gap-2 lg:justify-end">
                    {source.status !== 'active' ? (
                      <button type="button" onClick={() => void decideSource(source, 'active')} disabled={savingId === source.id || source.source_role === 'unknown'} className="inline-flex min-h-10 items-center gap-2 rounded-md bg-slate-950 px-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.96]">
                        <Play className="h-4 w-4" /> Отслеживать
                      </button>
                    ) : (
                      <button type="button" onClick={() => void decideSource(source, 'paused')} disabled={savingId === source.id} className="inline-flex min-h-10 items-center gap-2 rounded-md bg-slate-100 px-3 text-sm font-semibold text-slate-700 hover:bg-slate-200 disabled:opacity-50 active:scale-[0.96]">
                        <Pause className="h-4 w-4" /> Пауза
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {activeView === 'runs' ? (
          <section aria-labelledby="knowledge-runs-title">
            <h3 id="knowledge-runs-title" className="text-lg font-semibold text-slate-950">Как обновляются знания</h3>
            <p className="mt-1 text-sm text-slate-600">Импорт, анализ и ошибки отдельных источников. Ошибка одного канала не останавливает остальные.</p>
            <div className="mt-4 divide-y divide-slate-200 rounded-lg bg-white shadow-[0_1px_3px_rgba(15,23,42,0.06),0_0_0_1px_rgba(148,163,184,0.18)]">
              {!loading && runs.length === 0 ? <div className="px-5 py-12 text-center text-sm text-slate-500">Запусков пока не было.</div> : runs.map((run) => (
                <div key={run.id} className="grid gap-3 px-4 py-4 sm:grid-cols-[minmax(0,1fr)_140px_180px] sm:items-center">
                  <div>
                    <p className="font-semibold text-slate-900">{run.source_title || run.run_type}</p>
                    <p className="mt-1 text-sm text-slate-500">{formatDate(run.created_at)}</p>
                  </div>
                  <span className="inline-flex w-fit items-center gap-2 rounded bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                    {run.status === 'completed' ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Clock3 className="h-3.5 w-3.5" />}
                    {statusLabels[run.status] || run.status}
                  </span>
                  <div className="text-sm tabular-nums text-slate-600 sm:text-right">
                    {formatNumber(run.processed_count)} из {formatNumber(run.document_count)} · {formatNumber(run.failed_count)} ошибок
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {activeView === 'privacy' ? (
          <section aria-labelledby="knowledge-privacy-title">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-6 w-6 text-emerald-600" />
              <div>
                <h3 id="knowledge-privacy-title" className="text-lg font-semibold text-slate-950">Что можно превратить в общий вывод</h3>
                <p className="mt-1 text-sm text-slate-600">Здесь нет названий компаний, точных дат, исходных текстов и абсолютных показателей. Публикация требует отдельного флага и решения.</p>
              </div>
            </div>
            <div className="mt-4 divide-y divide-slate-200 rounded-lg bg-white shadow-[0_1px_3px_rgba(15,23,42,0.06),0_0_0_1px_rgba(148,163,184,0.18)]">
              {!loading && privacy.length === 0 ? <div className="px-5 py-12 text-center text-sm text-slate-500">Кандидатов на общее обучение пока нет.</div> : privacy.map((candidate) => (
                <div key={candidate.review_id} className="grid gap-4 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_220px] lg:items-center">
                  <div>
                    <p className="font-semibold text-slate-900">{candidate.title}</p>
                    <p className="mt-2 text-sm leading-6 text-slate-700">{candidate.statement_text}</p>
                    <p className="mt-2 text-xs text-slate-500">{formatNumber(candidate.sample_businesses)} бизнесов · {candidate.evidence_level}</p>
                  </div>
                  <div className="flex gap-2 lg:justify-end">
                    <button type="button" onClick={() => void decidePrivacy(candidate, 'rejected')} disabled={savingId === candidate.review_id} className="min-h-10 rounded-md bg-slate-100 px-3 text-sm font-semibold text-slate-700 hover:bg-slate-200 disabled:opacity-50">Отклонить</button>
                    <button type="button" onClick={() => void decidePrivacy(candidate, 'approved')} disabled={savingId === candidate.review_id} className="min-h-10 rounded-md bg-emerald-600 px-3 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50">Разрешить</button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {loading && !overview ? (
          <div className="space-y-3" aria-label="Загрузка знаний рынка">
            {[0, 1, 2].map((item) => <div key={item} className="h-24 animate-pulse rounded-lg bg-slate-200/70" />)}
          </div>
        ) : null}
      </div>
    </div>
  );
};
