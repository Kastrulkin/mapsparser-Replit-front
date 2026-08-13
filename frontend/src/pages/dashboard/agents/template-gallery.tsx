import { CheckCircle2, Clock3, Database, Loader2, ShieldCheck, Sparkles } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { AgentTemplate } from './types';
import { connectorLabel } from './normalization';

type AgentTemplateGalleryProps = {
  templates: AgentTemplate[];
  loading: boolean;
  usingTemplateKey: string;
  onUse: (template: AgentTemplate) => void;
};

const triggerLabel = (trigger: string) => {
  if (trigger === 'schedule.daily') return 'По расписанию';
  if (trigger.includes('review')) return 'При новом отзыве';
  return 'По команде';
};

const statusLabel = (status: AgentTemplate['certification_status']) => {
  if (status === 'certified') return 'Проверен';
  if (status === 'beta') return 'Beta-проверка';
  if (status === 'testing') return 'На испытании';
  return 'Черновик';
};

export const AgentTemplateGallery = ({ templates, loading, usingTemplateKey, onUse }: AgentTemplateGalleryProps) => (
  <section className="rounded-3xl bg-white p-5 shadow-[0_18px_48px_rgba(15,23,42,0.07),0_0_0_1px_rgba(15,23,42,0.07)]">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-orange-700">
          <Sparkles className="h-4 w-4" />
          Готовые практики
        </div>
        <h2 className="mt-2 text-balance text-xl font-semibold text-slate-950">Выберите результат, который нужен бизнесу</h2>
        <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">
          Просмотр бесплатный и ничего не создаёт. После выбора LocalOS подготовит одного агента для проверки сценария.
        </p>
      </div>
      <div className="text-xs font-medium tabular-nums text-slate-500">{templates.length} практик</div>
    </div>
    {loading ? (
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3" aria-label="Загружаются готовые практики">
        {[0, 1, 2].map((item) => <div key={item} className="h-56 animate-pulse rounded-2xl bg-slate-100" />)}
      </div>
    ) : (
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {templates.map((template) => {
          const using = usingTemplateKey === template.key;
          const available = template.certification_status === 'beta' || template.certification_status === 'certified';
          const connections = template.required_connections || [];
          return (
            <article key={`${template.key}:${template.version}`} className="flex min-h-64 flex-col rounded-2xl bg-slate-50 p-4 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]">
              <div className="flex items-start justify-between gap-3">
                <div className="rounded-xl bg-white p-2 text-slate-700 shadow-[0_2px_8px_rgba(15,23,42,0.07)]">
                  {connections.length ? <Database className="h-5 w-5" /> : <CheckCircle2 className="h-5 w-5" />}
                </div>
                <span className={cn('rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1', template.certification_status === 'certified' ? 'bg-emerald-50 text-emerald-800 ring-emerald-200' : template.certification_status === 'beta' ? 'bg-sky-50 text-sky-800 ring-sky-200' : 'bg-white text-slate-600 ring-slate-200')}>
                  {statusLabel(template.certification_status)}
                </span>
              </div>
              <h3 className="mt-3 text-balance text-base font-semibold leading-6 text-slate-950">{template.name}</h3>
              <p className="mt-1 flex-1 text-pretty text-sm leading-6 text-slate-600">{template.business_result}</p>
              <div className="mt-3 space-y-1.5 text-xs text-slate-600">
                <div className="flex items-center gap-2"><Clock3 className="h-4 w-4" />{triggerLabel(template.trigger)}</div>
                <div className="flex items-start gap-2"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" /><span>{connections.length ? `Понадобится: ${connections.map(connectorLabel).join(', ')}` : 'Работает на данных LocalOS'}</span></div>
              </div>
              <Button type="button" variant={available ? 'default' : 'outline'} className="mt-4 min-h-11 transition-transform duration-150 ease-out active:scale-[0.96]" onClick={() => onUse(template)} disabled={Boolean(usingTemplateKey) || !available}>
                {using ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                {using ? 'Подготавливаем…' : available ? 'Использовать' : 'Скоро'}
              </Button>
            </article>
          );
        })}
      </div>
    )}
  </section>
);
