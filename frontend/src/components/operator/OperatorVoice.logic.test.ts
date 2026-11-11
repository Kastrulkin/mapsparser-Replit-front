import { afterEach, expect, it, vi } from 'vitest';
import { teamWorkJson } from '@/lib/teamWorkRequest';
import { waitForOperatorResult } from './OperatorVoice.logic';

vi.mock('@/lib/teamWorkRequest', () => ({ teamWorkJson: vi.fn() }));
afterEach(() => vi.clearAllMocks());

it('reports failed inbox checks without content-plan copy or private worker errors', async () => {
  vi.mocked(teamWorkJson).mockResolvedValue({ response: new Response('{}'), body: { job: { kind: 'outreach_inbox_sync', status: 'failed', error: 'private provider credentials' } } });
  const result = await waitForOperatorResult({ async_job_id: 'sync-1' }, 'localos', () => ({}), () => true);
  expect(result).toMatchObject({ status: 'failed', chat_response: 'Не удалось завершить проверку входящих. Сохранённые ответы доступны в «Партнёрствах».' });
  expect(JSON.stringify(result)).not.toContain('private provider credentials');
});
