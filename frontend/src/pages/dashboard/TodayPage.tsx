import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { ArrowRight, Bot, CheckCircle2, Clock3, Radio, RefreshCw, TriangleAlert } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { DashboardEmptyState, DashboardPageHeader, DashboardSection } from '@/components/dashboard/DashboardPrimitives';
import { newAuth } from '@/lib/auth_new';
import { cn } from '@/lib/utils';

type DashboardContext = { currentBusinessId?: string | null };

type Mission = { id?: string; title: string; reason: string; expected_outcome: string; cta_label: string; screen?: string };
type TodayItem = { id: string; title: string; description?: string; stage?: string; source?: string; occurred_at?: string; progress?: number | null; screen?: string; business_name?: string };
type TodayOverview = {
  focus_action?: Mission | null;
  data_health?: { source?: string; source_label?: string; updated_at?: string | null; last_updated_at?: string | null; stale?: boolean; is_stale?: boolean; missing?: string[] } | null;
  active_work?: TodayItem[];
  changes_24h?: TodayItem[];
  community_pulse?: TodayItem[];
  completed_results?: TodayItem[];
};

const screenRoute = (screen?: string) => ({
  cards: '/dashboard/card', reviews: '/dashboard/card?tab=reviews', content: '/dashboard/content', services: '/dashboard/card?tab=services', finance: '/dashboard/finance', partnerships: '/dashboard/partnerships', agents: '/dashboard/agents', settings: '/dashboard/settings', progress: '/dashboard/progress', operator: '/dashboard/operator',
}[screen || ''] || '/dashboard/progress');

const formatDate = (value?: string | null) => {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(date);
};

export const TodayPage = () => {
  const navigate = useNavigate();
  const { currentBusinessId } = useOutletContext<DashboardContext>();
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
    const params = new URLSearchParams({ scope_type: 'business', scope_id: currentBusinessId });
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

  useEffect(() => { load(); }, [currentBusinessId]);

  const mission = overview?.focus_action || null;
  const activeWork = useMemo(() => (overview?.active_work || []).slice(0, 3), [overview?.active_work]);
  const changes = overview?.changes_24h?.slice(0, 3) || [];
  const completedResults = overview?.completed_results?.slice(0, 3) || [];
  const communityPulse = overview?.community_pulse?.slice(0, 2) || [];
  const dataHealth = overview?.data_health;
  const dataNeedsAttention = Boolean(dataHealth?.stale || dataHealth?.is_stale || dataHealth?.missing?.length);

  if (!currentBusinessId) return <DashboardEmptyState title="Выберите бизнес" description="После выбора здесь появятся изменения, текущая работа LocalOS и ближайший шаг." />;

  if (loading && !overview) {
    return <div className="space-y-6" aria-busy="true"><DashboardPageHeader eyebrow="LocalOS" title="Сегодня" description="Собираем актуальную картину по бизнесу." /><div className="h-44 animate-pulse rounded-3xl bg-slate-100" /><div className="h-72 animate-pulse rounded-3xl bg-slate-100" /></div>;
  }

  if (error && !overview) {
    return <div className="space-y-6"><DashboardPageHeader eyebrow="LocalOS" title="Сегодня" description="Не удалось получить рабочую сводку." /><DashboardEmptyState title="Сводка пока недоступна" description="Попробуйте обновить страницу: никакие действия и данные не были изменены." action={<Button type="button" onClick={load} className="min-h-11 gap-2 transition-transform active:scale-[0.96]"><RefreshCw className="h-4 w-4" />Обновить</Button>} /></div>;
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-10">
      <DashboardPageHeader eyebrow="LocalOS" title="Сегодня" description="Что изменилось, над чем идёт работа и один следующий шаг для выбранного бизнеса." icon={Clock3} actions={<Button type="button" variant="outline" onClick={load} disabled={loading} className="min-h-11 gap-2 transition-transform active:scale-[0.96]"><RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />Обновить</Button>} />

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(260px,0.7fr)] lg:items-center">
          <div className="min-w-0">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-orange-700">Следующий шаг</div>
            <h2 className="mt-2 text-balance text-2xl font-semibold text-slate-950">{mission?.title || 'Проверьте рабочую сводку'}</h2>
            <p className="mt-2 max-w-3xl text-pretty text-sm leading-6 text-slate-600">{mission?.reason || 'LocalOS пока не нашёл подтверждённого следующего действия. Откройте прогресс, чтобы проверить доступные данные.'}</p>
            {mission ? <div className="mt-3 rounded-2xl bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700"><strong>Результат:</strong> {mission.expected_outcome}</div> : null}
          </div>
          <Button type="button" onClick={() => navigate(screenRoute(mission?.screen))} className="min-h-11 w-full gap-2 transition-transform active:scale-[0.96] lg:w-auto lg:justify-self-end">{mission?.cta_label || 'Открыть прогресс'}<ArrowRight className="h-4 w-4" /></Button>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <DashboardSection title="Что изменилось" description="Новые события бизнеса за последние 24 часа — отдельно от работы LocalOS.">
          {changes.length ? <div className="divide-y divide-slate-100">{changes.map((item) => <div key={item.id} className="flex gap-3 py-3 first:pt-0 last:pb-0"><CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" /><div className="min-w-0"><div className="font-medium text-slate-950">{item.title}</div><p className="mt-1 text-pretty text-sm leading-5 text-slate-600">{item.description}</p>{formatDate(item.occurred_at) ? <div className="mt-1 text-xs tabular-nums text-slate-400">{formatDate(item.occurred_at)}</div> : null}</div></div>)}</div> : <p className="text-sm leading-6 text-slate-600">За последние 24 часа новых отзывов, продаж и других подтверждённых событий не найдено.</p>}
        </DashboardSection>

        <DashboardSection title="Что LocalOS делает" description="Текущие направления и состояния без предположений о внешних действиях.">
          {activeWork.length ? <div className="space-y-3">{activeWork.map((item) => <button key={item.id} type="button" onClick={() => navigate(screenRoute(item.screen))} className="w-full rounded-2xl bg-slate-50 px-4 py-3 text-left transition-transform active:scale-[0.96]"><div className="flex items-start gap-2"><Bot className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" /><div className="min-w-0 flex-1"><div className="font-medium text-slate-950">{item.title}</div><p className="mt-1 text-pretty text-sm leading-5 text-slate-600">{item.stage || item.description}</p></div>{item.progress == null ? null : <span className="text-sm tabular-nums text-slate-500">{item.progress}%</span>}</div></button>)}</div> : <p className="text-sm leading-6 text-slate-600">Сейчас нет активной работы, которую LocalOS выполняет в этом бизнесе.</p>}
        </DashboardSection>
      </div>

      {completedResults.length ? <DashboardSection title="Результаты LocalOS" description="Подготовленные или завершённые результаты; внешние публикации и отправки не подразумеваются."><div className="divide-y divide-slate-100">{completedResults.map((item) => <div key={item.id} className="flex gap-3 py-3 first:pt-0 last:pb-0"><CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" /><div className="min-w-0"><div className="font-medium text-slate-950">{item.title}</div>{item.description ? <p className="mt-1 text-pretty text-sm leading-5 text-slate-600">{item.description}</p> : null}{item.source ? <div className="mt-1 text-xs text-slate-500">Источник: {item.source}</div> : null}</div></div>)}</div></DashboardSection> : null}

      {communityPulse.length ? <DashboardSection title="Пульс сообщества" description="Наблюдения из подключённых источников; это не действие от имени бизнеса."><div className="space-y-3">{communityPulse.map((item) => <div key={item.id} className="flex gap-3 rounded-2xl bg-slate-50 px-4 py-3"><Radio className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" /><div className="min-w-0"><div className="font-medium text-slate-950">{item.title}</div>{item.description ? <p className="mt-1 text-pretty text-sm leading-5 text-slate-600">{item.description}</p> : null}{item.source ? <div className="mt-1 text-xs text-slate-500">Источник: {item.source}</div> : null}</div></div>)}</div></DashboardSection> : null}

      {dataHealth ? <div className={cn('flex items-start gap-3 rounded-2xl px-4 py-3 text-sm shadow-[0_0_0_1px_rgba(15,23,42,0.08)]', dataNeedsAttention ? 'bg-amber-50 text-amber-950' : 'bg-slate-50 text-slate-700')}><TriangleAlert className={cn('mt-0.5 h-5 w-5 shrink-0', dataNeedsAttention ? 'text-amber-700' : 'text-slate-500')} /><div><span className="font-semibold">Источник данных:</span> {dataHealth.source_label || dataHealth.source || 'не указан'}{formatDate(dataHealth.updated_at || dataHealth.last_updated_at) ? <span className="tabular-nums"> · обновлено {formatDate(dataHealth.updated_at || dataHealth.last_updated_at)}</span> : null}{dataNeedsAttention && dataHealth.missing?.length ? <span> · не хватает: {dataHealth.missing.join(', ')}</span> : null}</div></div> : null}

      <DashboardSection title="Путь роста" description="Подтверждённые шаги, препятствия и следующий приоритет собраны в одном плане.">
        <Button type="button" variant="outline" onClick={() => navigate('/dashboard/progress')} className="min-h-11 gap-2 transition-transform active:scale-[0.96]">Продолжить путь роста<ArrowRight className="h-4 w-4" /></Button>
      </DashboardSection>
    </div>
  );
};
