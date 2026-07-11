import { Link } from 'react-router-dom';
import React from 'react';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  CircleDot,
  ClipboardList,
  ExternalLink,
  Info,
  LucideIcon,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { cn } from '@/lib/utils';

import { SettingsHubCopy } from './settingsHubCopy';
import { HubStatus, ModuleState, SettingsHubState } from './settingsHubState';

type StatusView = {
  className: string;
  icon: LucideIcon;
};

const statusViews: Record<HubStatus | 'partially_configured', StatusView> = {
  ready: {
    className: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    icon: CheckCircle2,
  },
  attention: {
    className: 'bg-amber-50 text-amber-700 ring-amber-200',
    icon: AlertCircle,
  },
  not_configured: {
    className: 'bg-slate-100 text-slate-600 ring-slate-200',
    icon: CircleDot,
  },
  manual: {
    className: 'bg-sky-50 text-sky-700 ring-sky-200',
    icon: Info,
  },
  error: {
    className: 'bg-rose-50 text-rose-700 ring-rose-200',
    icon: AlertCircle,
  },
  partially_configured: {
    className: 'bg-amber-50 text-amber-700 ring-amber-200',
    icon: AlertCircle,
  },
};

const statusView = (status: HubStatus | 'partially_configured') => statusViews[status];

export const StatusBadge = ({
  status,
  copy,
}: {
  status: HubStatus | 'partially_configured';
  copy: SettingsHubCopy;
}) => {
  const view = statusView(status);
  const Icon = view.icon;
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ring-1', view.className)}>
      <Icon className="h-3.5 w-3.5" />
      {copy.status[status]}
    </span>
  );
};

export const ReadinessSummary = ({
  summary,
  copy,
}: {
  summary: SettingsHubState['summary'];
  copy: SettingsHubCopy;
}) => {
  const items = [
    { ...copy.summary.communications, status: summary.communications },
    { ...copy.summary.publications, status: summary.publications },
    { ...copy.summary.crm, status: summary.crm },
  ];

  return (
    <section data-settings-hub-first-layer="readiness-summary" className="grid gap-3 md:grid-cols-3">
      {items.map((item) => (
        <div key={item.label} className="rounded-2xl border border-slate-200/80 bg-white px-4 py-4 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{item.label}</div>
              <div className="mt-2 text-sm leading-6 text-slate-600">{item.hint}</div>
            </div>
            <StatusBadge status={item.status} copy={copy} />
          </div>
        </div>
      ))}
    </section>
  );
};

export const NextStepBanner = ({
  nextStep,
  onOpenDetail,
  copy,
}: {
  nextStep: SettingsHubState['nextStep'];
  onOpenDetail: (detail: string) => void;
  copy: SettingsHubCopy;
}) => {
  if (!nextStep) {
    return (
      <section data-settings-hub-first-layer="next-step" className="rounded-3xl border border-emerald-200 bg-emerald-50/85 p-5 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">{copy.nextStep.readyTitle}</h2>
            <p className="mt-1 text-sm leading-6 text-slate-700">{copy.nextStep.readyDescription}</p>
          </div>
          <Button type="button" variant="outline" asChild>
            <Link to="/dashboard/card?tab=news&mode=plan">{copy.nextStep.openContentPlan}</Link>
          </Button>
        </div>
      </section>
    );
  }

  return (
    <section data-settings-hub-first-layer="next-step" className="rounded-3xl border border-sky-200 bg-sky-50/85 p-5 shadow-sm">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-700">{copy.nextStep.eyebrow}</div>
          <h2 className="mt-2 text-xl font-semibold text-slate-950">{copy.nextStep.titles[nextStep.title] || nextStep.title}</h2>
          <p className="mt-1 text-sm leading-6 text-slate-700">{copy.nextStep.description}</p>
        </div>
        <Button
          type="button"
          onClick={() => nextStep.drawer ? onOpenDetail(nextStep.drawer) : undefined}
          className="min-h-10 bg-slate-900 text-white hover:bg-slate-800"
        >
          {copy.nextStep.actions[nextStep.actionLabel] || nextStep.actionLabel}
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </section>
  );
};

const ModuleMetaRows = ({ module, copy }: { module: ModuleState; copy: SettingsHubCopy }) => {
  if (module.key === 'telegram') {
    return (
      <div className="grid gap-2 text-xs sm:grid-cols-2">
        <div className={cn('rounded-xl px-3 py-2 ring-1', module.meta?.ownerBotConnected ? 'bg-emerald-50 text-emerald-800 ring-emerald-100' : 'bg-amber-50 text-amber-800 ring-amber-100')}>
          {copy.metaRows.ownerBot}: {module.meta?.ownerBotConnected ? copy.metaRows.connected : copy.metaRows.missing}
        </div>
        <div className={cn('rounded-xl px-3 py-2 ring-1', module.meta?.publicationTargetSet ? 'bg-emerald-50 text-emerald-800 ring-emerald-100' : 'bg-amber-50 text-amber-800 ring-amber-100')}>
          {copy.metaRows.publicationTarget}: {module.meta?.publicationTargetSet ? copy.metaRows.set : copy.metaRows.missing}
        </div>
      </div>
    );
  }

  if (module.key === 'whatsapp') {
    return (
      <div className="grid gap-2 text-xs sm:grid-cols-2">
        <div className={cn('rounded-xl px-3 py-2 ring-1', module.meta?.phoneAdded ? 'bg-emerald-50 text-emerald-800 ring-emerald-100' : 'bg-slate-50 text-slate-600 ring-slate-200')}>
          {copy.metaRows.number}: {module.meta?.phoneAdded ? copy.metaRows.added : copy.metaRows.missing}
        </div>
        <div className={cn('rounded-xl px-3 py-2 ring-1', module.meta?.wabaConnected ? 'bg-emerald-50 text-emerald-800 ring-emerald-100' : 'bg-slate-50 text-slate-600 ring-slate-200')}>
          {copy.metaRows.sending}: {module.meta?.wabaConnected ? copy.metaRows.configured : copy.metaRows.notConfigured}
        </div>
      </div>
    );
  }

  if (module.meta?.provider) {
    return <div className="rounded-xl bg-emerald-50 px-3 py-2 text-xs text-emerald-800 ring-1 ring-emerald-100">{module.meta.provider}</div>;
  }

  return null;
};

export const SettingsModuleCard = ({
  module,
  onOpenDetail,
  copy,
}: {
  module: ModuleState;
  onOpenDetail: (detail: string) => void;
  copy: SettingsHubCopy;
}) => {
  const displayStatus = module.displayStatus || module.status;
  const moduleCopy = copy.modules[module.key];
  return (
    <article data-settings-hub-first-layer="module-card" className="flex min-h-[220px] flex-col justify-between rounded-3xl border border-slate-200/80 bg-white p-5 shadow-sm">
      <div>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-slate-950">{moduleCopy.label}</h3>
            <p className="mt-1 truncate text-sm text-slate-600">{moduleCopy.description}</p>
          </div>
          <StatusBadge status={displayStatus} copy={copy} />
        </div>
        <div className="mt-4">
          <ModuleMetaRows module={module} copy={copy} />
        </div>
      </div>
      <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <Button
          type="button"
          onClick={() => onOpenDetail(module.primaryAction.target)}
          className="min-h-10 bg-slate-900 text-white hover:bg-slate-800"
        >
          {copy.actions[module.primaryAction.label] || module.primaryAction.label}
        </Button>
        {module.secondaryAction ? (
          <Button type="button" variant="ghost" className="min-h-10 text-slate-600 hover:text-slate-950" asChild>
            <Link to={module.secondaryAction.target}>
              {copy.actions[module.secondaryAction.label] || module.secondaryAction.label}
              <ExternalLink className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        ) : null}
      </div>
    </article>
  );
};

export const SecondaryLinks = ({ copy }: { copy: SettingsHubCopy }) => (
  <section data-settings-hub-first-layer="secondary-links" className="grid gap-3 md:grid-cols-2">
    <Button type="button" variant="outline" className="min-h-12 justify-start gap-2 rounded-2xl bg-white" asChild>
      <Link to="/dashboard/agents">
        <ClipboardList className="h-4 w-4" />
        {copy.secondaryLinks.agents}
      </Link>
    </Button>
    <Button type="button" variant="outline" className="min-h-12 justify-start gap-2 rounded-2xl bg-white" asChild>
      <Link to="/dashboard/network">
        <ClipboardList className="h-4 w-4" />
        {copy.secondaryLinks.network}
      </Link>
    </Button>
  </section>
);

export const SettingsDetailSheet = ({
  open,
  title,
  description,
  children,
  onOpenChange,
}: {
  open: boolean;
  title: string;
  description: string;
  children: React.ReactNode;
  onOpenChange: (open: boolean) => void;
}) => (
  <Sheet open={open} onOpenChange={onOpenChange}>
    <SheetContent side="right" className="w-[96vw] overflow-y-auto bg-slate-50 p-0 sm:max-w-4xl">
      <div className="border-b border-slate-200 bg-white px-6 py-5">
        <SheetHeader>
          <SheetTitle className="text-2xl text-slate-950">{title}</SheetTitle>
          <SheetDescription className="text-sm leading-6 text-slate-600">{description}</SheetDescription>
        </SheetHeader>
      </div>
      <div className="space-y-5 px-4 py-5 sm:px-6">{children}</div>
    </SheetContent>
  </Sheet>
);
