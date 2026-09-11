import { useEffect, useRef, useState } from 'react';
import { Mic, Square, Volume2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { browserCookieAuthEnabled, browserCookieValue } from '@/lib/browserSessionFetch';
import { newAuth } from '@/lib/auth_new';

export type VoiceSubmission = { transcription_id: string; conversation_id: string; request_id: string };
type HeadersProvider = () => Record<string, string>;
export const voiceHeaders = (): Record<string, string> => {
  const token = newAuth.getToken();
  const result: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
  const csrf = browserCookieValue('localos_csrf');
  if (browserCookieAuthEnabled() && csrf) result['X-CSRF-Token'] = csrf;
  return result;
};
async function jsonRequest(url: string, options: RequestInit) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'Не удалось обработать аудио');
  return body;
}
async function waitJob(jobId: string, businessId: string, headers: HeadersProvider, signal: AbortSignal) {
  const query = new URLSearchParams({ scope_type: 'business', scope_id: businessId });
  for (let attempt = 0; attempt < 150; attempt++) {
    signal.throwIfAborted();
    const body = await jsonRequest(`/api/operator/mobile/jobs/${jobId}?${query}`, { headers: headers(), signal });
    if (body.job?.status === 'completed') return body.job.result;
    if (['failed', 'cancelled'].includes(body.job?.status)) throw new Error(body.job.error || 'Обработка остановлена');
    await new Promise<void>((resolve) => window.setTimeout(resolve, 2000));
  }
  throw new Error('Обработка занимает больше времени. Результат доступен в заданиях.');
}

export function OperatorVoiceInput({ businessId, channel, conversationId, disabled, onSubmit, headers = voiceHeaders }: {
  businessId: string; channel: string; conversationId?: string | null; disabled?: boolean;
  onSubmit: (text: string, source: VoiceSubmission) => Promise<void>; headers?: HeadersProvider;
}) {
  const [available, setAvailable] = useState(false);
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [clip, setClip] = useState<Blob | null>(null);
  const [clipUrl, setClipUrl] = useState('');
  const [text, setText] = useState('');
  const [source, setSource] = useState<VoiceSubmission | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const lifetime = useRef(new AbortController());
  const asset = useRef('');
  const fileInput = useRef<HTMLInputElement | null>(null);
  const clearStream = () => { stream.current?.getTracks().forEach((track) => track.stop()); stream.current = null; };
  useEffect(() => {
    const controller = new AbortController(); lifetime.current = controller;
    void jsonRequest(`/api/operator/audio/config?business_id=${encodeURIComponent(businessId)}`, { headers: headers(), signal: controller.signal })
      .then((config) => setAvailable(Boolean(config.input_enabled))).catch(() => setAvailable(false));
    return () => { controller.abort(); if (recorder.current?.state === 'recording') recorder.current.stop(); clearStream(); };
  }, [businessId, channel]);
  useEffect(() => { if (!clip) { setClipUrl(''); return; } const url = URL.createObjectURL(clip); setClipUrl(url); return () => URL.revokeObjectURL(url); }, [clip]);
  useEffect(() => {
    if (!recording) return;
    const timer = window.setInterval(() => setSeconds((value) => value + 1), 1000);
    const stop = window.setTimeout(() => recorder.current?.stop(), 120000);
    return () => { window.clearInterval(timer); window.clearTimeout(stop); };
  }, [recording]);
  const cancel = () => {
    if (recorder.current?.state === 'recording') recorder.current.stop(); clearStream();
    lifetime.current.abort(); lifetime.current = new AbortController();
    if (asset.current) void jsonRequest(`/api/operator/audio/${asset.current}/cancel`, { method: 'POST', headers: headers() }).catch(() => undefined);
    asset.current = ''; setClip(null); setSource(null); setText(''); setBusy(false); setRecording(false);
  };
  const start = async () => {
    setError(''); const signal = lifetime.current.signal;
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') throw new Error('Микрофон недоступен. Загрузите аудиофайл или напишите текст.');
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (signal.aborted) { media.getTracks().forEach((track) => track.stop()); return; }
      stream.current = media;
      const mimeType = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus'].find((mime) => MediaRecorder.isTypeSupported(mime));
      const next = mimeType ? new MediaRecorder(media, { mimeType }) : new MediaRecorder(media);
      const chunks: Blob[] = []; next.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      next.onstop = () => { clearStream(); if (!signal.aborted) { setClip(new Blob(chunks, { type: next.mimeType })); setRecording(false); } };
      next.onerror = () => { clearStream(); setRecording(false); setError('Запись прервалась. Попробуйте ещё раз.'); };
      recorder.current = next; setSeconds(0); setSource(null); setClip(null); next.start(); setRecording(true);
    } catch (failure) { clearStream(); setError(failure instanceof Error ? failure.message : 'Разрешите доступ к микрофону или загрузите аудио.'); }
  };
  const transcribe = async () => {
    if (!clip || busy) return;
    if (clip.size > 10 * 1024 * 1024) { setError('Максимальный размер — 10 МБ'); return; }
    setBusy(true); setError(''); const signal = lifetime.current.signal;
    try {
      const form = new FormData(); form.append('file', clip, 'recording'); form.append('business_id', businessId);
      form.append('channel', channel); form.append('request_id', crypto.randomUUID());
      if (conversationId) form.append('conversation_id', conversationId);
      const queued = await jsonRequest('/api/operator/audio/transcriptions', { method: 'POST', headers: headers(), body: form, signal });
      asset.current = queued.asset_id;
      const result = await waitJob(queued.job_id, businessId, headers, signal);
      if (signal.aborted) return;
      setText(result.transcript); setSource({ transcription_id: queued.asset_id, conversation_id: queued.conversation_id, request_id: `voice:${queued.asset_id}` });
    } catch (failure) { if (!signal.aborted) setError(failure instanceof Error ? failure.message : 'Ошибка распознавания'); }
    finally { if (!signal.aborted) setBusy(false); }
  };
  if (!available) return null;
  return <div className="space-y-2" aria-label="Голосовая команда">
    {!clip && !source && <div className="flex flex-wrap items-center gap-2">
      <Button type="button" variant="outline" disabled={disabled || busy} onClick={() => recording ? recorder.current?.stop() : void start()}>
        {recording ? <Square className="mr-2 h-4 w-4" /> : <Mic className="mr-2 h-4 w-4" />}{recording ? `Остановить · ${seconds} с` : 'Записать голосом'}
      </Button>
      <Button type="button" variant="outline" disabled={disabled || busy || recording} onClick={() => fileInput.current?.click()}>Загрузить аудио</Button>
      <input ref={fileInput} className="sr-only" aria-label="Загрузить аудио" type="file" accept="audio/*,.webm,.m4a" disabled={disabled || busy || recording} onChange={(event) => { setSource(null); setClip(event.target.files?.[0] || null); }} />
    </div>}
    {clipUrl && <audio controls src={clipUrl} preload="metadata" />}
    {clip && !source && <Button type="button" disabled={busy || disabled} onClick={() => void transcribe()}>{busy ? 'Распознаю…' : 'Распознать запись'}</Button>}
    {source && <div className="space-y-2"><label className="block text-sm">Проверьте команду<textarea className="block w-full rounded-md border bg-background p-2 text-foreground" value={text} onChange={(event) => setText(event.target.value)} /></label>
      <Button type="button" disabled={disabled || busy || !text.trim()} onClick={async () => { setBusy(true); try { await onSubmit(text, source); setSource(null); setClip(null); asset.current = ''; } catch { setError('Не удалось отправить. Повторите с тем же текстом.'); } finally { setBusy(false); } }}>Отправить Оператору</Button></div>}
    {(clip || recording || busy || source) && <Button type="button" variant="ghost" className="!bg-transparent !text-muted-foreground hover:!bg-muted" onClick={cancel}>Отменить запись</Button>}
    {error && <p role="alert" className="text-sm">{error}</p>}
    <p className="text-xs text-muted-foreground">До 2 минут. Распознавание — Яндекс SpeechKit. Проверьте текст перед отправкой.</p>
  </div>;
}

export function OperatorSpeech({ messageId, businessId, prepare = false, headers = voiceHeaders }: {
  messageId: string; businessId: string; prepare?: boolean; headers?: HeadersProvider;
}) {
  const [available, setAvailable] = useState(false); const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const controller = useRef(new AbortController()); const objectUrl = useRef(''); const started = useRef(false);
  useEffect(() => {
    const next = new AbortController(); controller.current = next;
    void jsonRequest(`/api/operator/audio/config?business_id=${encodeURIComponent(businessId)}`, { headers: headers(), signal: next.signal }).then((config) => setAvailable(Boolean(config.output_enabled))).catch(() => undefined);
    return () => { next.abort(); URL.revokeObjectURL(objectUrl.current); };
  }, [businessId, messageId]);
  const load = async () => {
    if (busy || url) return; setBusy(true); setError(''); const signal = controller.current.signal;
    try {
      const queued = await jsonRequest(`/api/operator/messages/${messageId}/speech`, { method: 'POST', headers: headers(), signal });
      const result = await waitJob(queued.job_id, businessId, headers, signal);
      const response = await fetch(result.audio_url, { headers: headers(), signal });
      if (!response.ok) throw new Error('Аудио недоступно');
      const blob = await response.blob(); if (signal.aborted) return;
      objectUrl.current = URL.createObjectURL(blob); setUrl(objectUrl.current);
    } catch (failure) { if (!signal.aborted) setError(failure instanceof Error ? failure.message : 'Озвучивание недоступно'); }
    finally { if (!signal.aborted) setBusy(false); }
  };
  useEffect(() => { if (available && prepare && !started.current) { started.current = true; void load(); } }, [available, prepare]);
  if (!available) return null;
  return <div className="mt-2">{url ? <audio aria-label="Озвученный ответ" controls src={url} /> : <Button type="button" variant="ghost" disabled={busy} onClick={() => void load()}><Volume2 className="mr-2 h-4 w-4" />{busy ? 'Готовлю аудио…' : 'Прослушать'}</Button>}{error && <p role="status" className="text-xs">{error}. Текст ответа сохранён.</p>}</div>;
}
