import { GUIDED_TOUR_VERSION, type GuidedTourStep } from './tourConfig';

export type TourStatus = 'not_started' | 'active' | 'paused' | 'skipped' | 'completed';
export type TourProgress = {
  tour_version?: number;
  status: TourStatus;
  chapter_key?: string | null;
  step_key?: string | null;
  completed_steps?: string[];
  updated_at?: string | null;
};
const statuses: TourStatus[] = ['not_started', 'active', 'paused', 'skipped', 'completed'];
const isStatus = (value: unknown): value is TourStatus => statuses.some(status => status === value);

export function normalizeTourProgress(value: unknown, steps: GuidedTourStep[]): TourProgress {
  const fresh: TourProgress = { tour_version: GUIDED_TOUR_VERSION, status: 'not_started', step_key: steps[0]?.key, completed_steps: [] };
  if (!value || typeof value !== 'object' || !('tour_version' in value) || value.tour_version !== GUIDED_TOUR_VERSION) return fresh;
  if (!('status' in value) || !isStatus(value.status)) return fresh;
  const step = 'step_key' in value ? steps.find(item => item.key === value.step_key) : undefined;
  if (!step) return fresh;
  const rawCompleted = 'completed_steps' in value && Array.isArray(value.completed_steps) ? value.completed_steps : [];
  const completed = steps.filter(item => rawCompleted.includes(item.key)).map(item => item.key);
  return {
    tour_version: GUIDED_TOUR_VERSION,
    status: value.status,
    step_key: step.key,
    chapter_key: step.chapter,
    completed_steps: completed,
    updated_at: 'updated_at' in value && typeof value.updated_at === 'string' ? value.updated_at : null,
  };
}
