import { Clock3, Database, Loader2, ShieldCheck, Sparkles } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { Language } from '@/i18n/LanguageContext';
import type { AgentTemplate } from './types';
import { connectorLabel } from './normalization';
import { getAgentTemplateGalleryCopy, getLocalizedAgentTemplateContent } from './template-gallery-copy';

type AgentTemplateGalleryProps = {
  templates: AgentTemplate[];
  loading: boolean;
  usingTemplateKey: string;
  onUse: (template: AgentTemplate) => void;
  language: Language;
};

export const AgentTemplateGallery = ({ templates, loading, usingTemplateKey, onUse, language }: AgentTemplateGalleryProps) => {
  const copy = getAgentTemplateGalleryCopy(language);
  const triggerLabel = (trigger: string) => trigger === 'schedule.daily' ? copy.scheduled : trigger === 'schedule.weekly' ? copy.weekly : trigger.includes('review') ? copy.review : copy.manual;
  const statusLabel = (status: AgentTemplate['certification_status']) => status === 'certified' ? copy.certified : status === 'beta' ? copy.beta : status === 'testing' ? copy.testing : copy.draft;
  const availableTemplates = templates.filter((template) => template.certification_status === 'beta' || template.certification_status === 'certified');
  const plannedTemplates = templates.filter((template) => template.certification_status !== 'beta' && template.certification_status !== 'certified');
  const renderTemplate = (template: AgentTemplate, available: boolean) => {
    const using = usingTemplateKey === template.key;
    const connections = template.required_connections || [];
    const content = getLocalizedAgentTemplateContent(template, language);
    return (
      <article key={`${template.key}:${template.version}`} className="flex h-full flex-col rounded-2xl bg-slate-50 p-4 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]">
        <div className="flex items-start justify-between gap-3">
          <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-white text-slate-700 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.06)]">
            {connections.length ? <Database className="h-5 w-5" /> : <ShieldCheck className="h-5 w-5" />}
          </div>
          <div className="flex flex-wrap justify-end gap-1.5">
            {template.key === 'daily_owner_digest' && available ? <span className="rounded-full bg-orange-50 px-2.5 py-1 text-[11px] font-semibold text-orange-800 ring-1 ring-orange-200">{copy.recommended}</span> : null}
            <span className={cn('rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1', template.certification_status === 'certified' ? 'bg-emerald-50 text-emerald-800 ring-emerald-200' : template.certification_status === 'beta' ? 'bg-sky-50 text-sky-800 ring-sky-200' : 'bg-white text-slate-600 ring-slate-200')}>
              {statusLabel(template.certification_status)}
            </span>
          </div>
        </div>
        <h3 className="mt-3 text-balance text-base font-semibold leading-6 text-slate-950">{content.name}</h3>
        <p className="mt-1 flex-1 text-pretty text-sm leading-6 text-slate-600">{content.business_result}</p>
        <div className="mt-3 space-y-1.5 text-xs text-slate-600">
          <div className="flex items-center gap-2"><Clock3 className="h-4 w-4 shrink-0" /><span>{triggerLabel(template.trigger)}</span></div>
          <div className="flex items-start gap-2"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" /><span>{connections.length ? `${copy.needs}: ${connections.map(connectorLabel).join(', ')}` : copy.localos}</span></div>
        </div>
        {available ? (
          <Button type="button" className="mt-4 min-h-11 transition-transform duration-150 ease-out active:scale-[0.96]" onClick={() => onUse(template)} disabled={Boolean(usingTemplateKey)}>
            {using ? <Loader2 className="mr-2 h-4 w-4 animate-spin motion-reduce:animate-none" /> : null}
            {using ? copy.preparing : copy.use}
          </Button>
        ) : null}
      </article>
    );
  };
  return (
  <section className="rounded-3xl bg-white p-5 shadow-[0_18px_48px_rgba(15,23,42,0.07),0_0_0_1px_rgba(15,23,42,0.07)]">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-orange-700">
          <Sparkles className="h-4 w-4" />
          {copy.eyebrow}
        </div>
        <h2 className="mt-2 text-balance text-xl font-semibold text-slate-950">{copy.title}</h2>
        <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">
          {copy.description}
        </p>
      </div>
      <div className="text-xs font-medium tabular-nums text-slate-500">{templates.length} {copy.count}</div>
    </div>
    {loading ? (
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3" aria-label={copy.loading}>
        {[0, 1, 2].map((item) => <div key={item} className="h-56 animate-pulse rounded-2xl bg-slate-100" />)}
      </div>
    ) : (
      <div className="mt-4 grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
        {availableTemplates.map((template) => renderTemplate(template, true))}
      </div>
    )}
    {!loading && plannedTemplates.length ? (
      <details className="mt-4 rounded-2xl bg-slate-50 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]">
        <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 marker:content-none">
          <span>
            <span className="block text-sm font-semibold text-slate-900">{copy.plannedTitle} · <span className="tabular-nums">{plannedTemplates.length}</span></span>
            <span className="mt-0.5 block text-xs text-slate-500">{copy.plannedDescription}</span>
          </span>
          <Sparkles className="h-4 w-4 shrink-0 text-slate-400" />
        </summary>
        <div className="grid gap-3 px-3 pb-3 md:grid-cols-2 2xl:grid-cols-3">
          {plannedTemplates.map((template) => renderTemplate(template, false))}
        </div>
      </details>
    ) : null}
  </section>
  );
};
