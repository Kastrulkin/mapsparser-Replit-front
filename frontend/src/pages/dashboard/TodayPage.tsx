import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { ArrowRight, Bot, CheckCircle2, Clock3, Radio, RefreshCw, TriangleAlert } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { DashboardEmptyState, DashboardPageHeader, DashboardSection } from '@/components/dashboard/DashboardPrimitives';
import { newAuth } from '@/lib/auth_new';
import { cn } from '@/lib/utils';
import type { ControlScope } from '@/components/DashboardLayout';

type DashboardContext = { currentBusinessId?: string | null; controlScope?: ControlScope | null; onControlScopeChange?: (scope: ControlScope) => void; onBusinessChange?: (businessId: string) => void };

type Mission = { id?: string; title: string; reason: string; expected_outcome: string; cta_label: string; screen?: string; cta_url?: string; target_scope?: { kind?: string; id?: string } };
type TodayItem = { id: string; title: string; description?: string; stage?: string; source?: string; occurred_at?: string; progress?: number | null; screen?: string; business_id?: string; business_name?: string };
type ProblemLocation = { business_id: string; business_name: string; problem?: string; data_health_status?: string; focus_action?: Mission | null };
type TodayOverview = {
  focus_action?: Mission | null;
  data_health?: { status?: string; source?: string; source_label?: string; source_updated_at?: string | null; updated_at?: string | null; last_updated_at?: string | null; stale?: boolean; is_stale?: boolean; missing?: string[] } | null;
  active_work?: TodayItem[];
  changes_24h?: TodayItem[];
  community_pulse?: TodayItem[];
  completed_results?: TodayItem[];
  network_summary?: { locations_count?: number; problem_locations_count?: number; healthy_locations_count?: number; finance?: { missing?: number; stale?: number; due?: number; fresh?: number } } | null;
  problem_locations?: ProblemLocation[];
  data_rhythm?: { status?: string; coverage?: number; completed_periods_8w?: number; next_due_at?: string | null } | null;
  analytics_modules?: Array<{ key?: string; label?: string; status?: string; next_unlock?: string | null }>;
};

const screenRoute = (screen?: string) => ({
  cards: '/dashboard/card', reviews: '/dashboard/card?tab=reviews', content: '/dashboard/content', services: '/dashboard/card?tab=services', finance: '/dashboard/finance', partnerships: '/dashboard/partnerships', agents: '/dashboard/agents', settings: '/dashboard/settings', progress: '/dashboard/progress', operator: '/dashboard/operator',
}[screen || ''] || '/dashboard/progress');

const missionRoute = (mission?: Mission | null) => {
  if (mission?.screen) return screenRoute(mission.screen);
  if (mission?.cta_url?.startsWith('/dashboard/')) return mission.cta_url;
  return '/dashboard/progress';
};

const missionCopy = (mission?: Mission | null) => {
  if (!mission) return null;
  if (mission.title === 'Обновите финансовые данные') {
    return {
      ...mission,
      reason: 'Финансовая сводка ещё не загружена.',
      expected_outcome: 'После загрузки здесь появятся выручка, расходы, средний чек и загрузка за выбранный период.',
    };
  }
  return mission;
};

const analyticsLabel = (key?: string, fallback?: string) => {
  if (key === 'trend') return 'Сравнение показателей по неделям';
  return fallback || 'Аналитика';
};

const analyticsStatus = (status?: string) => {
  if (status === 'ready') return 'можно смотреть';
  if (status === 'available') return 'обновите сводку';
  return 'загрузите сводку';
};

const dataSourceLabel = (source?: string) => {
  if (!source || source === 'unknown') return 'не указан';
  return source;
};

const resultSourceLabel = (source?: string) => {
  if (source === 'Прогресс LocalOS') return 'история выполненных задач';
  return source;
};

const formatDate = (value?: string | null) => {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(date);
};

export const TodayPage = () => {
  const navigate = useNavigate();
  const { currentBusinessId, controlScope, onControlScopeChange, onBusinessChange } = useOutletContext<DashboardContext>();
  const [overview, setOverview] = useState<TodayOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const requestSequence = useRef(0);

  const load = () => {
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;
    if (!currentBusinessId) {
      setOverview(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(false);
    const params = new URLSearchParams({ scope_type: controlScope?.kind || 'business', scope_id: controlScope?.id || currentBusinessId });
    let request: Promise<TodayOverview>;
    try {
      request = newAuth.makeRequest(`/operator/today?${params.toString()}`, { method: 'GET' });
    } catch {
      if (requestSequence.current === requestId) {
        setError(true);
        setLoading(false);
      }
      return;
    }
    void request
      .then((data: TodayOverview) => {
        if (requestSequence.current === requestId) setOverview(data);
      })
      .catch(() => {
        if (requestSequence.current === requestId) setError(true);
      })
      .finally(() => {
        if (requestSequence.current === requestId) setLoading(false);
      });
  };

  useEffect(() => { load(); }, [currentBusinessId, controlScope?.id, controlScope?.kind]);

  const openItem = (itemMission?: Mission | null, businessId?: string, businessName?: string) => {
    if (businessId && controlScope?.kind === 'network') {
      onBusinessChange?.(businessId);
      onControlScopeChange?.({ kind: 'business', id: businessId, name: businessName || 'Точка сети' });
    }
    navigate(missionRoute(itemMission));
  };

  const openMission = () => {
    const target = mission?.target_scope;
    if (target?.kind === 'business' && target.id) {
      onBusinessChange?.(target.id);
      onControlScopeChange?.({ kind: 'business', id: target.id, name: 'Точка сети' });
    }
    navigate(missionRoute(mission));
  };

  const mission = missionCopy(overview?.focus_action);
  const activeWork = useMemo(() => (overview?.active_work || []).slice(0, 3), [overview?.active_work]);
  const changes = overview?.changes_24h?.slice(0, 3) || [];
  const completedResults = overview?.completed_results?.slice(0, 3) || [];
  const communityPulse = overview?.community_pulse?.slice(0, 2) || [];
  const networkSummary = overview?.network_summary;
  const problemLocations = overview?.problem_locations?.slice(0, 5) || [];
  const dataRhythm = overview?.data_rhythm;
  const analyticsModules = overview?.analytics_modules || [];
  const dataHealth = overview?.data_health;
  const dataNeedsAttention = Boolean(['missing', 'stale', 'due'].includes(dataHealth?.status || '') || dataHealth?.stale || dataHealth?.is_stale || dataHealth?.missing?.length);

  if (!currentBusinessId) return <DashboardEmptyState title="Выберите бизнес" description="После выбора здесь появятся новые события, задачи LocalOS и действие, которое требует вашего решения." />;

  if (loading && !overview) {
    return <div className="space-y-6" aria-busy="true" data-tour-target="today-overview"><DashboardPageHeader eyebrow="LocalOS" title="Сегодня" description="Загружаем новые события и текущие задачи." /><div className="h-44 animate-pulse rounded-3xl bg-slate-100" /><div className="h-72 animate-pulse rounded-3xl bg-slate-100" /></div>;
  }

  if (error && !overview) {
    return <div className="space-y-6" data-tour-target="today-overview"><DashboardPageHeader eyebrow="LocalOS" title="Сегодня" description="Не удалось загрузить события и задачи." /><DashboardEmptyState title="Страница временно недоступна" description="Попробуйте ещё раз. Данные бизнеса не изменились." action={<Button type="button" onClick={load} className="min-h-11 gap-2 transition-transform active:scale-[0.96]"><RefreshCw className="h-4 w-4" />Повторить</Button>} /></div>;
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-10" data-tour-target="today-overview">
      <DashboardPageHeader eyebrow={controlScope?.kind === 'network' ? 'LocalOS · сеть' : 'LocalOS'} title="Сегодня" description="Новые события, задачи LocalOS и действие, которое сейчас важнее всего." icon={Clock3} actions={<Button type="button" variant="outline" onClick={load} disabled={loading} className="min-h-11 gap-2 transition-transform active:scale-[0.96]"><RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />Обновить</Button>} />

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(260px,0.7fr)] lg:items-center">
          <div className="min-w-0">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-orange-700">Что сделать сейчас</div>
            <h2 className="mt-2 text-balance text-2xl font-semibold text-slate-950">{mission?.title || 'Откройте список задач'}</h2>
            <p className="mt-2 max-w-3xl text-pretty text-sm leading-6 text-slate-600">{mission?.reason || 'Срочных действий сейчас нет. В разделе «Прогресс» можно проверить выполненные и незавершённые задачи.'}</p>
            {mission ? <div className="mt-3 rounded-2xl bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700"><strong>После этого:</strong> {mission.expected_outcome}</div> : null}
          </div>
          <Button type="button" onClick={openMission} className="min-h-11 w-full gap-2 transition-transform active:scale-[0.96] lg:w-auto lg:justify-self-end">{mission?.cta_label || 'Открыть прогресс'}<ArrowRight className="h-4 w-4" /></Button>
        </div>
      </section>

      {controlScope?.kind === 'network' && networkSummary ? (
        <DashboardSection title="Состояние филиалов" description="Сколько точек работает без замечаний и где нужно ваше решение.">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl bg-slate-50 px-4 py-3"><strong className="block text-2xl tabular-nums text-slate-950">{networkSummary.locations_count || 0}</strong><span className="text-sm text-slate-600">точек в сети</span></div>
            <div className="rounded-2xl bg-emerald-50 px-4 py-3"><strong className="block text-2xl tabular-nums text-emerald-800">{networkSummary.healthy_locations_count || 0}</strong><span className="text-sm text-emerald-900">в порядке</span></div>
            <div className="rounded-2xl bg-amber-50 px-4 py-3"><strong className="block text-2xl tabular-nums text-amber-800">{networkSummary.problem_locations_count || 0}</strong><span className="text-sm text-amber-900">требуют внимания</span></div>
          </div>
          {problemLocations.length ? <div className="mt-4 divide-y divide-slate-100">{problemLocations.map((location) => (
            <button key={location.business_id} type="button" onClick={() => openItem(location.focus_action, location.business_id, location.business_name)} className="flex min-h-16 w-full items-center gap-3 py-3 text-left transition-transform active:scale-[0.96]">
              <span className="min-w-0 flex-1"><strong className="block text-sm text-slate-950">{location.business_name}</strong><span className="mt-1 block text-pretty text-sm text-slate-600">{location.problem || 'Точка требует внимания.'}</span></span>
              <ArrowRight className="h-4 w-4 shrink-0 text-slate-400" />
            </button>
          ))}</div> : <p className="mt-4 text-sm text-emerald-800">Все активные точки сети сейчас в порядке.</p>}
        </DashboardSection>
      ) : null}

      {dataRhythm || analyticsModules.length ? (
        <DashboardSection title="Данные за последние 8 недель" description="Чтобы видеть выручку, средний чек, допродажи и загрузку, регулярно загружайте финансовую сводку. Подключать CRM не обязательно.">
          {dataRhythm ? <div className="rounded-2xl bg-slate-50 px-4 py-3"><div className="flex items-center justify-between gap-3 text-sm"><span className="text-slate-600">Заполнено за 8 недель</span><strong className="tabular-nums text-slate-950">{dataRhythm.coverage || 0}%</strong></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-orange-500" style={{ width: `${Math.min(100, Math.max(0, dataRhythm.coverage || 0))}%` }} /></div><p className="mt-2 text-sm text-slate-600">Сводки загружены за <span className="tabular-nums">{dataRhythm.completed_periods_8w || 0}</span> из 8 недель{formatDate(dataRhythm.next_due_at) ? ` · следующую сводку добавьте ${formatDate(dataRhythm.next_due_at)}` : ''}</p></div> : null}
          {analyticsModules.length ? <div className="mt-3 flex flex-wrap gap-2">{analyticsModules.map((module) => <span key={module.key || module.label} className={cn('rounded-full px-3 py-1.5 text-sm', module.status === 'ready' ? 'bg-emerald-50 text-emerald-800' : module.status === 'available' ? 'bg-amber-50 text-amber-900' : 'bg-slate-100 text-slate-600')}>{analyticsLabel(module.key, module.label)}: {analyticsStatus(module.status)}</span>)}</div> : null}
        </DashboardSection>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <DashboardSection title="Что изменилось" description="Отзывы, продажи и другие события бизнеса за последние 24 часа.">
          {changes.length ? <div className="divide-y divide-slate-100">{changes.map((item) => <div key={item.id} className="flex gap-3 py-3 first:pt-0 last:pb-0"><CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" /><div className="min-w-0"><div className="font-medium text-slate-950">{item.title}</div><p className="mt-1 text-pretty text-sm leading-5 text-slate-600">{item.description}</p>{formatDate(item.occurred_at) ? <div className="mt-1 text-xs tabular-nums text-slate-400">{formatDate(item.occurred_at)}</div> : null}</div></div>)}</div> : <p className="text-sm leading-6 text-slate-600">За последние 24 часа новых отзывов, продаж и других подтверждённых событий не найдено.</p>}
        </DashboardSection>

        <DashboardSection title="Что LocalOS делает сейчас" description="Текущие задачи LocalOS. В режиме сети рядом с задачей указана точка.">
          {activeWork.length ? <div className="space-y-3">{activeWork.map((item) => <button key={item.id} type="button" onClick={() => openItem({ title: item.title, reason: '', expected_outcome: '', cta_label: '', screen: item.screen }, item.business_id, item.business_name)} className="w-full rounded-2xl bg-slate-50 px-4 py-3 text-left transition-transform active:scale-[0.96]"><div className="flex items-start gap-2"><Bot className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" /><div className="min-w-0 flex-1"><div className="font-medium text-slate-950">{item.title}</div><p className="mt-1 text-pretty text-sm leading-5 text-slate-600">{[item.business_name, item.stage || item.description].filter(Boolean).join(' · ')}</p></div>{item.progress == null ? null : <span className="text-sm tabular-nums text-slate-500">{item.progress}%</span>}</div></button>)}</div> : <p className="text-sm leading-6 text-slate-600">Сейчас у LocalOS нет активных задач.</p>}
        </DashboardSection>
      </div>

      {completedResults.length ? <DashboardSection title="Готово в LocalOS" description="Черновики, планы и отчёты, которые уже можно открыть и проверить. Ничего не опубликовано и не отправлено автоматически."><div className="divide-y divide-slate-100">{completedResults.map((item) => <div key={item.id} className="flex gap-3 py-3 first:pt-0 last:pb-0"><CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" /><div className="min-w-0"><div className="font-medium text-slate-950">{item.title}</div>{item.description ? <p className="mt-1 text-pretty text-sm leading-5 text-slate-600">{item.description}</p> : null}{item.source ? <div className="mt-1 text-xs text-slate-500">Источник: {resultSourceLabel(item.source)}</div> : null}</div></div>)}</div></DashboardSection> : null}

      {communityPulse.length ? <DashboardSection title="Что обсуждают в ваших источниках" description="Сообщения из подключённых Telegram-каналов и других источников. LocalOS только показывает их здесь."><div className="space-y-3">{communityPulse.map((item) => <div key={item.id} className="flex gap-3 rounded-2xl bg-slate-50 px-4 py-3"><Radio className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" /><div className="min-w-0"><div className="font-medium text-slate-950">{item.title}</div>{item.description ? <p className="mt-1 text-pretty text-sm leading-5 text-slate-600">{item.description}</p> : null}{item.source ? <div className="mt-1 text-xs text-slate-500">Источник: {item.source}</div> : null}</div></div>)}</div></DashboardSection> : null}

      {dataHealth ? <div className={cn('flex items-start gap-3 rounded-2xl px-4 py-3 text-sm shadow-[0_0_0_1px_rgba(15,23,42,0.08)]', dataNeedsAttention ? 'bg-amber-50 text-amber-950' : 'bg-slate-50 text-slate-700')}><TriangleAlert className={cn('mt-0.5 h-5 w-5 shrink-0', dataNeedsAttention ? 'text-amber-700' : 'text-slate-500')} /><div><span className="font-semibold">Источник финансовых данных:</span> {dataSourceLabel(dataHealth.source_label || dataHealth.source)}{formatDate(dataHealth.source_updated_at || dataHealth.updated_at || dataHealth.last_updated_at) ? <span className="tabular-nums"> · обновлено {formatDate(dataHealth.source_updated_at || dataHealth.updated_at || dataHealth.last_updated_at)}</span> : null}{dataNeedsAttention && dataHealth.missing?.length ? <span> · нужно добавить: {dataHealth.missing.join(', ')}</span> : null}</div></div> : null}

      <DashboardSection title="Все задачи и результаты" description="Откройте полный список: выполненные шаги, найденные проблемы и действия, которые ещё нужно сделать.">
        <Button type="button" variant="outline" onClick={() => navigate('/dashboard/progress')} className="min-h-11 gap-2 transition-transform active:scale-[0.96]">Открыть прогресс<ArrowRight className="h-4 w-4" /></Button>
      </DashboardSection>
    </div>
  );
};
