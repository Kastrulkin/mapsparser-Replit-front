import { FormEvent, ReactNode } from 'react';
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

export type TodayFocusAction = {
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
};

const spring = { type: 'spring', duration: 0.3, bounce: 0 };

const timeLabel = (value?: string) => {
  if (!value) return 'время не указано';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'время не указано';
  return date.toLocaleString('ru-RU', {
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
  const content = (
    <>
      <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-[13px] ${accent ? 'bg-emerald-400/10 text-emerald-300' : 'bg-white/[0.045] text-zinc-500'}`}>
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1">
        <b className="block text-pretty text-sm leading-5 text-zinc-200">{item.title || 'Новое событие'}</b>
        {item.description ? <small className="mt-1 block text-pretty text-[11px] leading-4 text-zinc-600">{item.description}</small> : null}
        <small className="mt-1 block truncate text-[10px] text-zinc-700">
          {[item.business_name, item.source, timeLabel(item.occurred_at)].filter(Boolean).join(' · ')}
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
}: TodayMobileV2Props) => {
  if (loading && !data) return <TodaySkeleton slow={slowLoading} />;

  const focus = data?.focus_action;
  const activeWork = data?.active_work || [];
  const changes = data?.changes_24h || [];
  const pulse = data?.community_pulse || [];
  const results = data?.completed_results || [];
  const profileReminders = data?.profile_reminders || [];
  const progress = data?.progress_summary;
  const isPlatform = data?.scope?.kind === 'platform';
  const isNetwork = data?.scope?.kind === 'network';

  return (
    <div className="px-4">
      <motion.section
        initial={{ opacity: 0, y: 10, filter: 'blur(4px)' }}
        animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
        transition={spring}
        className="rounded-[28px] bg-gradient-to-b from-zinc-900 to-zinc-900/70 p-5 shadow-[0_24px_80px_rgba(0,0,0,0.28),0_0_0_1px_rgba(255,255,255,0.08)]"
      >
        <div className="flex items-center gap-2 text-xs font-medium text-primary">
          <Sparkles className="h-4 w-4" />
          {focus ? 'Что сделать сейчас' : 'Новых задач нет'}
        </div>
        <div className="mt-4 flex items-start gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="text-balance text-[26px] font-semibold leading-8 tracking-[-0.045em]">
              {focus?.title || 'Сегодня от вас ничего не требуется'}
            </h1>
            <p className="mt-2 text-pretty text-sm leading-6 text-zinc-400">
              {focus?.reason || (isNetwork ? 'По точкам сети нет задач, которые сейчас требуют вашего решения.' : 'По последним загруженным данным новых задач для вас нет.')}
            </p>
          </div>
          {focus?.count ? <b className="rounded-2xl bg-primary/15 px-3 py-2 text-xl tabular-nums text-primary">{focus.count}</b> : <Check className="h-8 w-8 shrink-0 text-emerald-400" />}
        </div>
        {focus?.expected_outcome ? (
          <div className="mt-4 rounded-[16px] bg-black/20 px-3 py-2.5 text-pretty text-xs leading-5 text-zinc-400">
            <b className="text-zinc-200">После этого:</b> {focus.expected_outcome}
          </div>
        ) : null}
        <button
          type="button"
          onClick={() => {
            track('today_focus_open', focus?.screen || 'progress');
            trackProduct?.('mission_open', data?.growth_loop?.mission_id || focus?.id || focus?.screen);
            if (focus) openTarget(focus.screen, focus.target_scope);
            else openProgress();
          }}
          className="mt-5 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary pl-4 pr-3.5 text-sm font-semibold text-white shadow-[0_12px_32px_rgba(255,92,51,0.24)] transition-[filter,transform] active:scale-[0.96]"
        >
          {focus?.cta_label || (isPlatform ? 'Открыть очередь платформы' : 'Открыть план роста')}
          <ChevronRight className="h-4 w-4" />
        </button>
      </motion.section>

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

      {activeWork.length ? (
        <motion.section layout className="mt-4 rounded-[22px] bg-sky-400/[0.055] p-4 shadow-[0_0_0_1px_rgba(56,189,248,0.12)]">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-sky-300" />
            <h2 className="text-sm font-semibold">ЛокалОС сейчас</h2>
            <span className="ml-auto h-2 w-2 rounded-full bg-sky-300 motion-safe:animate-pulse" />
          </div>
          <div className="mt-3 space-y-3">
            {activeWork.slice(0, 2).map((item) => (
              <button key={item.id} type="button" onClick={() => openTarget(item.screen, item.business_id ? { kind: 'business', id: item.business_id } : undefined)} className="block min-h-11 w-full text-left transition-transform active:scale-[0.96]">
                <div className="flex items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <b className="block truncate text-xs text-zinc-200">{item.title}</b>
                    <small className="mt-1 block truncate text-[11px] text-zinc-600">{[item.business_name, item.stage].filter(Boolean).join(' · ')}</small>
                  </div>
                  {item.progress !== null && item.progress !== undefined ? <b className="text-xs tabular-nums text-sky-300">{item.progress}%</b> : <Clock3 className="h-4 w-4 text-sky-300" />}
                </div>
                {item.progress !== null && item.progress !== undefined ? <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/[0.06]"><motion.div className="h-full rounded-full bg-sky-300" animate={{ width: `${item.progress}%` }} transition={spring} /></div> : null}
              </button>
            ))}
          </div>
        </motion.section>
      ) : null}

      <GrowthLoopPanel growthLoop={data?.growth_loop} dataHealth={data?.data_health} analyticsLevel={data?.analytics_level} rhythm={data?.rhythm} scopeKind={data?.scope?.kind} analyticsModules={data?.analytics_modules} networkSummary={data?.network_summary} problemLocations={data?.problem_locations} locationBreakdown={data?.location_breakdown} showImportAction={!['finance', 'finance_import'].includes(focus?.screen || '')} onOpenImport={() => { trackProduct?.('statistics_flow_opened', 'finance_import'); openFinanceImport?.(); }} onOpenLocation={(businessId, screen) => { trackProduct?.('statistics_flow_opened', businessId); openTarget(screen, { kind: 'business', id: businessId }); }} />

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
        {changes.length ? changes.slice(0, 3).map((item) => <ActivityRow key={item.id} item={item} icon={Clock3} onClick={() => openTarget(item.screen, item.business_id ? { kind: 'business', id: item.business_id } : undefined)} />) : (
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
                <small className="mt-2 block truncate text-[10px] text-zinc-700">{[item.source_name, item.message_count ? ruCountLabel(item.message_count, 'сообщение', 'сообщения', 'сообщений') : '', timeLabel(item.last_discussed_at)].filter(Boolean).join(' · ')}</small>
              </span>
              <ArrowUpRight className="h-4 w-4 shrink-0 text-zinc-700" />
            </a>
          )) : <button type="button" onClick={openSources} className="flex min-h-16 w-full items-center gap-3 py-3 text-left text-sm text-zinc-600"><Radio className="h-5 w-5 text-primary" /><span>За последние сутки заметных обсуждений не было. Можно добавить каналы, за которыми вы хотите следить.</span><ChevronRight className="ml-auto h-4 w-4" /></button>}
        </Section>
      ) : null}

      <Section title="Готово в ЛокалОС" subtitle="Черновики, планы и отчёты, которые уже можно открыть и проверить.">
        {results.length ? (
          <AnimatePresence initial={false}>
            {results.slice(0, 3).map((item) => (
              <motion.div key={item.id} initial={{ opacity: 0, y: 8, filter: 'blur(4px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }} exit={{ opacity: 0, y: -5 }} transition={spring}>
                <ActivityRow item={item} icon={Check} accent onClick={() => openTarget(item.screen, item.business_id ? { kind: 'business', id: item.business_id } : undefined)} />
              </motion.div>
            ))}
          </AnimatePresence>
        ) : <div className="py-4 text-pretty text-sm leading-6 text-zinc-600">Готовых материалов пока нет.</div>}
      </Section>

      {progress ? (
        <section className="mt-7 rounded-[24px] bg-gradient-to-br from-primary/[0.1] to-white/[0.035] p-5 shadow-[0_18px_60px_rgba(0,0,0,0.24),0_0_0_1px_rgba(255,92,51,0.14)]">
          <div className="flex items-end justify-between gap-3">
            <div>
              <small className="text-zinc-600">План роста</small>
              <b className="mt-1 block text-lg">Что уже сделано</b>
            </div>
            <b className="text-2xl tabular-nums text-primary">{progress.percent || 0}%</b>
          </div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-black/20"><motion.div className="h-full rounded-full bg-primary" initial={false} animate={{ width: `${progress.percent || 0}%` }} transition={spring} /></div>
          <p className="mt-3 text-pretty text-xs leading-5 text-zinc-500">Выполнено <span className="tabular-nums">{progress.completed_milestones || 0}</span> из <span className="tabular-nums">{progress.total_milestones || 0}</span> шагов.</p>
          <button type="button" onClick={() => { track('today_progress_open', 'progress'); openProgress(); }} className="mt-4 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-white/[0.07] pl-4 pr-3.5 text-sm font-semibold shadow-[0_0_0_1px_rgba(255,255,255,0.08)] transition-transform active:scale-[0.96]">Открыть план роста<ChevronRight className="h-4 w-4" /></button>
        </section>
      ) : isPlatform ? (
        <section className="mt-7 rounded-[24px] bg-gradient-to-br from-primary/[0.1] to-white/[0.035] p-5 shadow-[0_18px_60px_rgba(0,0,0,0.24),0_0_0_1px_rgba(255,92,51,0.14)]">
          <small className="text-zinc-600">Операционная картина платформы</small>
          <b className="mt-1 block text-balance text-lg">Все очереди и инциденты в одном месте</b>
          <p className="mt-2 text-pretty text-xs leading-5 text-zinc-500">В очереди собраны инциденты и задачи платформы в порядке приоритета.</p>
          <button type="button" onClick={() => { track('today_progress_open', 'platform_inbox'); openTarget('tasks'); }} className="mt-4 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-white/[0.07] pl-4 pr-3.5 text-sm font-semibold shadow-[0_0_0_1px_rgba(255,255,255,0.08)] transition-transform active:scale-[0.96]">Открыть очередь платформы<ChevronRight className="h-4 w-4" /></button>
        </section>
      ) : null}
    </div>
  );
};
