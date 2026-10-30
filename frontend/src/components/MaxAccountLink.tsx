import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { readMobileJson } from '@/lib/mobileDataClient';
import logo from '@/assets/images/logo.png';
import { maxAccountInviteCode } from '@/lib/maxAccountInvite';

export default function MaxAccountLink({ initData, onLinked }: { initData: string; onLinked: () => void }) {
  const [invitationCode] = useState(() => maxAccountInviteCode(initData, window.location.search));
  const [code, setCode] = useState(invitationCode);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return <main className="grid min-h-[100dvh] place-items-center bg-background p-6 text-foreground"><form className="w-full max-w-sm space-y-5" onSubmit={async (event) => {
    event.preventDefault(); if (busy) return; setBusy(true); setError('');
    try {
      await fetch('/api/max/link', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ init_data: initData, code: code.trim() }) }).then(readMobileJson);
      setCode('');
      onLinked();
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось связать аккаунт'); }
    finally { setBusy(false); }
  }}>
    <img src={logo} alt="LocalOS" className="h-12 w-12 object-contain" />
    <h1 className="text-2xl font-semibold">Подключите свой LocalOS к MAX</h1>
    {invitationCode ? <p className="text-sm text-muted-foreground">Данные подключения уже получены из персональной ссылки. Нажмите кнопку, чтобы открыть свои бизнесы и задачи в MAX.</p> : <>
      <p className="text-sm text-muted-foreground">Получите одноразовый код в кабинете LocalOS и вставьте его здесь. После подключения откроются ваши бизнесы и задачи.</p>
      <a className="block min-h-11 text-primary underline" href="/dashboard/max" target="_blank" rel="noopener noreferrer">Войти в кабинет и получить код</a>
      <Label htmlFor="max-link-code">Код из кабинета LocalOS</Label>
      <Input id="max-link-code" autoComplete="off" value={code} onChange={(event) => setCode(event.target.value)} />
    </>}
    <Button className="min-h-11 w-full" disabled={busy || !code.trim()}>{busy ? 'Подключаем…' : 'Подключить аккаунт'}</Button>
    {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    {error && invitationCode ? <p className="text-sm text-muted-foreground">Если ссылка истекла или уже использована, попросите новую персональную ссылку.</p> : null}
  </form></main>;
}
