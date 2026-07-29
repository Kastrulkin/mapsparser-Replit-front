import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Bot,
  Check,
  ChevronRight,
  Circle,
  FileText,
  Handshake,
  MapPinned,
  PackageCheck,
  Sparkles,
} from 'lucide-react';

import type { TodayFocusAction } from '@/components/telegram/TodayMobileV2';

type ProgressMilestone = {
  key?: string;
  label?: string;
  status?: 'done' | 'next';
  achieved_at?: string;
  evidence?: string;
};

type ProgressArea = {
  key?: string;
  label?: string;
  status?: string;
  summary?: string;
  problem?: string;
  expected_outcome?: string;
  progress?: { completed?: number; total?: number };
  milestones?: ProgressMilestone[];
  action?: TodayFocusAction & { cta_url?: string };
};

export type ProgressPayload = {
  status?: string;
  focus_action?: TodayFocusAction | null;
  summary?: {
    completed_milestones?: number;
    total_milestones?: number;
    active_areas?: number;
    needs_attention?: number;
    completed_last_30_days?: number;
    percent?: number;
  } | null;
  areas?: ProgressArea[];
  recent_results?: Array<{ key?: string; title?: string; description?: string; occurred_at?: string }>;
  data_warnings?: string[];
};

type ProgressMobileModuleProps = {
  data?: ProgressPayload | null;
  loading: boolean;
  openTarget: (screen?: string) => void;
  track: (eventName: string, target?: string) => void;
};

const spring = { type: 'spring', duration: 0.3, bounce: 0 };
const icons: Record<string, typeof MapPinned> = {
  maps: MapPinned,
  content: FileText,
  partnerships: Handshake,
  automation: Bot,
  upsells: PackageCheck,
};

const statusLabel = (value?: string) => {
  if (value === 'healthy') return 'Работает';
  if (value === 'needs_attention') return 'Нужно внимание';
  if (value === 'in_progress') return 'В процессе';
  if (value === 'not_started') return 'Не начато';
  return 'Нет данных';
};

const statusClass = (value?: string) => {
  if (value === 'healthy') return 'bg-emerald-400/10 text-emerald-300';
  if (value === 'needs_attention') return 'bg-amber-400/10 text-amber-300';
  if (value === 'in_progress') return 'bg-sky-400/10 text-sky-300';
  return 'bg-white/[0.05] text-zinc-500';
};

export const ProgressMobileModule = ({ data, loading, openTarget, track }: ProgressMobileModuleProps) => {
  const [expanded, setExpanded] = useState('');
  if (loading && !data) {
    return <div className="space-y-3" aria-busy="true"><div className="h-52 animate-pulse rounded-[24px] bg-white/[0.045] motion-reduce:animate-none" /><div className="h-24 animate-pulse rounded-[22px] bg-white/[0.035] motion-reduce:animate-none" /><div className="h-24 animate-pulse rounded-[22px] bg-white/[0.035] motion-reduce:animate-none" /></div>;
  }
  if (!data?.summary) {
    return <div className="rounded-[22px] bg-white/[0.035] p-6 text-center shadow-[0_0_0_1px_rgba(255,255,255,0.07)]"><Circle className="mx-auto h-6 w-6 text-zinc-700" /><b className="mt-3 block text-sm">Прогресс пока не собран</b><p className="mt-1 text-pretty text-xs leading-5 text-zinc-600">Выберите бизнес или сеть, чтобы ЛокалОС собрал подтверждённый путь роста.</p></div>;
  }

  const summary = data.summary;
  const focus = data.focus_action;
  return (
    <div>
      <section className="rounded-[24px] bg-gradient-to-b from-primary/[0.11] to-white/[0.035] p-5 shadow-[0_18px_60px_rgba(0,0,0,0.24),0_0_0_1px_rgba(255,92,51,0.15)]">
        <div className="flex items-center gap-2 text-xs font-medium text-primary"><Sparkles className="h-4 w-4" />Понятный план роста</div>
        <h2 className="mt-3 text-balance text-xl font-semibold">Десятки задач собраны в один путь</h2>
        <p className="mt-2 text-pretty text-xs leading-5 text-zinc-500">Карты, контент, партнёрства, автоматизация и допродажи — с подтверждёнными результатами и одним следующим шагом.</p>
        <div className="mt-5 flex items-end justify-between gap-4">
          <div><b className="text-3xl tabular-nums">{summary.completed_milestones || 0}</b><span className="text-lg tabular-nums text-zinc-600"> / {summary.total_milestones || 0}</span><small className="mt-1 block text-zinc-600">шагов подтверждено</small></div>
          <b className="text-2xl tabular-nums text-primary">{summary.percent || 0}%</b>
        </div>
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-black/20"><motion.div initial={false} animate={{ width: `${summary.percent || 0}%` }} transition={spring} className="h-full rounded-full bg-primary" /></div>
        <div className="mt-4 grid grid-cols-3 gap-2 text-center"><div><b className="block tabular-nums">{summary.active_areas || 0}</b><small className="text-[9px] text-zinc-600">направлений</small></div><div><b className="block tabular-nums">{summary.needs_attention || 0}</b><small className="text-[9px] text-zinc-600">ждут решения</small></div><div><b className="block tabular-nums">{summary.completed_last_30_days || 0}</b><small className="text-[9px] text-zinc-600">за 30 дней</small></div></div>
      </section>

      {focus ? (
        <section className="mt-3 rounded-[22px] bg-white/[0.04] p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.075)]">
          <small className="font-semibold uppercase tracking-[0.12em] text-primary">Сейчас важнее всего</small>
          <h3 className="mt-2 text-balance text-lg font-semibold">{focus.title}</h3>
          <p className="mt-2 text-pretty text-xs leading-5 text-zinc-500">{focus.reason}</p>
          {focus.expected_outcome ? <div className="mt-3 rounded-[15px] bg-black/20 px-3 py-2.5 text-pretty text-xs leading-5 text-zinc-400"><b className="text-zinc-200">Результат:</b> {focus.expected_outcome}</div> : null}
          <button type="button" onClick={() => { track('progress_action_open', focus.screen); openTarget(focus.screen); }} className="mt-4 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary pl-4 pr-3.5 text-sm font-semibold shadow-[0_12px_32px_rgba(255,92,51,0.22)] transition-transform active:scale-[0.96]">{focus.cta_label || 'Продолжить'}<ChevronRight className="h-4 w-4" /></button>
        </section>
      ) : null}

      <section className="mt-7">
        <h2 className="text-balance text-lg font-semibold tracking-[-0.025em]">Направления роста</h2>
        <p className="mt-1 text-pretty text-xs leading-5 text-zinc-600">Откройте направление, чтобы увидеть сделанное, препятствие и следующий шаг.</p>
        <div className="mt-3 space-y-2">
          {(data.areas || []).map((area) => {
            const key = area.key || 'area';
            const Icon = icons[key] || Circle;
            const isOpen = expanded === key;
            const completed = area.progress?.completed || 0;
            const total = area.progress?.total || 0;
            const percent = total > 0 ? Math.round(completed / total * 100) : 0;
            return (
              <article key={key} className="overflow-hidden rounded-[22px] bg-white/[0.035] shadow-[0_0_0_1px_rgba(255,255,255,0.07)]">
                <button type="button" aria-expanded={isOpen} onClick={() => setExpanded(isOpen ? '' : key)} className="flex min-h-20 w-full items-center gap-3 p-4 text-left transition-[background-color,transform] active:scale-[0.96]">
                  <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-primary/12 text-primary"><Icon className="h-5 w-5" /></span>
                  <span className="min-w-0 flex-1"><span className="flex items-center gap-2"><b className="truncate text-sm">{area.label || 'Направление'}</b><small className={`shrink-0 rounded-full px-2 py-1 text-[9px] ${statusClass(area.status)}`}>{statusLabel(area.status)}</small></span><small className="mt-1 block truncate text-zinc-600">{area.summary || area.problem}</small><span className="mt-2 flex items-center gap-2"><span className="h-1 min-w-0 flex-1 overflow-hidden rounded-full bg-white/[0.06]"><span className="block h-full rounded-full bg-primary" style={{ width: `${percent}%` }} /></span><small className="tabular-nums text-zinc-700">{completed}/{total}</small></span></span>
                  <ChevronRight className={`h-4 w-4 shrink-0 text-zinc-700 transition-transform ${isOpen ? 'rotate-90' : ''}`} />
                </button>
                <AnimatePresence initial={false}>
                  {isOpen ? (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={spring} className="overflow-hidden">
                      <div className="border-t border-white/[0.055] p-4">
                        {area.problem ? <div className="text-pretty text-xs leading-5 text-amber-200/75"><b>Мешает двигаться:</b> {area.problem}</div> : <div className="text-pretty text-xs leading-5 text-emerald-200/75">Направление работает без критичных препятствий.</div>}
                        <div className="mt-4 space-y-3">
                          {(area.milestones || []).map((milestone) => (
                            <div key={milestone.key} className="flex gap-3"><span className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-lg ${milestone.status === 'done' ? 'bg-emerald-400/10 text-emerald-300' : 'bg-white/[0.05] text-zinc-600'}`}>{milestone.status === 'done' ? <Check className="h-3.5 w-3.5" /> : <Circle className="h-3.5 w-3.5" />}</span><span className="min-w-0"><b className="block text-xs text-zinc-300">{milestone.label}</b>{milestone.evidence ? <small className="mt-1 block text-pretty leading-4 text-zinc-600">{milestone.evidence}</small> : null}</span></div>
                          ))}
                        </div>
                        {area.action ? <button type="button" onClick={() => openTarget(area.action?.screen)} className="mt-4 min-h-11 w-full rounded-[14px] bg-white/[0.055] px-3 text-xs font-semibold shadow-[0_0_0_1px_rgba(255,255,255,0.075)] transition-transform active:scale-[0.96]">{area.action.cta_label || 'Открыть следующий шаг'}</button> : null}
                      </div>
                    </motion.div>
                  ) : null}
                </AnimatePresence>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
};
