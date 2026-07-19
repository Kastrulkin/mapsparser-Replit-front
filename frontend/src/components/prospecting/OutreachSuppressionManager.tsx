import { useCallback, useEffect, useState } from 'react';
import { Ban, RefreshCw, ShieldOff, Trash2, Upload } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { newAuth } from '@/lib/auth_new';

type Suppression = {
  id: string;
  reason_code?: string;
  scope_type?: string;
  source?: string;
  note?: string | null;
  expires_at?: string | null;
  created_at?: string;
};

const inferContact = (rawValue: string) => {
  const value = rawValue.trim();
  if (!value) return null;
  const colonIndex = value.indexOf(':');
  if (colonIndex > 0) {
    const contactType = value.slice(0, colonIndex).trim().toLowerCase();
    const contactValue = value.slice(colonIndex + 1).trim();
    if (['email', 'telegram', 'phone', 'whatsapp', 'vk', 'max', 'sms'].includes(contactType) && contactValue) {
      return { contact_type: contactType, contact_value: contactValue };
    }
  }
  if (value.includes('@') && !value.startsWith('@')) return { contact_type: 'email', contact_value: value };
  if (value.startsWith('@') || value.includes('t.me/')) return { contact_type: 'telegram', contact_value: value };
  if (/^[+\d\s()-]{7,}$/.test(value)) return { contact_type: 'phone', contact_value: value };
  return null;
};

export function OutreachSuppressionManager({
  workstreamId,
  businessId,
  scopeType = 'business',
  onChanged,
}: {
  workstreamId?: string | null;
  businessId?: string | null;
  scopeType?: 'business' | 'platform';
  onChanged?: () => void;
}) {
  const [items, setItems] = useState<Suppression[]>([]);
  const [reason, setReason] = useState('manual_dnc');
  const [note, setNote] = useState('');
  const [importText, setImportText] = useState('');
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!workstreamId) {
      setItems([]);
      return;
    }
    try {
      const payload = await newAuth.makeRequest(`/outreach/workstreams/${encodeURIComponent(workstreamId)}/suppressions`);
      setItems(Array.isArray(payload?.suppressions) ? payload.suppressions : []);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось проверить stop-list');
    }
  }, [workstreamId]);

  useEffect(() => {
    void load();
  }, [load]);

  const suppressLead = async () => {
    if (!workstreamId) return;
    setBusy('create');
    setError('');
    setNotice('');
    try {
      await newAuth.makeRequest('/outreach/suppressions', {
        method: 'POST',
        body: JSON.stringify({
          workstream_id: workstreamId,
          scope_type: scopeType,
          reason_code: reason,
          note: note.trim(),
        }),
      });
      setNotice('Лид добавлен в stop-list. Новые касания заблокированы до provider call.');
      setNote('');
      await load();
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось добавить запрет');
    } finally {
      setBusy('');
    }
  };

  const remove = async (suppressionId: string) => {
    if (!window.confirm('Снять запрет? Сама кампания не запустится автоматически.')) return;
    setBusy(`delete-${suppressionId}`);
    setError('');
    try {
      await newAuth.makeRequest(`/outreach/suppressions/${encodeURIComponent(suppressionId)}`, { method: 'DELETE' });
      setNotice('Запрет снят. Для отправки всё равно потребуется новый preflight и approval.');
      await load();
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось снять запрет');
    } finally {
      setBusy('');
    }
  };

  const importContacts = async () => {
    if (scopeType === 'business' && !businessId) return;
    const parsed = importText.split('\n').map(inferContact).filter((item) => item !== null);
    if (parsed.length === 0) {
      setError('Не найдено корректных контактов. Используйте email, телефон или формат telegram:@username.');
      return;
    }
    setBusy('import');
    setError('');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest('/outreach/suppressions/import', {
        method: 'POST',
        body: JSON.stringify({
          scope_type: scopeType,
          business_id: businessId,
          items: parsed.map((item) => ({ ...item, reason_code: 'imported_dnc' })),
        }),
      });
      setNotice(`Импортировано запретов: ${payload?.imported || parsed.length}. Контакты не раскрываются другим бизнесам.`);
      setImportText('');
      onChanged?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Импорт stop-list не выполнен');
    } finally {
      setBusy('');
    }
  };

  if (!workstreamId) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <ShieldOff className="mt-0.5 h-5 w-5 text-rose-700" />
        <div>
          <div className="font-semibold text-slate-950">Stop-list и «не беспокоить»</div>
          <p className="mt-1 text-sm leading-6 text-slate-600">Запрет проверяется по лиду и по всем каналам перед каждой отправкой. Область: {scopeType === 'platform' ? 'продажи LocalOS' : 'только этот бизнес'}.</p>
        </div>
      </div>

      {items.length > 0 ? (
        <div className="space-y-2">
          {items.map((item) => (
            <div key={item.id} className="flex flex-col gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className="border-rose-200 bg-white text-rose-800">{item.reason_code || 'DNC'}</Badge><span className="text-xs text-rose-800">{item.scope_type} · {item.source}</span></div>
                {item.note ? <div className="mt-1 text-sm text-rose-950">{item.note}</div> : null}
              </div>
              <Button variant="outline" size="sm" onClick={() => void remove(item.id)} disabled={Boolean(busy)} className="bg-white text-rose-700"><Trash2 className="mr-1.5 h-4 w-4" />Снять</Button>
            </div>
          ))}
        </div>
      ) : <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-600">Активных запретов для этого лида нет.</div>}

      <div className="grid gap-2 sm:grid-cols-[180px_minmax(0,1fr)]">
        <select value={reason} onChange={(event) => setReason(event.target.value)} className="min-h-11 rounded-md border border-slate-200 bg-white px-3 text-sm">
          <option value="manual_dnc">Не контактировать</option>
          <option value="not_interested">Не интересно</option>
          <option value="unsubscribe">Отписка</option>
          <option value="complaint">Жалоба</option>
        </select>
        <Input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Причина или комментарий" className="min-h-11 bg-white" />
      </div>
      <Button variant="outline" onClick={() => void suppressLead()} disabled={Boolean(busy)} className="min-h-11 w-full border-rose-200 bg-white text-rose-700"><Ban className="mr-2 h-4 w-4" />Добавить лида в stop-list</Button>

      <details className="border-t border-slate-200 pt-2">
        <summary className="min-h-10 cursor-pointer text-sm font-semibold text-slate-700">Импортировать stop-list бизнеса</summary>
        <div className="space-y-3 pt-3">
          <Textarea value={importText} onChange={(event) => setImportText(event.target.value)} placeholder={'email@example.ru\ntelegram:@username\nphone:+79990000000'} className="min-h-28 bg-white font-mono text-sm" />
          <Button variant="outline" onClick={() => void importContacts()} disabled={busy === 'import' || !importText.trim()} className="min-h-11 w-full bg-white">{busy === 'import' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}Импортировать</Button>
        </div>
      </details>

      {notice ? <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">{notice}</div> : null}
      {error ? <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-950">{error}</div> : null}
    </div>
  );
}
