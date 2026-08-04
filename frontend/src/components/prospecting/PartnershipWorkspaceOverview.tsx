import { ProspectingWorkspaceTabs } from '@/components/prospecting/ProspectingWorkspaceChrome';
import {
  DashboardActionPanel,
  DashboardCompactMetricsRow,
  DashboardPageHeader,
} from '@/components/dashboard/DashboardPrimitives';
import { useLanguage } from '@/i18n/LanguageContext';
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
        title={copy.title}
        description={copy.description}
      />

      <DashboardCompactMetricsRow
        items={[
          { label: copy.candidates, value: rawLeadCount, hint: copy.candidatesHint },
          { label: copy.pipeline, value: pipelineLeadCount, hint: copy.pipelineHint },
          { label: copy.drafts, value: visibleDraftsCount, hint: copy.draftsHint },
          { label: copy.queue, value: visibleBatchesCount, hint: copy.queueHint },
          { label: copy.replies, value: visibleReactionsCount, hint: copy.repliesHint },
        ]}
      />

      <DashboardActionPanel
        title={copy.nextStep}
        description={copy.nextStepDescription}
        status={!currentBusinessId ? copy.selectBusiness : `${copy.currentLayer}: ${workspaceLabelByValue[workspaceView] || copy.workspace}.`}
        tone={!currentBusinessId ? 'amber' : 'default'}
      />

      <div className="rounded-3xl border border-slate-200/80 bg-white/92 p-3 shadow-sm">
        <ProspectingWorkspaceTabs
          activeWorkspace={workspaceView}
          onWorkspaceChange={onWorkspaceChange}
          workspaces={[
            { value: 'overview', label: copy.overview },
            { value: 'raw', label: copy.candidates, count: rawLeadCount },
            { value: 'pipeline', label: copy.pipeline, count: pipelineLeadCount },
            { value: 'drafts', label: copy.drafts, count: visibleDraftsCount },
            { value: 'queue', label: copy.sending, count: visibleBatchesCount },
            { value: 'sent', label: copy.replies, count: visibleReactionsCount },
            { value: 'analytics', label: copy.report },
          ]}
        />
      </div>
    </>
  );
}
