import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { diskRequest } from './DiskImportPanel';
export function GoogleDriveReaderSettings() {
  const keyInput = useRef<HTMLInputElement>(null);
  const [settings, setSettings] = useState<{ configured: boolean; client_email: string; version: number } | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState('');
  useEffect(() => { const controller = new AbortController();
    void diskRequest('/google-reader', undefined, controller.signal).then(setSettings).catch(caught => { if (!controller.signal.aborted) setError(caught.message); });
    return () => controller.abort();
  }, []);
  return <section className="space-y-3 rounded-lg border bg-card p-5">
    <h2 className="text-lg font-semibold">Чтение папок Google Диска</h2>
    <p className="text-sm text-muted-foreground">Создайте отдельный служебный аккаунт в Google Cloud, включите Drive API и загрузите JSON-ключ. Делегирование доступа ко всей организации не требуется. Клиент поделится только своей папкой с адресом этого аккаунта.</p>
    <a className="text-primary underline" href="https://console.cloud.google.com/iam-admin/serviceaccounts" target="_blank" rel="noreferrer">Служебные аккаунты Google Cloud</a>
    {settings?.configured && <Input aria-label="Адрес служебного аккаунта Google" readOnly value={settings.client_email} />}
    <label className="block">JSON-ключ служебного аккаунта<Input ref={keyInput} type="file" accept="application/json,.json" disabled={busy} onChange={event => setFile(event.target.files?.[0] || null)} /></label>
    {error && <p role="alert" className="text-destructive">{error}</p>}{notice && <p role="status">{notice}</p>}
    <Button disabled={!file || !settings || busy} onClick={async () => {
      if (!file || !settings) return; setBusy(true); setError('');
      try {
        if (file.size > 12000) throw new Error('JSON-ключ слишком большой. Выберите файл служебного аккаунта.');
        const credentials = JSON.parse(await file.text());
        setSettings(await diskRequest('/google-reader', { credentials, version: settings.version })); setFile(null); if (keyInput.current) keyInput.current.value = ''; setNotice('Ключ сохранён зашифрованным. Владельцы могут подключать папки.');
      } catch (caught) { setError(caught instanceof Error ? caught.message : 'Не удалось сохранить ключ'); }
      finally { setBusy(false); }
    }}>Сохранить служебный аккаунт</Button>
  </section>;
}
