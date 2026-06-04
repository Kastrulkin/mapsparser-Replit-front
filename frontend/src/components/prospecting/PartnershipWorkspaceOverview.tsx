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
  raw: 'поиск',
  pipeline: 'отбор',
  analytics: 'аналитика',
  drafts: 'письма',
  queue: 'отправка',
  sent: 'результаты',
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
        description="Простой маршрут: найти партнёра, отобрать подходящих, подготовить письмо, отправить вручную и зафиксировать результат."
      />

      <DashboardCompactMetricsRow
        items={[
          { label: 'Найдено', value: rawLeadCount, hint: 'Все импортированные и найденные компании.' },
          { label: 'В отборе', value: pipelineLeadCount, hint: 'Партнёры, с которыми уже работаем.' },
          { label: 'Письма', value: visibleDraftsCount, hint: 'Черновики, которые ждут проверки.' },
          { label: 'Результаты', value: visibleBatchesCount + visibleReactionsCount, hint: 'Отправка и зафиксированные ответы.' },
        ]}
      />

      <DashboardActionPanel
        title="Следующий шаг"
        description="Двигайтесь слева направо: поиск → отбор → письма → ручная отправка → результат. Каждый экран показывает только действия текущего шага."
        status={!currentBusinessId ? 'Сначала выберите бизнес в переключателе сверху.' : `Сейчас открыт слой: ${workspaceLabelByValue[workspaceView] || 'рабочий экран'}.`}
        tone={!currentBusinessId ? 'amber' : 'default'}
      />

      <div className="rounded-3xl border border-slate-200/80 bg-white/92 p-3 shadow-sm">
        <ProspectingWorkspaceTabs
          activeWorkspace={workspaceView}
          onWorkspaceChange={onWorkspaceChange}
          workspaces={[
            { value: 'raw', label: 'Поиск', count: rawLeadCount },
            { value: 'pipeline', label: 'Отбор', count: pipelineLeadCount },
            { value: 'drafts', label: 'Письма', count: visibleDraftsCount },
            { value: 'queue', label: 'Отправка', count: visibleBatchesCount },
            { value: 'sent', label: 'Результаты', count: visibleReactionsCount },
            { value: 'analytics', label: 'Аналитика' },
          ]}
        />
      </div>
    </>
  );
}
