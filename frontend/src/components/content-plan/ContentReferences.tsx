import { useEffect, useRef, useState } from 'react';
import { ExternalLink, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { contentRequest, ContentAccessError } from './contentRequest';

type Reference = {
  id: string; source_name: string; source_url: string; techniques: string[];
  scope: string; owned: boolean; enabled: boolean; moderation: string;
  moderation_note?: string; version: number;
};
type Catalogue = {
  industry_label: string; items: Reference[]; settings_version: number;
  can_manage: boolean; can_moderate: boolean; pending: Reference[];
};

export function ContentReferences({ businessId, open, onOpenChange, language = 'ru', headers }: {
  businessId: string; open: boolean; onOpenChange: (open: boolean) => void; language?: string; headers?: () => HeadersInit;
}) {
  const ru = language === 'ru';
  const [data, setData] = useState<Catalogue | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [title, setTitle] = useState('');
  const [url, setUrl] = useState('');
  const [technique, setTechnique] = useState('');
  const [share, setShare] = useState(false);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const generation = useRef(0);
  const requestId = useRef(crypto.randomUUID());
  const endpoint = `/content-voice/references?business_id=${encodeURIComponent(businessId)}`;

  useEffect(() => { requestId.current = crypto.randomUUID(); }, [title, url, technique, share]);

  useEffect(() => {
    const current = ++generation.current;
    setData(null); setError(''); setMessage(''); setBusy(false);
    setTitle(''); setUrl(''); setTechnique(''); setShare(false); setNotes({});
    requestId.current = crypto.randomUUID();
    if (!open || !businessId) return;
    setLoading(true);
    void contentRequest<Catalogue>(endpoint, undefined, headers).then((result) => {
      if (current === generation.current) setData(result);
    }).catch((reason: Error) => {
      if (current === generation.current) setError(reason.message);
    }).finally(() => {
      if (current === generation.current) setLoading(false);
    });
    return () => { generation.current += 1; };
  }, [open, businessId, endpoint, headers]);

  const change = async (payload: Record<string, unknown>) => {
    const current = generation.current;
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await contentRequest<Catalogue>(endpoint, {
        method: 'POST', body: JSON.stringify({ ...payload, business_id: businessId }),
      }, headers);
      if (current !== generation.current) return;
      setData(result);
      setMessage(ru ? 'Сохранено. Изменения применяются к подготовке новых текстов.' : 'Saved. Changes apply to newly prepared copy.');
      if (payload.action === 'add') {
        setTitle(''); setUrl(''); setTechnique(''); setShare(false);
        requestId.current = crypto.randomUUID();
      }
    } catch (reason) {
      if (current === generation.current) {
        setError(reason instanceof Error ? reason.message : (ru ? 'Не удалось сохранить' : 'Could not save'));
        if (reason instanceof ContentAccessError) { setData(null); setTitle(''); setUrl(''); setTechnique(''); setNotes({}); return; }
        // A conflict may mean another user changed the same selection. Refresh
        // the version while retaining the user's add form and error notice.
        try {
          const result = await contentRequest<Catalogue>(endpoint, undefined, headers);
          if (current === generation.current) setData(result);
        } catch { /* The original error remains visible with a retry action. */ }
      }
    } finally {
      if (current === generation.current) setBusy(false);
    }
  };
  const link = (item: Reference) => /^https?:\/\//i.test(item.source_url) ? (
    <a href={item.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-10 items-center gap-1 text-sm underline underline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">
      {ru ? 'Открыть источник' : 'Open source'}<ExternalLink aria-hidden="true" className="size-3.5" />
    </a>
  ) : null;

  return <Sheet open={open} onOpenChange={(value) => { if (!busy) onOpenChange(value); }}>
    <SheetContent closeLabel={ru ? 'Закрыть ориентиры' : 'Close references'} className={`flex w-full flex-col gap-0 overflow-y-auto text-foreground sm:max-w-xl ${headers ? 'dark' : ''}`} onCloseAutoFocus={(event) => {
      event.preventDefault(); (document.getElementById('content-references-button') || document.getElementById('content-settings-button'))?.focus();
    }}>
      <SheetHeader>
        <SheetTitle>{ru ? 'Ориентиры для постов' : 'Post references'}</SheetTitle>
        <SheetDescription>{ru ? 'Примеры подачи для новых текстов. Чужие характеристики, цены и обещания не становятся фактами вашей компании.' : 'Writing references for new copy. Other companies’ specifications, prices and promises are not facts about your business.'}</SheetDescription>
      </SheetHeader>
      {loading && <p role="status" className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />{ru ? 'Загружаем ориентиры…' : 'Loading references…'}</p>}
      {error && <div role="alert" className="mt-4 text-sm text-destructive">{error}<Button variant="outline" className="mt-2 block" disabled={busy} onClick={() => {
        const current = generation.current;
        setLoading(true);
        void contentRequest<Catalogue>(endpoint, undefined, headers).then((result) => { if (current === generation.current) { setData(result); setError(''); } })
          .catch((reason: Error) => { if (current === generation.current) setError(reason.message); })
          .finally(() => { if (current === generation.current) setLoading(false); });
      }}>{ru ? 'Обновить список' : 'Refresh list'}</Button></div>}
      {message && <p role="status" className="mt-4 text-sm text-muted-foreground">{message}</p>}
      {data && <div className="space-y-6 py-5">
        <section>
          <h3 className="font-medium">{data.industry_label}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{ru ? 'Отключение действует только для выбранного бизнеса. Готовые посты не изменятся.' : 'Disabling only affects this business. Existing posts stay unchanged.'}</p>
          {data.can_manage && <Button variant="outline" className="mt-3 min-h-11" onClick={() => document.getElementById('reference-title')?.focus()}>{ru ? 'Добавить свой ориентир' : 'Add your reference'}</Button>}
          {!data.items.length && <p className="py-4 text-sm">{ru ? 'Для этого типа пока нет общих ориентиров. Добавьте свой пример ниже.' : 'No shared references yet. Add your own below.'}</p>}
          <ul className="mt-3 divide-y">
            {data.items.map((item) => <li key={item.id} className="py-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h4 className="break-words font-medium">{item.source_name}</h4>
                  <p className="mt-1 text-xs text-muted-foreground">{item.scope === 'industry' ? (ru ? 'Общий ориентир типа бизнеса' : 'Shared industry reference') : (ru ? 'Ваш ориентир' : 'Your reference')}
                    {item.moderation === 'pending' ? (ru ? ' · На модерации' : ' · Pending review') : item.moderation === 'rejected' ? (ru ? ' · Не включён в общий набор' : ' · Not accepted for sharing') : ''}
                    {!item.enabled ? (ru ? ' · Не используется' : ' · Disabled') : ''}</p>
                </div>
                <Button variant="outline" className="min-h-11 shrink-0" disabled={!data.can_manage || busy} aria-label={`${item.enabled ? (ru ? 'Отключить' : 'Disable') : (ru ? 'Включить' : 'Enable')} ${item.source_name}`}
                  onClick={() => void change({ action: item.enabled ? 'disable' : 'enable', id: item.id, expected_version: data.settings_version })}>
                  {item.enabled ? (ru ? 'Отключить' : 'Disable') : (ru ? 'Включить' : 'Enable')}
                </Button>
              </div>
              <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6">{item.techniques.join(' · ')}</p>
              {item.moderation_note && <p className="mt-2 text-sm text-muted-foreground">{ru ? 'Результат проверки: ' : 'Review: '}{item.moderation_note}</p>}
              <div className="flex flex-wrap items-center justify-between gap-2">{link(item)}
                {item.owned && item.scope !== 'industry' && data.can_manage && <Button variant="ghost" disabled={busy} onClick={() => void change({ action: 'remove', id: item.id, expected_version: data.settings_version })}>{ru ? 'Убрать из моих ориентиров' : 'Remove my reference'}</Button>}
              </div>
            </li>)}
          </ul>
        </section>
        {data.can_manage && <form className="space-y-3 border-t pt-5" onSubmit={(event) => {
          event.preventDefault();
          void change({ action: 'add', title, url, technique, submit_for_review: share, request_id: requestId.current });
        }}>
          <h3 className="font-medium">{ru ? 'Добавить свой ориентир' : 'Add your reference'}</h3>
          <label className="block text-sm">{ru ? 'Название компании или примера' : 'Company or example name'}<Input id="reference-title" required maxLength={120} minLength={2} value={title} onChange={(e) => setTitle(e.target.value)} className="mt-1" disabled={busy} /></label>
          <label className="block text-sm">{ru ? 'Публичная ссылка' : 'Public URL'}<Input type="url" required maxLength={2000} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" className="mt-1" disabled={busy} /></label>
          <label className="block text-sm">{ru ? 'Что взять из примера' : 'What to learn from it'}<Textarea required minLength={15} maxLength={1200} value={technique} onChange={(e) => setTechnique(e.target.value)} placeholder={ru ? 'Например: показывать общий вид изделия и крупный план отделки' : 'For example: show the garment and close-ups of its details'} className="mt-1" disabled={busy} /></label>
          <label className="flex min-h-11 items-start gap-2 py-2 text-sm"><input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} disabled={busy} className="mt-1" /><span>{ru ? 'Предложить для общего набора этого типа бизнеса. Название, ссылка и пояснение станут доступны другим компаниям только после модерации.' : 'Suggest for the shared industry set. The name, URL and guidance will become available to other companies only after moderation.'}</span></label>
          <Button type="submit" disabled={busy}>{busy ? (ru ? 'Сохраняем…' : 'Saving…') : (ru ? 'Добавить ориентир' : 'Add reference')}</Button>
        </form>}
        {data.can_moderate && <details className="border-t pt-4"><summary className="min-h-11 cursor-pointer py-2 font-medium">{ru ? 'Модерация предложений' : 'Review suggestions'} · {data.pending.length}</summary>
          <p className="mb-3 text-sm text-muted-foreground">{ru ? 'Проверьте источник и полезность приёма. Одобрение добавляет пример всем бизнесам этого типа, но не публикует посты.' : 'Check the source and guidance. Approval shares the reference with this industry, not any posts.'}</p>
          {data.pending.map((item) => <article key={item.id} className="space-y-2 border-t py-4">
            <h4 className="font-medium">{item.source_name}</h4><p className="whitespace-pre-wrap break-words text-sm">{item.techniques.join(' · ')}</p>{link(item)}
            <label className="block text-sm">{ru ? 'Результат проверки' : 'Review note'}<Textarea minLength={5} maxLength={1000} value={notes[item.id] || ''} onChange={(e) => setNotes({ ...notes, [item.id]: e.target.value })} disabled={busy} /></label>
            <div className="flex flex-wrap gap-2"><Button disabled={busy || (notes[item.id] || '').trim().length < 5} onClick={() => void change({ action: 'moderate_approve', id: item.id, expected_version: item.version, note: notes[item.id] })}>{ru ? 'Включить в общий набор' : 'Approve for shared set'}</Button>
              <Button variant="outline" disabled={busy || (notes[item.id] || '').trim().length < 5} onClick={() => void change({ action: 'moderate_reject', id: item.id, expected_version: item.version, note: notes[item.id] })}>{ru ? 'Отклонить' : 'Reject'}</Button></div>
          </article>)}
        </details>}
      </div>}
    </SheetContent>
  </Sheet>;
}
