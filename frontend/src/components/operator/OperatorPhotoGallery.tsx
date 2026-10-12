import { useEffect, useState } from 'react';
import { newAuth } from '@/lib/auth_new';
import { API_URL } from '@/config/api';
import { Button } from '@/components/ui/button';
import { Dialog, DialogTrigger, DialogPortal, DialogOverlay, DialogClose, DialogTitle } from '@/components/ui/dialog';
import { Content } from '@radix-ui/react-dialog';
import { X } from 'lucide-react';

export type OperatorPhoto = { asset_id: string; name?: string; category?: string };

const PhotoPreview = ({ photo, index }: { photo: OperatorPhoto; index: number }) => {
  const [url, setUrl] = useState('');
  const [failed, setFailed] = useState(false);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl = '';
    setUrl('');
    setFailed(false);
    const token = newAuth.getToken();
    fetch(`${API_URL}/api/media-intelligence/photos/${encodeURIComponent(photo.asset_id)}/file?variant=preview`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      signal: controller.signal,
    }).then(async response => {
      if (!response.ok) throw new Error(`Фото недоступно (${response.status})`);
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      objectUrl = URL.createObjectURL(blob);
      setUrl(objectUrl);
    }).catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [photo.asset_id]);
  const label = `${index + 1}. ${photo.name || 'Фото без названия'}`;
  return (
    <figure className="min-w-0 space-y-2">
      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogTrigger asChild>
          <button type="button" disabled={!url} aria-label={`Открыть фото: ${photo.name || index + 1}`} className="flex aspect-square w-full items-center justify-center overflow-hidden rounded-lg bg-slate-50 ring-1 ring-slate-200 enabled:cursor-zoom-in focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            {url ? <img src={url} alt={label} className="h-full w-full object-contain" onError={() => { setUrl(''); setFailed(true); setExpanded(false); }} />
              : <span role="status" className="p-3 text-center text-xs text-slate-500">{failed ? 'Не удалось загрузить фото' : 'Загружаю фото…'}</span>}
          </button>
        </DialogTrigger>
        {url && <DialogPortal>
          <DialogOverlay />
          <Content aria-describedby={undefined} className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-6xl -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-background p-4 shadow-lg">
            <div className="mb-3 flex items-center justify-between gap-3">
              <DialogTitle className="min-w-0 break-words text-sm">{label}</DialogTitle>
              <DialogClose asChild><Button variant="outline" size="icon" className="h-11 w-11 shrink-0" aria-label="Закрыть фото"><X className="h-5 w-5" /></Button></DialogClose>
            </div>
            <img src={url} alt={`Увеличенное фото: ${photo.name || index + 1}`} className="h-[75dvh] w-full object-contain" />
          </Content>
        </DialogPortal>}
      </Dialog>
      <figcaption className="break-words text-xs text-slate-600">{label}</figcaption>
    </figure>
  );
};

export const OperatorPhotoGallery = ({ photos }: { photos: OperatorPhoto[] }) => {
  const [page, setPage] = useState(0);
  const pageSize = 9;
  const pageCount = Math.ceil(photos.length / pageSize);
  const currentPage = Math.min(page, Math.max(0, pageCount - 1));
  const start = currentPage * pageSize;
  return (
  <section aria-label="Варианты фотографий" className="space-y-3">
    <p className="text-sm text-slate-600">Посмотрите фото. Чтобы выбрать, напишите в чат его номер или название. Пока фото поста не меняется.</p>
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
      {photos.slice(start, start + pageSize).map((photo, index) => <PhotoPreview key={photo.asset_id} photo={photo} index={start + index} />)}
    </div>
    <div className="flex flex-wrap items-center gap-3">
      <span role="status" className="text-sm text-slate-600">Фото {start + 1}–{Math.min(start + pageSize, photos.length)} из {photos.length}</span>
      {pageCount > 1 && <>
        <Button variant="outline" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>Предыдущие фото</Button>
        <Button variant="outline" disabled={currentPage + 1 >= pageCount} onClick={() => setPage(currentPage + 1)}>Следующие фото</Button>
      </>}
    </div>
  </section>
  );
};
