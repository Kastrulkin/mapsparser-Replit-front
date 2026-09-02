import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowRight, CircleAlert, Loader2, Megaphone, RefreshCw, Search, Send, Sparkles } from 'lucide-react';
import { Link, useOutletContext, useSearchParams } from 'react-router-dom';

import { AccessPreview } from '@/components/access/AccessBoundary';
import { DashboardPageHeader } from '@/components/dashboard/DashboardPrimitives';
import { JourneyActionCard } from '@/components/journey/JourneyActionCard';
import { Button } from '@/components/ui/button';
import { InfluencerCreatorCard } from '@/features/influencers/InfluencerCreatorCard';
import {
  influencerWorkspaceQuery,
  type InfluencerCreator,
  type InfluencerWorkspaceData,
  type InfluencerWorkspaceFilters,
} from '@/features/influencers/influencerWorkspace';
import { newAuth } from '@/lib/auth_new';
import { loadJourneyActions, type JourneyAction } from '@/lib/leadJourney';
import { getCapabilityAccessForBusiness } from '@/lib/subscriptionAccess';
import { cn } from '@/lib/utils';

type InfluencerContext = {
  currentBusinessId?: string | null;
  currentBusiness?: { name?: string; city?: string; subscription_tier?: string; subscription_status?: string; subscription_ends_at?: string } | null;
};

type WorkspaceSection = 'recommended' | 'all' | 'shortlisted' | 'messages' | 'placements' | 'results';

const sections: Array<{ key: WorkspaceSection; label: string }> = [
  { key: 'recommended', label: 'Подобранные' },
  { key: 'all', label: 'Все авторы' },
  { key: 'shortlisted', label: 'Избранные' },
  { key: 'messages', label: 'Сообщения' },
  { key: 'placements', label: 'Размещения' },
  { key: 'results', label: 'Результаты' },
];

const offerText = (workspace?: InfluencerWorkspaceData | null) => {
  const offer = workspace?.offer || {};
  const service = typeof offer.service === 'string' ? offer.service : '';
  const threshold = typeof offer.threshold === 'number' || typeof offer.threshold === 'string' ? String(offer.threshold) : '3';
  const reward = typeof offer.reward === 'string' ? offer.reward : service ? `${service} в подарок` : 'услуга в подарок';
  if (service || Object.keys(offer).length) return `Автор рассказывает о бизнесе и получает ${reward}, если по его рекомендации приходят ${threshold} новых клиента.`;
  const briefService = workspace?.latest_search?.brief?.service;
  if (typeof briefService === 'string' && briefService.trim()) return `Предложите автору «${briefService.trim()}» за подтверждённый результат. Условия можно уточнить до подготовки сообщений.`;
  return 'Выберите услугу, которую можно предложить автору за подтверждённый результат. LocalOS подготовит понятную механику бартера.';
};

export const InfluencersPage = () => {
  const { currentBusinessId, currentBusiness } = useOutletContext<InfluencerContext>();
  const [searchParams] = useSearchParams();
  const requestedSection = sections.find((item) => item.key === searchParams.get('section'))?.key || 'recommended';
  const [workspace, setWorkspace] = useState<InfluencerWorkspaceData | null>(null);
  const [journeyActions, setJourneyActions] = useState<JourneyAction[]>([]);
  const [section, setSection] = useState<WorkspaceSection>(requestedSection);
  const [filters, setFilters] = useState<InfluencerWorkspaceFilters>({});
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!currentBusinessId) return;
    setLoading(true);
    setError('');
    try {
      const queryFilters = { ...filters, shortlisted: section === 'shortlisted' || filters.shortlisted };
      const [response, actions] = await Promise.all([
        newAuth.makeRequest(`/promotion/influencers/workspace?${influencerWorkspaceQuery(currentBusinessId, queryFilters).toString()}`),
        loadJourneyActions(currentBusinessId),
      ]);
      setWorkspace(response.workspace || null);
      setJourneyActions(actions.filter((action) => action.flow_type === 'influencer'));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить авторов.');
    } finally {
      setLoading(false);
    }
  }, [currentBusinessId, filters.audience_size_band, filters.barter, filters.city, filters.contactable, filters.format, filters.platform, filters.shortlisted, filters.topic, section]);

  useEffect(() => { void load(); }, [load]);

  const updateShortlist = async (creator: InfluencerCreator) => {
    if (!currentBusinessId || !creator.result_id) return;
    if (workspace?.preview?.limited) {
      setError('Shortlist и полный каталог входят в тариф «Привлечение».');
      return;
    }
    setBusy(creator.result_id);
    setError('');
    try {
      await newAuth.makeRequest(`/promotion/influencers/search-results/${encodeURIComponent(creator.result_id)}`, {
        method: 'PATCH',
        body: JSON.stringify({ business_id: currentBusinessId, shortlist_status: creator.shortlist_status === 'shortlisted' ? 'suggested' : 'shortlisted' }),
      });
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось изменить выбор.');
    } finally {
      setBusy('');
    }
  };

  const loadMore = async () => {
    if (!currentBusinessId || !workspace?.cursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const queryFilters = { ...filters, shortlisted: section === 'shortlisted' || filters.shortlisted };
      const response = await newAuth.makeRequest(`/promotion/influencers/catalog?${influencerWorkspaceQuery(currentBusinessId, queryFilters, workspace.cursor).toString()}`);
      setWorkspace((current) => current ? { ...response.workspace, creators: [...(current.creators || []), ...(response.workspace?.creators || [])] } : response.workspace || null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить ещё авторов.');
    } finally {
      setLoadingMore(false);
    }
  };

  const creators = workspace?.creators || [];
  const discoverySection = section === 'recommended' || section === 'all' || section === 'shortlisted';
  const messageAccess = workspace?.access?.message_generation;
  const location = [currentBusiness?.city, workspace?.latest_search?.brief?.area].filter((value) => typeof value === 'string' && value.trim()).join(' · ');

  const filterCount = useMemo(() => Object.values(filters).filter(Boolean).length, [filters]);
  const influencerAccess = getCapabilityAccessForBusiness(currentBusiness, 'influencers');

  if (!currentBusinessId) return <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">Выберите бизнес, чтобы открыть подбор авторов.</div>;

  if (workspace?.preview?.limited) {
    return <div className="mx-auto max-w-7xl space-y-6 pb-12"><DashboardPageHeader eyebrow="Превью · тариф «Привлечение»" title="Инфлюенсеры рядом" description={`Сейчас: ${influencerAccess.tierName}. Видны 10 стабильных публичных карточек; полный подбор и действия откроются после повышения.`} icon={Megaphone} /><section className="rounded-[24px] bg-emerald-50 p-5 text-sm leading-6 text-emerald-950 ring-1 ring-emerald-200"><strong>Уже доступно:</strong> публичное preview и общее число авторов. <strong>После повышения:</strong> фильтры, shortlist, сообщения, размещения и результаты.</section>{error ? <div role="alert" className="rounded-2xl bg-rose-50 p-4 text-sm text-rose-900 ring-1 ring-rose-200">{error}</div> : null}<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3" aria-label="Превью каталога инфлюенсеров">{creators.map((creator) => <div key={creator.result_id} className="pointer-events-none select-none"><InfluencerCreatorCard creator={creator} onToggleShortlist={() => undefined} /></div>)}</div><section className="overflow-hidden rounded-[28px] bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.08)] sm:p-6"><div className="relative h-28 overflow-hidden rounded-[20px] bg-slate-100" aria-hidden="true"><div className="absolute inset-0 grid grid-cols-3 gap-3 p-3 blur-[7px]"><span className="rounded-2xl bg-white" /><span className="rounded-2xl bg-white" /><span className="rounded-2xl bg-white" /></div></div><div className="relative -mt-4 rounded-[20px] bg-white p-5 text-center ring-1 ring-slate-200"><h2 className="text-xl font-semibold text-slate-950">Ещё {workspace.preview.hidden_count || 0} авторов</h2><p className="mt-2 text-sm leading-6 text-slate-600">Скрытые карточки, контакты и evidence не загружаются в браузер. После оплаты вы вернётесь сюда.</p><Link to="/dashboard/profile?focus=subscription&tier=professional#subscription" className="mt-4 inline-flex min-h-11 items-center rounded-xl bg-slate-950 px-5 text-sm font-semibold text-white">Открыть полный подбор — «Привлечение»</Link></div></section></div>;
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-12">
      <DashboardPageHeader eyebrow="Путь роста" title="Инфлюенсеры" description="Найдите людей, которым уже доверяют ваши потенциальные клиенты, выберите подходящих и только затем переходите к сообщениям." icon={Megaphone} actions={<div className="flex flex-wrap gap-2"><Link to="/dashboard/influencers/registry" className="inline-flex min-h-11 items-center rounded-xl bg-slate-950 px-4 text-sm font-semibold text-white">База и общение</Link><Button type="button" variant="outline" onClick={() => void load()} disabled={loading} className="min-h-11 gap-2"><RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />Обновить</Button></div>} />

      {journeyActions.length ? <section aria-label="Текущий шаг по инфлюенсерам" className="space-y-3">{journeyActions.slice(0, 2).map((action) => <JourneyActionCard key={action.id} action={action} businessId={currentBusinessId} onUpdated={load} />)}</section> : null}

      <section className="rounded-[28px] bg-slate-950 p-5 text-white shadow-[0_18px_50px_-30px_rgba(15,23,42,0.8)] sm:p-6">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-orange-300">Следующий шаг</p><h2 className="mt-2 text-balance text-2xl font-semibold">{workspace?.next_action || 'Выберите подходящих авторов'}</h2><p className="mt-2 max-w-3xl text-pretty text-sm leading-6 text-slate-300">{offerText(workspace)}</p>{location ? <p className="mt-3 text-xs text-slate-400">Текущий подбор: {location}</p> : null}</div>
          <div className="grid grid-cols-2 gap-3 text-center"><div className="rounded-2xl bg-white/[0.07] px-5 py-4"><strong className="block text-2xl tabular-nums">{workspace?.counts?.total || 0}</strong><span className="text-xs text-slate-400">подходят</span></div><div className="rounded-2xl bg-white/[0.07] px-5 py-4"><strong className="block text-2xl tabular-nums">{workspace?.counts?.shortlisted || 0}</strong><span className="text-xs text-slate-400">выбрано</span></div></div>
        </div>
      </section>

      <nav className="flex gap-1 overflow-x-auto rounded-2xl bg-slate-100 p-1" role="tablist" aria-label="Работа с инфлюенсерами">{sections.map((item) => <button key={item.key} type="button" role="tab" aria-selected={section === item.key} onClick={() => setSection(item.key)} className={cn('min-h-11 shrink-0 rounded-xl px-4 text-sm font-semibold transition-[background-color,box-shadow,color,transform] active:scale-[0.96] lg:flex-1', section === item.key ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-600')}>{item.label}</button>)}</nav>

      {error ? <div role="alert" className="flex gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"><CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />{error}</div> : null}

      {discoverySection ? <>
        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold text-slate-950">Фильтры <span className="tabular-nums text-slate-400">{filterCount ? `· ${filterCount}` : ''}</span></h2><p className="mt-1 text-xs text-slate-500">Показываем только публичные и подтверждённые данные.</p></div>{filterCount ? <button type="button" onClick={() => setFilters({})} className="min-h-10 rounded-xl px-3 text-sm font-semibold text-slate-600">Сбросить</button> : null}</div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="text-xs font-semibold text-slate-600">Площадка<select value={filters.platform || ''} onChange={(event) => setFilters((current) => ({ ...current, platform: event.target.value }))} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900"><option value="">Любая</option>{(workspace?.filters?.platforms || []).map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
            <label className="text-xs font-semibold text-slate-600">Город<select value={filters.city || ''} onChange={(event) => setFilters((current) => ({ ...current, city: event.target.value }))} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900"><option value="">Любой</option>{(workspace?.filters?.cities || []).map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
            <label className="text-xs font-semibold text-slate-600">Тематика<select value={filters.topic || ''} onChange={(event) => setFilters((current) => ({ ...current, topic: event.target.value }))} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900"><option value="">Любая</option>{(workspace?.filters?.topics || []).map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
            <label className="text-xs font-semibold text-slate-600">Формат<select value={filters.format || ''} onChange={(event) => setFilters((current) => ({ ...current, format: event.target.value }))} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900"><option value="">Любой</option>{(workspace?.filters?.formats || []).map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
            <label className="text-xs font-semibold text-slate-600">Размер аудитории<select value={filters.audience_size_band || ''} onChange={(event) => setFilters((current) => ({ ...current, audience_size_band: event.target.value }))} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900"><option value="">Любой</option>{(workspace?.filters?.audience_size_bands || []).map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
            <div className="flex items-end"><label className="flex min-h-11 w-full cursor-pointer items-center gap-3 rounded-xl border border-slate-200 px-3 text-sm text-slate-700"><input type="checkbox" checked={Boolean(filters.barter)} onChange={(event) => setFilters((current) => ({ ...current, barter: event.target.checked }))} className="h-4 w-4" />Подходит для бартера</label></div>
            <div className="flex items-end"><label className="flex min-h-11 w-full cursor-pointer items-center gap-3 rounded-xl border border-slate-200 px-3 text-sm text-slate-700"><input type="checkbox" checked={Boolean(filters.contactable)} onChange={(event) => setFilters((current) => ({ ...current, contactable: event.target.checked }))} className="h-4 w-4" />Есть подтверждённый способ связи</label></div>
          </div>
        </section>

        {loading && !workspace ? <div className="grid min-h-64 place-items-center rounded-3xl bg-white"><span className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="h-5 w-5 animate-spin" />Загружаем авторов</span></div> : creators.length ? <div className={cn('grid gap-4 md:grid-cols-2 xl:grid-cols-3', workspace?.preview?.limited && 'pointer-events-none select-none')} aria-label={workspace?.preview?.limited ? 'Превью каталога инфлюенсеров' : 'Каталог инфлюенсеров'}>{creators.map((creator) => <InfluencerCreatorCard key={creator.result_id} creator={creator} busy={busy === creator.result_id} onToggleShortlist={(item) => void updateShortlist(item)} />)}</div> : <div className="rounded-[28px] border border-slate-200 bg-white px-6 py-12 text-center"><Search className="mx-auto h-7 w-7 text-slate-400" /><h2 className="mt-4 text-xl font-semibold text-slate-950">Подходящих авторов пока не видно</h2><p className="mx-auto mt-2 max-w-xl text-pretty text-sm leading-6 text-slate-600">Измените фильтры или запустите подбор. LocalOS будет искать локальные площадки, а не общий каталог известных блогеров.</p><Link to="/dashboard/influencers/operations" className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-xl bg-slate-950 px-5 text-sm font-semibold text-white">Настроить подбор<ArrowRight className="h-4 w-4" /></Link></div>}
        {workspace?.preview?.limited ? <section className="overflow-hidden rounded-[28px] bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_18px_45px_-34px_rgba(15,23,42,0.45)] sm:p-6" aria-labelledby="influencer-preview-title"><div className="relative h-32 overflow-hidden rounded-[20px] bg-slate-100" aria-hidden="true"><div className="absolute inset-0 grid grid-cols-3 gap-3 p-3 blur-[7px]"><span className="rounded-2xl bg-white shadow-sm" /><span className="rounded-2xl bg-white shadow-sm" /><span className="rounded-2xl bg-white shadow-sm" /></div><div className="absolute inset-0 bg-gradient-to-b from-white/10 to-white/80" /></div><div className="relative -mt-5 rounded-[20px] bg-white p-5 text-center shadow-[0_0_0_1px_rgba(15,23,42,0.07)]"><h2 id="influencer-preview-title" className="text-balance text-xl font-semibold text-slate-950">В каталоге ещё <span className="tabular-nums">{workspace.preview.hidden_count || 0}</span> авторов</h2><p className="mx-auto mt-2 max-w-xl text-pretty text-sm leading-6 text-slate-600">Вы увидели стабильное превью из 10 публичных карточек. Полный каталог, shortlist, сообщения и результаты откроются на тарифе «Привлечение».</p><Link to="/dashboard/profile?focus=subscription#subscription" className="mt-4 inline-flex min-h-11 items-center justify-center rounded-xl bg-slate-950 px-5 text-sm font-semibold text-white transition-[background-color,transform] hover:bg-slate-800 active:scale-[0.96]">Открыть полный подбор — тариф «Привлечение»</Link></div></section> : null}
        {workspace?.cursor ? <Button type="button" variant="outline" onClick={() => void loadMore()} disabled={loadingMore} className="min-h-11 w-full">{loadingMore ? 'Загружаем…' : 'Показать ещё'}</Button> : null}
      </> : null}

      {section === 'messages' ? <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm"><div className="flex items-start gap-3"><span className="grid h-12 w-12 place-items-center rounded-2xl bg-orange-50 text-orange-700"><Send className="h-5 w-5" /></span><div><h2 className="text-xl font-semibold text-slate-950">Персональные сообщения</h2><p className="mt-2 max-w-2xl text-pretty text-sm leading-6 text-slate-600">Базовое предложение уже видно бесплатно. Здесь LocalOS подготовит отдельное сообщение каждому выбранному автору, покажет preview и запросит подтверждение перед отправкой.</p></div></div>{messageAccess?.status === 'available' ? <Link to="/dashboard/influencers/operations" className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-xl bg-slate-950 px-5 text-sm font-semibold text-white">Подготовить сообщения<ArrowRight className="h-4 w-4" /></Link> : messageAccess ? <AccessPreview access={messageAccess} className="mt-5" /> : null}</section> : null}

      {section === 'placements' || section === 'results' ? <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm"><Sparkles className="h-6 w-6 text-orange-600" /><h2 className="mt-4 text-xl font-semibold text-slate-950">{section === 'placements' ? 'Размещения' : 'Результаты сотрудничества'}</h2><p className="mt-2 max-w-2xl text-pretty text-sm leading-6 text-slate-600">{section === 'placements' ? 'После согласования здесь появятся площадка, дата, ссылка на материал и статус проверки.' : 'Здесь собираются охват, обращения, записи, промокоды и подтверждённая выручка.'}</p><Link to="/dashboard/influencers/operations" className="mt-5 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-orange-700">Открыть расширенную работу<ArrowRight className="h-4 w-4" /></Link></section> : null}
    </div>
  );
};
