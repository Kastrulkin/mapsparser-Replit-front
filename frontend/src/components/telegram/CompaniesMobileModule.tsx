import { useEffect, useState, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowLeft, Building2, ChevronRight, CircleAlert, ExternalLink, MapPin, Search, ShieldCheck } from 'lucide-react';

type Role = { key: string; label: string };
type Company = { id: string; name?: string; city?: string; address?: string; primary_category?: string; locations_count?: number; roles?: Role[]; data_quality?: number; freshness?: { status?: string; updated_at?: string } };
type Detail = { company?: Company; locations?: Array<{ id: string; display_name?: string; address?: string; city?: string; is_primary?: boolean }>; external_profiles?: Array<{ id: string; provider?: string; canonical_url?: string; last_collected_at?: string }>; public_services?: Array<{ id: string; name?: string; price_text?: string; category?: string; observed_at?: string }>; contacts?: Array<{ id: string; contact_type?: string; value?: string; verification_status?: string }>; observations?: Array<{ id: string; predicate?: string; value_json?: unknown; source_type?: string; observed_at?: string }>; relationships?: Array<{ id: string; relationship_type?: string; subject_name?: string; object_name?: string }>; audits?: Array<{ id: string; kind?: string; status?: string; updated_at?: string }>; timeline?: Array<{ id: string; event_type?: string; title?: string; source?: string; occurred_at?: string; status?: string }>; freshness?: { status?: string; updated_at?: string }; data_warnings?: string[] };

const headers = () => ({ Authorization: `Bearer ${window.sessionStorage.getItem('localos_mini_session') || ''}` });
const read = async (path: string) => {
  const response = await fetch(path, { headers: headers() });
  let payload;
  try { payload = await response.json(); } catch { throw new Error('Сервис вернул некорректный ответ'); }
  if (!response.ok || payload?.success === false) throw new Error(payload?.error || 'Не удалось загрузить компании');
  return payload;
};
const post = async (path: string, body: unknown) => {
  const response = await fetch(path, { method: 'POST', headers: { ...headers(), 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  let payload;
  try { payload = await response.json(); } catch { throw new Error('Сервис вернул некорректный ответ'); }
  if (!response.ok || payload?.success === false) throw new Error(payload?.error || 'Не удалось добавить компанию в работу');
  return payload;
};
const dateLabel = (value?: string) => value ? new Date(value).toLocaleString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }) : 'ещё не обновлялось';
const valueText = (value: unknown) => typeof value === 'string' || typeof value === 'number' ? String(value) : value && typeof value === 'object' ? JSON.stringify(value) : 'Не указано';
const spring = { type: 'spring', duration: 0.3, bounce: 0 };

export const CompaniesMobileModule = ({ businessId }: { businessId?: string | null }) => {
  const requestedId = new URLSearchParams(window.location.search).get('item_id') || '';
  const [items, setItems] = useState<Company[]>([]);
  const [selectedId, setSelectedId] = useState(requestedId || (businessId ? 'own' : ''));
  const [detail, setDetail] = useState<Detail | null>(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [workBusy, setWorkBusy] = useState(false);
  const [workMessage, setWorkMessage] = useState('');

  const addToWork = async () => {
    const companyId = detail?.company?.id;
    if (!companyId) return;
    setWorkBusy(true); setWorkMessage('');
    try {
      await post(`/api/companies/${companyId}/workstreams`, { business_id: businessId || undefined });
      setWorkMessage('Компания добавлена в работу. Дальше она появится в партнёрском сценарии.');
    } catch (reason) {
      setWorkMessage(reason instanceof Error ? reason.message : 'Не удалось добавить компанию в работу');
    } finally { setWorkBusy(false); }
  };

  useEffect(() => {
    if (selectedId) {
      setLoading(true); setError('');
      const detailPath = selectedId === 'own' && businessId ? `/api/companies/by-business/${encodeURIComponent(businessId)}` : `/api/companies/${selectedId}`;
      void read(detailPath).then(setDetail).catch((reason) => setError(reason instanceof Error ? reason.message : 'Не удалось открыть компанию')).finally(() => setLoading(false));
      return;
    }
    const timer = window.setTimeout(() => {
      setLoading(true); setError('');
      const query = new URLSearchParams({ limit: '40' });
      if (search.trim()) query.set('search', search.trim());
      void read(`/api/companies?${query.toString()}`).then((payload) => setItems(Array.isArray(payload?.items) ? payload.items : [])).catch((reason) => setError(reason instanceof Error ? reason.message : 'Не удалось загрузить компании')).finally(() => setLoading(false));
    }, 220);
    return () => window.clearTimeout(timer);
  }, [search, selectedId]);

  if (selectedId) return <AnimatePresence initial={false} mode="wait"><motion.div key={selectedId} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={spring}>
    {!businessId ? <button type="button" onClick={() => { setSelectedId(''); setDetail(null); }} className="mb-4 flex min-h-11 items-center gap-2 rounded-2xl bg-white/[0.05] pl-3 pr-4 text-xs font-semibold text-zinc-300 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96]"><ArrowLeft className="h-4 w-4" />Все компании</button> : null}
    {loading ? <div className="space-y-3">{[1, 2, 3].map((item) => <div key={item} className="h-32 animate-pulse rounded-[24px] bg-white/[0.04] motion-reduce:animate-none" />)}</div> : error ? <Error text={error} /> : detail?.company ? <div className="space-y-6">
      <header><div className="flex flex-wrap gap-1.5">{detail.company.roles?.map((role) => <span key={role.key} className="rounded-full bg-primary/10 px-2.5 py-1 text-[10px] font-semibold text-primary ring-1 ring-inset ring-primary/15">{role.label}</span>)}</div><h2 className="mt-3 text-balance text-2xl font-semibold tracking-[-0.04em]">{detail.company.name}</h2><p className="mt-1 text-pretty text-sm text-zinc-500">{detail.company.primary_category || 'Категория ещё не определена'}</p></header>
      <section className="rounded-[26px] bg-primary/[0.1] p-5 ring-1 ring-inset ring-primary/20"><span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-primary">Сейчас важнее всего</span><h3 className="mt-2 text-balance text-lg font-semibold">{detail.freshness?.status === 'fresh' ? 'Проверить историю компании' : 'Проверить публичные источники'}</h3><p className="mt-2 text-pretty text-xs leading-5 text-zinc-400">Обновлено: {dateLabel(detail.freshness?.updated_at)}</p><button type="button" onClick={() => document.getElementById('mobile-company-sources')?.scrollIntoView({ behavior: 'smooth', block: 'start' })} className="mt-4 min-h-12 w-full rounded-2xl bg-primary text-sm font-semibold transition-transform active:scale-[0.96]">Открыть источники</button>{!detail.company.roles?.some((role) => role.key === 'client' || role.key === 'localos_lead') ? <button type="button" disabled={workBusy} onClick={() => void addToWork()} className="mt-2 min-h-11 w-full rounded-2xl bg-white/[0.05] text-xs font-semibold text-zinc-200 ring-1 ring-inset ring-white/[0.08] active:scale-[0.96] disabled:opacity-50">{workBusy ? 'Добавляем…' : 'Добавить в работу'}</button> : null}{workMessage ? <p className="mt-3 text-pretty text-xs leading-5 text-zinc-300" role="status">{workMessage}</p> : null}</section>
      <Section title="Локации" count={detail.locations?.length || 0}>{detail.locations?.map((location) => <div key={location.id} className="flex min-h-16 items-center gap-3 border-b border-white/[0.06] py-3 last:border-0"><MapPin className="h-5 w-5 shrink-0 text-primary" /><div className="min-w-0"><b className="block truncate text-sm">{location.display_name || location.city || 'Точка'}</b><p className="truncate text-xs text-zinc-600">{location.address || 'Адрес не подтверждён'}</p></div></div>)}</Section>
      <div id="mobile-company-sources" className="scroll-mt-20"><Section title="Публичные источники" count={(detail.external_profiles?.length || 0) + (detail.contacts?.length || 0)}>{detail.external_profiles?.map((profile) => <div key={profile.id} className="flex min-h-16 items-center gap-3 border-b border-white/[0.06] py-3 last:border-0"><ShieldCheck className="h-5 w-5 text-emerald-400" /><div className="min-w-0 flex-1"><b className="block text-sm capitalize">{profile.provider || 'Карты'}</b><p className="truncate text-xs text-zinc-600">{dateLabel(profile.last_collected_at)}</p></div>{profile.canonical_url ? <a href={profile.canonical_url} target="_blank" rel="noreferrer" className="grid h-11 w-11 place-items-center text-zinc-500"><ExternalLink className="h-4 w-4" /></a> : null}</div>)}{detail.contacts?.map((contact) => <div key={contact.id} className="min-h-16 border-b border-white/[0.06] py-3 last:border-0"><span className="text-[10px] uppercase tracking-[0.12em] text-zinc-600">{contact.contact_type}</span><b className="block truncate text-sm">{contact.value}</b></div>)}</Section></div>
      <Section title="Услуги на картах" count={detail.public_services?.length || 0}>{detail.public_services?.slice(0, 20).map((service) => <div key={service.id} className="flex min-h-16 items-center justify-between gap-3 border-b border-white/[0.06] py-3 last:border-0"><div className="min-w-0"><b className="block truncate text-sm">{service.name || 'Услуга'}</b><p className="mt-1 text-[10px] text-zinc-600">{service.category || `Найдено ${dateLabel(service.observed_at)}`}</p></div>{service.price_text ? <span className="shrink-0 text-xs tabular-nums text-zinc-300">{service.price_text}</span> : null}</div>)}</Section>
      <Section title="Наблюдения" count={detail.observations?.length || 0}>{detail.observations?.slice(0, 8).map((item) => <div key={item.id} className="border-b border-white/[0.06] py-3 last:border-0"><div className="flex justify-between gap-3"><b className="text-sm">{item.predicate || 'Наблюдение'}</b><span className="text-[10px] text-zinc-700">{dateLabel(item.observed_at)}</span></div><p className="mt-1 text-pretty text-xs leading-5 text-zinc-400">{valueText(item.value_json)}</p><p className="mt-1 text-[10px] text-zinc-700">Источник: {item.source_type || 'не указан'}</p></div>)}</Section>
      <Section title="Аудиты" count={detail.audits?.length || 0}>{detail.audits?.slice(0, 8).map((audit) => <div key={audit.id} className="flex min-h-16 items-center justify-between gap-3 border-b border-white/[0.06] py-3 last:border-0"><div><b className="block text-sm">{audit.kind === 'sales_room_audit' ? 'Аудит для предложения' : 'Публичный аудит'}</b><p className="mt-1 text-[10px] text-zinc-600">Обновлён {dateLabel(audit.updated_at)}</p></div><span className="rounded-full bg-white/[0.05] px-2.5 py-1 text-[10px] text-zinc-400">{audit.status || 'готовится'}</span></div>)}</Section>
      <Section title="Отношения" count={detail.relationships?.length || 0}>{detail.relationships?.slice(0, 8).map((relationship) => <div key={relationship.id} className="min-h-16 border-b border-white/[0.06] py-3 last:border-0"><span className="text-[10px] uppercase tracking-[0.12em] text-primary">{relationship.relationship_type || 'связь'}</span><b className="mt-1 block text-sm">{relationship.subject_name} ↔ {relationship.object_name}</b></div>)}</Section>
      <Section title="История" count={detail.timeline?.length || 0}>{detail.timeline?.slice(0, 12).map((event) => <div key={event.id} className="border-b border-white/[0.06] py-3 last:border-0"><div className="flex items-start justify-between gap-3"><b className="text-sm">{event.title || 'Изменение'}</b><span className="shrink-0 text-[10px] text-zinc-700">{dateLabel(event.occurred_at)}</span></div><p className="mt-1 text-[10px] text-zinc-600">{event.source || 'LocalOS'} · {event.status || 'записано'}</p></div>)}</Section>
    </div> : null}
  </motion.div></AnimatePresence>;

  return <div><label className="relative block"><Search className="absolute left-4 top-4 h-4 w-4 text-zinc-600" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Название, адрес, телефон или карты" className="min-h-12 w-full rounded-2xl bg-white/[0.05] pl-11 pr-4 text-sm outline-none ring-1 ring-inset ring-white/[0.08] placeholder:text-zinc-700 focus:ring-primary/50" /></label>{loading ? <div className="mt-4 space-y-2">{[1, 2, 3, 4].map((item) => <div key={item} className="h-20 animate-pulse rounded-[20px] bg-white/[0.04] motion-reduce:animate-none" />)}</div> : error ? <div className="mt-4"><Error text={error} /></div> : items.length ? <div className="mt-4 space-y-2">{items.map((company) => <button type="button" key={company.id} onClick={() => setSelectedId(company.id)} className="flex min-h-20 w-full items-center gap-3 rounded-[22px] bg-white/[0.04] px-3 text-left ring-1 ring-inset ring-white/[0.07] transition-[background-color,scale] active:scale-[0.96]"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-primary/12 text-primary"><Building2 className="h-5 w-5" /></span><span className="min-w-0 flex-1"><b className="block truncate text-sm">{company.name || 'Компания'}</b><small className="mt-1 block truncate text-zinc-600">{[company.city, company.address].filter(Boolean).join(' · ') || 'Данные собираются'}</small><span className="mt-2 flex gap-1">{company.roles?.slice(0, 2).map((role) => <i key={role.key} className="not-italic text-[9px] text-primary">{role.label}</i>)}</span></span><span className="text-right"><b className="block text-sm tabular-nums">{company.data_quality || 0}%</b><small className="text-[9px] text-zinc-700">данные</small></span><ChevronRight className="h-4 w-4 text-zinc-700" /></button>)}</div> : <div className="mt-5 rounded-[24px] bg-white/[0.025] p-8 text-center ring-1 ring-inset ring-white/[0.06]"><Building2 className="mx-auto h-7 w-7 text-zinc-700" /><b className="mt-3 block">Компании не найдены</b><p className="mt-2 text-pretty text-xs leading-5 text-zinc-600">Измените запрос. Новые организации появятся после поиска, импорта или парсинга.</p></div>}</div>;
};

const Section = ({ title, count, children }: { title: string; count: number; children: ReactNode }) => <section><div className="flex items-end justify-between px-1"><h3 className="text-lg font-semibold">{title}</h3><span className="text-xs tabular-nums text-zinc-600">{count}</span></div><div className="mt-2 rounded-[22px] bg-white/[0.035] px-4 ring-1 ring-inset ring-white/[0.07]">{count ? children : <p className="py-5 text-xs text-zinc-600">Пока данных нет.</p>}</div></section>;
const Error = ({ text }: { text: string }) => <div className="rounded-[20px] bg-rose-500/10 p-4 text-sm text-rose-200 ring-1 ring-inset ring-rose-400/20"><CircleAlert className="h-5 w-5" /><b className="mt-2 block">Не удалось загрузить данные</b><p className="mt-1 text-pretty text-xs leading-5">{text}</p></div>;
