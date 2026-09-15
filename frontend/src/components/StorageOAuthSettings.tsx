import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { voiceHeaders } from '@/components/operator/OperatorVoice';

type App = { provider: string; name: string; client_id: string; secret_saved: boolean; version: number; redirect_uri: string };
type Settings = { items: App[]; encryption_ready: boolean };

function AppForm({ app, enabled, onSaved }: { app: App; enabled: boolean; onSaved: (data: Settings) => void }) {
  const [client, setClient] = useState(app.client_id);
  const [secret, setSecret] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const providerUrl = app.provider === 'google' ? 'https://console.cloud.google.com/auth/clients' : 'https://oauth.yandex.ru/';
  return <form className="space-y-4 rounded-lg border bg-card p-5" onSubmit={async event => {
    event.preventDefault(); setBusy(true); setError(''); setSaved(false);
    try {
      const response = await fetch('/api/operator/storage-apps', { method: 'POST', headers: { ...voiceHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: app.provider, client_id: client, client_secret: secret, version: app.version }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Не удалось сохранить настройки');
      setSecret(''); setSaved(true); onSaved(data);
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Не удалось сохранить настройки'); }
    finally { setBusy(false); }
  }}>
    <h2 className="text-lg font-semibold">{app.name}</h2>
    <p className="text-sm text-muted-foreground">{app.secret_saved ? 'Реквизиты сохранены. Владелец бизнеса может подключить Диск в Операторе.' : 'Сначала создайте OAuth-приложение, затем сохраните его реквизиты здесь.'}</p>
    <a className="text-primary underline" href={providerUrl} target="_blank" rel="noreferrer">Открыть настройки приложения {app.name}</a>
    <label className="block space-y-1"><span>Redirect URI — добавьте в настройках приложения</span>
      <Input readOnly value={app.redirect_uri} onFocus={event => event.target.select()} /></label>
    <p className="break-all text-sm text-muted-foreground">Разрешение: {app.provider === 'google' ? 'https://www.googleapis.com/auth/drive.file' : 'cloud_api:disk.app_folder'}</p>
    <label className="block space-y-1"><span>Client ID · {app.name}</span><Input required value={client} autoComplete="off" disabled={busy || !enabled} onChange={event => { setClient(event.target.value); setSaved(false); }} /></label>
    <label className="block space-y-1"><span>Client Secret · {app.name}</span><Input type="password" value={secret} autoComplete="new-password" required={!app.secret_saved || client !== app.client_id} disabled={busy || !enabled} onChange={event => { setSecret(event.target.value); setSaved(false); }}
      placeholder={app.secret_saved ? 'Сохранён. Оставьте пустым, чтобы не менять' : 'Введите секрет приложения'} /></label>
    <p className="text-sm text-muted-foreground">Настройки общие для LocalOS. Секрет хранится зашифрованным и не показывается повторно. Сохранение не подключает личный Диск — владелец отдельно разрешает доступ.</p>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {saved && <p role="status" className="text-sm">Сохранено. Настройки уже доступны сайту и обработчикам фотографий.</p>}
    <Button type="submit" disabled={busy || !enabled}>{busy ? 'Сохраняю…' : `Сохранить ${app.name}`}</Button>
  </form>;
}

export function StorageOAuthSettings() {
  const [data, setData] = useState<Settings | null>(null);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); setError(''); setData(null);
    void fetch('/api/operator/storage-apps', { headers: voiceHeaders(), signal: controller.signal, cache: 'no-store' })
      .then(async response => { const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Не удалось загрузить настройки'); return body; })
      .then(body => { if (!controller.signal.aborted) setData(body); })
      .catch(caught => { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : 'Не удалось загрузить настройки'); });
    return () => controller.abort();
  }, [reload]);
  return <main className="mx-auto max-w-3xl space-y-5 pb-10">
    <Link className="text-primary underline" to="/dashboard/settings">Все настройки</Link>
    <h1 className="text-2xl font-semibold">Хранилища фотографий</h1>
    <p className="text-muted-foreground">Настройка OAuth-приложений для администратора LocalOS. Добавьте реквизиты выбранного сервиса; фотографии продолжат сохраняться в LocalOS.</p>
    {error && <div role="alert"><p>{error}</p><Button variant="outline" onClick={() => setReload(value => value + 1)}>Загрузить заново</Button></div>}
    {!data && !error && <p role="status">Загружаю настройки…</p>}
    {data && !data.encryption_ready && <p role="alert">Сначала настройте серверный ключ шифрования. Сохранение секретов отключено.</p>}
    {data?.items.map(app => <AppForm key={app.provider} app={app} enabled={data.encryption_ready} onSaved={setData} />)}
    <p className="text-sm text-muted-foreground">Яндекс: только папка приложения. Google: фотографии и папки, созданные через LocalOS. Выбор существующей папки пока не поддерживается.</p>
    <Link className="text-primary underline" to="/dashboard/operator">Перейти к подключению Диска в Операторе</Link>
  </main>;
}
