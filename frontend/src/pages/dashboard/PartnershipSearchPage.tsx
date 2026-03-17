import { useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { newAuth } from '@/lib/auth_new';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

type PartnershipLead = {
  id: string;
  name?: string;
  address?: string;
  city?: string;
  category?: string;
  source_url?: string;
  source?: string;
  source_kind?: string;
  source_provider?: string;
  external_place_id?: string;
  external_source_id?: string;
  dedupe_key?: string;
  lat?: number;
  lon?: number;
  matched_sources_json?: string[] | null;
  phone?: string;
  email?: string;
  website?: string;
  telegram_url?: string;
  whatsapp_url?: string;
  status?: string;
  partnership_stage?: string;
  pilot_cohort?: string;
  selected_channel?: string;
  updated_at?: string;
  parse_task_id?: string;
  parse_status?: string;
  parse_updated_at?: string;
  parse_retry_after?: string;
  parse_error?: string;
  next_best_action?: {
    code?: string;
    label?: string;
    hint?: string;
    priority?: 'low' | 'medium' | 'high';
  };
};

type PartnershipDraft = {
  id: string;
  lead_id: string;
  lead_name?: string;
  channel?: string;
  status?: string;
  generated_text?: string;
  edited_text?: string;
  approved_text?: string;
  updated_at?: string;
};

type PartnershipBatch = {
  id: string;
  status: string;
  batch_date?: string;
  created_at?: string;
  updated_at?: string;
  items?: Array<{
    id: string;
    lead_name?: string;
    delivery_status?: string;
    error_text?: string;
    channel?: string;
    latest_outcome?: string | null;
    latest_human_outcome?: string | null;
    latest_raw_reply?: string | null;
  }>;
};

type PartnershipReaction = {
  id: string;
  queue_id: string;
  lead_id: string;
  lead_name?: string;
  batch_id?: string;
  channel?: string;
  delivery_status?: string;
  raw_reply?: string | null;
  classified_outcome?: string | null;
  human_confirmed_outcome?: string | null;
};

type PartnershipLearningMetric = {
  capability: string;
  accepted_total: number;
  accepted_raw_total: number;
  accepted_edited_total: number;
  accepted_raw_pct: number;
  edited_before_accept_pct: number;
};

type PartnershipHealth = {
  openclaw?: {
    enabled?: boolean;
    caps_endpoint_configured?: boolean;
    token_configured?: boolean;
  };
  counts?: {
    leads_total?: number;
    drafts_total?: number;
    batches_total?: number;
    reactions_total?: number;
  };
};

type PartnershipFunnelStage = {
  key: string;
  label: string;
  count: number;
  conversion_from_prev_pct?: number;
};

type PartnershipFunnel = {
  window_days?: number;
  funnel?: PartnershipFunnelStage[];
  summary?: {
    import_to_sent_pct?: number;
    imported_count?: number;
    sent_count?: number;
  };
};

type PartnershipOutcomeSummary = {
  total_reactions?: number;
  positive_count?: number;
  question_count?: number;
  no_response_count?: number;
  hard_no_count?: number;
  positive_rate_pct?: number;
  question_rate_pct?: number;
  no_response_rate_pct?: number;
  hard_no_rate_pct?: number;
};

type PartnershipOutcomes = {
  window_days?: number;
  summary?: PartnershipOutcomeSummary;
  by_channel?: Array<{
    channel?: string;
    total?: number;
    positive_count?: number;
    question_count?: number;
    no_response_count?: number;
    hard_no_count?: number;
  }>;
};

type PartnershipSourceQualityItem = {
  source_kind?: string;
  source_provider?: string;
  leads_total?: number;
  audited_count?: number;
  matched_count?: number;
  draft_count?: number;
  sent_count?: number;
  positive_count?: number;
  audit_rate_pct?: number;
  match_rate_pct?: number;
  draft_rate_pct?: number;
  sent_rate_pct?: number;
  positive_rate_pct?: number;
  lead_to_positive_pct?: number;
};

type PartnershipSourceQuality = {
  window_days?: number;
  items?: PartnershipSourceQualityItem[];
};

type PartnershipBlocker = {
  key: string;
  label: string;
  count: number;
  severity?: 'info' | 'warning' | 'danger';
  hint?: string;
};

type PartnershipBlockers = {
  window_days?: number;
  summary?: Record<string, number>;
  blockers?: PartnershipBlocker[];
};

type PartnershipRalphLoop = {
  window_days?: number;
  pilot_cohort?: string;
  summary?: {
    leads_total?: number;
    parsed_completed_count?: number;
    audited_count?: number;
    matched_count?: number;
    drafts_total?: number;
    drafts_approved_count?: number;
    sent_total?: number;
    positive_count?: number;
    question_count?: number;
    no_response_count?: number;
    hard_no_count?: number;
    positive_rate_pct?: number;
  };
  baseline?: {
    window_days?: number;
    sent_total?: number;
    positive_count?: number;
    positive_rate_pct?: number;
    deltas?: {
      sent_total?: number;
      positive_count?: number;
      positive_rate_pct?: number;
    };
  };
  top_channels?: Array<{
    channel?: string;
    total?: number;
    positive_count?: number;
    positive_rate_pct?: number;
  }>;
  learning?: Array<{
    capability?: string;
    accepted_total?: number;
    accepted_edited_total?: number;
    edited_before_accept_pct?: number;
    prompt_key?: string;
    prompt_version?: string;
  }>;
  prompt_performance?: Array<{
    prompt_key?: string;
    prompt_version?: string;
    drafts_total?: number;
    approved_total?: number;
    edited_approved_total?: number;
    edited_before_accept_pct?: number;
    sent_total?: number;
    positive_count?: number;
    positive_rate_pct?: number;
  }>;
  recommended_prompt_version?: {
    prompt_key?: string;
    prompt_version?: string;
    drafts_total?: number;
    approved_total?: number;
    edited_approved_total?: number;
    edited_before_accept_pct?: number;
    sent_total?: number;
    positive_count?: number;
    positive_rate_pct?: number;
  } | null;
  blockers?: string[];
  recommendations?: string[];
  edit_insights?: {
    edited_accepts_total?: number;
    avg_generated_len?: number;
    avg_final_len?: number;
    expanded_count?: number;
    shortened_count?: number;
    unchanged_count?: number;
  };
};

const STAGE_OPTIONS = [
  { value: 'all', label: 'Все этапы' },
  { value: 'imported', label: 'Импортировано' },
  { value: 'audited', label: 'Аудит готов' },
  { value: 'matched', label: 'Матчинг готов' },
  { value: 'proposal_draft_ready', label: 'Черновик оффера готов' },
];
const BULK_STAGE_OPTIONS = [
  { value: 'imported', label: 'Импортировано' },
  { value: 'audited', label: 'Аудит готов' },
  { value: 'matched', label: 'Матчинг готов' },
  { value: 'proposal_draft_ready', label: 'Черновик оффера готов' },
  { value: 'selected_for_outreach', label: 'Выбрано для контакта' },
  { value: 'channel_selected', label: 'Канал выбран' },
  { value: 'approved_for_send', label: 'Готово к отправке' },
  { value: 'sent', label: 'Отправлено' },
];
const CHANNEL_OPTIONS = [
  { value: 'telegram', label: 'Telegram' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'email', label: 'Email' },
  { value: 'manual', label: 'Вручную' },
];
const OUTCOME_OPTIONS = ['positive', 'question', 'no_response', 'hard_no'] as const;
const LEAD_VIEW_OPTIONS = [
  { value: 'all', label: 'Все лиды' },
  { value: 'requires_action', label: 'Требуют действия' },
  { value: 'ready_next_step', label: 'Готовы к следующему шагу' },
  { value: 'parsed', label: 'Парсинг завершён' },
  { value: 'with_contacts', label: 'С контактами' },
] as const;
const DRAFT_VIEW_OPTIONS = [
  { value: 'all', label: 'Все черновики' },
  { value: 'needs_approval', label: 'Ждут утверждения' },
  { value: 'approved', label: 'Утверждённые' },
] as const;
const QUEUE_VIEW_OPTIONS = [
  { value: 'all', label: 'Вся очередь' },
  { value: 'needs_approval', label: 'Batch ждёт утверждения' },
  { value: 'waiting_delivery', label: 'Ждут доставки' },
  { value: 'waiting_outcome', label: 'Ждут outcome' },
  { value: 'failed', label: 'С ошибкой доставки' },
] as const;
const REACTION_VIEW_OPTIONS = [
  { value: 'all', label: 'Все реакции' },
  { value: 'needs_confirmation', label: 'Требуют подтверждения' },
  { value: 'positive', label: 'Positive' },
  { value: 'question', label: 'Question' },
  { value: 'no_response', label: 'No response' },
  { value: 'hard_no', label: 'Hard no' },
] as const;
const PILOT_COHORT_OPTIONS = [
  { value: 'all', label: 'Все когорты' },
  { value: 'pilot', label: 'Пилот' },
  { value: 'backlog', label: 'Backlog' },
  { value: 'watchlist', label: 'Watchlist' },
] as const;

export const PartnershipSearchPage: React.FC = () => {
  const { currentBusinessId } = useOutletContext<any>();
  const [loading, setLoading] = useState(false);
  const [linksText, setLinksText] = useState('');
  const [importFileName, setImportFileName] = useState('');
  const [importFileContent, setImportFileContent] = useState('');
  const [importFileFormat, setImportFileFormat] = useState<'csv' | 'json' | 'jsonl' | ''>('');
  const [importFileErrors, setImportFileErrors] = useState<Array<{ row?: number; error?: string }>>([]);
  const [geoCity, setGeoCity] = useState('');
  const [geoCategory, setGeoCategory] = useState('');
  const [geoQuery, setGeoQuery] = useState('');
  const [geoProvider, setGeoProvider] = useState<'google' | 'yandex' | 'both'>('google');
  const [geoRadiusKm, setGeoRadiusKm] = useState('5');
  const [geoLimit, setGeoLimit] = useState('25');
  const [stage, setStage] = useState('all');
  const [pilotCohort, setPilotCohort] = useState<(typeof PILOT_COHORT_OPTIONS)[number]['value']>('all');
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<PartnershipLead[]>([]);
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [selectedLeadIds, setSelectedLeadIds] = useState<string[]>([]);
  const [leadView, setLeadView] = useState<(typeof LEAD_VIEW_OPTIONS)[number]['value']>('all');
  const [bulkStage, setBulkStage] = useState('');
  const [bulkChannel, setBulkChannel] = useState('');
  const [bulkPilotCohort, setBulkPilotCohort] = useState('');
  const [auditData, setAuditData] = useState<any>(null);
  const [matchData, setMatchData] = useState<any>(null);
  const [draftText, setDraftText] = useState('');
  const [drafts, setDrafts] = useState<PartnershipDraft[]>([]);
  const [selectedDraftIds, setSelectedDraftIds] = useState<string[]>([]);
  const [draftView, setDraftView] = useState<(typeof DRAFT_VIEW_OPTIONS)[number]['value']>('all');
  const [batches, setBatches] = useState<PartnershipBatch[]>([]);
  const [selectedQueueIds, setSelectedQueueIds] = useState<string[]>([]);
  const [bulkQueueStatus, setBulkQueueStatus] = useState('');
  const [queueView, setQueueView] = useState<(typeof QUEUE_VIEW_OPTIONS)[number]['value']>('all');
  const [queueReadyDrafts, setQueueReadyDrafts] = useState<PartnershipDraft[]>([]);
  const [reactions, setReactions] = useState<PartnershipReaction[]>([]);
  const [reactionView, setReactionView] = useState<(typeof REACTION_VIEW_OPTIONS)[number]['value']>('all');
  const [sendQueueBusy, setSendQueueBusy] = useState<Record<string, string>>({});
  const [reactionBusy, setReactionBusy] = useState<Record<string, string>>({});
  const [learningMetrics, setLearningMetrics] = useState<PartnershipLearningMetric[]>([]);
  const [health, setHealth] = useState<PartnershipHealth | null>(null);
  const [funnel, setFunnel] = useState<PartnershipFunnel | null>(null);
  const [blockers, setBlockers] = useState<PartnershipBlockers | null>(null);
  const [outcomes, setOutcomes] = useState<PartnershipOutcomes | null>(null);
  const [sourceQuality, setSourceQuality] = useState<PartnershipSourceQuality | null>(null);
  const [ralphLoop, setRalphLoop] = useState<PartnershipRalphLoop | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [leadEdit, setLeadEdit] = useState<{
    name: string;
    city: string;
    category: string;
    address: string;
    phone: string;
    email: string;
    website: string;
    telegram_url: string;
    whatsapp_url: string;
  }>({
    name: '',
    city: '',
    category: '',
    address: '',
    phone: '',
    email: '',
    website: '',
    telegram_url: '',
    whatsapp_url: '',
  });

  const selectedLead = useMemo(
    () => items.find((item) => item.id === selectedLeadId) || null,
    [items, selectedLeadId]
  );

  const visibleLeads = useMemo(() => {
    return items.filter((item) => {
      const parseStatus = String(item.parse_status || '').toLowerCase();
      const nextCode = String(item.next_best_action?.code || '').toLowerCase();
      const hasContacts = Boolean(item.phone || item.email || item.telegram_url || item.whatsapp_url || item.website);
      if (leadView === 'requires_action') {
        return ['captcha', 'error'].includes(parseStatus) || ['parse_captcha', 'parse_error', 'fill_contacts'].includes(nextCode);
      }
      if (leadView === 'ready_next_step') {
        return ['parse', 'match', 'draft', 'approve_draft', 'queue', 'approve_batch', 'confirm_outcome'].includes(nextCode);
      }
      if (leadView === 'parsed') {
        return parseStatus === 'completed';
      }
      if (leadView === 'with_contacts') {
        return hasContacts;
      }
      return true;
    });
  }, [items, leadView]);

  const visibleDrafts = useMemo(() => {
    return drafts.filter((draft) => {
      const status = String(draft.status || '').toLowerCase();
      if (draftView === 'needs_approval') return !status || status === 'generated' || status === 'draft';
      if (draftView === 'approved') return status === 'approved';
      return true;
    });
  }, [drafts, draftView]);

  const allQueueItems = useMemo(
    () => batches.flatMap((batch) => (batch.items || []).map((item) => ({ ...item, batch_status: batch.status, batch_id: batch.id }))),
    [batches]
  );

  const visibleBatches = useMemo(() => {
    return batches
      .map((batch) => {
        const items = (batch.items || []).filter((item) => {
          const delivery = String(item.delivery_status || '').toLowerCase();
          const outcome = String(item.latest_human_outcome || item.latest_outcome || '').toLowerCase();
          if (queueView === 'needs_approval') return String(batch.status || '').toLowerCase() === 'draft';
          if (queueView === 'waiting_delivery') return ['queued', 'pending', 'created', 'draft', ''].includes(delivery);
          if (queueView === 'waiting_outcome') return delivery === 'sent' && !outcome;
          if (queueView === 'failed') return delivery === 'failed';
          return true;
        });
        return { ...batch, items };
      })
      .filter((batch) => queueView === 'needs_approval' ? String(batch.status || '').toLowerCase() === 'draft' : (batch.items || []).length > 0);
  }, [batches, queueView]);

  const visibleReactions = useMemo(() => {
    return reactions.filter((reaction) => {
      const finalOutcome = String(reaction.human_confirmed_outcome || reaction.classified_outcome || '').toLowerCase();
      if (reactionView === 'needs_confirmation') {
        return !reaction.human_confirmed_outcome;
      }
      if (reactionView !== 'all') {
        return finalOutcome === reactionView;
      }
      return true;
    });
  }, [reactions, reactionView]);

  const pilotSummary = useMemo(() => {
    const total = items.length;
    const parsed = items.filter((item) => String(item.parse_status || '').toLowerCase() === 'completed').length;
    const readyForDraft = items.filter((item) => String(item.next_best_action?.code || '') === 'draft').length;
    const waitingApproval = drafts.filter((draft) => {
      const status = String(draft.status || '').toLowerCase();
      return !status || status === 'generated' || status === 'draft';
    }).length;
    const waitingOutcome = allQueueItems.filter((item) => {
      const delivery = String(item.delivery_status || '').toLowerCase();
      return delivery === 'sent' && !(item.latest_human_outcome || item.latest_outcome);
    }).length;
    const acceptance = Number(outcomes?.summary?.positive_rate_pct || 0);
    return { total, parsed, readyForDraft, waitingApproval, waitingOutcome, acceptance };
  }, [items, drafts, allQueueItems, outcomes]);

  useEffect(() => {
    if (!selectedLead) {
      setLeadEdit({
        name: '',
        city: '',
        category: '',
        address: '',
        phone: '',
        email: '',
        website: '',
        telegram_url: '',
        whatsapp_url: '',
      });
      return;
    }
    setLeadEdit({
      name: selectedLead.name || '',
      city: selectedLead.city || '',
      category: selectedLead.category || '',
      address: selectedLead.address || '',
      phone: selectedLead.phone || '',
      email: selectedLead.email || '',
      website: selectedLead.website || '',
      telegram_url: selectedLead.telegram_url || '',
      whatsapp_url: selectedLead.whatsapp_url || '',
    });
  }, [selectedLeadId, selectedLead, items]);

  const loadLeads = async () => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      params.set('business_id', currentBusinessId);
      if (stage !== 'all') params.set('stage', stage);
      if (pilotCohort !== 'all') params.set('pilot_cohort', pilotCohort);
      if (query.trim()) params.set('q', query.trim());
      const data = await newAuth.makeRequest(`/partnership/leads?${params.toString()}`, { method: 'GET' });
      setItems(Array.isArray(data.items) ? data.items : []);
      setSelectedLeadIds((prev) => prev.filter((id) => (data.items || []).some((x: any) => x.id === id)));
      if (selectedLeadId && !(data.items || []).some((x: any) => x.id === selectedLeadId)) {
        setSelectedLeadId(null);
      }
    } catch (e: any) {
      setError(e.message || 'Не удалось загрузить список партнёров');
    } finally {
      setLoading(false);
    }
  };

  const loadRalphLoop = async () => {
    if (!currentBusinessId) return;
    try {
      const params = new URLSearchParams();
      params.set('business_id', currentBusinessId);
      params.set('window_days', '7');
      if (pilotCohort !== 'all') params.set('pilot_cohort', pilotCohort);
      const data = await newAuth.makeRequest(`/partnership/ralph-loop-summary?${params.toString()}`, {
        method: 'GET',
      });
      setRalphLoop(data || null);
    } catch {
      setRalphLoop(null);
    }
  };

  const loadDrafts = async () => {
    if (!currentBusinessId) return;
    const data = await newAuth.makeRequest(`/partnership/drafts?business_id=${encodeURIComponent(currentBusinessId)}`, {
      method: 'GET',
    });
    setDrafts(Array.isArray(data.drafts) ? data.drafts : []);
    setSelectedDraftIds((prev) => prev.filter((id) => (data.drafts || []).some((x: any) => x.id === id)));
  };

  const loadBatches = async () => {
    if (!currentBusinessId) return;
    const data = await newAuth.makeRequest(`/partnership/send-batches?business_id=${encodeURIComponent(currentBusinessId)}`, {
      method: 'GET',
    });
    setBatches(Array.isArray(data.batches) ? data.batches : []);
    const queueIds = (Array.isArray(data.batches) ? data.batches : [])
      .flatMap((batch: any) => (Array.isArray(batch.items) ? batch.items : []))
      .map((item: any) => item.id);
    setSelectedQueueIds((prev) => prev.filter((id) => queueIds.includes(id)));
    setQueueReadyDrafts(Array.isArray(data.ready_drafts) ? data.ready_drafts : []);
    setReactions(Array.isArray(data.reactions) ? data.reactions : []);
  };

  const loadLearningMetrics = async () => {
    try {
      const data = await newAuth.makeRequest('/admin/ai/learning-metrics?intent=partnership_outreach', {
        method: 'GET',
      });
      setLearningMetrics(Array.isArray(data.items) ? data.items : []);
    } catch {
      setLearningMetrics([]);
    }
  };

  const loadHealth = async () => {
    if (!currentBusinessId) return;
    try {
      const data = await newAuth.makeRequest(`/partnership/health?business_id=${encodeURIComponent(currentBusinessId)}`, {
        method: 'GET',
      });
      setHealth(data || null);
    } catch {
      setHealth(null);
    }
  };

  const loadFunnel = async () => {
    if (!currentBusinessId) return;
    try {
      const data = await newAuth.makeRequest(
        `/partnership/funnel?business_id=${encodeURIComponent(currentBusinessId)}&window_days=30`,
        { method: 'GET' }
      );
      setFunnel(data || null);
    } catch {
      setFunnel(null);
    }
  };

  const loadBlockers = async () => {
    if (!currentBusinessId) return;
    try {
      const data = await newAuth.makeRequest(
        `/partnership/blockers-summary?business_id=${encodeURIComponent(currentBusinessId)}&window_days=30`,
        { method: 'GET' }
      );
      setBlockers(data || null);
    } catch {
      setBlockers(null);
    }
  };

  const loadOutcomes = async () => {
    if (!currentBusinessId) return;
    try {
      const data = await newAuth.makeRequest(
        `/partnership/outcomes-summary?business_id=${encodeURIComponent(currentBusinessId)}&window_days=30`,
        { method: 'GET' }
      );
      setOutcomes(data || null);
    } catch {
      setOutcomes(null);
    }
  };

  const loadSourceQuality = async () => {
    if (!currentBusinessId) return;
    try {
      const data = await newAuth.makeRequest(
        `/partnership/source-quality-summary?business_id=${encodeURIComponent(currentBusinessId)}&window_days=30`,
        { method: 'GET' }
      );
      setSourceQuality(data || null);
    } catch {
      setSourceQuality(null);
    }
  };

  useEffect(() => {
    void loadLeads();
    void loadDrafts();
    void loadBatches();
    void loadLearningMetrics();
    void loadHealth();
    void loadFunnel();
    void loadBlockers();
    void loadOutcomes();
    void loadSourceQuality();
    void loadRalphLoop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentBusinessId, stage, pilotCohort]);

  const handleImportLinks = async () => {
    if (!currentBusinessId) return;
    const links = linksText
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean);
    if (links.length === 0) {
      setError('Добавьте минимум одну ссылку');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const data = await newAuth.makeRequest('/partnership/leads/import-links', {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId, links }),
      });
      setMessage(`Импортировано: ${data.imported_count || 0}, пропущено: ${data.skipped_count || 0}`);
      setLinksText('');
      await loadLeads();
      await loadDrafts();
      await loadBatches();
      await loadHealth();
      await loadFunnel();
      await loadOutcomes();
      await loadSourceQuality();
    } catch (e: any) {
      setError(e.message || 'Не удалось импортировать ссылки');
    } finally {
      setLoading(false);
    }
  };

  const handleImportFilePick = async (file?: File | null) => {
    if (!file) return;
    const name = file.name || 'partners-import';
    const lower = name.toLowerCase();
    const format: 'csv' | 'json' | 'jsonl' | '' =
      lower.endsWith('.csv') ? 'csv' : lower.endsWith('.jsonl') ? 'jsonl' : lower.endsWith('.json') ? 'json' : '';
    const text = await file.text();
    setImportFileName(name);
    setImportFileFormat(format);
    setImportFileContent(text);
    setImportFileErrors([]);
    setMessage(`Файл загружен: ${name}`);
  };

  const handleImportFile = async () => {
    if (!currentBusinessId) return;
    if (!importFileContent.trim()) {
      setError('Выберите CSV/JSON файл для импорта');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const data = await newAuth.makeRequest('/partnership/leads/import-file', {
        method: 'POST',
        body: JSON.stringify({
          business_id: currentBusinessId,
          filename: importFileName || 'partners-import',
          format: importFileFormat || undefined,
          content: importFileContent,
        }),
      });
      setImportFileErrors(Array.isArray(data.errors) ? data.errors : []);
      setMessage(
        `Импорт файла: ${data.imported_count || 0} добавлено, ${data.skipped_count || 0} пропущено, строк: ${data.rows_total || 0}`
      );
      await loadLeads();
      await loadDrafts();
      await loadBatches();
      await loadHealth();
      await loadFunnel();
      await loadOutcomes();
      await loadSourceQuality();
    } catch (e: any) {
      setError(e.message || 'Не удалось импортировать файл партнёров');
    } finally {
      setLoading(false);
    }
  };

  const handleGeoSearch = async () => {
    if (!currentBusinessId) return;
    const city = geoCity.trim();
    const category = geoCategory.trim();
    const q = geoQuery.trim();
    const radiusKm = Number.parseInt(geoRadiusKm, 10);
    const limit = Number.parseInt(geoLimit, 10);
    if (!city && !q) {
      setError('Укажите город или поисковый запрос для гео-поиска');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const data = await newAuth.makeRequest('/partnership/geo-search', {
        method: 'POST',
        body: JSON.stringify({
          business_id: currentBusinessId,
          provider: geoProvider,
          city,
          category,
          query: q,
          radius_km: Number.isFinite(radiusKm) ? radiusKm : 5,
          limit: Number.isFinite(limit) ? limit : 25,
        }),
      });
      const providerLabel =
        geoProvider === 'google' ? 'Google' : geoProvider === 'yandex' ? 'Яндекс' : 'Google + Яндекс';
      const baseMsg = `${providerLabel}: импортировано ${data.imported_count || 0}, пропущено ${data.skipped_count || 0}, найдено источником ${data.source_total || 0}`;
      setMessage(data.warning ? `${baseMsg}. ${data.warning}` : baseMsg);
      await loadLeads();
      await loadDrafts();
      await loadBatches();
      await loadHealth();
      await loadFunnel();
    } catch (e: any) {
      setError(e.message || 'Не удалось выполнить гео-поиск');
    } finally {
      setLoading(false);
    }
  };

  const runAudit = async (leadId: string) => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      setMatchData(null);
      setDraftText('');
      const lead = items.find((x) => x.id === leadId);
      const parseStatus = String(lead?.parse_status || '').toLowerCase();
      if (['pending', 'processing', 'captcha'].includes(parseStatus)) {
        throw new Error('Парсинг ещё не завершён. Дождитесь статуса completed/error и обновите список.');
      }
      const data = await newAuth.makeRequest(`/partnership/leads/${leadId}/audit`, {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId }),
      });
      setAuditData(data.snapshot || null);
      setSelectedLeadId(leadId);
      await loadLeads();
      await loadDrafts();
      await loadBatches();
      await loadFunnel();
      await loadOutcomes();
    } catch (e: any) {
      setError(e.message || 'Не удалось выполнить аудит');
    } finally {
      setLoading(false);
    }
  };

  const runParse = async (leadId: string) => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await newAuth.makeRequest(`/partnership/leads/${leadId}/parse`, {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId }),
      });
      const task = data?.parse_task;
      if (task?.id) {
        setMessage(`Парсинг запущен: ${task.id} (${task.status || 'pending'})`);
      } else {
        setMessage('Парсинг запрошен');
      }
      await loadLeads();
    } catch (e: any) {
      setError(e.message || 'Не удалось запустить парсинг');
    } finally {
      setLoading(false);
    }
  };

  const runMatch = async (leadId: string) => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      setDraftText('');
      const data = await newAuth.makeRequest(`/partnership/leads/${leadId}/match`, {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId }),
      });
      setMatchData(data.result || null);
      setSelectedLeadId(leadId);
      await loadLeads();
      await loadDrafts();
      await loadBatches();
      await loadFunnel();
      await loadOutcomes();
    } catch (e: any) {
      setError(e.message || 'Не удалось выполнить матчинг');
    } finally {
      setLoading(false);
    }
  };

  const enrichContacts = async (leadId: string) => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      await newAuth.makeRequest(`/partnership/leads/${leadId}/enrich-contacts`, {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId }),
      });
      setMessage('Контакты лида обновлены');
      await loadLeads();
    } catch (e: any) {
      setError(e.message || 'Не удалось обогатить контакты');
    } finally {
      setLoading(false);
    }
  };

  const runDraft = async (leadId: string) => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await newAuth.makeRequest(`/partnership/leads/${leadId}/draft-offer`, {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId, channel: 'telegram', tone: 'профессиональный' }),
      });
      setDraftText(data.text || '');
      setSelectedLeadId(leadId);
      await loadLeads();
      await loadDrafts();
      await loadBatches();
      await loadFunnel();
      await loadOutcomes();
    } catch (e: any) {
      setError(e.message || 'Не удалось сгенерировать первое письмо');
    } finally {
      setLoading(false);
    }
  };

  const saveLeadContacts = async () => {
    if (!currentBusinessId || !selectedLeadId) return;
    try {
      setLoading(true);
      setError(null);
      await newAuth.makeRequest(`/partnership/leads/${selectedLeadId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          business_id: currentBusinessId,
          ...leadEdit,
        }),
      });
      setMessage('Данные лида сохранены');
      await loadLeads();
    } catch (e: any) {
      setError(e.message || 'Не удалось сохранить данные лида');
    } finally {
      setLoading(false);
    }
  };

  const toggleLeadSelection = (leadId: string, checked: boolean) => {
    setSelectedLeadIds((prev) => {
      if (checked) return prev.includes(leadId) ? prev : [...prev, leadId];
      return prev.filter((id) => id !== leadId);
    });
  };

  const toggleAllLeadSelection = (checked: boolean) => {
    setSelectedLeadIds(checked ? visibleLeads.map((item) => item.id) : []);
  };

  const applyBulkUpdate = async () => {
    if (!currentBusinessId || selectedLeadIds.length === 0) return;
    if (!bulkStage && !bulkChannel) {
      setError('Выберите этап или канал для массового применения');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const data = await newAuth.makeRequest('/partnership/leads/bulk-update', {
        method: 'POST',
          body: JSON.stringify({
            business_id: currentBusinessId,
            lead_ids: selectedLeadIds,
            partnership_stage: bulkStage || undefined,
            selected_channel: bulkChannel || undefined,
            pilot_cohort: bulkPilotCohort || undefined,
          }),
        });
      setMessage(`Обновлено лидов: ${data.updated_count || 0}`);
      setSelectedLeadIds([]);
      await loadLeads();
    } catch (e: any) {
      setError(e.message || 'Не удалось массово обновить лиды');
    } finally {
      setLoading(false);
    }
  };

  const bulkDeleteLeads = async () => {
    if (!currentBusinessId || selectedLeadIds.length === 0) return;
    const ok = window.confirm(`Удалить выбранные лиды (${selectedLeadIds.length})?`);
    if (!ok) return;
    const deletingIds = new Set(selectedLeadIds);
    try {
      setLoading(true);
      setError(null);
      const data = await newAuth.makeRequest('/partnership/leads/bulk-delete', {
        method: 'POST',
        body: JSON.stringify({
          business_id: currentBusinessId,
          lead_ids: selectedLeadIds,
        }),
      });
      if (selectedLeadId && deletingIds.has(selectedLeadId)) {
        setSelectedLeadId(null);
        setAuditData(null);
        setMatchData(null);
        setDraftText('');
      }
      setMessage(`Удалено лидов: ${data.deleted_count || 0}`);
      setSelectedLeadIds([]);
      await loadLeads();
      await loadDrafts();
      await loadBatches();
    } catch (e: any) {
      setError(e.message || 'Не удалось удалить выбранные лиды');
    } finally {
      setLoading(false);
    }
  };

  const bulkEnrichContacts = async () => {
    if (!currentBusinessId || selectedLeadIds.length === 0) return;
    try {
      setLoading(true);
      setError(null);
      const data = await newAuth.makeRequest('/partnership/leads/bulk-enrich-contacts', {
        method: 'POST',
        body: JSON.stringify({
          business_id: currentBusinessId,
          lead_ids: selectedLeadIds,
        }),
      });
      setMessage(
        `Контакты обогащены: ${data.updated_count || 0}, пропущено: ${data.skipped_count || 0}${
          Array.isArray(data.errors) && data.errors.length ? `, ошибок: ${data.errors.length}` : ''
        }`
      );
      await loadLeads();
    } catch (e: any) {
      setError(e.message || 'Не удалось массово обогатить контакты');
    } finally {
      setLoading(false);
    }
  };

  const deleteLead = async (leadId: string) => {
    if (!currentBusinessId) return;
    const ok = window.confirm('Удалить этого партнёра из списка?');
    if (!ok) return;
    try {
      setLoading(true);
      setError(null);
      await newAuth.makeRequest(
        `/partnership/leads/${leadId}?business_id=${encodeURIComponent(currentBusinessId)}`,
        { method: 'DELETE' }
      );
      if (selectedLeadId === leadId) {
        setSelectedLeadId(null);
        setAuditData(null);
        setMatchData(null);
        setDraftText('');
      }
      setMessage('Лид удалён');
      await loadLeads();
      await loadDrafts();
      await loadBatches();
    } catch (e: any) {
      setError(e.message || 'Не удалось удалить лида');
    } finally {
      setLoading(false);
    }
  };

  const approveDraft = async (draftId: string, text: string) => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      await newAuth.makeRequest(`/partnership/drafts/${draftId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId, approved_text: text }),
      });
      setMessage('Черновик утверждён');
      await loadDrafts();
      await loadBatches();
      await loadLeads();
      await loadFunnel();
      await loadOutcomes();
    } catch (e: any) {
      setError(e.message || 'Не удалось утвердить черновик');
    } finally {
      setLoading(false);
    }
  };

  const toggleDraftSelection = (draftId: string, checked: boolean) => {
    setSelectedDraftIds((prev) => {
      if (checked) return prev.includes(draftId) ? prev : [...prev, draftId];
      return prev.filter((id) => id !== draftId);
    });
  };

  const toggleAllDraftSelection = (checked: boolean) => {
    setSelectedDraftIds(checked ? visibleDrafts.map((draft) => draft.id) : []);
  };

  const bulkApproveDrafts = async () => {
    if (!currentBusinessId || selectedDraftIds.length === 0) return;
    try {
      setLoading(true);
      setError(null);
      await Promise.all(
        selectedDraftIds.map((draftId) => {
          const draft = drafts.find((item) => item.id === draftId);
          const text = draft?.approved_text || draft?.edited_text || draft?.generated_text || '';
          return newAuth.makeRequest(`/partnership/drafts/${draftId}/approve`, {
            method: 'POST',
            body: JSON.stringify({ business_id: currentBusinessId, approved_text: text }),
          });
        })
      );
      setMessage(`Утверждено черновиков: ${selectedDraftIds.length}`);
      setSelectedDraftIds([]);
      await loadDrafts();
      await loadBatches();
      await loadLeads();
    } catch (e: any) {
      setError(e.message || 'Не удалось массово утвердить черновики');
    } finally {
      setLoading(false);
    }
  };

  const bulkDeleteDrafts = async () => {
    if (!currentBusinessId || selectedDraftIds.length === 0) return;
    const ok = window.confirm(`Удалить выбранные черновики (${selectedDraftIds.length})?`);
    if (!ok) return;
    try {
      setLoading(true);
      setError(null);
      await Promise.all(
        selectedDraftIds.map((draftId) =>
          newAuth.makeRequest(`/partnership/drafts/${draftId}?business_id=${encodeURIComponent(currentBusinessId)}`, {
            method: 'DELETE',
          })
        )
      );
      setMessage(`Удалено черновиков: ${selectedDraftIds.length}`);
      setSelectedDraftIds([]);
      await loadDrafts();
      await loadBatches();
    } catch (e: any) {
      setError(e.message || 'Не удалось массово удалить черновики');
    } finally {
      setLoading(false);
    }
  };

  const createBatch = async () => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await newAuth.makeRequest('/partnership/send-batches', {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId }),
      });
      if (data.batch?.id) {
        setMessage(`Batch создан: ${data.batch.id}`);
      } else {
        setMessage('Batch создан');
      }
      await loadBatches();
      await loadLeads();
      await loadFunnel();
      await loadOutcomes();
    } catch (e: any) {
      setError(e.message || 'Не удалось создать batch');
    } finally {
      setLoading(false);
    }
  };

  const approveBatch = async (batchId: string) => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      await newAuth.makeRequest(`/partnership/send-batches/${batchId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId }),
      });
      setMessage(`Batch утверждён: ${batchId}`);
      await loadBatches();
      await loadLeads();
      await loadFunnel();
      await loadOutcomes();
    } catch (e: any) {
      setError(e.message || 'Не удалось утвердить batch');
    } finally {
      setLoading(false);
    }
  };

  const toggleQueueSelection = (queueId: string, checked: boolean) => {
    setSelectedQueueIds((prev) => {
      if (checked) return prev.includes(queueId) ? prev : [...prev, queueId];
      return prev.filter((id) => id !== queueId);
    });
  };

  const toggleAllQueueSelection = (checked: boolean) => {
    const ids = visibleBatches.flatMap((batch) => (batch.items || []).map((item) => item.id));
    setSelectedQueueIds(checked ? ids : []);
  };

  const bulkUpdateQueueDelivery = async () => {
    if (!currentBusinessId || selectedQueueIds.length === 0) return;
    if (!bulkQueueStatus) {
      setError('Выберите delivery-статус для очереди');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      await Promise.all(
        selectedQueueIds.map((queueId) =>
          newAuth.makeRequest(`/partnership/send-queue/${queueId}/delivery`, {
            method: 'POST',
            body: JSON.stringify({ business_id: currentBusinessId, delivery_status: bulkQueueStatus }),
          })
        )
      );
      setMessage(`Обновлено queue-элементов: ${selectedQueueIds.length}`);
      setSelectedQueueIds([]);
      await loadBatches();
      await loadLeads();
      await loadOutcomes();
    } catch (e: any) {
      setError(e.message || 'Не удалось обновить очередь');
    } finally {
      setLoading(false);
    }
  };

  const bulkDeleteQueueItems = async () => {
    if (!currentBusinessId || selectedQueueIds.length === 0) return;
    const ok = window.confirm(`Удалить выбранные queue-элементы (${selectedQueueIds.length})?`);
    if (!ok) return;
    try {
      setLoading(true);
      setError(null);
      await Promise.all(
        selectedQueueIds.map((queueId) =>
          newAuth.makeRequest(`/partnership/send-queue/${queueId}?business_id=${encodeURIComponent(currentBusinessId)}`, {
            method: 'DELETE',
          })
        )
      );
      setMessage(`Удалено queue-элементов: ${selectedQueueIds.length}`);
      setSelectedQueueIds([]);
      await loadBatches();
      await loadLeads();
    } catch (e: any) {
      setError(e.message || 'Не удалось удалить queue-элементы');
    } finally {
      setLoading(false);
    }
  };

  const recordReaction = async (
    queueId: string,
    outcome?: (typeof OUTCOME_OPTIONS)[number]
  ) => {
    if (!currentBusinessId) return;
    setSendQueueBusy((prev) => ({ ...prev, [queueId]: `reaction:${outcome || 'auto'}` }));
    try {
      await newAuth.makeRequest(`/partnership/send-queue/${queueId}/reaction`, {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId, outcome }),
      });
      setMessage('Реакция сохранена');
      await loadBatches();
      await loadLeads();
      await loadFunnel();
      await loadOutcomes();
    } catch (e: any) {
      setError(e.message || 'Не удалось сохранить реакцию');
    } finally {
      setSendQueueBusy((prev) => {
        const next = { ...prev };
        delete next[queueId];
        return next;
      });
    }
  };

  const confirmReaction = async (reactionId: string, outcome: (typeof OUTCOME_OPTIONS)[number]) => {
    if (!currentBusinessId) return;
    setReactionBusy((prev) => ({ ...prev, [reactionId]: outcome }));
    try {
      await newAuth.makeRequest(`/partnership/reactions/${reactionId}/confirm`, {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId, outcome }),
      });
      setMessage('Outcome подтверждён');
      await loadBatches();
      await loadLeads();
      await loadFunnel();
      await loadOutcomes();
    } catch (e: any) {
      setError(e.message || 'Не удалось подтвердить outcome');
    } finally {
      setReactionBusy((prev) => {
        const next = { ...prev };
        delete next[reactionId];
        return next;
      });
    }
  };

  const downloadTextFile = (filename: string, content: string, mime = 'text/plain;charset=utf-8') => {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const buildOperatorSnapshotPayload = () => ({
    generated_at: new Date().toISOString(),
    business_id: currentBusinessId,
    pilot_summary: pilotSummary,
    ralph_loop: ralphLoop,
    blockers,
    funnel,
    outcomes,
    health,
  });

  const buildOperatorSnapshotMarkdown = () => {
    const snapshot = buildOperatorSnapshotPayload();
    const lines: string[] = [
      '# Partnership Operator Snapshot',
      '',
      `- business_id: \`${snapshot.business_id || '-'}\``,
      `- generated_at: \`${snapshot.generated_at}\``,
      '',
      '## Pilot Summary',
      `- leads_total: ${snapshot.pilot_summary?.total ?? 0}`,
      `- parsed_completed: ${snapshot.pilot_summary?.parsed ?? 0}`,
      `- ready_for_draft: ${snapshot.pilot_summary?.readyForDraft ?? 0}`,
      `- waiting_approval: ${snapshot.pilot_summary?.waitingApproval ?? 0}`,
      `- waiting_outcome: ${snapshot.pilot_summary?.waitingOutcome ?? 0}`,
      `- positive_rate_pct: ${snapshot.pilot_summary?.acceptance ?? 0}`,
      '',
      '## Ralph Loop (7 days)',
      `- sent_total: ${snapshot.ralph_loop?.summary?.sent_total ?? 0}`,
      `- positive_count: ${snapshot.ralph_loop?.summary?.positive_count ?? 0}`,
      `- positive_rate_pct: ${snapshot.ralph_loop?.summary?.positive_rate_pct ?? 0}`,
      `- baseline_sent_total: ${snapshot.ralph_loop?.baseline?.sent_total ?? 0}`,
      `- baseline_positive_rate_pct: ${snapshot.ralph_loop?.baseline?.positive_rate_pct ?? 0}`,
      '',
      '### Recommendations',
    ];
    const recommendations = Array.isArray(snapshot.ralph_loop?.recommendations) ? snapshot.ralph_loop?.recommendations || [] : [];
    if (recommendations.length > 0) {
      recommendations.forEach((item) => lines.push(`- ${item}`));
    } else {
      lines.push('- none');
    }
    lines.push('', '### Prompt Versions');
    const promptPerf = Array.isArray(snapshot.ralph_loop?.prompt_performance) ? snapshot.ralph_loop?.prompt_performance || [] : [];
    if (promptPerf.length > 0) {
      promptPerf.slice(0, 10).forEach((item) => {
        lines.push(
          `- ${item.prompt_key || 'unknown'} / v${item.prompt_version || 'unknown'} | approved=${item.approved_total ?? 0} | edited=${item.edited_before_accept_pct ?? 0}% | sent=${item.sent_total ?? 0} | positive=${item.positive_rate_pct ?? 0}%`
        );
      });
    } else {
      lines.push('- none');
    }
    lines.push('', '### Blockers');
    const blockerItems = Array.isArray(snapshot.ralph_loop?.blockers) ? snapshot.ralph_loop?.blockers || [] : [];
    if (blockerItems.length > 0) {
      blockerItems.forEach((item) => lines.push(`- ${item}`));
    } else {
      lines.push('- none');
    }
    lines.push('', '### Outcome Summary');
    lines.push(`- positive: ${snapshot.outcomes?.summary?.positive_count ?? 0}`);
    lines.push(`- question: ${snapshot.outcomes?.summary?.question_count ?? 0}`);
    lines.push(`- no_response: ${snapshot.outcomes?.summary?.no_response_count ?? 0}`);
    lines.push(`- hard_no: ${snapshot.outcomes?.summary?.hard_no_count ?? 0}`);
    lines.push('', '### Funnel');
    const funnelItems = Array.isArray(snapshot.funnel?.funnel) ? snapshot.funnel?.funnel || [] : [];
    if (funnelItems.length > 0) {
      funnelItems.forEach((item) => {
        lines.push(`- ${item.label}: ${item.count ?? 0} (conv ${item.conversion_from_prev_pct ?? 0}%)`);
      });
    } else {
      lines.push('- none');
    }
    return lines.join('\n');
  };

  const exportPartnershipReport = async (format: 'json' | 'markdown') => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await newAuth.makeRequest(
        `/partnership/export?business_id=${encodeURIComponent(currentBusinessId)}&format=${format}&limit=50`,
        { method: 'GET' }
      );
      const stamp = new Date().toISOString().replace(/[:.]/g, '-');
      if (format === 'markdown') {
        const md = `${String(data?.markdown_report || '')}\n\n---\n\n${buildOperatorSnapshotMarkdown()}`;
        downloadTextFile(`partnership-export-${currentBusinessId}-${stamp}.md`, md, 'text/markdown;charset=utf-8');
      } else {
        const payload = {
          ...(data || {}),
          operator_snapshot: buildOperatorSnapshotPayload(),
        };
        downloadTextFile(
          `partnership-export-${currentBusinessId}-${stamp}.json`,
          JSON.stringify(payload, null, 2),
          'application/json;charset=utf-8'
        );
      }
      setMessage(`Экспорт (${format}) сформирован`);
    } catch (e: any) {
      setError(e.message || 'Не удалось экспортировать отчёт');
    } finally {
      setLoading(false);
    }
  };

  const downloadPartnershipCsvTemplate = () => {
    const header = [
      'name',
      'source_url',
      'city',
      'category',
      'phone',
      'email',
      'website',
      'telegram_url',
      'whatsapp_url',
      'rating',
      'reviews_count',
    ].join(',');
    const example = [
      'Салон Ромашка',
      'https://yandex.ru/maps/org/1234567890/',
      'Санкт-Петербург',
      'Салон красоты',
      '+7 921 000-00-00',
      'owner@example.com',
      'https://romashka.example',
      'https://t.me/romashka',
      'https://wa.me/79210000000',
      '4.8',
      '152',
    ].join(',');
    downloadTextFile('partnership-import-template.csv', `${header}\n${example}\n`, 'text/csv;charset=utf-8');
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Поиск партнёрств</h1>
        <p className="text-muted-foreground mt-1">
          Добавьте компании по ссылкам, выполните аудит, матчинг услуг и подготовьте первое письмо.
        </p>
      </div>

      {!currentBusinessId ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Сначала выберите бизнес в переключателе сверху.
        </div>
      ) : (
        <>
          <div className="rounded-xl border bg-white p-4 space-y-3">
            <h2 className="text-lg font-semibold">Импорт компаний по ссылкам</h2>
            <Textarea
              rows={5}
              value={linksText}
              onChange={(e) => setLinksText(e.target.value)}
              placeholder="Вставьте ссылки на Яндекс Карты, по одной на строку"
            />
            <div className="flex gap-2">
              <Button onClick={handleImportLinks} disabled={loading}>
                Добавить в партнёрский список
              </Button>
              <Button variant="outline" onClick={() => void loadLeads()} disabled={loading}>
                Обновить список
              </Button>
            </div>
            <div className="pt-2 border-t border-gray-100 space-y-2">
              <h3 className="text-sm font-semibold">Импорт файла партнёров (CSV/JSON/JSONL)</h3>
              <p className="text-xs text-muted-foreground">
                Рекомендуемые поля: <code>name, source_url, city, category, phone, email, website, telegram_url, whatsapp_url, rating, reviews_count</code>.
              </p>
              <div className="flex flex-col md:flex-row gap-2 md:items-center">
                <Input
                  type="file"
                  accept=".csv,.json,.jsonl,text/csv,application/json"
                  onChange={(e) => void handleImportFilePick(e.target.files?.[0] || null)}
                />
                <Button onClick={handleImportFile} disabled={loading || !importFileContent.trim()}>
                  Импортировать файл
                </Button>
                <Button variant="outline" onClick={downloadPartnershipCsvTemplate} disabled={loading}>
                  Скачать CSV-шаблон
                </Button>
              </div>
              {importFileName ? (
                <p className="text-xs text-muted-foreground">
                  Файл: {importFileName} {importFileFormat ? `(${importFileFormat.toUpperCase()})` : ''}
                </p>
              ) : null}
              {importFileErrors.length > 0 ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                  <div className="font-medium mb-1">Ошибки валидации (первые {importFileErrors.length})</div>
                  <div className="space-y-1 max-h-32 overflow-auto">
                    {importFileErrors.map((err, idx) => (
                      <div key={`${err.row || 'x'}-${idx}`}>
                        Строка {err.row || '?'}: {err.error || 'ошибка'}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <h2 className="text-lg font-semibold">Гео-поиск партнёров</h2>
            <p className="text-sm text-muted-foreground">
              Единая точка входа для поиска партнёров. Google работает через OpenClaw, для Яндекс.Карт пока используйте ссылки или импорт файла.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-2">
              <Select value={geoProvider} onValueChange={(value) => setGeoProvider(value as 'google' | 'yandex' | 'both')}>
                <SelectTrigger>
                  <SelectValue placeholder="Источник поиска" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="google">Google Maps</SelectItem>
                  <SelectItem value="yandex">Яндекс Карты</SelectItem>
                  <SelectItem value="both">Оба источника</SelectItem>
                </SelectContent>
              </Select>
              <Input
                value={geoCity}
                onChange={(e) => setGeoCity(e.target.value)}
                placeholder="Город (например, Санкт-Петербург)"
              />
              <Input
                value={geoCategory}
                onChange={(e) => setGeoCategory(e.target.value)}
                placeholder="Категория (например, салон красоты)"
              />
              <Input
                value={geoQuery}
                onChange={(e) => setGeoQuery(e.target.value)}
                placeholder="Запрос (например, маникюр у метро)"
              />
              <Input
                value={geoRadiusKm}
                onChange={(e) => setGeoRadiusKm(e.target.value)}
                placeholder="Радиус (км)"
                type="number"
                min={1}
                max={100}
              />
              <Input
                value={geoLimit}
                onChange={(e) => setGeoLimit(e.target.value)}
                placeholder="Лимит"
                type="number"
                min={1}
                max={200}
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={handleGeoSearch} disabled={loading}>
                Запустить гео-поиск
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setGeoProvider('google');
                  setGeoCity('');
                  setGeoCategory('');
                  setGeoQuery('');
                  setGeoRadiusKm('5');
                  setGeoLimit('25');
                }}
                disabled={loading}
              >
                Сбросить
              </Button>
            </div>
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Состояние потока партнёрств</h2>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => void exportPartnershipReport('json')} disabled={loading}>
                  Экспорт JSON
                </Button>
                <Button variant="outline" onClick={() => void exportPartnershipReport('markdown')} disabled={loading}>
                  Экспорт Markdown
                </Button>
                <Button variant="outline" onClick={() => void loadHealth()} disabled={loading}>
                  Обновить
                </Button>
              </div>
            </div>
            {!health ? (
              <p className="text-sm text-muted-foreground">Health недоступен.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                <div className="rounded-lg border border-gray-200 p-3 bg-gray-50">
                  <div className="font-semibold text-foreground">OpenClaw</div>
                  <div className="text-muted-foreground mt-1">
                    Включен: {health.openclaw?.enabled ? 'да' : 'нет'}
                  </div>
                  <div className="text-muted-foreground">
                    Endpoint: {health.openclaw?.caps_endpoint_configured ? 'ok' : 'не задан'}
                  </div>
                  <div className="text-muted-foreground">
                    Token: {health.openclaw?.token_configured ? 'ok' : 'не задан'}
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 p-3 bg-gray-50">
                  <div className="font-semibold text-foreground">Объёмы</div>
                  <div className="text-muted-foreground mt-1">
                    Лиды: {health.counts?.leads_total ?? 0} · Черновики: {health.counts?.drafts_total ?? 0}
                  </div>
                  <div className="text-muted-foreground">
                    Batch: {health.counts?.batches_total ?? 0} · Реакции: {health.counts?.reactions_total ?? 0}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Пилотный запуск: сводка оператора</h2>
              <div className="text-xs text-muted-foreground">Короткий срез по текущему бизнесу</div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2">
              <div className="rounded-lg border border-gray-200 p-3 bg-gray-50">
                <div className="text-xs uppercase text-muted-foreground">Лиды</div>
                <div className="text-2xl font-semibold mt-1">{pilotSummary.total}</div>
              </div>
              <div className="rounded-lg border border-sky-200 p-3 bg-sky-50">
                <div className="text-xs uppercase text-sky-700">Парсинг завершён</div>
                <div className="text-2xl font-semibold mt-1 text-sky-700">{pilotSummary.parsed}</div>
              </div>
              <div className="rounded-lg border border-violet-200 p-3 bg-violet-50">
                <div className="text-xs uppercase text-violet-700">Готовы к письму</div>
                <div className="text-2xl font-semibold mt-1 text-violet-700">{pilotSummary.readyForDraft}</div>
              </div>
              <div className="rounded-lg border border-amber-200 p-3 bg-amber-50">
                <div className="text-xs uppercase text-amber-700">Ждут утверждения</div>
                <div className="text-2xl font-semibold mt-1 text-amber-700">{pilotSummary.waitingApproval}</div>
              </div>
              <div className="rounded-lg border border-blue-200 p-3 bg-blue-50">
                <div className="text-xs uppercase text-blue-700">Ждут outcome</div>
                <div className="text-2xl font-semibold mt-1 text-blue-700">{pilotSummary.waitingOutcome}</div>
              </div>
              <div className="rounded-lg border border-emerald-200 p-3 bg-emerald-50">
                <div className="text-xs uppercase text-emerald-700">Positive rate</div>
                <div className="text-2xl font-semibold mt-1 text-emerald-700">{pilotSummary.acceptance}%</div>
              </div>
            </div>
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Ralph loop summary (7 дней)</h2>
              <Button variant="outline" onClick={() => void loadRalphLoop()} disabled={loading}>
                Обновить
              </Button>
            </div>
            {!ralphLoop?.summary ? (
              <p className="text-sm text-muted-foreground">Недельная summary пока недоступна.</p>
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-2">
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                    <div className="text-xs uppercase text-muted-foreground">Лиды</div>
                    <div className="text-2xl font-semibold mt-1">{ralphLoop.summary.leads_total ?? 0}</div>
                  </div>
                  <div className="rounded-lg border border-sky-200 bg-sky-50 p-3">
                    <div className="text-xs uppercase text-sky-700">Парсинг</div>
                    <div className="text-2xl font-semibold mt-1 text-sky-700">{ralphLoop.summary.parsed_completed_count ?? 0}</div>
                  </div>
                  <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-3">
                    <div className="text-xs uppercase text-indigo-700">Аудит</div>
                    <div className="text-2xl font-semibold mt-1 text-indigo-700">{ralphLoop.summary.audited_count ?? 0}</div>
                  </div>
                  <div className="rounded-lg border border-violet-200 bg-violet-50 p-3">
                    <div className="text-xs uppercase text-violet-700">Матчинг</div>
                    <div className="text-2xl font-semibold mt-1 text-violet-700">{ralphLoop.summary.matched_count ?? 0}</div>
                  </div>
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                    <div className="text-xs uppercase text-amber-700">Черновики</div>
                    <div className="text-2xl font-semibold mt-1 text-amber-700">{ralphLoop.summary.drafts_total ?? 0}</div>
                  </div>
                  <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
                    <div className="text-xs uppercase text-emerald-700">Sent</div>
                    <div className="text-2xl font-semibold mt-1 text-emerald-700">{ralphLoop.summary.sent_total ?? 0}</div>
                  </div>
                  <div className="rounded-lg border border-green-200 bg-green-50 p-3">
                    <div className="text-xs uppercase text-green-700">Positive</div>
                    <div className="text-2xl font-semibold mt-1 text-green-700">{ralphLoop.summary.positive_count ?? 0}</div>
                  </div>
                  <div className="rounded-lg border border-teal-200 bg-teal-50 p-3">
                    <div className="text-xs uppercase text-teal-700">Positive rate</div>
                    <div className="text-2xl font-semibold mt-1 text-teal-700">{ralphLoop.summary.positive_rate_pct ?? 0}%</div>
                  </div>
                </div>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                  <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                    <div className="text-sm font-semibold mb-2">Сравнение с предыдущими 7 днями</div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                      <div className="rounded-lg border border-white/80 bg-white/80 p-3">
                        <div className="text-xs uppercase text-muted-foreground">Sent</div>
                        <div className="text-lg font-semibold text-foreground mt-1">
                          {ralphLoop.summary.sent_total ?? 0}
                          <span className={`ml-2 text-sm ${(ralphLoop.baseline?.deltas?.sent_total || 0) >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
                            {(ralphLoop.baseline?.deltas?.sent_total || 0) >= 0 ? '+' : ''}
                            {ralphLoop.baseline?.deltas?.sent_total || 0}
                          </span>
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          было: {ralphLoop.baseline?.sent_total ?? 0}
                        </div>
                      </div>
                      <div className="rounded-lg border border-white/80 bg-white/80 p-3">
                        <div className="text-xs uppercase text-muted-foreground">Positive</div>
                        <div className="text-lg font-semibold text-foreground mt-1">
                          {ralphLoop.summary.positive_count ?? 0}
                          <span className={`ml-2 text-sm ${(ralphLoop.baseline?.deltas?.positive_count || 0) >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
                            {(ralphLoop.baseline?.deltas?.positive_count || 0) >= 0 ? '+' : ''}
                            {ralphLoop.baseline?.deltas?.positive_count || 0}
                          </span>
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          было: {ralphLoop.baseline?.positive_count ?? 0}
                        </div>
                      </div>
                      <div className="rounded-lg border border-white/80 bg-white/80 p-3">
                        <div className="text-xs uppercase text-muted-foreground">Positive rate</div>
                        <div className="text-lg font-semibold text-foreground mt-1">
                          {ralphLoop.summary.positive_rate_pct ?? 0}%
                          <span className={`ml-2 text-sm ${(ralphLoop.baseline?.deltas?.positive_rate_pct || 0) >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
                            {(ralphLoop.baseline?.deltas?.positive_rate_pct || 0) >= 0 ? '+' : ''}
                            {ralphLoop.baseline?.deltas?.positive_rate_pct || 0} п.п.
                          </span>
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          было: {ralphLoop.baseline?.positive_rate_pct ?? 0}%
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                    <div className="text-sm font-semibold mb-2">Что менять на следующей неделе</div>
                    {Array.isArray(ralphLoop.recommendations) && ralphLoop.recommendations.length > 0 ? (
                      <div className="space-y-1 text-sm">
                        {ralphLoop.recommendations.map((item, idx) => (
                          <div key={`${item}-${idx}`} className="text-muted-foreground">
                            {idx + 1}. {item}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground">
                        Явных рекомендаций пока нет. Можно продолжать текущий сценарий и смотреть на outcome.
                      </div>
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                    <div className="text-sm font-semibold mb-2">Лучшие каналы</div>
                    {Array.isArray(ralphLoop.top_channels) && ralphLoop.top_channels.length > 0 ? (
                      <div className="space-y-1 text-sm">
                        {ralphLoop.top_channels.map((item, idx) => (
                          <div key={`${item.channel || 'channel'}-${idx}`} className="flex items-center justify-between gap-2">
                            <span>{item.channel || 'unknown'}</span>
                            <span className="text-muted-foreground">{item.positive_rate_pct ?? 0}% ({item.positive_count ?? 0}/{item.total ?? 0})</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground">Пока нет канальной статистики.</div>
                    )}
                  </div>
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                    <div className="text-sm font-semibold mb-2">Обучение по промптам</div>
                    {Array.isArray(ralphLoop.learning) && ralphLoop.learning.length > 0 ? (
                      <div className="space-y-1 text-sm">
                        {ralphLoop.learning.map((item, idx) => (
                          <div key={`${item.capability || 'cap'}-${idx}`} className="flex items-center justify-between gap-2">
                            <span>{item.capability || '—'}</span>
                            <span className="text-muted-foreground">{item.edited_before_accept_pct ?? 0}% правок</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground">Пока нет learning-сигналов.</div>
                    )}
                  </div>
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                    <div className="text-sm font-semibold mb-2">Что мешает росту</div>
                    {Array.isArray(ralphLoop.blockers) && ralphLoop.blockers.length > 0 ? (
                      <div className="space-y-1 text-sm">
                        {ralphLoop.blockers.map((item, idx) => (
                          <div key={`${item}-${idx}`} className="text-muted-foreground">{item}</div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground">Явных блокеров за период не найдено.</div>
                    )}
                  </div>
                </div>
                <div className="rounded-lg border border-fuchsia-200 bg-fuchsia-50 p-3">
                  <div className="text-sm font-semibold mb-2">Как оператор правит первое письмо</div>
                  {(ralphLoop.edit_insights?.edited_accepts_total || 0) > 0 ? (
                    <div className="grid grid-cols-2 md:grid-cols-6 gap-2 text-sm">
                      <div className="rounded-lg border border-white/80 bg-white/80 p-3">
                        <div className="text-xs uppercase text-muted-foreground">Правок</div>
                        <div className="text-lg font-semibold mt-1">{ralphLoop.edit_insights?.edited_accepts_total ?? 0}</div>
                      </div>
                      <div className="rounded-lg border border-white/80 bg-white/80 p-3">
                        <div className="text-xs uppercase text-muted-foreground">Черновик</div>
                        <div className="text-lg font-semibold mt-1">{ralphLoop.edit_insights?.avg_generated_len ?? 0}</div>
                        <div className="text-xs text-muted-foreground mt-1">ср. длина</div>
                      </div>
                      <div className="rounded-lg border border-white/80 bg-white/80 p-3">
                        <div className="text-xs uppercase text-muted-foreground">Финал</div>
                        <div className="text-lg font-semibold mt-1">{ralphLoop.edit_insights?.avg_final_len ?? 0}</div>
                        <div className="text-xs text-muted-foreground mt-1">ср. длина</div>
                      </div>
                      <div className="rounded-lg border border-white/80 bg-white/80 p-3">
                        <div className="text-xs uppercase text-muted-foreground">Дописывают</div>
                        <div className="text-lg font-semibold mt-1">{ralphLoop.edit_insights?.expanded_count ?? 0}</div>
                      </div>
                      <div className="rounded-lg border border-white/80 bg-white/80 p-3">
                        <div className="text-xs uppercase text-muted-foreground">Сокращают</div>
                        <div className="text-lg font-semibold mt-1">{ralphLoop.edit_insights?.shortened_count ?? 0}</div>
                      </div>
                      <div className="rounded-lg border border-white/80 bg-white/80 p-3">
                        <div className="text-xs uppercase text-muted-foreground">Без изменений</div>
                        <div className="text-lg font-semibold mt-1">{ralphLoop.edit_insights?.unchanged_count ?? 0}</div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-sm text-muted-foreground">
                      Пока нет утверждённых писем с ручными правками за выбранное окно.
                    </div>
                  )}
                </div>
                <div className="rounded-lg border border-cyan-200 bg-cyan-50 p-3">
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="text-sm font-semibold">Версии prompt для первого письма</div>
                    {ralphLoop.recommended_prompt_version ? (
                      <div className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                        Рекомендовано: {ralphLoop.recommended_prompt_version.prompt_key || 'unknown'} · v{ralphLoop.recommended_prompt_version.prompt_version || 'unknown'}
                      </div>
                    ) : null}
                  </div>
                  {Array.isArray(ralphLoop.prompt_performance) && ralphLoop.prompt_performance.length > 0 ? (
                    <div className="space-y-2 text-sm">
                      {ralphLoop.prompt_performance.map((item, idx) => (
                        <div
                          key={`${item.prompt_key || 'prompt'}-${item.prompt_version || 'version'}-${idx}`}
                          className="rounded-lg border border-white/80 bg-white/80 p-3"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="font-medium text-foreground">
                              {item.prompt_key || 'unknown'} · v{item.prompt_version || 'unknown'}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              sent: {item.sent_total ?? 0} · positive: {item.positive_rate_pct ?? 0}%
                            </div>
                          </div>
                          <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs text-muted-foreground">
                            <div>Утверждено: {item.approved_total ?? 0}</div>
                            <div>Правок: {item.edited_before_accept_pct ?? 0}%</div>
                            <div>Черновиков: {item.drafts_total ?? 0}</div>
                            <div>Positive: {item.positive_count ?? 0}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-muted-foreground">
                      Пока нет данных по версиям prompt. Они начнут копиться на новых первых письмах.
                    </div>
                  )}
                </div>
              </>
            )}
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Воронка партнёрств (30 дней)</h2>
              <Button variant="outline" onClick={() => void loadFunnel()} disabled={loading}>
                Обновить
              </Button>
            </div>
            {!funnel || !Array.isArray(funnel.funnel) ? (
              <p className="text-sm text-muted-foreground">Данные воронки пока недоступны.</p>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
                  {funnel.funnel.map((stage) => (
                    <div key={stage.key} className="rounded-lg border border-gray-200 p-3 bg-gray-50">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">{stage.label}</div>
                      <div className="text-2xl font-semibold text-foreground mt-1">{stage.count ?? 0}</div>
                      {stage.key !== 'imported' ? (
                        <div className="text-xs text-muted-foreground mt-1">
                          Конверсия: {stage.conversion_from_prev_pct ?? 0}%
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
                <div className="text-sm text-muted-foreground">
                  Общая конверсия import → sent: <span className="font-medium text-foreground">{funnel.summary?.import_to_sent_pct ?? 0}%</span>
                  {' '}({funnel.summary?.sent_count ?? 0} из {funnel.summary?.imported_count ?? 0})
                </div>
              </>
            )}
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Качество источников лидов</h2>
              <Button variant="outline" onClick={() => void loadSourceQuality()} disabled={loading}>
                Обновить
              </Button>
            </div>
            {!sourceQuality || !Array.isArray(sourceQuality.items) || sourceQuality.items.length === 0 ? (
              <p className="text-sm text-muted-foreground">Пока нет данных по качеству источников.</p>
            ) : (
              <div className="space-y-2">
                {sourceQuality.items.map((item, idx) => (
                  <div key={`${item.source_kind || 'source'}-${item.source_provider || 'provider'}-${idx}`} className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                      <div>
                        <div className="font-medium text-foreground">
                          {item.source_kind || 'unknown'} · {item.source_provider || 'unknown'}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Лидов: {item.leads_total ?? 0} · Аудит: {item.audited_count ?? 0} · Матчинг: {item.matched_count ?? 0} · Черновики: {item.draft_count ?? 0} · Отправлено: {item.sent_count ?? 0}
                        </div>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        lead → positive: <span className="font-medium text-foreground">{item.lead_to_positive_pct ?? 0}%</span>
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
                      <div className="rounded-md border border-white bg-white p-2">
                        <div className="text-muted-foreground uppercase">Audit rate</div>
                        <div className="text-sm font-semibold text-foreground mt-1">{item.audit_rate_pct ?? 0}%</div>
                      </div>
                      <div className="rounded-md border border-white bg-white p-2">
                        <div className="text-muted-foreground uppercase">Match rate</div>
                        <div className="text-sm font-semibold text-foreground mt-1">{item.match_rate_pct ?? 0}%</div>
                      </div>
                      <div className="rounded-md border border-white bg-white p-2">
                        <div className="text-muted-foreground uppercase">Draft rate</div>
                        <div className="text-sm font-semibold text-foreground mt-1">{item.draft_rate_pct ?? 0}%</div>
                      </div>
                      <div className="rounded-md border border-white bg-white p-2">
                        <div className="text-muted-foreground uppercase">Sent rate</div>
                        <div className="text-sm font-semibold text-foreground mt-1">{item.sent_rate_pct ?? 0}%</div>
                      </div>
                      <div className="rounded-md border border-white bg-white p-2">
                        <div className="text-muted-foreground uppercase">Positive rate</div>
                        <div className="text-sm font-semibold text-foreground mt-1">{item.positive_rate_pct ?? 0}%</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Что тормозит конверсию</h2>
              <Button variant="outline" onClick={() => void loadBlockers()} disabled={loading}>
                Обновить
              </Button>
            </div>
            {!blockers || !Array.isArray(blockers.blockers) ? (
              <p className="text-sm text-muted-foreground">Диагностика пока недоступна.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
                {blockers.blockers.map((item) => {
                  const tone =
                    item.severity === 'danger'
                      ? 'border-rose-200 bg-rose-50'
                      : item.severity === 'warning'
                        ? 'border-amber-200 bg-amber-50'
                        : 'border-sky-200 bg-sky-50';
                  return (
                    <div key={item.key} className={`rounded-lg border p-3 ${tone}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="text-sm font-semibold text-foreground">{item.label}</div>
                        <div className="text-2xl font-semibold text-foreground">{item.count ?? 0}</div>
                      </div>
                      <div className="mt-2 text-xs text-muted-foreground">{item.hint || '—'}</div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Outcome-аналитика (30 дней)</h2>
              <Button variant="outline" onClick={() => void loadOutcomes()} disabled={loading}>
                Обновить
              </Button>
            </div>
            {!outcomes?.summary ? (
              <p className="text-sm text-muted-foreground">Данные outcome пока недоступны.</p>
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                  <div className="rounded-lg border border-gray-200 p-3 bg-gray-50">
                    <div className="text-xs text-muted-foreground uppercase">Всего</div>
                    <div className="text-2xl font-semibold">{outcomes.summary.total_reactions ?? 0}</div>
                  </div>
                  <div className="rounded-lg border border-emerald-200 p-3 bg-emerald-50">
                    <div className="text-xs text-emerald-700 uppercase">Positive</div>
                    <div className="text-2xl font-semibold text-emerald-700">{outcomes.summary.positive_count ?? 0}</div>
                    <div className="text-xs text-emerald-700">{outcomes.summary.positive_rate_pct ?? 0}%</div>
                  </div>
                  <div className="rounded-lg border border-blue-200 p-3 bg-blue-50">
                    <div className="text-xs text-blue-700 uppercase">Question</div>
                    <div className="text-2xl font-semibold text-blue-700">{outcomes.summary.question_count ?? 0}</div>
                    <div className="text-xs text-blue-700">{outcomes.summary.question_rate_pct ?? 0}%</div>
                  </div>
                  <div className="rounded-lg border border-amber-200 p-3 bg-amber-50">
                    <div className="text-xs text-amber-700 uppercase">No response</div>
                    <div className="text-2xl font-semibold text-amber-700">{outcomes.summary.no_response_count ?? 0}</div>
                    <div className="text-xs text-amber-700">{outcomes.summary.no_response_rate_pct ?? 0}%</div>
                  </div>
                  <div className="rounded-lg border border-rose-200 p-3 bg-rose-50">
                    <div className="text-xs text-rose-700 uppercase">Hard no</div>
                    <div className="text-2xl font-semibold text-rose-700">{outcomes.summary.hard_no_count ?? 0}</div>
                    <div className="text-xs text-rose-700">{outcomes.summary.hard_no_rate_pct ?? 0}%</div>
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 p-3 bg-gray-50">
                  <div className="text-sm font-medium mb-2">По каналам</div>
                  {!Array.isArray(outcomes.by_channel) || outcomes.by_channel.length === 0 ? (
                    <div className="text-sm text-muted-foreground">Пока нет разбивки по каналам.</div>
                  ) : (
                    <div className="space-y-1 text-sm">
                      {outcomes.by_channel.map((ch, idx) => (
                        <div key={`${ch.channel || 'channel'}-${idx}`} className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">{ch.channel || 'unknown'}</span>
                          <span className="text-muted-foreground">всего: {ch.total ?? 0}</span>
                          <span className="text-emerald-700">positive: {ch.positive_count ?? 0}</span>
                          <span className="text-blue-700">question: {ch.question_count ?? 0}</span>
                          <span className="text-amber-700">no_response: {ch.no_response_count ?? 0}</span>
                          <span className="text-rose-700">hard_no: {ch.hard_no_count ?? 0}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>

          <div className="rounded-xl border bg-white p-4">
            <div className="flex flex-col md:flex-row gap-3 mb-4">
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Поиск по названию/ссылке"
              />
              <Select value={stage} onValueChange={setStage}>
                <SelectTrigger className="w-full md:w-[240px]">
                  <SelectValue placeholder="Этап" />
                </SelectTrigger>
                <SelectContent>
                  {STAGE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button variant="outline" onClick={() => void loadLeads()} disabled={loading}>
                Применить
              </Button>
              <Button variant="outline" onClick={() => void loadHealth()} disabled={loading}>
                Health
              </Button>
              <Select value={pilotCohort} onValueChange={(value) => setPilotCohort(value as typeof pilotCohort)}>
                <SelectTrigger className="w-full md:w-[190px]">
                  <SelectValue placeholder="Когорта" />
                </SelectTrigger>
                <SelectContent>
                  {PILOT_COHORT_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={leadView} onValueChange={(value) => setLeadView(value as typeof leadView)}>
                <SelectTrigger className="w-full md:w-[250px]">
                  <SelectValue placeholder="Операторский фильтр" />
                </SelectTrigger>
                <SelectContent>
                  {LEAD_VIEW_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3 mb-4">
              <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-foreground">Массовые действия</div>
                  <div className="text-xs text-muted-foreground">
                    Выбрано: {selectedLeadIds.length}. Можно быстро перевести лиды по этапам, назначить канал или очистить тестовые записи.
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Select value={bulkStage} onValueChange={setBulkStage}>
                    <SelectTrigger className="w-[220px] bg-white">
                      <SelectValue placeholder="Этап для выбранных" />
                    </SelectTrigger>
                    <SelectContent>
                      {BULK_STAGE_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select value={bulkChannel} onValueChange={setBulkChannel}>
                    <SelectTrigger className="w-[200px] bg-white">
                      <SelectValue placeholder="Канал для выбранных" />
                    </SelectTrigger>
                    <SelectContent>
                      {CHANNEL_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select value={bulkPilotCohort} onValueChange={setBulkPilotCohort}>
                    <SelectTrigger className="w-[180px] bg-white">
                      <SelectValue placeholder="Когорта" />
                    </SelectTrigger>
                    <SelectContent>
                      {PILOT_COHORT_OPTIONS.filter((opt) => opt.value !== 'all').map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button variant="outline" onClick={applyBulkUpdate} disabled={loading || selectedLeadIds.length === 0}>
                    Применить к выбранным
                  </Button>
                  <Button variant="outline" onClick={bulkEnrichContacts} disabled={loading || selectedLeadIds.length === 0}>
                    Обогатить контакты
                  </Button>
                  <Button variant="outline" onClick={bulkDeleteLeads} disabled={loading || selectedLeadIds.length === 0}>
                    Удалить выбранные
                  </Button>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              {visibleLeads.length === 0 ? (
                <p className="text-sm text-muted-foreground">Список пуст.</p>
              ) : (
                <>
                  <label className="flex items-center gap-2 text-sm text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={visibleLeads.length > 0 && visibleLeads.every((item) => selectedLeadIds.includes(item.id))}
                      onChange={(e) => toggleAllLeadSelection(e.target.checked)}
                    />
                    Выбрать все в текущем фильтре
                  </label>
                {visibleLeads.map((item) => (
                  <div
                    key={item.id}
                    className={`rounded-lg border p-3 ${selectedLeadId === item.id ? 'border-primary' : 'border-gray-200'}`}
                  >
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                      <div className="flex items-start gap-3">
                        <input
                          className="mt-1"
                          type="checkbox"
                          checked={selectedLeadIds.includes(item.id)}
                          onChange={(e) => toggleLeadSelection(item.id, e.target.checked)}
                        />
                        <div>
                        <div className="font-semibold text-foreground">{item.name || 'Без названия'}</div>
                        <div className="text-sm text-muted-foreground">
                          {item.city || '—'} · {item.category || '—'} · этап: {item.partnership_stage || 'imported'} · когорта: {item.pilot_cohort || 'backlog'}
                        </div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {item.source_provider ? (
                            <span className="inline-flex items-center rounded-full border border-gray-300 bg-white px-2 py-0.5 text-[11px] text-gray-700">
                              provider: {item.source_provider}
                            </span>
                          ) : null}
                          {item.source_kind ? (
                            <span className="inline-flex items-center rounded-full border border-gray-300 bg-white px-2 py-0.5 text-[11px] text-gray-700">
                              source: {item.source_kind}
                            </span>
                          ) : null}
                          {Array.isArray(item.matched_sources_json) && item.matched_sources_json.length > 1 ? (
                            <span className="inline-flex items-center rounded-full border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700">
                              merged: {item.matched_sources_json.length}
                            </span>
                          ) : null}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Парсинг: {item.parse_status || 'не запускался'}
                          {item.parse_updated_at ? ` · ${new Date(item.parse_updated_at).toLocaleString('ru-RU')}` : ''}
                          {item.parse_retry_after ? ` · retry_after: ${new Date(item.parse_retry_after).toLocaleString('ru-RU')}` : ''}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Контакты: {item.phone || 'телефон —'} · {item.email || 'email —'} · {item.telegram_url ? 'telegram ✓' : 'telegram —'} · {item.whatsapp_url ? 'whatsapp ✓' : 'whatsapp —'}
                        </div>
                        {item.next_best_action ? (
                          <div className="mt-2 rounded-md border border-sky-200 bg-sky-50 px-2 py-1.5">
                            <div className="text-xs font-medium text-sky-900">
                              Следующее действие: {item.next_best_action.label || '—'}
                            </div>
                            <div className="text-[11px] text-sky-800 mt-0.5">
                              {item.next_best_action.hint || '—'}
                            </div>
                          </div>
                        ) : null}
                        {item.parse_error ? (
                          <div className="text-xs text-red-600 mt-1">{item.parse_error}</div>
                        ) : null}
                        <a
                          href={item.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sm text-blue-600 underline break-all"
                        >
                          {item.source_url}
                        </a>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button variant="outline" size="sm" onClick={() => void runParse(item.id)} disabled={loading}>
                          Запустить парсинг
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => void enrichContacts(item.id)} disabled={loading}>
                          Обогатить контакты
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => void runAudit(item.id)} disabled={loading}>
                          Аудит
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => void runMatch(item.id)} disabled={loading}>
                          Матчинг
                        </Button>
                        <Button size="sm" onClick={() => void runDraft(item.id)} disabled={loading}>
                          Первое письмо
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => void deleteLead(item.id)} disabled={loading}>
                          Удалить
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
                </>
              )}
            </div>
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Метрики обучения (30 дней)</h2>
              <Button variant="outline" onClick={() => void loadLearningMetrics()} disabled={loading}>
                Обновить
              </Button>
            </div>
            {learningMetrics.length === 0 ? (
              <p className="text-sm text-muted-foreground">Метрики пока недоступны.</p>
            ) : (
              <div className="grid gap-2 md:grid-cols-2">
                {learningMetrics.map((metric) => (
                  <div key={metric.capability} className="rounded-lg border border-gray-200 p-3 bg-gray-50">
                    <div className="text-sm font-semibold text-foreground">{metric.capability}</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Принято: {metric.accepted_total} · без правок: {metric.accepted_raw_total} ({metric.accepted_raw_pct}%)
                    </div>
                    <div className="text-xs text-muted-foreground">
                      С правками: {metric.accepted_edited_total} ({metric.edited_before_accept_pct}%)
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <h2 className="text-lg font-semibold">Результат по выбранному лиду</h2>
            <p className="text-sm text-muted-foreground">
              {selectedLead ? `${selectedLead.name || 'Лид'} (${selectedLead.id})` : 'Лид не выбран'}
            </p>

            {auditData && (
              <div className="rounded-lg border border-gray-200 p-3 bg-gray-50">
                <div className="font-medium mb-1">Аудит карточки</div>
                <p className="text-sm text-muted-foreground">
                  Услуг в превью: {(auditData.services_preview || []).length || 0}
                </p>
              </div>
            )}

            {matchData && (
              <div className="rounded-lg border border-gray-200 p-3 bg-gray-50">
                <div className="font-medium mb-1">Матчинг услуг</div>
                <p className="text-sm text-muted-foreground">
                  Match score: {matchData.match_score ?? 0}%
                </p>
                <p className="text-sm text-muted-foreground">
                  Пересечения: {(matchData.overlap || []).slice(0, 8).join(', ') || '—'}
                </p>
                {matchData.score_explanation ? (
                  <p className="text-sm text-gray-700 mt-2">
                    {String(matchData.score_explanation)}
                  </p>
                ) : null}
                {Array.isArray(matchData.reason_codes) && matchData.reason_codes.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {matchData.reason_codes.map((code: string) => (
                      <span key={code} className="inline-flex items-center rounded-full border border-gray-300 bg-white px-2 py-0.5 text-[11px] text-gray-700">
                        {code}
                      </span>
                    ))}
                  </div>
                ) : null}
                <p className="text-sm text-muted-foreground mt-2">
                  Комплементарные направления: {((matchData.complement || {}).partner_strength_tokens || []).slice(0, 6).join(', ') || '—'}
                </p>
                <p className="text-sm text-muted-foreground">
                  Углы оффера: {(matchData.offer_angles || []).slice(0, 3).join(' · ') || '—'}
                </p>
              </div>
            )}

            {draftText && (
              <div className="rounded-lg border border-gray-200 p-3 bg-gray-50">
                <div className="font-medium mb-2">Первое письмо</div>
                <Textarea value={draftText} rows={8} readOnly />
              </div>
            )}

            {selectedLead && (
              <div className="rounded-lg border border-gray-200 p-3 bg-gray-50 space-y-2">
                {selectedLead.next_best_action ? (
                  <div className="rounded-lg border border-sky-200 bg-sky-50 p-3">
                    <div className="text-sm font-semibold text-foreground">Следующее лучшее действие</div>
                    <div className="text-sm text-sky-900 mt-1">{selectedLead.next_best_action.label || '—'}</div>
                    <div className="text-xs text-muted-foreground mt-1">{selectedLead.next_best_action.hint || '—'}</div>
                  </div>
                ) : null}
                <div className="font-medium">Ручное редактирование лида</div>
                <div className="rounded-lg border border-gray-200 bg-white p-3">
                  <div className="text-sm font-medium text-foreground">Источник лида</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    provider: {selectedLead.source_provider || '—'} · source: {selectedLead.source_kind || '—'}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    external_source_id: {selectedLead.external_source_id || '—'} · external_place_id: {selectedLead.external_place_id || '—'}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    coords: {selectedLead.lat ?? '—'}, {selectedLead.lon ?? '—'}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    matched_sources: {Array.isArray(selectedLead.matched_sources_json) && selectedLead.matched_sources_json.length
                      ? selectedLead.matched_sources_json.join(', ')
                      : '—'}
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  <Input value={leadEdit.name} onChange={(e) => setLeadEdit((p) => ({ ...p, name: e.target.value }))} placeholder="Название" />
                  <Input value={leadEdit.category} onChange={(e) => setLeadEdit((p) => ({ ...p, category: e.target.value }))} placeholder="Категория" />
                  <Input value={leadEdit.city} onChange={(e) => setLeadEdit((p) => ({ ...p, city: e.target.value }))} placeholder="Город" />
                  <Input value={leadEdit.address} onChange={(e) => setLeadEdit((p) => ({ ...p, address: e.target.value }))} placeholder="Адрес" />
                  <Input value={leadEdit.phone} onChange={(e) => setLeadEdit((p) => ({ ...p, phone: e.target.value }))} placeholder="Телефон" />
                  <Input value={leadEdit.email} onChange={(e) => setLeadEdit((p) => ({ ...p, email: e.target.value }))} placeholder="Email" />
                  <Input value={leadEdit.website} onChange={(e) => setLeadEdit((p) => ({ ...p, website: e.target.value }))} placeholder="Сайт" />
                  <Input value={leadEdit.telegram_url} onChange={(e) => setLeadEdit((p) => ({ ...p, telegram_url: e.target.value }))} placeholder="Telegram URL" />
                  <Input value={leadEdit.whatsapp_url} onChange={(e) => setLeadEdit((p) => ({ ...p, whatsapp_url: e.target.value }))} placeholder="WhatsApp URL" />
                </div>
                <div className="flex justify-end">
              <Button variant="outline" onClick={() => void saveLeadContacts()} disabled={loading}>
                Сохранить данные лида
              </Button>
              {selectedLead ? (
                <Select
                  value={selectedLead.pilot_cohort || 'backlog'}
                  onValueChange={async (value) => {
                    if (!currentBusinessId || !selectedLead) return;
                    try {
                      setLoading(true);
                      setError(null);
                      await newAuth.makeRequest(`/partnership/leads/${selectedLead.id}`, {
                        method: 'PATCH',
                        body: JSON.stringify({
                          business_id: currentBusinessId,
                          pilot_cohort: value,
                        }),
                      });
                      setMessage(`Когорта обновлена: ${value}`);
                      await loadLeads();
                      await loadRalphLoop();
                    } catch (e: any) {
                      setError(e.message || 'Не удалось обновить когорту');
                    } finally {
                      setLoading(false);
                    }
                  }}
                >
                  <SelectTrigger className="w-[180px] bg-white">
                    <SelectValue placeholder="Когорта" />
                  </SelectTrigger>
                  <SelectContent>
                    {PILOT_COHORT_OPTIONS.filter((opt) => opt.value !== 'all').map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : null}
            </div>
              </div>
            )}
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Черновики партнёрского оффера</h2>
              <div className="flex gap-2">
                <Select value={draftView} onValueChange={(value) => setDraftView(value as typeof draftView)}>
                  <SelectTrigger className="w-[220px]">
                    <SelectValue placeholder="Фильтр черновиков" />
                  </SelectTrigger>
                  <SelectContent>
                    {DRAFT_VIEW_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button variant="outline" onClick={() => void loadDrafts()} disabled={loading}>
                  Обновить
                </Button>
              </div>
            </div>
            {visibleDrafts.length > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3">
                <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
                  <div className="text-xs text-muted-foreground">
                    Выбрано черновиков: {selectedDraftIds.length}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" onClick={bulkApproveDrafts} disabled={loading || selectedDraftIds.length === 0}>
                      Утвердить выбранные
                    </Button>
                    <Button variant="outline" onClick={bulkDeleteDrafts} disabled={loading || selectedDraftIds.length === 0}>
                      Удалить выбранные
                    </Button>
                  </div>
                </div>
              </div>
            )}
            {visibleDrafts.length === 0 ? (
              <p className="text-sm text-muted-foreground">Черновиков пока нет.</p>
            ) : (
              <>
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={visibleDrafts.length > 0 && visibleDrafts.every((draft) => selectedDraftIds.includes(draft.id))}
                    onChange={(e) => toggleAllDraftSelection(e.target.checked)}
                  />
                  Выбрать все черновики в текущем фильтре
                </label>
              {visibleDrafts.map((draft) => (
                <div key={draft.id} className="rounded-lg border border-gray-200 p-3">
                  <div className="flex items-start gap-3">
                    <input
                      className="mt-1"
                      type="checkbox"
                      checked={selectedDraftIds.includes(draft.id)}
                      onChange={(e) => toggleDraftSelection(draft.id, e.target.checked)}
                    />
                    <div className="flex-1">
                  <div className="text-sm font-semibold text-foreground">{draft.lead_name || draft.lead_id}</div>
                  <div className="text-xs text-muted-foreground mb-2">
                    статус: {draft.status || '—'} · канал: {draft.channel || '—'}
                  </div>
                  <Textarea
                    rows={5}
                    value={draft.approved_text || draft.edited_text || draft.generated_text || ''}
                    onChange={(e) =>
                      setDrafts((prev) =>
                        prev.map((x) => (x.id === draft.id ? { ...x, approved_text: e.target.value } : x))
                      )
                    }
                  />
                  <div className="flex justify-end mt-2">
                    <Button
                      size="sm"
                      onClick={() => void approveDraft(draft.id, draft.approved_text || draft.edited_text || draft.generated_text || '')}
                      disabled={loading}
                    >
                      Утвердить для отправки
                    </Button>
                  </div>
                    </div>
                  </div>
                </div>
              ))}
              </>
            )}
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Очередь отправки партнёрств</h2>
              <div className="flex gap-2">
                <Select value={queueView} onValueChange={(value) => setQueueView(value as typeof queueView)}>
                  <SelectTrigger className="w-[230px]">
                    <SelectValue placeholder="Фильтр очереди" />
                  </SelectTrigger>
                  <SelectContent>
                    {QUEUE_VIEW_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button variant="outline" onClick={() => void loadBatches()} disabled={loading}>
                  Обновить
                </Button>
                <Button onClick={createBatch} disabled={loading || queueReadyDrafts.length === 0}>
                  Создать batch ({queueReadyDrafts.length})
                </Button>
              </div>
            </div>
            {visibleBatches.length > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3">
                <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-3">
                  <div className="text-xs text-muted-foreground">
                    Выбрано queue-элементов: {selectedQueueIds.length}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Select value={bulkQueueStatus} onValueChange={setBulkQueueStatus}>
                      <SelectTrigger className="w-[220px] bg-white">
                        <SelectValue placeholder="Delivery-статус" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="sent">sent</SelectItem>
                        <SelectItem value="delivered">delivered</SelectItem>
                        <SelectItem value="failed">failed</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button variant="outline" onClick={bulkUpdateQueueDelivery} disabled={loading || selectedQueueIds.length === 0}>
                      Обновить статус
                    </Button>
                    <Button variant="outline" onClick={bulkDeleteQueueItems} disabled={loading || selectedQueueIds.length === 0}>
                      Удалить выбранные
                    </Button>
                  </div>
                </div>
              </div>
            )}
            {visibleBatches.length === 0 ? (
              <p className="text-sm text-muted-foreground">Batch пока нет.</p>
            ) : (
              <>
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={
                      visibleBatches.flatMap((batch) => (batch.items || []).map((item) => item.id)).length > 0 &&
                      visibleBatches.flatMap((batch) => (batch.items || []).map((item) => item.id)).every((id) => selectedQueueIds.includes(id))
                    }
                    onChange={(e) => toggleAllQueueSelection(e.target.checked)}
                  />
                  Выбрать все queue-элементы в текущем фильтре
                </label>
              {visibleBatches.map((batch) => (
                <div key={batch.id} className="rounded-lg border border-gray-200 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-semibold text-foreground">{batch.id}</div>
                      <div className="text-xs text-muted-foreground">
                        статус: {batch.status} · элементов: {(batch.items || []).length}
                      </div>
                    </div>
                    {batch.status === 'draft' && (
                      <Button size="sm" onClick={() => void approveBatch(batch.id)} disabled={loading}>
                        Утвердить batch
                      </Button>
                    )}
                  </div>
                  {(batch.items || []).length > 0 && (
                    <div className="mt-2 space-y-2">
                      {(batch.items || []).slice(0, 8).map((item) => (
                        <div key={item.id} className="rounded border border-gray-100 p-2 text-xs text-muted-foreground">
                          <div className="flex items-start gap-2">
                            <input
                              className="mt-0.5"
                              type="checkbox"
                              checked={selectedQueueIds.includes(item.id)}
                              onChange={(e) => toggleQueueSelection(item.id, e.target.checked)}
                            />
                            <div>
                              <div>
                                {item.lead_name || item.id} · {item.channel || '—'} · {item.delivery_status || '—'}
                                {item.error_text ? ` · ${item.error_text}` : ''}
                              </div>
                          {(item.latest_human_outcome || item.latest_outcome) && (
                            <div className="mt-1 text-emerald-700">
                              outcome: {item.latest_human_outcome || item.latest_outcome}
                            </div>
                          )}
                          {item.delivery_status === 'sent' && !(item.latest_human_outcome || item.latest_outcome) && (
                            <div className="mt-2 flex flex-wrap gap-1">
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 px-2"
                                onClick={() => void recordReaction(item.id)}
                                disabled={Boolean(sendQueueBusy[item.id])}
                              >
                                Авто outcome
                              </Button>
                              {OUTCOME_OPTIONS.map((outcome) => (
                                <Button
                                  key={`${item.id}-${outcome}`}
                                  size="sm"
                                  variant="outline"
                                  className="h-7 px-2"
                                  onClick={() => void recordReaction(item.id, outcome)}
                                  disabled={Boolean(sendQueueBusy[item.id])}
                                >
                                  {outcome}
                                </Button>
                              ))}
                            </div>
                          )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              </>
            )}
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Реакции и outcome</h2>
              <div className="flex gap-2">
                <Select value={reactionView} onValueChange={(value) => setReactionView(value as typeof reactionView)}>
                  <SelectTrigger className="w-[220px]">
                    <SelectValue placeholder="Фильтр outcome" />
                  </SelectTrigger>
                  <SelectContent>
                    {REACTION_VIEW_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button variant="outline" onClick={() => void loadBatches()} disabled={loading}>
                  Обновить
                </Button>
              </div>
            </div>
            {visibleReactions.length === 0 ? (
              <p className="text-sm text-muted-foreground">Реакций пока нет.</p>
            ) : (
              visibleReactions.slice(0, 20).map((reaction) => (
                <div key={reaction.id} className="rounded-lg border border-gray-200 p-3">
                  <div className="text-sm font-semibold">{reaction.lead_name || reaction.lead_id}</div>
                  <div className="text-xs text-muted-foreground">
                    batch: {reaction.batch_id || '—'} · канал: {reaction.channel || '—'} · delivery: {reaction.delivery_status || '—'}
                  </div>
                  {reaction.raw_reply && (
                    <div className="mt-2 text-sm text-foreground whitespace-pre-wrap">{reaction.raw_reply}</div>
                  )}
                  <div className="mt-2 text-xs text-muted-foreground">
                    AI: {reaction.classified_outcome || '—'} · Подтверждено: {reaction.human_confirmed_outcome || reaction.classified_outcome || '—'}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {OUTCOME_OPTIONS.map((outcome) => (
                      <Button
                        key={`${reaction.id}-${outcome}`}
                        size="sm"
                        variant={(reaction.human_confirmed_outcome || reaction.classified_outcome) === outcome ? 'default' : 'outline'}
                        className="h-7 px-2"
                        onClick={() => void confirmReaction(reaction.id, outcome)}
                        disabled={Boolean(reactionBusy[reaction.id])}
                      >
                        {outcome}
                      </Button>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </>
      )}

      {message && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
          {message}
        </div>
      )}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
    </div>
  );
};
