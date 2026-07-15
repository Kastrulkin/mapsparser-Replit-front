import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  Building2,
  Check,
  ChevronDown,
  CircleAlert,
  ExternalLink,
  Filter,
  Mail,
  MapPin,
  MessageCircle,
  Phone,
  Plus,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  Users,
} from 'lucide-react';
import { newAuth } from '../../lib/auth_new';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { Checkbox } from '../ui/checkbox';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '../ui/sheet';

const LegacyProspectingManagement = React.lazy(() =>
  import('../ProspectingManagement').then((module) => ({ default: module.ProspectingManagement })),
);

type WorkstreamType = 'localos_sales' | 'client_partnership';
type RegistryView = 'leads' | 'messages' | 'results';
type ScopeFilter = 'all' | 'localos_sales' | 'client_partnership';

interface BusinessOption {
  id: string;
  name: string;
  owner: string;
  address?: string;
}

interface ClientFilterOption {
  id: string;
  name: string;
}

interface WorkstreamState {
  code?: string;
  label?: string;
  url?: string | null;
}

interface WorkstreamAction {
  code?: string;
  label?: string;
}

interface ResearchSource {
  title?: string;
  url?: string;
  source_type?: string;
  published_at?: string;
}

interface WorkstreamResearch {
  id?: string;
  score?: number;
  qualification_stage?: string;
  signal_label?: 'strong_signal' | 'reason_to_check' | 'fit_only';
  why_now?: string;
  sources?: ResearchSource[];
  suggested_opener?: string;
  opener_source_url?: string;
  limitations?: string[];
  researched_at?: string;
  stale?: boolean;
}

interface LeadWorkstream {
  id?: string | null;
  workstream_type: WorkstreamType;
  client_business_id?: string | null;
  client_business_name?: string | null;
  status?: string;
  selected_channel?: string | null;
  last_contact_at?: string | null;
  channel_state?: WorkstreamState;
  room_state?: WorkstreamState;
  next_action?: WorkstreamAction;
  research?: WorkstreamResearch | null;
  service_compatibility_score?: number | null;
  legacy?: boolean;
}

interface LeadItem {
  id: string;
  name?: string;
  category?: string;
  city?: string;
  address?: string;
  phone?: string;
  email?: string;
  website?: string;
  telegram_url?: string;
  whatsapp_url?: string;
  source?: string;
  source_kind?: string;
  source_provider?: string;
  rating?: number;
  reviews_count?: number;
  lead_kind?: 'localos' | 'partner' | 'both';
  client_business_name?: string;
  workstreams?: LeadWorkstream[];
}

interface SearchResult extends LeadItem {
  source_url?: string;
  google_id?: string;
}

interface AdminLeadRegistryProps {
  businessOptions: BusinessOption[];
}

const viewOptions: Array<{ id: RegistryView; label: string }> = [
  { id: 'leads', label: 'Лиды' },
  { id: 'messages', label: 'Сообщения' },
  { id: 'results', label: 'Результаты' },
];

const scopeOptions: Array<{ id: ScopeFilter; label: string }> = [
  { id: 'all', label: 'Все' },
  { id: 'localos_sales', label: 'LocalOS' },
  { id: 'client_partnership', label: 'Партнёры клиентов' },
];

const statusLabels: Record<string, string> = {
  unprocessed: 'Новый',
  in_progress: 'В работе',
  contacted: 'Сообщение отправлено',
  waiting_reply: 'Ждём ответ',
  replied: 'Есть ответ',
  responded: 'Есть ответ',
  converted: 'Результат получен',
  qualified: 'Результат получен',
  postponed: 'Отложен',
  not_relevant: 'Не подходит',
  closed_lost: 'Закрыт',
};

const sourceLabel = (lead: LeadItem) => {
  const provider = String(lead.source_provider || lead.source || '').toLowerCase();
  const partner = (lead.workstreams || []).find((item) => item.workstream_type === 'client_partnership');
  if (partner?.client_business_name) {
    return `Найден рядом с ${partner.client_business_name}`;
  }
  if (provider.includes('manual')) {
    return 'Добавлен вручную';
  }
  if (provider.includes('google') || provider.includes('yandex') || provider.includes('2gis') || provider.includes('apify')) {
    return 'Найден LocalOS';
  }
  return 'Добавлен в работу';
};

const workstreamLabel = (workstream: LeadWorkstream) => {
  if (workstream.workstream_type === 'localos_sales') {
    return 'Лид LocalOS';
  }
  return `Лид-партнёр · ${workstream.client_business_name || 'клиент'}`;
};

const statusLabel = (workstream: LeadWorkstream) =>
  statusLabels[String(workstream.status || 'unprocessed')] || 'В работе';

const availableContacts = (lead: LeadItem) => [
  lead.telegram_url ? 'Telegram' : '',
  lead.whatsapp_url ? 'WhatsApp' : '',
  lead.email ? 'Email' : '',
  lead.phone ? 'Телефон' : '',
].filter(Boolean);

const actionTone = (code?: string) => {
  if (code === 'find_contact') return 'text-amber-700';
  if (code === 'prepare_room') return 'text-orange-700';
  if (code === 'record_result') return 'text-emerald-700';
  return 'text-slate-700';
};

const signalLabel = (research?: WorkstreamResearch | null) => {
  if (research?.stale) return 'Нужно обновить';
  if (research?.signal_label === 'strong_signal') return 'Сильный сигнал';
  if (research?.signal_label === 'reason_to_check') return 'Есть повод';
  if (research) return 'Только соответствие';
  return '';
};

const signalTone = (research?: WorkstreamResearch | null) => {
  if (research?.stale) return 'border-amber-200 bg-amber-50 text-amber-800';
  if (research?.signal_label === 'strong_signal') return 'border-emerald-200 bg-emerald-50 text-emerald-800';
  if (research?.signal_label === 'reason_to_check') return 'border-sky-200 bg-sky-50 text-sky-800';
  return 'border-slate-200 bg-slate-50 text-slate-700';
};

const strongestResearch = (workstreams: LeadWorkstream[]) => workstreams
  .map((item) => item.research)
  .filter((item): item is WorkstreamResearch => Boolean(item))
  .sort((left, right) => Number(right.score || 0) - Number(left.score || 0))[0] || null;

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

export function AdminLeadRegistry({ businessOptions }: AdminLeadRegistryProps) {
  const [view, setView] = useState<RegistryView>('leads');
  const [scope, setScope] = useState<ScopeFilter>('all');
  const [clientBusinessId, setClientBusinessId] = useState('');
  const [actionState, setActionState] = useState('');
  const [signalStrength, setSignalStrength] = useState('');
  const [query, setQuery] = useState('');
  const [leads, setLeads] = useState<LeadItem[]>([]);
  const [clientFilterOptions, setClientFilterOptions] = useState<ClientFilterOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [selectedWorkstreamId, setSelectedWorkstreamId] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState('');
  const [notice, setNotice] = useState('');
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchStep, setSearchStep] = useState(1);
  const [searchScope, setSearchScope] = useState<WorkstreamType>('localos_sales');
  const [searchClientId, setSearchClientId] = useState('');
  const [searchCategory, setSearchCategory] = useState('');
  const [searchLocation, setSearchLocation] = useState('');
  const [searchRadius, setSearchRadius] = useState('1000');
  const [searchSource, setSearchSource] = useState('apify_yandex');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [selectedSearchIds, setSelectedSearchIds] = useState<string[]>([]);
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [localosTelegramReady, setLocalosTelegramReady] = useState(false);

  const loadLeads = useCallback(async () => {
    setLoading(true);
    setError('');
    const params = new URLSearchParams({ compact: '1', include_groups: '0', include_timeline: '0' });
    if (scope !== 'all') params.set('workstream_type', scope);
    if (clientBusinessId) params.set('client_business_id', clientBusinessId);
    if (actionState) params.set('action_state', actionState);
    try {
      const payload = await newAuth.makeRequest(`/admin/prospecting/leads?${params.toString()}`);
      setLeads(Array.isArray(payload?.leads) ? payload.leads : []);
      setClientFilterOptions(Array.isArray(payload?.client_options) ? payload.client_options : []);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить лидов');
    } finally {
      setLoading(false);
    }
  }, [scope, clientBusinessId, actionState]);

  useEffect(() => {
    loadLeads();
  }, [loadLeads]);

  useEffect(() => {
    newAuth.makeRequest('/admin/prospecting/outbound/health')
      .then((payload) => setLocalosTelegramReady(Boolean(payload?.telegram_app?.authorized)))
      .catch(() => setLocalosTelegramReady(false));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const leadId = params.get('lead');
    const workstreamId = params.get('workstream');
    if (leadId && leads.some((lead) => lead.id === leadId)) {
      setSelectedLeadId(leadId);
      setSelectedWorkstreamId(workstreamId);
    }
  }, [leads]);

  const filteredLeads = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return leads.filter((lead) => {
      if (normalized) {
        const haystack = [lead.name, lead.category, lead.city, lead.address, lead.phone, lead.email]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        if (!haystack.includes(normalized)) return false;
      }
      const workstreams = lead.workstreams || [];
      if (signalStrength && !workstreams.some((item) => item.research?.signal_label === signalStrength)) return false;
      if (view === 'messages') {
        return workstreams.some((item) => item.channel_state?.code !== 'choose_channel' || item.room_state?.code !== 'missing');
      }
      if (view === 'results') {
        return workstreams.some((item) => ['replied', 'responded', 'converted', 'qualified'].includes(String(item.status || '')));
      }
      return true;
    });
  }, [leads, query, signalStrength, view]);

  const selectedLead = leads.find((lead) => lead.id === selectedLeadId) || null;
  const selectedWorkstream = selectedLead?.workstreams?.find((item) => item.id === selectedWorkstreamId)
    || selectedLead?.workstreams?.[0]
    || null;

  useEffect(() => {
    if (!selectedLead) return;
    if (selectedWorkstreamId && selectedLead.workstreams?.some((item) => item.id === selectedWorkstreamId)) return;
    setSelectedWorkstreamId(selectedLead.workstreams?.[0]?.id || null);
  }, [selectedLead, selectedWorkstreamId]);

  const runAction = async (key: string, requestFactory: () => Promise<unknown>, successMessage: string) => {
    setBusyAction(key);
    setNotice('');
    try {
      await requestFactory();
      setNotice(successMessage);
      await loadLeads();
    } catch (requestError) {
      setNotice(requestError instanceof Error ? requestError.message : 'Действие не выполнено');
    } finally {
      setBusyAction('');
    }
  };

  const addLocalosWorkstream = () => {
    if (!selectedLead) return;
    runAction(
      'add-localos',
      () => newAuth.makeRequest(`/admin/prospecting/lead/${selectedLead.id}/workstreams`, {
        method: 'POST',
        body: JSON.stringify({ workstream_type: 'localos_sales' }),
      }),
      'Компания добавлена в продажи LocalOS. Партнёрский контур не изменён.',
    );
  };

  const chooseChannel = (channel: string) => {
    if (!selectedLead || !selectedWorkstream?.id) return;
    runAction(
      `channel-${channel}`,
      () => newAuth.makeRequest(`/admin/prospecting/lead/${selectedLead.id}/channel`, {
        method: 'POST',
        body: JSON.stringify({ channel, workstream_id: selectedWorkstream.id }),
      }),
      `Канал ${channel === 'manual' ? 'ручной отправки' : channel} выбран.`,
    );
  };

  const prepareRoom = () => {
    if (!selectedLead || !selectedWorkstream?.id) return;
    const isPartner = selectedWorkstream.workstream_type === 'client_partnership';
    const endpoint = isPartner
      ? `/partnership/leads/${selectedLead.id}/prepare-room`
      : `/admin/prospecting/lead/${selectedLead.id}/prepare-room`;
    runAction(
      'prepare-room',
      () => newAuth.makeRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify({
          business_id: selectedWorkstream.client_business_id,
          workstream_id: selectedWorkstream.id,
          data_mode: 'template',
          channel: selectedWorkstream.selected_channel || 'manual',
          reuse_existing: true,
        }),
      }),
      'Цифровая комната готова. Проверьте предложение перед отправкой.',
    );
  };

  const markSent = () => {
    if (!selectedLead || !selectedWorkstream?.id) return;
    const isPartner = selectedWorkstream.workstream_type === 'client_partnership';
    const endpoint = isPartner
      ? `/partnership/leads/${selectedLead.id}/manual-contact`
      : `/admin/prospecting/lead/${selectedLead.id}/manual-contact`;
    runAction(
      'mark-sent',
      () => newAuth.makeRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify({
          business_id: selectedWorkstream.client_business_id,
          workstream_id: selectedWorkstream.id,
          channel: selectedWorkstream.selected_channel || 'manual',
          comment: 'Отправлено вручную после проверки',
        }),
      }),
      'Отправка отмечена. Следующий шаг — зафиксировать ответ.',
    );
  };

  const startSearch = async () => {
    if (!searchCategory.trim() || !searchLocation.trim()) {
      setSearchError('Укажите категорию и территорию поиска.');
      return;
    }
    if (searchScope === 'client_partnership' && !searchClientId) {
      setSearchError('Выберите клиента, для которого ищем партнёров.');
      return;
    }
    setSearchBusy(true);
    setSearchError('');
    try {
      const created = await newAuth.makeRequest('/admin/prospecting/search', {
        method: 'POST',
        body: JSON.stringify({
          query: searchCategory.trim(),
          location: searchLocation.trim(),
          source: searchSource,
          limit: 30,
          workstream_type: searchScope,
          client_business_id: searchClientId || null,
          radius_meters: Number(searchRadius),
        }),
      });
      const jobId = String(created?.job_id || '');
      if (!jobId) throw new Error('Поиск не запустился');
      let completedResults: SearchResult[] = [];
      for (let attempt = 0; attempt < 45; attempt += 1) {
        await wait(1500);
        const response = await newAuth.makeRequest(`/admin/prospecting/search-job/${jobId}`);
        if (response?.job?.status === 'completed') {
          completedResults = Array.isArray(response.job.results) ? response.job.results : [];
          break;
        }
        if (response?.job?.status === 'failed') {
          throw new Error(response.job.error_text || 'Поиск завершился с ошибкой');
        }
      }
      setSearchResults(completedResults);
      setSelectedSearchIds([]);
      setSearchStep(3);
      if (!completedResults.length) setSearchError('Компании не найдены. Попробуйте изменить категорию или территорию.');
    } catch (requestError) {
      setSearchError(requestError instanceof Error ? requestError.message : 'Не удалось выполнить поиск');
    } finally {
      setSearchBusy(false);
    }
  };

  const saveSearchResults = async () => {
    const selected = searchResults.filter((item) => selectedSearchIds.includes(item.id || item.google_id || item.name || ''));
    if (!selected.length) {
      setSearchError('Выберите хотя бы одну компанию.');
      return;
    }
    setSearchBusy(true);
    setSearchError('');
    try {
      for (const lead of selected) {
        await newAuth.makeRequest('/admin/prospecting/save', {
          method: 'POST',
          body: JSON.stringify({
            lead,
            workstream_type: searchScope,
            client_business_id: searchScope === 'client_partnership' ? searchClientId : null,
          }),
        });
      }
      setSearchOpen(false);
      setSearchStep(1);
      setSearchResults([]);
      setNotice(`Добавлено в работу: ${selected.length}. Уже известные компании получили новый контур без дубля.`);
      await loadLeads();
    } catch (requestError) {
      setSearchError(requestError instanceof Error ? requestError.message : 'Не удалось добавить компании');
    } finally {
      setSearchBusy(false);
    }
  };

  const selectedClient = businessOptions.find((item) => item.id === searchClientId);

  useEffect(() => {
    if (searchScope !== 'client_partnership' || !selectedClient?.address || searchLocation.trim()) return;
    setSearchLocation(selectedClient.address);
  }, [searchScope, selectedClient, searchLocation]);

  return (
    <div className="min-h-[620px] bg-white">
      <div className="border-b border-slate-200 px-4 py-4 sm:px-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex min-w-0 items-center gap-2 overflow-x-auto pb-1 xl:pb-0">
            {viewOptions.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setView(item.id)}
                className={`min-h-10 whitespace-nowrap rounded-md px-4 text-sm font-semibold transition-colors active:scale-[0.96] ${
                  view === item.id ? 'bg-slate-950 text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <Button onClick={() => setSearchOpen(true)} className="min-h-11 bg-orange-500 text-white hover:bg-orange-600">
            <Search className="mr-2 h-4 w-4" />
            Найти лидов
          </Button>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(240px,1fr)_auto_minmax(170px,220px)_minmax(180px,240px)_minmax(180px,240px)]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Компания, категория, город или контакт"
              className="h-10 pl-9"
            />
          </div>
          <div className="flex min-w-0 gap-1 overflow-x-auto rounded-md bg-slate-100 p-1">
            {scopeOptions.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setScope(item.id)}
                className={`min-h-8 whitespace-nowrap rounded px-3 text-xs font-semibold transition-colors ${
                  scope === item.id ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-600 hover:text-slate-950'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <select
            value={clientBusinessId}
            onChange={(event) => setClientBusinessId(event.target.value)}
            className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-800"
            aria-label="Фильтр по клиенту"
          >
            <option value="">Все клиенты</option>
            {clientFilterOptions.map((business) => <option key={business.id} value={business.id}>{business.name}</option>)}
          </select>
          <select
            value={signalStrength}
            onChange={(event) => setSignalStrength(event.target.value)}
            className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-800"
            aria-label="Фильтр по силе сигнала"
          >
            <option value="">Любой сигнал</option>
            <option value="strong_signal">Сильный сигнал</option>
            <option value="reason_to_check">Есть повод</option>
            <option value="fit_only">Только соответствие</option>
          </select>
          <select
            value={actionState}
            onChange={(event) => setActionState(event.target.value)}
            className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-800"
            aria-label="Фильтр по следующему действию"
          >
            <option value="">Любое действие</option>
            <option value="find_contact">Найти контакт</option>
            <option value="prepare_room">Подготовить комнату</option>
            <option value="review_message">Проверить сообщение</option>
            <option value="wait_or_follow_up">Проверить ответ</option>
            <option value="record_result">Зафиксировать результат</option>
          </select>
        </div>
      </div>

      {notice && (
        <div className="mx-4 mt-4 flex items-start gap-2 rounded-md bg-emerald-50 px-4 py-3 text-sm text-emerald-800 sm:mx-6">
          <Check className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      <div className="px-4 py-3 sm:px-6">
        <div className="flex items-center justify-between gap-3 pb-3 text-sm text-slate-500">
          <span className="tabular-nums">{loading ? 'Загружаем…' : `${filteredLeads.length} компаний`}</span>
          <button type="button" onClick={loadLeads} className="flex min-h-10 items-center gap-2 px-2 font-medium hover:text-slate-950">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Обновить
          </button>
        </div>

        {error ? (
          <div className="flex min-h-40 flex-col items-center justify-center gap-3 text-center">
            <CircleAlert className="h-7 w-7 text-amber-500" />
            <p className="max-w-md text-sm text-slate-600">{error}</p>
            <Button variant="outline" onClick={loadLeads}>Повторить</Button>
          </div>
        ) : !loading && !filteredLeads.length ? (
          <div className="flex min-h-52 flex-col items-center justify-center gap-3 text-center">
            <Users className="h-8 w-8 text-slate-300" />
            <div>
              <h3 className="font-semibold text-slate-950">В этом списке пока нет компаний</h3>
              <p className="mt-1 max-w-md text-sm text-slate-500">Найдите новые компании или измените фильтры.</p>
            </div>
            <Button onClick={() => setSearchOpen(true)} className="bg-orange-500 text-white hover:bg-orange-600">Найти лидов</Button>
          </div>
        ) : (
          <div className="divide-y divide-slate-200">
            {filteredLeads.map((lead) => {
              const workstreams = lead.workstreams || [];
              const primary = workstreams[0];
              const contacts = availableContacts(lead);
              const research = strongestResearch(workstreams);
              return (
                <button
                  key={lead.id}
                  type="button"
                  onClick={() => {
                    setSelectedLeadId(lead.id);
                    setSelectedWorkstreamId(primary?.id || null);
                    setNotice('');
                  }}
                  className="grid w-full gap-3 py-4 text-left transition-colors hover:bg-slate-50 active:scale-[0.996] md:grid-cols-[minmax(240px,1.4fr)_minmax(210px,1fr)_minmax(180px,.8fr)_minmax(180px,.8fr)_40px] md:items-center md:px-2"
                >
                  <div className="min-w-0">
                    <div className="truncate font-semibold text-slate-950">{lead.name || 'Компания без названия'}</div>
                    <div className="mt-1 flex min-w-0 items-center gap-1.5 text-xs text-slate-500">
                      <MapPin className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">{[lead.category, lead.city || lead.address].filter(Boolean).join(' · ') || 'Данные уточняются'}</span>
                    </div>
                  </div>
                  <div className="flex min-w-0 flex-wrap gap-1.5">
                    {workstreams.map((workstream) => (
                      <Badge
                        key={workstream.id || `${workstream.workstream_type}-${workstream.client_business_id || 'localos'}`}
                        variant="outline"
                        className={workstream.workstream_type === 'localos_sales'
                          ? 'border-sky-200 bg-sky-50 text-sky-800'
                          : 'border-violet-200 bg-violet-50 text-violet-800'}
                      >
                        {workstreamLabel(workstream)}
                      </Badge>
                    ))}
                    {research && (
                      <Badge variant="outline" className={signalTone(research)}>
                        {signalLabel(research)} · {Number(research.score || 0)}
                      </Badge>
                    )}
                  </div>
                  <div className="min-w-0 text-sm">
                    <div className="font-medium text-slate-800">{contacts.length ? contacts.join(' · ') : 'Контакта пока нет'}</div>
                    <div className="mt-1 truncate text-xs text-slate-500">{sourceLabel(lead)}</div>
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-400">Следующий шаг</div>
                    <div className={`mt-1 truncate text-sm font-semibold ${actionTone(primary?.next_action?.code)}`}>
                      {primary?.next_action?.label || 'Открыть карточку'}
                    </div>
                  </div>
                  <ArrowRight className="hidden h-4 w-4 text-slate-400 md:block" />
                </button>
              );
            })}
          </div>
        )}
      </div>

      <details
        className="border-t border-slate-200 px-4 py-4 sm:px-6"
        onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}
      >
        <summary className="flex min-h-10 cursor-pointer list-none items-center gap-2 text-sm font-semibold text-slate-700">
          <Filter className="h-4 w-4" />
          Дополнительные инструменты и аналитика
          <ChevronDown className="ml-auto h-4 w-4" />
        </summary>
        {advancedOpen && (
          <div className="mt-4 border-t border-slate-200 pt-4">
            <React.Suspense fallback={<div className="py-8 text-center text-sm text-slate-500">Загружаем дополнительные инструменты…</div>}>
              <LegacyProspectingManagement />
            </React.Suspense>
          </div>
        )}
      </details>

      <Sheet open={Boolean(selectedLead)} onOpenChange={(open) => { if (!open) setSelectedLeadId(null); }}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          <SheetHeader className="pr-8">
            <SheetTitle className="text-wrap-balance text-xl">{selectedLead?.name || 'Карточка лида'}</SheetTitle>
            <SheetDescription>{[selectedLead?.category, selectedLead?.city || selectedLead?.address].filter(Boolean).join(' · ')}</SheetDescription>
          </SheetHeader>

          {selectedLead && selectedWorkstream && (
            <div className="mt-6 space-y-6">
              {(selectedLead.workstreams || []).length > 1 && (
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-500">Сейчас работаем как</label>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    {(selectedLead.workstreams || []).map((workstream) => (
                      <button
                        key={workstream.id || workstream.workstream_type}
                        type="button"
                        onClick={() => setSelectedWorkstreamId(workstream.id || null)}
                        className={`min-h-12 rounded-md px-3 text-left text-sm font-semibold transition-colors ${
                          selectedWorkstream.id === workstream.id
                            ? 'bg-slate-950 text-white'
                            : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                        }`}
                      >
                        {workstreamLabel(workstream)}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="bg-slate-50">{workstreamLabel(selectedWorkstream)}</Badge>
                <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-800">{statusLabel(selectedWorkstream)}</Badge>
                {selectedWorkstream.research && (
                  <Badge variant="outline" className={signalTone(selectedWorkstream.research)}>
                    {signalLabel(selectedWorkstream.research)} · {Number(selectedWorkstream.research.score || 0)}
                  </Badge>
                )}
                {selectedWorkstream.workstream_type === 'client_partnership' && selectedWorkstream.service_compatibility_score != null && (
                  <Badge variant="outline" className="border-violet-200 bg-violet-50 text-violet-800">
                    Совместимость услуг · {Number(selectedWorkstream.service_compatibility_score)}
                  </Badge>
                )}
              </div>

              {selectedWorkstream.research && (
                <section className="rounded-md bg-slate-50 p-4" aria-labelledby="lead-research-title">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 id="lead-research-title" className="text-sm font-semibold text-slate-950">Почему сейчас</h3>
                      <p className="mt-1 text-sm leading-6 text-slate-700">
                        {selectedWorkstream.research.why_now || 'Публичный повод не подтверждён. Компания подходит только по общим признакам.'}
                      </p>
                    </div>
                    <span className="text-xs text-slate-500 tabular-nums">
                      {selectedWorkstream.research.researched_at
                        ? new Date(selectedWorkstream.research.researched_at).toLocaleDateString('ru-RU')
                        : 'дата не указана'}
                    </span>
                  </div>
                  {(selectedWorkstream.research.sources || []).length > 0 && (
                    <div className="mt-3 space-y-2">
                      {(selectedWorkstream.research.sources || []).slice(0, 3).map((source) => (
                        <a
                          key={`${source.url}-${source.title}`}
                          href={source.url}
                          target="_blank"
                          rel="noreferrer"
                          className="flex min-h-10 items-center justify-between gap-3 rounded-md bg-white px-3 text-sm font-medium text-slate-800 hover:text-orange-700"
                        >
                          <span className="min-w-0 truncate">{source.title || 'Открыть источник'}</span>
                          <ExternalLink className="h-4 w-4 shrink-0" />
                        </a>
                      ))}
                    </div>
                  )}
                  {selectedWorkstream.research.suggested_opener && (
                    <div className="mt-3 rounded-md bg-white p-3">
                      <div className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">Первый абзац письма</div>
                      <p className="mt-1 text-sm leading-6 text-slate-700">{selectedWorkstream.research.suggested_opener}</p>
                      {selectedWorkstream.research.opener_source_url ? (
                        <a
                          href={selectedWorkstream.research.opener_source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-2 inline-flex min-h-9 items-center gap-2 text-xs font-semibold text-sky-700 hover:text-sky-900"
                        >
                          Источник вступления
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      ) : (
                        <p className="mt-2 text-xs text-slate-500">Нейтральное вступление без персонального публичного сигнала.</p>
                      )}
                    </div>
                  )}
                  {(selectedWorkstream.research.limitations || []).length > 0 && (
                    <details className="mt-2">
                      <summary className="min-h-10 cursor-pointer py-2 text-sm font-semibold text-slate-600">Ограничения исследования</summary>
                      <ul className="space-y-1 text-sm text-slate-600">
                        {(selectedWorkstream.research.limitations || []).map((item) => <li key={item}>{item}</li>)}
                      </ul>
                    </details>
                  )}
                </section>
              )}

              <div className="space-y-2">
                {[
                  ['Найти контакт', availableContacts(selectedLead).length > 0],
                  ['Подготовить предложение', Boolean(selectedWorkstream.room_state?.url)],
                  ['Проверить сообщение', Boolean(selectedWorkstream.room_state?.url)],
                  ['Отправить вручную', Boolean(selectedWorkstream.last_contact_at)],
                  ['Зафиксировать ответ', ['replied', 'responded', 'converted', 'qualified'].includes(String(selectedWorkstream.status || ''))],
                ].map(([label, done], index) => (
                  <div key={String(label)} className="flex min-h-11 items-center gap-3 rounded-md bg-slate-50 px-3">
                    <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${done ? 'bg-emerald-100 text-emerald-700' : 'bg-white text-slate-500'}`}>
                      {done ? <Check className="h-3.5 w-3.5" /> : index + 1}
                    </span>
                    <span className={`text-sm ${done ? 'text-slate-500 line-through' : 'font-medium text-slate-800'}`}>{String(label)}</span>
                  </div>
                ))}
              </div>

              <div>
                <h3 className="text-sm font-semibold text-slate-950">Контакт получателя</h3>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {selectedLead.telegram_url && <button type="button" onClick={() => chooseChannel('telegram')} className="flex min-h-11 items-center gap-2 rounded-md bg-slate-100 px-3 text-sm font-medium hover:bg-slate-200"><MessageCircle className="h-4 w-4" />Telegram</button>}
                  {selectedLead.whatsapp_url && <button type="button" onClick={() => chooseChannel('whatsapp')} className="flex min-h-11 items-center gap-2 rounded-md bg-slate-100 px-3 text-sm font-medium hover:bg-slate-200"><MessageCircle className="h-4 w-4" />WhatsApp</button>}
                  {selectedLead.email && <button type="button" onClick={() => chooseChannel('email')} className="flex min-h-11 items-center gap-2 rounded-md bg-slate-100 px-3 text-sm font-medium hover:bg-slate-200"><Mail className="h-4 w-4" />{selectedLead.email}</button>}
                  {selectedLead.phone && <button type="button" onClick={() => chooseChannel('manual')} className="flex min-h-11 items-center gap-2 rounded-md bg-slate-100 px-3 text-sm font-medium hover:bg-slate-200"><Phone className="h-4 w-4" />{selectedLead.phone}</button>}
                </div>
                {!availableContacts(selectedLead).length && <p className="mt-2 text-sm text-amber-700">Сначала добавьте телефон, email, Telegram или WhatsApp получателя.</p>}
              </div>

              <div className="rounded-md bg-slate-50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-500">Отправитель</div>
                    <div className="mt-1 font-semibold text-slate-950">{selectedWorkstream.workstream_type === 'localos_sales' ? 'LocalOS' : selectedWorkstream.client_business_name || 'Выбранный клиент'}</div>
                  </div>
                  <Badge variant="outline" className={selectedWorkstream.workstream_type === 'localos_sales' && selectedWorkstream.selected_channel === 'telegram' && localosTelegramReady
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                    : 'border-amber-200 bg-amber-50 text-amber-800'}>
                    {selectedWorkstream.workstream_type === 'localos_sales' && selectedWorkstream.selected_channel === 'telegram' && localosTelegramReady
                      ? 'Подключён'
                      : 'Только ручная отправка'}
                  </Badge>
                </div>
                {selectedWorkstream.workstream_type === 'localos_sales' && selectedWorkstream.selected_channel === 'telegram' && !localosTelegramReady && (
                  <a
                    href={`/dashboard/settings/integrations?focus=telegram&return_to=${encodeURIComponent(`/dashboard/bazich?lead=${selectedLead.id}&workstream=${selectedWorkstream.id || ''}`)}`}
                    className="mt-3 inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-orange-700 hover:text-orange-800"
                  >
                    Подключить канал <ArrowRight className="h-4 w-4" />
                  </a>
                )}
              </div>

              <div className="space-y-2">
                <Button onClick={prepareRoom} disabled={busyAction === 'prepare-room'} className="w-full min-h-11 bg-orange-500 text-white hover:bg-orange-600">
                  {busyAction === 'prepare-room' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                  {selectedWorkstream.room_state?.url ? 'Обновить цифровую комнату' : 'Подготовить цифровую комнату'}
                </Button>
                {selectedWorkstream.room_state?.url && (
                  <a href={selectedWorkstream.room_state.url} target="_blank" rel="noreferrer" className="flex min-h-11 items-center justify-center gap-2 rounded-md bg-slate-100 text-sm font-semibold text-slate-800 hover:bg-slate-200">
                    Открыть комнату <ExternalLink className="h-4 w-4" />
                  </a>
                )}
                {selectedWorkstream.room_state?.url && (
                  <Button variant="outline" onClick={markSent} disabled={busyAction === 'mark-sent'} className="w-full min-h-11">
                    <Send className="mr-2 h-4 w-4" />Отметить ручную отправку
                  </Button>
                )}
              </div>

              {selectedWorkstream.workstream_type === 'client_partnership' && selectedLead.lead_kind !== 'both' && (
                <div className="rounded-md bg-sky-50 p-4">
                  <div className="font-semibold text-sky-950">Компания интересна и для LocalOS?</div>
                  <p className="mt-1 text-sm text-sky-800">Добавьте отдельный контур продаж. Клиент не увидит эту работу, а его партнёрская история останется без изменений.</p>
                  <Button variant="outline" onClick={addLocalosWorkstream} disabled={busyAction === 'add-localos'} className="mt-3 min-h-10 border-sky-200 bg-white text-sky-900">
                    <Plus className="mr-2 h-4 w-4" />Добавить в продажи LocalOS
                  </Button>
                </div>
              )}

              {notice && <div className="rounded-md bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div>}

              <details className="border-t border-slate-200 pt-4">
                <summary className="min-h-10 cursor-pointer text-sm font-semibold text-slate-600">Происхождение и технические данные</summary>
                <div className="mt-2 space-y-1 text-xs text-slate-500">
                  <p>{sourceLabel(selectedLead)}</p>
                  <p>ID компании: {selectedLead.id}</p>
                  <p>ID контура: {selectedWorkstream.id || 'legacy'}</p>
                </div>
              </details>
            </div>
          )}
        </SheetContent>
      </Sheet>

      <Sheet open={searchOpen} onOpenChange={setSearchOpen}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          <SheetHeader className="pr-8">
            <SheetTitle>Найти лидов</SheetTitle>
            <SheetDescription>Сначала выберите, для кого ищем компании. Это определит отправителя, предложение и цифровую комнату.</SheetDescription>
          </SheetHeader>

          <div className="mt-6 flex items-center gap-2 text-xs font-semibold text-slate-500">
            {[1, 2, 3].map((step) => (
              <React.Fragment key={step}>
                <span className={`flex h-7 w-7 items-center justify-center rounded-full ${searchStep >= step ? 'bg-slate-950 text-white' : 'bg-slate-100'}`}>{step}</span>
                {step < 3 && <span className={`h-px flex-1 ${searchStep > step ? 'bg-slate-950' : 'bg-slate-200'}`} />}
              </React.Fragment>
            ))}
          </div>

          {searchStep === 1 && (
            <div className="mt-6 space-y-3">
              <button type="button" onClick={() => setSearchScope('localos_sales')} className={`w-full rounded-md p-4 text-left ${searchScope === 'localos_sales' ? 'bg-sky-50 ring-2 ring-sky-300' : 'bg-slate-50 hover:bg-slate-100'}`}>
                <div className="flex items-center gap-3 font-semibold text-slate-950"><Building2 className="h-5 w-5 text-sky-600" />Для LocalOS</div>
                <p className="mt-1 pl-8 text-sm text-slate-600">Найти компании, которым LocalOS может помочь с картами, контентом и автоматизацией.</p>
              </button>
              <button type="button" onClick={() => setSearchScope('client_partnership')} className={`w-full rounded-md p-4 text-left ${searchScope === 'client_partnership' ? 'bg-violet-50 ring-2 ring-violet-300' : 'bg-slate-50 hover:bg-slate-100'}`}>
                <div className="flex items-center gap-3 font-semibold text-slate-950"><Users className="h-5 w-5 text-violet-600" />Для клиента</div>
                <p className="mt-1 pl-8 text-sm text-slate-600">Найти потенциальных партнёров рядом с точкой клиента.</p>
              </button>
              {searchScope === 'client_partnership' && (
                <select value={searchClientId} onChange={(event) => setSearchClientId(event.target.value)} className="h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm">
                  <option value="">Выберите клиента</option>
                  {businessOptions.map((business) => <option key={business.id} value={business.id}>{business.name}</option>)}
                </select>
              )}
              <Button onClick={() => setSearchStep(2)} disabled={searchScope === 'client_partnership' && !searchClientId} className="w-full min-h-11 bg-orange-500 text-white hover:bg-orange-600">
                Указать категорию и территорию <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          )}

          {searchStep === 2 && (
            <div className="mt-6 space-y-4">
              <div>
                <label className="text-sm font-semibold text-slate-800">Кого ищем</label>
                <Input value={searchCategory} onChange={(event) => setSearchCategory(event.target.value)} placeholder="Например: стоматологии, фитнес-клубы" className="mt-2 h-11" />
              </div>
              <div>
                <label className="text-sm font-semibold text-slate-800">Где ищем</label>
                <Input value={searchLocation} onChange={(event) => setSearchLocation(event.target.value)} placeholder="Город, район или адрес точки" className="mt-2 h-11" />
              </div>
              {searchScope === 'client_partnership' && (
                <div>
                  <label className="text-sm font-semibold text-slate-800">Радиус от точки клиента</label>
                  <div className="mt-2 grid grid-cols-4 gap-2">
                    {[['500', '500 м'], ['1000', '1 км'], ['3000', '3 км'], ['5000', '5 км']].map(([value, label]) => (
                      <button key={value} type="button" onClick={() => setSearchRadius(value)} className={`min-h-10 rounded-md text-sm font-semibold ${searchRadius === value ? 'bg-slate-950 text-white' : 'bg-slate-100 text-slate-700'}`}>{label}</button>
                    ))}
                  </div>
                </div>
              )}
              <details className="rounded-md bg-slate-50 p-3">
                <summary className="cursor-pointer text-sm font-semibold text-slate-700">Дополнительные настройки</summary>
                <select value={searchSource} onChange={(event) => setSearchSource(event.target.value)} className="mt-3 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm">
                  <option value="apify_yandex">Яндекс Карты</option>
                  <option value="apify_2gis">2ГИС</option>
                  <option value="apify_google">Google Maps</option>
                  <option value="apify_apple">Apple Maps</option>
                </select>
              </details>
              {searchError && <p className="text-sm text-red-600">{searchError}</p>}
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setSearchStep(1)} className="min-h-11">Назад</Button>
                <Button onClick={startSearch} disabled={searchBusy} className="min-h-11 flex-1 bg-orange-500 text-white hover:bg-orange-600">
                  {searchBusy ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}
                  {searchBusy ? 'Ищем компании…' : 'Найти компании'}
                </Button>
              </div>
            </div>
          )}

          {searchStep === 3 && (
            <div className="mt-6 space-y-4">
              <div>
                <h3 className="font-semibold text-slate-950">Проверьте найденные компании</h3>
                <p className="mt-1 text-sm text-slate-500">Выбранные компании попадут в {searchScope === 'localos_sales' ? 'продажи LocalOS' : `партнёры · ${selectedClient?.name || 'клиент'}`}.</p>
              </div>
              <div className="max-h-[52vh] divide-y divide-slate-200 overflow-y-auto">
                {searchResults.map((lead) => {
                  const resultId = lead.id || lead.google_id || lead.name || '';
                  const checked = selectedSearchIds.includes(resultId);
                  return (
                    <label key={resultId} className="flex cursor-pointer gap-3 py-3">
                      <Checkbox
                        checked={checked}
                        onCheckedChange={(nextChecked) => setSelectedSearchIds((current) => nextChecked
                          ? [...current, resultId]
                          : current.filter((item) => item !== resultId))}
                      />
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold text-slate-950">{lead.name || 'Компания'}</span>
                        <span className="mt-1 block truncate text-xs text-slate-500">{[lead.category, lead.address || lead.city].filter(Boolean).join(' · ')}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
              {searchError && <p className="text-sm text-red-600">{searchError}</p>}
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setSearchStep(2)} className="min-h-11">Изменить поиск</Button>
                <Button onClick={saveSearchResults} disabled={searchBusy || !selectedSearchIds.length} className="min-h-11 flex-1 bg-orange-500 text-white hover:bg-orange-600">
                  {searchBusy ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                  Добавить выбранные
                </Button>
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

export default AdminLeadRegistry;
