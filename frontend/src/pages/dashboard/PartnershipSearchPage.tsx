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
  city?: string;
  category?: string;
  source_url?: string;
  phone?: string;
  email?: string;
  website?: string;
  telegram_url?: string;
  whatsapp_url?: string;
  status?: string;
  partnership_stage?: string;
  selected_channel?: string;
  updated_at?: string;
  parse_task_id?: string;
  parse_status?: string;
  parse_updated_at?: string;
  parse_retry_after?: string;
  parse_error?: string;
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

const STAGE_OPTIONS = [
  { value: 'all', label: 'Все этапы' },
  { value: 'imported', label: 'Импортировано' },
  { value: 'audited', label: 'Аудит готов' },
  { value: 'matched', label: 'Матчинг готов' },
  { value: 'proposal_draft_ready', label: 'Черновик оффера готов' },
];
const OUTCOME_OPTIONS = ['positive', 'question', 'no_response', 'hard_no'] as const;

export const PartnershipSearchPage: React.FC = () => {
  const { currentBusinessId } = useOutletContext<any>();
  const [loading, setLoading] = useState(false);
  const [linksText, setLinksText] = useState('');
  const [geoCity, setGeoCity] = useState('');
  const [geoCategory, setGeoCategory] = useState('');
  const [geoQuery, setGeoQuery] = useState('');
  const [geoRadiusKm, setGeoRadiusKm] = useState('5');
  const [geoLimit, setGeoLimit] = useState('25');
  const [stage, setStage] = useState('all');
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<PartnershipLead[]>([]);
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [auditData, setAuditData] = useState<any>(null);
  const [matchData, setMatchData] = useState<any>(null);
  const [draftText, setDraftText] = useState('');
  const [drafts, setDrafts] = useState<PartnershipDraft[]>([]);
  const [batches, setBatches] = useState<PartnershipBatch[]>([]);
  const [queueReadyDrafts, setQueueReadyDrafts] = useState<PartnershipDraft[]>([]);
  const [reactions, setReactions] = useState<PartnershipReaction[]>([]);
  const [sendQueueBusy, setSendQueueBusy] = useState<Record<string, string>>({});
  const [reactionBusy, setReactionBusy] = useState<Record<string, string>>({});
  const [learningMetrics, setLearningMetrics] = useState<PartnershipLearningMetric[]>([]);
  const [health, setHealth] = useState<PartnershipHealth | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedLead = useMemo(
    () => items.find((item) => item.id === selectedLeadId) || null,
    [items, selectedLeadId]
  );

  const loadLeads = async () => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      params.set('business_id', currentBusinessId);
      if (stage !== 'all') params.set('stage', stage);
      if (query.trim()) params.set('q', query.trim());
      const data = await newAuth.makeRequest(`/partnership/leads?${params.toString()}`, { method: 'GET' });
      setItems(Array.isArray(data.items) ? data.items : []);
      if (selectedLeadId && !(data.items || []).some((x: any) => x.id === selectedLeadId)) {
        setSelectedLeadId(null);
      }
    } catch (e: any) {
      setError(e.message || 'Не удалось загрузить список партнёров');
    } finally {
      setLoading(false);
    }
  };

  const loadDrafts = async () => {
    if (!currentBusinessId) return;
    const data = await newAuth.makeRequest(`/partnership/drafts?business_id=${encodeURIComponent(currentBusinessId)}`, {
      method: 'GET',
    });
    setDrafts(Array.isArray(data.drafts) ? data.drafts : []);
  };

  const loadBatches = async () => {
    if (!currentBusinessId) return;
    const data = await newAuth.makeRequest(`/partnership/send-batches?business_id=${encodeURIComponent(currentBusinessId)}`, {
      method: 'GET',
    });
    setBatches(Array.isArray(data.batches) ? data.batches : []);
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

  useEffect(() => {
    void loadLeads();
    void loadDrafts();
    void loadBatches();
    void loadLearningMetrics();
    void loadHealth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentBusinessId, stage]);

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
    } catch (e: any) {
      setError(e.message || 'Не удалось импортировать ссылки');
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
          city,
          category,
          query: q,
          radius_km: Number.isFinite(radiusKm) ? radiusKm : 5,
          limit: Number.isFinite(limit) ? limit : 25,
        }),
      });
      const baseMsg = `Гео-поиск: импортировано ${data.imported_count || 0}, пропущено ${data.skipped_count || 0}, найдено источником ${data.source_total || 0}`;
      setMessage(data.warning ? `${baseMsg}. ${data.warning}` : baseMsg);
      await loadLeads();
      await loadDrafts();
      await loadBatches();
      await loadHealth();
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
    } catch (e: any) {
      setError(e.message || 'Не удалось сгенерировать первое письмо');
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
    } catch (e: any) {
      setError(e.message || 'Не удалось утвердить черновик');
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
    } catch (e: any) {
      setError(e.message || 'Не удалось утвердить batch');
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
        const md = String(data?.markdown_report || '');
        downloadTextFile(`partnership-export-${currentBusinessId}-${stamp}.md`, md, 'text/markdown;charset=utf-8');
      } else {
        downloadTextFile(
          `partnership-export-${currentBusinessId}-${stamp}.json`,
          JSON.stringify(data || {}, null, 2),
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
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <h2 className="text-lg font-semibold">Гео-поиск партнёров (OpenClaw)</h2>
            <p className="text-sm text-muted-foreground">
              Поиск ближайших компаний по городу/категории/запросу с автоматическим импортом в список партнёрств.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-2">
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
            </div>

            <div className="space-y-3">
              {items.length === 0 ? (
                <p className="text-sm text-muted-foreground">Список пуст.</p>
              ) : (
                items.map((item) => (
                  <div
                    key={item.id}
                    className={`rounded-lg border p-3 ${selectedLeadId === item.id ? 'border-primary' : 'border-gray-200'}`}
                  >
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                      <div>
                        <div className="font-semibold text-foreground">{item.name || 'Без названия'}</div>
                        <div className="text-sm text-muted-foreground">
                          {item.city || '—'} · {item.category || '—'} · этап: {item.partnership_stage || 'imported'}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Парсинг: {item.parse_status || 'не запускался'}
                          {item.parse_updated_at ? ` · ${new Date(item.parse_updated_at).toLocaleString('ru-RU')}` : ''}
                          {item.parse_retry_after ? ` · retry_after: ${new Date(item.parse_retry_after).toLocaleString('ru-RU')}` : ''}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Контакты: {item.phone || 'телефон —'} · {item.email || 'email —'} · {item.telegram_url ? 'telegram ✓' : 'telegram —'} · {item.whatsapp_url ? 'whatsapp ✓' : 'whatsapp —'}
                        </div>
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
                      </div>
                    </div>
                  </div>
                ))
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
              </div>
            )}

            {draftText && (
              <div className="rounded-lg border border-gray-200 p-3 bg-gray-50">
                <div className="font-medium mb-2">Первое письмо</div>
                <Textarea value={draftText} rows={8} readOnly />
              </div>
            )}
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Черновики партнёрского оффера</h2>
              <Button variant="outline" onClick={() => void loadDrafts()} disabled={loading}>
                Обновить
              </Button>
            </div>
            {drafts.length === 0 ? (
              <p className="text-sm text-muted-foreground">Черновиков пока нет.</p>
            ) : (
              drafts.map((draft) => (
                <div key={draft.id} className="rounded-lg border border-gray-200 p-3">
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
              ))
            )}
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Очередь отправки партнёрств</h2>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => void loadBatches()} disabled={loading}>
                  Обновить
                </Button>
                <Button onClick={createBatch} disabled={loading || queueReadyDrafts.length === 0}>
                  Создать batch ({queueReadyDrafts.length})
                </Button>
              </div>
            </div>
            {batches.length === 0 ? (
              <p className="text-sm text-muted-foreground">Batch пока нет.</p>
            ) : (
              batches.map((batch) => (
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
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Реакции и outcome</h2>
              <Button variant="outline" onClick={() => void loadBatches()} disabled={loading}>
                Обновить
              </Button>
            </div>
            {reactions.length === 0 ? (
              <p className="text-sm text-muted-foreground">Реакций пока нет.</p>
            ) : (
              reactions.slice(0, 20).map((reaction) => (
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
