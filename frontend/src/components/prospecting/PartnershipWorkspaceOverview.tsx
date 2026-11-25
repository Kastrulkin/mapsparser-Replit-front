import { Building2, Mail, Send, MessageSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { getPartnershipWorkspaceCopy } from '@/i18n/partnershipWorkspaceCopy';

type PartnershipWorkspaceOverviewProps = {
  workspaceView: string; currentBusinessId?: string | null;
  rawLeadCount: number; pipelineLeadCount: number; visibleDraftsCount: number;
  visibleBatchesCount: number; visibleReactionsCount: number; sendCount?: number;
  onWorkspaceChange: (value: string) => void;
  part?: 'header' | 'navigation' | 'both';
};

export function PartnershipWorkspaceOverview({ workspaceView, rawLeadCount, pipelineLeadCount,
  visibleDraftsCount, visibleBatchesCount, visibleReactionsCount, sendCount, onWorkspaceChange,
  part = 'both' }: PartnershipWorkspaceOverviewProps) {
  const { language } = useLanguage();
  const copy = getPartnershipWorkspaceCopy(language);
  const stages = [
    { value: 'raw', label: language === 'ru' ? 'Компании' : 'Companies', count: rawLeadCount + pipelineLeadCount, Icon: Building2 },
    { value: 'drafts', label: copy.drafts, count: visibleDraftsCount, Icon: Mail },
    { value: 'queue', label: copy.sending, count: sendCount ?? visibleBatchesCount, Icon: Send },
    { value: 'sent', label: copy.replies, count: visibleReactionsCount, Icon: MessageSquare },
  ];
  return <>
    {part !== 'navigation' && <header className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
      <div className="max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          {language === 'ru' ? 'LocalOS · Партнёрства' : 'LocalOS · Partnerships'}
        </p>
        <h1 className="mt-2 text-balance text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
          {language === 'ru' ? 'Партнёрства' : copy.title}
        </h1>
        <p className="mt-3 max-w-2xl text-pretty text-sm leading-6 text-muted-foreground">
          {language === 'ru'
            ? 'Найдите подходящие компании, подготовьте письма и контролируйте отправку и ответы в одном рабочем процессе.'
            : 'Find suitable companies, prepare messages, and track delivery and replies in one workspace.'}
        </p>
      </div>
      <div className="flex flex-wrap gap-2" aria-label={language === 'ru' ? 'Дополнительные представления' : 'Additional views'}>
        {[{ value: 'overview', label: copy.overview }, { value: 'analytics', label: copy.report }].map(view =>
          <Button key={view.value} variant={workspaceView === view.value ? 'default' : 'outline'} className="min-h-10" aria-pressed={workspaceView === view.value} onClick={() => onWorkspaceChange(view.value)}>{view.label}</Button>)}
      </div>
    </header>}
    {part !== 'header' && <nav aria-label={language === 'ru' ? 'Этапы аутрича' : 'Outreach stages'} className="grid grid-cols-2 gap-1 rounded-[24px] border border-border bg-background p-1.5 shadow-sm sm:grid-cols-4">
      {stages.map(({ value, label, count, Icon }) => {
        const active = workspaceView === value || value === 'raw' && workspaceView === 'pipeline';
        return <Button key={value} variant="ghost" data-shared-treatment={active ? 'brand' : undefined} aria-current={active ? 'page' : undefined} onClick={() => onWorkspaceChange(value)} className={`min-h-11 justify-center gap-2 rounded-[18px] transition-[background-color,color] ${active ? 'bg-slate-950 text-white hover:bg-slate-900 hover:text-white' : 'text-muted-foreground hover:text-foreground'}`}>
          <Icon className="h-4 w-4 shrink-0" aria-hidden="true" /><span>{label}</span><span className={`min-w-[3ch] shrink-0 rounded-md px-1.5 text-center text-xs tabular-nums ${active ? 'bg-white/15 text-white' : 'bg-muted text-foreground'}`}>{count}</span>
        </Button>;
      })}
    </nav>}
  </>;
}
