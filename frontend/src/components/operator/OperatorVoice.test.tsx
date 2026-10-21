import '@testing-library/jest-dom/vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { OperatorVoiceInput, OperatorSpeech } from './OperatorVoice';

const headers = () => ({ Authorization: 'Bearer test' });
const reply = (value: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('does not show recording when voice is disabled', async () => {
  vi.stubGlobal('fetch', vi.fn(() => reply({ input_enabled: false })));
  render(<OperatorVoiceInput businessId="b" channel="web" onSubmit={vi.fn()} headers={headers} />);
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(screen.queryByText('Записать голосом')).not.toBeInTheDocument();
});

it('submits a general voice command once without a review step', async () => {
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:recording'), revokeObjectURL: vi.fn() }));
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/config')) return reply({ input_enabled: true });
    if (url.includes('/transcriptions')) return reply({ asset_id: 'a', job_id: 'j', conversation_id: 'c' }, 202);
    return reply({ job: { status: 'completed', result: { transcript: 'Цена 500' } } });
  });
  vi.stubGlobal('fetch', fetchMock);
  const submit = vi.fn(() => Promise.resolve()); const user = userEvent.setup();
  render(<OperatorVoiceInput businessId="b" channel="telegram_mini_app" onSubmit={submit} headers={headers} />);
  await user.upload(await screen.findByLabelText('Загрузить аудио'), new File(['voice'], 'voice.ogg', { type: 'audio/ogg' }));
  await user.click(screen.getByText('Распознать запись'));
  await waitFor(() => expect(submit).toHaveBeenCalledExactlyOnceWith('Цена 500', { transcription_id: 'a', conversation_id: 'c', request_id: 'voice:a' }));
  expect(screen.queryByText('Отправить Оператору')).not.toBeInTheDocument();
});

it('keeps text available when synthesis fails and never calls chat', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => String(input).includes('/config') ? reply({ output_enabled: true }) : reply({ error: 'Сервис недоступен' }, 400));
  vi.stubGlobal('fetch', fetchMock);
  render(<div>Пост подготовлен<OperatorSpeech businessId="b" messageId="m" prepare headers={headers} /></div>);
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(screen.queryByText('Прослушать')).not.toBeInTheDocument();
  expect(screen.queryByText(/Текст ответа сохранён|Сервис недоступен|Озвучивание недоступно/)).not.toBeInTheDocument();
  expect(screen.getByText('Пост подготовлен')).toBeInTheDocument();
  expect(fetchMock.mock.calls.every(([input]) => !String(input).endsWith('/chat'))).toBe(true);
});

it.each(['web', 'telegram_mini_app'])('sends financial transcription directly to the approval flow in %s', async (channel) => {
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:recording'), revokeObjectURL: vi.fn() }));
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    if (String(input).includes('/config')) return reply({ input_enabled: true });
    if (String(input).includes('/transcriptions')) return reply({ asset_id: 'a', job_id: 'j', conversation_id: 'c' }, 202);
    return reply({ job: { status: 'completed', result: { transcript: '10 продаж, выручка 350 евро', auto_submit_finance: true } } });
  }));
  const submit = vi.fn(() => Promise.resolve()); const user = userEvent.setup();
  render(<OperatorVoiceInput businessId="b" channel={channel} onSubmit={submit} headers={headers} />);
  await user.upload(await screen.findByLabelText('Загрузить аудио'), new File(['voice'], 'voice.ogg', { type: 'audio/ogg' }));
  await user.click(screen.getByText('Распознать запись'));
  await waitFor(() => expect(submit).toHaveBeenCalledExactlyOnceWith('10 продаж, выручка 350 евро', { transcription_id: 'a', conversation_id: 'c', request_id: 'voice:a' }));
  expect(screen.queryByText('Отправить Оператору')).not.toBeInTheDocument();
});

it.each(['auto_submit_work', 'auto_submit_finance'])('keeps a daily focus for review despite %s', async flag => {
  sessionStorage.clear();
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:recording'), revokeObjectURL: vi.fn() }));
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    if (String(input).includes('/config')) return reply({ input_enabled: true });
    if (String(input).includes('/transcriptions')) return reply({ asset_id: 'daily-a', job_id: 'daily-j', conversation_id: 'daily-c' }, 202);
    return reply({ job: { status: 'completed', result: { transcript: 'Сегодня предлагаем подходящий уход', [flag]: true } } });
  }));
  const submit=vi.fn(()=>Promise.resolve());const user=userEvent.setup();
  render(<OperatorVoiceInput businessId="daily-business" channel="telegram_mini_app" contextKey="day_brief" directSubmit={false} submitLabel="Вставить в фокус дня" draftLabel="Распознанный фокус" onSubmit={submit} headers={headers} />);
  await user.upload(await screen.findByLabelText('Загрузить аудио'),new File(['audio'],'daily.ogg',{type:'audio/ogg'}));
  await user.click(screen.getByText('Распознать запись'));
  await screen.findByLabelText('Распознанный фокус');
  expect(submit).not.toHaveBeenCalled();
  await user.click(screen.getByText('Вставить в фокус дня'));
  expect(submit).toHaveBeenCalledExactlyOnceWith('Сегодня предлагаем подходящий уход',{transcription_id:'daily-a',conversation_id:'daily-c',request_id:'voice:daily-a'});
  expect(sessionStorage.getItem('localos-voice:telegram_mini_app:daily-business:day_brief')).toBeNull();
});

it('restores interrupted daily transcription for explicit review without submitting', async()=>{
 sessionStorage.clear();
 sessionStorage.setItem('localos-voice:telegram_mini_app:daily-business:day_brief',JSON.stringify({asset_id:'restored-a',job_id:'restored-j',conversation_id:'restored-c'}));
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>String(input).includes('/config')?reply({input_enabled:true}):reply({job:{status:'completed',result:{transcript:'Фокус после перезапуска'}}})));
 const submit=vi.fn(()=>Promise.resolve());
 render(<OperatorVoiceInput businessId="daily-business" channel="telegram_mini_app" contextKey="day_brief" directSubmit={false} draftLabel="Распознанный фокус" onSubmit={submit} headers={headers}/>);
 expect(await screen.findByLabelText('Распознанный фокус')).toHaveValue('Фокус после перезапуска');
 expect(submit).not.toHaveBeenCalled();
});

it('does not restore a general chat recording into daily briefing',async()=>{
 sessionStorage.clear();sessionStorage.setItem('localos-voice:telegram_mini_app:daily-business',JSON.stringify({asset_id:'chat-a',job_id:'chat-j',conversation_id:'chat-c'}));
 const fetchMock=vi.fn(()=>reply({input_enabled:true}));vi.stubGlobal('fetch',fetchMock);
 const submit=vi.fn(()=>Promise.resolve());
 render(<OperatorVoiceInput businessId="daily-business" channel="telegram_mini_app" contextKey="day_brief" directSubmit={false} onSubmit={submit} headers={headers}/>);
 await screen.findByLabelText('Загрузить аудио');expect(fetchMock).toHaveBeenCalledTimes(1);expect(submit).not.toHaveBeenCalled();
});


it.each(['telegram_mini_app', 'max_mini_app'])('explains denied microphone access without leaking browser errors in %s', async channel => {
  sessionStorage.clear();
  vi.stubGlobal('fetch', vi.fn(() => reply({ input_enabled: true })));
  vi.stubGlobal('MediaRecorder', vi.fn());
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia: vi.fn().mockRejectedValue(new DOMException('Permission denied by system', 'NotAllowedError')) } });
  const submit=vi.fn(()=>Promise.resolve());
  const user=userEvent.setup();
  render(<OperatorVoiceInput businessId="denied-mic" channel={channel} directSubmit={false} onSubmit={submit} headers={headers}/>);
  await user.click(await screen.findByRole('button',{name:'Записать голосом'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Нет доступа к микрофону');
  expect(screen.getByRole('alert')).toHaveTextContent('загрузите аудиофайл');
  expect(screen.getByRole('alert')).not.toHaveTextContent('Permission denied');
  expect(screen.getByRole('button',{name:'Загрузить аудио'})).toBeEnabled();
  expect(submit).not.toHaveBeenCalled();
  expect(fetch).toHaveBeenCalledTimes(1);
});


it('rechecks the queued transcription instead of uploading the recording twice', async()=>{
 sessionStorage.clear();
 vi.stubGlobal('URL',Object.assign(URL,{createObjectURL:vi.fn(()=>'blob:retry'),revokeObjectURL:vi.fn()}));
 let retried=false;
 const mock=vi.fn((input:RequestInfo|URL)=>{
  const url=String(input);
  if(url.includes('/config'))return reply({input_enabled:true});
  if(url.includes('/transcriptions'))return reply({asset_id:'slow-a',job_id:'slow-j',conversation_id:'slow-c'},202);
  if(url.includes('/retry')){retried=true;return reply({job:{status:'queued'}});}
  return reply({job:retried?{status:'completed',result:{transcript:'Проверяем чистоту окон'}}:{status:'failed',error:'Распознавание ещё не завершено. Повторите проверку'}});
 });
 vi.stubGlobal('fetch',mock);const submit=vi.fn(()=>Promise.resolve());const user=userEvent.setup();
 render(<OperatorVoiceInput businessId="slow-business" channel="telegram_mini_app" directSubmit={false} draftLabel="Распознанный фокус" onSubmit={submit} headers={headers}/>);
 await user.upload(await screen.findByLabelText('Загрузить аудио'),new File(['voice'],'focus.ogg',{type:'audio/ogg'}));
 await user.click(screen.getByRole('button',{name:'Распознать запись'}));
 await screen.findByRole('alert');
 await user.click(screen.getByRole('button',{name:'Проверить распознавание'}));
 expect(await screen.findByLabelText('Распознанный фокус')).toHaveValue('Проверяем чистоту окон');
 expect(mock.mock.calls.filter(([url])=>String(url).includes('/transcriptions'))).toHaveLength(1);
 expect(mock.mock.calls.filter(([url])=>String(url).includes('/retry'))).toHaveLength(1);
 expect(submit).not.toHaveBeenCalled();
});

it.each([false,true])('clears a recording on business switch after cancellation=%s',async cancelFirst=>{
 sessionStorage.clear();
 vi.stubGlobal('URL',Object.assign(URL,{createObjectURL:vi.fn(()=>'blob:scope'),revokeObjectURL:vi.fn()}));
 class Recording {
  static isTypeSupported(){return true;}
  state='inactive';mimeType='audio/webm';ondataavailable:((event:{data:Blob})=>void)|null=null;onstop:(()=>void)|null=null;
  start(){this.state='recording';}
  stop(){this.state='inactive';setTimeout(()=>{this.ondataavailable?.({data:new Blob(['scope recording'])});this.onstop?.();},0);}
 }
 vi.stubGlobal('MediaRecorder',Recording);
 const stop=vi.fn();vi.stubGlobal('navigator',{mediaDevices:{getUserMedia:vi.fn(async()=>({getTracks:()=>[{stop}]}))}});
 const mock=vi.fn(()=>reply({input_enabled:true}));vi.stubGlobal('fetch',mock);
 const submit=vi.fn(async()=>{});const user=userEvent.setup();
 const view=render(<OperatorVoiceInput businessId="first" channel="telegram_mini_app" directSubmit={false} onSubmit={submit} headers={headers}/>);
 await user.click(await screen.findByRole('button',{name:'Записать голосом'}));
 if(cancelFirst){await user.click(screen.getByRole('button',{name:'Отменить запись'}));await user.click(screen.getByRole('button',{name:'Записать голосом'}));}
 view.rerender(<OperatorVoiceInput businessId="other" channel="telegram_mini_app" directSubmit={false} onSubmit={submit} headers={headers}/>);
 await waitFor(()=>expect(screen.queryByRole('button',{name:'Остановить запись'})).not.toBeInTheDocument());
 await screen.findByRole('button',{name:'Записать голосом'});
 expect(screen.queryByRole('button',{name:'Распознать запись'})).not.toBeInTheDocument();
 expect(stop).toHaveBeenCalled();expect(submit).not.toHaveBeenCalled();
 expect(mock.mock.calls.every(([input])=>String(input).includes('/config'))).toBe(true);
});

it('does not let a delayed cancelled recorder stop a newer recording',async()=>{
 sessionStorage.clear();const callbacks:(()=>void)[]=[];
 class Recording {
  static isTypeSupported(){return true;}
  state='inactive';mimeType='audio/webm';ondataavailable:((event:{data:Blob})=>void)|null=null;onstop:(()=>void)|null=null;
  start(){this.state='recording';}
  stop(){this.state='inactive';callbacks.push(()=>{this.ondataavailable?.({data:new Blob(['old'])});this.onstop?.();});}
 }
 vi.stubGlobal('MediaRecorder',Recording);const first=vi.fn();const second=vi.fn();
 vi.stubGlobal('navigator',{mediaDevices:{getUserMedia:vi.fn().mockResolvedValueOnce({getTracks:()=>[{stop:first}]}).mockResolvedValueOnce({getTracks:()=>[{stop:second}]})}});
 vi.stubGlobal('fetch',vi.fn(()=>reply({input_enabled:true})));
 const user=userEvent.setup();render(<OperatorVoiceInput businessId="recording" channel="telegram_mini_app" directSubmit={false} onSubmit={vi.fn()} headers={headers}/>);
 await user.click(await screen.findByRole('button',{name:'Записать голосом'}));await user.click(screen.getByRole('button',{name:'Отменить запись'}));
 await user.click(screen.getByRole('button',{name:'Записать голосом'}));
 await act(async()=>{callbacks.splice(0).forEach(callback=>callback());});
 expect(first).toHaveBeenCalled();expect(second).not.toHaveBeenCalled();
 expect(screen.getByRole('button',{name:'Остановить запись'})).toBeInTheDocument();
});
