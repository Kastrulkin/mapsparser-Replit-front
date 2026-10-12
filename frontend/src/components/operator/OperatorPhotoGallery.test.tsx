import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { vi, test, expect, afterEach } from 'vitest';
import { OperatorPhotoGallery } from './OperatorPhotoGallery';
import { API_URL } from '@/config/api';

vi.mock('@/lib/auth_new', () => ({ newAuth: { getToken: () => 'test-token' } }));
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

test('renders authenticated photo previews and enlarges without changing the post', async () => {
  const revoke = vi.fn();
  vi.stubGlobal('URL', { createObjectURL:vi.fn(() => 'blob:photo'), revokeObjectURL:revoke });
  const blob = new Blob(['image'], { type:'image/jpeg' });
  const fetchPhoto = vi.fn().mockResolvedValue({ ok:true, blob:async () => blob });
  vi.stubGlobal('fetch', fetchPhoto);
  const view = render(<OperatorPhotoGallery photos={[{ asset_id:'photo-1', name:'hair.jpg' }]} />);
  await waitFor(() => expect(screen.getByAltText('1. hair.jpg')).toHaveAttribute('src','blob:photo'));
  expect(fetchPhoto).toHaveBeenCalledWith(`${API_URL}/api/media-intelligence/photos/photo-1/file?variant=preview`, expect.objectContaining({ headers:{ Authorization:'Bearer test-token' } }));
  expect(URL.createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
  fireEvent.click(screen.getByRole('button',{ name:'Открыть фото: hair.jpg' }));
  expect(screen.getByRole('dialog')).toHaveAccessibleName('1. hair.jpg');
  expect(screen.getByAltText('Увеличенное фото: hair.jpg')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name:'Закрыть фото' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  fireEvent.click(screen.getByRole('button', { name:'Открыть фото: hair.jpg' }));
  fireEvent.keyDown(screen.getByRole('dialog'), { key:'Escape', code:'Escape' });
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  view.unmount();
  expect(revoke).toHaveBeenCalledWith('blob:photo');
});

test('shows an explicit failure instead of a broken image', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('forbidden', { status:403 })));
  render(<OperatorPhotoGallery photos={[{ asset_id:'denied', name:'private.jpg' }]} />);
  await waitFor(() => expect(screen.getByText('Не удалось загрузить фото')).toHaveAttribute('role', 'status'));
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
});

test('browses the whole result in pages without loading all images at once', async () => {
  const fetchPhoto = vi.fn().mockResolvedValue({ ok:true, blob:async () => new Blob(['image']) });
  vi.stubGlobal('fetch', fetchPhoto);
  vi.stubGlobal('URL', { createObjectURL:vi.fn(() => 'blob:photo'), revokeObjectURL:vi.fn() });
  const photos = Array.from({ length:120 }, (_, index) => ({ asset_id:`photo-${index}`, name:`photo-${index}.jpg` }));
  render(<OperatorPhotoGallery photos={photos} />);
  await waitFor(() => expect(screen.getAllByRole('img')).toHaveLength(9));
  expect(fetchPhoto).toHaveBeenCalledTimes(9);
  expect(screen.getByText('Фото 1–9 из 120')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name:'Следующие фото' }));
  await waitFor(() => expect(screen.getByAltText('10. photo-9.jpg')).toBeInTheDocument());
  expect(screen.getByText('Фото 10–18 из 120')).toBeInTheDocument();
});
