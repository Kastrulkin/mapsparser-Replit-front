import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ContentPersonalization } from './ContentPersonalization';

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: request } }));
const profile = {version: 3, summary: 'Спокойно', preferences: {business_description: 'Мелиора', audience_description: 'Наши клиенты', editorial_notes: [{id:'fact',kind:'founder_story',text:'История из бота'}]}, examples: []};
beforeEach(() => request.mockReset());
afterEach(() => { vi.unstubAllGlobals(); window.history.replaceState({}, '', '/'); });

it('shares existing bot facts and saves a versioned founder story without replacing notes', async () => {
  request.mockResolvedValueOnce({profile}).mockResolvedValueOnce({profile:{...profile,version:4}});
  render(<ContentPersonalization businessId="meliora" open onOpenChange={vi.fn()} />);
  await screen.findByText('История из бота');
  fireEvent.change(screen.getByLabelText('История основателя'), {target:{value:'Я открыла компанию после десяти лет практики.'}});
  fireEvent.click(screen.getByRole('button',{name:'Как писать'}));
  fireEvent.click(screen.getByRole('button',{name:'Сохранить'}));
  await screen.findByText(/Сохранено для будущих текстов/);
  expect(JSON.parse(request.mock.calls[1][1].body)).toEqual({business_id:'meliora',expected_version:3,summary:'Спокойно',preferences:{business_description:'Мелиора',audience_description:'Наши клиенты'},founder_story:'Я открыла компанию после десяти лет практики.',confirm:true});
});

it.each(['telegram','max'])('uses only the %s mini-app session for shared settings', async platform => {
  window.history.replaceState({}, '', `/${platform}/control`);
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({profile}),{status:200}));
  vi.stubGlobal('fetch',fetch);
  const headers = () => ({Authorization:'Bearer mini-session'});
  render(<ContentPersonalization businessId="meliora" open onOpenChange={vi.fn()} headers={headers} />);
  await screen.findByText('История из бота');
  expect(fetch.mock.calls[0][0]).toBe('/api/content-voice?business_id=meliora');
  expect(fetch.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer mini-session');
  expect(request).not.toHaveBeenCalled();
});

it('keeps a typed edit after a conflict and never pretends it was saved', async () => {
  request.mockResolvedValueOnce({profile}).mockRejectedValueOnce(new Error('Настройки изменились в другом окне'));
  render(<ContentPersonalization businessId="meliora" open onOpenChange={vi.fn()} />);
  await screen.findByText('История из бота');
  fireEvent.change(screen.getByLabelText('История основателя'),{target:{value:'Не терять этот текст'}});
  fireEvent.click(screen.getByRole('button',{name:'Как писать'}));
  fireEvent.click(screen.getByRole('button',{name:'Сохранить'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('другом окне');
  fireEvent.click(screen.getByRole('button',{name:'О бизнесе'}));
  expect(screen.getByLabelText('История основателя')).toHaveValue('Не терять этот текст');
});

it('discards a late response and private facts after switching business', async () => {
  let finish: (value: unknown) => void = () => {};
  request.mockReturnValueOnce(new Promise(resolve => {finish=resolve;})).mockResolvedValueOnce({profile:{version:1,summary:'Другой стиль',preferences:{business_description:'Другой бизнес'}}});
  const view=render(<ContentPersonalization businessId="old" open onOpenChange={vi.fn()} />);
  view.rerender(<ContentPersonalization businessId="new" open onOpenChange={vi.fn()} />);
  await waitFor(() => expect(screen.getByLabelText('Что важно знать о бизнесе')).toHaveValue('Другой бизнес'));
  await act(async () => finish({profile}));
  expect(screen.queryByText('История из бота')).not.toBeInTheDocument();
});

it('clears private facts when access is revoked during a save', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({profile}),{status:200})).mockResolvedValueOnce(new Response(JSON.stringify({error:'Доступ отозван'}),{status:403}));
  vi.stubGlobal('fetch',fetch);
  const headers=()=>({Authorization:'Bearer mini-session'});
  render(<ContentPersonalization businessId="meliora" open onOpenChange={vi.fn()} headers={headers} />);
  await screen.findByText('История из бота');
  fireEvent.click(screen.getByRole('button',{name:'Как писать'}));
  fireEvent.click(screen.getByRole('button',{name:'Сохранить'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Доступ отозван');
  expect(screen.queryByText('История из бота')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Как должны звучать тексты')).not.toBeInTheDocument();
});
