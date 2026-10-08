import '@testing-library/jest-dom/vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { OperatorActivity, OperatorReply } from './OperatorActivity';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('reveals a fresh reply and lets the user skip without restarting it', () => {
  const frames: FrameRequestCallback[] = [];
  vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => { frames.push(callback); return frames.length; }));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  render(<OperatorReply text="Условия готовы" animate />);
  expect(screen.getByRole('button', { name: 'Показать сразу' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Показать сразу' }));
  act(() => frames[0](performance.now() + 50));
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
  expect(screen.getAllByText('Условия готовы')).toHaveLength(1);
});

it('shows history and reduced-motion replies immediately', () => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })));
  render(<OperatorReply text="Готово" animate />);
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
  expect(screen.getAllByText('Готово')).toHaveLength(1);
});

it('does not claim server acceptance while the request is in flight', () => {
  const view = render(<OperatorActivity phase="Отправляем команду…" accepted={false} />);
  expect(screen.getByRole('status')).toHaveTextContent('Ждём подтверждения от сервера');
  expect(screen.queryByText(/Команда принята/)).not.toBeInTheDocument();
  view.rerender(<OperatorActivity phase="Команда в очереди · ждёт запуска" accepted />);
  expect(screen.getByRole('status')).toHaveTextContent('Команда принята');
  expect(screen.getByRole('status')).toHaveTextContent('ждёт запуска');
});


it('keeps a long reply visibly typing beyond the old 1.2-second cap', () => {
  const frames: FrameRequestCallback[] = [];
  vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => { frames.push(callback); return frames.length; }));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  vi.spyOn(performance, 'now').mockReturnValue(0);
  const text = 'Подготовлено письмо. '.repeat(30);
  const view = render(<OperatorReply text={text} animate />);
  act(() => frames.shift()?.(1200));
  const revealed = view.container.querySelector('[aria-hidden="true"].notranslate');
  expect(revealed?.textContent?.length).toBeLessThan(60);
  expect(screen.getByRole('button', { name: 'Показать сразу' })).toBeInTheDocument();
  act(() => frames.shift()?.(15000));
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
  vi.restoreAllMocks();
});

it('gives short replies a noticeable reveal instead of flashing them', () => {
  const frames: FrameRequestCallback[] = [];
  vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => { frames.push(callback); return frames.length; }));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  vi.spyOn(performance, 'now').mockReturnValue(0);
  render(<OperatorReply text="Готово" animate />);
  act(() => frames.shift()?.(400));
  expect(screen.getByRole('button', { name: 'Показать сразу' })).toBeInTheDocument();
  act(() => frames.shift()?.(800));
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
  vi.restoreAllMocks();
});
