import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  ExternalLink,
  Pause,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  XCircle,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { newAuth } from '@/lib/auth_new';
import {
  buildProjectedOutreachTouches,
  defaultOutreachStartValue,
  OutreachScheduleCalendar,
  outreachStartIso,
} from '@/components/prospecting/OutreachScheduleCalendar';

type ChannelStatus =
  | 'ready'
  | 'connect_required'
  | 'permission_required'
  | 'manual'
  | 'recipient_missing'
  | 'adapter_unavailable'
  | 'sender_degraded'
  | 'sender_paused'
  | 'sender_selection_required';

type QualityGate = {
  passed?: boolean;
  verdict?: 'approve' | 'revise' | 'reject';
  score?: number;
  total_score?: number;
  max_score?: number;
  criterion_scores?: Record<string, number>;
  reason_codes?: string[];
};

type TouchPreview = {
  id?: string;
  sequence_index: number;
  channel: string;
  day_offset: number;
  angle: string;
  subject?: string | null;
  text: string;
  channel_status: ChannelStatus;
  source_url?: string | null;
  observation?: string | null;
  problem_hypothesis?: string | null;
  relevance_bridge?: string | null;
  quality_gate?: QualityGate;
  status?: string;
  generated_text?: string;
  approved_text?: string | null;
  scheduled_at?: string | null;
};

type CampaignTouch = TouchPreview & {
  id: string;
  status?: string;
  generated_text?: string;
  approved_text?: string | null;
  quality_gate_json?: QualityGate;
  message_brief_json?: {
    source_url?: string | null;
    observation?: string | null;
    problem_hypothesis?: string | null;
    relevance_bridge?: string | null;
  };
};

type Campaign = {
  id: string;
  version?: number;
  status?: string;
  stop_reason?: string | null;
  needs_attention_reason?: string | null;
  touches?: CampaignTouch[];
  events?: Array<{
    id?: string;
    event_type?: string;
    reason_code?: string | null;
    created_at?: string;
  }>;
};

type StrategyRecommendation = {
  id: string;
  strategy_fingerprint: string;
  dimensions_json?: { segment?: string; channel?: string; angle?: string };
  delivered_count?: number;
  positive_reply_count?: number;
  confidence?: number;
  sample_status?: string;
  recommendation_status?: string;
};

type Preview = {
  status?: 'ready' | 'needs_evidence' | 'needs_generation' | 'needs_revision' | 'needs_channel_setup' | 'invalid_sequence' | 'suppressed';
  missing?: string[];
  sequence_issues?: string[];
  touches?: TouchPreview[];
  generation?: {
    status?: string;
    source?: string;
    error?: string | null;
  };
  quality_gate?: QualityGate;
  channel_availability?: Record<string, {
    status?: ChannelStatus;
    recipient?: string | null;
    sender_account_id?: string | null;
    sender_accounts?: Array<{
      id: string;
      sender_identity?: string | null;
      display_name?: string | null;
      health_status?: string | null;
      status?: ChannelStatus;
    }>;
  }>;
};

type OutreachCampaignBuilderProps = {
  workstreamId?: string | null;
  businessId?: string | null;
  leadSegment?: string | null;
  onChanged?: () => void;
};

type CampaignBusinessOutcome = 'meeting_booked' | 'converted' | 'no_reply';

type PilotReadiness = {
  status?: string;
  reason_code?: string;
  can_dispatch_first_touch?: boolean;
  next_action?: string;
  checks?: Array<{
    code?: string;
    label?: string;
    passed?: boolean;
  }>;
};

const ANGLES = ['signal', 'founder_story', 'proof', 'respectful_close'] as const;
const ANGLE_LABELS = ['Сигнал', 'Опыт основателя', 'Кейс или материал', 'Завершение'];
const MANUAL_CHANNELS = new Set(['max', 'vk', 'whatsapp', 'sms', 'manual']);
const DEFAULT_CHANNELS = ['telegram', 'email', 'max', 'vk'];
const DEFAULT_DAYS = [0, 3, 7, 12];

const CHANNEL_STATUS_LABELS: Record<string, string> = {
  ready: 'готов',
  connect_required: 'нужно подключить отправителя',
  permission_required: 'отправка запрещена',
  manual: 'вручную',
  recipient_missing: 'нет контакта',
  adapter_unavailable: 'нет безопасной отправки',
  sender_degraded: 'отправитель ограничен',
  sender_paused: 'отправитель на паузе',
  sender_selection_required: 'выберите отправителя',
};

const CAMPAIGN_STATUS_LABELS: Record<string, string> = {
  draft: 'черновик',
  approved: 'подтверждена',
  active: 'активна',
  paused: 'на паузе',
  stopped: 'остановлена',
  completed: 'завершена',
  cancelled: 'отменена',
};

const QUALITY_CRITERION_LABELS: Record<string, string> = {
  source_validity: 'Надёжность источника',
  observation_accuracy: 'Точность наблюдения',
  freshness_and_why_now: 'Актуальность сигнала',
  offer_bridge: 'Связь с предложением',
  recipient_specificity: 'Конкретность для получателя',
  proof_integrity: 'Подтверждение опыта',
  channel_fit: 'Естественность для канала',
  single_cta_and_length: 'Один вопрос и длина',
  state_and_suppression_safety: 'Безопасность контакта',
};

const QUALITY_REASON_LABELS: Record<string, string> = {
  SOURCE_MISSING: 'Не хватает подтверждённого источника',
  SOURCE_MISMATCH: 'Источник не подтверждает наблюдение',
  STALE_AS_CURRENT: 'Устаревший сигнал используется как текущий',
  INFERENCE_AS_FACT: 'Гипотеза подана как факт',
  DECORATIVE_PERSONALIZATION: 'Персонализация не меняет причину обращения',
  WEAK_OFFER_BRIDGE: 'Неясно, как сигнал связан с предложением',
  UNSUPPORTED_PROOF: 'Опыт отправителя не подтверждён',
  MULTIPLE_CTA: 'В сообщении больше одного следующего шага',
  CHANNEL_LIMIT_EXCEEDED: 'Текст не подходит выбранному каналу',
  STYLE_VIOLATION: 'Текст звучит неестественно или нарушает голос',
  TERMINAL_CONTACT_STATE: 'Контакт уже находится в конечном статусе',
  SUPPRESSED_CONTACT: 'Получатель находится в stop-list',
  APPROVAL_BYPASS: 'Требуется новое ручное подтверждение',
  SENSITIVE_TARGETING: 'Сигнал нельзя безопасно использовать в сообщении',
};

const QUALITY_VERDICT_LABELS: Record<string, string> = {
  approve: 'Можно подтверждать',
  revise: 'Нужно исправить',
  reject: 'Нельзя использовать',
};

const formatDate = (value?: string) => {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('ru-RU');
};

export function OutreachCampaignBuilder({
  workstreamId,
  businessId,
  leadSegment,
  onChanged,
}: OutreachCampaignBuilderProps) {
  const [channels, setChannels] = useState(DEFAULT_CHANNELS);
  const [days, setDays] = useState(DEFAULT_DAYS);
  const [startAt, setStartAt] = useState(defaultOutreachStartValue);
  const [scheduleDirty, setScheduleDirty] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState('');
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [manualNotes, setManualNotes] = useState<Record<string, string>>({});
  const [outcomeNote, setOutcomeNote] = useState('');
  const [recommendations, setRecommendations] = useState<StrategyRecommendation[]>([]);
  const [senderSelections, setSenderSelections] = useState<Record<number, string>>({});
  const [pilotReadiness, setPilotReadiness] = useState<PilotReadiness | null>(null);

  const loadCampaigns = useCallback(async () => {
    if (!workstreamId) {
      setCampaigns([]);
      setSelectedCampaignId('');
      return;
    }
    try {
      const payload = await newAuth.makeRequest(`/outreach/workstreams/${encodeURIComponent(workstreamId)}/campaigns`);
      const nextCampaigns: Campaign[] = (Array.isArray(payload?.campaigns) ? payload.campaigns : [])
        .map((campaign: Campaign) => ({
          ...campaign,
          touches: (campaign.touches || []).map((touch) => ({
            ...touch,
            day_offset: touch.day_offset ?? touch.sequence_index,
            text: touch.text || touch.approved_text || touch.generated_text || '',
            quality_gate: touch.quality_gate || touch.quality_gate_json,
            source_url: touch.source_url || touch.message_brief_json?.source_url || null,
            observation: touch.observation || touch.message_brief_json?.observation || null,
            problem_hypothesis: touch.problem_hypothesis || touch.message_brief_json?.problem_hypothesis || null,
            relevance_bridge: touch.relevance_bridge || touch.message_brief_json?.relevance_bridge || null,
          })),
        }));
      setCampaigns(nextCampaigns);
      setSelectedCampaignId((current) => (
        current && nextCampaigns.some((item: Campaign) => item.id === current)
          ? current
          : String(nextCampaigns[0]?.id || '')
      ));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить кампании');
    }
  }, [workstreamId]);

  const loadRecommendations = useCallback(async () => {
    if (!businessId) {
      setRecommendations([]);
      return;
    }
    try {
      const query = new URLSearchParams({
        workstream_type: 'client_partnership',
        business_id: businessId,
      });
      const payload = await newAuth.makeRequest(`/outreach/learning/strategy-stats?${query.toString()}`);
      const items = Array.isArray(payload?.stats) ? payload.stats : [];
      const currentTokens = new Set((String(leadSegment || '').toLowerCase().match(/[a-zа-яё0-9]+/g) || []).filter((token) => token.length >= 4).map((token) => token.slice(0, 6)));
      setRecommendations(items.filter((item: StrategyRecommendation) => {
        if (item.recommendation_status !== 'candidate_for_reuse') return false;
        const learnedTokens = (String(item.dimensions_json?.segment || '').toLowerCase().match(/[a-zа-яё0-9]+/g) || []).filter((token) => token.length >= 4).map((token) => token.slice(0, 6));
        return currentTokens.size === 0 || learnedTokens.length === 0 || learnedTokens.some((token) => currentTokens.has(token));
      }));
    } catch {
      setRecommendations([]);
    }
  }, [businessId, leadSegment]);

  useEffect(() => {
    setChannels(DEFAULT_CHANNELS);
    setDays(DEFAULT_DAYS);
    setStartAt(defaultOutreachStartValue());
    setScheduleDirty(false);
    setPreview(null);
    setSenderSelections({});
    setOutcomeNote('');
    setNotice('');
    setError('');
    setPilotReadiness(null);
    void loadCampaigns();
    void loadRecommendations();
  }, [loadCampaigns, loadRecommendations]);

  const selectedCampaign = useMemo(
    () => campaigns.find((item) => item.id === selectedCampaignId) || campaigns[0] || null,
    [campaigns, selectedCampaignId],
  );

  const projectedScheduleTouches = useMemo(() => {
    const sourceTouches = preview?.touches || (scheduleDirty ? [] : selectedCampaign?.touches || []);
    if (!scheduleDirty && !preview?.touches?.length && selectedCampaign?.touches?.some((touch) => touch.scheduled_at)) {
      return selectedCampaign.touches;
    }
    return buildProjectedOutreachTouches(channels, days, startAt, sourceTouches);
  }, [channels, days, preview?.touches, scheduleDirty, selectedCampaign?.touches, startAt]);

  const sequence = () => ANGLES.map((angle, index) => ({
    channel: channels[index],
    day_offset: days[index],
    angle,
    sender_account_id: senderSelections[index] || undefined,
  }));

  const invalidateDraft = () => {
    setScheduleDirty(true);
    setPreview(null);
    setPilotReadiness(null);
    setNotice('Порядок изменён. Обновите preview; прежний approval не будет перенесён.');
  };

  const prepare = async (save: boolean) => {
    if (!workstreamId) return;
    const scheduleStart = outreachStartIso(startAt);
    if (!scheduleStart) {
      setError('Выберите корректные дату и время первого касания.');
      return;
    }
    setBusy(save ? 'save' : 'preview');
    setError('');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest(`/outreach/workstreams/${encodeURIComponent(workstreamId)}/preview`, {
        method: 'POST',
        body: JSON.stringify({ sequence: sequence(), start_at: scheduleStart, save }),
      });
      setPreview(payload?.preview || null);
      if (payload?.campaign) {
        setScheduleDirty(false);
        setNotice(`Версия ${payload.campaign.version} сохранена как черновик. Проверьте всю цепочку.`);
        await loadCampaigns();
        setSelectedCampaignId(String(payload.campaign.id || ''));
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось подготовить цепочку');
    } finally {
      setBusy('');
    }
  };

  const approve = async () => {
    if (!selectedCampaign?.id) return;
    setBusy('approve');
    setError('');
    setNotice('');
    setPilotReadiness(null);
    try {
      await newAuth.makeRequest(`/outreach/campaigns/${encodeURIComponent(selectedCampaign.id)}/approve`, { method: 'POST' });
      setNotice('Цепочка подтверждена. Перед каждым касанием LocalOS повторит все safety-проверки.');
      await loadCampaigns();
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось подтвердить цепочку');
    } finally {
      setBusy('');
    }
  };

  const changeCampaign = async (action: 'pause' | 'resume' | 'cancel') => {
    if (!selectedCampaign?.id) return;
    if (action === 'cancel' && !window.confirm('Отменить кампанию? Будущие касания не будут отправлены.')) return;
    setBusy(action);
    setError('');
    try {
      await newAuth.makeRequest(`/outreach/campaigns/${encodeURIComponent(selectedCampaign.id)}/${action}`, { method: 'POST' });
      setNotice(action === 'pause' ? 'Кампания на паузе.' : action === 'resume' ? 'Камания возобновлена после повторного preflight.' : 'Камания отменена.');
      await loadCampaigns();
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Действие не выполнено');
    } finally {
      setBusy('');
    }
  };

  const applyRecommendation = async (recommendation: StrategyRecommendation) => {
    if (!workstreamId) return;
    setBusy('apply-learning');
    setError('');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest(`/outreach/workstreams/${encodeURIComponent(workstreamId)}/apply-learning-recommendation`, {
        method: 'POST',
        body: JSON.stringify({ strategy_fingerprint: recommendation.strategy_fingerprint }),
      });
      setPreview(payload?.preview || null);
      setNotice(`Связка применена к фактам этого лида. Создана новая draft-версия ${payload?.campaign?.version || ''}; approval не перенесён.`);
      await loadCampaigns();
      setSelectedCampaignId(String(payload?.campaign?.id || ''));
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось применить рекомендацию');
    } finally {
      setBusy('');
    }
  };

  const manualEvent = async (touch: TouchPreview, eventType: 'sent' | 'skipped' | 'reply') => {
    if (!selectedCampaign?.id || !touch.id) return;
    const note = String(manualNotes[touch.id] || '').trim();
    if (eventType === 'reply' && !note) {
      setError('Для ответа добавьте его текст: он нужен для остановки и обучения.');
      return;
    }
    setBusy(`manual-${touch.id}-${eventType}`);
    setError('');
    try {
      await newAuth.makeRequest(`/outreach/campaigns/${encodeURIComponent(selectedCampaign.id)}/touches/${encodeURIComponent(touch.id)}/manual-event`, {
        method: 'POST',
        body: JSON.stringify({ event_type: eventType, note }),
      });
      setNotice(eventType === 'reply' ? 'Ответ записан. Все будущие каналы остановлены.' : 'Ручное касание обновлено.');
      setManualNotes((current) => ({ ...current, [touch.id]: '' }));
      await loadCampaigns();
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось записать ручное действие');
    } finally {
      setBusy('');
    }
  };

  const recordBusinessOutcome = async (outcomeType: CampaignBusinessOutcome) => {
    if (!selectedCampaign?.id) return;
    if (outcomeType !== 'no_reply' && !outcomeNote.trim()) {
      setError('Добавьте короткую заметку: что согласовано или какой результат получен.');
      return;
    }
    setBusy(`outcome-${outcomeType}`);
    setError('');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest(`/outreach/campaigns/${encodeURIComponent(selectedCampaign.id)}/outcome`, {
        method: 'POST',
        body: JSON.stringify({ outcome_type: outcomeType, note: outcomeNote.trim() }),
      });
      const reused = Boolean(payload?.outcome?.reused);
      const label = outcomeType === 'meeting_booked'
        ? 'Встреча записана в обучающую петлю.'
        : outcomeType === 'converted'
          ? 'Конверсия записана в обучающую петлю.'
          : 'Кампания отмечена завершённой без ответа.';
      setNotice(reused ? `Этот результат уже был записан. ${label}` : label);
      setOutcomeNote('');
      await loadCampaigns();
      await loadRecommendations();
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось записать результат кампании');
    } finally {
      setBusy('');
    }
  };

  const dispatchPilotFirstTouch = async () => {
    if (!selectedCampaign?.id) return;
    const confirmed = window.confirm(
      'Отправить только первое касание этой кампании реальному получателю? LocalOS ещё раз проверит ответы, разрешения, tenant scope, suppression и лимиты. Остальные касания не будут отправлены.',
    );
    if (!confirmed) return;
    setBusy('pilot-dispatch');
    setError('');
    setNotice('');
    setPilotReadiness(null);
    try {
      const payload = await newAuth.makeRequest(`/outreach/campaigns/${encodeURIComponent(selectedCampaign.id)}/pilot-dispatch-first-touch`, {
        method: 'POST',
        body: JSON.stringify({ confirm_campaign_id: selectedCampaign.id }),
      });
      if (Number(payload?.messages_sent || 0) !== 1) {
        setError('Первое касание не отправлено: safety-preflight остановил операцию. Проверьте журнал кампании.');
      } else {
        setNotice('Первое пилотное касание отправлено. Остальные каналы не запускались; теперь LocalOS ждёт и синхронизирует ответ.');
      }
      await loadCampaigns();
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Пилотное касание не отправлено');
    } finally {
      setBusy('');
    }
  };

  const runPilotPreflight = async () => {
    if (!selectedCampaign?.id) return;
    setBusy('pilot-preflight');
    setError('');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest(`/outreach/campaigns/${encodeURIComponent(selectedCampaign.id)}/pilot-preflight`, {
        method: 'POST',
      });
      const readiness: PilotReadiness = payload?.pilot_readiness || {};
      setPilotReadiness(readiness);
      if (readiness.can_dispatch_first_touch) {
        setNotice('Проверка пройдена. LocalOS готов отправить только первое касание после вашего отдельного подтверждения.');
      }
    } catch (requestError) {
      setPilotReadiness(null);
      setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить готовность к пилоту');
    } finally {
      setBusy('');
    }
  };

  const syncPilotReply = async () => {
    if (!selectedCampaign?.id) return;
    setBusy('pilot-reply-sync');
    setError('');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest(`/outreach/campaigns/${encodeURIComponent(selectedCampaign.id)}/pilot-reply-sync`, {
        method: 'POST',
      });
      if (payload?.reply_received) {
        setNotice(`Ответ получен и классифицирован${payload.classification ? `: ${payload.classification}` : ''}. Все следующие касания остановлены.`);
      } else {
        setNotice('Нового ответа пока нет. Проверка выполнена без отправки сообщений.');
      }
      await loadCampaigns();
      await loadRecommendations();
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить ответ');
    } finally {
      setBusy('');
    }
  };

  if (!workstreamId) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
        Для этого лида ещё не создан партнёрский workstream. Сначала добавьте лида в партнёрскую воронку.
      </div>
    );
  }

  const manualFirst = MANUAL_CHANNELS.has(channels[0]);
  const visibleTouches = preview?.touches || selectedCampaign?.touches || [];
  const recordedOutcomes = new Set(
    (selectedCampaign?.events || [])
      .filter((event) => event.event_type === 'campaign_outcome_recorded')
      .map((event) => String(event.reason_code || '')),
  );
  const canRecordReplyOutcome = selectedCampaign?.status === 'stopped'
    && selectedCampaign.stop_reason === 'recipient_replied';
  const canRecordNoReply = selectedCampaign?.status === 'completed'
    && !selectedCampaign.stop_reason;
  const firstCampaignTouch = (selectedCampaign?.touches || [])
    .find((touch) => Number(touch.sequence_index) === 0);
  const pilotAlreadySent = (selectedCampaign?.touches || []).some((touch) => (
    ['manual_sent', 'sent', 'delivered'].includes(String(touch.status || ''))
  ));
  const canPilotDispatch = Boolean(
    selectedCampaign?.status === 'approved'
    && firstCampaignTouch
    && ['telegram', 'email'].includes(firstCampaignTouch.channel)
    && !pilotAlreadySent
    && pilotReadiness?.can_dispatch_first_touch,
  );
  const pilotReplyReceived = selectedCampaign?.stop_reason === 'recipient_replied';
  const canPilotReplySync = Boolean(
    firstCampaignTouch
    && ['telegram', 'email'].includes(firstCampaignTouch.channel)
    && pilotAlreadySent
    && !pilotReplyReceived,
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-base font-semibold text-slate-950">Кампания до первого ответа</h3>
          <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">
            Проверьте сигнал, опыт основателя, каналы и всю цепочку. Любой ответ остановит будущие касания.
          </p>
        </div>
        {selectedCampaign ? (
          <Badge variant="outline" className={['approved', 'active'].includes(String(selectedCampaign.status || ''))
            ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
            : 'border-slate-200 bg-white text-slate-700'}>
            Версия {selectedCampaign.version} · {CAMPAIGN_STATUS_LABELS[String(selectedCampaign.status || '')] || selectedCampaign.status}
          </Badge>
        ) : <Badge variant="outline">Не сохранена</Badge>}
      </div>

      {campaigns.length > 1 ? (
        <label className="block text-sm font-medium text-slate-800">
          Версия
          <select
            value={selectedCampaign?.id || ''}
            onChange={(event) => {
              setSelectedCampaignId(event.target.value);
              setPilotReadiness(null);
            }}
            className="mt-2 min-h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900"
          >
            {campaigns.map((campaign) => (
              <option key={campaign.id} value={campaign.id}>
                Версия {campaign.version} · {CAMPAIGN_STATUS_LABELS[String(campaign.status || '')] || campaign.status}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <label className="block rounded-xl bg-white p-3 shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_1px_2px_-1px_rgba(15,23,42,0.06)]">
        <span className="text-sm font-semibold text-slate-950">Дата и время первого касания</span>
        <span className="mt-1 block text-pretty text-xs leading-5 text-slate-600">Остальные сообщения появятся в календаре по выбранным интервалам. Изменение создаёт новую версию и требует повторного подтверждения.</span>
        <Input
          aria-label="Дата и время первого касания"
          type="datetime-local"
          required
          value={startAt}
          onChange={(event) => {
            setStartAt(event.target.value);
            invalidateDraft();
          }}
          className="mt-2 h-11 max-w-xs bg-white tabular-nums"
        />
      </label>

      <div className="grid gap-2 sm:grid-cols-2">
        {ANGLES.map((angle, index) => (
          <div key={angle} className="rounded-xl border border-slate-200 bg-white p-3">
            <div className="text-xs font-semibold uppercase tracking-[0.06em] text-slate-500">{ANGLE_LABELS[index]}</div>
            <div className="mt-2 grid grid-cols-[minmax(0,1fr)_84px] gap-2">
              <select
                aria-label={`Канал касания ${index + 1}`}
                value={channels[index]}
                onChange={(event) => {
                  setChannels((current) => current.map((item, itemIndex) => itemIndex === index ? event.target.value : item));
                  invalidateDraft();
                }}
                className="min-h-10 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-900"
              >
                <option value="telegram">Telegram</option>
                <option value="email">Email</option>
                <option value="max">MAX · вручную</option>
                <option value="vk">VK · вручную</option>
                <option value="whatsapp">WhatsApp · вручную</option>
                <option value="sms">SMS · вручную</option>
              </select>
              <Input
                aria-label={`День касания ${index + 1}`}
                type="number"
                min={index === 0 ? 0 : 1}
                value={days[index]}
                disabled={index === 0}
                onChange={(event) => {
                  setDays((current) => current.map((item, itemIndex) => itemIndex === index ? Math.max(0, Number(event.target.value)) : item));
                  invalidateDraft();
                }}
                className="h-10 text-center tabular-nums"
              />
            </div>
            <div className="mt-1 text-xs text-slate-400">День <span className="tabular-nums">{days[index]}</span> от старта</div>
          </div>
        ))}
      </div>

      <OutreachScheduleCalendar
        touches={projectedScheduleTouches}
        modeLabel={scheduleDirty || preview?.touches?.length ? 'Новая версия' : selectedCampaign ? `Сохранённая версия ${selectedCampaign.version || 1}` : 'Новая версия'}
      />

      {manualFirst ? (
        <div className="flex gap-2 rounded-xl border border-sky-200 bg-sky-50 p-3 text-sm leading-6 text-sky-950">
          <AlertTriangle className="mt-1 h-4 w-4 shrink-0" />
          <span>Первое касание ручное. LocalOS подождёт вашей отметки; через 48 часов появится статус «Нужно внимание», без скрытого продолжения.</span>
        </div>
      ) : null}

      {recommendations[0] ? (
        <div className="rounded-xl border border-violet-200 bg-violet-50 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-sm font-semibold text-violet-950">Найдена рабочая связка</div>
              <p className="mt-1 text-sm leading-6 text-violet-900">
                {recommendations[0].dimensions_json?.segment || 'Похожий сегмент'} · {recommendations[0].dimensions_json?.channel || 'канал'} · {recommendations[0].dimensions_json?.angle || 'угол'}: {recommendations[0].positive_reply_count || 0} положительных ответа из {recommendations[0].delivered_count || 0}, confidence {Math.round(Number(recommendations[0].confidence || 0) * 100)}%.
              </p>
            </div>
            <Button variant="outline" className="min-h-10 shrink-0 border-violet-300 bg-white text-violet-900" onClick={() => void applyRecommendation(recommendations[0])} disabled={Boolean(busy)}>
              {busy === 'apply-learning' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
              Применить в новой версии
            </Button>
          </div>
          <p className="mt-2 text-xs text-violet-800">Переносится структура, но не факты другого получателя. Новая версия потребует вашего approval.</p>
        </div>
      ) : null}

      {preview?.channel_availability ? (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            {Object.entries(preview.channel_availability).map(([channel, item]) => (
              <Badge key={channel} variant="outline" className={item.status === 'ready'
                ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                : ['permission_required', 'sender_selection_required'].includes(String(item.status || ''))
                  ? 'border-amber-200 bg-amber-50 text-amber-800'
                  : 'bg-white text-slate-700'}>
                {channel} · {CHANNEL_STATUS_LABELS[String(item.status || '')] || item.status}
              </Badge>
            ))}
          </div>
          {[0, 1, 2, 3].map((touchIndex) => {
            const channel = channels[touchIndex];
            const availability = preview.channel_availability?.[channel];
            const accounts = availability?.sender_accounts || [];
            if (!['telegram', 'email'].includes(channel) || accounts.length <= 1) return null;
            return (
              <label key={`${channel}-${touchIndex}`} className="block rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm font-medium text-amber-950">
                Отправитель для касания {touchIndex + 1} · {channel}
                <select
                  value={senderSelections[touchIndex] || ''}
                  onChange={(event) => {
                    setSenderSelections((current) => ({ ...current, [touchIndex]: event.target.value }));
                    setPreview(null);
                    setNotice('Отправитель выбран. Обновите preview.');
                  }}
                  className="mt-2 min-h-11 w-full rounded-md border border-amber-200 bg-white px-3 text-sm text-slate-900"
                >
                  <option value="">Выберите аккаунт</option>
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id} disabled={account.status !== 'ready'}>
                      {account.display_name || account.sender_identity || account.id} · {CHANNEL_STATUS_LABELS[String(account.status || '')] || account.status}
                    </option>
                  ))}
                </select>
              </label>
            );
          })}
        </div>
      ) : null}

      {preview?.status === 'needs_evidence' ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
          Общий шаблон не будет создан. Не хватает: {(preview.missing || []).join(', ') || 'подтверждённых фактов'}.
        </div>
      ) : null}
      {preview?.status === 'needs_generation' ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-pretty text-sm leading-6 text-amber-950">
          LocalOS сохранил факты, но не смог подготовить персональный текст. Нажмите «Показать всю цепочку» ещё раз. Отправка и сохранение версии заблокированы.
        </div>
      ) : null}
      {preview?.status === 'needs_revision' ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-pretty text-sm leading-6 text-amber-950">
          Текст не прошёл проверку точности и естественности. Проверьте источник и факты об отправителе, затем обновите предпросмотр. LocalOS не даст подтвердить эту версию.
        </div>
      ) : null}
      {preview?.status === 'invalid_sequence' ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-950">
          Дни должны идти по возрастанию с интервалом не менее суток. {(preview.sequence_issues || []).join(' · ')}
        </div>
      ) : null}
      {preview?.status === 'suppressed' ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-950">
          Получатель находится в stop-list. Отправка заблокирована до provider call.
        </div>
      ) : null}
      {preview?.generation?.status === 'ready' ? (
        <p className="text-pretty text-xs leading-5 text-slate-500">Персонализацию подготовил LocalOS; каждое касание отдельно проверено по источнику, фактам и тону.</p>
      ) : null}

      {preview?.quality_gate ? (
        <section className={`flex items-start gap-3 rounded-xl p-4 ${preview.quality_gate.passed
          ? 'bg-emerald-50 text-emerald-950 ring-1 ring-inset ring-emerald-200'
          : 'bg-amber-50 text-amber-950 ring-1 ring-inset ring-amber-200'}`}>
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h4 className="text-wrap-balance text-sm font-semibold">Проверка всей цепочки</h4>
              <span className="tabular-nums text-sm font-semibold">
                {Number(preview.quality_gate.total_score ?? preview.quality_gate.score ?? 0)}/{Number(preview.quality_gate.max_score || 18)}
              </span>
            </div>
            <p className="mt-1 text-pretty text-sm leading-6">
              {QUALITY_VERDICT_LABELS[String(preview.quality_gate.verdict || '')] || 'Нужна проверка'}.
              {preview.quality_gate.passed
                ? ' Все сообщения опираются на источники и готовы к вашему решению.'
                : ' Откройте проверку нужного касания ниже — LocalOS покажет, что именно исправить.'}
            </p>
          </div>
        </section>
      ) : null}

      {visibleTouches.length > 0 ? (
        <div className="space-y-3">
          {visibleTouches.map((touch) => {
            const text = touch.text || touch.approved_text || touch.generated_text || '';
            const isManual = MANUAL_CHANNELS.has(touch.channel);
            const canRecordManual = isManual && ['awaiting_manual_send', 'needs_attention', 'manual_expired', 'manual_sent', 'sent', 'delivered'].includes(String(touch.status || ''));
            return (
              <article key={`${touch.id || 'preview'}-${touch.sequence_index}`} className="rounded-xl border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-semibold uppercase tracking-[0.06em] text-slate-500">
                  <span>День {touch.day_offset} · {touch.channel}</span>
                  <span className={touch.quality_gate?.passed ? 'text-emerald-700' : 'text-amber-700'}>
                    {touch.quality_gate?.passed ? 'Факты проверены' : touch.status || 'Нужна проверка'}
                  </span>
                </div>
                {touch.subject ? <div className="mt-2 text-sm font-semibold text-slate-950">Тема: {touch.subject}</div> : null}
                {touch.observation || touch.problem_hypothesis || touch.relevance_bridge ? (
                  <div className="mt-3 space-y-1 border-l-2 border-sky-200 pl-3 text-sm leading-6 text-slate-700">
                    {touch.observation ? <p><span className="font-semibold text-slate-900">Факт:</span> {touch.observation}</p> : null}
                    {touch.problem_hypothesis ? <p><span className="font-semibold text-slate-900">Гипотеза:</span> {touch.problem_hypothesis}</p> : null}
                    {touch.relevance_bridge ? <p><span className="font-semibold text-slate-900">Почему это связано:</span> {touch.relevance_bridge}</p> : null}
                  </div>
                ) : null}
                <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-800">{text}</p>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {text ? (
                    <Button type="button" variant="outline" size="sm" onClick={() => void navigator.clipboard.writeText(text)}>
                      <Copy className="mr-1.5 h-4 w-4" /> Скопировать
                    </Button>
                  ) : null}
                  {touch.source_url ? (
                    <a href={touch.source_url} target="_blank" rel="noreferrer" className="inline-flex min-h-9 items-center gap-1 text-xs font-semibold text-sky-700">
                      Источник <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  ) : null}
                </div>
                {touch.quality_gate ? (
                  <details open={!touch.quality_gate.passed} className="mt-3 rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-inset ring-slate-200">
                    <summary className="min-h-10 cursor-pointer select-none py-2 text-sm font-semibold text-slate-800">
                      Почему такая оценка ·{' '}
                      <span className="tabular-nums">
                        {Number(touch.quality_gate.total_score ?? touch.quality_gate.score ?? 0)}/{Number(touch.quality_gate.max_score || 18)}
                      </span>
                      {' '}· {QUALITY_VERDICT_LABELS[String(touch.quality_gate.verdict || '')] || 'Нужна проверка'}
                    </summary>
                    <div className="grid gap-x-4 gap-y-2 pb-3 sm:grid-cols-2">
                      {Object.entries(touch.quality_gate.criterion_scores || {}).map(([criterion, score]) => (
                        <div key={criterion} className="flex items-center justify-between gap-3 text-xs text-slate-600">
                          <span>{QUALITY_CRITERION_LABELS[criterion] || criterion}</span>
                          <span className={`shrink-0 tabular-nums font-semibold ${Number(score) === 2 ? 'text-emerald-700' : Number(score) === 1 ? 'text-amber-700' : 'text-rose-700'}`}>
                            {Number(score)}/2
                          </span>
                        </div>
                      ))}
                    </div>
                    {(touch.quality_gate.reason_codes || []).length > 0 ? (
                      <div className="border-t border-slate-200 py-3">
                        <div className="text-xs font-semibold uppercase tracking-[0.06em] text-slate-500">Что исправить</div>
                        <ul className="mt-2 space-y-1 text-sm leading-5 text-slate-700">
                          {(touch.quality_gate.reason_codes || []).map((reasonCode) => (
                            <li key={reasonCode}>• {QUALITY_REASON_LABELS[reasonCode] || reasonCode}</li>
                          ))}
                        </ul>
                      </div>
                    ) : (
                      <p className="border-t border-slate-200 py-3 text-sm text-emerald-700">Критических замечаний нет.</p>
                    )}
                  </details>
                ) : null}
                {canRecordManual && touch.id ? (
                  <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <Textarea
                      value={manualNotes[touch.id] || ''}
                      onChange={(event) => setManualNotes((current) => ({ ...current, [touch.id]: event.target.value }))}
                      placeholder="Комментарий или текст ответа"
                      className="min-h-20 bg-white"
                    />
                    <div className="mt-2 flex flex-wrap gap-2">
                      {['awaiting_manual_send', 'needs_attention', 'manual_expired'].includes(String(touch.status || '')) ? (
                        <>
                          <Button size="sm" onClick={() => void manualEvent(touch, 'sent')} disabled={busy.startsWith(`manual-${touch.id}`)}>Отметить отправленным</Button>
                          <Button size="sm" variant="outline" onClick={() => void manualEvent(touch, 'skipped')} disabled={busy.startsWith(`manual-${touch.id}`)}>Пропустить</Button>
                        </>
                      ) : null}
                      <Button size="sm" variant="outline" onClick={() => void manualEvent(touch, 'reply')} disabled={busy.startsWith(`manual-${touch.id}`)}>Записать ответ</Button>
                    </div>
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : null}

      {selectedCampaign && (canRecordReplyOutcome || canRecordNoReply) ? (
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-sm font-semibold text-slate-950">Какой результат получен</div>
          <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">
            LocalOS свяжет результат с сегментом, сигналом, историей основателя, предложением, каналом и номером касания.
          </p>
          {canRecordReplyOutcome ? (
            <>
              <Textarea
                value={outcomeNote}
                onChange={(event) => setOutcomeNote(event.target.value)}
                placeholder="Например: договорились о созвоне во вторник или запустили пробное партнёрство"
                className="mt-3 min-h-20 bg-white"
              />
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => void recordBusinessOutcome('meeting_booked')}
                  disabled={Boolean(busy) || recordedOutcomes.has('meeting_booked')}
                >
                  {recordedOutcomes.has('meeting_booked') ? 'Встреча уже записана' : 'Встреча назначена'}
                </Button>
                <Button
                  size="sm"
                  onClick={() => void recordBusinessOutcome('converted')}
                  disabled={Boolean(busy) || recordedOutcomes.has('converted')}
                >
                  {recordedOutcomes.has('converted') ? 'Конверсия уже записана' : 'Стала клиентом или партнёром'}
                </Button>
              </div>
            </>
          ) : null}
          {canRecordNoReply ? (
            <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm leading-6 text-slate-600">Все касания завершены, человеческий ответ не зафиксирован.</p>
              <Button
                size="sm"
                variant="outline"
                onClick={() => void recordBusinessOutcome('no_reply')}
                disabled={Boolean(busy) || recordedOutcomes.has('no_reply')}
              >
                {recordedOutcomes.has('no_reply') ? 'Без ответа · записано' : 'Завершить без ответа'}
              </Button>
            </div>
          ) : null}
        </section>
      ) : null}

      {notice ? <div className="flex gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900"><CheckCircle2 className="h-4 w-4 shrink-0" />{notice}</div> : null}
      {error ? <div className="flex gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-950"><AlertTriangle className="h-4 w-4 shrink-0" />{error}</div> : null}

      <div className="grid gap-2 sm:grid-cols-2">
        <Button variant="outline" onClick={() => void prepare(false)} disabled={Boolean(busy) || !outreachStartIso(startAt)} className="min-h-11 bg-white">
          {busy === 'preview' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
          Показать всю цепочку
        </Button>
        <Button variant="outline" onClick={() => void prepare(true)} disabled={Boolean(busy) || !outreachStartIso(startAt) || preview?.status !== 'ready'} className="min-h-11 bg-white">
          {busy === 'save' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : null}
          Сохранить новую версию
        </Button>
      </div>

      {selectedCampaign?.status === 'draft' ? (
        <Button onClick={() => void approve()} disabled={Boolean(busy)} className="min-h-11 w-full bg-orange-500 text-white hover:bg-orange-600">
          {busy === 'approve' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
          Подтвердить всю цепочку один раз
        </Button>
      ) : null}

      {selectedCampaign && !pilotAlreadySent && !pilotReplyReceived ? (
        <section className={pilotReadiness?.can_dispatch_first_touch
          ? 'rounded-2xl bg-emerald-50 p-4 shadow-[0_0_0_1px_rgba(16,185,129,0.22),0_1px_2px_-1px_rgba(15,23,42,0.08)]'
          : 'rounded-2xl bg-slate-50 p-4 shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_1px_2px_-1px_rgba(15,23,42,0.06)]'}>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h4 className="text-balance text-sm font-semibold text-slate-950">Готовность к первому касанию</h4>
              <p className="mt-1 max-w-2xl text-pretty text-sm leading-6 text-slate-600">
                LocalOS проверит текущую версию, отправителя, контакт, ответы, stop-list и лимиты. Сообщение не отправится.
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => void runPilotPreflight()}
              disabled={Boolean(busy)}
              className="min-h-11 shrink-0 bg-white"
            >
              {busy === 'pilot-preflight' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
              Проверить готовность
            </Button>
          </div>
          {pilotReadiness ? (
            <div className="mt-4 border-t border-slate-200/80 pt-3">
              <ul className="grid gap-2 sm:grid-cols-2">
                {(pilotReadiness.checks || []).map((check) => (
                  <li key={String(check.code || check.label)} className="flex items-start gap-2 text-sm leading-5 text-slate-700">
                    {check.passed
                      ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                      : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />}
                    <span className="text-pretty">{check.label}</span>
                  </li>
                ))}
              </ul>
              <p className={`mt-3 text-pretty text-sm font-medium leading-6 ${pilotReadiness.can_dispatch_first_touch ? 'text-emerald-900' : 'text-amber-900'}`}>
                {pilotReadiness.next_action}
              </p>
            </div>
          ) : null}
        </section>
      ) : null}

      {canPilotDispatch ? (
        <section className="rounded-xl border border-orange-200 bg-orange-50 p-4">
          <div className="text-sm font-semibold text-orange-950">Контролируемый пилот</div>
          <p className="mt-1 text-sm leading-6 text-orange-900">
            Будет отправлено ровно первое касание выбранной кампании. Глобальный dispatcher должен оставаться выключенным, остальные касания останутся в очереди.
          </p>
          <Button
            onClick={() => void dispatchPilotFirstTouch()}
            disabled={Boolean(busy)}
            className="mt-3 min-h-11 w-full bg-orange-500 text-white hover:bg-orange-600"
          >
            {busy === 'pilot-dispatch' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
            Отправить только первое касание
          </Button>
        </section>
      ) : null}

      {canPilotReplySync || pilotReplyReceived ? (
        <section className={pilotReplyReceived
          ? 'rounded-xl border border-emerald-200 bg-emerald-50 p-4'
          : 'rounded-xl border border-sky-200 bg-sky-50 p-4'}>
          <div className={pilotReplyReceived ? 'text-sm font-semibold text-emerald-950' : 'text-sm font-semibold text-sky-950'}>
            {pilotReplyReceived ? 'Ответ получен — цепочка остановлена' : 'Ожидание ответа на пилот'}
          </div>
          <p className={pilotReplyReceived ? 'mt-1 text-sm leading-6 text-emerald-900' : 'mt-1 text-sm leading-6 text-sky-900'}>
            {pilotReplyReceived
              ? 'LocalOS сохранил классификацию ответа и отменил все будущие касания по другим каналам.'
              : 'Глобальный worker выключен. Запустите безопасную проверку входящих для отправителя этой кампании.'}
          </p>
          {canPilotReplySync ? (
            <Button
              variant="outline"
              onClick={() => void syncPilotReply()}
              disabled={Boolean(busy)}
              className="mt-3 min-h-11 w-full border-sky-300 bg-white text-sky-950"
            >
              {busy === 'pilot-reply-sync' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              Проверить ответ сейчас
            </Button>
          ) : null}
        </section>
      ) : null}

      {selectedCampaign && ['approved', 'active', 'paused'].includes(String(selectedCampaign.status || '')) ? (
        <div className="flex flex-wrap gap-2 border-t border-slate-200 pt-3">
          {selectedCampaign.status === 'paused' ? (
            <Button variant="outline" onClick={() => void changeCampaign('resume')} disabled={Boolean(busy)}><Play className="mr-2 h-4 w-4" />Возобновить</Button>
          ) : (
            <Button variant="outline" onClick={() => void changeCampaign('pause')} disabled={Boolean(busy)}><Pause className="mr-2 h-4 w-4" />Пауза</Button>
          )}
          <Button variant="outline" onClick={() => void changeCampaign('cancel')} disabled={Boolean(busy)} className="text-rose-700"><XCircle className="mr-2 h-4 w-4" />Отменить</Button>
        </div>
      ) : null}

      {selectedCampaign?.events?.length ? (
        <details className="border-t border-slate-200 pt-3">
          <summary className="min-h-10 cursor-pointer text-sm font-semibold text-slate-700">Журнал кампании</summary>
          <div className="space-y-2 pt-2">
            {selectedCampaign.events.slice(0, 20).map((event, index) => (
              <div key={event.id || `${event.event_type}-${index}`} className="flex items-start justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-700">
                <span>{event.event_type}{event.reason_code ? ` · ${event.reason_code}` : ''}</span>
                <span className="shrink-0 tabular-nums text-slate-500">{formatDate(event.created_at)}</span>
              </div>
            ))}
          </div>
        </details>
      ) : null}

      <p className="text-xs leading-5 text-slate-500">
        Перед каждым касанием LocalOS проверит approval версии, sender account, tenant, ответы, DNC, cooldown, лимит и sender health. Business: {businessId || '—'}.
      </p>
    </div>
  );
}
