import { AnimatePresence, motion } from 'framer-motion';
import { Bot, Check, CircleAlert, Clock3, Loader2 } from 'lucide-react';

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

export default function AgentsMobileModule({ items }: { items: AgentItem[] }) {
  if (!items.length) {
    return <section className="rounded-[24px] bg-white/[0.04] p-5 text-center ring-1 ring-inset ring-white/[0.07]"><span className="mx-auto grid h-12 w-12 place-items-center rounded-[16px] bg-primary/10 text-primary"><Bot className="h-5 w-5" /></span><h2 className="mt-4 text-balance text-base font-semibold">ИИ-сотрудники ещё не настроены</h2><p className="mt-2 text-pretty text-sm leading-6 text-zinc-500">Когда появится готовый сценарий, здесь будут видны его работа, результат и ошибки.</p></section>;
  }
  return <div className="space-y-2"><AnimatePresence initial={false}>{items.map((item) => {
    const [label, color, Icon] = statusCopy(item.run_status || item.status);
    const running = ['running', 'processing', 'in_progress'].includes(String(item.run_status || item.status || '').toLowerCase());
    return <motion.article key={item.id} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={spring} className="rounded-[22px] bg-white/[0.04] p-4 shadow-[0_18px_54px_rgba(0,0,0,0.2)] ring-1 ring-inset ring-white/[0.07]"><div className="flex items-start gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-primary/10 text-primary"><Bot className="h-5 w-5" /></span><div className="min-w-0 flex-1"><h2 className="text-balance text-sm font-semibold leading-5">{item.title || 'ИИ-сотрудник'}</h2><p className="mt-1 text-pretty text-xs leading-5 text-zinc-500">{item.subtitle || item.category || 'Выполняет настроенную работу LocalOS.'}</p></div></div><div className="mt-4 flex min-h-11 items-center gap-2 border-t border-white/[0.06] pt-3"><Icon className={`h-4 w-4 shrink-0 ${color} ${running ? 'animate-spin motion-reduce:animate-none' : ''}`} /><b className={`text-xs ${color}`}>{label}</b><span className="ml-auto text-right text-[11px] tabular-nums text-zinc-600">{dateLabel(item.completed_at || item.started_at)}</span></div>{item.error_text ? <p className="mt-3 rounded-[15px] bg-rose-500/[0.08] p-3 text-pretty text-xs leading-5 text-rose-200 ring-1 ring-inset ring-rose-400/15">{item.error_text}</p> : null}</motion.article>;
  })}</AnimatePresence></div>;
}
