import { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, CircleAlert, Copy, ExternalLink, Loader2, Mail, MapPin, UserRoundSearch, Users } from 'lucide-react';
import { Link, useOutletContext } from 'react-router-dom';

import { DashboardPageHeader } from '@/components/dashboard/DashboardPrimitives';
import { Button } from '@/components/ui/button';
import { newAuth } from '@/lib/auth_new';
import { cn } from '@/lib/utils';

type Context = { currentBusinessId?: string | null };
type Channel = { platform: string; url: string; metrics?: Record<string, number>; contactability?: string };
type Creator = {
  id: string; display_name: string; description?: string; primary_city?: string; primary_area?: string;
  home_city?: string; home_district?: string; metro_stations?: string[]; stage: string;
  channels?: Channel[]; audience_size_band?: string; audience_types?: string[]; content_styles?: string[];
  topics?: string[]; formats?: string[]; accepts_barter?: boolean; price_min?: number; price_max?: number;
  currency?: string; availability_text?: string; last_contacted_at?: string; last_replied_at?: string;
  status_reason?: string; evidence_summary?: string; evidence_url?: string; account_status?: string;
};
type Registry = { items: Creator[]; counts: Record<string, number>; total: number };
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

const audience = (channels: Channel[] = []) => {
  let total = 0;
  for (const channel of channels) {
    const metrics = channel.metrics || {};
    total += Number(metrics.followers || metrics.subscribers || metrics.members || metrics.audience_count || 0);
  }
  return total ? new Intl.NumberFormat('ru-RU').format(total) : 'не указана';
};

export const InfluencerRegistryPage = () => {
  const { currentBusinessId } = useOutletContext<Context>();
  const [registry, setRegistry] = useState<Registry | null>(null);
  const [phase, setPhase] = useState<Phase>('base');
  const [stage, setStage] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [invite, setInvite] = useState<{ name: string; url: string } | null>(null);

  const load = useCallback(async () => {
    if (!currentBusinessId) return;
    setLoading(true); setError('');
    try {
      const query = new URLSearchParams({ business_id: currentBusinessId, limit: '500' });
      if (stage) query.set('stage', stage);
      else query.set('stages', phaseStages[phase].join(','));
      const response = await newAuth.makeRequest(`/creator-portal/internal/relationships?${query.toString()}`);
      setRegistry(response.registry || null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Не удалось загрузить реестр.');
    } finally { setLoading(false); }
  }, [currentBusinessId, phase, stage]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { setStage(''); }, [phase]);

  const items = useMemo(() => (registry?.items || []).filter((item) => phaseStages[phase].includes(item.stage)), [phase, registry]);
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

  if (!currentBusinessId) return <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">Выберите бизнес.</div>;
  return <div className="mx-auto max-w-7xl space-y-6 pb-12">
    <DashboardPageHeader eyebrow="Продвижение" title="Работа с авторами" description="Единый реестр: от найденного профиля до согласованного размещения. Контакты и переписку ведёт LocalOS." icon={Users} actions={<Link to="/dashboard/influencers" className="inline-flex min-h-11 items-center rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold">К подбору</Link>} />

    <nav className="grid gap-2 rounded-[24px] bg-slate-100 p-1.5 md:grid-cols-3" aria-label="Этап работы">
      {phases.map((item) => { const Icon = item.icon; const count = phaseStages[item.key].reduce((sum, key) => sum + Number(registry?.counts?.[key] || 0), 0); return <button key={item.key} type="button" onClick={() => setPhase(item.key)} className={cn('flex min-h-16 items-center gap-3 rounded-[18px] px-4 text-left transition-[background-color,box-shadow,transform] active:scale-[0.98]', phase === item.key ? 'bg-white shadow-sm' : 'hover:bg-white/60')}><Icon className="h-5 w-5 text-orange-600" /><span className="min-w-0 flex-1"><strong className="block text-sm text-slate-950">{item.label}</strong><span className="block truncate text-xs text-slate-500">{item.hint}</span></span><span className="tabular-nums text-sm font-semibold text-slate-500">{count}</span></button>; })}
    </nav>

    <section className="flex flex-wrap items-end gap-3 rounded-2xl border border-slate-200 bg-white p-4">
      <label className="min-w-56 text-xs font-semibold text-slate-600">Статус<select value={stage} onChange={(event) => setStage(event.target.value)} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"><option value="">Все на этом этапе</option>{phaseStages[phase].map((value) => <option key={value} value={value}>{labels[value]}</option>)}</select></label>
      <p className="pb-3 text-xs text-slate-500">Найденные авторы не смешиваются с теми, кому уже написали.</p>
    </section>
    {error ? <div role="alert" className="flex gap-2 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"><CircleAlert className="h-4 w-4 shrink-0" />{error}</div> : null}
    {invite ? <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4"><div className="flex flex-wrap items-center gap-3"><Check className="h-5 w-5 text-emerald-700" /><div className="min-w-0 flex-1"><strong className="text-sm text-emerald-950">Приглашение для {invite.name}</strong><p className="mt-1 break-all text-xs text-emerald-800">{invite.url}</p></div><Button type="button" variant="outline" onClick={() => void navigator.clipboard.writeText(invite.url)} className="gap-2"><Copy className="h-4 w-4" />Скопировать</Button></div><p className="mt-3 text-xs text-emerald-800">LocalOS ничего не отправлял: ссылку нужно передать автору вручную.</p></section> : null}

    {loading ? <div className="grid min-h-64 place-items-center rounded-3xl bg-white"><span className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="h-5 w-5 animate-spin" />Загружаем реестр</span></div> : items.length ? <div className="grid gap-4 lg:grid-cols-2">{items.map((creator) => <article key={creator.id} className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-start gap-3"><div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-orange-50 font-semibold text-orange-800">{creator.display_name.slice(0, 1)}</div><div className="min-w-0 flex-1"><h2 className="truncate text-lg font-semibold text-slate-950">{creator.display_name}</h2><p className="mt-1 flex items-center gap-1 text-xs text-slate-500"><MapPin className="h-3.5 w-3.5" />{[creator.home_city || creator.primary_city, creator.home_district || creator.primary_area, ...(creator.metro_stations || [])].filter(Boolean).join(' · ') || 'география не уточнена'}</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">{labels[creator.stage] || creator.stage}</span></div>
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm"><div className="rounded-xl bg-slate-50 p-3"><span className="block text-xs text-slate-500">Аудитория</span><strong className="mt-1 block tabular-nums">{audience(creator.channels)}</strong></div><div className="rounded-xl bg-slate-50 p-3"><span className="block text-xs text-slate-500">Условия</span><strong className="mt-1 block">{creator.accepts_barter === true ? 'Бартер' : creator.price_min ? `от ${creator.price_min} ${creator.currency || 'RUB'}` : 'нужно уточнить'}</strong></div></div>
        <div className="mt-4 flex flex-wrap gap-2">{(creator.channels || []).map((channel) => <a key={`${channel.platform}-${channel.url}`} href={channel.url} target="_blank" rel="noreferrer" className="inline-flex min-h-8 items-center gap-1 rounded-lg bg-slate-100 px-2.5 text-xs font-semibold text-slate-700">{channel.platform}<ExternalLink className="h-3 w-3" /></a>)}</div>
        {creator.status_reason ? <p className="mt-4 text-sm leading-6 text-slate-700">{creator.status_reason}</p> : null}
        {creator.evidence_summary ? <div className="mt-4 rounded-xl border border-slate-100 p-3 text-xs leading-5 text-slate-600"><strong className="text-slate-800">Доказательство:</strong> {creator.evidence_summary}{creator.evidence_url ? <a href={creator.evidence_url} target="_blank" rel="noreferrer" className="ml-2 text-orange-700 underline">открыть</a> : null}</div> : null}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4"><span className="text-xs text-slate-500">{creator.last_replied_at ? `Ответ: ${new Date(creator.last_replied_at).toLocaleDateString('ru-RU')}` : creator.last_contacted_at ? `Контакт: ${new Date(creator.last_contacted_at).toLocaleDateString('ru-RU')}` : 'Ещё не писали'}</span>{creator.account_status === 'active' ? <span className="text-xs font-semibold text-emerald-700">Кабинет активен</span> : <Button type="button" variant="outline" disabled={busy === creator.id} onClick={() => void createInvite(creator)} className="min-h-10">{busy === creator.id ? 'Создаём…' : 'Создать приглашение'}</Button>}</div>
      </article>)}</div> : <div className="rounded-[28px] border border-dashed border-slate-300 bg-white px-6 py-14 text-center"><Users className="mx-auto h-7 w-7 text-slate-400" /><h2 className="mt-4 text-lg font-semibold">На этом этапе пока нет авторов</h2><p className="mt-2 text-sm text-slate-500">Вернитесь в «Базу» или измените фильтр.</p></div>}
  </div>;
};
