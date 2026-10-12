import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { useEffect, useRef, useState } from 'react';
import { diskRequest } from './DiskImportPanel.logic';
import { diskImportCopy, diskImportMessage } from './diskImportCopy';

type Source = { id: string; provider: string; root_name: string; root_url: string; state: string; version: number; last_checked_at?: string; error_code?: string; scan_id?: string; counts: { status: string; count: number; error_code?: string }[] };
type Status = { enabled: boolean; can_configure: boolean; sources: Source[]; google?: { configured: boolean; client_email: string } };
export function DiskImportPanel({ businessId, onImported }: { businessId: string; onImported?: () => void }) {
  const { language } = useLanguage();
  const copy = diskImportCopy(language);
  const stateNames: Record<string, string> = { awaiting_proof: copy.awaiting_proof, ready: copy.ready, active: copy.active, paused: copy.paused, needs_reconnect: copy.needs_reconnect };
  const reasons: Record<string, string> = { unsupported_format: copy.unsupported_format, photo_too_large: copy.photo_too_large, photo_too_many_pixels: copy.photo_too_many_pixels, invalid_image: copy.invalid_image, access_lost: copy.access_lost, retry_pending: copy.retry_pending };
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
    } catch (caught) { if (!signal.aborted) setError(caught instanceof Error ? caught.message : copy.actionFailed); }
    finally { if (!signal.aborted) setBusy(false); }
  }
  if (!data && !error) return null;
  if (data?.enabled === false) return null;
  const sources = Array.isArray(data?.sources) ? data.sources : [];
  return <section className="space-y-4 rounded-lg border bg-card p-5" aria-label={copy.title}>
    <h2 className="text-lg font-semibold">{copy.title}</h2>
    <p className="text-sm text-muted-foreground">{copy.description}</p>
    {error && <div role="alert"><p className="text-destructive">{diskImportMessage(error, language)}</p><Button variant="ghost" onClick={() => setRefreshKey(value => value + 1)}>{copy.refresh}</Button></div>}
    {data?.can_configure && <details open={!sources.length}><summary className="cursor-pointer">{copy.connect}</summary><div className="space-y-3 py-3">
      <label className="block">{copy.disk}<select className="ml-2 rounded-md border bg-background p-2" value={provider} onChange={event => setProvider(event.target.value)} disabled={busy}><option value="yandex">{copy.yandex}</option><option value="google">{copy.google}</option></select></label>
      {provider === 'google' ? <>
        <p className="text-sm">{copy.googleInstructions}</p>
        <Input aria-label={copy.accessAddress} readOnly value={data.google?.client_email || copy.accountMissing} />
        <label className="block">{copy.googleLink}<Input value={folder} onChange={event => setFolder(event.target.value)} disabled={busy} /></label>
      </> : <>
        <p className="text-sm">{copy.yandexInstructions}</p>
        <label className="block">{copy.yandexLink}<Input value={folder} onChange={event => setFolder(event.target.value)} disabled={busy} placeholder="https://disk.360.yandex.ru/d/…" /></label>
        <p className="text-sm text-muted-foreground">{copy.yandexConnected}</p>
      </>}
      <Button disabled={busy || (provider === 'google' && (!data.google?.configured || !folder))} onClick={() => void perform('/prepare', { provider, folder_url: folder })}>{copy.prepare}</Button>
    </div></details>}
    {sources.map(source => <div key={source.id} className="space-y-2 border-t pt-3">
      <h3 className="font-medium">{source.provider === 'google' ? copy.google : copy.yandex} · {source.root_name}</h3>
      <p role="status">{stateNames[source.state] || source.state}{source.scan_id && source.state === 'active' ? ` · ${copy.scanning}` : ''}</p>
      {source.last_checked_at && <p className="text-sm text-muted-foreground">{copy.lastChecked}: {new Date(source.last_checked_at).toLocaleString(language === 'hy' ? 'hy-AM' : language === 'kk' ? 'kk-KZ' : 'ru-RU')}</p>}
      {source.error_code && <p className="text-sm text-destructive">{reasons[source.error_code] || copy.retry}</p>}
      {(Array.isArray(source.counts) ? source.counts : []).map((row, index) => <p key={index} className="text-sm">{row.status === 'imported' ? copy.imported : row.status === 'skipped' ? copy.skipped : copy.pending}: {row.count}{row.error_code ? ` · ${reasons[row.error_code] || row.error_code}` : ''}</p>)}
      <a className="text-primary underline" href={source.root_url} target="_blank" rel="noreferrer">{copy.openFolder}</a>
      {data.can_configure && <div className="flex flex-wrap gap-2">
        {source.state === 'awaiting_proof' && <div className="w-full space-y-2"><p>{copy.proofInstructions}</p>
          <Input aria-label={copy.proofCode} value={proof} onChange={event => setProof(event.target.value)} />
          <Button disabled={busy || !proof} onClick={() => void perform('/verify', { source_id: source.id, code: proof })}>{copy.verify}</Button>
          <p className="text-sm text-muted-foreground">{copy.proofExpired}</p>
        </div>}
        {(source.state === 'ready' ? [['enable', copy.enable]] : source.state === 'active' ? [['scan', copy.scan], ['pause', copy.pause]] : ['paused', 'needs_reconnect'].includes(source.state) ? [['resume', copy.resume]] : []).map(([action, label]) => <Button key={action} variant="outline" disabled={busy} onClick={() => void perform('/action', { source_id: source.id, version: source.version, action })}>{label}</Button>)}
        <Button variant="ghost" disabled={busy} onClick={() => void perform('/action', { source_id: source.id, version: source.version, action: 'disconnect' })}>{copy.disconnect}</Button>
      </div>}
    </div>)}
  </section>;
}
