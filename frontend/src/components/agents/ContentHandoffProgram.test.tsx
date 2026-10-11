import { describe, expect, it } from 'vitest';
import { hasContentHandoff } from './ContentHandoffProgram';

describe('content handoff entry in existing automation screen', () => {
  it('shows content-specific review for the current candidate', () => {
    expect(hasContentHandoff({ versions: [], runs: [], candidate_version: {
      steps_json: [{ capability: 'content.publish_handoff' }],
    } })).toBe(true);
  });
  it('does not replace another automation with a stale active handoff', () => {
    expect(hasContentHandoff({ versions: [], runs: [], candidate_version: {
      steps_json: [{ capability: 'business.summary' }],
    }, active_version: { steps_json: [{ capability: 'content.publish_handoff' }] } })).toBe(false);
    expect(hasContentHandoff(null)).toBe(false);
  });
});
