import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { CompiledScriptBuilder } from './CompiledScriptBuilder';

vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn() } }));

describe('CompiledScriptBuilder', () => {
  beforeEach(() => { vi.mocked(newAuth.makeRequest).mockReset(); });
  it('does not compile on mount and sends an explicit user fixture', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ success: true, candidate_version: { id: 'v-1' }, artifact: { source: 'def run(): pass' } });
    render(<CompiledScriptBuilder blueprintId="bp-1" />);
    expect(newAuth.makeRequest).not.toHaveBeenCalled();
    const fields = screen.getAllByRole('textbox');
    fireEvent.change(fields[0], { target: { value: 'Проверять строки' } });
    fireEvent.change(fields[2], { target: { value: '{"row": 1}' } });
    fireEvent.change(fields[3], { target: { value: '{"valid": true}' } });
    fireEvent.click(screen.getByRole('button', { name: 'Подготовить скрипт' }));
    await waitFor(() => expect(newAuth.makeRequest).toHaveBeenCalledWith('/agent-blueprints/bp-1/compiled-script/compile', {
      method: 'POST', body: JSON.stringify({ description: 'Проверять строки\n\nПравила:\n', fixtures: [{ input: { row: 1 }, expected: { valid: true }, source: 'user' }] }),
    }));
  });

  it('cannot approve before a successful preview', async () => {
    render(<CompiledScriptBuilder blueprintId="bp-1" />);
    expect(screen.queryByRole('button', { name: 'Подтвердить эту версию' })).not.toBeInTheDocument();
  });

  it('runs only after preview and exact approval, with one idempotent run request', async () => {
    const queued = vi.fn();
    vi.mocked(newAuth.makeRequest)
      .mockResolvedValueOnce({ success: true, candidate_version: { id: 'v-1' }, artifact: { source: 'def run(): pass' } })
      .mockResolvedValueOnce({ success: true, version_id: 'v-1', preview: { status: 'passed', result: { valid: true }, fixture_digest: 'fixture-1', fixture_results: [{ passed: true }] }, approval_digest: 'hash-1' })
      .mockResolvedValueOnce({ success: true, version_id: 'v-1', state: 'approved' })
      .mockResolvedValueOnce({ success: true, run: { id: 'run-1' }, status: 'queued' });
    render(<CompiledScriptBuilder blueprintId="bp-1" onRunQueued={queued} />);
    const fields = screen.getAllByRole('textbox');
    fireEvent.change(fields[0], { target: { value: 'Проверять строки' } });
    fireEvent.change(fields[2], { target: { value: '{"row": 1}' } });
    fireEvent.change(fields[3], { target: { value: '{"valid": true}' } });
    fireEvent.click(screen.getByRole('button', { name: 'Подготовить скрипт' }));
    await screen.findByRole('button', { name: 'Проверить на примере' });
    fireEvent.click(screen.getByRole('button', { name: 'Проверить на примере' }));
    await screen.findByRole('button', { name: 'Подтвердить эту версию' });
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить эту версию' }));
    await screen.findByRole('button', { name: 'Запустить скрипт' });
    fireEvent.change(screen.getByLabelText('Данные для запуска (JSON)'), { target: { value: '{"row": 2}' } });
    fireEvent.click(screen.getByRole('button', { name: 'Запустить скрипт' }));
    await waitFor(() => expect(queued).toHaveBeenCalledWith('run-1'));
    expect(newAuth.makeRequest).toHaveBeenCalledTimes(4);
    expect(vi.mocked(newAuth.makeRequest).mock.calls[3]?.[1]).toEqual({ method: 'POST', body: expect.stringContaining('"row":2') });
  });

  it('hydrates a confirmed active compiled version without calling the model', async () => {
    render(<CompiledScriptBuilder blueprintId="bp-1" blueprintDetails={{ versions: [], runs: [], active_version: { id: 'v-active', compiled_state: 'approved', compiled_artifact_json: { source: 'def run(): pass' } } }} />);
    expect(await screen.findByRole('button', { name: 'Запустить скрипт' })).toBeInTheDocument();
    expect(newAuth.makeRequest).not.toHaveBeenCalled();
  });

  it('keeps an edited hydrated approved candidate invalidated until it is compiled again', async () => {
    render(<CompiledScriptBuilder blueprintId="bp-1" blueprintDetails={{ versions: [], runs: [], candidate_version: { id: 'v-approved', compiled_state: 'approved', compiled_artifact_json: { source: 'def run(): pass' } } }} />);
    expect(await screen.findByRole('button', { name: 'Запустить скрипт' })).toBeInTheDocument();
    fireEvent.click(screen.getByText('Настроить повторяемую задачу'));
    fireEvent.change(screen.getByLabelText('Что должен делать сотрудник?'), { target: { value: 'Проверять новые строки' } });
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Запустить скрипт' })).not.toBeInTheDocument());
    expect(screen.queryByRole('button', { name: 'Проверить на примере' })).not.toBeInTheDocument();
    expect(newAuth.makeRequest).not.toHaveBeenCalled();
  });
});
