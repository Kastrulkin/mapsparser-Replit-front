import { useState } from 'react';
import { KeyRound } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { newAuth } from '@/lib/auth_new';

export function PreparedCabinetInvite({ businessId, disabled }: { businessId: string; disabled: boolean }) {
  const [url, setUrl] = useState('');
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const path = '/superadmin/businesses/' + encodeURIComponent(businessId) + '/prepared-cabinet/invitation';

  const manage = async (method: 'POST' | 'DELETE') => {
    setBusy(true);
    setStatus('');
    try {
      const response = await newAuth.makeRequest(path, { method });
      setUrl(method === 'POST' ? response.setup_url : '');
      if (method === 'DELETE') setStatus('Ссылка отозвана.');
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Не удалось обновить приглашение.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog onOpenChange={open => {
      if (!open && !busy) { setUrl(''); setStatus(''); }
    }}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" disabled={disabled} aria-label="Приглашение в подготовленный кабинет" title="Приглашение в подготовленный кабинет">
          <KeyRound className="h-4 w-4" />
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Приглашение в подготовленный кабинет</DialogTitle>
          <DialogDescription>Ссылка действует 7 дней. Выпуск новой ссылки отзывает предыдущую. Передайте ссылку владельцу через проверенный канал.</DialogDescription>
        </DialogHeader>
        {url && (
          <div className="flex flex-wrap gap-2">
            <Input value={url} readOnly aria-label="Ссылка приглашения" onFocus={event => event.currentTarget.select()} />
            <Button variant="outline" onClick={async () => {
              try {
                await navigator.clipboard.writeText(url);
                setStatus('Ссылка скопирована.');
              } catch {
                setStatus('Выделите ссылку и скопируйте вручную.');
              }
            }}>Скопировать ссылку</Button>
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          <Button disabled={busy} onClick={() => void manage('POST')}>Выпустить ссылку</Button>
          <Button variant="outline" disabled={busy} onClick={() => void manage('DELETE')}>Отозвать ссылку</Button>
        </div>
        {status && <p role="status" className="text-sm">{status}</p>}
      </DialogContent>
    </Dialog>
  );
}
