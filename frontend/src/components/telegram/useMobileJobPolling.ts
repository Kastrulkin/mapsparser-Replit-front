import { usePolling } from '@/hooks/usePolling';
import { loadMobileJob, type MobileJob, type MobileScopeRef } from '@/lib/mobileDataClient';

export function useMobileJobPolling({ job, scope, onJob, onComplete, intervalMs = 3000 }: {
  job: MobileJob | null;
  scope?: MobileScopeRef;
  onJob: (job: MobileJob | null) => void;
  onComplete: (job: MobileJob) => void;
  intervalMs?: number;
}) {
  usePolling({
    enabled: Boolean(job?.id && !job.terminal),
    scopeKey: `${scope?.kind || ''}:${scope?.id || ''}:${job?.id || ''}`,
    intervalMs,
    request: (signal) => loadMobileJob(job?.id || '', scope, signal),
    onResult: (result) => {
      onJob(result.job || null);
      if (result.job?.terminal) onComplete(result.job);
    },
  });
}
