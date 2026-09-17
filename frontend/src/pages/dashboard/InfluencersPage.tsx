import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowRight, CheckCircle2, CircleAlert, Loader2, Megaphone, RefreshCw, Search, Sparkles } from 'lucide-react';
import { Link, useOutletContext, useSearchParams } from 'react-router-dom';

import { AccessPreview } from '@/components/access/AccessBoundary';
import { DashboardPageHeader } from '@/components/dashboard/DashboardPrimitives';
import { JourneyActionCard } from '@/components/journey/JourneyActionCard';
import { Button } from '@/components/ui/button';
import { CreatorCityCombobox } from '@/features/influencers/CreatorCityCombobox';
import { CreatorOfferBuilder } from '@/features/influencers/CreatorOfferBuilder';
import {
  influencerWorkspaceQuery,
  influencerAudienceLabel,
  influencerPlatformLabel,
  influencerTopicLabel,
  type InfluencerCreator,
  type InfluencerWorkspaceData,
  type InfluencerWorkspaceFilters,
} from '@/features/influencers/influencerWorkspace';
import { newAuth } from '@/lib/auth_new';
import { loadJourneyActions, type JourneyAction } from '@/lib/leadJourney';
import { cn } from '@/lib/utils';

type InfluencerContext = {
  currentBusinessId?: string | null;
  currentBusiness?: { name?: string; city?: string; subscription_tier?: string; subscription_status?: string; subscription_ends_at?: string } | null;
};

type WorkspaceSection = 'all' | 'shortlisted' | 'excluded' | 'messages' | 'results';

const sections: Array<{ key: WorkspaceSection; label: string }> = [
  { key: 'all', label: 'База' },
  { key: 'shortlisted', label: 'Избранные' },
  { key: 'excluded', label: 'Не подходят' },
  { key: 'messages', label: 'Предложение' },
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

const creatorPriceLabel = (creator: InfluencerCreator) => {
  if (creator.price_min || creator.price_max) {
    const amount = creator.price_min && creator.price_max && creator.price_min !== creator.price_max
      ? `${creator.price_min.toLocaleString('ru-RU')}–${creator.price_max.toLocaleString('ru-RU')}`
      : (creator.price_min || creator.price_max || 0).toLocaleString('ru-RU');
    return `${amount} ${creator.currency || '₽'}`;
  }
  return creator.accepts_barter === true ? 'Бартер' : 'Не указана';
};

const creatorConfirmationLabel = (creator: InfluencerCreator) => {
  if (creator.confirmation_status === 'creator_confirmed') return 'Автор подтвердил';
  if (creator.confirmation_status === 'business_confirmed') return 'Проверено LocalOS';
  if (creator.confirmation_status === 'expired') return 'Нужно обновить';
  return 'Нужно уточнить';
};

export const InfluencersPage = () => {
  const { currentBusinessId, currentBusiness } = useOutletContext<InfluencerContext>();
  const [searchParams] = useSearchParams();
  const requestedSection = sections.find((item) => item.key === searchParams.get('section'))?.key || 'all';
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
      const queryFilters = { ...filters, disposition: section === 'shortlisted' ? 'shortlisted' : section === 'excluded' ? 'excluded' : filters.disposition };
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
  }, [currentBusinessId, filters, section]);

  useEffect(() => { void load(); }, [load]);

  const updateShortlist = async (creator: InfluencerCreator) => {
    if (!currentBusinessId || !creator.id) return;
    if (workspace?.preview?.limited) {
      setError('Shortlist и полный каталог входят в тариф «Привлечение».');
      return;
    }
    setBusy(creator.id);
    setError('');
    try {
      const disposition = creator.disposition === 'shortlisted' || creator.disposition === 'excluded' ? 'available' : 'shortlisted';
      await newAuth.makeRequest(`/promotion/influencers/catalog/${encodeURIComponent(creator.id)}/disposition`, {
        method: 'PATCH',
        body: JSON.stringify({ business_id: currentBusinessId, disposition }),
      });
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось изменить выбор.');
    } finally {
      setBusy('');
    }
  };

  const excludeCreator = async (creator: InfluencerCreator) => {
    if (!currentBusinessId || !creator.id) return;
    setBusy(creator.id); setError('');
    try {
      await newAuth.makeRequest(`/promotion/influencers/catalog/${encodeURIComponent(creator.id)}/disposition`, {
        method: 'PATCH',
        body: JSON.stringify({ business_id: currentBusinessId, disposition: 'excluded', reason: 'Не подходит этому бизнесу' }),
      });
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось исключить автора.');
    } finally { setBusy(''); }
  };

  const loadMore = async () => {
    if (!currentBusinessId || !workspace?.cursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const queryFilters = { ...filters, disposition: section === 'shortlisted' ? 'shortlisted' : section === 'excluded' ? 'excluded' : filters.disposition };
      const response = await newAuth.makeRequest(`/promotion/influencers/catalog?${influencerWorkspaceQuery(currentBusinessId, queryFilters, workspace.cursor).toString()}`);
      setWorkspace((current) => current ? { ...response.workspace, creators: [...(current.creators || []), ...(response.workspace?.creators || [])] } : response.workspace || null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить ещё авторов.');
    } finally {
      setLoadingMore(false);
    }
  };

  const creators = workspace?.creators || [];
  const discoverySection = section === 'all' || section === 'shortlisted' || section === 'excluded';
  const messageAccess = workspace?.access?.message_generation;
  const location = [currentBusiness?.city, workspace?.latest_search?.brief?.area].filter((value) => typeof value === 'string' && value.trim()).join(' · ');

  const filterCount = useMemo(() => Object.values(filters).filter(Boolean).length, [filters]);
  if (!currentBusinessId) return <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">Выберите бизнес, чтобы открыть подбор авторов.</div>;

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-12">
      <DashboardPageHeader eyebrow="Путь роста" title="Локальные авторы" description="Изучите общую базу, уберите неподходящих и сформулируйте одно понятное предложение. LocalOS проверит его и покажет всем подходящим авторам." icon={Megaphone} actions={<div className="flex flex-wrap gap-2"><Link to="/dashboard/influencers/registry" className="inline-flex min-h-11 items-center rounded-xl bg-slate-950 px-4 text-sm font-semibold text-white">Отклики и сотрудничества</Link><Button type="button" variant="outline" onClick={() => void load()} disabled={loading} className="min-h-11 gap-2"><RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />Обновить</Button></div>} />

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
            <label className="text-xs font-semibold text-slate-600">Имя или описание<input value={filters.query || ''} onChange={(event) => setFilters((current) => ({ ...current, query: event.target.value }))} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm" /></label>
            <label className="text-xs font-semibold text-slate-600">Площадка<select value={filters.platform || ''} onChange={(event) => setFilters((current) => ({ ...current, platform: event.target.value }))} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900"><option value="">Любая</option>{['telegram', 'instagram', 'threads', 'youtube', 'tiktok', 'vk'].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
            <CreatorCityCombobox value={filters.city || ''} options={workspace?.filters?.cities || []} onChange={(city) => setFilters((current) => ({ ...current, city }))} />
            <label className="text-xs font-semibold text-slate-600">Район<input value={filters.district || ''} onChange={(event) => setFilters((current) => ({ ...current, district: event.target.value }))} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm" /></label>
            <label className="text-xs font-semibold text-slate-600">Метро<input value={filters.metro || ''} onChange={(event) => setFilters((current) => ({ ...current, metro: event.target.value }))} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm" /></label>
            <label className="text-xs font-semibold text-slate-600">География аудитории<input value={filters.audience_geography || ''} onChange={(event) => setFilters((current) => ({ ...current, audience_geography: event.target.value }))} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm" /></label>
            <label className="text-xs font-semibold text-slate-600">Тематика<input value={filters.topic || ''} onChange={(event) => setFilters((current) => ({ ...current, topic: event.target.value }))} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm" /></label>
            <label className="text-xs font-semibold text-slate-600">Формат<input value={filters.format || ''} onChange={(event) => setFilters((current) => ({ ...current, format: event.target.value }))} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm" /></label>
            <label className="text-xs font-semibold text-slate-600">Размер аудитории<select value={filters.audience_size_band || ''} onChange={(event) => setFilters((current) => ({ ...current, audience_size_band: event.target.value }))} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900"><option value="">Любой</option><option value="nano">До 10 тыс.</option><option value="micro">10–100 тыс.</option><option value="mid">100–500 тыс.</option><option value="macro">От 500 тыс.</option></select></label>
            <div className="flex items-end"><label className="flex min-h-11 w-full cursor-pointer items-center gap-3 rounded-xl border border-slate-200 px-3 text-sm text-slate-700"><input type="checkbox" checked={Boolean(filters.barter)} onChange={(event) => setFilters((current) => ({ ...current, barter: event.target.checked }))} className="h-4 w-4" />Подходит для бартера</label></div>
            <div className="flex items-end"><label className="flex min-h-11 w-full cursor-pointer items-center gap-3 rounded-xl border border-slate-200 px-3 text-sm text-slate-700"><input type="checkbox" checked={Boolean(filters.contactable)} onChange={(event) => setFilters((current) => ({ ...current, contactable: event.target.checked }))} className="h-4 w-4" />Есть подтверждённый способ связи</label></div>
          </div>
        </section>

        {loading && !workspace ? <div className="grid min-h-64 place-items-center rounded-3xl bg-white"><span className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="h-5 w-5 animate-spin" />Загружаем авторов</span></div> : creators.length ? <section className={cn('overflow-hidden rounded-[24px] border border-slate-200 bg-white shadow-sm', workspace?.preview?.limited && 'pointer-events-none select-none')} aria-label={workspace?.preview?.limited ? 'Превью каталога инфлюенсеров' : 'Каталог инфлюенсеров'}><div className="overflow-x-auto"><table className="min-w-[1420px] w-full border-collapse text-left text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr><th className="px-4 py-3 font-semibold">Автор</th><th className="px-4 py-3 font-semibold">Аудитория</th><th className="px-4 py-3 font-semibold">Описание</th><th className="px-4 py-3 font-semibold">Темы и площадки</th><th className="px-4 py-3 font-semibold">Условия</th><th className="px-4 py-3 font-semibold">Стоимость</th><th className="px-4 py-3 font-semibold">Подтверждение</th><th className="px-4 py-3 font-semibold"><span className="sr-only">Действия</span></th></tr></thead><tbody className="divide-y divide-slate-100">{creators.map((creator) => { const shortlisted = creator.disposition === 'shortlisted' || creator.shortlist_status === 'shortlisted'; const excluded = creator.disposition === 'excluded' || creator.shortlist_status === 'rejected'; const topics = [creator.primary_topic, ...(creator.topics || []), ...(creator.content_styles || [])].filter((value): value is string => Boolean(value)).slice(0, 3); const evidence = (creator.evidence || []).find((item) => item.summary); return <tr key={creator.result_id} className="align-top transition-colors hover:bg-slate-50/70"><td className="w-52 px-4 py-4"><h3 className="text-sm font-semibold text-slate-950">{creator.display_name}</h3><span className="mt-1 block text-xs text-slate-500">{influencerPlatformLabel(creator.platform)} · {[creator.city, creator.area].filter(Boolean).join(' · ') || 'География уточняется'}</span></td><td className="w-28 px-4 py-4 font-semibold tabular-nums text-slate-950">{influencerAudienceLabel(creator)}</td><td className="max-w-80 px-4 py-4 text-sm leading-5 text-slate-600"><p className="line-clamp-3">{creator.description || evidence?.summary || 'Описание не добавлено'}</p></td><td className="w-56 px-4 py-4"><div className="flex flex-wrap gap-1.5">{topics.length ? topics.map((topic) => <span key={topic} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">{influencerTopicLabel(topic)}</span>) : <span className="text-xs text-slate-500">Не указаны</span>}</div><p className="mt-2 text-xs text-slate-500">{(creator.platforms || []).map(influencerPlatformLabel).join(' · ') || influencerPlatformLabel(creator.platform)}</p></td><td className="w-44 px-4 py-4 text-sm text-slate-700"><p>{creator.accepts_barter === true ? 'Готов к бартеру' : creator.accepts_barter === false ? 'Только оплата' : 'Не уточнены'}</p>{creator.formats?.length ? <p className="mt-1 text-xs text-slate-500">{creator.formats.slice(0, 3).join(' · ')}</p> : null}{creator.availability_text ? <p className="mt-1 text-xs text-slate-500">{creator.availability_text}</p> : null}</td><td className="w-32 px-4 py-4 font-medium text-slate-950">{creatorPriceLabel(creator)}</td><td className="w-44 px-4 py-4"><span className={cn('inline-flex items-center gap-1.5 text-xs font-semibold', creator.confirmation_status === 'creator_confirmed' || creator.confirmation_status === 'business_confirmed' ? 'text-emerald-700' : 'text-slate-500')}><CheckCircle2 className="h-4 w-4" />{creatorConfirmationLabel(creator)}</span>{creator.confirmed_at ? <p className="mt-1 text-xs text-slate-500">{new Date(creator.confirmed_at).toLocaleDateString('ru-RU')}</p> : null}</td><td className="w-44 px-4 py-4"><div className="flex flex-col gap-2">{creator.public_url ? <a href={creator.public_url} target="_blank" rel="noreferrer" className="inline-flex min-h-9 items-center justify-center gap-1 rounded-lg border border-slate-200 px-2 text-xs font-semibold text-slate-700"><ArrowRight className="h-3.5 w-3.5" />Площадка</a> : null}<button type="button" disabled={busy === creator.id} onClick={() => void updateShortlist(creator)} className={cn('min-h-9 rounded-lg px-2 text-xs font-semibold disabled:opacity-50', shortlisted ? 'bg-emerald-700 text-white' : 'bg-slate-950 text-white')}>{excluded ? 'Вернуть' : 'Подходит'}</button>{!excluded ? <button type="button" disabled={busy === creator.id} onClick={() => void excludeCreator(creator)} className="min-h-8 text-xs font-semibold text-slate-500 hover:text-rose-700 disabled:opacity-50">Не подходит</button> : null}</div></td></tr>; })}</tbody></table></div></section> : <div className="rounded-[28px] border border-slate-200 bg-white px-6 py-12 text-center"><Search className="mx-auto h-7 w-7 text-slate-400" /><h2 className="mt-4 text-xl font-semibold text-slate-950">Подходящих авторов пока не видно</h2><p className="mx-auto mt-2 max-w-xl text-pretty text-sm leading-6 text-slate-600">Измените фильтры. Новые авторы будут добавляться в эту же базу.</p></div>}
        {workspace?.preview?.limited ? <section className="overflow-hidden rounded-[28px] bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_18px_45px_-34px_rgba(15,23,42,0.45)] sm:p-6" aria-labelledby="influencer-preview-title"><div className="relative h-32 overflow-hidden rounded-[20px] bg-slate-100" aria-hidden="true"><div className="absolute inset-0 grid grid-cols-3 gap-3 p-3 blur-[7px]"><span className="rounded-2xl bg-white shadow-sm" /><span className="rounded-2xl bg-white shadow-sm" /><span className="rounded-2xl bg-white shadow-sm" /></div><div className="absolute inset-0 bg-gradient-to-b from-white/10 to-white/80" /></div><div className="relative -mt-5 rounded-[20px] bg-white p-5 text-center shadow-[0_0_0_1px_rgba(15,23,42,0.07)]"><h2 id="influencer-preview-title" className="text-balance text-xl font-semibold text-slate-950">В каталоге ещё <span className="tabular-nums">{workspace.preview.hidden_count || 0}</span> авторов</h2><p className="mx-auto mt-2 max-w-xl text-pretty text-sm leading-6 text-slate-600">Вы увидели стабильное превью из 10 публичных карточек. Полный каталог, shortlist, сообщения и результаты откроются на тарифе «Привлечение».</p><Link to="/dashboard/profile?focus=subscription#subscription" className="mt-4 inline-flex min-h-11 items-center justify-center rounded-xl bg-slate-950 px-5 text-sm font-semibold text-white transition-[background-color,transform] hover:bg-slate-800 active:scale-[0.96]">Открыть полный подбор — тариф «Привлечение»</Link></div></section> : null}
        {workspace?.cursor ? <Button type="button" variant="outline" onClick={() => void loadMore()} disabled={loadingMore} className="min-h-11 w-full">{loadingMore ? 'Загружаем…' : 'Показать ещё'}</Button> : null}
      </> : null}

      {section === 'messages' ? (workspace?.feature_state?.offer_distribution === true || messageAccess?.status === 'available' ? <CreatorOfferBuilder businessId={currentBusinessId} businessCity={currentBusiness?.city} cityOptions={workspace?.filters?.cities || []} onSubmitted={load} /> : messageAccess ? <AccessPreview access={messageAccess} /> : null) : null}

      {section === 'results' ? <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm"><Sparkles className="h-6 w-6 text-orange-600" /><h2 className="mt-4 text-xl font-semibold text-slate-950">Результаты сотрудничества</h2><p className="mt-2 max-w-2xl text-pretty text-sm leading-6 text-slate-600">Здесь собираются размещения, охват, обращения, записи, промокоды и подтверждённая выручка.</p><Link to="/dashboard/influencers/operations" className="mt-5 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-orange-700">Открыть расширенную работу<ArrowRight className="h-4 w-4" /></Link></section> : null}
    </div>
  );
};
