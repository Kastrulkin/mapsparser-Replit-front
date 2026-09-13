import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { voiceHeaders } from './OperatorVoice';

type Entry = {
  id: string; input_summary: string; output_summary: string; status: string; reason_code?: string;
  created_at: string; metadata_json: { operator_channel?: string; input_type?: string; input_origin?: string; duplicates?: number; delivery?: string };
  response?: { result_json?: { tool_trace?: unknown[]; approval?: unknown; result_ref?: unknown } };
  audio?: { transcript?: string; corrected_text?: string };
  speech?: { status?: string; delivery?: string };
  feedback?: { input_summary: string; created_at: string }[];
};
const labels: Record<string, string> = { received: 'Обработка не завершена', completed: 'Выполнено',
  failed: 'Ошибка', blocked: 'Недоступно', approval_required: 'Ожидает подтверждения',
  clarification_required: 'Нужно уточнение', manual_handoff: 'Нужен ручной шаг', history: 'Из прежней переписки', cancelled: 'Отменено', rejected: 'Отклонено' };
const reasons: Record<string, string> = { access: 'проверка доступа', understanding: 'разбор команды', execution: 'выполнение', stt: 'распознавание речи' };
const channels: Record<string, string> = { web: 'Веб', telegram: 'Бот', telegram_mini_app: 'Mini App' };

const english: Record<string, string> = {
  "Обработка не завершена": "Processing unfinished",
  "Выполнено": "Completed",
  "Ошибка": "Error",
  "Недоступно": "Unavailable",
  "Ожидает подтверждения": "Awaiting confirmation",
  "Нужно уточнение": "Clarification needed",
  "Нужен ручной шаг": "Manual step needed",
  "Из прежней переписки": "Earlier conversation",
  "Отменено": "Cancelled",
  "Отклонено": "Rejected",
  "проверка доступа": "access check",
  "разбор команды": "command interpretation",
  "выполнение": "execution",
  "распознавание речи": "speech recognition",
  "Веб": "Web",
  "Бот": "Bot",
  "История недоступна": "History unavailable",
  "Не удалось загрузить": "Could not load",
  "Обращение недоступно": "Request unavailable",
  "Не удалось сохранить замечание": "Could not save feedback",
  "Замечание сохранено для разбора. Команда повторно не выполнялась.": "Feedback saved for review. The command was not executed again.",
  "Другой канал": "Other channel",
  "Голос": "Voice",
  "Текст": "Text",
  "Сохранённого ответа пока нет. Это не подтверждает выполнение команды.": "No saved reply yet. This does not confirm that the command was executed.",
  "Telegram принял ответ": "Telegram accepted the reply",
  "ошибка доставки; выполнение команды проверяйте отдельно": "delivery failed; check command execution separately",
  "готово": "ready",
  "срок хранения истёк, можно запросить заново": "expired; you can request it again",
  "ошибка, текст сохранён": "failed; text preserved",
  "в обработке": "processing",
  "История обращений": "Request history",
  "Посмотрите, что было распознано, какой ответ получен и где возникла ошибка. Прежняя переписка также доступна; подробный разбор собирается с момента включения пилота. Дата — по часовому поясу устройства.": "Review the transcription, reply and errors. Earlier conversations are also available; detailed analysis starts when the pilot is enabled. Dates use your device time zone.",
  "Дата": "Date",
  "Канал": "Channel",
  "Все": "All",
  "Ввод": "Input",
  "Любой": "Any",
  "Результат": "Result",
  "Сотрудник": "Employee",
  "Обновить": "Refresh",
  "Загружаю…": "Loading…",
  "Обращений пока нет. Отправьте Оператору текст или голосовую команду, затем обновите историю.": "No requests yet. Send a text or voice command to Operator, then refresh the history.",
  "Продолжение после настройки бизнеса": "Continued after business setup",
  "Назад": "Back",
  "Дальше": "Next",
  "Распознано: ": "Transcribed: ",
  "После исправления: ": "After correction: ",
  "Этап ошибки: ": "Error stage: ",
  "Повторных доставок: ": "Duplicate deliveries: ",
  "Доставка ответа: ": "Reply delivery: ",
  "Озвучивание: ": "Speech: ",
  "Замечание: ": "Feedback: ",
  "Подробности результата": "Result details",
  "Оператор понял неправильно": "Operator misunderstood",
  "Сохранить замечание": "Save feedback",
  "Разбор обращения": "Request details",
  "Что вы имели в виду и что получилось?": "What did you mean, and what happened?"
};

export function OperatorRequestHistory({ businessId, language = 'ru' }: { businessId: string; language?: string }) {
  const t = (text: string) => language === 'ru' ? text : text === 'История обращений' && language === 'el' ? 'Ιστορικό αιτημάτων' : english[text] || text;
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Entry[]>([]);
  const [selected, setSelected] = useState<Entry | null>(null);
  const [channel, setChannel] = useState(''); const [inputType, setInputType] = useState('');
  const [status, setStatus] = useState(''); const [date, setDate] = useState('');
  const [person, setPerson] = useState(''); const [people, setPeople] = useState<{ id: string; name: string }[]>([]);
  const [offset, setOffset] = useState(0); const [next, setNext] = useState<number | null>(null);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const [comment, setComment] = useState(''); const [notice, setNotice] = useState('');
  const [refresh, setRefresh] = useState(0);
  const detailPanel = useRef<HTMLElement | null>(null);
  useEffect(() => { if (selected) detailPanel.current?.focus(); }, [selected?.id]);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setBusy(true); setError(''); setItems([]); setSelected(null); setPeople([]);
    const query = new URLSearchParams({ business_id: businessId, channel, input_type: inputType, status, user_id: person, offset: String(offset) });
    if (date) { query.set('from', new Date(`${date}T00:00:00`).toISOString()); const end = new Date(`${date}T00:00:00`); end.setDate(end.getDate() + 1); query.set('until', end.toISOString()); }
    void fetch(`/api/operator/requests?${query}`, { headers: voiceHeaders(), signal: controller.signal })
      .then(async (response) => { const data = await response.json(); if (!response.ok) throw new Error(data.error || t("История недоступна")); return data; })
      .then((data) => { if (!controller.signal.aborted) { setItems(data.items); setNext(data.next_offset); setPeople(data.people || []); } })
      .catch((failure) => { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : t("Не удалось загрузить")); })
      .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [businessId, open, channel, inputType, status, date, person, offset, refresh]);
  useEffect(() => { setOffset(0); }, [channel, inputType, status, date, person]);
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    void fetch(`/api/operator/requests/${selected.id}?business_id=${encodeURIComponent(businessId)}`, { headers: voiceHeaders(), signal: controller.signal })
      .then(async (response) => { const data = await response.json(); if (!response.ok) throw new Error(data.error || t("Обращение недоступно")); return data; })
      .then((data) => { if (!controller.signal.aborted) setSelected(data); })
      .catch((failure) => { if (!controller.signal.aborted) { setSelected(null); setItems([]); setError(failure instanceof Error ? failure.message : t("Ошибка")); } });
    return () => controller.abort();
  }, [businessId, selected?.id]);
  const sendFeedback = async () => {
    if (!selected) return;
    setBusy(true); setNotice('');
    try {
      const response = await fetch(`/api/operator/requests/${selected.id}/feedback`, { method: 'POST',
        headers: { ...voiceHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify({ business_id: businessId, comment }) });
      if (!response.ok) throw new Error(t("Не удалось сохранить замечание"));
      setNotice(t("Замечание сохранено для разбора. Команда повторно не выполнялась.")); setComment('');
    } catch (failure) { setNotice(failure instanceof Error ? failure.message : t("Ошибка")); }
    finally { setBusy(false); }
  };
  return <details className="rounded-xl border bg-card p-4" onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary className="cursor-pointer font-medium">{t("История обращений")}</summary>
    {open && <div className="mt-4 space-y-4">
      <p className="text-sm text-muted-foreground">{t("Посмотрите, что было распознано, какой ответ получен и где возникла ошибка. Прежняя переписка также доступна; подробный разбор собирается с момента включения пилота. Дата — по часовому поясу устройства.")}</p>
      <div className="flex flex-wrap gap-3">
        <label className="text-sm">{t("Дата")}<input className="block rounded-md border bg-background p-2" type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label>
        <label className="text-sm">{t("Канал")}<select className="block rounded-md border bg-background p-2" value={channel} onChange={(event) => setChannel(event.target.value)}><option value="">{t("Все")}</option>{Object.entries(channels).map(([key, name]) => <option key={key} value={key}>{t(name)}</option>)}</select></label>
        <label className="text-sm">{t("Ввод")}<select className="block rounded-md border bg-background p-2" value={inputType} onChange={(event) => setInputType(event.target.value)}><option value="">{t("Любой")}</option><option value="voice">{t("Голос")}</option><option value="text">{t("Текст")}</option></select></label>
        <label className="text-sm">{t("Результат")}<select className="block rounded-md border bg-background p-2" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">{t("Все")}</option>{Object.entries(labels).map(([key, name]) => <option key={key} value={key}>{t(name)}</option>)}</select></label>
        {people.length > 0 && <label className="text-sm">{t("Сотрудник")}<select className="block rounded-md border bg-background p-2" value={person} onChange={(event) => setPerson(event.target.value)}><option value="">{t("Все")}</option>{people.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}</select></label>}
        <Button variant="outline" disabled={busy} onClick={() => setRefresh((value) => value + 1)}>{t("Обновить")}</Button>
      </div>
      {error && <p role="alert">{error}</p>}
      {busy && <p role="status">{t("Загружаю…")}</p>}
      {!busy && !error && !items.length && <p>{t("Обращений пока нет. Отправьте Оператору текст или голосовую команду, затем обновите историю.")}</p>}
      <ul className="space-y-2">{items.map((entry) => <li key={entry.id}><button className="w-full rounded-md border p-3 text-left hover:bg-muted focus-visible:outline" onClick={() => { setSelected(entry); setNotice(''); setComment(''); }}>
        <span className="block text-xs text-muted-foreground">{new Date(entry.created_at).toLocaleString()} · {t(channels[entry.metadata_json.operator_channel || ''] || '') || t("Другой канал")} · {entry.metadata_json.input_type === 'voice' ? t("Голос") : t("Текст")}</span>
        <span className="block break-words">{entry.input_summary}</span><span className="text-sm">{t(labels[entry.status] || entry.status)}</span>
        {entry.metadata_json.input_origin === 'settings_resume' && <span className="block text-xs text-muted-foreground">{t("Продолжение после настройки бизнеса")}</span>}
      </button></li>)}</ul>
      <div className="flex gap-2">{offset > 0 && <Button variant="outline" onClick={() => setOffset(Math.max(0, offset - 50))}>{t("Назад")}</Button>}{next !== null && <Button variant="outline" onClick={() => setOffset(next)}>{t("Дальше")}</Button>}</div>
      {selected && <section ref={detailPanel} tabIndex={-1} className="space-y-3 rounded-lg border p-3" aria-label={t("Разбор обращения")}>
        <h3 className="font-medium">{t(labels[selected.status] || selected.status)}</h3>
        <p className="whitespace-pre-wrap break-words">{selected.output_summary || t("Сохранённого ответа пока нет. Это не подтверждает выполнение команды.")}</p>
        {selected.audio?.transcript && <p>{t("Распознано: ")}{selected.audio.transcript}</p>}
        {selected.audio?.corrected_text && selected.audio.corrected_text !== selected.audio.transcript && <p>{t("После исправления: ")}{selected.audio.corrected_text}</p>}
        {selected.reason_code && <p>{t("Этап ошибки: ")}{t(reasons[selected.reason_code] || selected.reason_code)}</p>}
        <p className="text-sm">{t("Повторных доставок: ")}{selected.metadata_json.duplicates || 0}</p>
        {selected.metadata_json.delivery && <p className="text-sm">{t("Доставка ответа: ")}{selected.metadata_json.delivery === 'delivered' ? t("Telegram принял ответ") : t("ошибка доставки; выполнение команды проверяйте отдельно")}</p>}
        {selected.speech?.status && <p className="text-sm">{t("Озвучивание: ")}{selected.speech.status === 'ready' ? t("готово") : selected.speech.status === 'expired' ? t("срок хранения истёк, можно запросить заново") : selected.speech.status === 'failed' ? t("ошибка, текст сохранён") : t("в обработке")}</p>}
        {selected.feedback?.map((entry) => <p key={entry.created_at} className="text-sm">{t("Замечание: ")}{entry.input_summary}</p>)}
        {selected.response?.result_json && <details><summary className="cursor-pointer">{t("Подробности результата")}</summary><pre className="whitespace-pre-wrap break-all text-xs">{JSON.stringify(selected.response.result_json, null, 2)}</pre></details>}
        <label className="block text-sm">{t("Оператор понял неправильно")}<textarea className="mt-1 block w-full rounded-md border bg-background p-2" maxLength={2000} value={comment} onChange={(event) => setComment(event.target.value)} placeholder={t("Что вы имели в виду и что получилось?")} /></label>
        <Button disabled={busy || !comment.trim()} onClick={() => void sendFeedback()}>{t("Сохранить замечание")}</Button>
        {notice && <p role="status">{notice}</p>}
      </section>}
    </div>}
  </details>;
}
