import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { newAuth } from '@/lib/auth_new';

type HelpProps = { businessId?: string | null; business?: string | null; address?: string | null; service?: string };

export function ConnectionHelpButton(props: HelpProps) {
  return <ConnectionHelpForm key={(props.businessId || '') + ':' + (props.service || '')} {...props} />;
}

function ConnectionHelpForm({ businessId, business, address, service = 'Подключения' }: HelpProps) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const [savedId, setSavedId] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [history, setHistory] = useState<{id:string;request_text:string;status:string}[]>([]);
  const [historyError, setHistoryError] = useState(false);
  useEffect(() => {
    if (!open || !businessId) return;
    let current = true;
    newAuth.makeRequest('/business/' + encodeURIComponent(businessId) + '/connection-help').then(result => {
      if (current) { setHistory(result.requests || []); setHistoryError(false); }
    }).catch(() => { if (current) setHistoryError(true); });
    return () => { current = false; };
  }, [open, businessId, savedId]);
  const send = async () => {
    if (pending.current || !businessId || !message.trim()) return;
    pending.current = true;
    setBusy(true);
    setError('');
    try {
      const result = await newAuth.makeRequest('/business/' + encodeURIComponent(businessId) + '/connection-help', {
        method: 'POST', body: JSON.stringify({ service, message, request_id: requestId }),
      });
      setSavedId(result.request_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось сохранить обращение. Повторите попытку.');
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };
  return <Dialog open={open} onOpenChange={value => { if (!busy) setOpen(value); }}>
    <DialogTrigger asChild><Button variant="outline">Помогите настроить подключение</Button></DialogTrigger>
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Помощь с подключением</DialogTitle>
        <DialogDescription>{[business, address, service].filter(Boolean).join(' · ')}</DialogDescription>
      </DialogHeader>
      {savedId ? <div role="status" className="space-y-3">
        <p>Обращение сохранено в очереди команды LocalOS. Ответим на почту вашего аккаунта.</p>
        <p className="break-all text-xs text-muted-foreground">Номер обращения {savedId}</p>
        <Button variant="outline" onClick={() => { setMessage(''); setSavedId(''); setRequestId(crypto.randomUUID()); }}>Задать ещё вопрос</Button>
      </div> : <form className="space-y-4" onSubmit={event => { event.preventDefault(); void send(); }}>
        <Label htmlFor={'connection-help-' + requestId}>На каком шаге нужна помощь?</Label>
        <Textarea id={'connection-help-' + requestId} value={message} onChange={event => setMessage(event.target.value)} maxLength={2000} disabled={busy} required placeholder="Например, не вижу раздел «Доступы» в Яндекс Бизнесе" />
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <Button type="submit" disabled={busy || !businessId || !message.trim()}>{busy ? 'Сохраняем…' : 'Отправить запрос команде'}</Button>
        {!businessId && <p className="text-sm text-muted-foreground">Выберите бизнес для обращения из кабинета.</p>}
      </form>}
      {history.length > 0 && <details className="space-y-2 text-sm">
        <summary className="cursor-pointer font-medium">Ваши запросы помощи</summary>
        {history.map(item => <p key={item.id} className="rounded-lg border p-2">{item.request_text} · {item.status === 'done' ? 'Помощь оказана' : item.status === 'in_progress' ? 'В работе' : 'Принято командой'}</p>)}
      </details>}
      {historyError && <p className="text-xs text-muted-foreground">История обращений сейчас недоступна.</p>}
      <a className="text-sm underline" href={'mailto:info@localos.pro?subject=' + encodeURIComponent('Помощь с подключением в LocalOS') + '&body=' + encodeURIComponent([business, address, service, message].filter(Boolean).join('\n'))}>Написать по электронной почте</a>
    </DialogContent>
  </Dialog>;
}
