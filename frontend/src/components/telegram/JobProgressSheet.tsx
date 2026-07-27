import { AnimatePresence, motion } from 'framer-motion';
import { Check, Loader2, RefreshCw, Square, X } from 'lucide-react';
import type { MobileJob } from '@/lib/mobileDataClient';

const spring = { duration: 0.3, bounce: 0 };

const jobTitle = (job?: MobileJob | null) => {
  if (job?.kind === 'content_plan_generate') return 'Собираем контент-план';
  if (job?.kind === 'content_draft_generate') return 'Готовим текст публикации';
  if (job?.kind === 'finance_document_recognize') return 'Разбираем продажи';
  if (job?.kind === 'card_refresh') return 'Обновляем данные карточки';
  if (job?.kind === 'agent_run') return 'ИИ-сотрудник выполняет задачу';
  return 'LocalOS выполняет задачу';
};

export default function JobProgressSheet({ job, busy = false, onClose, onRetry, onCancel }: { job: MobileJob | null; busy?: boolean; onClose: () => void; onRetry?: () => void; onCancel?: () => void }) {
  const completed = job?.status === 'completed';
  const failed = job?.status === 'failed';
  const cancelled = job?.status === 'cancelled';
  const progress = Math.max(0, Math.min(100, Number(job?.progress || 0)));
  const canRetry = Boolean(onRetry && job?.available_actions?.includes('retry'));
  const canCancel = Boolean(onCancel && job?.available_actions?.includes('cancel'));

  return <AnimatePresence initial={false}>
    {job ? <motion.div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 px-3 pb-[calc(12px+env(safe-area-inset-bottom))] backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
      <motion.section role="dialog" aria-modal="true" aria-labelledby="mobile-job-title" initial={{ opacity: 0, y: 40, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 24, scale: 0.98 }} transition={spring} className="w-full max-w-xl rounded-[28px] bg-zinc-900 p-5 shadow-[0_30px_100px_rgba(0,0,0,0.6)] ring-1 ring-inset ring-white/[0.09]">
        <div className="flex items-start gap-3">
          <motion.span animate={completed ? { scale: [0.86, 1.05, 1] } : { scale: 1 }} transition={spring} className={`grid h-12 w-12 shrink-0 place-items-center rounded-[16px] ${completed ? 'bg-emerald-400/12 text-emerald-300' : failed ? 'bg-rose-400/12 text-rose-300' : 'bg-primary/12 text-primary'}`}>
            {completed ? <Check className="h-5 w-5" /> : <Loader2 className={`h-5 w-5 ${failed || cancelled ? '' : 'animate-spin motion-reduce:animate-none'}`} />}
          </motion.span>
          <div className="min-w-0 flex-1">
            <small className="font-semibold uppercase tracking-[0.13em] text-primary">{completed ? 'Готово' : failed ? 'Нужно внимание' : cancelled ? 'Остановлено' : 'LocalOS работает'}</small>
            <h2 id="mobile-job-title" className="mt-1 text-balance text-xl font-semibold tracking-[-0.035em]">{jobTitle(job)}</h2>
            <p className="mt-2 text-pretty text-xs leading-5 text-zinc-500">{job.error || job.stage || 'Задача сохранена. Экран можно закрыть.'}</p>
          </div>
          <button type="button" aria-label="Закрыть" onClick={onClose} className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-white/[0.05] text-zinc-400 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96]"><X className="h-4 w-4" /></button>
        </div>
        <div className="mt-5">
          <div className="flex items-center justify-between text-[11px] text-zinc-500"><span>{completed ? 'Результат сохранён' : 'Текущий этап'}</span><b className="tabular-nums text-zinc-300">{progress}%</b></div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.06]"><motion.div className={`h-full rounded-full ${failed ? 'bg-rose-400' : completed ? 'bg-emerald-400' : 'bg-primary'}`} initial={false} animate={{ width: `${progress}%` }} transition={spring} /></div>
        </div>
        {!completed && !failed && !cancelled ? <p className="mt-4 text-pretty text-[11px] leading-5 text-zinc-600">Работа продолжится, даже если закрыть Mini App. Готовый результат появится в «Задачах».</p> : null}
        <div className="mt-5 grid gap-2">
          {canRetry ? <button type="button" disabled={busy} onClick={onRetry} className="flex min-h-12 items-center justify-center gap-2 rounded-[16px] bg-primary px-4 text-sm font-semibold text-white shadow-[0_12px_32px_rgba(255,92,51,0.24)] transition-[filter,transform] active:scale-[0.96] disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${busy ? 'animate-spin motion-reduce:animate-none' : ''}`} />Повторить</button> : null}
          {canCancel ? <button type="button" disabled={busy} onClick={onCancel} className="flex min-h-11 items-center justify-center gap-2 rounded-[14px] bg-white/[0.05] px-4 text-xs font-semibold text-zinc-400 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96] disabled:opacity-50"><Square className="h-3.5 w-3.5" />Остановить</button> : null}
          {completed || cancelled ? <button type="button" onClick={onClose} className="min-h-12 rounded-[16px] bg-primary px-4 text-sm font-semibold text-white transition-transform active:scale-[0.96]">Вернуться к результату</button> : null}
        </div>
      </motion.section>
    </motion.div> : null}
  </AnimatePresence>;
}
