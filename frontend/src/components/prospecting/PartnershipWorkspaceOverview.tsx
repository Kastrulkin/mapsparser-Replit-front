import { ProspectingWorkspaceTabs } from '@/components/prospecting/ProspectingWorkspaceChrome';
import {
  DashboardActionPanel,
  DashboardCompactMetricsRow,
  DashboardPageHeader,
} from '@/components/dashboard/DashboardPrimitives';

type PartnershipWorkspaceOverviewProps = {
  workspaceView: string;
  currentBusinessId?: string | null;
  rawLeadCount: number;
  pipelineLeadCount: number;
  visibleDraftsCount: number;
  visibleBatchesCount: number;
  visibleReactionsCount: number;
  onWorkspaceChange: (value: string) => void;
};

const workspaceLabelByValue: Record<string, string> = {
  raw: 'поиск лидов',
  pipeline: 'воронка',
  analytics: 'аналитика',
  drafts: 'черновики',
  queue: 'отправка',
  sent: 'отправленные',
};

export function PartnershipWorkspaceOverview({
  workspaceView,
  currentBusinessId,
  rawLeadCount,
  pipelineLeadCount,
  visibleDraftsCount,
  visibleBatchesCount,
  visibleReactionsCount,
  onWorkspaceChange,
}: PartnershipWorkspaceOverviewProps) {
  return (
    <>
      <DashboardPageHeader
        eyebrow="LocalOS"
        title="Поиск партнёров"
        description="Находите бизнес-партнёров вокруг вашей точки, отбирайте релевантных и доводите их до первого контакта без хаоса в таблицах."
      />

      <DashboardCompactMetricsRow
        items={[
          { label: 'Найдено', value: rawLeadCount, hint: 'Все импортированные и найденные компании.' },
          { label: 'В воронке', value: pipelineLeadCount, hint: 'Партнёры, по которым уже есть следующий шаг.' },
          { label: 'Черновики', value: visibleDraftsCount, hint: 'Сообщения, которые ждут проверки.' },
          { label: 'Касания', value: visibleBatchesCount + visibleReactionsCount, hint: 'Очередь отправки и зафиксированные ответы.' },
        ]}
      />

      <DashboardActionPanel
        title="Следующий шаг"
        description="Начните с поиска лидов, затем перенесите подходящих партнёров в воронку. Черновики и отправка доступны отдельными слоями, чтобы не смешивать поиск, подготовку и результат."
        status={!currentBusinessId ? 'Сначала выберите бизнес в переключателе сверху.' : `Сейчас открыт слой: ${workspaceLabelByValue[workspaceView] || 'рабочий экран'}.`}
        tone={!currentBusinessId ? 'amber' : 'default'}
      />

      <div className="rounded-3xl border border-slate-200/80 bg-white/92 p-3 shadow-sm">
        <ProspectingWorkspaceTabs
          activeWorkspace={workspaceView}
          onWorkspaceChange={onWorkspaceChange}
          workspaces={[
            { value: 'raw', label: 'Поиск лидов', count: rawLeadCount },
            { value: 'pipeline', label: 'Воронка', count: pipelineLeadCount },
            { value: 'analytics', label: 'Аналитика' },
            { value: 'drafts', label: 'Черновики', count: visibleDraftsCount },
            { value: 'queue', label: 'Отправка', count: visibleBatchesCount },
            { value: 'sent', label: 'Отправлено', count: visibleReactionsCount },
          ]}
        />
      </div>
    </>
  );
}
