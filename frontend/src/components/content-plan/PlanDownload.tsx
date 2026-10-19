import { downloadMiniAppFile, openMiniAppLink } from "@/lib/miniAppPlatform";
import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { newAuth } from '@/lib/auth_new';
import { mobileJsonHeaders, readMobileJson } from '@/lib/mobileDataClient';

export function PlanDownload({ planId, mobile = false, dirty = false }: { planId: string; mobile?: boolean; dirty?: boolean }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [file, setFile] = useState<{ download_url: string; filename: string } | null>(null);
  const version = useRef(0);
  useEffect(() => { version.current += 1; setFile(null); setError(''); setBusy(false); return () => { version.current += 1; }; }, [planId, dirty]);
  const prepare = async (format: string) => {
    if (dirty) return;
    const current = ++version.current;
    setBusy(true); setError(''); setFile(null);
    try {
      const path = `/content-plans/${encodeURIComponent(planId)}/export`;
      const options = { method: 'POST', body: JSON.stringify({ format }) };
      const result = mobile
        ? await fetch(`/api${path}`, { ...options, headers: mobileJsonHeaders() }).then(readMobileJson<{ download_url: string; filename: string }>)
        : await newAuth.makeRequest(path, options);
      if (current === version.current) setFile(result);
    } catch (failure) { if (current === version.current) setError(failure instanceof Error ? failure.message : 'Не удалось подготовить файл. Повторите попытку.'); }
    finally { if (current === version.current) setBusy(false); }
  };
  return <div className="my-3 space-y-2">
    <span className="text-sm font-medium">Скачать план</span>
    <div className="flex gap-2">{['xlsx', 'pdf'].map(format => <Button key={format} variant="outline" className="min-h-11" disabled={busy || dirty} onClick={() => void prepare(format)}>{format === 'xlsx' ? 'Excel' : 'PDF'}</Button>)}</div>
    {dirty ? <p className="text-sm">Сначала сохраните или отмените изменения публикации.</p> : null}
    {busy ? <p role="status">Подготавливаем сохранённый план…</p> : null}
    {error ? <p role="alert">{error}</p> : null}
    {file ? <div className="space-y-2"><Button onClick={() => {
      try {
        const url = new URL(file.download_url, window.location.origin).href;
        if (mobile && downloadMiniAppFile(url, file.filename)) return;
        const anchor = document.createElement('a'); anchor.href = url; anchor.download = file.filename; anchor.click();
      } catch (failure) {
        setError(failure instanceof Error ? failure.message : 'Не удалось скачать файл. Откройте его в браузере.');
      }
    }}>Сохранить файл</Button><button type="button" className="block min-h-11 text-sm underline" onClick={() => openMiniAppLink(new URL(file.download_url, window.location.origin).href)}>Если скачивание не началось — открыть файл в браузере</button><p className="text-xs">Ссылка действует 5 минут.</p></div> : null}
  </div>;
}
