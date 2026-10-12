import React, { useState } from 'react';
import { newAuth } from '../../lib/auth_new';
import { Button } from '../ui/button';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '../ui/sheet';

interface ReadyLetter { company: string; email: string; subject: string; body: string; content_sha256: string; }
interface ImportResult { email: string; status: string; readiness?: string; error?: string; }

export function ReadyEmailImport({ onSaved }: { onSaved: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [source, setSource] = useState('');
  const [letters, setLetters] = useState<ReadyLetter[]>([]);
  const [results, setResults] = useState<ImportResult[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const changeSource = (value: string) => { setSource(value); setLetters([]); setResults([]); setError(''); };
  const inspect = async () => {
    setBusy(true); setError(''); setLetters([]); setResults([]);
    try {
      const response = await newAuth.makeRequest('/outreach/ready-emails/import', {
        method: 'POST', body: JSON.stringify({ items: JSON.parse(source), save: false }),
      });
      setLetters(response.items);
    } catch (issue) { setError(issue instanceof Error ? issue.message : 'Не удалось проверить файл'); }
    finally { setBusy(false); }
  };
  const save = async () => {
    setBusy(true); setError('');
    const next: ImportResult[] = [];
    for (const letter of letters) {
      try {
        const response = await newAuth.makeRequest('/outreach/ready-emails/import', {
          method: 'POST', body: JSON.stringify({ items: [letter], save: true }),
        });
        next.push({ email: letter.email, ...response.result });
      } catch (issue) {
        next.push({ email: letter.email, status: 'error', error: issue instanceof Error ? issue.message : 'Ошибка сохранения' });
        // Stop on an unresolved write rather than continuing an unknown batch state.
        setResults([...next]); break;
      }
      setResults([...next]);
    }
    setBusy(false);
    await onSaved();
  };
  return <>
    <Button variant="outline" className="min-h-11" onClick={() => setOpen(true)}>Импорт готовых писем</Button>
    <Sheet open={open} onOpenChange={(value) => { if (!busy) setOpen(value); }}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>Добавить готовые письма LocalOS</SheetTitle>
          <SheetDescription>Загрузите JSON с контактами, источниками, темами и текстами. Письма сохранятся без изменений как черновики от localosgo@gmail.com. Отправку нужно подтвердить отдельно в «Сообщениях».</SheetDescription>
        </SheetHeader>
        <div className="mt-6 space-y-4">
          <label className="block space-y-2 text-sm font-medium">Файл JSON
            <input type="file" accept=".json,application/json" disabled={busy} onChange={async (event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              if (file.size > 2000000) { setError('Файл слишком большой: максимум 2 МБ'); return; }
              try { changeSource(await file.text()); } catch { setError('Не удалось прочитать файл'); }
            }} className="block w-full text-sm" />
          </label>
          <label className="block space-y-2 text-sm font-medium">Или вставьте JSON
            <textarea value={source} disabled={busy} onChange={(event) => changeSource(event.target.value)} rows={6} className="w-full rounded-md border border-input bg-background p-3 text-sm" />
          </label>
          <Button disabled={busy || !source.trim()} onClick={inspect}>{busy ? 'Обработка…' : 'Проверить письма'}</Button>
          {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
          {letters.length ? <div className="space-y-3">
            <p className="text-sm">Проверено: {letters.length}. Повторный импорт не создаст новую кампанию для уже обработанного контакта. Запреты и готовность к отправке проверяются при подготовке кампании.</p>
            <details className="rounded-md border p-3"><summary className="cursor-pointer">Пример: {letters[0].company} · {letters[0].email}</summary>
              <p className="mt-3 font-medium">{letters[0].subject}</p><p className="mt-3 whitespace-pre-wrap text-sm">{letters[0].body}</p>
            </details>
            <Button disabled={busy || results.length > 0} onClick={save}>Сохранить {letters.length} черновиков</Button>
          </div> : null}
          {results.length ? <div aria-live="polite" className="space-y-2 text-sm">
            <p>Обработано {results.length} из {letters.length}. Сохранено: {results.filter((item) => item.status === 'draft').length}. Пропущено: {results.filter((item) => item.status === 'skipped_existing_campaign').length}. Отправлено: 0.</p>
            {results.map((item) => <p key={item.email}>{item.email}: {item.status === 'draft' ? (item.readiness === 'ready' ? 'черновик готов к проверке' : 'черновик требует внимания') : item.status === 'skipped_existing_campaign' ? 'кампания уже существует' : item.error}</p>)}
            {!busy ? <p>Откройте «Сообщения», проверьте тексты и подтвердите отправку готовых писем. Письма с ошибками не отправляются.</p> : null}
          </div> : null}
        </div>
      </SheetContent>
    </Sheet>
  </>;
}
