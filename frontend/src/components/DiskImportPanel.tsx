import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { voiceHeaders } from '@/components/operator/OperatorVoice';

type Source = { id: string; provider: string; root_name: string; root_url: string; state: string; version: number; last_checked_at?: string; error_code?: string; scan_id?: string; counts: { status: string; count: number; error_code?: string }[] };
type Status = { enabled: boolean; can_configure: boolean; sources: Source[]; google?: { configured: boolean; client_email: string } };
const stateNames: Record<string, string> = { awaiting_proof: 'Подтвердите папку', ready: 'Готов к включению', active: 'Импорт включён', paused: 'Приостановлен', needs_reconnect: 'Нужна проверка доступа' };
const reasons: Record<string, string> = { unsupported_format: 'Неподдерживаемый формат', photo_too_large: 'Фото больше 10 МБ', photo_too_many_pixels: 'Фото больше 40 мегапикселей', invalid_image: 'Повреждённое изображение', access_lost: 'Нет доступа к папке', retry_pending: 'Временная ошибка — повторим проверку' };

export async function diskRequest(path: string, body?: unknown, signal?: AbortSignal) {
  const response = await fetch('/api/media-intelligence/disk-import' + path, { method: body === undefined ? 'GET' : 'POST',
    headers: { ...voiceHeaders(), ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: body === undefined ? undefined : JSON.stringify(body), signal });
  const data = await response.json(); signal?.throwIfAborted();
  if (response.status === 404 && body === undefined) return { enabled: false, can_configure: false, sources: [] };
  if (!response.ok) throw new Error(response.status === 403 ? 'Нет доступа к импорту' : data.error || 'Не удалось выполнить действие');
  return data;
}

export function DiskImportPanel({ businessId, onImported }: { businessId: string; onImported?: () => void }) {
  const lifetime = useRef(new AbortController());
  const importedCallback = useRef(onImported); importedCallback.current = onImported;
  useEffect(() => { const controller = new AbortController(); lifetime.current = controller; return () => controller.abort(); }, [businessId]);
  const [data, setData] = useState<Status | null>(null);
  const [error, setError] = useState('');
  const [provider, setProvider] = useState('yandex');
  const [folder, setFolder] = useState('');
  const [proof, setProof] = useState('');
  const [busy, setBusy] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); setData(null); setError(''); setProof('');
    let previous = '';
    const refresh = () => diskRequest(`?business_id=${encodeURIComponent(businessId)}`, undefined, controller.signal).then(body => {
      const current = JSON.stringify(body.sources);
      if (previous && previous !== current) importedCallback.current?.();
      previous = current; setData(body);
    }).catch(caught => {
      if (!controller.signal.aborted && caught.message !== 'Нет доступа к импорту') setError(caught.message);
    });
    void refresh(); const timer = window.setInterval(() => { void refresh(); }, 30000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [businessId, refreshKey]);
  async function perform(path: string, body: Record<string, unknown>) {
    const signal = lifetime.current.signal;
    setBusy(true); setError('');
    try {
      const result = await diskRequest(path, { ...body, business_id: businessId }, signal);
      if (result.proof_folder_name) setProof(result.proof_folder_name);
      setData(await diskRequest(`?business_id=${encodeURIComponent(businessId)}`, undefined, signal));
      onImported?.();
    } catch (caught) { if (!signal.aborted) setError(caught instanceof Error ? caught.message : 'Не удалось выполнить действие'); }
    finally { if (!signal.aborted) setBusy(false); }
  }
  if (!data && !error) return null;
  if (data?.enabled === false) return null;
  const sources = Array.isArray(data?.sources) ? data.sources : [];
  return <section className="space-y-4 rounded-lg border bg-card p-5" aria-label="Материалы с Диска">
    <h2 className="text-lg font-semibold">Материалы с Диска</h2>
    <p className="text-sm text-muted-foreground">Добавляйте фото и видео в подключённую папку. LocalOS проверяет её каждые пять минут. Фото сохраняются в медиатеке, видео остаются на Диске. Посты автоматически не создаются.</p>
    {error && <div role="alert"><p className="text-destructive">{error}</p><Button variant="ghost" onClick={() => setRefreshKey(value => value + 1)}>Обновить</Button></div>}
    {data?.can_configure && <details open={!sources.length}><summary className="cursor-pointer">Подключить папку</summary><div className="space-y-3 py-3">
      <label className="block">Диск<select className="ml-2 rounded-md border bg-background p-2" value={provider} onChange={event => setProvider(event.target.value)} disabled={busy}><option value="yandex">Яндекс Диск</option><option value="google">Google Диск</option></select></label>
      {provider === 'google' ? <>
        <p className="text-sm">Откройте доступ «Читатель» к одной папке для адреса ниже. Остальные папки подключать не требуется.</p>
        <Input aria-label="Адрес LocalOS для доступа к папке" readOnly value={data.google?.client_email || 'Служебный аккаунт ещё не настроен администратором LocalOS'} />
        <label className="block">Ссылка на папку Google Диска<Input value={folder} onChange={event => setFolder(event.target.value)} disabled={busy} /></label>
      </> : <p className="text-sm">Сначала подключите Яндекс Диск в Операторе. Затем создадим отдельную входящую папку этого бизнеса.</p>}
      <Button disabled={busy || (provider === 'google' && (!data.google?.configured || !folder))} onClick={() => void perform('/prepare', { provider, folder_url: folder })}>Подготовить папку</Button>
    </div></details>}
    {sources.map(source => <div key={source.id} className="space-y-2 border-t pt-3">
      <h3 className="font-medium">{source.provider === 'google' ? 'Google Диск' : 'Яндекс Диск'} · {source.root_name}</h3>
      <p role="status">{stateNames[source.state] || source.state}{source.scan_id && source.state === 'active' ? ' · идёт проверка' : ''}</p>
      {source.last_checked_at && <p className="text-sm text-muted-foreground">Последняя проверка: {new Date(source.last_checked_at).toLocaleString('ru-RU')}</p>}
      {source.error_code && <p className="text-sm text-destructive">{reasons[source.error_code] || 'Нужна повторная проверка'}</p>}
      {(Array.isArray(source.counts) ? source.counts : []).map((row, index) => <p key={index} className="text-sm">{row.status === 'imported' ? 'Добавлено' : row.status === 'skipped' ? 'Пропущено' : 'Ожидает обработки'}: {row.count}{row.error_code ? ` · ${reasons[row.error_code] || row.error_code}` : ''}</p>)}
      <a className="text-primary underline" href={source.root_url} target="_blank" rel="noreferrer">Открыть папку на Диске</a>
      {data.can_configure && <div className="flex flex-wrap gap-2">
        {source.state === 'awaiting_proof' && <div className="w-full space-y-2"><p>Создайте внутри этой папки пустую подпапку с кодом ниже. Это подтвердит, что вы управляете папкой.</p>
          <Input aria-label="Код подтверждения папки" value={proof} onChange={event => setProof(event.target.value)} />
          <Button disabled={busy || !proof} onClick={() => void perform('/verify', { source_id: source.id, code: proof })}>Проверить папку</Button>
          <p className="text-sm text-muted-foreground">Если код потерян или истёк, снова нажмите «Подготовить папку» с той же ссылкой.</p>
        </div>}
        {(source.state === 'ready' ? [['enable', 'Включить автоматическое добавление']] : source.state === 'active' ? [['scan', 'Проверить сейчас'], ['pause', 'Приостановить']] : ['paused', 'needs_reconnect'].includes(source.state) ? [['resume', 'Возобновить']] : []).map(([action, label]) => <Button key={action} variant="outline" disabled={busy} onClick={() => void perform('/action', { source_id: source.id, version: source.version, action })}>{label}</Button>)}
        <Button variant="ghost" disabled={busy} onClick={() => void perform('/action', { source_id: source.id, version: source.version, action: 'disconnect' })}>Отключить</Button>
      </div>}
    </div>)}
  </section>;
}
