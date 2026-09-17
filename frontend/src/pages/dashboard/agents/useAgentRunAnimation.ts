import { useCallback, useEffect, useState } from 'react';
import { workflowStepsForAnimation } from './model';
import { waitForPollInterval } from './run-polling';
import type { AgentBlueprintDetails, AgentRun, AgentRunAnimation } from './types';

export function useAgentRunAnimation(blueprintDetails: AgentBlueprintDetails | null) {
  const [runAnimation, setRunAnimation] = useState<AgentRunAnimation | null>(null);
  const runAnimationBlueprintId = runAnimation?.blueprintId;
  const runAnimationStartedAt = runAnimation?.startedAt;
  const runAnimationStatus = runAnimation?.status;
  useEffect(() => {
    if (runAnimationStatus !== 'running') {
      return;
    }
    const timer = window.setInterval(() => {
      setRunAnimation((current) => {
        if (!current || current.status !== 'running') {
          return current;
        }
        const total = Math.max(current.steps.length, 1);
        const completed = Math.max(0, current.serverCompletedSteps || 0);
        const cap = current.queueState === 'queued'
          ? 12
          : Math.min(92, Math.round(((completed + 0.85) / total) * 92));
        const progress = Math.min(cap, current.progress + 3);
        return { ...current, progress, stepIndex: Math.min(total - 1, current.serverCurrentStepIndex ?? completed) };
      });
    }, 500);
    return () => window.clearInterval(timer);
  }, [runAnimationBlueprintId, runAnimationStartedAt, runAnimationStatus]);

  const beginRunAnimation = (blueprintId: string, kind: AgentRunAnimation['kind']) => {
    const animation: AgentRunAnimation = {
      kind,
      blueprintId,
      startedAt: Date.now(),
      progress: 8,
      stepIndex: 0,
      steps: workflowStepsForAnimation(blueprintDetails, kind),
      status: 'running',
      serverCompletedSteps: 0,
      serverCurrentStepIndex: 0,
      queueState: 'queued',
    };
    setRunAnimation(animation);
    return animation.startedAt;
  };

  const finishRunAnimation = useCallback(async (startedAt: number, signal?: AbortSignal) => {
    const waitMs = Math.max(0, 6500 - (Date.now() - startedAt));
    if (waitMs > 0) {
      await waitForPollInterval(waitMs, signal);
    }
    signal?.throwIfAborted();
    setRunAnimation((current) => current?.startedAt === startedAt ? {
      ...current,
      progress: 100,
      stepIndex: Math.max(0, current.steps.length - 1),
      status: 'finishing',
    } : current);
    await waitForPollInterval(360, signal);
  }, []);

  const failRunAnimation = useCallback((message: string) => {
    setRunAnimation((current) => current ? { ...current, status: 'error', error: message } : current);
  }, []);

  const syncRunAnimation = useCallback((run: AgentRun | null) => {
    if (!run) return;
    setRunAnimation((current) => {
      if (!current || current.blueprintId !== run.blueprint_id) return current;
      const total = Math.max(current.steps.length, Number(run.progress?.total_steps || 0), 1);
      const completed = Math.min(total, Math.max(0, Number(run.progress?.completed_steps || 0)));
      const currentIndex = Math.min(total - 1, Math.max(0, Number(run.progress?.current_step_index ?? completed)));
      const floor = Math.min(92, Math.round((completed / total) * 92));
      return {
        ...current,
        runId: run.id,
        queueState: String(run.progress?.state || run.status || 'queued'),
        serverCompletedSteps: completed,
        serverCurrentStepIndex: currentIndex,
        stepIndex: currentIndex,
        progress: Math.max(current.progress, floor),
      };
    });
  }, []);

  return { runAnimation, setRunAnimation, beginRunAnimation, finishRunAnimation, failRunAnimation, syncRunAnimation };
}
