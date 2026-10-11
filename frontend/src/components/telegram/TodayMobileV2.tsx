import { workCoherenceCopy } from '@/i18n/workCoherenceCopy';
import { todayClarityCopy } from '@/i18n/todayClarityCopy';
import { workSections, type TodayItem } from '@/pages/dashboard/todayWorkModel';
import { safeWorkReturn, workNavigationCopy } from '@/lib/workNavigation';
import { workStatusLabel, workStatusDetail } from '@/lib/workStatus';
import { useState, type FormEvent, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  ArrowUpRight,
  Check,
  ChevronRight,
  Clock3,
  Radio,
  Send,
  Sparkles,
} from 'lucide-react';
import { GrowthLoopPanel, type AnalyticsLevel, type AnalyticsModule, type DataHealth, type GrowthLoop, type GrowthRhythm, type LocationBreakdown, type NetworkSummary, type ProblemLocation } from '@/components/telegram/GrowthLoopPanel';
import { ruCountLabel } from '@/lib/ruPlural';
import { JourneyActionCard } from '@/components/journey/JourneyActionCard';
import type { JourneyAction } from '@/lib/leadJourney';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { getTodayPageCopy } from '@/i18n/todayPageCopy';
import { getTodayMobileCopy, isTodayPreferredFlow, type TodayPreferredFlow } from '@/i18n/todayMobileCopy';

export type TodayFocusAction = {
  href?: string;
  priority?: number;
  id?: string;
  title?: string;
  reason?: string;
  expected_outcome?: string;
  cta_label?: string;
  screen?: string;
  count?: number;
  target_scope?: { kind?: string; id?: string };
};

export type TodayActivityItem = {
  status?: string; work_status?: string; entity_type?: string; entity_id?: string; kind?: string; due_at?: string | null; requires_decision?: boolean; action?: TodayItem['action'];
  flow?: string;
  urgency?: string;
  preview?: string | null;
  id?: string;
  title?: string;
  description?: string;
  stage?: string;
  source?: string;
  occurred_at?: string;
  last_discussed_at?: string;
  progress?: number | null;
  screen?: string;
  business_id?: string;
  business_name?: string;
};

export type CommunityPulseItem = TodayActivityItem & {
  eyebrow?: string;
  message_count?: number;
  sources_count?: number;
  source_name?: string;
  source_url?: string;
};

export type TodayPayload = {
  preference?: { primary_flow: string; available_flows?: string[] };
  work_source_states?: Record<string, { status?: string }>;
  work_sections?: { needs_decision?: TodayActivityItem[]; continue_work?: TodayActivityItem[]; results?: TodayActivityItem[] };
  scope?: { kind?: 'platform' | 'network' | 'business'; id?: string | null; name?: string; business_ids?: string[] };
  focus_action?: TodayFocusAction | null;
  active_work?: TodayActivityItem[];
  changes_24h?: TodayActivityItem[];
  community_pulse?: CommunityPulseItem[];
  completed_results?: TodayActivityItem[];
  profile_reminders?: Array<{
    id: string;
    title: string;
    description?: string;
    cta_label?: string;
    screen?: string;
    business_id?: string;
    business_name?: string;
    target_scope?: { kind: 'business' | 'network' | 'platform'; id?: string | null };
  }>;
  progress_summary?: {
    completed_milestones?: number;
    total_milestones?: number;
    percent?: number;
  } | null;
  as_of?: string;
  data_warnings?: string[];
  growth_loop?: GrowthLoop | null;
  data_health?: DataHealth | null;
  analytics_level?: AnalyticsLevel | null;
  rhythm?: GrowthRhythm | null;
  analytics_modules?: AnalyticsModule[];
  network_summary?: NetworkSummary | null;
  problem_locations?: ProblemLocation[];
  location_breakdown?: LocationBreakdown[];
  journey_actions?: JourneyAction[];
};

type TodayMobileV2Props = {
  data?: TodayPayload | null;
  loading: boolean;
  slowLoading: boolean;
  command: string;
  setCommand: (value: string) => void;
  ask: (event: FormEvent) => void;
  openTarget: (screen?: string, targetScope?: { kind?: string; id?: string }) => void;
  openProgress: () => void;
  openSources?: () => void;
  track: (eventName: string, target?: string) => void;
  trackProduct?: (eventName: 'mission_open' | 'statistics_flow_opened', objectId?: string) => void;
  openFinanceImport?: () => void;
  refresh?: () => void;
};

const spring = { type: 'spring', duration: 0.3, bounce: 0 };

const timeLabel = (value?: string, language?: string) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString(language, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const TodaySkeleton = ({ slow }: { slow: boolean }) => (
  <div className="space-y-3 px-4" aria-busy="true">
    <div className="h-60 animate-pulse rounded-[28px] bg-white/[0.045] motion-reduce:animate-none" />
    <div className="h-20 animate-pulse rounded-[22px] bg-white/[0.035] motion-reduce:animate-none" />
    <div className="space-y-2 pt-4">
      <div className="h-5 w-44 animate-pulse rounded-lg bg-white/[0.05] motion-reduce:animate-none" />
      <div className="h-16 animate-pulse rounded-[18px] bg-white/[0.035] motion-reduce:animate-none" />
      <div className="h-16 animate-pulse rounded-[18px] bg-white/[0.035] motion-reduce:animate-none" />
    </div>
    {slow ? <p className="text-center text-xs text-zinc-600">Сверяем свежие события и результаты бизнеса…</p> : null}
  </div>
);

const ActivityRow = ({
  item,
  icon: Icon,
  onClick,
  accent = false,
}: {
  item: TodayActivityItem;
  icon: typeof Check;
  onClick?: () => void;
  accent?: boolean;
}) => {
  const { language } = useLanguage();
  const sources: Record<string, string> = { yandex: 'Яндекс Карты', yandex_maps: 'Яндекс Карты', '2gis': '2ГИС', telegram: 'Telegram', vk: 'VK', import: 'Import', manual: 'LocalOS', localos: 'LocalOS', operator: 'LocalOS' };
  const content = (
    <>
      <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-[13px] ${accent ? 'bg-emerald-400/10 text-emerald-300' : 'bg-white/[0.045] text-zinc-500'}`}>
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1">
        <b className="block text-pretty text-sm leading-5 text-zinc-200">{item.title || 'Новое событие'}</b>
        {item.description ? <small className="mt-1 block text-pretty text-[11px] leading-4 text-zinc-600">{item.description}</small> : null}
        <small className="mt-1 block truncate text-[10px] text-zinc-700">
          {[item.business_name, sources[item.source || ''] || workNavigationCopy(language).unknownSource, timeLabel(item.occurred_at, language)].filter(Boolean).join(' · ')}
        </small>
      </span>
      {onClick ? <ChevronRight className="h-4 w-4 shrink-0 text-zinc-700" /> : null}
    </>
  );
  if (!onClick) return <div className="flex min-h-16 items-start gap-3 py-3">{content}</div>;
  return <button type="button" onClick={onClick} className="flex min-h-16 w-full items-start gap-3 py-3 text-left transition-transform active:scale-[0.96]">{content}</button>;
};

const Section = ({ title, subtitle, action, children }: { title: string; subtitle?: string; action?: ReactNode; children: ReactNode }) => (
  <section className="mt-7">
    <div className="flex min-h-11 items-center justify-between gap-3"><h2 className="text-balance text-lg font-semibold tracking-[-0.025em]">{title}</h2>{action}</div>
    {subtitle ? <p className="mt-1 text-pretty text-xs leading-5 text-zinc-600">{subtitle}</p> : null}
    <div className="mt-3 divide-y divide-white/[0.055]">{children}</div>
  </section>
);

export const TodayMobileV2 = ({
  data,
  loading,
  slowLoading,
  command,
  setCommand,
  ask,
  openTarget,
  openProgress,
  openSources,
  track,
  trackProduct,
  openFinanceImport,
  refresh,
}: TodayMobileV2Props) => {
  const { language } = useLanguage();
  const pageCopy = getTodayPageCopy(language);
  const mobileCopy = getTodayMobileCopy(language); const ui = todayClarityCopy(language);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  if (loading && !data) return <TodaySkeleton slow={slowLoading} />;

  const preferredFlow = data?.preference?.primary_flow;
  const preferredScreens: Record<TodayPreferredFlow, string> = { content: 'content', maps: 'cards', influencers: 'influencers', partnerships: 'partnerships', upsells: 'average_ticket', automation: 'agents' };
  const preferredFocusFlow = isTodayPreferredFlow(preferredFlow) &&
    (data?.preference?.available_flows || []).includes(preferredFlow) ? preferredFlow : null;
  const decisions = data?.work_sections?.needs_decision || [];
  const urgent = decisions.find((item) => item.urgency === 'urgent');
  const preferredItem = [...decisions, ...(data?.work_sections?.continue_work || [])].find((item) => item.flow === preferredFocusFlow);
  const personalizedFocus: TodayFocusAction | null = preferredFocusFlow ? {
    id: preferredItem?.id || `priority:${preferredFocusFlow}`,
    title: mobileCopy.preferredLabels[preferredFocusFlow],
    reason: preferredItem?.title || mobileCopy.preferredFallbackReason,
    cta_label: preferredFocusFlow === 'content' ? mobileCopy.preferredContentCta : mobileCopy.preferredGeneralCta,
    screen: preferredScreens[preferredFocusFlow],
    target_scope: preferredItem?.business_id ? { kind: 'business', id: preferredItem.business_id } : undefined,
  } : null;
  const urgentFlow = urgent?.flow;
  const urgentFlowScreen = isTodayPreferredFlow(urgentFlow) ? preferredScreens[urgentFlow] : undefined;
  const urgentFocus: TodayFocusAction | null = urgent ? {
    id: urgent.id, title: urgent.title, reason: urgent.description,
    screen: urgent.screen || urgentFlowScreen || 'tasks',
    cta_label: mobileCopy.urgentCta,
    target_scope: urgent.business_id ? { kind: 'business', id: urgent.business_id } : undefined,
  } : null;
  const legacyFocus = urgentFocus || ((data?.focus_action?.priority || 0) >= 100 ? data?.focus_action : personalizedFocus || data?.focus_action);
  const normalize = (item: TodayActivityItem): TodayItem => ({ ...item, id: item.id || JSON.stringify([item.business_id,item.entity_type,item.entity_id]), title: item.title || '', flow: isTodayPreferredFlow(item.flow) ? item.flow : undefined, urgency: item.urgency === 'urgent' ? 'urgent' : 'normal' });
  const coherent = data?.work_sections ? workSections({ preference: { scope_type: data.scope?.kind === 'network' ? 'network' : 'business', scope_id: data.scope?.id || '', primary_flow: preferredFocusFlow || 'overview', suggestions_enabled: true, revision: 0 }, work_sections: { needs_decision: (data.work_sections.needs_decision || []).map(normalize), continue_work: (data.work_sections.continue_work || []).map(normalize), results: (data.work_sections.results || []).map(normalize) } }, Date.parse(data.as_of || '') || Date.now()) : null;
  const sourceUnavailable = Object.values(data?.work_source_states || {}).some(source => source.status === 'error' || source.status === 'unavailable');
  const chosen = coherent?.primary;
  const focus: TodayFocusAction | null | undefined = chosen ? { id: chosen.id, title: chosen.title, reason: chosen.description || chosen.stage, cta_label: chosen.action?.label || mobileCopy.urgentCta, href: safeWorkReturn(chosen.action?.url) || undefined, screen: chosen.screen || (chosen.flow ? preferredScreens[chosen.flow] : undefined) || 'tasks', target_scope: chosen.business_id ? { kind: 'business', id: chosen.business_id } : undefined } : legacyFocus;
  const activeWork = (coherent?.continuing || data?.active_work || []).filter(item => item.id !== chosen?.id);
  const decisionWork = (coherent?.decisions || []).filter(item => item.id !== chosen?.id);
  const openWork = (item: TodayActivityItem) => { const href = safeWorkReturn(item.action?.url); if (href) window.location.assign(href); else openTarget(item.screen, item.business_id ? { kind: 'business', id: item.business_id } : undefined); };
  const changes = data?.changes_24h || [];
  const pulse = data?.community_pulse || [];
  const results = coherent?.results || workSections({ completed_results: (data?.completed_results || []).map(normalize) }, Date.now()).results;
  const profileReminders = data?.profile_reminders || [];
  const progress = data?.progress_summary;
  const isPlatform = data?.scope?.kind === 'platform';
  const isNetwork = data?.scope?.kind === 'network';
  const journeyActions = data?.journey_actions || [];

  return (
    <div className="px-4">
      {journeyActions.length && !personalizedFocus && !coherent && !legacyFocus ? <section className="space-y-3">{journeyActions.slice(0, 3).map((action) => action.business_id ? <JourneyActionCard key={action.id} action={action} businessId={action.business_id} surface="telegram_mini_app" dark onUpdated={() => refresh?.()} /> : null)}</section> : <motion.section
        initial={{ opacity: 0, y: 10, filter: 'blur(4px)' }}
        animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
        transition={spring}
        className="rounded-[28px] bg-gradient-to-b from-zinc-900 to-zinc-900/70 p-5 shadow-[0_24px_80px_rgba(0,0,0,0.28),0_0_0_1px_rgba(255,255,255,0.08)]"
      >
        <div className="flex items-center gap-2 text-xs font-medium text-primary">
          <Sparkles className="h-4 w-4" />
          {focus ? pageCopy.now : mobileCopy.noTasksEyebrow}
        </div>
        <div className="mt-4 flex items-start gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="text-balance text-[26px] font-semibold leading-8 tracking-[-0.045em]">
              {focus?.title || mobileCopy.emptyTitle}
            </h1>
            <p className="mt-2 text-pretty text-sm leading-6 text-zinc-400">
              {focus?.reason || (isNetwork ? mobileCopy.emptyNetworkReason : mobileCopy.emptyReason)}
            </p>
          </div>
          {focus?.count ? <b className="rounded-2xl bg-primary/15 px-3 py-2 text-xl tabular-nums text-primary">{focus.count}</b> : <Check className="h-8 w-8 shrink-0 text-emerald-400" />}
        </div>
        {focus?.expected_outcome ? (
          <div className="mt-4 rounded-[16px] bg-black/20 px-3 py-2.5 text-pretty text-xs leading-5 text-zinc-400">
            <b className="text-zinc-200">{pageCopy.after}</b> {focus.expected_outcome}
          </div>
        ) : null}
        <button
          type="button"
          onClick={() => {
            track('today_focus_open', focus?.screen || 'progress');
            trackProduct?.('mission_open', data?.growth_loop?.mission_id || focus?.id || focus?.screen);
            if (focus?.href) window.location.assign(focus.href);
            else if (focus) openTarget(focus.screen, focus.target_scope);
            else openProgress();
          }}
          className="mt-5 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-slate-950 pl-4 pr-3.5 text-sm font-semibold text-white ring-1 ring-white/20 transition-[filter,transform] active:scale-[0.96]"
        >
          {focus?.cta_label || (isPlatform ? mobileCopy.openPlatformQueue : mobileCopy.openGrowthPlan)}
          <ChevronRight className="h-4 w-4" />
        </button>
      </motion.section>}

      {!coherent && personalizedFocus && focus !== personalizedFocus ? <section className="mt-3 rounded-2xl bg-white/[0.04] p-4">
        <h2 className="text-balance text-lg font-semibold">{personalizedFocus.title}</h2>
        <p className="mt-1 text-sm text-zinc-400">{mobileCopy.preferredHint}</p>
        <button type="button" onClick={() => openTarget(personalizedFocus.screen, personalizedFocus.target_scope)} className="mt-3 min-h-11 rounded-xl bg-white/[0.08] px-4 text-sm font-semibold active:scale-[0.96]">{personalizedFocus.cta_label}</button>
      </section> : null}

      <details className="mt-3 rounded-xl bg-white/[0.025] p-3"><summary className="min-h-11 cursor-pointer py-2 text-sm">{ui.how}</summary><p className="text-sm text-zinc-400">{pageCopy.after} {ui.review} → {ui.decision} → {ui.running} → {ui.completed}</p></details>

      <section className="mt-3 overflow-hidden rounded-[22px] bg-white/[0.035] shadow-[0_0_0_1px_rgba(255,255,255,0.07)]">
        <div className="flex min-h-14 items-center gap-3 px-4">
          <Sparkles className="h-4 w-4 text-primary" />
          <h2 className="min-w-0 flex-1 text-balance text-sm font-semibold">Поручить ЛокалОС</h2>
        </div>
        <form onSubmit={ask} className="border-t border-white/[0.055] p-3">
          <div className="flex gap-2">
            <input onFocus={() => track('today_delegate_focus')} value={command} onChange={(event) => setCommand(event.target.value)} placeholder="Например: подготовь ответы" className="min-h-12 min-w-0 flex-1 rounded-2xl bg-black/20 px-4 text-sm outline-none ring-1 ring-inset ring-white/[0.07] placeholder:text-zinc-700 focus:ring-primary/50" />
            <button aria-label="Отправить поручение" className="grid h-12 w-12 place-items-center rounded-2xl bg-primary text-white transition-transform active:scale-[0.96]"><Send className="h-4 w-4" /></button>
          </div>
          <p className="px-1 pt-2 text-pretty text-[11px] leading-4 text-zinc-600">Опишите результат обычными словами. Перед публикацией, отправкой или оплатой ЛокалОС попросит подтверждение.</p>
        </form>
      </section>

      {[{ key: 'decisions', title: ui.decisions, items: coherent ? decisionWork : [], empty: ui.emptyDecisions }, { key: 'continuing', title: ui.continue, items: activeWork, empty: ui.emptyContinue }, { key: 'results', title: ui.completed, items: results, empty: ui.emptyResults }].map(section => <Section key={section.key} title={section.title} subtitle={ui.limited}>{section.items.length ? section.items.slice(0, expanded[section.key] ? undefined : 3).map(item => <ActivityRow key={JSON.stringify([item.business_id,item.entity_type,item.entity_id,item.id])} item={{ ...item, description: [workStatusDetail(item.status || item.work_status, language), item.description || item.stage].filter(Boolean).join(' · ') }} icon={section.key === 'results' ? Check : Clock3} accent={section.key === 'results'} onClick={() => openWork(item)} />) : <p className="py-3 text-sm text-zinc-400">{sourceUnavailable ? ui.sourceUnavailable : (section.key === 'decisions' ? coherent?.decisions : section.key === 'continuing' ? coherent?.continuing : [])?.some(item => item.id === chosen?.id) ? workCoherenceCopy(language).currentWorkAbove : section.empty}</p>}{section.items.length > 3 && !expanded[section.key] ? <button type="button" className="min-h-11 text-sm focus-visible:ring-2 focus-visible:ring-white" onClick={() => setExpanded(value => ({...value,[section.key]:true}))}>{ui.more}</button> : null}</Section>)}
      <details className="mt-4 rounded-xl bg-white/[0.025] p-3"><summary className="min-h-11 cursor-pointer py-2 text-sm">{ui.data}</summary><GrowthLoopPanel growthLoop={data?.growth_loop} dataHealth={data?.data_health} analyticsLevel={data?.analytics_level} rhythm={data?.rhythm} scopeKind={data?.scope?.kind} analyticsModules={data?.analytics_modules} networkSummary={data?.network_summary} problemLocations={data?.problem_locations} locationBreakdown={data?.location_breakdown} showImportAction={!['finance', 'finance_import'].includes(focus?.screen || '')} onOpenImport={() => { trackProduct?.('statistics_flow_opened', 'finance_import'); openFinanceImport?.(); }} onOpenLocation={(businessId, screen) => { trackProduct?.('statistics_flow_opened', businessId); openTarget(screen, { kind: 'business', id: businessId }); }} /></details>

      {profileReminders.length ? (
        <Section title="Сделайте ЛокалОС точнее" subtitle="Один раз расскажите о бизнесе — дальше эти факты будут использоваться в работе.">
          {profileReminders.slice(0, 3).map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => openTarget(item.screen || 'partnerships', item.target_scope)}
              className="flex min-h-20 w-full items-start gap-3 py-4 text-left transition-transform active:scale-[0.96]"
            >
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[13px] bg-primary/15 text-primary"><Sparkles className="h-4 w-4" /></span>
              <span className="min-w-0 flex-1">
                <b className="block text-balance text-sm leading-5">{item.title}</b>
                <small className="mt-1 block text-pretty text-[11px] leading-4 text-zinc-600">{item.description}</small>
                {item.business_name && isNetwork ? <small className="mt-2 block truncate text-[10px] text-zinc-700">{item.business_name}</small> : null}
              </span>
              <ChevronRight className="mt-3 h-4 w-4 shrink-0 text-zinc-700" />
            </button>
          ))}
        </Section>
      ) : null}

      <Section title="Что изменилось" subtitle="Отзывы, продажи и другие события за последние 24 часа.">
        {changes.length ? changes.slice(0, 3).map((item) => <ActivityRow key={item.id} item={item} icon={Clock3} onClick={() => openWork(item)} />) : (
          <div className="flex min-h-16 items-center gap-3 py-3 text-sm text-zinc-600"><Check className="h-5 w-5 text-emerald-400" />За последние сутки ничего нового.</div>
        )}
      </Section>

      {pulse.length || openSources ? (
        <Section title="Пульс сообщества" subtitle="Что обсуждали и публиковали в отраслевых источниках за последние сутки." action={openSources ? <button type="button" onClick={openSources} className="min-h-11 rounded-[14px] px-3 text-xs font-semibold text-zinc-400 ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]">Источники</button> : null}>
          {pulse.length ? pulse.map((item, index) => (
            <a
              key={item.id}
              href={item.source_url || undefined}
              target="_blank"
              rel="noreferrer"
              onClick={() => track('today_pulse_open', item.id)}
              className="flex min-h-20 items-start gap-3 py-4 transition-transform active:scale-[0.96]"
            >
              <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-[13px] ${index === 0 ? 'bg-primary/15 text-primary' : 'bg-white/[0.045] text-zinc-500'}`}><Radio className="h-4 w-4" /></span>
              <span className="min-w-0 flex-1">
                {item.eyebrow ? <small className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.14em] text-primary/80">{item.eyebrow}</small> : null}
                <b className="block text-balance text-sm leading-5">{item.title}</b>
                <small className="mt-1 block text-pretty text-[11px] leading-4 text-zinc-600">{item.description}</small>
                <small className="mt-2 block truncate text-[10px] text-zinc-700">{[item.source_name, item.message_count ? ruCountLabel(item.message_count, 'сообщение', 'сообщения', 'сообщений') : '', timeLabel(item.last_discussed_at, language)].filter(Boolean).join(' · ')}</small>
              </span>
              <ArrowUpRight className="h-4 w-4 shrink-0 text-zinc-700" />
            </a>
          )) : <button type="button" onClick={openSources} className="flex min-h-16 w-full items-center gap-3 py-3 text-left text-sm text-zinc-600"><Radio className="h-5 w-5 text-primary" /><span>За последние сутки заметных обсуждений не было. Можно добавить каналы, за которыми вы хотите следить.</span><ChevronRight className="ml-auto h-4 w-4" /></button>}
        </Section>
      ) : null}

      <button type="button" onClick={() => { track('today_progress_open', 'progress'); openProgress(); }} className="mt-5 min-h-12 w-full rounded-xl bg-white/[0.04] px-4 text-sm font-medium focus-visible:ring-2 focus-visible:ring-white">{pageCopy.openProgress}</button>

    </div>
  );
};
