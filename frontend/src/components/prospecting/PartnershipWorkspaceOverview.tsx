import {
	DashboardActionPanel,
	DashboardCompactMetricsRow,
	DashboardPageHeader,
} from '@/components/dashboard/DashboardPrimitives';
import { ProspectingWorkspaceTabs } from '@/components/prospecting/ProspectingWorkspaceChrome';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { getPartnershipWorkspaceCopy } from '@/i18n/partnershipWorkspaceCopy';

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
  const { language } = useLanguage();
  const copy = getPartnershipWorkspaceCopy(language);
  const workspaceLabelByValue: Record<string, string> = {
    overview: copy.overview,
    raw: copy.candidates,
    pipeline: copy.pipeline,
    drafts: copy.drafts,
    queue: copy.sending,
    sent: copy.replies,
    analytics: copy.report,
  };

  return (
    <>
      <DashboardPageHeader
        eyebrow="LocalOS"
        title={language === 'ru' ? 'Партнёрства' : copy.title}
        description={language === 'ru' ? 'Найдите компании, подготовьте письма, согласуйте отправку и работайте с ответами.' : copy.description}
      />

      <div className="rounded-3xl border border-slate-200/80 bg-white/92 p-3 shadow-sm">
        <ProspectingWorkspaceTabs
          activeWorkspace={workspaceView === 'pipeline' ? 'raw' : workspaceView}
          onWorkspaceChange={onWorkspaceChange}
          workspaces={[
            { value: 'overview', label: copy.overview },
            { value: 'raw', label: language === 'ru' ? 'Компании' : 'Companies', count: rawLeadCount + pipelineLeadCount },
            { value: 'drafts', label: language === 'ru' ? 'Письма' : copy.drafts, count: visibleDraftsCount },
            { value: 'queue', label: copy.sending, count: visibleBatchesCount },
            { value: 'sent', label: copy.replies, count: visibleReactionsCount },
            { value: 'analytics', label: copy.report },
          ]}
        />
      </div>
    </>
  );
}
