import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Bot, Check, CircleAlert, Clock3, Loader2, Play } from 'lucide-react';
import ActionPreviewSheet, { type MobileActionPreview } from './ActionPreviewSheet';
import JobProgressSheet from './JobProgressSheet';
import type { MobileScope } from './ScopeProvider';
import { confirmMobileAction, loadMobileJob, mobileJsonHeaders, readMobileJson, type MobileJob } from '@/lib/mobileDataClient';

type AgentItem = {
  id?: string;
  title?: string;
  subtitle?: string;
  business_name?: string;
  category?: string;
  status?: string;
  run_status?: string;
  started_at?: string;
  completed_at?: string;
  error_text?: string;
};

const spring = { duration: 0.3, bounce: 0 };

const statusCopy = (value?: string) => {
  const status = String(value || '').toLowerCase();
  if (['running', 'processing', 'in_progress'].includes(status)) return ['В работе', 'text-primary', Loader2];
  if (['failed', 'error', 'stuck'].includes(status)) return ['Нужно внимание', 'text-rose-300', CircleAlert];
  if (['completed', 'success', 'succeeded'].includes(status)) return ['Готово', 'text-emerald-300', Check];
  return ['Готов к запуску', 'text-zinc-400', Clock3];
};

const dateLabel = (value?: string) => {
  if (!value) return 'Запусков ещё не было';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Дата не определена';
  return date.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
};

export default function AgentsMobileModule({ items, scope, reload, canRun }: { items: AgentItem[]; scope?: MobileScope; reload: () => Promise<void>; canRun: boolean }) {
  const [preview, setPreview] = useState<MobileActionPreview | null>(null);
  const [job, setJob] = useState<MobileJob | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const prepareRun = async (item: AgentItem) => {
    if (!item.id) return;
    setBusy(item.id); setError('');
    try {
      const result = await fetch('/api/operator/mobile/actions/preview', { method: 'POST', headers: mobileJsonHeaders(), body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, capability: 'agents.run', input: { blueprint_id: item.id, inputs: {} } }) }).then(readMobileJson<{ preview?: MobileActionPreview }>);
      setPreview(result.preview || null);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить запуск.'); }
    finally { setBusy(''); }
  };
  const confirmRun = async () => {
    if (!preview?.action_id) return;
    setBusy(preview.action_id); setError('');
    try {
      const result = await confirmMobileAction(preview.action_id, scope);
      const jobId = String(result.operator_result?.job_id || '');
      setPreview(null);
      if (jobId) {
        const loaded = await loadMobileJob(jobId, scope);
        setJob(loaded.job || null);
      }
      await reload();
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось запустить ИИ-сотрудника.'); }
    finally { setBusy(''); }
  };
  useEffect(() => {
    if (!job?.id || job.terminal) return;
    const timer = window.setInterval(() => {
      void loadMobileJob(job.id || '', scope).then((result) => {
        setJob(result.job || null);
        if (result.job?.terminal) void reload();
      }).catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [job?.id, job?.terminal, scope?.kind, scope?.id, reload]);
  if (!items.length) {
    return <section className="rounded-[24px] bg-white/[0.04] p-5 text-center ring-1 ring-inset ring-white/[0.07]"><span className="mx-auto grid h-12 w-12 place-items-center rounded-[16px] bg-primary/10 text-primary"><Bot className="h-5 w-5" /></span><h2 className="mt-4 text-balance text-base font-semibold">ИИ-сотрудники ещё не настроены</h2><p className="mt-2 text-pretty text-sm leading-6 text-zinc-500">Когда появится готовый сценарий, здесь будут видны его работа, результат и ошибки.</p></section>;
  }
  return <div className="space-y-2">{!canRun ? <p className="rounded-[16px] bg-white/[0.035] p-3 text-pretty text-xs leading-5 text-zinc-500 ring-1 ring-inset ring-white/[0.06]">Сейчас можно посмотреть состояние и результаты. Запуск появится после подключения фонового выполнения.</p> : null}{error ? <p className="rounded-[16px] bg-rose-500/[0.08] p-3 text-pretty text-xs leading-5 text-rose-200 ring-1 ring-inset ring-rose-400/15">{error}</p> : null}<AnimatePresence initial={false}>{items.map((item) => {
    const [label, color, Icon] = statusCopy(item.run_status || item.status);
    const running = ['running', 'processing', 'in_progress'].includes(String(item.run_status || item.status || '').toLowerCase());
    return <motion.article key={item.id} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={spring} className="rounded-[22px] bg-white/[0.04] p-4 shadow-[0_18px_54px_rgba(0,0,0,0.2)] ring-1 ring-inset ring-white/[0.07]"><div className="flex items-start gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-primary/10 text-primary"><Bot className="h-5 w-5" /></span><div className="min-w-0 flex-1"><h2 className="text-balance text-sm font-semibold leading-5">{item.title || 'ИИ-сотрудник'}</h2><p className="mt-1 text-pretty text-xs leading-5 text-zinc-500">{item.subtitle || item.category || 'Выполняет настроенную работу LocalOS.'}</p></div></div><div className="mt-4 flex min-h-11 items-center gap-2 border-t border-white/[0.06] pt-3"><Icon className={`h-4 w-4 shrink-0 ${color} ${running ? 'animate-spin motion-reduce:animate-none' : ''}`} /><b className={`text-xs ${color}`}>{label}</b><span className="ml-auto text-right text-[11px] tabular-nums text-zinc-600">{dateLabel(item.completed_at || item.started_at)}</span></div>{item.error_text ? <p className="mt-3 rounded-[15px] bg-rose-500/[0.08] p-3 text-pretty text-xs leading-5 text-rose-200 ring-1 ring-inset ring-rose-400/15">{item.error_text}</p> : null}{canRun && !running ? <button type="button" disabled={Boolean(busy)} onClick={() => void prepareRun(item)} className="mt-3 flex min-h-12 w-full items-center justify-center gap-2 rounded-[16px] bg-primary px-4 text-sm font-semibold text-white shadow-[0_12px_32px_rgba(255,92,51,0.22)] transition-transform active:scale-[0.96] disabled:opacity-50">{busy === item.id ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Play className="h-4 w-4" />}{busy === item.id ? 'Проверяем…' : 'Запустить'}</button> : null}</motion.article>;
  })}</AnimatePresence><ActionPreviewSheet preview={preview} busy={Boolean(busy)} confirmLabel="Запустить" onCancel={() => setPreview(null)} onConfirm={() => void confirmRun()} /><JobProgressSheet job={job} onClose={() => { setJob(null); void reload(); }} /></div>;
}
