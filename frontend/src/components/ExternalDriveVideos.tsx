import { Button } from '@/components/ui/button';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { useEffect, useRef, useState } from 'react';
import { diskRequest } from './DiskImportPanel.logic';
import { diskImportCopy, diskImportMessage } from './diskImportCopy';
type Video = { id: string; name: string; original_url: string; mime_type: string; available: boolean; size_bytes?: number; duration_ms?: number };
type Listing = { videos: Video[]; selected: Video[]; item_version: string; warnings?: string[] };

export function ExternalDriveVideos({ businessId, itemId, onChanged }: { businessId: string; itemId?: string; onChanged?: () => void }) {
  const { language } = useLanguage();
  const copy = diskImportCopy(language);
  const lifetime = useRef(new AbortController());
  const [refreshKey, setRefreshKey] = useState(0);
  useEffect(() => { const controller = new AbortController(); lifetime.current = controller; return () => controller.abort(); }, [businessId, itemId]);
  useEffect(() => { if (itemId) return; const timer = window.setInterval(() => setRefreshKey(value => value + 1), 30000); return () => window.clearInterval(timer); }, [itemId]);
  const [data, setData] = useState<Listing | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController(); setData(null); setError(''); setSelected([]);
    void diskRequest(`/videos?business_id=${encodeURIComponent(businessId)}${itemId ? `&item_id=${encodeURIComponent(itemId)}` : ''}`, undefined, controller.signal)
      .then(body => {
        if (body?.enabled === false) return;
        if (!Array.isArray(body?.videos) || !Array.isArray(body?.selected)) throw new Error(copy.actionFailed);
        setData(body); setSelected(body.selected.map((video: Video) => video.id));
      })
      .catch(caught => { if (!controller.signal.aborted && caught.message !== 'Нет доступа к импорту') setError(caught.message); });
    return () => controller.abort();
  }, [businessId, itemId, refreshKey]);
  if (!data && !error) return null;
  const videos = [...(data?.videos || []), ...(data?.selected || []).filter(video => !data?.videos.some(candidate => candidate.id === video.id))];
  return <section className="space-y-3 rounded-lg border bg-card p-4">
    <h3 className="font-semibold">{copy.videoTitle}</h3>
    <Button variant="ghost" disabled={busy} onClick={() => setRefreshKey(value => value + 1)}>{copy.videoRefresh}</Button>
    <p className="text-sm text-muted-foreground">{copy.videoDescription}</p>
    {error && <p role="alert" className="text-destructive">{diskImportMessage(error, language)}</p>}
    {data?.warnings?.map(warning => <p key={warning} role="status" className="text-sm text-destructive">{diskImportMessage(warning, language)}</p>)}
    {!error && !videos.length && <p className="text-sm">{copy.noVideos}</p>}
    {videos.map(video => <div key={video.id} className="space-y-1 border-t pt-2">
      {itemId ? <label className="flex items-start gap-2"><input type="checkbox" checked={selected.includes(video.id)} disabled={busy || (!video.available && !selected.includes(video.id))} onChange={event => setSelected(ids => event.target.checked ? [...ids, video.id] : ids.filter(id => id !== video.id))} /><span className="break-all">{video.name}</span></label> : <p className="break-all">{video.name}</p>}
      <p className="text-sm text-muted-foreground">{video.mime_type}{video.size_bytes ? ` · ${(video.size_bytes / 1024 / 1024).toFixed(1)} ${copy.mb}` : ''}{video.duration_ms ? ` · ${Math.round(video.duration_ms / 1000)} ${copy.sec}` : ''}</p>
      {!video.available && <p className="text-sm text-destructive">{copy.videoUnavailable}</p>}
      <a className="text-sm text-primary underline" href={video.original_url} target="_blank" rel="noreferrer">{copy.openVideo}</a>
    </div>)}
    {itemId && data && <Button disabled={busy} variant="outline" onClick={async () => {
      const signal = lifetime.current.signal;
      setBusy(true); setError('');
      try {
        const body = await diskRequest('/videos/select', { business_id: businessId, item_id: itemId, item_version: data.item_version, video_ids: selected }, signal);
        setData(body); onChanged?.();
      } catch (caught) { if (!signal.aborted) setError(caught instanceof Error ? caught.message : copy.saveFailed); }
      finally { if (!signal.aborted) setBusy(false); }
    }}>{copy.saveVideos}</Button>}
  </section>;
}
