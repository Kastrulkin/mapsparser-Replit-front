import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ContentHandoffProgram, HandoffPhotoPreview } from './ContentHandoffProgram';
import { api } from '@/services/api';

vi.mock('@/lib/auth_new', () => ({ newAuth: { getToken: () => 'test-only-token' } }));
vi.mock('@/services/api', () => ({ api: { post: vi.fn() } }));

describe('restored handoff approval', () => {
  it('requires a fresh preview after reopening a ready candidate', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: { snapshot: { id: 'snapshot', input: { posts: [] } } } })
      .mockResolvedValueOnce({ data: { preview: { status: 'passed', fixture_digest: 'fixtures', delivery_context: { digest: 'context', recipient_name: 'Owner' } } } });
    render(<ContentHandoffProgram blueprintId="pilot" details={{ versions: [], runs: [], candidate_version: { id: 'version', compiled_state: 'ready_approval' } }} onRunQueued={vi.fn()} />);
    expect(screen.queryByRole('button', { name: 'Утвердить программу и условия передачи' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Проверить на текущем плане без отправки' }));
    expect(await screen.findByRole('button', { name: 'Утвердить программу и условия передачи' })).toBeEnabled();
    expect(api.post).toHaveBeenCalledTimes(2);
    expect(vi.mocked(api.post).mock.calls.every(([url]) => !url.endsWith('/approve') && !url.endsWith('/run'))).toBe(true);
  });
});

describe('handoff photo preview', () => {
  afterEach(() => vi.unstubAllGlobals());
  it('shows the selected photo through the authenticated media route', async () => {
    const fetchImage = vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(['photo']) });
    vi.stubGlobal('fetch', fetchImage);
    const create = vi.fn().mockReturnValue('blob:test-photo');
    const revoke = vi.fn();
    vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: revoke });
    const view = render(<HandoffPhotoPreview assetId="asset-1" />);
    expect(await screen.findByRole('img')).toHaveAttribute('src', 'blob:test-photo');
    expect(fetchImage.mock.calls[0][0]).toContain('/api/media-intelligence/photos/asset-1/file');
    expect(fetchImage.mock.calls[0][1].headers.Authorization).toBe('Bearer test-only-token');
    view.unmount();
    expect(revoke).toHaveBeenCalledWith('blob:test-photo');
  });
  it('shows an unavailable-photo warning instead of a broken image', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
    render(<HandoffPhotoPreview assetId="unavailable" />);
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Не удалось загрузить выбранное фото'));
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
});
