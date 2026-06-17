import { ReactNode } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { LayoutGrid, List, Plus, Search, SlidersHorizontal } from 'lucide-react';

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
      <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-2">
        {workspaces.map((workspace) => {
          const isActive = activeWorkspace === workspace.value;
          return (
            <button
              key={workspace.value}
              type="button"
              onClick={() => onWorkspaceChange(workspace.value)}
              className={[
                'min-h-[56px] rounded-2xl border px-5 py-3 text-left transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50',
                isActive
                  ? 'border-primary/20 bg-primary text-primary-foreground shadow-md'
                  : 'border-border/60 bg-background text-foreground hover:border-border hover:bg-muted/40',
              ].join(' ')}
              aria-pressed={isActive}
            >
              <div className="flex min-w-0 flex-wrap items-baseline gap-2">
                <span className="min-w-0 text-lg font-semibold leading-tight">{workspace.label}</span>
                {workspace.count !== undefined ? (
                  <span className={isActive ? 'shrink-0 text-sm font-medium text-primary-foreground/85' : 'shrink-0 text-sm font-medium text-muted-foreground'}>
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
  search: string;
  onSearchChange: (value: string) => void;
  onOpenFilters: () => void;
  onOpenIntake: () => void;
  pipelineView: 'kanban' | 'list';
  onPipelineViewChange: (value: 'kanban' | 'list') => void;
  quickFilter: 'all' | 'needs_contact' | 'ready_room' | 'room_ready' | 'contacted' | 'replied';
  onQuickFilterChange: (value: 'all' | 'needs_contact' | 'ready_room' | 'room_ready' | 'contacted' | 'replied') => void;
  onResetFilters: () => void;
};

type ProspectingIntakePanelProps = {
  title: string;
  description: string;
  badges?: Array<{ label: string; value: string | number }>;
  children: ReactNode;
};

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
  search,
  onSearchChange,
  onOpenFilters,
  onOpenIntake,
  pipelineView,
  onPipelineViewChange,
  quickFilter,
  onQuickFilterChange,
  onResetFilters,
}: ProspectingPipelineHeaderProps) {
  return (
    <Card className="border-border/70 shadow-sm">
      <CardHeader className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <CardTitle>Лиды</CardTitle>
            <CardDescription>
              Кто требует действия сейчас и что сделать следующим.
            </CardDescription>
          </div>
          <Badge variant="outline">Всего лидов: {totalLeads}</Badge>
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
          <Button size="sm" variant={quickFilter === 'needs_contact' ? 'secondary' : 'outline'} onClick={() => onQuickFilterChange('needs_contact')}>Нужен контакт</Button>
          <Button size="sm" variant={quickFilter === 'ready_room' ? 'secondary' : 'outline'} onClick={() => onQuickFilterChange('ready_room')}>Готовы к комнате</Button>
          <Button size="sm" variant={quickFilter === 'room_ready' ? 'secondary' : 'outline'} onClick={() => onQuickFilterChange('room_ready')}>Комната готова</Button>
          <Button size="sm" variant={quickFilter === 'contacted' ? 'secondary' : 'outline'} onClick={() => onQuickFilterChange('contacted')}>Письмо отправлено</Button>
          <Button size="sm" variant={quickFilter === 'replied' ? 'secondary' : 'outline'} onClick={() => onQuickFilterChange('replied')}>Ответили</Button>
          <Button size="sm" variant="ghost" onClick={onResetFilters}>Сбросить фильтры</Button>
        </div>
      </CardContent>
    </Card>
  );
}
