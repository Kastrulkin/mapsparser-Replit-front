import { RotateCcw, Sparkles } from 'lucide-react';
import { useId, useState } from 'react';

import { DashboardPageHeader, DashboardSection } from '@/components/dashboard/DashboardPrimitives';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { demoAverageTicketCopy } from '@/i18n/demoAverageTicketCopy';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { getDemoShowcaseData } from '@/i18n/demoShowcaseData';
import { getDemoWorkspaceCopy } from '@/i18n/demoWorkspaceCopy';

const formatRub = (language: string, value: number) => `${new Intl.NumberFormat(language).format(value)} ₽`;

export function DemoAverageTicketPage() {
  const { language } = useLanguage();
  const [showScript, setShowScript] = useState(false);
  const scriptPanelId = useId();
  const workspaceCopy = getDemoWorkspaceCopy(language).averageTicket;
  const copy = demoAverageTicketCopy[language];
  const service = getDemoShowcaseData(language).services[0];
  const addOnPrice = 300;
  const total = service.price + addOnPrice;

  const toggleScript = () => {
    setShowScript((visible) => !visible);
  };

  return (
    <div className="space-y-5 pb-16" data-tour-target="average-ticket-demo">
      <DashboardPageHeader
        eyebrow={copy.eyebrow}
        title={workspaceCopy.title}
        description={copy.description}
      />

      <DashboardSection title={copy.examplePlan} description={copy.description}>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">{copy.fictitious}</Badge>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] md:items-stretch">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{copy.primaryService}</p>
            <p className="mt-2 text-lg font-semibold text-slate-950">{service.name}</p>
            <p className="mt-2 text-sm tabular-nums text-slate-600">{formatRub(language, service.price)}</p>
          </div>
          <div className="hidden items-center justify-center text-xl font-semibold text-slate-400 md:flex" aria-hidden="true">+</div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{copy.addOn}</p>
            <p className="mt-2 text-lg font-semibold text-slate-950">{copy.addOnService}</p>
            <p className="mt-2 text-sm tabular-nums text-slate-600">{formatRub(language, addOnPrice)}</p>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between gap-4 rounded-2xl bg-slate-950 px-4 py-3 text-white">
          <span className="text-sm font-medium">{copy.total}</span>
          <strong className="text-lg tabular-nums">{formatRub(language, total)}</strong>
        </div>

        <div id={scriptPanelId} className="mt-5" aria-live="polite">
          {showScript ? (
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
              <h2 className="font-semibold text-emerald-950">{copy.scriptTitle}</h2>
              <p className="mt-2 text-sm leading-6 text-emerald-900">{copy.script}</p>
              <p className="mt-3 text-xs leading-5 text-emerald-800">{copy.safety}</p>
            </div>
          ) : null}
        </div>

        <Button type="button" className="mt-5 h-auto min-h-11 max-w-full gap-2 whitespace-normal text-start" onClick={toggleScript} aria-expanded={showScript} aria-controls={scriptPanelId}>
          {showScript ? <RotateCcw className="h-4 w-4" aria-hidden="true" /> : <Sparkles className="h-4 w-4" aria-hidden="true" />}
          {showScript ? copy.hideScript : copy.showScript}
        </Button>
      </DashboardSection>
    </div>
  );
}
