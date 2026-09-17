import { Button } from '@/components/ui/button';
import { useLatestCallback } from '@/hooks/useLatestCallback';
import { Mic, Square } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { jsonRequest, voiceHeaders, type HeadersProvider } from './OperatorVoice.logic';

export type VoiceSubmission = { transcription_id: string; conversation_id: string; request_id: string };
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

export function OperatorVoiceInput({ businessId, channel, conversationId, disabled, directSubmit = true, onSubmit, headers = voiceHeaders }: {
  businessId: string; channel: string; conversationId?: string | null; disabled?: boolean; directSubmit?: boolean;
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
  const [delayed, setDelayed] = useState(false);
  const [showExamples,setShowExamples]=useState(()=>sessionStorage.getItem('localos-voice-examples-hidden')!=='true');
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const lifetime = useRef(new AbortController());
  const asset = useRef('');
  const fileInput = useRef<HTMLInputElement | null>(null);
  const onSubmitRef = useRef(onSubmit); onSubmitRef.current = onSubmit;
  const pendingKey = `localos-voice:${channel}:${businessId}`;
  useEffect(() => {
    if (!busy) { setDelayed(false); return; }
    const timer=window.setTimeout(()=>setDelayed(true),15000);
    return ()=>window.clearTimeout(timer);
  },[busy]);
  const clearStream = () => { stream.current?.getTracks().forEach((track) => track.stop()); stream.current = null; };
  useEffect(() => {
    const controller = new AbortController(); lifetime.current = controller;
    void jsonRequest(`/api/operator/audio/config?business_id=${encodeURIComponent(businessId)}`, { headers: headers(), signal: controller.signal })
      .then((config) => setAvailable(Boolean(config.input_enabled))).catch(() => setAvailable(false));
    return () => { controller.abort(); if (recorder.current?.state === 'recording') recorder.current.stop(); clearStream(); };
  }, [businessId, channel, headers]);
  useEffect(() => {
    const signal=lifetime.current.signal;
    const saved=sessionStorage.getItem(pendingKey);
    if (!saved) return;
    async function restore() {
      try {
        const pending = JSON.parse(saved || '{}');
        if (!pending.job_id || !pending.asset_id || !pending.conversation_id) { sessionStorage.removeItem(pendingKey); return; }
        setBusy(true); asset.current=pending.asset_id;
        const result=await waitJob(pending.job_id,businessId,headers,signal);
        if(signal.aborted)return;
        const submission={transcription_id:pending.asset_id,conversation_id:pending.conversation_id,request_id:`voice:${pending.asset_id}`};
        setText(result.transcript);setSource(submission);
        await onSubmitRef.current(result.transcript,submission);
        if(!signal.aborted){sessionStorage.removeItem(pendingKey);setSource(null);asset.current='';}
      } catch(failure) { if(!signal.aborted)setError(failure instanceof Error ? failure.message:'Не удалось восстановить задание'); }
      finally { if(!signal.aborted)setBusy(false); }
    }
    void restore();
  },[pendingKey, businessId, headers]);
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
    sessionStorage.removeItem(pendingKey);
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
      sessionStorage.setItem(pendingKey,JSON.stringify({job_id:queued.job_id,asset_id:queued.asset_id,conversation_id:queued.conversation_id}));
      const result = await waitJob(queued.job_id, businessId, headers, signal);
      if (signal.aborted) return;
      const submission = { transcription_id: queued.asset_id, conversation_id: queued.conversation_id, request_id: `voice:${queued.asset_id}` };
      setText(result.transcript); setSource(submission);
      if (directSubmit || result.auto_submit_finance || result.auto_submit_work) {
        await onSubmit(result.transcript, submission);
        if (!signal.aborted) { sessionStorage.removeItem(pendingKey); setSource(null); setClip(null); asset.current = ''; }
      }
    } catch (failure) { if (!signal.aborted) setError(failure instanceof Error ? failure.message : 'Ошибка распознавания'); }
    finally { if (!signal.aborted) setBusy(false); }
  };
  if (!available) return null;
  return <div className="space-y-2" aria-label="Голосовая команда">
    {showExamples && <div className="text-sm text-muted-foreground"><p>Можно сказать: «Покажи ближайший пост», «Запомни для будущих текстов: …», «Есть пожелание клиента: …».</p><Button type="button" variant="ghost" onClick={()=>{sessionStorage.setItem('localos-voice-examples-hidden','true');setShowExamples(false);}}>Скрыть подсказки</Button></div>}
    {!clip && !source && <div className="flex flex-wrap items-center gap-2">
      <Button type="button" variant="outline" disabled={disabled || busy} onClick={() => recording ? recorder.current?.stop() : void start()}>
        {recording ? <Square className="mr-2 h-4 w-4" /> : <Mic className="mr-2 h-4 w-4" />}{recording ? `Остановить · ${seconds} с` : 'Записать голосом'}
      </Button>
      <Button type="button" variant="outline" disabled={disabled || busy || recording} onClick={() => fileInput.current?.click()}>Загрузить аудио</Button>
      <input ref={fileInput} className="sr-only" aria-label="Загрузить аудио" type="file" accept="audio/*,.webm,.m4a" disabled={disabled || busy || recording} onChange={(event) => { setSource(null); setClip(event.target.files?.[0] || null); }} />
    </div>}
    {clipUrl && <audio controls src={clipUrl} preload="metadata" />}
    {clip && !source && <Button type="button" disabled={busy || disabled} onClick={() => void transcribe()}>{busy ? 'Распознаю…' : 'Распознать запись'}</Button>}
    {text && !source && <p role="status" className="text-sm">Распознано: {text}</p>}
    {source && <div className="space-y-2"><label className="block text-sm">{busy ? 'Распознано' : 'Команда'}<textarea disabled={busy} className="block w-full rounded-md border bg-background p-2 text-foreground" value={text} onChange={(event) => setText(event.target.value)} /></label>
      {!busy && <Button type="button" disabled={disabled || !text.trim()} onClick={async () => { setBusy(true); try { await onSubmit(text, source); setSource(null); setClip(null); asset.current = ''; } catch { setError('Не удалось отправить. Повторите с тем же текстом.'); } finally { setBusy(false); } }}>Повторить отправку</Button>}</div>}
    {(clip || recording || busy || source) && !(busy && source) && <Button type="button" variant="ghost" className="!bg-transparent !text-muted-foreground hover:!bg-muted" onClick={cancel}>Отменить запись</Button>}
    {busy && <p role="status">{delayed && asset.current ? 'Задание сохранено, ещё выполняется. Повторять сообщение не нужно.' : source ? 'Обрабатываю команду…' : 'Распознаю запись…'}</p>}
    {error && <p role="alert" className="text-sm">{error}</p>}
    <p className="text-xs text-muted-foreground">До 2 минут. Распознавание — Яндекс SpeechKit. Рабочая заметка сохранится с возможностью отмены. Финансовые записи и публикации потребуют подтверждения.</p>
  </div>;
}

export function OperatorSpeech({ messageId, businessId, prepare = false, headers = voiceHeaders }: {
  messageId: string; businessId: string; prepare?: boolean; headers?: HeadersProvider;
}) {
  const [available, setAvailable] = useState(false); const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const controller = useRef(new AbortController()); const objectUrl = useRef(''); const started = useRef(false);
  useEffect(() => {
    const next = new AbortController(); controller.current = next;
    void jsonRequest(`/api/operator/audio/config?business_id=${encodeURIComponent(businessId)}`, { headers: headers(), signal: next.signal }).then((config) => setAvailable(Boolean(config.output_enabled))).catch(() => undefined);
    return () => { next.abort(); URL.revokeObjectURL(objectUrl.current); };
  }, [businessId, messageId, headers]);
  const load = useLatestCallback(async () => {
    if (busy || url) return; setBusy(true); const signal = controller.current.signal;
    try {
      const queued = await jsonRequest(`/api/operator/messages/${messageId}/speech`, { method: 'POST', headers: headers(), signal });
      const result = await waitJob(queued.job_id, businessId, headers, signal);
      const response = await fetch(result.audio_url, { headers: headers(), signal });
      if (!response.ok) throw new Error('Аудио недоступно');
      const blob = await response.blob(); if (signal.aborted) return;
      objectUrl.current = URL.createObjectURL(blob); setUrl(objectUrl.current);
    } catch { /* Keep the text reply and allow retry with the listen button. */ }
    finally { if (!signal.aborted) setBusy(false); }
  });
  useEffect(() => { if (available && prepare && !started.current) { started.current = true; void load(); } }, [available, prepare, load]);
  if (!available || !url) return null;
  return <div className="mt-2"><audio aria-label="Озвученный ответ" controls src={url} /></div>;
}
