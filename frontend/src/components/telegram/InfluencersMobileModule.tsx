import { useCallback, useEffect, useState } from 'react';
import { CircleAlert, CreditCard, Loader2, Megaphone, RefreshCw, Send } from 'lucide-react';

import { JourneyActionCard } from '@/components/journey/JourneyActionCard';
import { InfluencerCreatorCard } from '@/features/influencers/InfluencerCreatorCard';
import {
  influencerWorkspaceQuery,
  type InfluencerCreator,
  type InfluencerWorkspaceData,
  type InfluencerWorkspaceFilters,
} from '@/features/influencers/influencerWorkspace';
import { mobileAuthHeaders, mobileJsonHeaders, readMobileJson } from '@/lib/mobileDataClient';
import type { JourneyAction } from '@/lib/leadJourney';
import type { MobileScope } from './ScopeProvider';

type InfluencersMobileModuleProps = {
  scope?: MobileScope;
  focusItemId?: string;
};

const mobileOfferText = (workspace?: InfluencerWorkspaceData | null) => {
  const offer = workspace?.offer || {};
  const service = typeof offer.service === 'string' ? offer.service : '';
  const reward = typeof offer.reward === 'string' ? offer.reward : service ? `${service} в подарок` : 'услуга в подарок';
  const threshold = typeof offer.threshold === 'number' || typeof offer.threshold === 'string' ? String(offer.threshold) : '3';
  return service || Object.keys(offer).length
    ? `Автор получает ${reward}, если приводит ${threshold} новых клиента.`
    : 'Выберите услугу для бартера — LocalOS подготовит механику до персональных сообщений.';
};

export const InfluencersMobileModule = ({ scope, focusItemId }: InfluencersMobileModuleProps) => {
  const businessId = scope?.kind === 'business' ? scope.id || '' : '';
  const [workspace, setWorkspace] = useState<InfluencerWorkspaceData | null>(null);
  const [journeyActions, setJourneyActions] = useState<JourneyAction[]>([]);
  const [filters, setFilters] = useState<InfluencerWorkspaceFilters>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!businessId) return;
    setLoading(true);
    setError('');
    try {
      const params = influencerWorkspaceQuery(businessId, filters);
      const [workspaceResponse, actionResponse] = await Promise.all([
        fetch(`/api/promotion/influencers/workspace?${params.toString()}`, { headers: mobileAuthHeaders() })
          .then(readMobileJson<{ workspace?: InfluencerWorkspaceData }>),
        fetch(`/api/journey-actions?business_id=${encodeURIComponent(businessId)}`, { headers: mobileAuthHeaders() })
          .then(readMobileJson<{ actions?: JourneyAction[] }>),
      ]);
      setWorkspace(workspaceResponse.workspace || null);
      setJourneyActions((actionResponse.actions || []).filter((action) => action.flow_type === 'influencer'));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить авторов.');
    } finally {
      setLoading(false);
    }
  }, [businessId, filters.audience_size_band, filters.barter, filters.city, filters.contactable, filters.format, filters.platform, filters.shortlisted, filters.topic]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!focusItemId) return;
    const focusedCreator = workspace?.creators?.find((creator) => creator.id === focusItemId || creator.result_id === focusItemId);
    if (!focusedCreator) return;
    window.requestAnimationFrame(() => document.getElementById(`mobile-influencer-${focusedCreator.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
  }, [focusItemId, workspace?.creators]);

  const updateShortlist = async (creator: InfluencerCreator) => {
    if (!businessId || !creator.result_id || workspace?.preview?.limited) return;
    setBusy(creator.result_id);
    setError('');
    try {
      await fetch(`/api/promotion/influencers/search-results/${encodeURIComponent(creator.result_id)}`, {
        method: 'PATCH',
        headers: mobileJsonHeaders(),
        body: JSON.stringify({ business_id: businessId, shortlist_status: creator.shortlist_status === 'shortlisted' ? 'suggested' : 'shortlisted' }),
      }).then(readMobileJson);
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось изменить выбор.');
    } finally {
      setBusy('');
    }
  };

  if (!businessId) return <div className="rounded-[22px] bg-white/[0.04] p-5 text-sm leading-6 text-zinc-500 ring-1 ring-inset ring-white/[0.07]">Выберите конкретный бизнес, чтобы работать с локальными авторами.</div>;

  return <div>
    <section className="rounded-[26px] bg-gradient-to-b from-primary/[0.14] to-white/[0.035] p-5 shadow-[0_18px_54px_rgba(0,0,0,0.24),0_0_0_1px_rgba(255,92,51,0.15)]">
      <div className="flex items-start gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-primary/15 text-primary"><Megaphone className="h-5 w-5" /></span><div><small className="font-semibold uppercase tracking-[0.12em] text-primary/80">Следующий шаг</small><h2 className="mt-1 text-balance text-xl font-semibold">{workspace?.next_action || 'Выберите подходящих авторов'}</h2><p className="mt-2 text-pretty text-xs leading-5 text-zinc-500">{mobileOfferText(workspace)}</p></div></div>
      <div className="mt-4 grid grid-cols-2 gap-2 text-center"><div className="rounded-[16px] bg-black/20 px-3 py-3"><b className="block text-xl tabular-nums">{workspace?.counts?.total || 0}</b><small className="text-zinc-600">подходят</small></div><div className="rounded-[16px] bg-black/20 px-3 py-3"><b className="block text-xl tabular-nums">{workspace?.counts?.shortlisted || 0}</b><small className="text-zinc-600">выбрано</small></div></div>
    </section>

    {journeyActions.length ? <section aria-label="Текущий шаг по инфлюенсерам" className="mt-4 space-y-3">{journeyActions.slice(0, 1).map((action) => <JourneyActionCard key={action.id} action={action} businessId={businessId} surface="telegram_mini_app" dark onUpdated={() => void load()} />)}</section> : null}

    {!workspace?.preview?.limited ? <div className="mt-4 grid grid-cols-2 gap-2">
      <label className="text-[11px] text-zinc-500">Площадка<select value={filters.platform || ''} onChange={(event) => setFilters((current) => ({ ...current, platform: event.target.value }))} className="mt-2 min-h-11 w-full rounded-[14px] bg-white/[0.05] px-3 text-sm text-zinc-200 ring-1 ring-inset ring-white/[0.07]"><option value="">Любая</option>{(workspace?.filters?.platforms || []).map((platform) => <option key={platform} value={platform}>{platform}</option>)}</select></label>
      <label className="text-[11px] text-zinc-500">Город и район<select value={filters.city || ''} onChange={(event) => setFilters((current) => ({ ...current, city: event.target.value }))} className="mt-2 min-h-11 w-full rounded-[14px] bg-white/[0.05] px-3 text-sm text-zinc-200 ring-1 ring-inset ring-white/[0.07]"><option value="">Любой</option>{(workspace?.filters?.cities || []).map((city) => <option key={city} value={city}>{city}</option>)}</select></label>
      <label className="text-[11px] text-zinc-500">Тема<select value={filters.topic || ''} onChange={(event) => setFilters((current) => ({ ...current, topic: event.target.value }))} className="mt-2 min-h-11 w-full rounded-[14px] bg-white/[0.05] px-3 text-sm text-zinc-200 ring-1 ring-inset ring-white/[0.07]"><option value="">Любая</option>{(workspace?.filters?.topics || []).map((topic) => <option key={topic} value={topic}>{topic}</option>)}</select></label>
      <label className="text-[11px] text-zinc-500">Формат<select value={filters.format || ''} onChange={(event) => setFilters((current) => ({ ...current, format: event.target.value }))} className="mt-2 min-h-11 w-full rounded-[14px] bg-white/[0.05] px-3 text-sm text-zinc-200 ring-1 ring-inset ring-white/[0.07]"><option value="">Любой</option>{(workspace?.filters?.formats || []).map((format) => <option key={format} value={format}>{format}</option>)}</select></label>
      <label className="flex min-h-11 items-center gap-2 rounded-[14px] bg-white/[0.05] px-3 text-xs text-zinc-400 ring-1 ring-inset ring-white/[0.07]"><input type="checkbox" checked={Boolean(filters.shortlisted)} onChange={(event) => setFilters((current) => ({ ...current, shortlisted: event.target.checked }))} className="h-4 w-4" />Избранные</label>
      <label className="flex min-h-11 items-center gap-2 rounded-[14px] bg-white/[0.05] px-3 text-xs text-zinc-400 ring-1 ring-inset ring-white/[0.07]"><input type="checkbox" checked={Boolean(filters.barter)} onChange={(event) => setFilters((current) => ({ ...current, barter: event.target.checked }))} className="h-4 w-4" />Бартер</label>
    </div> : <div className="mt-4 rounded-[18px] bg-white/[0.04] p-4 text-xs leading-5 text-zinc-500 ring-1 ring-inset ring-white/[0.07]">Это стабильное превью каталога. Фильтры откроются вместе с полным подбором и не меняют показанные 10 карточек.</div>}

    {error ? <div role="alert" className="mt-4 flex gap-3 rounded-[18px] bg-rose-400/10 p-4 text-xs leading-5 text-rose-100 ring-1 ring-inset ring-rose-400/20"><CircleAlert className="h-4 w-4 shrink-0" />{error}</div> : null}
    {loading && !workspace ? <div className="grid min-h-52 place-items-center"><span className="flex items-center gap-2 text-sm text-zinc-500"><Loader2 className="h-4 w-4 animate-spin text-primary" />Загружаем авторов</span></div> : null}

    <div className={`mt-4 space-y-3 ${workspace?.preview?.limited ? 'pointer-events-none select-none' : ''}`} aria-label={workspace?.preview?.limited ? 'Превью каталога инфлюенсеров' : 'Каталог инфлюенсеров'}>{(workspace?.creators || []).map((creator) => <div key={creator.result_id} id={`mobile-influencer-${creator.id}`}><InfluencerCreatorCard creator={creator} dark busy={busy === creator.result_id} onToggleShortlist={(item) => void updateShortlist(item)} /></div>)}</div>
    {workspace?.preview?.limited ? <section className="mt-4 overflow-hidden rounded-[24px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]" aria-labelledby="mobile-influencer-preview-title"><div className="relative h-24 overflow-hidden rounded-[18px] bg-white/[0.05]" aria-hidden="true"><div className="absolute inset-0 grid grid-cols-2 gap-2 p-3 blur-md"><span className="rounded-[15px] bg-white/[0.09]" /><span className="rounded-[15px] bg-white/[0.09]" /></div><div className="absolute inset-0 bg-gradient-to-b from-transparent to-zinc-950/80" /></div><div className="relative -mt-3 rounded-[18px] bg-zinc-900 p-4 text-center ring-1 ring-inset ring-white/[0.07]"><h3 id="mobile-influencer-preview-title" className="text-balance font-semibold">Ещё {workspace.preview.hidden_count || 0} авторов в подборе</h3><p className="mt-2 text-pretty text-xs leading-5 text-zinc-500">Полный каталог, shortlist и персональные сообщения входят в тариф «Привлечение».</p><a href={`/dashboard/profile?focus=subscription&return_to=${encodeURIComponent('/telegram/control?screen=influencers')}#subscription`} className="mt-4 flex min-h-12 items-center justify-center rounded-[15px] bg-primary px-4 text-sm font-semibold text-white transition-transform duration-150 active:scale-[0.96]">Открыть полный подбор</a></div></section> : null}
    {!loading && !(workspace?.creators || []).length ? <div className="mt-4 rounded-[24px] bg-white/[0.025] px-6 py-10 text-center ring-1 ring-inset ring-white/[0.06]"><Megaphone className="mx-auto h-7 w-7 text-zinc-700" /><h3 className="mt-3 font-semibold">Авторы пока не подобраны</h3><p className="mt-2 text-pretty text-sm leading-6 text-zinc-600">Откройте web-версию, чтобы уточнить город, аудиторию и запустить новый поиск.</p></div> : null}

    <section className="mt-5 rounded-[24px] bg-white/[0.035] p-5 ring-1 ring-inset ring-white/[0.07]">
      <div className="flex items-start gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-[14px] bg-primary/15 text-primary"><Send className="h-4 w-4" /></span><div><h2 className="font-semibold">Персональные сообщения</h2><p className="mt-1 text-pretty text-xs leading-5 text-zinc-500">Выберите авторов бесплатно. Подготовка отдельных сообщений, подключение Telegram/email и отправка открываются после оплаты.</p></div></div>
      {workspace?.access?.message_generation?.status === 'available' ? <a href="/dashboard/influencers/operations" className="mt-4 flex min-h-12 items-center justify-center gap-2 rounded-2xl bg-primary px-4 text-sm font-semibold text-white transition-transform duration-150 active:scale-[0.96]">Подготовить сообщения<Send className="h-4 w-4" /></a> : <a href={`/dashboard/profile?focus=subscription&return_to=${encodeURIComponent('/telegram/control?screen=influencers')}#subscription`} className="mt-4 flex min-h-12 items-center justify-center gap-2 rounded-2xl bg-primary px-4 text-sm font-semibold text-white transition-transform duration-150 active:scale-[0.96]"><CreditCard className="h-4 w-4" />Выбрать тариф</a>}
    </section>

    <button type="button" onClick={() => void load()} disabled={loading} className="mt-4 flex min-h-11 w-full items-center justify-center gap-2 rounded-[15px] bg-white/[0.04] text-xs font-semibold text-zinc-400 ring-1 ring-inset ring-white/[0.06]"><RefreshCw className={loading ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />Обновить</button>
  </div>;
};

export default InfluencersMobileModule;
