import { spring } from './motion';
import { useMobileJobPolling } from '@/components/telegram/useMobileJobPolling';
import ActionPreviewSheet,{ type MobileActionPreview } from '@/components/telegram/ActionPreviewSheet';
import JobProgressSheet from '@/components/telegram/JobProgressSheet';
import { type MobileScope } from '@/components/telegram/ScopeProvider.logic';
import { useLatestCallback } from '@/hooks/useLatestCallback';
import { cancelMobileJob,confirmMobileAction,loadMobileJob,mobileAuthHeaders,mobileJsonHeaders,mobileScopeQuery,readMobileJson,retryMobileJob,type MobileJob } from '@/lib/mobileDataClient';
import { AnimatePresence,motion } from 'framer-motion';
import {
Building2,CalendarDays,
Check,ChevronLeft,ChevronRight,CircleEllipsis,
Loader2,
Pencil,
Sparkles,
Trash2,
WandSparkles
} from 'lucide-react';
import { lazy,useEffect,useMemo,useRef,useState } from 'react';
import { Empty,InlineError } from './shared';
import type { ModuleData,ModuleItem } from './types';
const readJson = readMobileJson;
const scopeQuery = mobileScopeQuery;
const authHeaders = mobileJsonHeaders;
const authOnlyHeaders = mobileAuthHeaders;

const contentDateKey = (value?: string) => {
  const raw = String(value || '').trim();
  const match = raw.match(/^(\d{4}-\d{2}-\d{2})/);
  if (match?.[1]) {
    const [year, month, day] = match[1].split('-').map(Number);
    const parsed = new Date(Date.UTC(year, month - 1, day));
    if (parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month - 1 && parsed.getUTCDate() === day) return match[1];
    return '';
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return '';
  return [parsed.getUTCFullYear(), String(parsed.getUTCMonth() + 1).padStart(2, '0'), String(parsed.getUTCDate()).padStart(2, '0')].join('-');
};

const contentDateLabel = (value?: string, withWeekday = false) => {
  const key = contentDateKey(value);
  if (!key) return 'Без даты';
  return new Date(`${key}T12:00:00`).toLocaleDateString('ru-RU', withWeekday ? { weekday: 'long', day: 'numeric', month: 'long' } : { day: 'numeric', month: 'long' });
};

export const ContentModule = ({ focusItemId, scope, items, filters, busy, generate, update, reload }: { focusItemId?: string; scope?: MobileScope; items: ModuleItem[]; filters?: ModuleData['filters']; busy: string; generate: (item: ModuleItem) => Promise<void>; update: (item: ModuleItem, values: { theme: string; draft_text: string; scheduled_for: string }) => Promise<void>; reload: () => Promise<void> }) => {
  const [editing, setEditing] = useState('');
  const [contentSection, setContentSection] = useState('calendar');
  const [generating, setGenerating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [planAction, setPlanAction] = useState('');
  const [error, setError] = useState('');
  const [deletePreview, setDeletePreview] = useState<MobileActionPreview | null>(null);
  const [generatePreview, setGeneratePreview] = useState<MobileActionPreview | null>(null);
  const [draftPreview, setDraftPreview] = useState<MobileActionPreview | null>(null);
  const [draftItem, setDraftItem] = useState<ModuleItem | null>(null);
  const [activeJob, setActiveJob] = useState<MobileJob | null>(null);
  const [jobBusy, setJobBusy] = useState(false);
  const allowedPeriods = (filters?.period_days || [14, 30]).filter((value) => Number.isFinite(value) && value > 0);
  const [periodDays, setPeriodDays] = useState(() => allowedPeriods.includes(30) ? 30 : allowedPeriods[0] || 30);
  const [density, setDensity] = useState('standard');
  const calendarRef = useRef<HTMLDivElement | null>(null);
  const postsRef = useRef<HTMLDivElement | null>(null);
  const planTitle = items.find((item) => item.plan_title)?.plan_title;
  const planId = items.find((item) => item.plan_id)?.plan_id;
  const reloadEffect = useLatestCallback(reload);
  useEffect(() => {
    if (!focusItemId || !items.some((item) => item.id === focusItemId)) return;
    setContentSection('posts');
    setEditing(focusItemId);
    window.requestAnimationFrame(() => document.getElementById(`content-item-${focusItemId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
  }, [focusItemId, items]);
  const scrollTo = (section: 'calendar' | 'posts') => {
    setContentSection(section);
    const target = section === 'calendar' ? calendarRef.current : postsRef.current;
    window.requestAnimationFrame(() => target?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  };
  const scrollToDate = (date: string) => {
    setContentSection('posts');
    window.requestAnimationFrame(() => document.getElementById(`content-day-${date}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  };
  const prepareGeneratePlan = async () => {
    setGenerating(true); setError('');
    try {
      const result = await fetch('/api/operator/mobile/actions/preview', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, capability: 'content.plan.generate', input: { business_id: scope?.kind === 'business' ? scope.id : null, period_days: periodDays, density } }) }).then(readJson<{ preview?: MobileActionPreview }>);
      setGeneratePreview(result.preview || null);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось подготовить план.'); }
    finally { setGenerating(false); }
  };
  const confirmGeneratePlan = async () => {
    if (!generatePreview?.action_id) return;
    setGenerating(true); setError('');
    try {
      const result = await confirmMobileAction(generatePreview.action_id, scope);
      const job = result.operator_result?.job;
      const jobId = String(result.operator_result?.job_id || job?.id || '');
      setGeneratePreview(null);
      if (job) setActiveJob(job);
      else if (jobId) {
        const loaded = await loadMobileJob(jobId, scope);
        setActiveJob(loaded.job || null);
      }
      setPlanAction('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось запустить сборку плана.'); }
    finally { setGenerating(false); }
  };
  const prepareDraft = async (item: ModuleItem) => {
    if (!item.id) return;
    if (item.id.startsWith('content-')) { await generate(item); return; }
    setDraftItem(item); setError('');
    try {
      const result = await fetch('/api/operator/mobile/actions/preview', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, capability: 'content.item.generate', input: { item_id: item.id } }) }).then(readJson<{ preview?: MobileActionPreview }>);
      setDraftPreview(result.preview || null);
    } catch (requestError) { setDraftItem(null); setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить генерацию текста.'); }
  };
  const confirmDraft = async () => {
    if (!draftPreview?.action_id || !draftItem?.id) return;
    setJobBusy(true); setError('');
    try {
      const result = await confirmMobileAction(draftPreview.action_id, scope);
      const job = result.operator_result?.job;
      const jobId = String(result.operator_result?.job_id || job?.id || '');
      setDraftPreview(null);
      if (job) setActiveJob(job);
      else if (jobId) {
        const loaded = await loadMobileJob(jobId, scope);
        setActiveJob(loaded.job || null);
      }
      setContentSection('posts');
      setEditing(draftItem.id);
      setDraftItem(null);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось запустить подготовку текста.'); }
    finally { setJobBusy(false); }
  };
  useMobileJobPolling({ job: activeJob, scope, onJob: setActiveJob, onComplete: (completedJob) => { if (completedJob.status === 'completed') void reloadEffect(); }, intervalMs: 2000 });
  const retryJob = async () => {
    if (!activeJob?.id) return;
    setJobBusy(true);
    try { const result = await retryMobileJob(activeJob.id, scope); setActiveJob(result.job || null); setError(''); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось повторить задачу.'); }
    finally { setJobBusy(false); }
  };
  const cancelJob = async () => {
    if (!activeJob?.id) return;
    setJobBusy(true);
    try { const result = await cancelMobileJob(activeJob.id, scope); setActiveJob(result.job || null); setError(''); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось остановить задачу.'); }
    finally { setJobBusy(false); }
  };
  const prepareDeletePlan = async () => { if (!planId) return; setDeleting(true); try { const result = await fetch('/api/operator/mobile/actions/preview', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, capability: 'content.plan.delete', input: { plan_id: planId, business_id: scope?.kind === 'business' ? scope.id : null } }) }).then(readJson<{ preview?: MobileActionPreview }>); setDeletePreview(result.preview || null); setPlanAction(''); setError(''); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить удаление плана.'); } finally { setDeleting(false); } };
  const confirmDeletePlan = async () => { if (!deletePreview?.action_id) return; setDeleting(true); try { await fetch(`/api/operator/mobile/actions/${deletePreview.action_id}/confirm`, { method: 'POST', headers: authHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null }) }).then(readJson); setDeletePreview(null); await reload(); setPlanAction(''); setError(''); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось удалить план.'); } finally { setDeleting(false); } };
  return <>{planId ? <PlanDownload key={`${scope?.kind}:${scope?.id}:${planId}`} planId={planId} mobile dirty={Boolean(editing)} /> : null}<AnimatePresence initial={false} mode="wait">
    <motion.div key="content" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={spring}>
      {planTitle ? <section className="mb-3 rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><small className="text-zinc-600">Текущий контент-план</small><b className="mt-1 block text-balance text-base">{planTitle}</b><p className="mt-2 text-pretty text-xs text-zinc-500"><span className="tabular-nums">{items.length}</span> публикаций{items[0]?.plan_period_days ? <> · <span className="tabular-nums">{items[0].plan_period_days}</span> дней</> : null}</p></div><button type="button" aria-label="Дополнительные действия с планом" aria-expanded={planAction === 'menu'} onClick={() => setPlanAction(planAction === 'menu' ? '' : 'menu')} className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-white/[0.05] text-zinc-400 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96]"><CircleEllipsis className="h-5 w-5" /></button></div><div className="mt-4 grid grid-cols-[minmax(0,1fr)_auto] gap-2"><button type="button" onClick={() => { setEditing(''); scrollTo('posts'); }} className="flex min-h-11 items-center justify-center gap-2 rounded-[14px] bg-primary px-3 text-xs font-semibold text-white shadow-[0_10px_24px_rgba(255,92,51,0.2)] transition-transform active:scale-[0.96]"><Pencil className="h-4 w-4" />Редактировать публикации</button><button type="button" onClick={() => setPlanAction('new')} className="min-h-11 rounded-[14px] bg-white/[0.05] px-4 text-xs font-semibold text-zinc-300 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96]">Новый план</button></div>{planAction === 'menu' ? <div className="mt-3"><button type="button" disabled={deleting} onClick={() => void prepareDeletePlan()} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-[14px] bg-rose-500/[0.08] px-3 text-xs font-semibold text-rose-300 ring-1 ring-inset ring-rose-400/15 transition-transform active:scale-[0.96] disabled:opacity-50">{deleting ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Trash2 className="h-4 w-4" />}{deleting ? 'Проверяем…' : 'Удалить текущий план'}</button></div> : null}</section> : null}
      {error ? <InlineError text={error} /> : null}
      {(!items.length || planAction === 'new') && scope?.kind === 'business' ? <ContentPlanSetup periods={allowedPeriods} periodDays={periodDays} setPeriodDays={setPeriodDays} density={density} setDensity={setDensity} existingPlan={Boolean(items.length)} cancel={items.length ? () => setPlanAction('') : undefined} generate={() => void prepareGeneratePlan()} /> : null}
      {scope?.kind !== 'business' && !items.length ? <Empty icon={Building2} title="Выберите одну точку" text="Сеть можно анализировать целиком, но календарь создаётся для конкретного бизнеса." /> : null}
      {items.length && planAction !== 'new' ? <><div role="navigation" aria-label="Разделы контент-плана" className="sticky top-2 z-10 mb-3 grid grid-cols-2 rounded-[20px] bg-zinc-900/90 p-1 shadow-[0_12px_38px_rgba(0,0,0,0.34)] ring-1 ring-inset ring-white/[0.08] backdrop-blur-xl"><button type="button" aria-current={contentSection === 'calendar' ? 'page' : undefined} onClick={() => scrollTo('calendar')} className={`min-h-11 rounded-[16px] text-sm font-semibold transition-[background-color,color,transform,box-shadow] active:scale-[0.96] ${contentSection === 'calendar' ? 'bg-white/[0.1] text-white shadow-[0_4px_14px_rgba(0,0,0,0.24)]' : 'text-zinc-500'}`}>Календарь</button><button type="button" aria-current={contentSection === 'posts' ? 'page' : undefined} onClick={() => scrollTo('posts')} className={`min-h-11 rounded-[16px] text-sm font-semibold transition-[background-color,color,transform,box-shadow] active:scale-[0.96] ${contentSection === 'posts' ? 'bg-white/[0.1] text-white shadow-[0_4px_14px_rgba(0,0,0,0.24)]' : 'text-zinc-500'}`}>Посты <span className="ml-1 tabular-nums text-[11px] opacity-60">{items.length}</span></button></div><div ref={calendarRef} className="scroll-mt-20"><ContentCalendar items={items} openDate={scrollToDate} /></div><ContentPostList postsRef={postsRef} items={items} editing={editing} busy={busy} setEditing={setEditing} generate={prepareDraft} update={update} /></> : null}
    </motion.div>
  </AnimatePresence><ActionPreviewSheet preview={deletePreview} busy={deleting} confirmLabel="Удалить план" onCancel={() => setDeletePreview(null)} onConfirm={() => void confirmDeletePlan()} /><ActionPreviewSheet preview={generatePreview} busy={generating} confirmLabel="Собрать план" onCancel={() => setGeneratePreview(null)} onConfirm={() => void confirmGeneratePlan()} /><ActionPreviewSheet preview={draftPreview} busy={jobBusy} confirmLabel="Создать текст" onCancel={() => { setDraftPreview(null); setDraftItem(null); }} onConfirm={() => void confirmDraft()} /><JobProgressSheet job={activeJob} busy={jobBusy} onClose={() => { setActiveJob(null); if (activeJob?.status === 'completed') void reload(); }} onRetry={() => void retryJob()} onCancel={() => void cancelJob()} /></>;
};

const ContentPlanSetup = ({ periods, periodDays, setPeriodDays, density, setDensity, existingPlan, cancel, generate }: { periods: number[]; periodDays: number; setPeriodDays: (value: number) => void; density: string; setDensity: (value: string) => void; existingPlan: boolean; cancel?: () => void; generate: () => void }) => {
  const weekly = density === 'light' ? 1 : density === 'active' ? 3 : 2;
  const estimate = Math.max(4, Math.round(periodDays / 7 * weekly));
  return <section className="mb-4 rounded-[26px] bg-gradient-to-b from-primary/[0.09] to-white/[0.035] p-4 shadow-[0_18px_60px_rgba(0,0,0,0.24)] ring-1 ring-inset ring-primary/15"><div className="flex items-start gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-primary/15 text-primary"><WandSparkles className="h-5 w-5" /></span><div><h2 className="text-balance text-base font-semibold">{existingPlan ? 'Настройте новый план' : 'ЛокалОС соберёт план за вас'}</h2><p className="mt-1 text-pretty text-xs leading-5 text-zinc-500">Выберите горизонт и темп. Мы сверим услуги, спрос и карточку, затем расставим темы по календарю.</p></div></div><div className="mt-5"><p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-zinc-600">Период</p><div className="grid grid-flow-col auto-cols-fr gap-2">{periods.map((days) => <button type="button" key={days} aria-pressed={periodDays === days} onClick={() => setPeriodDays(days)} className={`min-h-12 rounded-[15px] px-3 text-sm font-semibold tabular-nums ring-1 ring-inset transition-[background-color,color,transform,box-shadow] active:scale-[0.96] ${periodDays === days ? 'bg-primary text-white shadow-[0_10px_26px_rgba(255,92,51,0.2)] ring-primary' : 'bg-black/20 text-zinc-400 ring-white/[0.07]'}`}>{days} дней</button>)}</div></div><div className="mt-4"><p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-zinc-600">Темп публикаций</p><div className="grid grid-cols-3 gap-2">{[['light', '1 в неделю'], ['standard', '2 в неделю'], ['active', '3 в неделю']].map(([key, label]) => <button type="button" key={key} aria-pressed={density === key} onClick={() => setDensity(key)} className={`min-h-12 rounded-[15px] px-2 text-[11px] font-semibold ring-1 ring-inset transition-[background-color,color,transform] active:scale-[0.96] ${density === key ? 'bg-white/[0.1] text-white ring-white/15' : 'bg-black/15 text-zinc-600 ring-white/[0.06]'}`}>{label}</button>)}</div></div><div className="mt-4 flex items-center justify-between rounded-[16px] bg-black/20 px-3 py-3 ring-1 ring-inset ring-white/[0.05]"><span className="text-xs text-zinc-500">Будет подготовлено</span><b className="text-sm tabular-nums text-zinc-200">около {estimate} публикаций</b></div><p className="mt-3 text-pretty text-[11px] leading-5 text-zinc-600">Ничего не публикуется автоматически. Сначала вы увидите календарь и сможете изменить каждую тему.</p><div className={`mt-4 grid gap-2 ${cancel ? 'grid-cols-[auto_minmax(0,1fr)]' : 'grid-cols-1'}`}>{cancel ? <button type="button" onClick={cancel} className="min-h-12 rounded-[16px] bg-white/[0.05] px-4 text-xs font-semibold text-zinc-400 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96]">Отмена</button> : null}<button type="button" onClick={generate} className="flex min-h-12 items-center justify-center gap-2 rounded-[16px] bg-primary px-4 text-sm font-semibold text-white shadow-[0_12px_32px_rgba(255,92,51,0.24)] transition-[filter,transform] active:scale-[0.96]"><WandSparkles className="h-4 w-4" />Собрать план на {periodDays} дней</button></div></section>;
};

const calendarMonthStart = (items: ModuleItem[]) => {
  const firstDate = items.map((item) => contentDateKey(item.scheduled_for)).filter(Boolean).sort()[0];
  const date = firstDate ? new Date(`${firstDate}T12:00:00`) : new Date();
  return new Date(date.getFullYear(), date.getMonth(), 1);
};

const calendarKey = (year: number, month: number, day: number) => [year, String(month + 1).padStart(2, '0'), String(day).padStart(2, '0')].join('-');

const ContentCalendar = ({ items, openDate }: { items: ModuleItem[]; openDate: (date: string) => void }) => {
  const [month, setMonth] = useState(() => calendarMonthStart(items));
  const [selectedDate, setSelectedDate] = useState(() => items.map((item) => contentDateKey(item.scheduled_for)).filter(Boolean).sort()[0] || '');
  const itemsByDate = useMemo(() => items.reduce<Record<string, ModuleItem[]>>((result, item) => {
    const key = contentDateKey(item.scheduled_for);
    if (key) result[key] = [...(result[key] || []), item];
    return result;
  }, {}), [items]);
  const year = month.getFullYear();
  const monthIndex = month.getMonth();
  const firstWeekday = (new Date(year, monthIndex, 1).getDay() + 6) % 7;
  const dayCount = new Date(year, monthIndex + 1, 0).getDate();
  const cellCount = Math.ceil((firstWeekday + dayCount) / 7) * 7;
  const todayKey = contentDateKey(new Date().toISOString());
  const moveMonth = (offset: number) => setMonth(new Date(year, monthIndex + offset, 1));
  return <section className="rounded-[26px] bg-white/[0.04] p-4 shadow-[0_18px_54px_rgba(0,0,0,0.24)] ring-1 ring-inset ring-white/[0.07]">
    <div className="flex min-h-11 items-center justify-between"><div><small className="block text-[10px] font-semibold uppercase tracking-[0.13em] text-primary">Контент-календарь</small><h2 className="mt-1 text-balance text-lg font-semibold capitalize tracking-[-0.025em]">{month.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })}</h2></div><div className="flex gap-1"><button type="button" aria-label="Предыдущий месяц" onClick={() => moveMonth(-1)} className="grid h-11 w-11 place-items-center rounded-[14px] text-zinc-400 ring-1 ring-inset ring-white/[0.07] transition-[background-color,transform] active:scale-[0.96] active:bg-white/[0.06]"><ChevronLeft className="h-5 w-5" /></button><button type="button" aria-label="Следующий месяц" onClick={() => moveMonth(1)} className="grid h-11 w-11 place-items-center rounded-[14px] text-zinc-400 ring-1 ring-inset ring-white/[0.07] transition-[background-color,transform] active:scale-[0.96] active:bg-white/[0.06]"><ChevronRight className="h-5 w-5" /></button></div></div>
    <div className="mt-5 grid grid-cols-7 text-center">{['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((day) => <span key={day} className="pb-2 text-[10px] font-semibold uppercase text-zinc-600">{day}</span>)}</div>
    <div className="grid grid-cols-7">{Array.from({ length: cellCount }, (_, index) => {
      const day = index - firstWeekday + 1;
      if (day < 1 || day > dayCount) return <span key={`empty-${index}`} className="h-12" aria-hidden="true" />;
      const key = calendarKey(year, monthIndex, day);
      const dayItems = itemsByDate[key] || [];
      const selected = selectedDate === key;
      const today = todayKey === key;
      const readyCount = dayItems.filter((item) => Boolean(item.draft_text?.trim())).length;
      return <button type="button" key={key} aria-label={`${day} ${month.toLocaleDateString('ru-RU', { month: 'long' })}${dayItems.length ? `, публикаций: ${dayItems.length}` : ', публикаций нет'}`} aria-pressed={selected} onClick={() => { setSelectedDate(key); if (dayItems.length) openDate(key); }} className="group relative grid h-12 min-w-0 place-items-center rounded-[14px] transition-[background-color,color,transform] active:scale-[0.96]"><span className={`grid h-9 w-9 place-items-center rounded-full text-sm font-medium tabular-nums transition-[background-color,color,box-shadow] ${selected ? 'bg-primary text-white shadow-[0_6px_18px_rgba(255,92,51,0.32)]' : today ? 'text-primary ring-1 ring-inset ring-primary/50' : dayItems.length ? 'text-zinc-100' : 'text-zinc-600 group-active:bg-white/[0.05]'}`}>{day}</span>{dayItems.length ? <span className="absolute bottom-0.5 flex gap-0.5" aria-hidden="true">{Array.from({ length: Math.min(dayItems.length, 3) }, (_, dot) => <span key={dot} className={`h-1 w-1 rounded-full ${readyCount > dot ? 'bg-emerald-400' : 'bg-amber-400'}`} />)}</span> : null}</button>;
    })}</div>
    <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 border-t border-white/[0.06] pt-3 text-[10px] text-zinc-500"><span className="flex items-center gap-1.5"><i className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Текст готов</span><span className="flex items-center gap-1.5"><i className="h-1.5 w-1.5 rounded-full bg-amber-400" />Нужно подготовить</span><span className="ml-auto tabular-nums">{items.length} публикаций</span></div>
  </section>;
};

const ContentPostList = ({ postsRef, items, editing, busy, setEditing, generate, update }: { postsRef: { current: HTMLDivElement | null }; items: ModuleItem[]; editing: string; busy: string; setEditing: (id: string) => void; generate: (item: ModuleItem) => Promise<void>; update: (item: ModuleItem, values: { theme: string; draft_text: string; scheduled_for: string }) => Promise<void> }) => {
  const groups = items.reduce<Record<string, ModuleItem[]>>((result, item) => {
    const key = contentDateKey(item.scheduled_for) || 'undated';
    result[key] = [...(result[key] || []), item];
    return result;
  }, {});
  const orderedGroups = Object.entries(groups).sort(([left], [right]) => left === 'undated' ? 1 : right === 'undated' ? -1 : left.localeCompare(right));
  return <div ref={postsRef} className="scroll-mt-20 pt-6"><div className="mb-3 flex items-end justify-between px-1"><div><small className="text-[10px] font-semibold uppercase tracking-[0.13em] text-primary">Публикации</small><h2 className="mt-1 text-lg font-semibold tracking-[-0.025em]">Посты по плану</h2></div><span className="text-xs tabular-nums text-zinc-500">{items.length}</span></div><div className="space-y-5">{orderedGroups.map(([date, dayItems]) => <section id={`content-day-${date}`} key={date} className="scroll-mt-20"><div className="mb-2 flex items-center gap-2 px-1"><CalendarDays className="h-4 w-4 text-primary" /><b className="text-sm capitalize text-zinc-300">{date === 'undated' ? 'Без даты' : contentDateLabel(date, true)}</b><span className="ml-auto text-[10px] tabular-nums text-zinc-600">{dayItems.length}</span></div><div className="space-y-2">{dayItems.map((item) => <ContentItemCard key={item.id} item={item} editing={editing === item.id} busy={busy === item.id} setEditing={() => setEditing(editing === item.id ? '' : item.id || '')} generate={generate} update={async (values) => { await update(item, values); setEditing(''); }} />)}</div></section>)}</div></div>;
};

const ContentDraftProgress = ({ ready }: { ready: boolean }) => {
  return <motion.div aria-live="polite" initial={{ opacity: 0, y: 8, filter: 'blur(4px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }} transition={spring} className={`rounded-[18px] p-4 ring-1 ring-inset transition-[background-color,box-shadow] ${ready ? 'bg-emerald-500/[0.08] ring-emerald-400/15' : 'bg-primary/[0.08] ring-primary/20'}`}><div className="flex items-center gap-3"><span className={`grid h-10 w-10 shrink-0 place-items-center rounded-[14px] ${ready ? 'bg-emerald-400/15 text-emerald-300' : 'bg-primary/15 text-primary'}`}><AnimatePresence initial={false} mode="popLayout">{ready ? <motion.span key="done" initial={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }} exit={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} transition={spring}><Check className="h-5 w-5" /></motion.span> : <motion.span key="work" initial={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }} exit={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }} transition={spring}><Sparkles className="h-5 w-5" /></motion.span>}</AnimatePresence></span><div className="min-w-0 flex-1"><b className="block text-balance text-sm">{ready ? 'Черновик готов' : 'ЛокалОС готовит текст'}</b><small className="mt-1 block text-pretty text-zinc-500">{ready ? 'Проверьте формулировки перед публикацией.' : 'Можно закрыть экран — результат сохранится в публикации.'}</small></div></div>{ready ? null : <div className="relative mt-3 h-1.5 overflow-hidden rounded-full bg-black/20"><motion.span className="absolute inset-y-0 w-1/3 rounded-full bg-primary" animate={{ x: ['-110%', '310%'] }} transition={{ duration: 1.1, repeat: Number.POSITIVE_INFINITY, ease: 'easeInOut' }} /></div>}</motion.div>;
};

const ContentItemCard = ({ item, editing, busy, setEditing, generate, update }: { item: ModuleItem; editing: boolean; busy: boolean; setEditing: () => void; generate: (item: ModuleItem) => Promise<void>; update: (values: { theme: string; draft_text: string; scheduled_for: string }) => Promise<void> }) => {
  const [theme, setTheme] = useState(item.title || '');
  const [draft, setDraft] = useState(item.draft_text || '');
  const [scheduled, setScheduled] = useState(contentDateKey(item.scheduled_for));
  const hasDraft = Boolean(item.draft_text?.trim());
  useEffect(() => { setTheme(item.title || ''); setDraft(item.draft_text || ''); setScheduled(contentDateKey(item.scheduled_for)); }, [item.title, item.draft_text, item.scheduled_for]);
  return <article id={`content-item-${item.id || ''}`} className={`scroll-mt-24 rounded-[22px] p-4 ring-1 ring-inset ${hasDraft ? 'bg-emerald-500/[0.025] ring-emerald-400/10' : 'bg-white/[0.04] ring-white/[0.07]'}`}><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><small className="text-[10px] font-semibold uppercase tracking-[0.12em] text-primary">{contentDateLabel(item.scheduled_for)} · {item.content_type || 'публикация'}</small><b className="mt-1 block text-sm leading-5">{item.title}</b><small className="mt-1 block truncate text-zinc-600">{item.business_name}</small></div><span className={`flex min-h-8 shrink-0 items-center gap-1.5 rounded-full px-2.5 text-[10px] font-semibold ring-1 ring-inset ${hasDraft ? 'bg-emerald-400/10 text-emerald-300 ring-emerald-400/15' : 'bg-amber-400/[0.08] text-amber-300 ring-amber-400/15'}`}>{hasDraft ? <Check className="h-3.5 w-3.5" /> : <WandSparkles className="h-3.5 w-3.5" />}{hasDraft ? 'Текст готов' : 'Нужен текст'}</span></div>{editing ? <div className="mt-4 space-y-2"><input value={theme} onChange={(event) => setTheme(event.target.value)} aria-label="Тема публикации" className="min-h-11 w-full rounded-[14px] bg-black/20 px-3 text-sm outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" /><input type="date" value={scheduled} onChange={(event) => setScheduled(event.target.value)} aria-label="Дата публикации" className="min-h-11 w-full rounded-[14px] bg-black/20 px-3 text-sm text-zinc-300 outline-none ring-1 ring-inset ring-white/[0.07]" /><textarea value={draft} onChange={(event) => setDraft(event.target.value)} aria-label="Текст публикации" rows={6} className="w-full rounded-[14px] bg-black/20 p-3 text-sm leading-6 outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" />{busy ? <ContentDraftProgress ready={Boolean(draft.trim())} /> : draft.trim() ? null : <button type="button" onClick={() => void generate(item)} className="flex min-h-12 w-full items-center justify-center gap-2 rounded-[14px] bg-primary/15 px-3 text-sm font-semibold text-primary ring-1 ring-inset ring-primary/20 transition-transform active:scale-[0.96]"><WandSparkles className="h-4 w-4" />Создать текст</button>}<button type="button" disabled={busy} onClick={() => void update({ theme, draft_text: draft, scheduled_for: scheduled })} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-[14px] bg-primary text-xs font-semibold transition-transform active:scale-[0.96] disabled:opacity-50">{busy ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Check className="h-4 w-4" />}Сохранить</button></div> : <>{hasDraft ? <div className="mt-4"><small className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-300/80"><Check className="h-3.5 w-3.5" />Черновик ЛокалОС</small><p className="mt-2 line-clamp-6 whitespace-pre-wrap text-pretty text-sm leading-6 text-zinc-300">{item.draft_text}</p></div> : <div className="mt-4 rounded-[16px] bg-amber-400/[0.045] p-3 ring-1 ring-inset ring-amber-400/10"><small className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-300/80"><WandSparkles className="h-3.5 w-3.5" />Задача из контент-плана</small><p className="mt-2 line-clamp-5 whitespace-pre-wrap text-pretty text-sm leading-6 text-zinc-500">{item.subtitle || 'Есть тема, но текст ещё не создан.'}</p></div>}{hasDraft ? <button type="button" disabled={busy} onClick={setEditing} className="mt-4 flex min-h-11 w-full items-center justify-center gap-2 rounded-[14px] bg-white/[0.055] text-xs font-semibold text-zinc-200 ring-1 ring-inset ring-white/[0.08] transition-transform active:scale-[0.96] disabled:opacity-50"><Pencil className="h-4 w-4" />Редактировать текст</button> : <div className="mt-4 grid grid-cols-[auto_minmax(0,1fr)] gap-2"><button type="button" disabled={busy} onClick={setEditing} className="flex min-h-12 items-center justify-center gap-2 rounded-[14px] bg-white/[0.05] px-4 text-xs font-semibold text-zinc-400 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96] disabled:opacity-50"><Pencil className="h-4 w-4" />Тема</button><button type="button" disabled={busy} onClick={() => { setEditing(); void generate(item); }} className="flex min-h-12 items-center justify-center gap-2 rounded-[14px] bg-primary px-3 text-sm font-semibold text-white shadow-[0_10px_28px_rgba(255,92,51,0.2)] transition-transform active:scale-[0.96] disabled:opacity-50"><WandSparkles className="h-4 w-4" />Создать текст</button></div>}</>}</article>;
};

const PlanDownload = lazy(() => import('@/components/content-plan/PlanDownload').then((module) => ({ default: module.PlanDownload })));
