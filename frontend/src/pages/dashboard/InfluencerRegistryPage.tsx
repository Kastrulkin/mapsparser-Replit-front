import { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, CircleAlert, Copy, ExternalLink, Loader2, Mail, UserRoundSearch, Users } from 'lucide-react';
import { Link, useOutletContext } from 'react-router-dom';

import { DashboardPageHeader } from '@/components/dashboard/DashboardPrimitives';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { newAuth } from '@/lib/auth_new';
import { cn } from '@/lib/utils';

type Context = { currentBusinessId?: string | null; user?: { is_superadmin?: boolean } | null };
type Channel = { platform: string; url: string; metrics?: Record<string, number>; contactability?: string };
type Creator = {
  id: string; display_name: string; description?: string; primary_city?: string; primary_area?: string;
  home_city?: string; home_district?: string; metro_stations?: string[]; stage: string;
  channels?: Channel[]; audience_size_band?: string; audience_types?: string[]; content_styles?: string[];
  topics?: string[]; formats?: string[]; accepts_barter?: boolean; price_min?: number; price_max?: number;
  currency?: string; availability_text?: string; last_contacted_at?: string; last_replied_at?: string;
  status_reason?: string; evidence_summary?: string; evidence_url?: string; account_status?: string;
  pending_offers_count?: number;
  profile_type?: string;
  representation_type?: string;
};
type RegistryFilters = {
  cities?: string[]; platforms?: string[]; audience_size_bands?: string[]; representation_types?: string[];
};
type Registry = { items: Creator[]; counts: Record<string, number>; total: number; filtered_total?: number; limit?: number; offset?: number; filters?: RegistryFilters };
type Campaign = { id: string; title: string; status: string; candidates_count?: number; engaged_count?: number };
type DistributionPreview = { eligible: number; active_accounts: number; pending_accounts: number; shortlisted: number; excluded: number };
type OfferRecipient = { id: string; status: string; display_name: string; city?: string; area?: string; responded_at?: string; response_text?: string; collaboration_id?: string; collaboration_status?: string; deliverables_count?: number; submitted_deliverables?: number; verified_deliverables?: number };
type Phase = 'base' | 'communication' | 'collaboration';

const labels: Record<string, string> = {
  discovered: 'Найден', contact_ready: 'Можно связаться', contacted: 'Написали', replied: 'Ответил',
  interested: 'Заинтересован', needs_details: 'Нужна конкретика', declined: 'Отказ', paid_only: 'Только платно',
  invalid_contact: 'Контакт недействителен', paused: 'Пауза',
};
const phaseStages: Record<Phase, string[]> = {
  base: ['discovered', 'contact_ready'],
  communication: ['contacted', 'replied', 'interested', 'needs_details', 'declined', 'paid_only', 'invalid_contact', 'paused'],
  collaboration: ['interested', 'needs_details'],
};
const phases: Array<{ key: Phase; label: string; hint: string; icon: typeof Users }> = [
  { key: 'base', label: 'База', hint: 'найти и проверить', icon: UserRoundSearch },
  { key: 'communication', label: 'Общение', hint: 'ответы и условия', icon: Mail },
  { key: 'collaboration', label: 'Сотрудничество', hint: 'офферы и результат', icon: Users },
];
const representationLabels: Record<string, string> = {
  independent: 'Самостоятельно', agency: 'Через агентство', manager: 'Через менеджера', unknown: 'Не указано',
};
const audienceBandLabels: Record<string, string> = {
  nano: 'Нано - до 1 тыс.', micro: 'Микро - 1-10 тыс.', mid: 'Средняя - 10-100 тыс.', macro: 'Крупная - 100 тыс.+', unknown: 'Не указан',
};
const profileTypeLabels: Record<string, string> = {
  author: 'Автор', channel: 'Канал', community: 'Сообщество', media: 'Медиа', aggregator: 'Агрегатор',
};

const audience = (channels: Channel[] = []) => {
  let total = 0;
  for (const channel of channels) {
    const metrics = channel.metrics || {};
    total += Number(metrics.followers || metrics.subscribers || metrics.members || metrics.audience_count || 0);
  }
  return total ? new Intl.NumberFormat('ru-RU').format(total) : 'не указана';
};

export const InfluencerRegistryPage = () => {
  const { currentBusinessId, user } = useOutletContext<Context>();
  const [registry, setRegistry] = useState<Registry | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [previews, setPreviews] = useState<Record<string, DistributionPreview>>({});
  const [recipients, setRecipients] = useState<Record<string, OfferRecipient[]>>({});
  const [phase, setPhase] = useState<Phase>('base');
  const [stage, setStage] = useState('');
  const [filters, setFilters] = useState({ query: '', city: '', topic: '', platform: '', audience_size_band: '', barter: '', representation: '', profile_type: '' });
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [invite, setInvite] = useState<{ name: string; url: string } | null>(null);
  const [messageDrafts, setMessageDrafts] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    if (!currentBusinessId) return;
    setLoading(true); setError('');
    try {
      const query = new URLSearchParams({ business_id: currentBusinessId, limit: '100', offset: String(offset) });
      if (stage) query.set('stage', stage);
      else query.set('stages', phaseStages[phase].join(','));
      Object.entries(filters).forEach(([key, value]) => {
        if (value.trim()) query.set(key, value.trim());
      });
      const [response, campaignResponse] = await Promise.all([
        newAuth.makeRequest(`/creator-portal/internal/relationships?${query.toString()}`),
        newAuth.makeRequest(`/promotion/influencers/campaigns?business_id=${encodeURIComponent(currentBusinessId)}`),
      ]);
      setRegistry(response.registry || null);
      setCampaigns(campaignResponse.campaigns || []);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Не удалось загрузить реестр.');
    } finally { setLoading(false); }
  }, [currentBusinessId, filters, offset, phase, stage]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { setStage(''); setOffset(0); }, [phase]);

  const updateFilter = (key: keyof typeof filters, value: string) => {
    setOffset(0);
    setFilters((current) => ({ ...current, [key]: value }));
  };

  const items = useMemo(() => (registry?.items || []).filter((item) => phaseStages[phase].includes(item.stage)), [phase, registry]);
  const filteredTotal = Number(registry?.filtered_total || 0);
  const canGoBack = offset > 0;
  const canGoForward = offset + items.length < filteredTotal;
  const createInvite = async (creator: Creator) => {
    if (!currentBusinessId) return;
    setBusy(creator.id); setError('');
    try {
      const response = await newAuth.makeRequest(`/creator-portal/internal/relationships/${creator.id}/invite`, {
        method: 'POST', body: JSON.stringify({ business_id: currentBusinessId }),
      });
      setInvite({ name: creator.display_name, url: response.invite.invite_url });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось создать приглашение.');
    } finally { setBusy(''); }
  };

  const previewCampaign = async (campaign: Campaign) => {
    if (!currentBusinessId) return;
    setBusy(`preview:${campaign.id}`); setError('');
    try {
      const response = await newAuth.makeRequest(`/promotion/influencers/campaigns/${encodeURIComponent(campaign.id)}/distribution-preview?business_id=${encodeURIComponent(currentBusinessId)}`);
      setPreviews((current) => ({ ...current, [campaign.id]: response.preview }));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить получателей.');
    } finally { setBusy(''); }
  };

  const approveCampaign = async (campaign: Campaign) => {
    if (!currentBusinessId || !user?.is_superadmin) return;
    setBusy(`approve:${campaign.id}`); setError('');
    try {
      await newAuth.makeRequest(`/promotion/influencers/campaigns/${encodeURIComponent(campaign.id)}/distribution-approve`, { method: 'POST', body: JSON.stringify({ business_id: currentBusinessId }) });
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось запустить выдачу.');
    } finally { setBusy(''); }
  };

  const loadRecipients = async (campaign: Campaign) => {
    if (!currentBusinessId) return;
    setBusy(`recipients:${campaign.id}`); setError('');
    try {
      const response = await newAuth.makeRequest(`/promotion/influencers/campaigns/${encodeURIComponent(campaign.id)}/offer-recipients?business_id=${encodeURIComponent(currentBusinessId)}`);
      setRecipients((current) => ({ ...current, [campaign.id]: response.recipients?.items || [] }));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить отклики.');
    } finally { setBusy(''); }
  };

  const selectCreator = async (recipient: OfferRecipient) => {
    if (!currentBusinessId || !user?.is_superadmin) return;
    setBusy(`select:${recipient.id}`); setError('');
    try {
      await newAuth.makeRequest(`/promotion/influencers/offer-recipients/${encodeURIComponent(recipient.id)}/select`, { method: 'POST', body: JSON.stringify({ business_id: currentBusinessId }) });
      const campaign = campaigns.find((item) => (recipients[item.id] || []).some((candidate) => candidate.id === recipient.id));
      if (campaign) await loadRecipients(campaign);
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось выбрать автора.');
    } finally { setBusy(''); }
  };

  const sendRecipientMessage = async (recipient: OfferRecipient) => {
    if (!currentBusinessId || !user?.is_superadmin) return;
    const message = String(messageDrafts[recipient.id] || '').trim();
    if (!message) return;
    setBusy(`message:${recipient.id}`); setError('');
    try {
      await newAuth.makeRequest(`/promotion/influencers/offer-recipients/${encodeURIComponent(recipient.id)}/messages`, { method: 'POST', body: JSON.stringify({ business_id: currentBusinessId, message }) });
      setMessageDrafts((current) => ({ ...current, [recipient.id]: '' }));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось ответить автору.');
    } finally { setBusy(''); }
  };

  if (!currentBusinessId) return <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">Выберите бизнес.</div>;
  return <div className="mx-auto max-w-7xl space-y-6 pb-12">
    <DashboardPageHeader eyebrow="Продвижение" title="Работа с авторами" description="Единый реестр: от найденного профиля до согласованного размещения. Контакты и переписку ведёт LocalOS." icon={Users} actions={<Link to="/dashboard/influencers" className="inline-flex min-h-11 items-center rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold">К подбору</Link>} />

    <nav className="grid gap-2 rounded-[24px] bg-slate-100 p-1.5 md:grid-cols-3" aria-label="Этап работы">
      {phases.map((item) => { const Icon = item.icon; const count = phaseStages[item.key].reduce((sum, key) => sum + Number(registry?.counts?.[key] || 0), 0); return <button key={item.key} type="button" onClick={() => setPhase(item.key)} className={cn('flex min-h-16 items-center gap-3 rounded-[18px] px-4 text-left transition-[background-color,box-shadow,transform] active:scale-[0.98]', phase === item.key ? 'bg-white shadow-sm' : 'hover:bg-white/60')}><Icon className="h-5 w-5 text-orange-600" /><span className="min-w-0 flex-1"><strong className="block text-sm text-slate-950">{item.label}</strong><span className="block truncate text-xs text-slate-500">{item.hint}</span></span><span className="tabular-nums text-sm font-semibold text-slate-500">{count}</span></button>; })}
    </nav>

    <section className="rounded-2xl border border-slate-200 bg-white p-4" aria-label="Фильтры авторов">
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-52 flex-1 text-xs font-semibold text-slate-600">Поиск
          <Input value={filters.query} onChange={(event) => updateFilter('query', event.target.value)} className="mt-2" placeholder="Имя или описание" />
        </label>
        <label className="min-w-48 flex-1 text-xs font-semibold text-slate-600">Этап
          <select value={stage} onChange={(event) => { setOffset(0); setStage(event.target.value); }} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"><option value="">Все на этом этапе</option>{phaseStages[phase].map((value) => <option key={value} value={value}>{labels[value]}</option>)}</select>
        </label>
        <label className="min-w-48 flex-1 text-xs font-semibold text-slate-600">Город
          <Input list="creator-registry-cities" value={filters.city} onChange={(event) => updateFilter('city', event.target.value)} className="mt-2" placeholder="Все города" />
          <datalist id="creator-registry-cities">{(registry?.filters?.cities || []).map((city) => <option key={city} value={city} />)}</datalist>
        </label>
        <label className="min-w-48 flex-1 text-xs font-semibold text-slate-600">Тематика
          <Input value={filters.topic} onChange={(event) => updateFilter('topic', event.target.value)} className="mt-2" placeholder="Например, семья" />
        </label>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <label className="text-xs font-semibold text-slate-600">Площадка<select value={filters.platform} onChange={(event) => updateFilter('platform', event.target.value)} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"><option value="">Все</option>{(registry?.filters?.platforms || []).map((platform) => <option key={platform} value={platform}>{platform}</option>)}</select></label>
        <label className="text-xs font-semibold text-slate-600">Аудитория<select value={filters.audience_size_band} onChange={(event) => updateFilter('audience_size_band', event.target.value)} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"><option value="">Любой размер</option>{(registry?.filters?.audience_size_bands || []).map((band) => <option key={band} value={band}>{audienceBandLabels[band] || band}</option>)}</select></label>
        <label className="text-xs font-semibold text-slate-600">Бартер<select value={filters.barter} onChange={(event) => updateFilter('barter', event.target.value)} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"><option value="">Не важно</option><option value="yes">Готов к бартеру</option><option value="no">Только оплата</option><option value="unknown">Не уточнено</option></select></label>
        <label className="text-xs font-semibold text-slate-600">Представительство<select value={filters.representation} onChange={(event) => updateFilter('representation', event.target.value)} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"><option value="">Любое</option>{(registry?.filters?.representation_types || []).map((value) => <option key={value} value={value}>{representationLabels[value] || value}</option>)}</select></label>
        <label className="text-xs font-semibold text-slate-600">Тип<select value={filters.profile_type} onChange={(event) => updateFilter('profile_type', event.target.value)} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"><option value="">Все</option>{Object.entries(profileTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500"><span>Показано {items.length} из {filteredTotal.toLocaleString('ru-RU')}. Город учитывает варианты названия, например «Питер» и «Санкт-Петербург».</span>{Object.values(filters).some(Boolean) ? <Button type="button" variant="ghost" onClick={() => { setOffset(0); setFilters({ query: '', city: '', topic: '', platform: '', audience_size_band: '', barter: '', representation: '', profile_type: '' }); }} className="h-8 px-2 text-xs">Сбросить фильтры</Button> : null}</div>
    </section>
    {error ? <div role="alert" className="flex gap-2 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"><CircleAlert className="h-4 w-4 shrink-0" />{error}</div> : null}
    {invite ? <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4"><div className="flex flex-wrap items-center gap-3"><Check className="h-5 w-5 text-emerald-700" /><div className="min-w-0 flex-1"><strong className="text-sm text-emerald-950">Приглашение для {invite.name}</strong><p className="mt-1 break-all text-xs text-emerald-800">{invite.url}</p></div><Button type="button" variant="outline" onClick={() => void navigator.clipboard.writeText(invite.url)} className="gap-2"><Copy className="h-4 w-4" />Скопировать</Button></div><p className="mt-3 text-xs text-emerald-800">LocalOS ничего не отправлял: ссылку нужно передать автору вручную.</p></section> : null}

    {phase === 'collaboration' ? <section className="space-y-3" aria-label="Предложения и отклики"><div><h2 className="text-xl font-semibold text-slate-950">Предложения клиента</h2><p className="mt-1 text-sm text-slate-500">Бизнес формулирует условия, LocalOS проверяет получателей и выбирает авторов из откликнувшихся.</p></div>{campaigns.length ? campaigns.map((campaign) => { const preview = previews[campaign.id]; const campaignRecipients = recipients[campaign.id] || []; return <article key={campaign.id} className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold text-slate-950">{campaign.title}</h3><p className="mt-1 text-xs text-slate-500">Статус: {campaign.status === 'needs_review' ? 'ждёт проверки LocalOS' : campaign.status === 'approved' ? 'распределяется' : campaign.status === 'active' ? 'предложение доступно авторам' : campaign.status}</p></div><div className="flex flex-wrap gap-2">{campaign.status === 'needs_review' ? <Button variant="outline" disabled={busy === `preview:${campaign.id}`} onClick={() => void previewCampaign(campaign)}>Проверить получателей</Button> : null}{['active', 'completed'].includes(campaign.status) ? <Button variant="outline" disabled={busy === `recipients:${campaign.id}`} onClick={() => void loadRecipients(campaign)}>Показать отклики</Button> : null}</div></div>{preview ? <div className="mt-4 rounded-2xl bg-slate-50 p-4"><div className="grid grid-cols-2 gap-3 sm:grid-cols-5">{[['Подходят', preview.eligible], ['С кабинетом', preview.active_accounts], ['Ждут активации', preview.pending_accounts], ['Shortlist', preview.shortlisted], ['Исключены', preview.excluded]].map(([label, value]) => <div key={String(label)}><strong className="block text-lg tabular-nums">{value}</strong><span className="text-xs text-slate-500">{label}</span></div>)}</div>{user?.is_superadmin ? <Button disabled={busy === `approve:${campaign.id}`} onClick={() => void approveCampaign(campaign)} className="mt-4 bg-slate-950">Одобрить и выдать всем подходящим</Button> : <p className="mt-4 text-xs text-slate-500">Одобрение и распределение выполняет LocalOS.</p>}</div> : null}{campaignRecipients.length ? <div className="mt-4 space-y-2 border-t border-slate-100 pt-4">{campaignRecipients.map((recipient) => <div key={recipient.id} className="rounded-xl bg-slate-50 px-3 py-3"><div className="flex flex-wrap items-center justify-between gap-3"><div><strong className="text-sm text-slate-900">{recipient.display_name}</strong><p className="text-xs text-slate-500">{[recipient.city, recipient.area].filter(Boolean).join(' · ') || 'география не указана'} · {recipient.status}</p>{recipient.response_text ? <p className="mt-1 text-xs text-slate-700">{recipient.response_text}</p> : null}{recipient.collaboration_id ? <p className="mt-2 text-xs font-medium text-slate-600">Сотрудничество: {recipient.collaboration_status || 'согласование'} · материалов {recipient.deliverables_count || 0} · на проверке {recipient.submitted_deliverables || 0} · проверено {recipient.verified_deliverables || 0}</p> : null}</div>{user?.is_superadmin && recipient.status === 'interested' ? <Button disabled={busy === `select:${recipient.id}`} onClick={() => void selectCreator(recipient)} className="bg-emerald-700">Выбрать для сотрудничества</Button> : null}</div>{user?.is_superadmin && ['available', 'interested', 'needs_details', 'selected'].includes(recipient.status) ? <div className="mt-3 flex gap-2"><Input value={messageDrafts[recipient.id] || ''} onChange={(event) => setMessageDrafts((current) => ({ ...current, [recipient.id]: event.target.value }))} placeholder="Ответить от LocalOS" /><Button variant="outline" disabled={!String(messageDrafts[recipient.id] || '').trim() || busy === `message:${recipient.id}`} onClick={() => void sendRecipientMessage(recipient)}>Отправить</Button></div> : null}</div>)}</div> : null}</article>; }) : <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">Предложений пока нет.</div>}</section> : null}

    {loading ? <div className="grid min-h-64 place-items-center rounded-3xl bg-white"><span className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="h-5 w-5 animate-spin" />Загружаем реестр</span></div> : items.length ? <section className="overflow-hidden rounded-[24px] border border-slate-200 bg-white shadow-sm" aria-label="Таблица авторов"><div className="overflow-x-auto"><table className="min-w-[1260px] w-full border-collapse text-left text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr><th className="px-4 py-3 font-semibold">Автор</th><th className="px-4 py-3 font-semibold">Город и район</th><th className="px-4 py-3 font-semibold">Тематика</th><th className="px-4 py-3 font-semibold">Площадки</th><th className="px-4 py-3 font-semibold">Аудитория</th><th className="px-4 py-3 font-semibold">Условия</th><th className="px-4 py-3 font-semibold">Представительство</th><th className="px-4 py-3 font-semibold">Этап</th><th className="px-4 py-3 font-semibold">Последнее</th><th className="px-4 py-3 font-semibold"><span className="sr-only">Действие</span></th></tr></thead><tbody className="divide-y divide-slate-100">{items.map((creator) => <tr key={creator.id} className="align-top hover:bg-slate-50/70"><td className="max-w-56 px-4 py-4"><strong className="block truncate text-slate-950">{creator.display_name}</strong><span className="mt-1 block text-xs text-slate-500">{profileTypeLabels[creator.profile_type || ''] || 'Автор'}</span></td><td className="max-w-48 px-4 py-4 text-slate-700">{[creator.home_city || creator.primary_city, creator.home_district || creator.primary_area, ...(creator.metro_stations || [])].filter(Boolean).join(' · ') || 'Не указано'}</td><td className="max-w-52 px-4 py-4 text-slate-700">{[...(creator.topics || []), ...(creator.content_styles || [])].slice(0, 4).join(' · ') || 'Не указана'}</td><td className="px-4 py-4"><div className="flex max-w-48 flex-wrap gap-1.5">{(creator.channels || []).map((channel) => <a key={`${channel.platform}-${channel.url}`} href={channel.url} target="_blank" rel="noreferrer" className="inline-flex min-h-7 items-center gap-1 rounded-md bg-slate-100 px-2 text-xs font-medium text-slate-700">{channel.platform}<ExternalLink className="h-3 w-3" /></a>)}</div></td><td className="px-4 py-4 font-semibold tabular-nums text-slate-950">{audience(creator.channels)}</td><td className="px-4 py-4 text-slate-700">{creator.accepts_barter === true ? 'Бартер' : creator.accepts_barter === false ? (creator.price_min ? `от ${creator.price_min} ${creator.currency || 'RUB'}` : 'Только оплата') : 'Не уточнены'}</td><td className="px-4 py-4 text-slate-700">{representationLabels[creator.representation_type || 'unknown'] || 'Не указано'}</td><td className="px-4 py-4"><span className="whitespace-nowrap rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">{labels[creator.stage] || creator.stage}</span></td><td className="px-4 py-4 whitespace-nowrap text-xs text-slate-500">{creator.last_replied_at ? `Ответ: ${new Date(creator.last_replied_at).toLocaleDateString('ru-RU')}` : creator.last_contacted_at ? `Контакт: ${new Date(creator.last_contacted_at).toLocaleDateString('ru-RU')}` : 'Не писали'}</td><td className="px-4 py-4 text-right">{creator.account_status === 'active' ? <span className="whitespace-nowrap text-xs font-semibold text-emerald-700">Кабинет активен</span> : Number(creator.pending_offers_count || 0) > 0 ? <Button type="button" variant="outline" disabled={busy === creator.id} onClick={() => void createInvite(creator)} className="min-h-9 whitespace-nowrap px-3 text-xs">{busy === creator.id ? 'Создаём…' : 'Пригласить'}</Button> : <span className="whitespace-nowrap text-xs text-slate-500">Нет предложения</span>}</td></tr>)}</tbody></table></div><div className="flex items-center justify-between border-t border-slate-200 px-4 py-3"><span className="text-xs text-slate-500">Страница {Math.floor(offset / 100) + 1}</span><div className="flex gap-2"><Button type="button" variant="outline" size="sm" disabled={!canGoBack} onClick={() => setOffset(Math.max(0, offset - 100))}>Назад</Button><Button type="button" variant="outline" size="sm" disabled={!canGoForward} onClick={() => setOffset(offset + 100)}>Дальше</Button></div></div></section> : <div className="rounded-[28px] border border-dashed border-slate-300 bg-white px-6 py-14 text-center"><Users className="mx-auto h-7 w-7 text-slate-400" /><h2 className="mt-4 text-lg font-semibold">По этим условиям авторов нет</h2><p className="mt-2 text-sm text-slate-500">Измените фильтры или вернитесь к другому этапу.</p></div>}
  </div>;
};
