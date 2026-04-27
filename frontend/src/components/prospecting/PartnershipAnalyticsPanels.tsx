import { ReactNode } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AnalyticsSection, AnalyticsSummaryGrid } from '@/components/prospecting/ProspectingAnalyticsBlocks';

type RalphLoopSummary = {
  leads_total?: number;
  parsed_completed_count?: number;
  audited_count?: number;
  matched_count?: number;
  drafts_total?: number;
  sent_total?: number;
  positive_count?: number;
  positive_rate_pct?: number;
};

type RalphLoopBaseline = {
  sent_total?: number;
  positive_count?: number;
  positive_rate_pct?: number;
  deltas?: {
    sent_total?: number;
    positive_count?: number;
    positive_rate_pct?: number;
  };
};

type RalphLoopTopChannel = {
  channel?: string;
  total?: number;
  positive_count?: number;
  positive_rate_pct?: number;
};

type RalphLoopSourcePerformance = {
  source_kind?: string;
  source_provider?: string;
  leads_total?: number;
  draft_rate_pct?: number;
  sent_count?: number;
  positive_rate_pct?: number;
  lead_to_positive_pct?: number;
};

type RalphLoopLearning = {
  capability?: string;
  edited_before_accept_pct?: number;
};

type RalphLoopPromptPerformance = {
  prompt_key?: string;
  prompt_version?: string;
  drafts_total?: number;
  approved_total?: number;
  edited_before_accept_pct?: number;
  sent_total?: number;
  positive_count?: number;
  positive_rate_pct?: number;
};

type RalphLoopEditInsights = {
  edited_accepts_total?: number;
  avg_generated_len?: number;
  avg_final_len?: number;
  expanded_count?: number;
  shortened_count?: number;
  unchanged_count?: number;
};

export type RalphLoopAnalyticsData = {
  summary?: RalphLoopSummary;
  baseline?: RalphLoopBaseline;
  top_channels?: RalphLoopTopChannel[];
  source_performance?: RalphLoopSourcePerformance[];
  learning?: RalphLoopLearning[];
  prompt_performance?: RalphLoopPromptPerformance[];
  recommended_prompt_version?: {
    prompt_key?: string;
    prompt_version?: string;
  } | null;
  blockers?: string[];
  recommendations?: string[];
  edit_insights?: RalphLoopEditInsights;
};

type RalphLoopAnalyticsPanelProps = {
  loading?: boolean;
  ralphLoop?: RalphLoopAnalyticsData | null;
  onRefresh: () => void;
  onFocusBestSource: () => void;
  onMoveBestSourceToPilot: () => void;
  onRunBestSourcePilotFlow: () => void;
  onPrepareBestSourceBatch: () => void;
  hasBestSource: boolean;
};

function deltaClassName(delta: number) {
  return delta >= 0 ? 'text-emerald-700' : 'text-rose-700';
}

function DeltaValue({ value, suffix = '' }: { value: number; suffix?: string }) {
  return (
    <span className={`ml-2 text-sm ${deltaClassName(value)}`}>
      {value >= 0 ? '+' : ''}
      {value}
      {suffix}
    </span>
  );
}

function InfoCard({
  title,
  children,
  tone = 'bg-gray-50 border-gray-200',
}: {
  title: string;
  children: ReactNode;
  tone?: string;
}) {
  return (
    <div className={`rounded-lg border p-3 ${tone}`}>
      <div className="text-sm font-semibold mb-2">{title}</div>
      {children}
    </div>
  );
}

export function RalphLoopAnalyticsPanel({
  loading,
  ralphLoop,
  onRefresh,
  onFocusBestSource,
  onMoveBestSourceToPilot,
  onRunBestSourcePilotFlow,
  onPrepareBestSourceBatch,
  hasBestSource,
}: RalphLoopAnalyticsPanelProps) {
  const summary = ralphLoop?.summary;
  const baseline = ralphLoop?.baseline;
  const editInsights = ralphLoop?.edit_insights;

  return (
    <AnalyticsSection
      title="Ralph loop summary (7 дней)"
      actions={
        <Button variant="outline" onClick={onRefresh} disabled={loading}>
          Обновить
        </Button>
      }
    >
      {!summary ? (
        <p className="text-sm text-muted-foreground">Недельная summary пока недоступна.</p>
      ) : (
        <div className="space-y-3">
          <AnalyticsSummaryGrid
            columnsClassName="md:grid-cols-4 xl:grid-cols-8"
            items={[
              { key: 'leads', label: 'Лиды', value: summary.leads_total ?? 0, helper: 'Всего за окно' },
              { key: 'parsed', label: 'Парсинг', value: summary.parsed_completed_count ?? 0, helper: 'Завершено', tone: 'text-sky-700' },
              { key: 'audited', label: 'Аудит', value: summary.audited_count ?? 0, helper: 'С данными', tone: 'text-indigo-700' },
              { key: 'matched', label: 'Матчинг', value: summary.matched_count ?? 0, helper: 'Совпадения найдены', tone: 'text-violet-700' },
              { key: 'drafts', label: 'Черновики', value: summary.drafts_total ?? 0, helper: 'Подготовлено', tone: 'text-amber-700' },
              { key: 'sent', label: 'Sent', value: summary.sent_total ?? 0, helper: 'Ушло в канал', tone: 'text-emerald-700' },
              { key: 'positive', label: 'Positive', value: summary.positive_count ?? 0, helper: 'Есть интерес', tone: 'text-green-700' },
              { key: 'rate', label: 'Positive rate', value: `${summary.positive_rate_pct ?? 0}%`, helper: 'Итог по окну', tone: 'text-teal-700' },
            ]}
          />

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            <InfoCard title="Сравнение с предыдущими 7 днями" tone="bg-blue-50 border-blue-200">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                <div className="rounded-lg border border-white/80 bg-white/80 p-3">
                  <div className="text-xs uppercase text-muted-foreground">Sent</div>
                  <div className="text-lg font-semibold text-foreground mt-1">
                    {summary.sent_total ?? 0}
                    <DeltaValue value={baseline?.deltas?.sent_total ?? 0} />
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">было: {baseline?.sent_total ?? 0}</div>
                </div>
                <div className="rounded-lg border border-white/80 bg-white/80 p-3">
                  <div className="text-xs uppercase text-muted-foreground">Positive</div>
                  <div className="text-lg font-semibold text-foreground mt-1">
                    {summary.positive_count ?? 0}
                    <DeltaValue value={baseline?.deltas?.positive_count ?? 0} />
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">было: {baseline?.positive_count ?? 0}</div>
                </div>
                <div className="rounded-lg border border-white/80 bg-white/80 p-3">
                  <div className="text-xs uppercase text-muted-foreground">Positive rate</div>
                  <div className="text-lg font-semibold text-foreground mt-1">
                    {summary.positive_rate_pct ?? 0}%
                    <DeltaValue value={baseline?.deltas?.positive_rate_pct ?? 0} suffix=" п.п." />
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">было: {baseline?.positive_rate_pct ?? 0}%</div>
                </div>
              </div>
            </InfoCard>

            <InfoCard title="Что менять на следующей неделе" tone="bg-amber-50 border-amber-200">
              {Array.isArray(ralphLoop?.recommendations) && ralphLoop.recommendations.length > 0 ? (
                <div className="space-y-1 text-sm">
                  {ralphLoop.recommendations.map((item, index) => (
                    <div key={`${item}-${index}`} className="text-muted-foreground">
                      {index + 1}. {item}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">
                  Явных рекомендаций пока нет. Можно продолжать текущий сценарий и смотреть на outcome.
                </div>
              )}
            </InfoCard>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
            <InfoCard title="Лучшие каналы">
              {Array.isArray(ralphLoop?.top_channels) && ralphLoop.top_channels.length > 0 ? (
                <div className="space-y-1 text-sm">
                  {ralphLoop.top_channels.map((item, index) => (
                    <div key={`${item.channel || 'channel'}-${index}`} className="flex items-center justify-between gap-2">
                      <span>{item.channel || 'unknown'}</span>
                      <span className="text-muted-foreground">
                        {item.positive_rate_pct ?? 0}% ({item.positive_count ?? 0}/{item.total ?? 0})
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">Пока нет канальной статистики.</div>
              )}
            </InfoCard>

            <InfoCard title="Источники недели">
              <div className="flex flex-wrap gap-2 mb-2">
                <Button size="sm" variant="outline" onClick={onFocusBestSource} disabled={loading || !hasBestSource}>
                  Показать лиды
                </Button>
                <Button size="sm" onClick={onMoveBestSourceToPilot} disabled={loading || !hasBestSource}>
                  В pilot cohort
                </Button>
                <Button size="sm" variant="outline" onClick={onRunBestSourcePilotFlow} disabled={loading || !hasBestSource}>
                  Pilot run
                </Button>
                <Button size="sm" variant="outline" onClick={onPrepareBestSourceBatch} disabled={loading || !hasBestSource}>
                  Batch prep
                </Button>
              </div>
              {Array.isArray(ralphLoop?.source_performance) && ralphLoop.source_performance.length > 0 ? (
                <div className="space-y-2 text-sm">
                  {ralphLoop.source_performance.slice(0, 3).map((item, index) => (
                    <div
                      key={`${item.source_kind || 'source'}-${item.source_provider || 'provider'}-${index}`}
                      className="rounded-lg border border-white/80 bg-white/80 p-3"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium text-foreground">
                          {item.source_kind || 'unknown'} / {item.source_provider || 'unknown'}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {item.lead_to_positive_pct ?? 0}% lead→positive
                        </span>
                      </div>
                      <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                        <div>Лидов: {item.leads_total ?? 0}</div>
                        <div>Sent: {item.sent_count ?? 0}</div>
                        <div>Draft: {item.draft_rate_pct ?? 0}%</div>
                        <div>Positive: {item.positive_rate_pct ?? 0}%</div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">Пока нет статистики по источникам за неделю.</div>
              )}
            </InfoCard>

            <InfoCard title="Обучение по промптам">
              {Array.isArray(ralphLoop?.learning) && ralphLoop.learning.length > 0 ? (
                <div className="space-y-1 text-sm">
                  {ralphLoop.learning.map((item, index) => (
                    <div key={`${item.capability || 'cap'}-${index}`} className="flex items-center justify-between gap-2">
                      <span>{item.capability || '—'}</span>
                      <span className="text-muted-foreground">{item.edited_before_accept_pct ?? 0}% правок</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">Пока нет learning-сигналов.</div>
              )}
            </InfoCard>
          </div>

          <InfoCard title="Что мешает росту">
            {Array.isArray(ralphLoop?.blockers) && ralphLoop.blockers.length > 0 ? (
              <div className="space-y-1 text-sm">
                {ralphLoop.blockers.map((item, index) => (
                  <div key={`${item}-${index}`} className="text-muted-foreground">{item}</div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">Явных блокеров за период не найдено.</div>
            )}
          </InfoCard>

          <InfoCard title="Как оператор правит первое письмо" tone="bg-fuchsia-50 border-fuchsia-200">
            {(editInsights?.edited_accepts_total ?? 0) > 0 ? (
              <AnalyticsSummaryGrid
                columnsClassName="md:grid-cols-3 xl:grid-cols-6"
                items={[
                  { key: 'edited-total', label: 'Правок', value: editInsights?.edited_accepts_total ?? 0, helper: 'Утверждённые письма' },
                  { key: 'generated', label: 'Черновик', value: editInsights?.avg_generated_len ?? 0, helper: 'ср. длина' },
                  { key: 'final', label: 'Финал', value: editInsights?.avg_final_len ?? 0, helper: 'ср. длина' },
                  { key: 'expanded', label: 'Дописывают', value: editInsights?.expanded_count ?? 0, helper: 'Удлинили текст' },
                  { key: 'shortened', label: 'Сокращают', value: editInsights?.shortened_count ?? 0, helper: 'Сжали текст' },
                  { key: 'unchanged', label: 'Без изменений', value: editInsights?.unchanged_count ?? 0, helper: 'Приняли как есть' },
                ]}
              />
            ) : (
              <div className="text-sm text-muted-foreground">
                Пока нет утверждённых писем с ручными правками за выбранное окно.
              </div>
            )}
          </InfoCard>

          <InfoCard title="Версии prompt для первого письма" tone="bg-cyan-50 border-cyan-200">
            <div className="flex items-center justify-between gap-2 mb-2">
              <div className="text-sm font-semibold">Какая версия даёт лучший отклик</div>
              {ralphLoop?.recommended_prompt_version ? (
                <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">
                  Рекомендовано: {ralphLoop.recommended_prompt_version.prompt_key || 'unknown'} · v{ralphLoop.recommended_prompt_version.prompt_version || 'unknown'}
                </Badge>
              ) : null}
            </div>
            {Array.isArray(ralphLoop?.prompt_performance) && ralphLoop.prompt_performance.length > 0 ? (
              <div className="space-y-2 text-sm">
                {ralphLoop.prompt_performance.map((item, index) => (
                  <div
                    key={`${item.prompt_key || 'prompt'}-${item.prompt_version || 'version'}-${index}`}
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
          </InfoCard>
        </div>
      )}
    </AnalyticsSection>
  );
}
