import { api } from '@/services/api';
import { useCallback, useEffect, type Dispatch, type MutableRefObject, type SetStateAction } from 'react';
import { workflowStepsForAnimation } from './model';
import { getRequestErrorMessage } from './normalization';
import { isAgentWorkRun } from './results';
import { pollAgentRun } from './run-polling';
import { clearAgentRunResume, isWaitingForProviderResult, readAgentRunResume, shouldContinueAgentRunPolling } from './run-resume';
import type { AgentBlueprint, AgentBlueprintDetails, AgentRun, AgentRunAnimation, AgentWorkspaceMode } from './types';

type RunTarget = { blueprintId: string; runId: string } | null;
type RunTrackingOptions = {
  currentBusinessId: string;
  blueprints: AgentBlueprint[];
  blueprintDetails: AgentBlueprintDetails | null;
  selectedBlueprint: AgentBlueprint | null;
  runAnimation: AgentRunAnimation | null;
  compiledRunContext: RunTarget;
  explicitRunTarget: RunTarget;
  requestedDeepLinkRef: MutableRefObject<string>;
  setSelectedBlueprintId: Dispatch<SetStateAction<string>>;
  setRunAnimation: Dispatch<SetStateAction<AgentRunAnimation | null>>;
  setActiveRun: Dispatch<SetStateAction<AgentRun | null>>;
  setWorkspaceMode: Dispatch<SetStateAction<AgentWorkspaceMode>>;
  setError: Dispatch<SetStateAction<string | null>>;
  syncRunAnimation: (run: AgentRun | null) => void;
  finishRunAnimation: (startedAt: number, signal?: AbortSignal) => Promise<void>;
  failRunAnimation: (message: string) => void;
  loadBlueprintDetails: (id: string) => Promise<void>;
  loadBlueprintReview: (id: string) => Promise<void>;
  loadBlueprints: () => Promise<void>;
};

/** Restore interrupted runs and track compiled/recovered results within the current scope. */
export function useAgentRunTracking({ currentBusinessId, blueprints, blueprintDetails, selectedBlueprint, runAnimation, compiledRunContext, explicitRunTarget,
  requestedDeepLinkRef, setSelectedBlueprintId, setRunAnimation, setActiveRun, setWorkspaceMode, setError,
  syncRunAnimation, finishRunAnimation, failRunAnimation, loadBlueprintDetails, loadBlueprintReview, loadBlueprints }: RunTrackingOptions) {
  useEffect(() => {
    if (!currentBusinessId || !blueprints.length || runAnimation || requestedDeepLinkRef.current.includes(':')) return;
    const resume = readAgentRunResume(currentBusinessId);
    if (!resume) return;
    const resumeBlueprintExists = blueprints.some((blueprint) => blueprint.id === resume.blueprintId);
    if (!resumeBlueprintExists) {
      clearAgentRunResume(currentBusinessId, resume.runId);
      return;
    }
    if (selectedBlueprint?.id !== resume.blueprintId) {
      setSelectedBlueprintId(resume.blueprintId);
      return;
    }
    let cancelled = false;
    void api.get(`/agent-runs/${resume.runId}`).then((response) => {
      if (cancelled) return;
      const run: AgentRun | null = response.data?.run && typeof response.data.run === 'object' ? response.data.run : null;
      if (!run || run.blueprint_id !== resume.blueprintId) {
        clearAgentRunResume(currentBusinessId, resume.runId);
        return;
      }
      setActiveRun(run);
      if (!shouldContinueAgentRunPolling(run)) {
        setWorkspaceMode('results');
        if (!isWaitingForProviderResult(run)) {
          clearAgentRunResume(currentBusinessId, resume.runId);
        }
        return;
      }
      const steps = workflowStepsForAnimation(blueprintDetails, resume.kind);
      const total = Math.max(steps.length, Number(run.progress?.total_steps || 0), 1);
      const completed = Math.min(total, Math.max(0, Number(run.progress?.completed_steps || 0)));
      const currentIndex = Math.min(total - 1, Math.max(0, Number(run.progress?.current_step_index ?? completed)));
      setRunAnimation({
        kind: resume.kind,
        blueprintId: resume.blueprintId,
        runId: resume.runId,
        startedAt: resume.startedAt,
        progress: Math.max(8, Math.min(92, Math.round((completed / total) * 92))),
        stepIndex: currentIndex,
        steps,
        status: 'running',
        serverCompletedSteps: completed,
        serverCurrentStepIndex: currentIndex,
        queueState: String(run.progress?.state || run.status || 'queued'),
        recoveredFromReload: true,
      });
    }).catch((requestError) => {
      if (cancelled) return;
      console.error(requestError);
      clearAgentRunResume(currentBusinessId, resume.runId);
      setError('Не удалось восстановить последнюю запущенную задачу. Результат остаётся в истории агента.');
    });
    return () => { cancelled = true; };
  }, [blueprintDetails, blueprints, currentBusinessId, runAnimation, selectedBlueprint?.id, setRunAnimation, requestedDeepLinkRef, setSelectedBlueprintId, setActiveRun, setWorkspaceMode, setError]);

  useEffect(() => {
    if (runAnimation || !selectedBlueprint?.id || explicitRunTarget?.blueprintId === selectedBlueprint.id) return;
    const inflight = (blueprintDetails?.runs || []).find((run) => ['queued', 'running', 'retry_wait', 'waiting_provider'].includes(String(run.status || '')) && shouldContinueAgentRunPolling(run));
    if (!inflight?.id) return;
    let cancelled = false;
    void api.get(`/agent-runs/${inflight.id}`).then((response) => {
      if (cancelled) return;
      const run: AgentRun | null = response.data?.run && typeof response.data.run === 'object' ? response.data.run : null;
      if (!run) return;
      const kind: AgentRunAnimation['kind'] = isAgentWorkRun(run) ? 'work' : 'test';
      const steps = workflowStepsForAnimation(blueprintDetails, kind);
      const total = Math.max(steps.length, Number(run.progress?.total_steps || 0), 1);
      const completed = Math.min(total, Math.max(0, Number(run.progress?.completed_steps || 0)));
      const currentIndex = Math.min(total - 1, Math.max(0, Number(run.progress?.current_step_index ?? completed)));
      setActiveRun(run);
      setRunAnimation({
        kind,
        blueprintId: selectedBlueprint.id,
        runId: run.id,
        startedAt: Date.parse(String(run.queued_at || run.started_at || '')) || Date.now(),
        progress: Math.max(8, Math.min(92, Math.round((completed / total) * 92))),
        stepIndex: currentIndex,
        steps,
        status: 'running',
        serverCompletedSteps: completed,
        serverCurrentStepIndex: currentIndex,
        queueState: String(run.progress?.state || run.status || 'queued'),
        recoveredFromReload: true,
      });
    }).catch((requestError) => console.error(requestError));
    return () => { cancelled = true; };
  }, [blueprintDetails, explicitRunTarget?.blueprintId, runAnimation, selectedBlueprint?.id, setRunAnimation, setActiveRun]);

  const waitForAgentRun = useCallback((runId: string, signal?: AbortSignal) => pollAgentRun(runId, {
    signal,
    onRun: (run) => { setActiveRun(run); syncRunAnimation(run); },
  }), [syncRunAnimation, setActiveRun]);

  useEffect(() => {
    if (!compiledRunContext?.runId || !selectedBlueprint?.id || compiledRunContext.blueprintId !== selectedBlueprint.id
      || (explicitRunTarget?.runId && explicitRunTarget.runId !== compiledRunContext.runId)) {
      return;
    }
    const controller = new AbortController();
    const blueprintId = compiledRunContext.blueprintId;
    void pollAgentRun(compiledRunContext.runId, {
      signal: controller.signal, expectedBlueprintId: blueprintId, onRun: setActiveRun,
    }).then(async (run) => {
      if (!run || controller.signal.aborted) return;
      setWorkspaceMode('results');
      await loadBlueprintDetails(blueprintId);
      if (!controller.signal.aborted) await loadBlueprintReview(blueprintId);
    }).catch((requestError) => {
      if (controller.signal.aborted) return;
      console.error(requestError);
      setError('Не удалось обновить состояние проверки таблицы. Попробуйте открыть запуск из истории.');
    });
    return () => controller.abort();
  }, [compiledRunContext?.blueprintId, compiledRunContext?.runId, explicitRunTarget?.runId, loadBlueprintDetails, loadBlueprintReview, selectedBlueprint?.id, setActiveRun, setWorkspaceMode, setError]);

  useEffect(() => {
    if (!runAnimation?.recoveredFromReload || !runAnimation.runId) return;
    const controller = new AbortController();
    const runId = runAnimation.runId;
    const startedAt = runAnimation.startedAt;
    void waitForAgentRun(runId, controller.signal).then(async (run) => {
      if (controller.signal.aborted) return;
      if (run?.status === 'failed') {
        failRunAnimation(run.error_text || 'Агент не смог завершить задачу.');
        return;
      }
      if (isWaitingForProviderResult(run)) {
        setRunAnimation(null);
        setWorkspaceMode('results');
        if (selectedBlueprint?.id) await loadBlueprintDetails(selectedBlueprint.id);
        await loadBlueprints();
        return;
      }
      await finishRunAnimation(startedAt, controller.signal);
      if (controller.signal.aborted) return;
      setRunAnimation(null);
      setWorkspaceMode('results');
      clearAgentRunResume(currentBusinessId, runId);
      if (selectedBlueprint?.id) await loadBlueprintDetails(selectedBlueprint.id);
      await loadBlueprints();
    }).catch((requestError) => {
      if (!controller.signal.aborted) failRunAnimation(getRequestErrorMessage(requestError, 'Не удалось продолжить отслеживание задачи.'));
    });
    return () => controller.abort();
  }, [
    currentBusinessId,
    failRunAnimation,
    finishRunAnimation,
    loadBlueprintDetails,
    loadBlueprints,
    runAnimation?.recoveredFromReload,
    runAnimation?.runId,
    runAnimation?.startedAt,
    selectedBlueprint?.id,
    waitForAgentRun,
    setRunAnimation,
    setWorkspaceMode,
  ]);

  return { waitForAgentRun };
}
