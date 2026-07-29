import { useCallback, useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import {
  ArrowRight,
  Building2,
  ChevronRight,
  CircleAlert,
  CopyCheck,
  ExternalLink,
  LayoutList,
  Map,
  MapPin,
  RefreshCw,
  Search,
  ShieldCheck,
  Users,
  X,
} from 'lucide-react';
import { newAuth } from '../../lib/auth_new';
import { CompanyRegistryMap } from './CompanyRegistryMap';
import { type CompanyMapPoint } from './companyRegistryMapModel';

type CompanyRole = { key: string; label: string };
type CompanySummary = {
  id: string;
  name: string;
  primary_category?: string;
  status?: string;
  address?: string;
  city?: string;
  locations_count?: number;
  roles?: CompanyRole[];
  data_quality?: number;
  freshness?: { status?: string; updated_at?: string; source?: string };
  next_action?: { key?: string; label?: string };
};
type CompanyLocation = { id: string; display_name?: string; address?: string; city?: string; is_primary?: boolean };
type CompanyProfile = { id: string; provider?: string; canonical_url?: string; last_collected_at?: string; sync_status?: string };
type CompanyContact = { id: string; contact_type?: string; value?: string; verification_status?: string; source_url?: string };
type CompanyObservation = { id: string; predicate?: string; value_json?: unknown; source_type?: string; source_url?: string; observed_at?: string; status?: string };
type CompanyDetail = {
  company: CompanySummary;
  locations: CompanyLocation[];
  external_profiles: CompanyProfile[];
  public_services: Array<{ id: string; name?: string; price_text?: string; category?: string; observed_at?: string }>;
  contacts: CompanyContact[];
  observations: CompanyObservation[];
  social_sources: Array<{ id: string; title?: string; canonical_url?: string; relation_type?: string; verification_status?: string }>;
  relationships: Array<{ id: string; relationship_type?: string; subject_name?: string; object_name?: string }>;
  audits: Array<{ id: string; kind?: string; status?: string; updated_at?: string }>;
  timeline: Array<{ id: string; title?: string; source?: string; status?: string; occurred_at?: string }>;
  freshness?: { status?: string; updated_at?: string };
  data_warnings?: string[];
};
type DuplicateCandidate = {
  key_type: string;
  normalized_value: string;
  companies_count: number;
  companies: Array<{ id: string; name: string }>;
};
type MergePreview = {
  action_id: string;
  source_company_id: string;
  target_company_id: string;
  companies: Array<{ id: string; canonical_name: string }>;
  changes: string[];
  expires_at?: string;
};
type CompanyMapCounts = {
  matching: number;
  mapped: number;
  without_coordinates: number;
  roles?: Record<string, number>;
};
type CompanyCategoryOption = { value: string; label: string; count: number };

const roleOptions = [
  ['', 'Все'],
  ['client', 'Клиенты'],
  ['localos_lead', 'Лиды LocalOS'],
  ['partner', 'Партнёры'],
  ['competitor', 'Конкуренты'],
  ['unassigned', 'Без роли'],
  ['archive', 'Архив'],
];

const dateLabel = (value?: string) => {
  if (!value) return 'данных ещё нет';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'дата неизвестна';
  return date.toLocaleString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
};

const roleTone = (key: string) => {
  if (key === 'client') return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  if (key === 'localos_lead') return 'bg-orange-50 text-orange-700 ring-orange-200';
  if (key === 'partner') return 'bg-sky-50 text-sky-700 ring-sky-200';
  if (key === 'competitor') return 'bg-violet-50 text-violet-700 ring-violet-200';
  return 'bg-slate-50 text-slate-600 ring-slate-200';
};

const RolePills = ({ roles = [] }: { roles?: CompanyRole[] }) => (
  <div className="flex flex-wrap gap-1.5">
    {roles.map((role) => (
      <span key={role.key} className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ${roleTone(role.key)}`}>
        {role.label}
      </span>
    ))}
  </div>
);

const RegistrySkeleton = () => (
  <div className="space-y-2" aria-label="Загрузка компаний">
    {[0, 1, 2, 3].map((item) => (
      <div key={item} className="h-24 animate-pulse rounded-2xl bg-slate-100 motion-reduce:animate-none" />
    ))}
  </div>
);

const valueText = (value: unknown) => {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (value && typeof value === 'object') return JSON.stringify(value);
  return 'Не указано';
};

const CompanyDrawer = ({ companyId, close }: { companyId: string; close: () => void }) => {
  const [detail, setDetail] = useState<CompanyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [workBusy, setWorkBusy] = useState(false);
  const [workMessage, setWorkMessage] = useState('');
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    newAuth.makeRequest(`/companies/${companyId}`)
      .then((payload) => {
        if (!active) return;
        if (!payload?.company) throw new Error('Компания не найдена');
        setDetail(payload);
      })
      .catch((reason) => active && setError(reason instanceof Error ? reason.message : 'Не удалось открыть компанию'))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [companyId]);

  const addToWork = async () => {
    setWorkBusy(true); setWorkMessage('');
    try {
      await newAuth.makeRequest(`/companies/${companyId}/workstreams`, { method: 'POST', body: JSON.stringify({}) });
      setWorkMessage('Компания добавлена в работу LocalOS.');
    } catch (reason) {
      setWorkMessage(reason instanceof Error ? reason.message : 'Не удалось добавить компанию в работу');
    } finally {
      setWorkBusy(false);
    }
  };

  return (
    <motion.div
      className="fixed inset-0 z-50 flex justify-end bg-slate-950/35 backdrop-blur-[2px]"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: reducedMotion ? 0 : 0.15 }}
      onClick={close}
    >
      <motion.aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="company-drawer-title"
        className="h-full w-full max-w-2xl overflow-y-auto bg-white shadow-[-24px_0_80px_rgba(15,23,42,0.16)]"
        initial={{ x: reducedMotion ? 0 : 28, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: reducedMotion ? 0 : 20, opacity: 0 }}
        transition={{ type: 'spring', duration: 0.3, bounce: 0 }}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex min-h-16 items-center justify-between bg-white/90 px-5 backdrop-blur-xl sm:px-8">
          <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Карточка компании</span>
          <button type="button" onClick={close} aria-label="Закрыть" className="grid h-11 w-11 place-items-center rounded-2xl text-slate-500 transition-[background-color,scale] hover:bg-slate-100 active:scale-[0.96]">
            <X className="h-5 w-5" />
          </button>
        </div>
        {loading ? <div className="p-5 sm:p-8"><RegistrySkeleton /></div> : error ? (
          <div className="m-5 rounded-3xl bg-rose-50 p-6 text-rose-700 ring-1 ring-inset ring-rose-100 sm:m-8">
            <CircleAlert className="h-5 w-5" /><b className="mt-3 block">Не удалось открыть компанию</b><p className="mt-1 text-sm">{error}</p>
          </div>
        ) : detail ? (
          <div className="space-y-8 px-5 pb-12 sm:px-8">
            <header>
              <h2 id="company-drawer-title" className="max-w-xl text-balance text-3xl font-semibold tracking-[-0.035em] text-slate-950">{detail.company.name}</h2>
              <p className="mt-2 text-pretty text-sm text-slate-500">{detail.company.primary_category || 'Категория пока не определена'}</p>
              <div className="mt-4"><RolePills roles={detail.company.roles} /></div>
            </header>

            <section className="rounded-[28px] bg-slate-950 p-5 text-white shadow-[0_20px_55px_rgba(15,23,42,0.18)]">
              <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-orange-400">Сейчас важнее всего</span>
              <h3 className="mt-2 text-balance text-xl font-semibold">{detail.freshness?.status === 'fresh' ? 'Проверить накопленную историю' : 'Получить свежие данные карт'}</h3>
              <p className="mt-2 text-pretty text-sm leading-6 text-slate-400">Последнее подтверждённое обновление: {dateLabel(detail.freshness?.updated_at)}</p>
              <button type="button" onClick={() => document.getElementById('company-public-history')?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'start' })} className="mt-5 flex min-h-11 w-full items-center justify-center gap-2 rounded-2xl bg-orange-500 pl-4 pr-3.5 text-sm font-semibold transition-transform active:scale-[0.96]">
                Проверить источники и историю<ArrowRight className="h-4 w-4" />
              </button>
              {!detail.company.roles?.some((role) => role.key === 'client' || role.key === 'localos_lead') ? <button type="button" disabled={workBusy} onClick={() => void addToWork()} className="mt-2 min-h-11 w-full rounded-2xl bg-white/10 px-4 text-sm font-semibold text-white ring-1 ring-inset ring-white/15 active:scale-[0.96] disabled:opacity-50">{workBusy ? 'Добавляем…' : 'Добавить в работу'}</button> : null}
              {workMessage ? <p className="mt-3 text-pretty text-xs leading-5 text-slate-300" role="status">{workMessage}</p> : null}
            </section>

            <section id="company-public-history" className="scroll-mt-20">
              <div className="flex items-center justify-between"><h3 className="text-lg font-semibold text-slate-950">Локации</h3><span className="tabular-nums text-sm text-slate-400">{detail.locations.length}</span></div>
              <div className="mt-3 divide-y divide-slate-100 rounded-3xl shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_8px_30px_rgba(15,23,42,0.05)]">
                {detail.locations.length ? detail.locations.map((location) => (
                  <div key={location.id} className="flex min-h-16 items-center gap-3 px-4 py-3"><MapPin className="h-5 w-5 shrink-0 text-orange-500" /><div className="min-w-0"><b className="block truncate text-sm text-slate-900">{location.display_name || location.city || 'Точка'}</b><p className="truncate text-xs text-slate-500">{location.address || 'Адрес ещё не подтверждён'}</p></div>{location.is_primary ? <span className="ml-auto text-[10px] font-semibold text-slate-400">Основная</span> : null}</div>
                )) : <p className="p-5 text-sm text-slate-500">Локация ещё не подтверждена.</p>}
              </div>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-slate-950">Публичный профиль</h3>
              <div className="mt-3 divide-y divide-slate-100">
                {detail.external_profiles.map((profile) => (
                  <div key={profile.id} className="flex min-h-16 items-center gap-3 py-3"><ShieldCheck className="h-5 w-5 text-emerald-500" /><div className="min-w-0 flex-1"><b className="block text-sm capitalize text-slate-900">{profile.provider || 'Карты'}</b><p className="truncate text-xs text-slate-500">Обновлено {dateLabel(profile.last_collected_at)}</p></div>{profile.canonical_url ? <a href={profile.canonical_url} target="_blank" rel="noreferrer" aria-label="Открыть источник" className="grid h-11 w-11 place-items-center rounded-2xl text-slate-400 hover:bg-slate-50"><ExternalLink className="h-4 w-4" /></a> : null}</div>
                ))}
                {detail.contacts.map((contact) => (
                  <div key={contact.id} className="flex min-h-16 items-center gap-3 py-3"><div className="min-w-0 flex-1"><span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">{contact.contact_type}</span><b className="block truncate text-sm text-slate-900">{contact.value}</b></div><span className="text-[10px] text-slate-400">{contact.verification_status === 'verified' ? 'Подтверждено' : 'Найдено'}</span></div>
                ))}
                {!detail.external_profiles.length && !detail.contacts.length ? <p className="py-5 text-sm text-slate-500">Публичные источники ещё не собраны.</p> : null}
              </div>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-slate-950">Наблюдения</h3>
              <div className="mt-3 divide-y divide-slate-100">
                {detail.observations.length ? detail.observations.slice(0, 10).map((item) => (
                  <div key={item.id} className="py-3"><div className="flex items-start justify-between gap-3"><b className="text-sm text-slate-900">{item.predicate || 'Наблюдение'}</b><span className="shrink-0 text-[10px] text-slate-400">{dateLabel(item.observed_at)}</span></div><p className="mt-1 text-pretty text-sm text-slate-600">{valueText(item.value_json)}</p><p className="mt-1 text-[10px] text-slate-400">Источник: {item.source_type || 'не указан'}</p></div>
                )) : <p className="py-5 text-sm text-slate-500">Наблюдений пока нет.</p>}
              </div>
            </section>

            <section>
              <div className="flex items-center justify-between"><h3 className="text-lg font-semibold text-slate-950">Услуги на картах</h3><span className="tabular-nums text-sm text-slate-400">{detail.public_services.length}</span></div>
              <div className="mt-3 divide-y divide-slate-100">
                {detail.public_services.length ? detail.public_services.slice(0, 30).map((service) => <div key={service.id} className="flex min-h-16 items-center justify-between gap-3 py-3"><div className="min-w-0"><b className="block truncate text-sm text-slate-900">{service.name || 'Услуга'}</b><p className="mt-1 text-xs text-slate-500">{service.category || `Найдено ${dateLabel(service.observed_at)}`}</p></div>{service.price_text ? <span className="shrink-0 text-sm tabular-nums text-slate-700">{service.price_text}</span> : null}</div>) : <p className="py-5 text-sm text-slate-500">Публичные услуги ещё не собраны.</p>}
              </div>
            </section>

            <section>
              <div className="flex items-center justify-between"><h3 className="text-lg font-semibold text-slate-950">Аудиты</h3><span className="tabular-nums text-sm text-slate-400">{detail.audits.length}</span></div>
              <div className="mt-3 divide-y divide-slate-100">
                {detail.audits.length ? detail.audits.slice(0, 10).map((audit) => <div key={audit.id} className="flex min-h-16 items-center justify-between gap-3 py-3"><div><b className="block text-sm text-slate-900">{audit.kind === 'sales_room_audit' ? 'Аудит для предложения' : 'Публичный аудит'}</b><p className="mt-1 text-xs text-slate-500">Обновлён {dateLabel(audit.updated_at)}</p></div><span className="rounded-full bg-slate-50 px-2.5 py-1 text-[10px] text-slate-500 ring-1 ring-inset ring-slate-200">{audit.status || 'готовится'}</span></div>) : <p className="py-5 text-sm text-slate-500">Аудитов пока нет.</p>}
              </div>
            </section>

            <section>
              <div className="flex items-center justify-between"><h3 className="text-lg font-semibold text-slate-950">Отношения</h3><span className="tabular-nums text-sm text-slate-400">{detail.relationships.length}</span></div>
              <div className="mt-3 divide-y divide-slate-100">
                {detail.relationships.length ? detail.relationships.slice(0, 10).map((relationship) => <div key={relationship.id} className="py-3"><span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-orange-600">{relationship.relationship_type || 'связь'}</span><b className="mt-1 block text-sm text-slate-900">{relationship.subject_name} ↔ {relationship.object_name}</b></div>) : <p className="py-5 text-sm text-slate-500">Связей пока нет.</p>}
              </div>
            </section>

            <section>
              <div className="flex items-center justify-between"><h3 className="text-lg font-semibold text-slate-950">История</h3><span className="tabular-nums text-sm text-slate-400">{detail.timeline.length}</span></div>
              <div className="mt-3 divide-y divide-slate-100">
                {detail.timeline.length ? detail.timeline.slice(0, 15).map((event) => <div key={event.id} className="py-3"><div className="flex items-start justify-between gap-3"><b className="text-sm text-slate-900">{event.title || 'Изменение'}</b><span className="shrink-0 text-[10px] text-slate-400">{dateLabel(event.occurred_at)}</span></div><p className="mt-1 text-xs text-slate-500">{event.source || 'LocalOS'} · {event.status || 'записано'}</p></div>) : <p className="py-5 text-sm text-slate-500">История появится после первого наблюдения.</p>}
              </div>
            </section>
          </div>
        ) : null}
      </motion.aside>
    </motion.div>
  );
};

export const CompanyRegistry = () => {
  const [items, setItems] = useState<CompanySummary[]>([]);
  const [search, setSearch] = useState('');
  const [role, setRole] = useState('');
  const [category, setCategory] = useState('');
  const [view, setView] = useState<'list' | 'map'>('list');
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const [showDuplicates, setShowDuplicates] = useState(false);
  const [duplicates, setDuplicates] = useState<DuplicateCandidate[]>([]);
  const [duplicatesLoading, setDuplicatesLoading] = useState(false);
  const [mergePreview, setMergePreview] = useState<MergePreview | null>(null);
  const [mergeBusy, setMergeBusy] = useState(false);
  const [mergeMessage, setMergeMessage] = useState('');
  const [mapItems, setMapItems] = useState<CompanyMapPoint[]>([]);
  const [mapCounts, setMapCounts] = useState<CompanyMapCounts | null>(null);
  const [mapCategories, setMapCategories] = useState<CompanyCategoryOption[]>([]);
  const [mapLoading, setMapLoading] = useState(true);
  const [mapError, setMapError] = useState('');
  const [mapTruncated, setMapTruncated] = useState(false);
  const reducedMotion = useReducedMotion();

  const load = useCallback(async (nextCursor = '', append = false) => {
    if (append) setLoadingMore(true);
    else setLoading(true);
    setError('');
    try {
      const query = new URLSearchParams({ limit: '30' });
      if (search.trim()) query.set('search', search.trim());
      if (role === 'archive') query.set('status', 'archived');
      else if (role) query.set('role', role);
      if (category) query.set('category', category);
      if (nextCursor) query.set('cursor', nextCursor);
      const payload = await newAuth.makeRequest(`/companies?${query.toString()}`);
      const nextItems = Array.isArray(payload?.items) ? payload.items : [];
      setItems((current) => append ? [...current, ...nextItems] : nextItems);
      setCursor(payload?.cursor || null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось загрузить компании');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [category, role, search]);

  const loadMap = useCallback(async () => {
    setMapLoading(true);
    setMapError('');
    try {
      const query = new URLSearchParams();
      if (search.trim()) query.set('search', search.trim());
      if (role === 'archive') query.set('status', 'archived');
      else if (role) query.set('role', role);
      if (category) query.set('category', category);
      if (view === 'list') query.set('summary_only', 'true');
      const payload = await newAuth.makeRequest(`/admin/companies/map?${query.toString()}`);
      if (view === 'map') setMapItems(Array.isArray(payload?.items) ? payload.items : []);
      setMapCounts(payload?.counts || null);
      setMapCategories(Array.isArray(payload?.filters?.categories) ? payload.filters.categories : []);
      setMapTruncated(Boolean(payload?.truncated));
    } catch (reason) {
      setMapError(reason instanceof Error ? reason.message : 'Не удалось загрузить карту компаний');
    } finally {
      setMapLoading(false);
    }
  }, [category, role, search, view]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadMap(), 250);
    return () => window.clearTimeout(timer);
  }, [loadMap]);

  const summary = useMemo(() => ({
    total: mapCounts?.matching ?? items.length,
    clients: mapCounts?.roles?.client ?? items.filter((item) => item.roles?.some((itemRole) => itemRole.key === 'client')).length,
    mapped: mapCounts?.mapped ?? 0,
    withoutCoordinates: mapCounts?.without_coordinates ?? 0,
  }), [items, mapCounts]);
  const selectedCategoryLabel = useMemo(
    () => mapCategories.find((item) => item.value === category)?.label || '',
    [category, mapCategories],
  );

  const loadDuplicates = useCallback(async () => {
    setShowDuplicates(true);
    setDuplicatesLoading(true);
    setMergeMessage('');
    try {
      const payload = await newAuth.makeRequest('/admin/companies/duplicates');
      setDuplicates(Array.isArray(payload?.items) ? payload.items : []);
    } catch (reason) {
      setMergeMessage(reason instanceof Error ? reason.message : 'Не удалось проверить возможные дубли');
    } finally {
      setDuplicatesLoading(false);
    }
  }, []);

  const prepareMerge = useCallback(async (sourceCompanyId: string, targetCompanyId: string, duplicate: DuplicateCandidate) => {
    setMergeBusy(true);
    setMergeMessage('');
    try {
      const payload = await newAuth.makeRequest('/admin/companies/merge/preview', {
        method: 'POST',
        body: JSON.stringify({
          source_company_id: sourceCompanyId,
          target_company_id: targetCompanyId,
          reason: `duplicate_${duplicate.key_type}`,
          evidence: { key_type: duplicate.key_type, normalized_value: duplicate.normalized_value },
        }),
      });
      setMergePreview(payload);
    } catch (reason) {
      setMergeMessage(reason instanceof Error ? reason.message : 'Не удалось подготовить объединение');
    } finally {
      setMergeBusy(false);
    }
  }, []);

  const confirmMerge = useCallback(async () => {
    if (!mergePreview) return;
    setMergeBusy(true);
    setMergeMessage('');
    try {
      await newAuth.makeRequest(`/admin/companies/merge/${mergePreview.action_id}/confirm`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      setMergePreview(null);
      setMergeMessage('Компании объединены. История и исходные идентификаторы сохранены.');
      await loadDuplicates();
      await load();
    } catch (reason) {
      setMergeMessage(reason instanceof Error ? reason.message : 'Не удалось объединить компании');
    } finally {
      setMergeBusy(false);
    }
  }, [load, loadDuplicates, mergePreview]);

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[["В выборке", summary.total], ["Клиенты", summary.clients], ["На карте", summary.mapped], ["Без координат", summary.withoutCoordinates]].map(([label, value]) => (
          <div key={String(label)} className="rounded-3xl bg-white p-4 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_8px_28px_rgba(15,23,42,0.04)]"><b className="block text-2xl tabular-nums text-slate-950">{value}</b><span className="text-xs text-slate-500">{label}</span></div>
        ))}
      </div>

      <div className="space-y-3">
        <div className="flex flex-col gap-3 xl:flex-row">
          <label className="relative min-w-0 flex-1"><Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Название, адрес, телефон, сайт или ссылка на карты" className="h-12 w-full rounded-2xl border border-slate-200 bg-white pl-11 pr-4 text-sm text-slate-900 outline-none transition-[border-color,box-shadow] placeholder:text-slate-400 focus:border-orange-300 focus:ring-4 focus:ring-orange-100" /></label>
          <label className="flex h-12 min-w-0 items-center rounded-2xl border border-slate-200 bg-white pl-4 transition-[border-color,box-shadow] focus-within:border-orange-300 focus-within:ring-4 focus-within:ring-orange-100 xl:w-72"><Building2 className="h-4 w-4 shrink-0 text-slate-400" /><span className="ml-2 shrink-0 text-xs font-semibold text-slate-500">Тип:</span><select aria-label={view === 'map' ? 'Тип бизнеса на карте' : 'Тип бизнеса'} value={category} onChange={(event) => setCategory(event.target.value)} className="h-full min-w-0 flex-1 bg-transparent pl-2 pr-3 text-sm font-medium text-slate-700 outline-none"><option value="">Все бизнесы</option>{mapCategories.map((item) => <option key={item.value} value={item.value}>{item.label} · {item.count}</option>)}</select></label>
          <div className="grid h-12 grid-cols-2 rounded-2xl bg-slate-100 p-1 shadow-inner xl:w-56" aria-label="Представление реестра">
            <button type="button" aria-pressed={view === 'list'} onClick={() => setView('list')} className={`flex min-h-10 items-center justify-center gap-2 rounded-xl px-3 text-xs font-semibold transition-[background-color,color,box-shadow,scale] active:scale-[0.96] ${view === 'list' ? 'bg-white text-slate-950 shadow-[0_1px_4px_rgba(15,23,42,0.12)]' : 'text-slate-500 hover:text-slate-800'}`}><LayoutList className="h-4 w-4" />Список</button>
            <button type="button" aria-pressed={view === 'map'} onClick={() => { setMapLoading(true); setView('map'); }} className={`flex min-h-10 items-center justify-center gap-2 rounded-xl px-3 text-xs font-semibold transition-[background-color,color,box-shadow,scale] active:scale-[0.96] ${view === 'map' ? 'bg-white text-slate-950 shadow-[0_1px_4px_rgba(15,23,42,0.12)]' : 'text-slate-500 hover:text-slate-800'}`}><Map className="h-4 w-4" />Карта</button>
          </div>
        </div>
        <div className="flex gap-2 overflow-x-auto pb-1">
          {roleOptions.map(([key, label]) => <button type="button" key={key || 'all'} aria-pressed={role === key} onClick={() => setRole(key)} className={`min-h-11 shrink-0 rounded-2xl px-4 text-xs font-semibold transition-[background-color,color,scale] active:scale-[0.96] ${role === key ? 'bg-slate-950 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>{label}</button>)}
        </div>
      </div>

      <section className="rounded-3xl bg-amber-50/70 ring-1 ring-inset ring-amber-200/70">
        <button type="button" onClick={() => showDuplicates ? setShowDuplicates(false) : void loadDuplicates()} className="flex min-h-16 w-full items-center gap-3 px-4 text-left transition-transform active:scale-[0.99] sm:px-5">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-white text-amber-600 shadow-sm"><CopyCheck className="h-5 w-5" /></span>
          <span className="min-w-0 flex-1"><b className="block text-sm text-slate-950">Возможные дубли</b><span className="text-pretty text-xs text-slate-600">LocalOS показывает только совпадения с подтверждающими признаками. Решение всегда остаётся за вами.</span></span>
          <ChevronRight className={`h-4 w-4 text-amber-500 transition-transform ${showDuplicates ? 'rotate-90' : ''}`} />
        </button>
        <AnimatePresence initial={false}>
          {showDuplicates ? (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} transition={{ type: 'spring', duration: 0.3, bounce: 0 }} className="overflow-hidden">
              <div className="space-y-3 border-t border-amber-200/70 p-4 sm:p-5">
                {duplicatesLoading ? <div className="h-20 animate-pulse rounded-2xl bg-white/70 motion-reduce:animate-none" /> : duplicates.length ? duplicates.map((duplicate) => (
                  <div key={`${duplicate.key_type}:${duplicate.normalized_value}`} className="rounded-2xl bg-white p-4 shadow-sm">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-700">Совпадает {duplicate.key_type}</p>
                    <p className="mt-1 truncate text-xs text-slate-500">{duplicate.normalized_value}</p>
                    <div className="mt-3 space-y-2">
                      {duplicate.companies.map((company, index) => (
                        <div key={company.id} className="flex min-h-11 items-center gap-2 rounded-xl bg-slate-50 px-3"><b className="min-w-0 flex-1 truncate text-sm text-slate-900">{company.name}</b>{index > 0 && duplicate.companies[0] ? <button type="button" disabled={mergeBusy} onClick={() => void prepareMerge(company.id, duplicate.companies[0].id, duplicate)} className="min-h-9 shrink-0 rounded-xl px-3 text-xs font-semibold text-orange-700 hover:bg-orange-50 disabled:opacity-50">Объединить с первой</button> : <span className="text-[10px] text-slate-400">Оставить основной</span>}</div>
                      ))}
                    </div>
                  </div>
                )) : <p className="rounded-2xl bg-white p-5 text-sm text-slate-600">Совпадений, требующих решения, сейчас нет.</p>}
                {mergeMessage ? <p className="text-sm text-slate-700" role="status">{mergeMessage}</p> : null}
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </section>

      {view === 'map' ? <CompanyRegistryMap items={mapItems} loading={mapLoading} error={mapError} truncated={mapTruncated} withoutCoordinates={summary.withoutCoordinates} categoryLabel={selectedCategoryLabel} onSelect={setSelectedId} onRetry={() => void loadMap()} /> : loading ? <RegistrySkeleton /> : error ? (
        <div className="rounded-3xl bg-rose-50 p-6 text-rose-700 ring-1 ring-inset ring-rose-100"><CircleAlert className="h-5 w-5" /><b className="mt-3 block">Реестр временно недоступен</b><p className="mt-1 text-sm">{error}</p><button type="button" onClick={() => void load()} className="mt-4 min-h-11 rounded-2xl bg-white px-4 text-sm font-semibold shadow-sm transition-transform active:scale-[0.96]">Повторить</button></div>
      ) : items.length ? (
        <motion.div layout className="divide-y divide-slate-100 overflow-hidden rounded-3xl bg-white shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_12px_36px_rgba(15,23,42,0.05)]">
          {items.map((company) => (
            <motion.button layout="position" key={company.id} type="button" onClick={() => setSelectedId(company.id)} className="flex min-h-24 w-full items-center gap-4 px-4 py-4 text-left transition-[background-color,scale] hover:bg-slate-50 active:scale-[0.99] sm:px-5" transition={{ type: 'spring', duration: 0.3, bounce: 0 }}>
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-orange-50 text-orange-600"><Building2 className="h-5 w-5" /></span>
              <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><b className="max-w-full truncate text-sm text-slate-950">{company.name}</b><RolePills roles={company.roles} /></div><p className="mt-1 truncate text-xs text-slate-500">{[company.city, company.address, company.primary_category].filter(Boolean).join(' · ') || 'Публичные данные ещё собираются'}</p><p className="mt-2 text-[11px] text-slate-400">{company.freshness?.status === 'fresh' ? 'Данные актуальны' : 'Нужно обновить'} · {dateLabel(company.freshness?.updated_at)}</p></div>
              <div className="hidden shrink-0 text-right sm:block"><b className="block text-sm tabular-nums text-slate-800">{company.data_quality || 0}%</b><span className="text-[10px] text-slate-400">полнота</span></div><ChevronRight className="h-4 w-4 shrink-0 text-slate-300" />
            </motion.button>
          ))}
        </motion.div>
      ) : (
        <div className="rounded-3xl bg-slate-50 p-10 text-center"><Users className="mx-auto h-7 w-7 text-slate-300" /><b className="mt-4 block text-slate-900">Компании не найдены</b><p className="mt-1 text-pretty text-sm text-slate-500">Измените запрос или фильтр. Новые компании появятся после поиска, импорта или парсинга.</p></div>
      )}

      {view === 'list' && cursor ? <button type="button" disabled={loadingMore} onClick={() => void load(cursor, true)} className="flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-white text-sm font-semibold text-slate-700 shadow-[0_0_0_1px_rgba(15,23,42,0.07)] transition-transform active:scale-[0.96] disabled:opacity-50">{loadingMore ? <RefreshCw className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : null}{loadingMore ? 'Загружаем…' : 'Показать ещё'}</button> : null}

      <AnimatePresence initial={false}>{selectedId ? <CompanyDrawer key={selectedId} companyId={selectedId} close={() => setSelectedId('')} /> : null}</AnimatePresence>
      <AnimatePresence initial={false}>{mergePreview ? (
        <motion.div className="fixed inset-0 z-[60] grid place-items-end bg-slate-950/40 p-3 backdrop-blur-sm sm:place-items-center" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <motion.div role="dialog" aria-modal="true" aria-labelledby="merge-preview-title" className="w-full max-w-lg rounded-[28px] bg-white p-5 shadow-2xl sm:p-6" initial={{ y: reducedMotion ? 0 : 24, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: reducedMotion ? 0 : 16, opacity: 0 }} transition={{ type: 'spring', duration: 0.3, bounce: 0 }}>
            <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-orange-600">Проверка перед объединением</span>
            <h2 id="merge-preview-title" className="mt-2 text-balance text-xl font-semibold text-slate-950">Одна ли это компания?</h2>
            <p className="mt-2 text-pretty text-sm leading-6 text-slate-600">{mergePreview.companies.map((company) => company.canonical_name).join(' → ')}</p>
            <ul className="mt-4 space-y-2">{mergePreview.changes.map((change) => <li key={change} className="flex gap-2 text-sm text-slate-700"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />{change}</li>)}</ul>
            <p className="mt-4 rounded-2xl bg-slate-50 p-3 text-xs leading-5 text-slate-500">Исходная запись не удаляется: она останется в журнале с возможностью аудита.</p>
            <div className="mt-5 grid grid-cols-2 gap-2"><button type="button" disabled={mergeBusy} onClick={() => setMergePreview(null)} className="min-h-12 rounded-2xl bg-slate-100 px-4 text-sm font-semibold text-slate-700 active:scale-[0.96]">Отмена</button><button type="button" disabled={mergeBusy} onClick={() => void confirmMerge()} className="min-h-12 rounded-2xl bg-orange-500 px-4 text-sm font-semibold text-white active:scale-[0.96] disabled:opacity-50">{mergeBusy ? 'Объединяем…' : 'Подтвердить'}</button></div>
          </motion.div>
        </motion.div>
      ) : null}</AnimatePresence>
    </div>
  );
};
