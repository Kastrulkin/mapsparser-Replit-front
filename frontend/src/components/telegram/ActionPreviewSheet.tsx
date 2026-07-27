import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, Check, Coins, Loader2, MapPin, ShieldCheck, X } from 'lucide-react';

export type MobileActionPreview = {
  action_id?: string;
  capability?: string;
  target_businesses?: Array<{ id?: string; name?: string }>;
  objects?: Array<{ id?: string; author_name?: string; business_name?: string }>;
  changes?: Array<{ object_id?: string; operation?: string; label?: string; items_count?: number; interval_hours?: number }>;
  estimated_credits?: number;
  external_effects?: boolean;
  is_mass_action?: boolean;
  expires_at?: string;
  analysis?: { before_count?: number; after_count?: number; groups?: unknown[] };
};

const spring = { duration: 0.3, bounce: 0 };

const externalEffectCopy = (capability?: string) => {
  if (capability === 'cards.refresh' || capability === 'diagnostics.retry') {
    return 'LocalOS обратится ко внешнему источнику и обновит собранные данные.';
  }
  return 'Действие изменит данные во внешней системе.';
};

export default function ActionPreviewSheet({ preview, busy, confirmLabel = 'Подтвердить', onCancel, onConfirm }: { preview: MobileActionPreview | null; busy: boolean; confirmLabel?: string; onCancel: () => void; onConfirm: () => void }) {
  return <AnimatePresence initial={false}>
    {preview ? <motion.div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 px-3 pb-[calc(12px+env(safe-area-inset-bottom))] backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }} role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target && !busy) onCancel(); }}>
      <motion.section role="dialog" aria-modal="true" aria-labelledby="mobile-action-preview-title" initial={{ opacity: 0, y: 40, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 24, scale: 0.98 }} transition={spring} className="w-full max-w-xl rounded-[28px] bg-zinc-900 p-5 shadow-[0_30px_100px_rgba(0,0,0,0.6)] ring-1 ring-inset ring-white/[0.09]">
        <div className="flex items-start gap-3">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-primary/12 text-primary"><ShieldCheck className="h-5 w-5" /></span>
          <div className="min-w-0 flex-1"><h2 id="mobile-action-preview-title" className="text-balance text-lg font-semibold tracking-[-0.025em]">Проверьте действие</h2><p className="mt-1 text-pretty text-xs leading-5 text-zinc-500">LocalOS выполнит только перечисленные изменения после вашего подтверждения.</p></div>
          <button type="button" aria-label="Закрыть проверку" disabled={busy} onClick={onCancel} className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-white/[0.05] text-zinc-400 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96] disabled:opacity-40"><X className="h-4 w-4" /></button>
        </div>
        <div className="mt-5 space-y-2">
          {preview.objects?.length ? <div className="flex min-h-11 items-center gap-2 rounded-[15px] bg-white/[0.04] px-3 ring-1 ring-inset ring-white/[0.06]"><Check className="h-4 w-4 shrink-0 text-emerald-300" /><span className="text-xs text-zinc-400">Объектов: <b className="tabular-nums text-zinc-200">{preview.objects.length}</b></span></div> : null}
          {preview.target_businesses?.map((business) => <div key={business.id} className="flex min-h-11 items-center gap-2 rounded-[15px] bg-white/[0.04] px-3 ring-1 ring-inset ring-white/[0.06]"><MapPin className="h-4 w-4 shrink-0 text-primary" /><span className="min-w-0 flex-1 truncate text-xs font-medium">{business.name || 'Выбранная точка'}</span></div>)}
          {preview.changes?.map((change, index) => <div key={change.object_id || `${change.operation}-${index}`} className="flex min-h-11 items-center gap-2 px-3 text-xs text-zinc-400"><Check className="h-4 w-4 shrink-0 text-emerald-300" /><span className="text-pretty">{change.label || 'Подготовленное изменение'}{change.items_count ? <> · <span className="tabular-nums">{change.items_count}</span> публикаций</> : null}{change.interval_hours ? <> · каждые <span className="tabular-nums">{change.interval_hours}</span> ч.</> : null}</span></div>)}
        </div>
        {preview.external_effects ? <div className="mt-4 flex gap-3 rounded-[16px] bg-amber-400/[0.07] p-3 text-xs leading-5 text-amber-100/80 ring-1 ring-inset ring-amber-400/15"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />{externalEffectCopy(preview.capability)}</div> : null}
        <div className="mt-4 flex min-h-11 items-center gap-2 border-t border-white/[0.06] pt-3 text-xs text-zinc-500"><Coins className="h-4 w-4" /><span>Стоимость</span><b className="ml-auto tabular-nums text-zinc-200">{preview.estimated_credits || 0} кредитов</b></div>
        <div className="mt-4 grid grid-cols-[auto_minmax(0,1fr)] gap-2">
          <button type="button" disabled={busy} onClick={onCancel} className="min-h-12 rounded-[16px] bg-white/[0.05] px-5 text-sm font-semibold text-zinc-400 ring-1 ring-inset ring-white/[0.07] transition-transform active:scale-[0.96] disabled:opacity-40">Отмена</button>
          <button type="button" disabled={busy} onClick={onConfirm} className="flex min-h-12 items-center justify-center gap-2 rounded-[16px] bg-primary px-4 text-sm font-semibold text-white shadow-[0_12px_32px_rgba(255,92,51,0.24)] transition-[filter,transform] active:scale-[0.96] disabled:opacity-50">{busy ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Check className="h-4 w-4" />}{busy ? 'Выполняем…' : confirmLabel}</button>
        </div>
      </motion.section>
    </motion.div> : null}
  </AnimatePresence>;
}
