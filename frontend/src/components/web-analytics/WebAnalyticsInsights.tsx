import {
  AlertTriangle,
  CheckCircle2,
  MousePointerClick,
  Smartphone,
  Users,
} from "lucide-react";

import { DashboardSection } from "@/components/dashboard/DashboardPrimitives";

type FunnelStage = { key: string; label: string; sessions: number };
type CtaRow = {
  cta_id: string;
  label?: string | null;
  impressions: number;
  clicks: number;
  ctr_percent: number;
  confirmed?: number;
  page_path?: string | null;
  section_key?: string | null;
  position?: string | null;
};
type FormRow = {
  form_id: string;
  starts: number;
  validation_errors: number;
  attempts: number;
  successes: number;
  submit_errors: number;
};
type OutcomeRow = {
  event_type: string;
  count: number;
  attributed: number;
  revenue: number | string;
  currency?: string | null;
};
type DeviceRow = { device_type: string; sessions: number; visitors: number };
type Recommendation = { kind: string; title: string; detail: string };
type CampaignRow = {
  source: string;
  campaign: string;
  content?: string;
  sessions: number;
  leads: number;
  bookings: number;
  revenue: number | string;
  cost: number | string;
  cpa?: number | string | null;
  roi_percent?: number | string | null;
  currency?: string | null;
};
type TrendRow = { day: string; sessions: number; outcomes: number };
type InsightMetrics = {
  funnel_v2?: { configured: boolean; stages: FunnelStage[] };
  cta_performance?: CtaRow[];
  form_funnels?: FormRow[];
  confirmed_outcomes?: OutcomeRow[];
  devices?: DeviceRow[];
  visitor_cohorts?: { new_visitors?: number; returning_visitors?: number };
  recommendations?: Recommendation[];
  campaigns?: { performance?: CampaignRow[] };
  daily_trend?: TrendRow[];
  annotations?: Array<{ id: string; occurred_at: string; title: string }>;
};

const count = (value: unknown) => {
  const result = Number(value || 0);
  return Number.isFinite(result) ? result : 0;
};

const eventLabels: Record<string, string> = {
  lead_created: "Заявки",
  message_started: "Начатые диалоги",
  message_lead: "Заявки из мессенджеров",
  call_connected: "Состоявшиеся звонки",
  call_answered: "Принятые звонки",
  call_qualified: "Целевые звонки",
  booking_created: "Созданные записи",
  booking_confirmed: "Подтверждённые записи",
  booking_cancelled: "Отмены",
  visit_completed: "Состоявшиеся визиты",
  payment_completed: "Оплаты",
};

const deviceLabels: Record<string, string> = {
  mobile: "Телефон",
  tablet: "Планшет",
  desktop: "Компьютер",
  unknown: "Не определено",
};

export const WebAnalyticsInsights = ({
  metrics,
  locale,
}: {
  metrics: InsightMetrics | null;
  locale: string;
}) => {
  const format = (value: unknown) =>
    new Intl.NumberFormat(locale).format(count(value));
  const stages = metrics?.funnel_v2?.stages || [];
  const firstStage = count(stages[0]?.sessions);
  const trend = metrics?.daily_trend || [];
  const maxTrend = Math.max(1, ...trend.map((item) => count(item.sessions)));
  const annotationDays = new Set(
    (metrics?.annotations || []).map((item) =>
      String(item.occurred_at).slice(0, 10),
    ),
  );

  return (
    <div className="space-y-6">
      {(metrics?.recommendations || []).length ? (
        <DashboardSection
          title="Что требует внимания"
          description="LocalOS показывает только выводы, которые можно проверить по собранным данным."
        >
          <div className="grid gap-3 lg:grid-cols-2">
            {metrics?.recommendations?.map((item) => (
              <div
                key={`${item.kind}-${item.title}`}
                className="flex gap-3 rounded-2xl bg-amber-50 p-4 shadow-[inset_0_0_0_1px_rgba(217,119,6,0.18)]"
              >
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
                <div>
                  <h3 className="text-pretty text-sm font-semibold text-amber-950">
                    {item.title}
                  </h3>
                  <p className="mt-1 text-pretty text-sm leading-6 text-amber-800">
                    {item.detail}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </DashboardSection>
      ) : null}

      {trend.length ? (
        <DashboardSection
          title="Динамика и изменения"
          description="Метки показывают дни, когда вы меняли сайт, кампанию или трекер."
        >
          <div
            className="flex h-40 items-end gap-1 overflow-hidden rounded-2xl bg-slate-50 p-4 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.06)]"
            aria-label="Сессии по дням"
          >
            {trend.map((item) => (
              <div
                key={item.day}
                className="group relative flex h-full min-w-1 flex-1 items-end"
                title={`${item.day}: ${count(item.sessions)} сессий, ${count(item.outcomes)} результатов`}
              >
                <div
                  className="relative w-full rounded-t bg-slate-300 transition-[background-color] duration-150 group-hover:bg-slate-500"
                  style={{
                    height: `${Math.max(3, (count(item.sessions) * 100) / maxTrend)}%`,
                  }}
                >
                  {annotationDays.has(String(item.day).slice(0, 10)) ? (
                    <span
                      className="absolute -top-3 left-1/2 h-3 w-px bg-amber-600"
                      aria-label="В этот день было изменение"
                    />
                  ) : null}
                  {count(item.outcomes) ? (
                    <span className="absolute inset-x-0 bottom-0 h-1 rounded-full bg-emerald-500" />
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </DashboardSection>
      ) : null}

      <DashboardSection
        title="Воронка сайта"
        description={
          metrics?.funnel_v2?.configured
            ? "Группы страниц и цели настроены. Все значения считаются по уникальным сессиям."
            : "Настройте группы страниц, чтобы добавить этапы услуг и цен."
        }
      >
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {stages.map((stage, index) => {
            const stageValue = count(stage.sessions);
            const percent = firstStage
              ? Math.round((stageValue * 100) / firstStage)
              : 0;
            return (
              <div
                key={stage.key}
                className="relative rounded-2xl bg-slate-50 p-4 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.06)]"
              >
                <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                  Шаг {index + 1}
                </div>
                <div className="mt-2 text-sm font-semibold text-slate-800">
                  {stage.label}
                </div>
                <div className="mt-3 flex items-end justify-between gap-2">
                  <strong className="text-2xl text-slate-950 tabular-nums">
                    {format(stageValue)}
                  </strong>
                  <span className="text-sm text-slate-500 tabular-nums">
                    {percent}%
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </DashboardSection>

      <div className="grid gap-6 xl:grid-cols-2">
        <DashboardSection
          title="Кнопки, которые ведут к действию"
          description="Показы и клики считаются только для элементов с постоянным data-localos-cta."
        >
          {(metrics?.cta_performance || []).length ? (
            <div className="divide-y divide-slate-100">
              {metrics?.cta_performance?.map((item) => (
                <div
                  key={item.cta_id}
                  className="flex min-h-16 items-center gap-3 py-2"
                >
                  <div className="rounded-xl bg-slate-100 p-2 text-slate-600">
                    <MousePointerClick className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold text-slate-900">
                      {item.label || item.cta_id}
                    </div>
                    <div className="mt-1 text-xs text-slate-500 tabular-nums">
                      {format(item.clicks)} кликов из {format(item.impressions)}{" "}
                      показов
                      {item.confirmed
                        ? ` · ${format(item.confirmed)} подтверждено`
                        : ""}
                      {item.section_key ? ` · ${item.section_key}` : ""}
                    </div>
                  </div>
                  <strong className="tabular-nums text-slate-900">
                    {count(item.ctr_percent)}%
                  </strong>
                </div>
              ))}
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-slate-500">
              Разметьте основные кнопки, чтобы увидеть их CTR.
            </p>
          )}
        </DashboardSection>

        <DashboardSection
          title="Формы"
          description="Воронка не сохраняет имена, телефоны, комментарии и значения полей."
        >
          {(metrics?.form_funnels || []).length ? (
            <div className="space-y-3">
              {metrics?.form_funnels?.map((item) => (
                <div
                  key={item.form_id}
                  className="rounded-2xl bg-slate-50 p-4 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.06)]"
                >
                  <div className="font-semibold text-slate-900">
                    {item.form_id}
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                    <div>
                      <div className="text-lg font-semibold tabular-nums">
                        {format(item.starts)}
                      </div>
                      <div className="text-xs text-slate-500">Начали</div>
                    </div>
                    <div>
                      <div className="text-lg font-semibold tabular-nums">
                        {format(item.attempts)}
                      </div>
                      <div className="text-xs text-slate-500">Отправили</div>
                    </div>
                    <div>
                      <div className="text-lg font-semibold text-emerald-700 tabular-nums">
                        {format(item.successes)}
                      </div>
                      <div className="text-xs text-slate-500">Успешно</div>
                    </div>
                  </div>
                  {count(item.validation_errors) + count(item.submit_errors) ? (
                    <div className="mt-3 text-xs text-rose-700 tabular-nums">
                      Ошибок:{" "}
                      {format(
                        count(item.validation_errors) +
                          count(item.submit_errors),
                      )}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-slate-500">
              Стадии формы появятся после обновления трекера на сайте.
            </p>
          )}
        </DashboardSection>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <DashboardSection
          title="Подтверждённые результаты"
          description="Эти события поступают из CRM, телефонии, системы записи или оплаты."
        >
          {(metrics?.confirmed_outcomes || []).length ? (
            <div className="divide-y divide-slate-100">
              {metrics?.confirmed_outcomes?.map((item) => (
                <div
                  key={item.event_type}
                  className="flex min-h-14 items-center gap-3 py-2"
                >
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                  <span className="min-w-0 flex-1 text-sm font-medium text-slate-700">
                    {eventLabels[item.event_type] || item.event_type}
                  </span>
                  <strong className="tabular-nums text-slate-950">
                    {format(item.count)}
                  </strong>
                  {count(item.revenue) ? (
                    <span className="text-sm text-slate-500 tabular-nums">
                      {format(item.revenue)} {item.currency}
                    </span>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-slate-500">
              Подключите CRM или webhook, чтобы отличать намерение от
              состоявшейся продажи.
            </p>
          )}
        </DashboardSection>

        <DashboardSection
          title="Аудитория"
          description="Сравнение устройств, новых и вернувшихся анонимных посетителей."
        >
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-2xl bg-slate-950 p-4 text-white">
              <Users className="h-5 w-5 text-slate-300" />
              <div className="mt-4 text-2xl font-semibold tabular-nums">
                {format(metrics?.visitor_cohorts?.new_visitors)}
              </div>
              <div className="mt-1 text-sm text-slate-300">
                Новые посетители
              </div>
            </div>
            <div className="rounded-2xl bg-slate-100 p-4 text-slate-950">
              <Users className="h-5 w-5 text-slate-500" />
              <div className="mt-4 text-2xl font-semibold tabular-nums">
                {format(metrics?.visitor_cohorts?.returning_visitors)}
              </div>
              <div className="mt-1 text-sm text-slate-600">Вернувшиеся</div>
            </div>
          </div>
          <div className="mt-4 divide-y divide-slate-100">
            {metrics?.devices?.map((item) => (
              <div
                key={item.device_type}
                className="flex min-h-11 items-center gap-2 py-1"
              >
                <Smartphone className="h-4 w-4 text-slate-400" />
                <span className="flex-1 text-sm text-slate-700">
                  {deviceLabels[item.device_type] || item.device_type}
                </span>
                <span className="text-sm font-semibold tabular-nums">
                  {format(item.sessions)}
                </span>
              </div>
            ))}
          </div>
        </DashboardSection>
      </div>

      {(metrics?.campaigns?.performance || []).length ? (
        <DashboardSection
          title="Кампании: от визита до денег"
          description="CPA и ROI появляются, когда UTM-метки, расходы и подтверждённые результаты относятся к одной кампании."
        >
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-[0.1em] text-slate-400">
                  <th className="px-3 py-3">
                    Источник / кампания / объявление
                  </th>
                  <th className="px-3 py-3 text-right">Сессии</th>
                  <th className="px-3 py-3 text-right">Заявки</th>
                  <th className="px-3 py-3 text-right">Записи</th>
                  <th className="px-3 py-3 text-right">Расход</th>
                  <th className="px-3 py-3 text-right">CPA</th>
                  <th className="px-3 py-3 text-right">ROI</th>
                </tr>
              </thead>
              <tbody>
                {metrics?.campaigns?.performance?.map((item) => (
                  <tr
                    key={`${item.source}-${item.campaign}-${item.content || ""}`}
                    className="border-b border-slate-100 last:border-0"
                  >
                    <td className="px-3 py-4 font-medium text-slate-900">
                      {item.source}
                      {item.campaign ? ` · ${item.campaign}` : ""}
                      {item.content ? ` · ${item.content}` : ""}
                    </td>
                    <td className="px-3 py-4 text-right tabular-nums">
                      {format(item.sessions)}
                    </td>
                    <td className="px-3 py-4 text-right tabular-nums">
                      {format(item.leads)}
                    </td>
                    <td className="px-3 py-4 text-right tabular-nums">
                      {format(item.bookings)}
                    </td>
                    <td className="px-3 py-4 text-right tabular-nums">
                      {format(item.cost)}
                    </td>
                    <td className="px-3 py-4 text-right tabular-nums">
                      {item.cpa == null ? "—" : format(item.cpa)}
                    </td>
                    <td className="px-3 py-4 text-right font-semibold tabular-nums">
                      {item.roi_percent == null
                        ? "—"
                        : `${count(item.roi_percent)}%`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </DashboardSection>
      ) : null}
    </div>
  );
};
