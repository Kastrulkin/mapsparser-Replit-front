import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { miniAppLabel, miniAppPlatform, openMiniAppLink } from '@/lib/miniAppPlatform';
import { mobileJsonHeaders, readMobileJson } from '@/lib/mobileDataClient';

export function WorkDiscussion({ businessId, itemId, updatedAt, onDiscuss, disabled, itemType = 'content_item' }: {
  itemType?: 'content_item' | 'partner' | 'day_brief'; businessId: string; itemId: string; updatedAt?: string; onDiscuss?: () => void; disabled?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const requestId = useRef(crypto.randomUUID());
  const active = useRef(true);
  useEffect(() => { active.current = true; requestId.current = crypto.randomUUID(); return () => { active.current = false; }; }, [businessId, itemId, updatedAt, itemType]);
  const openBot = async () => {
    if (busy || disabled) return;
    setBusy(true); setError('');
    try {
      const result = await fetch('/api/operator/work-handoff', { method: 'POST', headers: mobileJsonHeaders(),
        body: JSON.stringify({ business_id: businessId, item_id: itemId, item_type: itemType, updated_at: updatedAt, platform: miniAppPlatform(), request_id: requestId.current }),
      }).then(readMobileJson<{ url: string }>);
      if (!active.current) return;
      const url = new URL(result.url);
      if (url.protocol !== 'https:' || url.hostname !== (miniAppPlatform() === 'max' ? 'max.ru' : 't.me')) throw new Error('Не удалось открыть бота.');
      openMiniAppLink(result.url);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось открыть бота. Повторите.'); }
    finally { setBusy(false); }
  };
  return <div className="space-y-2 border-t pt-3">
    <div className="flex flex-wrap gap-2">
      {onDiscuss && <Button variant="outline" disabled={disabled || busy} onClick={onDiscuss}>{itemType === 'partner' ? 'Обсудить партнёра' : 'Обсудить этот пост'}</Button>}
      <Button variant="ghost" disabled={disabled || busy} onClick={() => void openBot()}>{busy ? 'Открываем…' : `Продолжить в боте ${miniAppLabel()}`}</Button>
    </div>
    {disabled && <p className="text-sm text-muted-foreground">Сохраните правки или закройте редактор перед переходом.</p>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
  </div>;
}
