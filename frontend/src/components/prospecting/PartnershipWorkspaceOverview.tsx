import { Building2, Mail, Send, MessageSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useLanguage } from '@/i18n/LanguageContext';
import { getPartnershipWorkspaceCopy } from '@/i18n/partnershipWorkspaceCopy';

type PartnershipWorkspaceOverviewProps = {
  workspaceView: string; currentBusinessId?: string | null;
  rawLeadCount: number; pipelineLeadCount: number; visibleDraftsCount: number;
  visibleBatchesCount: number; visibleReactionsCount: number;
  onWorkspaceChange: (value: string) => void;
  part?: 'header' | 'navigation' | 'both';
};

export function PartnershipWorkspaceOverview({ workspaceView, rawLeadCount, pipelineLeadCount,
  visibleDraftsCount, visibleBatchesCount, visibleReactionsCount, onWorkspaceChange,
  part = 'both' }: PartnershipWorkspaceOverviewProps) {
  const { language } = useLanguage();
  const copy = getPartnershipWorkspaceCopy(language);
  const stages = [
    { value: 'raw', label: language === 'ru' ? 'Компании' : 'Companies', count: rawLeadCount + pipelineLeadCount, Icon: Building2 },
    { value: 'drafts', label: copy.drafts, count: visibleDraftsCount, Icon: Mail },
    { value: 'queue', label: copy.sending, count: visibleBatchesCount, Icon: Send },
    { value: 'sent', label: copy.replies, count: visibleReactionsCount, Icon: MessageSquare },
  ];
  return <>
    {part !== 'navigation' && <header className="flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-2xl font-semibold text-foreground">{language === 'ru' ? 'Партнёрства' : copy.title}</h1>
      <div className="flex gap-1" aria-label={language === 'ru' ? 'Дополнительные представления' : 'Additional views'}>
        {[{ value: 'overview', label: copy.overview }, { value: 'analytics', label: copy.report }].map(view =>
          <Button key={view.value} size="sm" variant={workspaceView === view.value ? 'secondary' : 'ghost'} aria-pressed={workspaceView === view.value} onClick={() => onWorkspaceChange(view.value)}>{view.label}</Button>)}
      </div>
    </header>}
    {part !== 'header' && <nav aria-label={language === 'ru' ? 'Этапы аутрича' : 'Outreach stages'} className="grid grid-cols-2 gap-1 border-b border-border bg-background sm:grid-cols-4">
      {stages.map(({ value, label, count, Icon }) => {
        const active = workspaceView === value || value === 'raw' && workspaceView === 'pipeline';
        return <Button key={value} variant={active ? "brand" : "ghost"} aria-current={active ? 'page' : undefined} onClick={() => onWorkspaceChange(value)} className={`min-h-11 justify-center gap-2 rounded-none border-b-2 ${active ? 'border-primary shadow-none hover:scale-100' : 'border-transparent text-muted-foreground'}`}>
          <Icon className="h-4 w-4 shrink-0" aria-hidden="true" /><span>{label}</span><span className="min-w-[3ch] shrink-0 rounded bg-muted px-1.5 text-center text-xs text-foreground tabular-nums">{count}</span>
        </Button>;
      })}
    </nav>}
  </>;
}
