import { useCallback, useEffect, useMemo, useState, type KeyboardEvent, type ReactNode } from 'react';
import { Link, Navigate, useOutletContext } from 'react-router-dom';
import {
  ArrowLeft,
  BarChart3,
  Check,
  ChevronRight,
  CircleAlert,
  Copy,
  ExternalLink,
  Loader2,
  MapPin,
  Megaphone,
  Plus,
  Search,
  Send,
  Sparkles,
  Users,
} from 'lucide-react';

import { DashboardPageHeader } from '@/components/dashboard/DashboardPrimitives';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { newAuth } from '@/lib/auth_new';
import { cn } from '@/lib/utils';

type DashboardContext = {
  currentBusinessId?: string | null;
  currentBusiness?: {
    creator_promotion_available?: boolean;
    city?: string;
    address?: string;
    name?: string;
  } | null;
};

type CreatorResult = {
  id: string;
  creator_profile_id: string;
  display_name: string;
  profile_type?: string;
  description?: string;
  primary_city?: string;
  primary_area?: string;
  platform?: string;
  canonical_url?: string;
  contactability?: string;
  score?: number;
  result_group?: string;
  shortlist_status?: string;
  reasons?: string[];
  score_breakdown?: Record<string, number>;
  public_metrics?: Record<string, number>;
  evidence?: Array<{ summary?: string; source_url?: string; observed_at?: string; confidence?: number }>;
};

type SearchJob = {
  id: string;
  status?: string;
  phase?: string;
  brief?: Record<string, unknown>;
  progress?: { found?: number; processed?: number };
  results?: CreatorResult[];
  results_count?: number;
  shortlisted_count?: number;
};

type CampaignCandidate = {
  id: string;
  display_name: string;
  status?: string;
  platform?: string;
  canonical_url?: string;
  workstream_id?: string | null;
  collaboration_id?: string | null;
  collaboration_status?: string | null;
};

type Campaign = {
  id: string;
  title: string;
  goal: string;
  status: string;
  candidates_count?: number;
  engaged_count?: number;
  candidates?: CampaignCandidate[];
  offer?: Record<string, unknown>;
  budget?: { maximum?: number; currency?: string };
  formats?: string[];
  period?: { description?: string };
  constraints?: { usage_rights?: { description?: string } };
  terms_version?: number;
  approved_terms_version?: number | null;
};

type OutreachPreview = {
  display_name: string;
  message: string;
  personalization?: { summary?: string; source_url?: string | null; confidence?: number | null };
  contact?: { value?: string | null; status?: 'confirmed' | 'public_unverified' | 'source_only' | 'missing'; source_url?: string | null };
  terms_review?: { checks?: Record<string, boolean>; missing?: string[] };
  requires_campaign_approval?: boolean;
};

type Deliverable = {
  id: string;
  platform: string;
  deliverable_type: string;
  verification_status: string;
  publication_url?: string | null;
  tracking?: {
    destination_url?: string | null;
    tracked_url?: string | null;
    promo_code?: string | null;
    cta?: string | null;
  };
  measurement_checkpoints?: Array<{
    checkpoint: '24h' | '7d' | '14d';
    due_at: string;
    status: 'pending' | 'completed' | 'skipped';
    completed_at?: string | null;
  }>;
};

type Collaboration = {
  id: string;
  display_name: string;
  status: string;
  deliverables?: Deliverable[];
  public_room_ready?: boolean;
};

type DeliverableDraft = {
  platform: string;
  deliverableType: string;
  publicationUrl: string;
  destinationUrl: string;
  promoCode: string;
  cta: string;
};

type MetricDraft = {
  reach: string;
  clicks: string;
  inquiries: string;
  bookings: string;
  placementCost: string;
};

type Metrics = {
  collaborations?: number;
  deliverables?: number;
  verified_deliverables?: number;
  reach?: number;
  clicks?: number;
  inquiries?: number;
  bookings?: number;
  placement_cost?: number;
  confirmed_revenue?: number;
  calculated?: {
    cpm?: number | null;
    cost_per_inquiry?: number | null;
    cost_per_booking?: number | null;
  };
  measurement_checkpoints?: {
    pending?: number;
    due?: number;
    completed?: number;
    next_due_at?: string | null;
  };
  disclaimer?: string;
};

type Overview = {
  feature_state?: { discovery?: boolean; outreach?: boolean; metrics?: boolean };
  latest_search?: SearchJob | null;
  campaigns?: Campaign[];
  collaborations?: Collaboration[];
  metrics?: Metrics;
  next_action?: string;
};

const defaultCampaignCurrency = (location: string) => /tallinn|таллин/i.test(location) ? 'EUR' : 'RUB';
const recommendedCampaignPeriod = 'Публикация в течение 14 дней после согласования; статистика через 24 часа, 7 и 14 дней.';
const recommendedUsageRights = 'Органический репост в собственных каналах бизнеса в течение 90 дней с указанием автора; без платного продвижения, монтажа и передачи третьим лицам.';

type WorkspaceSection = 'search' | 'campaigns' | 'collaborations' | 'results';

const statusLabel: Record<string, string> = {
  ready: 'Поиск завершён',
  partial: 'Найдена часть кандидатов',
  draft: 'Черновик',
  approved: 'Условия подтверждены',
  active: 'Активна',
  shortlisted: 'В shortlist',
  invitation_ready: 'Можно готовить сообщение',
  invited: 'Приглашён',
  replied: 'Получен ответ',
  negotiating: 'Переговоры',
  agreed: 'Условия согласованы',
  published: 'Опубликовано',
  measuring: 'Собираем результат',
  completed: 'Завершено',
  declined: 'Отказ',
  overdue: 'Требует внимания',
};

const groupLabel: Record<string, string> = {
  best_fit: 'Лучшее соответствие',
  strong_local: 'Сильная локальная площадка',
  precise_small_audience: 'Точная нишевая аудитория',
  needs_review: 'Нужно проверить',
  insufficient_data: 'Недостаточно данных',
  excluded: 'Не подходит',
};

const resultGroupOrder = ['best_fit', 'strong_local', 'precise_small_audience', 'needs_review', 'insufficient_data', 'excluded'];
const resultsPageSize = 30;

const nextCollaborationStatus: Record<string, { status: string; label: string }> = {
  draft: { status: 'invited', label: 'Отметить приглашённым' },
  invited: { status: 'replied', label: 'Зафиксировать ответ' },
  replied: { status: 'negotiating', label: 'Начать согласование' },
  negotiating: { status: 'agreed', label: 'Условия согласованы' },
  agreed: { status: 'awaiting_content', label: 'Ожидаем материал' },
  awaiting_content: { status: 'published', label: 'Материал опубликован' },
  published: { status: 'measuring', label: 'Собирать результат' },
  measuring: { status: 'completed', label: 'Завершить' },
};

const formatNumber = (value: unknown) => new Intl.NumberFormat('ru-RU').format(Number(value || 0));
const checkpointLabel = { '24h': '24 часа', '7d': '7 дней', '14d': '14 дней' };
const emptyDeliverableDraft = (): DeliverableDraft => ({ platform: 'telegram', deliverableType: 'post', publicationUrl: '', destinationUrl: '', promoCode: '', cta: '' });

const WorkspaceTabs = ({ section, onChange }: { section: WorkspaceSection; onChange: (section: WorkspaceSection) => void }) => {
  const items: Array<{ key: WorkspaceSection; label: string; icon: typeof Search }> = [
    { key: 'search', label: 'Поиск', icon: Search },
    { key: 'campaigns', label: 'Кампании', icon: Send },
    { key: 'collaborations', label: 'Коллаборации', icon: Users },
    { key: 'results', label: 'Результаты', icon: BarChart3 },
  ];
  const moveFocus = (event: KeyboardEvent<HTMLButtonElement>, key: WorkspaceSection) => {
    const currentIndex = items.findIndex((item) => item.key === key);
    let nextIndex = currentIndex;
    if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % items.length;
    else if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + items.length) % items.length;
    else if (event.key === 'Home') nextIndex = 0;
    else if (event.key === 'End') nextIndex = items.length - 1;
    else return;

    event.preventDefault();
    const nextItem = items[nextIndex];
    onChange(nextItem.key);
    event.currentTarget.parentElement
      ?.querySelector<HTMLButtonElement>(`#influencer-tab-${nextItem.key}`)
      ?.focus();
  };
  return (
    <div className="flex gap-1 overflow-x-auto rounded-2xl bg-slate-100 p-1" role="tablist" aria-label="Этап работы">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <button
            key={item.key}
            id={`influencer-tab-${item.key}`}
            type="button"
            role="tab"
            aria-selected={section === item.key}
            aria-controls={`influencer-panel-${item.key}`}
            tabIndex={section === item.key ? 0 : -1}
            onClick={() => onChange(item.key)}
            onKeyDown={(event) => moveFocus(event, item.key)}
            className={cn(
              'inline-flex min-h-11 flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-xl px-4 text-sm font-semibold transition-[background-color,box-shadow,color,transform] active:scale-[0.96]',
              section === item.key
                ? 'bg-white text-slate-950 shadow-[0_0_0_1px_rgba(15,23,42,0.05),0_2px_5px_rgba(15,23,42,0.08)]'
                : 'text-slate-500 hover:bg-white/60 hover:text-slate-800',
            )}
          >
            <Icon className="h-4 w-4" />{item.label}
          </button>
        );
      })}
    </div>
  );
};

const EmptyState = ({ icon: Icon, title, description, action }: { icon: typeof Search; title: string; description: string; action?: ReactNode }) => (
  <div className="rounded-[28px] bg-white px-6 py-12 text-center shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_12px_36px_-24px_rgba(15,23,42,0.24)]">
    <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-slate-100 text-slate-600"><Icon className="h-6 w-6" /></span>
    <h3 className="mt-5 text-balance text-xl font-semibold text-slate-950">{title}</h3>
    <p className="mx-auto mt-2 max-w-lg text-pretty text-sm leading-6 text-slate-500">{description}</p>
    {action ? <div className="mt-6">{action}</div> : null}
  </div>
);

export const InfluencerPromotionPage = () => {
  const { currentBusinessId, currentBusiness } = useOutletContext<DashboardContext>();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [searchJob, setSearchJob] = useState<SearchJob | null>(null);
  const [section, setSection] = useState<WorkspaceSection>('search');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [city, setCity] = useState(currentBusiness?.city || '');
  const [area, setArea] = useState('');
  const [audience, setAudience] = useState('');
  const [service, setService] = useState('');
  const [formats, setFormats] = useState('обзор, пост');
  const [budget, setBudget] = useState('');
  const [manualName, setManualName] = useState('');
  const [manualUrl, setManualUrl] = useState('');
  const [deliverableDrafts, setDeliverableDrafts] = useState<Record<string, DeliverableDraft>>({});
  const [metricDrafts, setMetricDrafts] = useState<Record<string, MetricDraft>>({});
  const [roomLinks, setRoomLinks] = useState<Record<string, string>>({});
  const [editingCampaignId, setEditingCampaignId] = useState('');
  const [campaignOffer, setCampaignOffer] = useState('');
  const [campaignBudget, setCampaignBudget] = useState('');
  const [campaignCurrency, setCampaignCurrency] = useState('RUB');
  const [campaignPeriod, setCampaignPeriod] = useState('');
  const [campaignUsageRights, setCampaignUsageRights] = useState('');
  const [visibleResultLimit, setVisibleResultLimit] = useState(resultsPageSize);
  const [outreachPreviews, setOutreachPreviews] = useState<Record<string, OutreachPreview>>({});
  const [contactConfirmationChecks, setContactConfirmationChecks] = useState<Record<string, boolean>>({});

  const request = useCallback(async (path: string, options?: RequestInit) => {
    const separator = path.includes('?') ? '&' : '?';
    return newAuth.makeRequest(`${path}${separator}business_id=${encodeURIComponent(currentBusinessId || '')}`, options);
  }, [currentBusinessId]);

  const loadOverview = useCallback(async () => {
    if (!currentBusinessId || currentBusiness?.creator_promotion_available !== true) return;
    setLoading(true);
    setError('');
    try {
      const response = await request('/promotion/influencers/overview');
      const nextOverview = response.overview || null;
      setOverview(nextOverview);
      if (nextOverview?.latest_search?.id) {
        const searchResponse = await request(`/promotion/influencers/searches/${nextOverview.latest_search.id}`);
        setSearchJob(searchResponse.search || null);
      } else {
        setSearchJob(null);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Не удалось загрузить продвижение через авторов.');
    } finally {
      setLoading(false);
    }
  }, [currentBusiness?.creator_promotion_available, currentBusinessId, request]);

  useEffect(() => { void loadOverview(); }, [loadOverview]);

  useEffect(() => { setVisibleResultLimit(resultsPageSize); }, [currentBusinessId, searchJob?.id]);

  useEffect(() => {
    if (!searchJob?.id || !['created', 'searching', 'enriching', 'checking'].includes(searchJob.status || '')) return undefined;
    const timer = window.setInterval(() => {
      void request(`/promotion/influencers/searches/${searchJob.id}`)
        .then((response) => setSearchJob(response.search || null))
        .catch((pollError) => setError(pollError instanceof Error ? pollError.message : 'Не удалось обновить ход поиска.'));
    }, 2000);
    return () => window.clearInterval(timer);
  }, [request, searchJob?.id, searchJob?.status]);

  const runSearch = async () => {
    if (!currentBusinessId) return;
    setBusy('search');
    setError('');
    setNotice('');
    try {
      const response = await newAuth.makeRequest('/promotion/influencers/searches', {
        method: 'POST',
        body: JSON.stringify({
          business_id: currentBusinessId,
          brief: {
            city,
            area,
            audience,
            service,
            formats: formats.split(',').map((item) => item.trim()).filter(Boolean),
            budget: budget ? { maximum: Number(budget), currency: 'RUB' } : {},
            goal: 'Получить локальный охват и обращения',
          },
        }),
      });
      setSearchJob(response.search || null);
      setNotice(response.search?.status === 'ready' ? 'Поиск завершён. Проверьте объяснения и соберите shortlist.' : 'Поиск запущен. Первые кандидаты появятся здесь автоматически.');
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : 'Не удалось выполнить поиск.');
    } finally {
      setBusy('');
    }
  };

  const updateShortlist = async (result: CreatorResult, shortlistStatus: string) => {
    if (!currentBusinessId) return;
    setBusy(`result:${result.id}`);
    setError('');
    try {
      const response = await newAuth.makeRequest(`/promotion/influencers/search-results/${result.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ business_id: currentBusinessId, shortlist_status: shortlistStatus }),
      });
      setSearchJob(response.search || null);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Не удалось обновить shortlist.');
    } finally {
      setBusy('');
    }
  };

  const addManualCreator = async () => {
    if (!currentBusinessId || !manualName.trim() || !manualUrl.trim()) return;
    setBusy('manual-creator');
    setError('');
    try {
      const response = await newAuth.makeRequest('/promotion/influencers/creators/manual', {
        method: 'POST',
        body: JSON.stringify({
          business_id: currentBusinessId,
          search_job_id: searchJob?.id,
          display_name: manualName.trim(),
          url: manualUrl.trim(),
          city,
          area,
          contactability: 'manual_only',
          formats: formats.split(',').map((item) => item.trim()).filter(Boolean),
        }),
      });
      if (response.search) setSearchJob(response.search);
      setManualName('');
      setManualUrl('');
      setNotice(searchJob ? 'Автор добавлен в текущий поиск и отмечен для ручной проверки.' : 'Публичная площадка сохранена. Запустите поиск, чтобы сравнить её с другими кандидатами.');
    } catch (manualError) {
      setError(manualError instanceof Error ? manualError.message : 'Не удалось добавить публичную площадку.');
    } finally {
      setBusy('');
    }
  };

  const importCreators = async (file: File) => {
    if (!currentBusinessId || !searchJob) return;
    setBusy('creator-import');
    setError('');
    try {
      const content = await file.text();
      const isJson = file.name.toLowerCase().endsWith('.json');
      const parsed = isJson ? JSON.parse(content) : null;
      const candidates = Array.isArray(parsed) ? parsed : Array.isArray(parsed?.candidates) ? parsed.candidates : undefined;
      const response = await newAuth.makeRequest('/promotion/influencers/creators/import', {
        method: 'POST',
        body: JSON.stringify({
          business_id: currentBusinessId,
          search_job_id: searchJob.id,
          format: isJson ? 'json' : 'csv',
          content: isJson ? undefined : content,
          candidates,
        }),
      });
      if (response.search) setSearchJob(response.search);
      setNotice(`Импортировано: ${Number(response.result?.imported_count || 0)}. Ошибок: ${Number(response.result?.error_count || 0)}.`);
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : 'Не удалось прочитать файл.');
    } finally {
      setBusy('');
    }
  };

  const createCampaign = async () => {
    if (!currentBusinessId || !searchJob) return;
    const shortlisted = (searchJob.results || []).filter((item) => item.shortlist_status === 'shortlisted');
    if (!shortlisted.length) {
      setError('Сначала добавьте хотя бы одного автора в shortlist.');
      return;
    }
    setBusy('campaign');
    setError('');
    try {
      await newAuth.makeRequest('/promotion/influencers/campaigns', {
        method: 'POST',
        body: JSON.stringify({
          business_id: currentBusinessId,
          search_job_id: searchJob.id,
          search_result_ids: shortlisted.map((item) => item.id),
          title: `Локальное продвижение · ${currentBusiness?.name || city || 'кампания'}`,
          goal: 'Получить локальный охват и обращения',
          geography: { city, area },
          audience: { description: audience },
          formats: formats.split(',').map((item) => item.trim()).filter(Boolean),
          budget: budget ? { maximum: Number(budget), currency: defaultCampaignCurrency(`${city} ${currentBusiness?.name || ''}`) } : {},
          offer: { service, compensation_requires_confirmation: true },
        }),
      });
      setSection('campaigns');
      setNotice('Кампания создана как черновик. Проверьте условия перед подготовкой сообщений.');
      await loadOverview();
    } catch (campaignError) {
      setError(campaignError instanceof Error ? campaignError.message : 'Не удалось создать кампанию.');
    } finally {
      setBusy('');
    }
  };

  const approveCampaign = async (campaign: Campaign) => {
    if (!currentBusinessId) return;
    setBusy(`approve:${campaign.id}`);
    setError('');
    try {
      await newAuth.makeRequest(`/promotion/influencers/campaigns/${campaign.id}/approve`, {
        method: 'POST', body: JSON.stringify({ business_id: currentBusinessId }),
      });
      setNotice('Условия подтверждены. Это ничего не отправило — теперь можно готовить сообщение для выбранного автора.');
      await loadOverview();
    } catch (approvalError) {
      setError(approvalError instanceof Error ? approvalError.message : 'Не удалось подтвердить кампанию.');
    } finally {
      setBusy('');
    }
  };

  const startCampaignEdit = (campaign: Campaign) => {
    setEditingCampaignId(campaign.id);
    setCampaignOffer(String(campaign.offer?.service || campaign.offer?.details || ''));
    setCampaignBudget(campaign.budget?.maximum == null ? '' : String(campaign.budget.maximum));
    setCampaignCurrency(campaign.budget?.currency || defaultCampaignCurrency(`${currentBusiness?.city || city} ${currentBusiness?.name || ''}`));
    setCampaignPeriod(campaign.period?.description || '');
    setCampaignUsageRights(campaign.constraints?.usage_rights?.description || '');
  };

  const saveCampaignTerms = async (campaign: Campaign) => {
    if (!currentBusinessId) return;
    setBusy(`campaign-edit:${campaign.id}`);
    setError('');
    try {
      await newAuth.makeRequest(`/promotion/influencers/campaigns/${campaign.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          business_id: currentBusinessId,
          offer: { ...(campaign.offer || {}), details: campaignOffer.trim() },
          budget: campaignBudget ? { maximum: Number(campaignBudget), currency: campaignCurrency } : {},
          period: { description: campaignPeriod.trim() },
          constraints: {
            ...(campaign.constraints || {}),
            usage_rights: { description: campaignUsageRights.trim() },
          },
        }),
      });
      setEditingCampaignId('');
      setNotice('Условия обновлены. Предыдущее подтверждение снято — проверьте и подтвердите новую версию.');
      await loadOverview();
    } catch (campaignError) {
      setError(campaignError instanceof Error ? campaignError.message : 'Не удалось обновить условия.');
    } finally {
      setBusy('');
    }
  };

  const prepareOutreach = async (campaign: Campaign, candidate: CampaignCandidate) => {
    if (!currentBusinessId) return;
    setBusy(`outreach:${candidate.id}`);
    setError('');
    try {
      const response = await newAuth.makeRequest(`/promotion/influencers/campaigns/${campaign.id}/candidates/${candidate.id}/prepare-outreach`, {
        method: 'POST', body: JSON.stringify({ business_id: currentBusinessId }),
      });
      setNotice(response.prepared?.next_action || 'Получатель подготовлен. Проверьте сообщение перед отправкой.');
      await loadOverview();
    } catch (outreachError) {
      setError(outreachError instanceof Error ? outreachError.message : 'Не удалось подготовить контакт.');
    } finally {
      setBusy('');
    }
  };

  const loadOutreachPreview = async (campaign: Campaign, candidate: CampaignCandidate) => {
    const previewKey = `${campaign.id}:${candidate.id}`;
    if (outreachPreviews[previewKey]) {
      setOutreachPreviews((current) => {
        const next = { ...current };
        delete next[previewKey];
        return next;
      });
      return;
    }
    setBusy(`preview:${candidate.id}`);
    setError('');
    try {
      const response = await request(`/promotion/influencers/campaigns/${campaign.id}/candidates/${candidate.id}/outreach-preview`);
      if (response.preview) setOutreachPreviews((current) => ({ ...current, [previewKey]: response.preview }));
    } catch (previewError) {
      setError(previewError instanceof Error ? previewError.message : 'Не удалось подготовить превью сообщения.');
    } finally {
      setBusy('');
    }
  };

  const confirmContact = async (campaign: Campaign, candidate: CampaignCandidate, preview: OutreachPreview) => {
    if (!currentBusinessId) return;
    const previewKey = `${campaign.id}:${candidate.id}`;
    setBusy(`contact-confirm:${candidate.id}`);
    setError('');
    try {
      const response = await newAuth.makeRequest(`/promotion/influencers/campaigns/${campaign.id}/candidates/${candidate.id}/confirm-contact`, {
        method: 'POST',
        body: JSON.stringify({
          business_id: currentBusinessId,
          confirmed: true,
          confirmation_note: 'Контакт вручную сопоставлен с автором, каналом или указанным представителем.',
          confirmation_source_url: preview.contact?.source_url || preview.personalization?.source_url || undefined,
        }),
      });
      if (response.preview) setOutreachPreviews((current) => ({ ...current, [previewKey]: response.preview }));
      setNotice('Контакт подтверждён владельцем бизнеса. Сообщение не отправлено.');
    } catch (confirmationError) {
      setError(confirmationError instanceof Error ? confirmationError.message : 'Не удалось подтвердить контакт.');
    } finally {
      setBusy('');
    }
  };

  const createCollaboration = async (campaign: Campaign, candidate: CampaignCandidate) => {
    if (!currentBusinessId) return;
    setBusy(`collaboration:${candidate.id}`);
    setError('');
    try {
      await newAuth.makeRequest(`/promotion/influencers/campaigns/${campaign.id}/candidates/${candidate.id}/collaboration`, {
        method: 'POST',
        body: JSON.stringify({
          business_id: currentBusinessId,
          status: 'negotiating',
          terms: { source: 'approved_campaign', requires_manual_confirmation: true },
        }),
      });
      setSection('collaborations');
      setNotice('Коллаборация создана. Зафиксируйте согласованные условия и следующий этап.');
      await loadOverview();
    } catch (collaborationError) {
      setError(collaborationError instanceof Error ? collaborationError.message : 'Не удалось создать коллаборацию.');
    } finally {
      setBusy('');
    }
  };

  const updateCollaborationStatus = async (collaboration: Collaboration, status: string) => {
    if (!currentBusinessId) return;
    setBusy(`collaboration-status:${collaboration.id}`);
    setError('');
    try {
      await newAuth.makeRequest(`/promotion/influencers/collaborations/${collaboration.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ business_id: currentBusinessId, status }),
      });
      setNotice('Этап коллаборации обновлён.');
      await loadOverview();
    } catch (statusError) {
      setError(statusError instanceof Error ? statusError.message : 'Не удалось обновить этап.');
    } finally {
      setBusy('');
    }
  };

  const addDeliverable = async (collaboration: Collaboration) => {
    if (!currentBusinessId) return;
    const draft = deliverableDrafts[collaboration.id] || emptyDeliverableDraft();
    setBusy(`deliverable:${collaboration.id}`);
    setError('');
    try {
      await newAuth.makeRequest(`/promotion/influencers/collaborations/${collaboration.id}/deliverables`, {
        method: 'POST',
        body: JSON.stringify({
          business_id: currentBusinessId,
          platform: draft.platform,
          deliverable_type: draft.deliverableType,
          publication_url: draft.publicationUrl.trim() || undefined,
          required_elements: [],
          usage_rights: { confirmed: false },
          tracking: {
            destination_url: draft.destinationUrl.trim() || undefined,
            promo_code: draft.promoCode.trim() || undefined,
            cta: draft.cta.trim() || undefined,
          },
        }),
      });
      setDeliverableDrafts((current) => ({ ...current, [collaboration.id]: emptyDeliverableDraft() }));
      setNotice(draft.publicationUrl.trim() ? 'Ссылка сохранена. Проверьте публикацию и подтвердите proof.' : 'Материал и план измерения сохранены. Права на повторное использование не назначены.');
      await loadOverview();
    } catch (deliverableError) {
      setError(deliverableError instanceof Error ? deliverableError.message : 'Не удалось добавить материал.');
    } finally {
      setBusy('');
    }
  };

  const verifyDeliverable = async (deliverable: Deliverable) => {
    if (!currentBusinessId) return;
    setBusy(`verify:${deliverable.id}`);
    setError('');
    try {
      await newAuth.makeRequest(`/promotion/influencers/deliverables/${deliverable.id}/verification`, {
        method: 'PATCH',
        body: JSON.stringify({
          business_id: currentBusinessId,
          verification_status: 'verified',
          proof: { publication_url: deliverable.publication_url },
        }),
      });
      setNotice('Публикация подтверждена. Теперь можно добавлять статистику размещения.');
      await loadOverview();
    } catch (verificationError) {
      setError(verificationError instanceof Error ? verificationError.message : 'Не удалось подтвердить материал.');
    } finally {
      setBusy('');
    }
  };

  const addMetrics = async (deliverable: Deliverable, checkpoint?: '24h' | '7d' | '14d') => {
    if (!currentBusinessId) return;
    const draft = metricDrafts[deliverable.id] || { reach: '', clicks: '', inquiries: '', bookings: '', placementCost: '' };
    setBusy(`metrics:${deliverable.id}`);
    setError('');
    try {
      await newAuth.makeRequest(`/promotion/influencers/deliverables/${deliverable.id}/metrics`, {
        method: 'POST',
        body: JSON.stringify({
          business_id: currentBusinessId,
          source_type: 'business_reported',
          confidence: 1,
          reach: Number(draft.reach || 0),
          clicks: Number(draft.clicks || 0),
          inquiries: Number(draft.inquiries || 0),
          bookings: Number(draft.bookings || 0),
          placement_cost: draft.placementCost ? Number(draft.placementCost) : undefined,
          checkpoint,
        }),
      });
      setNotice(checkpoint ? `Снимок «${checkpointLabel[checkpoint]}» сохранён как данные бизнеса.` : 'Статистика сохранена как данные бизнеса. Источник показателей зафиксирован.');
      await loadOverview();
    } catch (metricsError) {
      setError(metricsError instanceof Error ? metricsError.message : 'Не удалось сохранить статистику.');
    } finally {
      setBusy('');
    }
  };

  const createCreatorRoom = async (collaboration: Collaboration) => {
    if (!currentBusinessId) return;
    setBusy(`room:${collaboration.id}`);
    setError('');
    try {
      const response = await newAuth.makeRequest(`/promotion/influencers/collaborations/${collaboration.id}/room`, {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId }),
      });
      const publicUrl = String(response.room?.public_url || '');
      setRoomLinks((current) => ({ ...current, [collaboration.id]: publicUrl }));
      setNotice('Приватная ссылка создана. Её отправка остаётся под вашим контролем.');
      await loadOverview();
    } catch (roomError) {
      setError(roomError instanceof Error ? roomError.message : 'Не удалось создать приватную ссылку.');
    } finally {
      setBusy('');
    }
  };

  const results = useMemo(() => searchJob?.results || [], [searchJob?.results]);
  const shortlistedCount = results.filter((item) => item.shortlist_status === 'shortlisted').length;
  const visibleResults = useMemo(() => [...results]
    .sort((first, second) => {
      const shortlistDifference = Number(second.shortlist_status === 'shortlisted') - Number(first.shortlist_status === 'shortlisted');
      if (shortlistDifference) return shortlistDifference;
      const firstGroupIndex = resultGroupOrder.indexOf(first.result_group || 'needs_review');
      const secondGroupIndex = resultGroupOrder.indexOf(second.result_group || 'needs_review');
      const groupDifference = (firstGroupIndex < 0 ? resultGroupOrder.length : firstGroupIndex) - (secondGroupIndex < 0 ? resultGroupOrder.length : secondGroupIndex);
      if (groupDifference) return groupDifference;
      return Number(second.score || 0) - Number(first.score || 0);
    })
    .slice(0, visibleResultLimit), [results, visibleResultLimit]);
  const groupedResults = useMemo(() => {
    const groups: Record<string, CreatorResult[]> = {};
    for (const result of visibleResults) {
      const key = result.result_group || 'needs_review';
      groups[key] = [...(groups[key] || []), result];
    }
    return groups;
  }, [visibleResults]);

  if (!currentBusinessId) {
    return <div className="py-16 text-center text-sm text-slate-500">Выберите бизнес для поиска локальных авторов.</div>;
  }
  if (currentBusiness?.creator_promotion_available !== true) {
    return <Navigate to="/dashboard/partnerships" replace />;
  }

  return (
    <div className="space-y-6 pb-12 antialiased">
      <Link to="/dashboard/promotion" className="inline-flex min-h-10 items-center gap-2 rounded-xl px-2 text-sm font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900">
        <ArrowLeft className="h-4 w-4" />Все способы продвижения
      </Link>
      <DashboardPageHeader
        eyebrow="Продвижение"
        title="Локальные авторы"
        description="Найдите людей и сообщества, которые уже влияют на выбор вашей аудитории. LocalOS объяснит соответствие, поможет согласовать коллаборацию и собрать подтверждённый результат."
        icon={Megaphone}
        actions={<Button onClick={() => setSection('search')} className="min-h-11 rounded-xl bg-slate-950 px-5 text-white active:scale-[0.96] transition-transform"><Search className="mr-2 h-4 w-4" />Найти авторов</Button>}
      />

      <section className="rounded-[28px] bg-slate-950 p-3 text-white shadow-[0_16px_44px_-26px_rgba(15,23,42,0.72)]">
        <div className="rounded-2xl bg-white/[0.07] px-5 py-4 sm:flex sm:items-center sm:justify-between sm:gap-6">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Следующий шаг</div>
            <div className="mt-2 text-balance text-xl font-semibold">{overview?.next_action || 'Запустить первый поиск локальных авторов'}</div>
            <p className="mt-2 text-pretty text-sm leading-6 text-slate-300">Ни одно сообщение или размещение не запускается без вашего подтверждения.</p>
          </div>
          <div className="mt-4 flex shrink-0 items-center gap-3 sm:mt-0">
            <div className="text-right"><div className="text-2xl font-semibold tabular-nums">{formatNumber(results.length)}</div><div className="text-xs text-slate-400">найдено</div></div>
            <div className="h-10 w-px bg-white/10" />
            <div className="text-right"><div className="text-2xl font-semibold tabular-nums">{formatNumber(shortlistedCount)}</div><div className="text-xs text-slate-400">в shortlist</div></div>
          </div>
        </div>
      </section>

      <WorkspaceTabs section={section} onChange={setSection} />

      {error ? <div role="alert" className="flex flex-col gap-3 rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-800 shadow-[0_0_0_1px_rgba(225,29,72,0.12)] sm:flex-row sm:items-center"><div className="flex min-w-0 flex-1 gap-3"><CircleAlert className="mt-0.5 h-4 w-4 shrink-0" /><span>{error}</span></div><Button variant="outline" onClick={() => void loadOverview()} disabled={loading} className="min-h-10 shrink-0 rounded-xl border-rose-200 bg-white text-rose-900 hover:bg-rose-100">Повторить</Button></div> : null}
      {notice ? <div aria-live="polite" className="flex gap-3 rounded-2xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800 shadow-[0_0_0_1px_rgba(5,150,105,0.12)]"><Check className="mt-0.5 h-4 w-4 shrink-0" /><span>{notice}</span></div> : null}

      {loading ? (
        <div className="grid min-h-64 place-items-center rounded-[28px] bg-white shadow-[0_0_0_1px_rgba(15,23,42,0.06)]"><div className="text-center text-sm text-slate-500"><Loader2 className="mx-auto mb-3 h-6 w-6 animate-spin motion-reduce:animate-none" />Загружаем рабочее пространство</div></div>
      ) : null}

      {!loading && section === 'search' ? (
        <div id="influencer-panel-search" role="tabpanel" aria-labelledby="influencer-tab-search" className="space-y-6">
          <section className="rounded-[28px] bg-white p-3 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_12px_36px_-24px_rgba(15,23,42,0.24)]">
            <div className="rounded-2xl bg-slate-50 p-5 sm:p-6">
              <div className="flex items-start gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-white text-slate-700 shadow-[0_0_0_1px_rgba(15,23,42,0.06)]"><MapPin className="h-5 w-5" /></span><div><h2 className="text-balance text-xl font-semibold text-slate-950">Кого нужно найти</h2><p className="mt-1 text-pretty text-sm leading-6 text-slate-500">LocalOS начнёт с местных каналов и публикаций о районе, а не с общего каталога блогеров.</p></div></div>
              <div className="mt-6 grid gap-4 md:grid-cols-2">
                <label className="text-sm font-medium text-slate-700">Город<Input value={city} onChange={(event) => setCity(event.target.value)} placeholder="Санкт-Петербург" className="mt-2 min-h-11 rounded-xl bg-white" /></label>
                <label className="text-sm font-medium text-slate-700">Район или радиус<Input value={area} onChange={(event) => setArea(event.target.value)} placeholder="Приморский район, до 5 км" className="mt-2 min-h-11 rounded-xl bg-white" /></label>
                <label className="text-sm font-medium text-slate-700 md:col-span-2">Аудитория<Textarea value={audience} onChange={(event) => setAudience(event.target.value)} placeholder="Например: родители детей 2–12 лет, живущие рядом" className="mt-2 min-h-24 rounded-xl bg-white" /></label>
                <label className="text-sm font-medium text-slate-700">Услуга или повод<Input value={service} onChange={(event) => setService(event.target.value)} placeholder="Первая стрижка ребёнка" className="mt-2 min-h-11 rounded-xl bg-white" /></label>
                <label className="text-sm font-medium text-slate-700">Форматы<Input value={formats} onChange={(event) => setFormats(event.target.value)} placeholder="обзор, пост, визит" className="mt-2 min-h-11 rounded-xl bg-white" /></label>
                <label className="text-sm font-medium text-slate-700">Максимальный бюджет, ₽<Input value={budget} onChange={(event) => setBudget(event.target.value)} inputMode="decimal" placeholder="Можно оставить пустым" className="mt-2 min-h-11 rounded-xl bg-white tabular-nums" /></label>
              </div>
              <div className="mt-6 flex flex-wrap items-center gap-3"><Button onClick={() => void runSearch()} disabled={busy === 'search' || !city.trim() || overview?.feature_state?.discovery === false} className="min-h-12 rounded-xl bg-slate-950 px-5 text-white active:scale-[0.96] transition-transform">{busy === 'search' ? <Loader2 className="mr-2 h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Search className="mr-2 h-4 w-4" />}{busy === 'search' ? 'Ищем и проверяем…' : overview?.feature_state?.discovery === false ? 'Поиск пока закрыт' : 'Запустить поиск'}</Button><span className="text-pretty text-xs leading-5 text-slate-500">Поиск использует только разрешённые публичные источники и сохраняет происхождение каждого факта.</span></div>
            </div>
          </section>

          <section className="rounded-2xl bg-white p-4 shadow-[0_0_0_1px_rgba(15,23,42,0.06)]">
            <div className="text-sm font-semibold text-slate-900">Уже знаете подходящего автора?</div>
            <p className="mt-1 text-pretty text-xs leading-5 text-slate-500">{searchJob ? 'Добавьте публичную ссылку вручную. Площадка не станет получателем сообщения, пока контакт не будет отдельно проверен.' : 'Сначала запустите поиск — затем сможете добавить известную площадку в тот же список для сравнения.'}</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)_auto]"><Input value={manualName} onChange={(event) => setManualName(event.target.value)} placeholder="Имя или название площадки" className="min-h-11 rounded-xl" /><Input value={manualUrl} onChange={(event) => setManualUrl(event.target.value)} placeholder="https://t.me/…" className="min-h-11 rounded-xl" /><Button variant="outline" onClick={() => void addManualCreator()} disabled={busy === 'manual-creator' || !searchJob || !manualName.trim() || !manualUrl.trim()} className="min-h-11 rounded-xl">{busy === 'manual-creator' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}Добавить</Button></div>
            <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-slate-100 pt-3"><label className={cn('inline-flex min-h-10 cursor-pointer items-center rounded-xl border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700 hover:bg-slate-50', (!searchJob || busy === 'creator-import') && 'pointer-events-none opacity-50')}><input type="file" accept=".csv,.json,text/csv,application/json" className="sr-only" disabled={!searchJob || busy === 'creator-import'} onChange={(event) => { const file = event.target.files?.[0]; if (file) void importCreators(file); event.target.value = ''; }} />{busy === 'creator-import' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}Импорт CSV/JSON</label><span className="text-xs text-slate-500">Поля: display_name, url, city, area, topics, formats.</span></div>
          </section>

          {results.length ? (
            <section className="space-y-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><h2 className="text-balance text-2xl font-semibold text-slate-950">Кандидаты</h2><p className="mt-1 text-pretty text-sm text-slate-500">Сначала показаны shortlist и лучшие совпадения: <span className="tabular-nums">{visibleResults.length}</span> из <span className="tabular-nums">{results.length}</span>. Проверяйте доказательства и собирайте небольшой shortlist для конкретной задачи.</p></div><Button onClick={() => void createCampaign()} disabled={!shortlistedCount || busy === 'campaign'} className="min-h-11 rounded-xl bg-amber-600 px-5 text-white hover:bg-amber-700 active:scale-[0.96] transition-transform">{busy === 'campaign' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}Создать кампанию · <span className="ml-1 tabular-nums">{shortlistedCount}</span></Button></div>
              {Object.entries(groupedResults).map(([group, items]) => (
                <div key={group} className="space-y-3"><h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-slate-500">{groupLabel[group] || group} · <span className="tabular-nums">{items.length}</span></h3><div className="grid gap-3 lg:grid-cols-2">{items.map((result) => (
                  <article key={result.id} className="rounded-[24px] bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_8px_24px_-20px_rgba(15,23,42,0.22)]">
                    <div className="flex items-start gap-4"><div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-amber-100 text-lg font-semibold text-amber-900">{String(result.display_name || '?').slice(0, 1).toUpperCase()}</div><div className="min-w-0 flex-1"><div className="flex items-start justify-between gap-3"><div><h4 className="text-balance font-semibold text-slate-950">{result.display_name}</h4><p className="mt-1 text-xs text-slate-500">{[result.platform, result.primary_city, result.primary_area].filter(Boolean).join(' · ') || 'География требует проверки'}</p></div><span className="rounded-full bg-slate-950 px-3 py-1 text-sm font-semibold text-white tabular-nums">{result.score || 0}</span></div></div></div>
                    <ul className="mt-4 space-y-2 text-sm leading-5 text-slate-600">{(result.reasons || []).slice(0, 4).map((reason) => <li key={reason} className="flex gap-2 text-pretty"><Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" /><span>{reason}</span></li>)}</ul>
                    {result.evidence?.[0]?.summary ? <div className="mt-4 rounded-xl bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500"><span className="font-semibold text-slate-700">Публичное доказательство:</span> {result.evidence[0].summary}</div> : null}
                    <div className="mt-5 flex flex-wrap items-center justify-between gap-3">{result.canonical_url ? <a href={result.canonical_url} target="_blank" rel="noreferrer" aria-label={`Открыть источник: ${result.display_name}`} className="inline-flex min-h-10 items-center gap-2 rounded-xl px-2 text-sm font-medium text-slate-500 hover:bg-slate-50 hover:text-slate-900">Открыть источник<ExternalLink className="h-4 w-4" /></a> : <span className="text-xs text-slate-400">Ссылка не подтверждена</span>}<div className="flex gap-2"><Button variant="outline" aria-label={`Не подходит: ${result.display_name}`} onClick={() => void updateShortlist(result, 'rejected')} disabled={busy === `result:${result.id}`} className="min-h-10 rounded-xl active:scale-[0.96] transition-transform">Не подходит</Button><Button aria-label={`${result.shortlist_status === 'shortlisted' ? 'Убрать из shortlist' : 'Добавить в shortlist'}: ${result.display_name}`} onClick={() => void updateShortlist(result, result.shortlist_status === 'shortlisted' ? 'suggested' : 'shortlisted')} disabled={busy === `result:${result.id}`} className={cn('min-h-10 rounded-xl active:scale-[0.96] transition-transform', result.shortlist_status === 'shortlisted' ? 'bg-emerald-600 text-white hover:bg-emerald-700' : 'bg-slate-950 text-white')}>{result.shortlist_status === 'shortlisted' ? <Check className="mr-2 h-4 w-4" /> : <Plus className="mr-2 h-4 w-4" />}{result.shortlist_status === 'shortlisted' ? 'В shortlist' : 'Добавить'}</Button></div></div>
                  </article>
                ))}</div></div>
              ))}
              {visibleResults.length < results.length ? <div className="flex justify-center"><Button variant="outline" onClick={() => setVisibleResultLimit((current) => current + resultsPageSize)} className="min-h-11 rounded-xl bg-white px-5">Показать ещё <span className="tabular-nums">{Math.min(resultsPageSize, results.length - visibleResults.length)}</span></Button></div> : null}
            </section>
          ) : ['created', 'searching', 'enriching', 'checking'].includes(searchJob?.status || '') ? <EmptyState icon={Loader2} title="Ищем и проверяем площадки" description="Можно перейти в другой раздел. Поиск продолжится в фоне, а найденные кандидаты появятся здесь автоматически." /> : <EmptyState icon={Search} title="Подходящих авторов ещё не искали" description="Укажите аудиторию и район. LocalOS проверит существующие публичные источники, объяснит соответствие и покажет, где данных недостаточно." />}
        </div>
      ) : null}

      {!loading && section === 'campaigns' ? (
        <div id="influencer-panel-campaigns" role="tabpanel" aria-labelledby="influencer-tab-campaigns" className="space-y-4">{(overview?.campaigns || []).length ? (overview?.campaigns || []).map((campaign) => (
          <section key={campaign.id} className="rounded-[28px] bg-white p-3 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_10px_30px_-24px_rgba(15,23,42,0.24)]">
            <div className="rounded-2xl bg-slate-50 p-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div><span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{statusLabel[campaign.status] || campaign.status}</span><h2 className="mt-2 text-balance text-xl font-semibold text-slate-950">{campaign.title}</h2><p className="mt-2 text-pretty text-sm text-slate-600">{campaign.goal}</p></div>
                <div className="flex gap-5 text-right"><div><div className="text-2xl font-semibold tabular-nums">{campaign.candidates_count || campaign.candidates?.length || 0}</div><div className="text-xs text-slate-500">авторов</div></div><div><div className="text-2xl font-semibold tabular-nums">{campaign.engaged_count || 0}</div><div className="text-xs text-slate-500">ответили</div></div></div>
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500"><span>Версия условий: <span className="tabular-nums">{campaign.terms_version || 1}</span></span><Button variant="outline" onClick={() => startCampaignEdit(campaign)} className="min-h-9 rounded-xl bg-white">Изменить условия</Button></div>
              {editingCampaignId === campaign.id ? <div className="mt-4 rounded-2xl bg-white p-4 shadow-[0_0_0_1px_rgba(15,23,42,0.06)]"><div className="mb-4 flex flex-col gap-2 rounded-xl bg-amber-50 p-3 sm:flex-row sm:items-center sm:justify-between"><p className="text-xs leading-5 text-amber-950">Можно подставить безопасный пилотный шаблон сроков и прав. Бюджет и предложение останутся без изменений.</p><Button variant="outline" onClick={() => { if (!campaignPeriod.trim()) setCampaignPeriod(recommendedCampaignPeriod); if (!campaignUsageRights.trim()) setCampaignUsageRights(recommendedUsageRights); }} className="min-h-10 shrink-0 rounded-xl bg-white">Заполнить рекомендуемые условия</Button></div><div className="grid gap-3 sm:grid-cols-2"><label className="text-sm font-medium text-slate-700">Формат и предложение<Input value={campaignOffer} onChange={(event) => setCampaignOffer(event.target.value)} placeholder="Что получает автор и что ожидает бизнес" className="mt-2 min-h-11 rounded-xl" /></label><div className="grid grid-cols-[minmax(0,1fr)_7rem] gap-2"><label className="text-sm font-medium text-slate-700">Максимальный бюджет<Input value={campaignBudget} onChange={(event) => setCampaignBudget(event.target.value)} inputMode="decimal" placeholder="Например, 15 000" className="mt-2 min-h-11 rounded-xl" /></label><label className="text-sm font-medium text-slate-700">Валюта<select aria-label="Валюта бюджета" value={campaignCurrency} onChange={(event) => setCampaignCurrency(event.target.value)} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-slate-900"><option value="RUB">RUB</option><option value="EUR">EUR</option></select></label></div><label className="text-sm font-medium text-slate-700">Сроки<Input value={campaignPeriod} onChange={(event) => setCampaignPeriod(event.target.value)} placeholder="Например, публикация до 15 сентября" className="mt-2 min-h-11 rounded-xl" /></label><label className="text-sm font-medium text-slate-700">Права на материал<Input value={campaignUsageRights} onChange={(event) => setCampaignUsageRights(event.target.value)} placeholder="Например, репост в соцсетях 3 месяца" className="mt-2 min-h-11 rounded-xl" /></label></div><p className="mt-3 text-xs leading-5 text-slate-500">Сохранение создаст новую версию и снимет прежнее подтверждение. Подтвердить кампанию можно только после заполнения всех четырёх условий.</p><div className="mt-3 flex flex-wrap gap-2"><Button onClick={() => void saveCampaignTerms(campaign)} disabled={busy === `campaign-edit:${campaign.id}`} className="min-h-10 rounded-xl bg-slate-950 text-white">{busy === `campaign-edit:${campaign.id}` ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}Сохранить новую версию</Button><Button variant="ghost" onClick={() => setEditingCampaignId('')} className="min-h-10 rounded-xl">Отмена</Button></div></div> : null}
              {campaign.status === 'draft' || campaign.status === 'needs_review' ? <div className="mt-5 rounded-2xl bg-white p-4 shadow-[0_0_0_1px_rgba(15,23,42,0.06)]"><p className="text-pretty text-sm leading-6 text-slate-600">Проверьте формат, бюджет, сроки и права на материалы. Подтверждение условий не отправляет сообщения.</p><Button onClick={() => void approveCampaign(campaign)} disabled={busy === `approve:${campaign.id}`} className="mt-4 min-h-11 rounded-xl bg-slate-950 text-white active:scale-[0.96] transition-transform">{busy === `approve:${campaign.id}` ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}Подтвердить условия</Button></div> : null}
            </div>
            {(campaign.candidates || []).length ? <div className="divide-y divide-slate-100 px-3">{(campaign.candidates || []).map((candidate) => {
              const previewKey = `${campaign.id}:${candidate.id}`;
              const preview = outreachPreviews[previewKey];
              const contactLabel = preview?.contact?.status === 'confirmed' ? 'Контакт подтверждён' : preview?.contact?.status === 'public_unverified' ? 'Публичный контакт — принадлежность не подтверждена' : preview?.contact?.status === 'source_only' ? 'Есть только контакт площадки' : 'Контакт автора не подтверждён';
              return <div key={candidate.id} className="py-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><div className="font-medium text-slate-950">{candidate.display_name}</div><div className="mt-1 text-xs text-slate-500">{[candidate.platform, statusLabel[candidate.collaboration_status || candidate.status || ''] || candidate.collaboration_status || candidate.status].filter(Boolean).join(' · ')}</div></div><div className="flex flex-wrap items-center gap-2">{candidate.canonical_url ? <a href={candidate.canonical_url} target="_blank" rel="noreferrer" className="grid h-10 w-10 place-items-center rounded-xl text-slate-500 hover:bg-slate-100" aria-label={`Открыть площадку: ${candidate.display_name}`}><ExternalLink className="h-4 w-4" /></a> : null}<Button variant="outline" aria-expanded={Boolean(preview)} aria-label={`Черновик приглашения: ${candidate.display_name}`} onClick={() => void loadOutreachPreview(campaign, candidate)} disabled={busy === `preview:${candidate.id}`} className="min-h-10 rounded-xl bg-white">{busy === `preview:${candidate.id}` ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}{preview ? 'Скрыть черновик' : 'Черновик приглашения'}</Button>{candidate.collaboration_id ? <Button aria-label={`Открыть коллаборацию: ${candidate.display_name}`} onClick={() => setSection('collaborations')} className="min-h-10 rounded-xl bg-emerald-700 text-white">Открыть коллаборацию</Button> : candidate.workstream_id ? <Button aria-label={`Зафиксировать ответ: ${candidate.display_name}`} onClick={() => void createCollaboration(campaign, candidate)} disabled={busy === `collaboration:${candidate.id}`} className="min-h-10 rounded-xl bg-amber-600 text-white hover:bg-amber-700">{busy === `collaboration:${candidate.id}` ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Users className="mr-2 h-4 w-4" />}Зафиксировать ответ</Button> : <Button aria-label={`Подготовить контакт: ${candidate.display_name}`} onClick={() => void prepareOutreach(campaign, candidate)} disabled={campaign.status !== 'approved' || busy === `outreach:${candidate.id}` || overview?.feature_state?.outreach === false} className="min-h-10 rounded-xl bg-slate-950 text-white active:scale-[0.96] transition-transform">{busy === `outreach:${candidate.id}` ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}{overview?.feature_state?.outreach === false ? 'Контакты пока закрыты' : 'Подготовить контакт'}</Button>}</div></div>{preview ? <div className="mt-4 rounded-2xl bg-slate-50 p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><div className="text-sm font-semibold text-slate-950">Черновик до подтверждения</div><div className={cn('mt-1 text-xs', preview.contact?.status === 'confirmed' ? 'text-emerald-700' : 'text-amber-700')}>{contactLabel}</div></div><Button variant="outline" onClick={() => void navigator.clipboard.writeText(preview.message)} className="min-h-10 shrink-0 rounded-xl bg-white"><Copy className="mr-2 h-4 w-4" />Копировать текст</Button></div><p className="mt-4 whitespace-pre-line text-pretty text-sm leading-6 text-slate-700">{preview.message}</p>{preview.personalization?.summary ? <div className="mt-4 rounded-xl bg-white px-3 py-2 text-xs leading-5 text-slate-500"><span className="font-semibold text-slate-700">Основание персонализации:</span> {preview.personalization.summary}{preview.personalization.source_url ? <a href={preview.personalization.source_url} target="_blank" rel="noreferrer" className="ml-2 underline underline-offset-4">Источник</a> : null}</div> : null}{preview.contact?.value && preview.contact.status !== 'confirmed' ? <div className="mt-4 rounded-xl bg-white p-3"><label className="flex items-start gap-3 text-xs leading-5 text-slate-600"><input type="checkbox" checked={Boolean(contactConfirmationChecks[previewKey])} onChange={(event) => setContactConfirmationChecks((current) => ({ ...current, [previewKey]: event.target.checked }))} className="mt-1 h-4 w-4 rounded border-slate-300" /><span>Я проверил(а), что <span className="font-semibold text-slate-800">{preview.contact?.value}</span> принадлежит автору, каналу или указанному представителю.</span></label><Button variant="outline" onClick={() => void confirmContact(campaign, candidate, preview)} disabled={!contactConfirmationChecks[previewKey] || busy === `contact-confirm:${candidate.id}`} className="mt-3 min-h-10 rounded-xl bg-white">{busy === `contact-confirm:${candidate.id}` ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}Подтвердить контакт</Button></div> : null}{preview.terms_review?.missing?.length ? <div className="mt-3 text-xs leading-5 text-amber-800">До подтверждения заполните: {preview.terms_review.missing.join(', ')}.</div> : <div className="mt-3 text-xs leading-5 text-emerald-700">Формат, бюджет, сроки, права и контакт заполнены.</div>}</div> : null}</div>;
            })}</div> : null}
          </section>
        )) : <EmptyState icon={Send} title="Кампаний пока нет" description="Соберите shortlist в поиске. Кампания зафиксирует цель, условия, выбранных авторов и границы согласования." action={<Button onClick={() => setSection('search')} className="min-h-11 rounded-xl bg-slate-950 text-white"><ChevronRight className="mr-2 h-4 w-4" />Перейти к поиску</Button>} />}</div>
      ) : null}

      {!loading && section === 'collaborations' ? (
        <div id="influencer-panel-collaborations" role="tabpanel" aria-labelledby="influencer-tab-collaborations" className="space-y-4">{(overview?.collaborations || []).length ? (overview?.collaborations || []).map((collaboration) => {
          const draft = deliverableDrafts[collaboration.id] || emptyDeliverableDraft();
          const nextStatus = nextCollaborationStatus[collaboration.status];
          return <section key={collaboration.id} className="rounded-[24px] bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.06)]">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div><div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{statusLabel[collaboration.status] || collaboration.status}</div><h2 className="mt-2 text-balance text-lg font-semibold text-slate-950">{collaboration.display_name}</h2></div>
              <div className="flex flex-wrap items-center gap-2"><div className="rounded-xl bg-slate-100 px-3 py-2 text-sm text-slate-600 tabular-nums">Материалов: {collaboration.deliverables?.length || 0}</div><Button variant="outline" onClick={() => void createCreatorRoom(collaboration)} disabled={busy === `room:${collaboration.id}`} className="min-h-10 rounded-xl">{busy === `room:${collaboration.id}` ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ExternalLink className="mr-2 h-4 w-4" />}{collaboration.public_room_ready ? 'Обновить ссылку' : 'Создать ссылку автору'}</Button>{nextStatus ? <Button onClick={() => void updateCollaborationStatus(collaboration, nextStatus.status)} disabled={busy === `collaboration-status:${collaboration.id}`} className="min-h-10 rounded-xl bg-slate-950 text-white">{busy === `collaboration-status:${collaboration.id}` ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ChevronRight className="mr-2 h-4 w-4" />}{nextStatus.label}</Button> : null}</div>
            </div>
            {roomLinks[collaboration.id] ? <div className="mt-4 flex flex-col gap-2 rounded-2xl bg-amber-50 p-4 sm:flex-row sm:items-center"><Input readOnly value={roomLinks[collaboration.id]} className="min-h-10 rounded-xl bg-white text-xs" /><Button variant="outline" onClick={() => void navigator.clipboard.writeText(roomLinks[collaboration.id])} className="min-h-10 shrink-0 rounded-xl bg-white"><Copy className="mr-2 h-4 w-4" />Копировать</Button></div> : null}
            {collaboration.deliverables?.length ? <div className="mt-4 divide-y divide-slate-100">{collaboration.deliverables.map((deliverable) => {
              const metricDraft = metricDrafts[deliverable.id] || { reach: '', clicks: '', inquiries: '', bookings: '', placementCost: '' };
              const updateMetric = (field: keyof MetricDraft, value: string) => setMetricDrafts((current) => ({ ...current, [deliverable.id]: { ...metricDraft, [field]: value } }));
              return <div key={deliverable.id} className="py-4 text-sm">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><span>{deliverable.platform} · {deliverable.deliverable_type}</span>{deliverable.publication_url ? <a href={deliverable.publication_url} target="_blank" rel="noreferrer" className="ml-3 text-slate-500 underline underline-offset-4">Открыть</a> : null}<div className="mt-1 text-xs text-slate-500">{deliverable.verification_status}</div></div>{deliverable.publication_url && deliverable.verification_status !== 'verified' ? <Button variant="outline" onClick={() => void verifyDeliverable(deliverable)} disabled={busy === `verify:${deliverable.id}`} className="min-h-10 rounded-xl">{busy === `verify:${deliverable.id}` ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}Подтвердить proof</Button> : null}</div>
                {deliverable.tracking?.tracked_url || deliverable.tracking?.promo_code || deliverable.tracking?.cta ? <div className="mt-4 rounded-2xl bg-amber-50 p-4 text-xs leading-5 text-amber-950"><div className="font-semibold">План измерения</div>{deliverable.tracking.tracked_url ? <div className="mt-2 break-all">UTM: <a href={deliverable.tracking.tracked_url} target="_blank" rel="noreferrer" className="underline underline-offset-4">{deliverable.tracking.tracked_url}</a></div> : null}{deliverable.tracking.promo_code ? <div className="mt-1">Промокод: <span className="font-semibold tabular-nums">{deliverable.tracking.promo_code}</span></div> : null}{deliverable.tracking.cta ? <div className="mt-1">CTA: {deliverable.tracking.cta}</div> : null}</div> : null}
                {deliverable.verification_status === 'verified' && overview?.feature_state?.metrics !== false ? <div className="mt-4 rounded-2xl bg-slate-50 p-4"><div className="font-semibold text-slate-900">Статистика размещения</div><p className="mt-1 text-xs leading-5 text-slate-500">Заполните накопительные показатели и сохраните их в нужной контрольной точке.</p><div className="mt-3 grid gap-2 sm:grid-cols-5"><Input aria-label="Охват" value={metricDraft.reach} onChange={(event) => updateMetric('reach', event.target.value)} inputMode="numeric" placeholder="Охват" className="min-h-10 rounded-xl bg-white" /><Input aria-label="Переходы" value={metricDraft.clicks} onChange={(event) => updateMetric('clicks', event.target.value)} inputMode="numeric" placeholder="Переходы" className="min-h-10 rounded-xl bg-white" /><Input aria-label="Обращения" value={metricDraft.inquiries} onChange={(event) => updateMetric('inquiries', event.target.value)} inputMode="numeric" placeholder="Обращения" className="min-h-10 rounded-xl bg-white" /><Input aria-label="Записи" value={metricDraft.bookings} onChange={(event) => updateMetric('bookings', event.target.value)} inputMode="numeric" placeholder="Записи" className="min-h-10 rounded-xl bg-white" /><Input aria-label="Стоимость размещения" value={metricDraft.placementCost} onChange={(event) => updateMetric('placementCost', event.target.value)} inputMode="decimal" placeholder="Стоимость, ₽" className="min-h-10 rounded-xl bg-white" /></div><div className="mt-3 flex flex-wrap gap-2">{(deliverable.measurement_checkpoints || []).map((checkpoint) => <Button key={checkpoint.checkpoint} variant="outline" onClick={() => void addMetrics(deliverable, checkpoint.checkpoint)} disabled={checkpoint.status === 'completed' || busy === `metrics:${deliverable.id}`} className={cn('min-h-10 rounded-xl bg-white', checkpoint.status === 'completed' && 'border-emerald-200 text-emerald-800')}>{checkpoint.status === 'completed' ? <Check className="mr-2 h-4 w-4" /> : <BarChart3 className="mr-2 h-4 w-4" />}{checkpointLabel[checkpoint.checkpoint]}{checkpoint.status === 'completed' ? ' · сохранено' : ''}</Button>)}<Button variant="ghost" onClick={() => void addMetrics(deliverable)} disabled={busy === `metrics:${deliverable.id}`} className="min-h-10 rounded-xl">Сохранить вне графика</Button></div></div> : null}
              </div>;
            })}</div> : <p className="mt-4 text-pretty text-sm text-slate-500">Добавьте ожидаемый материал заранее или сохраните ссылку после публикации. Права на повторное использование останутся неподтверждёнными.</p>}
            <div className="mt-5 rounded-2xl bg-slate-50 p-4"><div className="text-sm font-semibold text-slate-900">Добавить материал</div><div className="mt-3 grid gap-3 sm:grid-cols-3"><Input aria-label="Платформа" value={draft.platform} onChange={(event) => setDeliverableDrafts((current) => ({ ...current, [collaboration.id]: { ...draft, platform: event.target.value } }))} placeholder="telegram" className="min-h-11 rounded-xl bg-white" /><Input aria-label="Формат материала" value={draft.deliverableType} onChange={(event) => setDeliverableDrafts((current) => ({ ...current, [collaboration.id]: { ...draft, deliverableType: event.target.value } }))} placeholder="пост, видео, обзор" className="min-h-11 rounded-xl bg-white" /><Input aria-label="Ссылка на публикацию" value={draft.publicationUrl} onChange={(event) => setDeliverableDrafts((current) => ({ ...current, [collaboration.id]: { ...draft, publicationUrl: event.target.value } }))} placeholder="Ссылка — можно добавить позже" className="min-h-11 rounded-xl bg-white" /></div><div className="mt-4 border-t border-slate-200 pt-4"><div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Как измерим результат</div><div className="mt-3 grid gap-3 sm:grid-cols-3"><Input aria-label="Ссылка бизнеса для UTM" value={draft.destinationUrl} onChange={(event) => setDeliverableDrafts((current) => ({ ...current, [collaboration.id]: { ...draft, destinationUrl: event.target.value } }))} placeholder="Ссылка бизнеса для UTM" className="min-h-11 rounded-xl bg-white" /><Input aria-label="Промокод" value={draft.promoCode} onChange={(event) => setDeliverableDrafts((current) => ({ ...current, [collaboration.id]: { ...draft, promoCode: event.target.value } }))} placeholder="Промокод, если нужен" className="min-h-11 rounded-xl bg-white" /><Input aria-label="Призыв к действию" value={draft.cta} onChange={(event) => setDeliverableDrafts((current) => ({ ...current, [collaboration.id]: { ...draft, cta: event.target.value } }))} placeholder="CTA: записаться, запросить расчёт…" className="min-h-11 rounded-xl bg-white" /></div><p className="mt-2 text-xs leading-5 text-slate-500">После подтверждения публикации LocalOS поставит снимки показателей через 24 часа, 7 и 14 дней.</p></div><Button onClick={() => void addDeliverable(collaboration)} disabled={busy === `deliverable:${collaboration.id}` || !draft.platform.trim() || !draft.deliverableType.trim()} className="mt-3 min-h-10 rounded-xl bg-slate-950 text-white">{busy === `deliverable:${collaboration.id}` ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}Сохранить материал и измерение</Button></div>
          </section>;
        }) : <EmptyState icon={Users} title="Активных коллабораций нет" description="Коллаборация появится после ответа автора и согласования условий. До этого кандидаты остаются внутри кампании." />}</div>
      ) : null}

      {!loading && section === 'results' ? (
        <div id="influencer-panel-results" role="tabpanel" aria-labelledby="influencer-tab-results" className="space-y-5"><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">{[
          ['Коллаборации', overview?.metrics?.collaborations || 0],
          ['Подтверждённые материалы', overview?.metrics?.verified_deliverables || 0],
          ['Локальный охват', overview?.metrics?.reach || 0],
          ['Обращения', overview?.metrics?.inquiries || 0],
          ['Снимки по графику', overview?.metrics?.measurement_checkpoints?.pending || 0],
        ].map(([label, value]) => <div key={String(label)} className="rounded-2xl bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_8px_24px_-20px_rgba(15,23,42,0.22)]"><div className="text-sm text-slate-500">{label}</div><div className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 tabular-nums">{formatNumber(value)}</div></div>)}</div><section className="rounded-[28px] bg-white p-6 shadow-[0_0_0_1px_rgba(15,23,42,0.06)]"><h2 className="text-balance text-xl font-semibold text-slate-950">Сопоставимая эффективность</h2><div className="mt-5 grid gap-4 sm:grid-cols-3"><div><div className="text-sm text-slate-500">CPM</div><div className="mt-1 text-xl font-semibold tabular-nums">{overview?.metrics?.calculated?.cpm == null ? '—' : `${formatNumber(overview.metrics.calculated.cpm)} ₽`}</div></div><div><div className="text-sm text-slate-500">Стоимость обращения</div><div className="mt-1 text-xl font-semibold tabular-nums">{overview?.metrics?.calculated?.cost_per_inquiry == null ? '—' : `${formatNumber(overview.metrics.calculated.cost_per_inquiry)} ₽`}</div></div><div><div className="text-sm text-slate-500">Подтверждённая выручка</div><div className="mt-1 text-xl font-semibold tabular-nums">{formatNumber(overview?.metrics?.confirmed_revenue || 0)} ₽</div></div></div><p className="mt-6 text-pretty text-xs leading-5 text-slate-500">{overview?.metrics?.disclaimer || 'Расчётные показатели отделены от подтверждённой выручки.'}</p></section></div>
      ) : null}
    </div>
  );
};
