import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ContentHandoffProgram, hasContentHandoff } from './ContentHandoffProgram';

vi.mock('@/services/api', () => ({ api: { get: vi.fn(async () => ({ data: { plans: [] } })), post: vi.fn() } }));

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
  it('keeps a no-send preview available after approval without enabling delivery', () => {
    render(<ContentHandoffProgram blueprintId="pilot" details={{ versions: [], runs: [], candidate_version: {
      id: 'v5', compiled_state: 'approved', steps_json: [{ capability: 'content.publish_handoff' }],
    }, compiled_access: { execute: false } }} onRunQueued={() => undefined} />);
    expect(screen.getByRole('button', { name: 'Проверить на текущем плане без отправки' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Передать готовые материалы — тест' })).toBeDisabled();
  });
});
