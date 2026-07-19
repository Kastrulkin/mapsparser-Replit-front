import { ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { AnalyticsSection, AnalyticsSummaryGrid } from '@/components/prospecting/ProspectingAnalyticsBlocks';

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

type PilotSummary = {
  total: number;
  parsed: number;
  readyForDraft: number;
  waitingApproval: number;
  waitingOutcome: number;
  acceptance: number;
};

type BestSource = {
  source_kind?: string;
  source_provider?: string;
} | null;

type FunnelStage = {
  key: string;
  label: string;
  count?: number;
  conversion_from_prev_pct?: number;
};

type FunnelData = {
  funnel?: FunnelStage[];
  summary?: {
    work_to_contact_pct?: number;
    reply_to_conversion_pct?: number;
    total_count?: number;
    contacted_count?: number;
    converted_count?: number;
  };
} | null;

type SourceQualityItem = {
  source_kind?: string;
  source_provider?: string;
  leads_total?: number;
  audited_count?: number;
  matched_count?: number;
  draft_count?: number;
  sent_count?: number;
  audit_rate_pct?: number;
  match_rate_pct?: number;
  draft_rate_pct?: number;
  sent_rate_pct?: number;
  positive_rate_pct?: number;
  lead_to_positive_pct?: number;
};

type SourceQualityData = {
  items?: SourceQualityItem[];
} | null;

type BlockerItem = {
  key: string;
  label: string;
  count?: number;
  severity?: 'info' | 'warning' | 'danger';
  hint?: string;
};

type BlockersData = {
  blockers?: BlockerItem[];
} | null;

type OutcomeChannel = {
  channel?: string;
  total?: number;
  positive_count?: number;
  question_count?: number;
  no_response_count?: number;
  hard_no_count?: number;
};

type OutcomesData = {
  summary?: {
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
  by_channel?: OutcomeChannel[];
} | null;

type PartnershipAnalyticsWorkspaceProps = {
  loading: boolean;
  health: PartnershipHealth | null;
  pilotSummary: PilotSummary;
  bestSourceThisWeek: BestSource;
  ralphLoopPanel: ReactNode;
  outreachLearningPanel: ReactNode;
  funnel: FunnelData;
  sourceQuality: SourceQualityData;
  blockers: BlockersData;
  outcomes: OutcomesData;
  onExportWeeklyReview: () => void;
  onExportReport: (format: 'json' | 'markdown') => void;
  onLoadHealth: () => void;
  onFocusBestSourceLeads: () => void;
  onMoveBestSourceToPilot: () => void;
  onRunBestSourcePilotFlow: () => void;
  onPrepareBestSourceBatch: () => void;
  onLoadFunnel: () => void;
  onLoadSourceQuality: () => void;
  onLoadBlockers: () => void;
  onLoadOutcomes: () => void;
};

const blockerTone = (severity?: string) => {
  if (severity === 'danger') return 'border-rose-200 bg-rose-50';
  if (severity === 'warning') return 'border-amber-200 bg-amber-50';
  return 'border-sky-200 bg-sky-50';
};

const outcomeLabel = (value: string) => {
  if (value === 'positive') return 'Интерес';
  if (value === 'question') return 'Вопрос';
  if (value === 'no_response') return 'Нет ответа';
  if (value === 'hard_no') return 'Отказ';
  return value;
};

const sourceKindLabel = (value?: string) => {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized.includes('google_doc')) return 'Документ';
  if (normalized.includes('yandex')) return 'Яндекс Карты';
  if (normalized.includes('2gis')) return '2ГИС';
  if (normalized.includes('manual')) return 'Ручной ввод';
  if (normalized.includes('network')) return 'Сеть / ручной список';
  return value || 'Источник не указан';
};

const sourceProviderLabel = (value?: string) => {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return 'провайдер не указан';
  if (normalized.includes('google_doc')) return 'импорт из документа';
  if (normalized.includes('yandex')) return 'поиск на картах';
  if (normalized.includes('manual')) return 'ручное добавление';
  return value || 'провайдер не указан';
};

const sourceLabel = (kind?: string, provider?: string) =>
  `${sourceKindLabel(kind)} · ${sourceProviderLabel(provider)}`;

const channelLabel = (value?: string) => {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'telegram') return 'Telegram';
  if (normalized === 'whatsapp') return 'WhatsApp';
  if (normalized === 'email') return 'Email';
  if (normalized === 'manual') return 'Вручную';
  if (normalized === 'max') return 'Max';
  return value || 'Канал не указан';
};

export const PartnershipAnalyticsWorkspace = ({
  loading,
  health,
  pilotSummary,
  bestSourceThisWeek,
  ralphLoopPanel,
  outreachLearningPanel,
  funnel,
  sourceQuality,
  blockers,
  outcomes,
  onExportWeeklyReview,
  onExportReport,
  onLoadHealth,
  onFocusBestSourceLeads,
  onMoveBestSourceToPilot,
  onRunBestSourcePilotFlow,
  onPrepareBestSourceBatch,
  onLoadFunnel,
  onLoadSourceQuality,
  onLoadBlockers,
  onLoadOutcomes,
}: PartnershipAnalyticsWorkspaceProps) => (
  <>
    <AnalyticsSection
      title="Состояние поиска партнёров"
      actions={(
        <>
          <Button variant="outline" onClick={onExportWeeklyReview} disabled={loading}>Еженедельный отчёт</Button>
          <Button variant="outline" onClick={() => onExportReport('json')} disabled={loading}>Экспорт JSON</Button>
          <Button variant="outline" onClick={() => onExportReport('markdown')} disabled={loading}>Экспорт Markdown</Button>
          <Button variant="outline" onClick={onLoadHealth} disabled={loading}>Обновить</Button>
        </>
      )}
    >
      {!health ? (
        <p className="text-sm text-muted-foreground">Проверка недоступна.</p>
      ) : (
        <div className="grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="font-semibold text-foreground">Поиск и обогащение</div>
            <div className="mt-1 text-muted-foreground">Сервис включён: {health.openclaw?.enabled ? 'да' : 'нет'}</div>
            <div className="text-muted-foreground">API настроен: {health.openclaw?.caps_endpoint_configured ? 'да' : 'нет'}</div>
            <div className="text-muted-foreground">Ключ доступа: {health.openclaw?.token_configured ? 'задан' : 'не задан'}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="font-semibold text-foreground">Объёмы</div>
            <div className="mt-1 text-muted-foreground">Партнёры: {health.counts?.leads_total ?? 0} · Письма: {health.counts?.drafts_total ?? 0}</div>
            <div className="text-muted-foreground">Очереди: {health.counts?.batches_total ?? 0} · Реакции: {health.counts?.reactions_total ?? 0}</div>
          </div>
        </div>
      )}
    </AnalyticsSection>

  <AnalyticsSection title="Сводка оператора" description="Короткий срез по текущему бизнесу">
    <AnalyticsSummaryGrid
      columnsClassName="md:grid-cols-3 xl:grid-cols-6"
        items={[
          { key: 'pilot-total', label: 'Лиды', value: pilotSummary.total, helper: 'Всего в текущем бизнесе' },
          { key: 'pilot-parsed', label: 'Данные готовы', value: pilotSummary.parsed, helper: 'Можно переходить к письмам', tone: 'text-sky-700' },
          { key: 'pilot-ready', label: 'Готовы к письму', value: pilotSummary.readyForDraft, helper: 'Можно готовить первое сообщение', tone: 'text-violet-700' },
          { key: 'pilot-approval', label: 'Ждут утверждения', value: pilotSummary.waitingApproval, helper: 'Есть письма или очереди на согласовании', tone: 'text-amber-700' },
          { key: 'pilot-outcome', label: 'Ждут результата', value: pilotSummary.waitingOutcome, helper: 'Отправлено, но ответ ещё не зафиксирован', tone: 'text-blue-700' },
          { key: 'pilot-positive', label: 'Интерес', value: `${pilotSummary.acceptance}%`, helper: 'Текущий показатель положительных ответов', tone: 'text-emerald-700' },
        ]}
    />
  </AnalyticsSection>

  <AnalyticsSection
    title="Отчёт по этапам кампании"
    description="Короткая цепочка, по которой оператор понимает, где сейчас теряются партнёры."
  >
    <div className="grid grid-cols-1 gap-2 md:grid-cols-5">
      {[
        {
          key: 'candidates',
          label: '1. Кандидаты',
          value: pilotSummary.total,
          helper: 'Все найденные партнёры',
        },
        {
          key: 'ready',
          label: '2. Готовы к письму',
          value: pilotSummary.readyForDraft,
          helper: 'Есть данные для первого контакта',
        },
        {
          key: 'approval',
          label: '3. Письма',
          value: pilotSummary.waitingApproval,
          helper: 'Ждут проверки или очереди',
        },
        {
          key: 'outcome',
          label: '4. Отправлено',
          value: pilotSummary.waitingOutcome,
          helper: 'Нужно зафиксировать результат',
        },
        {
          key: 'positive',
          label: '5. Интерес',
          value: `${pilotSummary.acceptance}%`,
          helper: 'Доля положительных ответов',
        },
      ].map((stage) => (
        <div key={stage.key} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
          <div className="text-xs font-medium uppercase text-muted-foreground">{stage.label}</div>
          <div className="mt-1 text-2xl font-semibold text-foreground">{stage.value}</div>
          <div className="mt-1 text-xs text-muted-foreground">{stage.helper}</div>
        </div>
      ))}
    </div>
  </AnalyticsSection>

  <AnalyticsSection
    title="Лучшее действие на неделю"
      description={bestSourceThisWeek ? `Лучший источник: ${sourceLabel(bestSourceThisWeek.source_kind, bestSourceThisWeek.source_provider)}` : 'Лучший источник недели пока не определён'}
    >
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={onExportWeeklyReview} disabled={loading}>Еженедельный отчёт</Button>
        <Button variant="outline" onClick={onFocusBestSourceLeads} disabled={loading || !bestSourceThisWeek}>Показать лиды</Button>
        <Button onClick={onMoveBestSourceToPilot} disabled={loading || !bestSourceThisWeek}>В пилотную группу</Button>
        <Button variant="outline" onClick={onRunBestSourcePilotFlow} disabled={loading || !bestSourceThisWeek}>Подготовить цепочку</Button>
        <Button variant="outline" onClick={onPrepareBestSourceBatch} disabled={loading || !bestSourceThisWeek}>Подготовить очередь</Button>
      </div>
      <div className="text-xs text-muted-foreground">Это короткий операторский путь: выбрать лучший источник, подготовить цепочку действий и собрать очередь отправки.</div>
    </AnalyticsSection>

    <div className="space-y-3 rounded-3xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Воронка партнёрств (30 дней)</h2>
        <Button variant="outline" onClick={onLoadFunnel} disabled={loading}>Обновить</Button>
      </div>
      {!funnel || !Array.isArray(funnel.funnel) ? (
        <p className="text-sm text-muted-foreground">Данные воронки пока недоступны.</p>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-5">
            {funnel.funnel.map((stage) => (
              <div key={stage.key} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">{stage.label}</div>
                <div className="mt-1 text-2xl font-semibold text-foreground">{stage.count ?? 0}</div>
                {stage.key !== 'unprocessed' && stage.conversion_from_prev_pct !== undefined ? <div className="mt-1 text-xs text-muted-foreground">Конверсия: {stage.conversion_from_prev_pct ?? 0}%</div> : null}
              </div>
            ))}
          </div>
          <div className="text-sm text-muted-foreground">
            Работа → контакт: <span className="font-medium text-foreground">{funnel.summary?.work_to_contact_pct ?? 0}%</span>{' '}
            · ответ → конверсия: <span className="font-medium text-foreground">{funnel.summary?.reply_to_conversion_pct ?? 0}%</span>{' '}
            · всего в срезе: {funnel.summary?.total_count ?? 0}
          </div>
        </>
      )}
    </div>

    <div className="space-y-3 rounded-3xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Качество источников лидов</h2>
        <Button variant="outline" onClick={onLoadSourceQuality} disabled={loading}>Обновить</Button>
      </div>
      {!sourceQuality || !Array.isArray(sourceQuality.items) || sourceQuality.items.length === 0 ? (
        <p className="text-sm text-muted-foreground">Пока нет данных по качеству источников.</p>
      ) : (
        <div className="space-y-2">
          {sourceQuality.items.map((item, index) => (
            <div key={`${item.source_kind || 'source'}-${item.source_provider || 'provider'}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
              <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="font-medium text-foreground">{sourceLabel(item.source_kind, item.source_provider)}</div>
                  <div className="mt-1 text-xs text-muted-foreground">Партнёров: {item.leads_total ?? 0} · Аудит: {item.audited_count ?? 0} · Оффер подобран: {item.matched_count ?? 0} · Письма: {item.draft_count ?? 0} · Отправлено: {item.sent_count ?? 0}</div>
                </div>
                <div className="text-sm text-muted-foreground">партнёр → интерес: <span className="font-medium text-foreground">{item.lead_to_positive_pct ?? 0}%</span></div>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs md:grid-cols-5">
                {[
                  ['Аудит', item.audit_rate_pct],
                  ['Оффер', item.match_rate_pct],
                  ['Письма', item.draft_rate_pct],
                  ['Отправка', item.sent_rate_pct],
                  ['Интерес', item.positive_rate_pct],
                ].map(([label, value]) => (
                  <div key={String(label)} className="rounded-md border border-white bg-white p-2">
                    <div className="uppercase text-muted-foreground">{label}</div>
                    <div className="mt-1 text-sm font-semibold text-foreground">{value ?? 0}%</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>

    <div className="space-y-3 rounded-3xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Что тормозит конверсию</h2>
        <Button variant="outline" onClick={onLoadBlockers} disabled={loading}>Обновить</Button>
      </div>
      {!blockers || !Array.isArray(blockers.blockers) ? (
        <p className="text-sm text-muted-foreground">Диагностика пока недоступна.</p>
      ) : (
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
          {blockers.blockers.map((item) => (
            <div key={item.key} className={`rounded-lg border p-3 ${blockerTone(item.severity)}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="text-sm font-semibold text-foreground">{item.label}</div>
                <div className="text-2xl font-semibold text-foreground">{item.count ?? 0}</div>
              </div>
              <div className="mt-2 text-xs text-muted-foreground">{item.hint || '—'}</div>
            </div>
          ))}
        </div>
      )}
    </div>

    <div className="space-y-3 rounded-3xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Результаты касаний (30 дней)</h2>
        <Button variant="outline" onClick={onLoadOutcomes} disabled={loading}>Обновить</Button>
      </div>
      {!outcomes?.summary ? (
        <p className="text-sm text-muted-foreground">Данные по результатам пока недоступны.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4"><div className="text-xs uppercase text-muted-foreground">Всего</div><div className="text-2xl font-semibold">{outcomes.summary.total_reactions ?? 0}</div></div>
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3"><div className="text-xs uppercase text-emerald-700">Интерес</div><div className="text-2xl font-semibold text-emerald-700">{outcomes.summary.positive_count ?? 0}</div><div className="text-xs text-emerald-700">{outcomes.summary.positive_rate_pct ?? 0}%</div></div>
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-3"><div className="text-xs uppercase text-blue-700">Вопрос</div><div className="text-2xl font-semibold text-blue-700">{outcomes.summary.question_count ?? 0}</div><div className="text-xs text-blue-700">{outcomes.summary.question_rate_pct ?? 0}%</div></div>
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3"><div className="text-xs uppercase text-amber-700">Нет ответа</div><div className="text-2xl font-semibold text-amber-700">{outcomes.summary.no_response_count ?? 0}</div><div className="text-xs text-amber-700">{outcomes.summary.no_response_rate_pct ?? 0}%</div></div>
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-3"><div className="text-xs uppercase text-rose-700">Отказ</div><div className="text-2xl font-semibold text-rose-700">{outcomes.summary.hard_no_count ?? 0}</div><div className="text-xs text-rose-700">{outcomes.summary.hard_no_rate_pct ?? 0}%</div></div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="mb-2 text-sm font-medium">По каналам</div>
            {!Array.isArray(outcomes.by_channel) || outcomes.by_channel.length === 0 ? (
              <div className="text-sm text-muted-foreground">Пока нет разбивки по каналам.</div>
            ) : (
              <div className="space-y-1 text-sm">
                {outcomes.by_channel.map((channel, index) => (
                  <div key={`${channel.channel || 'channel'}-${index}`} className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{channelLabel(channel.channel)}</span>
                    <span className="text-muted-foreground">всего: {channel.total ?? 0}</span>
                    <span className="text-emerald-700">{outcomeLabel('positive')}: {channel.positive_count ?? 0}</span>
                    <span className="text-blue-700">{outcomeLabel('question')}: {channel.question_count ?? 0}</span>
                    <span className="text-amber-700">{outcomeLabel('no_response')}: {channel.no_response_count ?? 0}</span>
                    <span className="text-rose-700">{outcomeLabel('hard_no')}: {channel.hard_no_count ?? 0}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>

    {outreachLearningPanel}

    <details className="rounded-3xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
      <summary className="cursor-pointer text-sm font-semibold text-slate-950">
        Дополнительно: обучение и рекомендации
      </summary>
      <div className="mt-4">
        {ralphLoopPanel}
      </div>
    </details>
  </>
);
