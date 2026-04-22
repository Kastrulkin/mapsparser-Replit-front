import { ReactNode } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Check, ChevronDown, LayoutGrid, List, Plus, Search, SlidersHorizontal } from 'lucide-react';

type WorkspaceTab = {
  value: string;
  label: string;
  count?: number;
};

type OutreachTab = {
  value: string;
  label: string;
  count?: number;
};

type ProspectingWorkspaceTabsProps = {
  activeWorkspace: string;
  onWorkspaceChange: (value: string) => void;
  workspaces: WorkspaceTab[];
  outreachTabs?: OutreachTab[];
  activeOutreachTab?: string;
  onOutreachTabChange?: (value: string) => void;
};

export function ProspectingWorkspaceTabs({
  activeWorkspace,
  onWorkspaceChange,
  workspaces,
  outreachTabs = [],
  activeOutreachTab,
  onOutreachTabChange,
}: ProspectingWorkspaceTabsProps) {
  return (
    <div className="rounded-[28px] border border-border/70 bg-gradient-to-b from-background to-muted/20 p-3 shadow-sm">
      <div className="flex flex-wrap items-end gap-2">
        {workspaces.map((workspace, index) => {
          const isActive = activeWorkspace === workspace.value;
          return (
            <button
              key={workspace.value}
              type="button"
              onClick={() => onWorkspaceChange(workspace.value)}
              className={[
                'relative min-w-[148px] rounded-t-2xl rounded-b-xl border px-5 py-3 text-left transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50',
                isActive
                  ? 'border-primary/20 bg-primary text-primary-foreground shadow-md -mb-px z-10'
                  : 'border-border/60 bg-background text-foreground hover:border-border hover:bg-muted/40',
                index > 0 ? '-ml-1' : '',
              ].join(' ')}
              aria-pressed={isActive}
            >
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-lg font-semibold leading-none">{workspace.label}</span>
                {workspace.count !== undefined ? (
                  <span className={isActive ? 'text-primary-foreground/85 text-sm font-medium' : 'text-muted-foreground text-sm font-medium'}>
                    {workspace.count}
                  </span>
                ) : null}
              </div>
            </button>
          );
        })}
      </div>
      {activeWorkspace === 'outreach' && outreachTabs.length > 0 ? (
        <div className="mt-3 rounded-2xl border border-primary/15 bg-primary/5 px-3 py-3">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">Меню аутрича</div>
          <div className="flex flex-wrap items-center gap-2">
            {outreachTabs.map((tab) => {
              const isActive = activeOutreachTab === tab.value;
              return (
                <Button
                  key={tab.value}
                  size="sm"
                  variant={isActive ? 'default' : 'ghost'}
                  className={isActive ? 'shadow-sm' : 'bg-background/60 hover:bg-background'}
                  onClick={() => onOutreachTabChange?.(tab.value)}
                >
                  {tab.label}
                  {tab.count !== undefined ? ` (${tab.count})` : ''}
                </Button>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}

type ProspectingPipelineHeaderProps = {
  totalLeads: number;
  summary: {
    withoutAudit: number;
    withAudit: number;
    readyToContact: number;
  };
  search: string;
  onSearchChange: (value: string) => void;
  filters: {
    source: string;
    hasTelegram: string;
    hasWhatsApp: string;
    hasMax: string;
    hasEmail: string;
    hasWebsite: string;
    hasVk: string;
  };
  onSourceChange: (value: string) => void;
  onHasTelegramChange: (value: string) => void;
  onHasWhatsAppChange: (value: string) => void;
  onHasMaxChange: (value: string) => void;
  onHasEmailChange: (value: string) => void;
  onHasWebsiteChange: (value: string) => void;
  onHasVkChange: (value: string) => void;
  onOpenFilters: () => void;
  onOpenIntake: () => void;
  pipelineView: 'kanban' | 'list';
  onPipelineViewChange: (value: 'kanban' | 'list') => void;
  quickFilter: 'all' | 'without_audit' | 'with_audit' | 'priority';
  onQuickFilterChange: (value: 'all' | 'without_audit' | 'with_audit' | 'priority') => void;
  onResetFilters: () => void;
  onApplyBestPreset: () => void;
  onApplyManyReviewsPreset: () => void;
};

type ProspectingIntakePanelProps = {
  title: string;
  description: string;
  badges?: Array<{ label: string; value: string | number }>;
  children: ReactNode;
};

type TriStateFilterOption = {
  value: string;
  label: string;
};

const triStateFilterOptions = (label: string): TriStateFilterOption[] => [
  { value: '', label: `${label}: любой` },
  { value: 'yes', label: `Есть ${label}` },
  { value: 'no', label: `Нет ${label}` },
];

const triStateFilterLabel = (label: string, value: string) => {
  if (value === 'yes') {
    return `${label}: есть`;
  }
  if (value === 'no') {
    return `${label}: нет`;
  }
  return `${label}: любой`;
};

function InlineFilterMenu({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className="h-10 min-w-[180px] justify-between font-normal">
          <span>{triStateFilterLabel(label, value)}</span>
          <ChevronDown className="ml-2 h-4 w-4 shrink-0 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="min-w-[220px]">
        {triStateFilterOptions(label).map((option) => {
          const checked = option.value === value;
          return (
            <DropdownMenuItem
              key={`${label}-${option.value || 'any'}`}
              onSelect={() => onChange(option.value)}
              className="gap-2"
            >
              <span className="flex h-4 w-4 items-center justify-center rounded-sm border border-border bg-background">
                {checked ? <Check className="h-3 w-3" /> : null}
              </span>
              <span>{option.label}</span>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function ProspectingIntakePanel({
  title,
  description,
  badges = [],
  children,
}: ProspectingIntakePanelProps) {
  return (
    <Card className="border-border/70 shadow-sm">
      <CardHeader className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <CardTitle>{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </div>
          {badges.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {badges.map((badge) => (
                <Badge key={badge.label} variant="outline">
                  {badge.label}: {badge.value}
                </Badge>
              ))}
            </div>
          ) : null}
        </div>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export function ProspectingPipelineHeader({
  totalLeads,
  summary,
  search,
  onSearchChange,
  filters,
  onSourceChange,
  onHasTelegramChange,
  onHasWhatsAppChange,
  onHasMaxChange,
  onHasEmailChange,
  onHasWebsiteChange,
  onHasVkChange,
  onOpenFilters,
  onOpenIntake,
  pipelineView,
  onPipelineViewChange,
  quickFilter,
  onQuickFilterChange,
  onResetFilters,
  onApplyBestPreset,
  onApplyManyReviewsPreset,
}: ProspectingPipelineHeaderProps) {
  return (
    <Card className="border-border/70 shadow-sm">
      <CardHeader className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <CardTitle>Воронка</CardTitle>
            <CardDescription>
              Один рабочий экран для лидов: intake живёт отдельно, а здесь только движение по воронке.
            </CardDescription>
          </div>
          <Badge variant="outline">Всего лидов: {totalLeads}</Badge>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary">Без аудита: {summary.withoutAudit}</Badge>
          <Badge variant="secondary">С аудитом: {summary.withAudit}</Badge>
          <Badge variant="secondary">Готово к контакту: {summary.readyToContact}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[240px] flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Поиск по названию, адресу, контактам"
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
            />
          </div>
          <select
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            value={filters.source}
            onChange={(event) => onSourceChange(event.target.value)}
          >
            <option value="">Источник: любой</option>
            <option value="apify_yandex">Apify Yandex</option>
            <option value="apify_2gis">Apify 2GIS</option>
            <option value="apify_google">Apify Google</option>
            <option value="apify_apple">Apify Apple</option>
            <option value="manual">Ручной ввод</option>
            <option value="external_import">Внешний импорт</option>
            <option value="openclaw">OpenClaw</option>
          </select>
          <InlineFilterMenu label="Telegram" value={filters.hasTelegram} onChange={onHasTelegramChange} />
          <InlineFilterMenu label="WhatsApp" value={filters.hasWhatsApp} onChange={onHasWhatsAppChange} />
          <InlineFilterMenu label="Max" value={filters.hasMax} onChange={onHasMaxChange} />
          <InlineFilterMenu label="Email" value={filters.hasEmail} onChange={onHasEmailChange} />
          <InlineFilterMenu label="Сайт" value={filters.hasWebsite} onChange={onHasWebsiteChange} />
          <InlineFilterMenu label="VK" value={filters.hasVk} onChange={onHasVkChange} />
          <Button variant="outline" onClick={onOpenFilters}>
            <SlidersHorizontal className="mr-2 h-4 w-4" />
            Фильтры
          </Button>
          <Button variant="outline" onClick={onOpenIntake}>
            <Plus className="mr-2 h-4 w-4" />
            Добавить лиды
          </Button>
          <div className="ml-auto flex items-center gap-2 rounded-lg border border-border p-1">
            <Button size="sm" variant={pipelineView === 'kanban' ? 'secondary' : 'ghost'} onClick={() => onPipelineViewChange('kanban')}>
              <LayoutGrid className="mr-2 h-4 w-4" />
              Kanban
            </Button>
            <Button size="sm" variant={pipelineView === 'list' ? 'secondary' : 'ghost'} onClick={() => onPipelineViewChange('list')}>
              <List className="mr-2 h-4 w-4" />
              Список
            </Button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant={quickFilter === 'all' ? 'secondary' : 'outline'} onClick={() => onQuickFilterChange('all')}>Все</Button>
          <Button size="sm" variant={quickFilter === 'without_audit' ? 'secondary' : 'outline'} onClick={() => onQuickFilterChange('without_audit')}>Без аудита</Button>
          <Button size="sm" variant={quickFilter === 'with_audit' ? 'secondary' : 'outline'} onClick={() => onQuickFilterChange('with_audit')}>С аудитом</Button>
          <Button size="sm" variant={quickFilter === 'priority' ? 'secondary' : 'outline'} onClick={() => onQuickFilterChange('priority')}>Приоритетные</Button>
          <Button size="sm" variant="ghost" onClick={onResetFilters}>Сбросить фильтры</Button>
          <Button size="sm" variant="ghost" onClick={onApplyBestPreset}>Лучшие лиды</Button>
          <Button size="sm" variant="ghost" onClick={onApplyManyReviewsPreset}>Много отзывов</Button>
        </div>
      </CardContent>
    </Card>
  );
}
