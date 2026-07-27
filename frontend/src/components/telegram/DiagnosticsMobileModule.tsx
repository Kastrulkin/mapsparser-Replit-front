import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { CheckCircle2, CircleAlert, Clock3, Loader2, RefreshCw, ShieldCheck } from 'lucide-react';
import ActionPreviewSheet, { type MobileActionPreview } from './ActionPreviewSheet';
import JobProgressSheet from './JobProgressSheet';
import type { MobileScope } from './ScopeProvider';
import { confirmMobileAction, loadMobileJob, mobileJsonHeaders, readMobileJson, type MobileJob } from '@/lib/mobileDataClient';

type DiagnosticItem = {
  id?: string;
  kind?: string;
  business_id?: string;
  title?: string;
  subtitle?: string;
  business_name?: string;
  status?: string;
  source?: string;
  updated_at?: string;
};

const spring = { duration: 0.3, bounce: 0 };

const dateLabel = (value?: string) => {
  if (!value) return 'Время не указано';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Время не определено';
  return date.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
};

export default function DiagnosticsMobileModule({ items, scope, reload }: { items: DiagnosticItem[]; scope?: MobileScope; reload: () => Promise<void> }) {
  const [preview, setPreview] = useState<MobileActionPreview | null>(null);
  const [job, setJob] = useState<MobileJob | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const prepareRetry = async (item: DiagnosticItem) => {
    if (!item.id || item.kind !== 'diagnostic_job' || !item.business_id) return;
    setBusy(item.id);
    setError('');
    try {
      const result = await fetch('/api/operator/mobile/actions/preview', {
        method: 'POST',
        headers: mobileJsonHeaders(),
        body: JSON.stringify({
          scope_type: scope?.kind,
          scope_id: scope?.id || null,
          capability: 'diagnostics.retry',
          input: { job_id: item.id },
        }),
      }).then(readMobileJson<{ preview?: MobileActionPreview }>);
      setPreview(result.preview || null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить повторный запуск.');
    } finally {
      setBusy('');
    }
  };

  const confirmRetry = async () => {
    if (!preview?.action_id) return;
    setBusy(preview.action_id);
    setError('');
    try {
      const result = await confirmMobileAction(preview.action_id, scope);
      const jobId = String(result.operator_result?.job_id || '');
      setPreview(null);
      if (jobId) {
        const loaded = await loadMobileJob(jobId, scope);
        setJob(loaded.job || null);
      }
      await reload();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось повторить задачу.');
    } finally {
      setBusy('');
    }
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
    return <section className="rounded-[24px] bg-emerald-500/[0.045] p-5 ring-1 ring-inset ring-emerald-400/10"><div className="flex items-start gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-emerald-400/10 text-emerald-300"><CheckCircle2 className="h-5 w-5" /></span><div><h2 className="text-balance text-base font-semibold">Критичных ошибок нет</h2><p className="mt-1 text-pretty text-sm leading-6 text-zinc-500">Очередь показывает только реальные сбои парсеров и интеграций, которые требуют вмешательства.</p></div></div></section>;
  }

  return <div>
    {error ? <p className="mb-3 rounded-[16px] bg-rose-500/[0.08] p-3 text-pretty text-xs leading-5 text-rose-200 ring-1 ring-inset ring-rose-400/15">{error}</p> : null}
    <section className="mb-3 rounded-[22px] bg-rose-500/[0.06] p-4 ring-1 ring-inset ring-rose-400/10"><div className="flex items-center gap-3"><ShieldCheck className="h-5 w-5 text-rose-300" /><div><b className="block text-sm">Требуют проверки</b><small className="mt-1 block text-pretty text-zinc-500"><span className="tabular-nums">{items.length}</span> задач парсинга или интеграций</small></div></div></section>
    <div className="space-y-2"><AnimatePresence initial={false}>{items.map((item) => {
      const retryable = item.kind === 'diagnostic_job' && Boolean(item.business_id);
      return <motion.article key={item.id} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={spring} className="rounded-[22px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]">
        <div className="flex items-start gap-3"><CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-rose-300" /><div className="min-w-0 flex-1"><h2 className="text-balance text-sm font-semibold leading-5">{item.title || 'Ошибка интеграции'}</h2><p className="mt-1 text-pretty text-xs leading-5 text-zinc-500">{item.subtitle || 'Нужна ручная проверка.'}</p></div></div>
        <div className="mt-3 flex items-center gap-2 border-t border-white/[0.06] pt-3 text-[11px] text-zinc-600"><Clock3 className="h-3.5 w-3.5" /><span className="tabular-nums">{dateLabel(item.updated_at)}</span>{item.business_name ? <span className="ml-auto max-w-[45%] truncate text-zinc-500">{item.business_name}</span> : null}</div>
        {retryable ? <button type="button" disabled={Boolean(busy)} onClick={() => void prepareRetry(item)} className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-[15px] bg-white/[0.055] px-4 text-xs font-semibold text-zinc-200 ring-1 ring-inset ring-white/[0.08] transition-transform active:scale-[0.96] disabled:opacity-50">{busy === item.id ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <RefreshCw className="h-4 w-4" />}{busy === item.id ? 'Проверяем…' : 'Проверить и повторить'}</button> : null}
      </motion.article>;
    })}</AnimatePresence></div>
    <ActionPreviewSheet preview={preview} busy={Boolean(busy)} confirmLabel="Повторить" onCancel={() => setPreview(null)} onConfirm={() => void confirmRetry()} />
    <JobProgressSheet job={job} onClose={() => { setJob(null); void reload(); }} />
  </div>;
}
