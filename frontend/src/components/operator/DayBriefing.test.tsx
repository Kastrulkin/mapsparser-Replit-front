import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DayBriefing } from './DayBriefing';
vi.mock('./OperatorVoice', () => ({ OperatorVoiceInput: ({ onSubmit }: { onSubmit: (text: string, source: object) => void }) => <button onClick={() => onSubmit('Голосовой фокус дня', { transcription_id: 'voice', conversation_id: 'audio-conversation', request_id: 'voice-request' })}>Надиктовать фокус</button> }));
vi.mock('@/components/telegram/WorkDiscussion', () => ({ WorkDiscussion: () => <p>Продолжить в боте</p> }));
const headers = () => ({ Authorization: 'Bearer fixture' });
let calls: { path: string; body: Record<string, unknown> }[];
let current = { id: 'record', focus: '', date: '2026-10-17', version: 0, status: 'draft', recipients: [] };
const overview = { date: '2026-10-17', user_id: 'owner', can_manage: true, can_complete: true, delivery_enabled: false, draft: null,
  members: [{ id: 'employee', name: 'Анна', platforms: ['telegram', 'max'] }], assignments: [] };
beforeEach(() => {
  calls = []; current = { id: 'record', focus: '', date: '2026-10-17', version: 0, status: 'draft', recipients: [] };
  vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
    const path = String(input); const body = init?.body ? JSON.parse(String(init.body)) : {};
    if (init?.method === 'POST') calls.push({ path, body });
    let value: unknown = overview;
    if (path.endsWith('/day-brief') && init?.method === 'POST') { current = { ...current, ...body, version: 1 }; value = { draft: current }; }
    if (path.endsWith('/preview')) value = { approval: { action_id: 'approval' }, day_brief_preview: { delivery_enabled: false, messages: [{ user_id: 'employee', name: 'Анна', platforms: ['telegram'], text: 'Точный текст сотруднику. Перед предложением проверьте свободное время.' }] } };
    if (path.endsWith('/confirm')) value = { operator_result: { status: 'completed', chat_response: 'Задачи доступны в кабинете. Уведомления выключены.' } };
    return new Response(JSON.stringify(value), { status: 200 });
  }));
});

describe('DayBriefing', () => {
  it.each(['telegram_mini_app','max_mini_app'])('%s: assigns cabinet-only work to a member without a messenger after review',async channel=>{
    const original=vi.mocked(fetch).getMockImplementation();
    vi.mocked(fetch).mockImplementation(async(input,init)=>{
      if (!init?.method || init.method==='GET') return new Response(JSON.stringify({...overview,delivery_enabled:true,members:[{id:'employee',name:'Анна',platforms:[]}]}));
      if(String(input).endsWith('/preview')) {
        calls.push({path:String(input),body:JSON.parse(String(init.body))});
        return new Response(JSON.stringify({approval:{action_id:'approval'},day_brief_preview:{delivery_enabled:true,messages:[{user_id:'employee',name:'Анна',platforms:[],text:'Проверить тестовое окно'}]}}));
      }
      return original!(input,init);
    });
    render(<DayBriefing businessId="business" channel={channel} headers={headers}/>);
    const member=await screen.findByRole('checkbox',{name:'Анна'});
    expect(member).toBeEnabled();
    fireEvent.change(screen.getByLabelText('Фокус дня'),{target:{value:'Проверить тестовое окно'}});
    fireEvent.click(member);
    fireEvent.click(screen.getByRole('button',{name:'Проверить перед передачей'}));
    await screen.findByRole('button',{name:'Подтвердить передачу задач'});
    expect(calls.find(call=>call.path.endsWith('/day-brief'))?.body.recipients).toEqual([{user_id:'employee',platforms:[],tasks:[{text:'Проверить тестовое окно'}]}]);
    expect(screen.getByRole('region',{name:'Проверка планёрки'})).toHaveTextContent('Кабинет LocalOS');
    expect(screen.getByRole('region',{name:'Проверка планёрки'})).not.toHaveTextContent('Уведомления будут поставлены');
    expect(calls.some(call=>call.path.endsWith('/confirm'))).toBe(false);
    fireEvent.click(screen.getByRole('button',{name:'Подтвердить передачу задач'}));
    await waitFor(()=>expect(calls.filter(call=>call.path.endsWith('/confirm'))).toHaveLength(1));
  });
  for (const channel of ['telegram_mini_app', 'max_mini_app']) it(channel + ': voice draft requires recipient review and explicit approval', async () => {
    render(<DayBriefing businessId="business" channel={channel} headers={headers} />);
    await screen.findByText('Анна');
    fireEvent.click(screen.getByRole('button', { name: 'Надиктовать фокус' }));
    expect(screen.getByLabelText('Фокус дня')).toHaveValue('Голосовой фокус дня');
    expect(calls).toHaveLength(0);
    fireEvent.click(screen.getByLabelText('Анна'));
    fireEvent.click(screen.getByRole('button', { name: 'Проверить перед передачей' }));
    await screen.findByRole('button', { name: 'Подтвердить передачу задач' });
    expect(calls.map(call => call.path)).toEqual(['/api/operator/day-brief', '/api/operator/day-brief/preview']);
    expect(calls[0].body).toMatchObject({ transcription_id: 'voice', channel, business_id: 'business' });
    expect(screen.getByText(/Точный текст сотруднику/)).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить передачу задач' }));
    await screen.findByText('Задачи доступны в кабинете. Уведомления выключены.');
    expect(calls.filter(call => call.path.endsWith('/confirm'))).toHaveLength(1);
  });
  it('editing invalidates the visible approval and retains the new focus', async () => {
    render(<DayBriefing businessId="business" channel="web" headers={headers} />);
    await screen.findByText('Анна');
    fireEvent.change(screen.getByLabelText('Фокус дня'), { target: { value: 'Первый фокус' } });
    fireEvent.click(screen.getByLabelText('Анна'));
    fireEvent.click(screen.getByRole('button', { name: 'Проверить перед передачей' }));
    await screen.findByRole('button', { name: 'Подтвердить передачу задач' });
    fireEvent.change(screen.getByLabelText('Фокус дня'), { target: { value: 'Исправленный фокус' } });
    expect(screen.queryByRole('button', { name: 'Подтвердить передачу задач' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Фокус дня')).toHaveValue('Исправленный фокус');
  });
  it('employees see only assigned work and can mark a task done', async () => {
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      if (init?.method === 'POST') { calls.push({ path: String(input), body: JSON.parse(String(init.body)) }); return new Response('{}'); }
      return new Response(JSON.stringify({ ...overview, user_id: 'employee', can_manage: false, members: [], assignments: [{ id: 'task', user_id: 'employee', version: 1, status: 'ready', payload_json: { date: '2026-10-17', focus: 'Качество встречи', tasks: [{ id: 'one', text: 'Подготовить материалы', done: false }], tips: [], note: 'Связки не настроены.' } }] }));
    });
    render(<DayBriefing businessId="business" channel="max_mini_app" headers={headers} />);
    await screen.findByText('Подготовить материалы');
    expect(screen.queryByLabelText('Фокус дня')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox'));
    await waitFor(() => expect(calls[0].body).toMatchObject({ action_id: 'task', task_id: 'one', done: true, version: 1 }));
  });
  it('failed save preserves dictation and never confirms or sends', async () => {
    const original = vi.mocked(fetch).getMockImplementation();
    vi.mocked(fetch).mockImplementation(async (input, init) => init?.method === 'POST' ? new Response(JSON.stringify({ error: 'Нет сети. Повторите.' }), { status: 503 }) : original!(input, init));
    render(<DayBriefing businessId="business" channel="web" headers={headers} />);
    await screen.findByText('Анна');
    fireEvent.change(screen.getByLabelText('Фокус дня'), { target: { value: 'Не терять этот фокус' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    await screen.findByRole('alert');
    expect(screen.getByLabelText('Фокус дня')).toHaveValue('Не терять этот фокус');
    expect(calls).toHaveLength(0);
  });
});

it('a conflicting edit keeps local text until the owner explicitly loads the saved version', async () => {
  let version = 1;
  vi.mocked(fetch).mockImplementation(async (_input, init) => {
    if (init?.method === 'POST') { version = 2; return new Response(JSON.stringify({ error: 'Планёрка уже изменена. Обновите её перед сохранением.' }), { status: 400 }); }
    return new Response(JSON.stringify({ ...overview, draft: { id: 'record', version, focus: version === 1 ? 'Первый фокус' : 'Правка из бота', date: '2026-10-17', status: 'draft', recipients: [] } }));
  });
  render(<DayBriefing businessId="business" channel="max_mini_app" headers={headers} />);
  await waitFor(() => expect(screen.getByLabelText('Фокус дня')).toHaveValue('Первый фокус'));
  fireEvent.change(screen.getByLabelText('Фокус дня'), { target: { value: 'Несохранённые правки' } });
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
  await screen.findByRole('alert');
  expect(screen.getByLabelText('Фокус дня')).toHaveValue('Несохранённые правки');
  fireEvent.click(screen.getByText('Если планёрка изменена в другом окне'));
  fireEvent.click(screen.getByRole('button', { name: 'Загрузить сохранённую версию' }));
  await waitFor(() => expect(screen.getByLabelText('Фокус дня')).toHaveValue('Правка из бота'));
});

it('keeps the focus and recipient after an internal failure without exposing database internals',async()=>{
  vi.stubGlobal('fetch',vi.fn(async (_input:string,init?:RequestInit)=>init?.method==='POST'
    ? new Response(JSON.stringify({error:'SQL private_internal_table constraint'}),{status:500})
    : new Response(JSON.stringify(overview),{status:200})));
  render(<DayBriefing businessId="business" channel="max_mini_app" headers={headers}/>);
  await screen.findByText('Анна');
  fireEvent.change(screen.getByLabelText('Фокус дня'),{target:{value:'Проверить окна'}});
  fireEvent.click(screen.getByLabelText('Анна'));
  fireEvent.click(screen.getByRole('button',{name:'Проверить перед передачей'}));
  const error=await screen.findByRole('alert');
  expect(error).toHaveTextContent('Данные остались в форме');
  expect(error).not.toHaveTextContent('private_internal_table');
  expect(screen.getByLabelText('Фокус дня')).toHaveValue('Проверить окна');
  expect(screen.getByLabelText('Анна')).toBeChecked();
});
