import { describe, expect, it } from 'vitest';
import { GUIDED_TOUR_STEPS, GUIDED_TOUR_VERSION } from './tourConfig';
import { normalizeTourProgress } from './tourProgress';

describe('progress belongs to the actual demo version', () => {
  it.each([null, {}, { tour_version: 5, status: 'completed', step_key: 'finish' }, { tour_version: 6, status: 'paused', step_key: 'geo-promotion' }])('starts the revised demo for old or absent progress %j', value => {
    expect(normalizeTourProgress(value, GUIDED_TOUR_STEPS)).toMatchObject({ status: 'not_started', step_key: 'welcome', completed_steps: [] });
  });
  it('resumes a current paused step, removes obsolete keys and duplicates', () => {
    expect(normalizeTourProgress({ tour_version: GUIDED_TOUR_VERSION, status: 'paused', step_key: 'influencers-nav', completed_steps: ['welcome', 'welcome', 'geo-promotion'] }, GUIDED_TOUR_STEPS)).toMatchObject({ status: 'paused', step_key: 'influencers-nav', completed_steps: ['welcome'] });
  });
  it('ignores an unknown current step or corrupt status', () => {
    for (const value of [
      { tour_version: GUIDED_TOUR_VERSION, status: 'completed', step_key: 'obsolete' },
      { tour_version: GUIDED_TOUR_VERSION, status: 'unexpected', step_key: 'finish' },
    ]) expect(normalizeTourProgress(value, GUIDED_TOUR_STEPS).status).toBe('not_started');
  });
});
