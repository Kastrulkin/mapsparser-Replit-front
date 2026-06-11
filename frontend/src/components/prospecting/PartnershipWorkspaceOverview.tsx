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
  overview: 'обзор кампании',
  raw: 'кандидаты',
  pipeline: 'отбор',
  drafts: 'письма',
  queue: 'отправка',
  sent: 'ответы',
  analytics: 'отчёт',
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
        title="Партнёрская кампания"
        description="Один рабочий объект для поиска партнёров: кандидаты, отбор, письма, ручная отправка, ответы и отчётность разделены по вкладкам."
      />

      <DashboardCompactMetricsRow
        items={[
          { label: 'Кандидаты', value: rawLeadCount, hint: 'Найденные компании, которые ещё не взяли в работу.' },
          { label: 'В отборе', value: pipelineLeadCount, hint: 'Партнёры, с которыми уже работаем.' },
          { label: 'Письма', value: visibleDraftsCount, hint: 'Первые письма и КП, которые ждут проверки.' },
          { label: 'Очередь', value: visibleBatchesCount, hint: 'Письма, подготовленные к ручной отправке.' },
          { label: 'Ответы', value: visibleReactionsCount, hint: 'Зафиксированные реакции партнёров.' },
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
            { value: 'overview', label: 'Обзор' },
            { value: 'raw', label: 'Кандидаты', count: rawLeadCount },
            { value: 'pipeline', label: 'Отбор', count: pipelineLeadCount },
            { value: 'drafts', label: 'Письма', count: visibleDraftsCount },
            { value: 'queue', label: 'Отправка', count: visibleBatchesCount },
            { value: 'sent', label: 'Ответы', count: visibleReactionsCount },
            { value: 'analytics', label: 'Отчёт' },
          ]}
        />
      </div>
    </>
  );
}
