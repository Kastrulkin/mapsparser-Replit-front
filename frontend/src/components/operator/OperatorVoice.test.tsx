import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
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

it('requires review and sends corrected transcript once', async () => {
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
  const review = await screen.findByLabelText('Проверьте команду');
  expect(submit).not.toHaveBeenCalled();
  await user.clear(review); await user.type(review, 'Цена 1500');
  await user.click(screen.getByText('Отправить Оператору'));
  expect(submit).toHaveBeenCalledExactlyOnceWith('Цена 1500', { transcription_id: 'a', conversation_id: 'c', request_id: 'voice:a' });
});

it('keeps text available when synthesis fails and never calls chat', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => String(input).includes('/config') ? reply({ output_enabled: true }) : reply({ error: 'Сервис недоступен' }, 400));
  vi.stubGlobal('fetch', fetchMock);
  const user = userEvent.setup();
  render(<div>Пост подготовлен<OperatorSpeech businessId="b" messageId="m" headers={headers} /></div>);
  await user.click(await screen.findByText('Прослушать'));
  expect(await screen.findByText(/Текст ответа сохранён/)).toBeInTheDocument();
  expect(screen.getByText('Пост подготовлен')).toBeInTheDocument();
  expect(fetchMock.mock.calls.every(([input]) => !String(input).endsWith('/chat'))).toBe(true);
});
