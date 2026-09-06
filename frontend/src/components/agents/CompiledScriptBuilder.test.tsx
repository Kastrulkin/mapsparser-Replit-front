import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { CompiledScriptBuilder } from './CompiledScriptBuilder';
import { mapTableColumns, parsePastedTable, reportCsv, tableInputError } from './compiledTable';

vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn() } }));
vi.mock('@/i18n/LanguageContext', () => ({ useLanguage: () => ({ language: 'ru' }) }));

const fixture = 'email\tamount\nanna@example.com\t1500\nanna@example.com\t1500\n\t900';
type PendingCompile = { success?: boolean; candidate_version?: { id?: string }; artifact?: { source?: string } };
type PendingSnapshot = { success?: boolean; snapshot?: { id?: string } };

const prepareVersion = async () => {
  fireEvent.change(screen.getByLabelText(/Вставьте пример таблицы/), { target: { value: fixture } });
  fireEvent.click(screen.getAllByRole('checkbox')[0]);
  fireEvent.click(screen.getAllByRole('checkbox')[2]);
  fireEvent.change(screen.getByLabelText(/Подтвердите ожидаемый результат: 2/), { target: { value: 'duplicate' } });
  fireEvent.change(screen.getByLabelText(/Подтвердите ожидаемый результат: 3/), { target: { value: 'missing' } });
  fireEvent.click(screen.getByRole('button', { name: 'Подготовить версию' }));
  await screen.findByRole('button', { name: 'Проверить на примере' });
  fireEvent.click(screen.getByRole('button', { name: 'Проверить на примере' }));
  await screen.findByRole('button', { name: 'Подтвердить версию' });
  fireEvent.click(screen.getByRole('button', { name: 'Подтвердить версию' }));
  await screen.findByRole('button', { name: 'Запустить проверку' });
};

describe('CompiledScriptBuilder', () => {
  beforeEach(() => { vi.mocked(newAuth.makeRequest).mockReset(); });

  it('parses only bounded string table cells and rejects duplicate headers', () => {
    expect(parsePastedTable('code\tamount\n001\t0').table).toEqual({ columns: ['code', 'amount'], rows: [{ code: '001', amount: '0' }] });
    expect(parsePastedTable('code\tcode\na\tb').error).toContain('уникальны');
  });

  it('keeps quoted commas and embedded newlines, accepts empty data, and enforces server bounds', () => {
    expect(parsePastedTable('name,comment\n"Анна, И.","первая\nвторая"').table).toEqual({ columns: ['name', 'comment'], rows: [{ name: 'Анна, И.', comment: 'первая\nвторая' }] });
    expect(parsePastedTable('email').table).toEqual({ columns: ['email'], rows: [] });
    expect(parsePastedTable(`${'a'.repeat(81)}\nvalue`).error).toContain('80');
    const twoHundredRows = Array.from({ length: 200 }, (_, index) => `v-${index}`).join('\n');
    expect(parsePastedTable(`value\n${twoHundredRows}`).table?.rows).toHaveLength(200);
    expect(parsePastedTable(`value\n${twoHundredRows}\nnext`).error).toContain('200');
    expect(parsePastedTable('email\na\u001fb').error).toContain('недопустимый');
  });

  it('rechecks encoded size after mapping and protects CSV downloads from formula cells', () => {
    const rows = Array.from({ length: 200 }, () => ({ x: 'x'.repeat(70) }));
    const renamed = mapTableColumns({ columns: ['x'], rows }, { x: 'x'.repeat(80) });
    expect(tableInputError(renamed)).toContain('20 KB');
    expect(reportCsv({ errors: [{ row: 1, code: '=HYPERLINK("https://bad")', columns: ['@email'] }] })).toContain("'=HYPERLINK");
  });

  it('builds a user-owned table contract and expected disposition without primary JSON entry', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ success: true, candidate_version: { id: 'v-1' }, artifact: { source: 'def process(input_payload): pass' } });
    render(<CompiledScriptBuilder blueprintId="bp-1" />);
    expect(screen.queryByLabelText('Пример входных данных (JSON)')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Вставьте пример таблицы/), { target: { value: fixture } });
    fireEvent.click(screen.getAllByRole('checkbox')[0]);
    fireEvent.click(screen.getAllByRole('checkbox')[2]);
    fireEvent.change(screen.getByLabelText(/Подтвердите ожидаемый результат: 2/), { target: { value: 'duplicate' } });
    fireEvent.change(screen.getByLabelText(/Подтвердите ожидаемый результат: 3/), { target: { value: 'missing' } });
    fireEvent.change(screen.getByLabelText('Название версии'), { target: { value: 'Прайс — сентябрь' } });
    fireEvent.click(screen.getByRole('button', { name: 'Подготовить версию' }));
    await waitFor(() => expect(newAuth.makeRequest).toHaveBeenCalledTimes(1));
    const request = vi.mocked(newAuth.makeRequest).mock.calls[0];
    expect(request?.[0]).toBe('/agent-blueprints/bp-1/compiled-script/compile');
    const options = request?.[1];
    expect(options).toEqual(expect.objectContaining({ method: 'POST' }));
    const body = JSON.parse(String(options?.body));
    expect(body.table_contract).toEqual({ version: 2, columns: ['email', 'amount'], required_columns: ['email'], dedupe_columns: ['email'], version_name: 'Прайс — сентябрь' });
    expect(body.fixtures[0]).toMatchObject({ source: 'user', input: { rows: [{ email: 'anna@example.com', amount: '1500' }, { email: 'anna@example.com', amount: '1500' }, { email: '', amount: '900' }] }, expected: { report: { received: 3, accepted: 1, duplicates: 1, invalid: 1, errors: [{ row: 2, code: 'duplicate' }, { row: 3, code: 'required', columns: ['email'] }] } } });
  });

  it('uses a new idempotency key for a deliberate second run, and retains one for retry after an uncertain request', async () => {
    const queued = vi.fn();
    vi.mocked(newAuth.makeRequest)
      .mockResolvedValueOnce({ success: true, candidate_version: { id: 'v-1' }, artifact: { source: 'def process(input_payload): pass', manifest: { table_contract: { columns: ['email', 'amount'], required_columns: ['email'], dedupe_columns: ['email'], version_name: 'Прайс' } } } })
      .mockResolvedValueOnce({ success: true, version_id: 'v-1', preview: { status: 'passed', result: { report: { received: 3, accepted: 1, duplicates: 1, invalid: 1 }, artifact_hash: 'hash' }, fixture_digest: 'fixture-1', fixture_results: [{ passed: true }] }, approval_digest: 'hash-1' })
      .mockResolvedValueOnce({ success: true, version_id: 'v-1', state: 'approved' })
      .mockResolvedValueOnce({ success: true, snapshot: { id: 'snapshot-1' } })
      .mockResolvedValueOnce({ success: true, run: { id: 'run-1' }, status: 'queued' })
      .mockResolvedValueOnce({ success: true, snapshot: { id: 'snapshot-2' } })
      .mockRejectedValueOnce(new Error('network interrupted'))
      .mockResolvedValueOnce({ success: true, run: { id: 'run-2' }, status: 'queued' });
    render(<CompiledScriptBuilder blueprintId="bp-1" onRunQueued={queued} />);
    await prepareVersion();
    fireEvent.click(screen.getByRole('button', { name: 'Запустить проверку' }));
    await waitFor(() => expect(queued).toHaveBeenCalledWith('run-1'));
    fireEvent.click(screen.getByRole('button', { name: 'Запустить проверку' }));
    await screen.findByRole('alert');
    fireEvent.click(screen.getByRole('button', { name: 'Запустить проверку' }));
    await waitFor(() => expect(queued).toHaveBeenCalledWith('run-2'));
    const calls = vi.mocked(newAuth.makeRequest).mock.calls;
    const runBodies = calls.filter((call) => String(call[0]).endsWith('/compiled-script/run')).map((call) => JSON.parse(String(call[1]?.body)));
    expect(runBodies).toHaveLength(3);
    expect(runBodies[0].idempotency_key).not.toBe(runBodies[1].idempotency_key);
    expect(runBodies[1].idempotency_key).toBe(runBodies[2].idempotency_key);
    expect(runBodies[1].snapshot_id).toBe('snapshot-2');
    expect(runBodies[2].snapshot_id).toBe('snapshot-2');
  });

  it('clears inputs on a blueprint switch and ignores a late compile response from the prior blueprint', async () => {
    let resolveCompile: (value: PendingCompile) => void = () => undefined;
    vi.mocked(newAuth.makeRequest).mockImplementation(() => new Promise((resolve) => { resolveCompile = resolve; }));
    const rendered = render(<CompiledScriptBuilder blueprintId="bp-1" />);
    fireEvent.change(screen.getByLabelText(/Вставьте пример таблицы/), { target: { value: 'email\na@example.com' } });
    fireEvent.click(screen.getAllByRole('checkbox')[1]);
    fireEvent.click(screen.getByRole('button', { name: 'Подготовить версию' }));
    rendered.rerender(<CompiledScriptBuilder blueprintId="bp-2" />);
    resolveCompile({ success: true, candidate_version: { id: 'old-version' }, artifact: { source: 'old code' } });
    await waitFor(() => expect(screen.getByLabelText(/Вставьте пример таблицы/)).toHaveValue(''));
    expect(screen.queryByRole('button', { name: 'Проверить на примере' })).not.toBeInTheDocument();
  });

  it('does not attach a late snapshot from another blueprint to the current run', async () => {
    let resolveSnapshot: (value: PendingSnapshot) => void = () => undefined;
    vi.mocked(newAuth.makeRequest)
      .mockResolvedValueOnce({ success: true, candidate_version: { id: 'v-1' }, artifact: { source: 'def process(input_payload): pass', manifest: { table_contract: { columns: ['email', 'amount'], required_columns: ['email'], dedupe_columns: ['email'], version_name: 'Прайс' } } } })
      .mockResolvedValueOnce({ success: true, version_id: 'v-1', preview: { status: 'passed', result: { report: {}, artifact_hash: 'hash' }, fixture_digest: 'fixture-1', fixture_results: [{ passed: true }] }, approval_digest: 'hash-1' })
      .mockResolvedValueOnce({ success: true, version_id: 'v-1', state: 'approved' })
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSnapshot = resolve; }));
    const rendered = render(<CompiledScriptBuilder blueprintId="bp-1" />);
    await prepareVersion();
    fireEvent.click(screen.getByRole('button', { name: 'Запустить проверку' }));
    rendered.rerender(<CompiledScriptBuilder blueprintId="bp-2" />);
    resolveSnapshot({ success: true, snapshot: { id: 'old-snapshot' } });
    await waitFor(() => expect(screen.getByLabelText(/Вставьте пример таблицы/)).toHaveValue(''));
    expect(vi.mocked(newAuth.makeRequest).mock.calls.filter((call) => String(call[0]).endsWith('/compiled-script/run'))).toHaveLength(0);
  });

  it('restores ready-for-approval evidence after reload without making preview overwrite approval', async () => {
    const approvedArtifact = { source: 'def process(input_payload): pass', artifact_hash: 'artifact-hash', manifest: { table_contract: { columns: ['email'], required_columns: [], dedupe_columns: ['email'], version_name: 'Проверка' } }, fixtures: [{ source: 'user', input: { rows: [{ email: 'a@example.com' }] }, expected: {} }] };
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ success: true, state: 'approved' });
    render(<CompiledScriptBuilder blueprintId="bp-1" blueprintDetails={{ versions: [], runs: [], candidate_version: { id: 'v-ready', compiled_state: 'ready_approval', compiled_artifact_json: approvedArtifact, compiled_preview_json: { status: 'passed', fixture_digest: 'fixture-evidence', result: { report: {}, artifact_hash: 'artifact-hash' } } } }} />);
    const approve = await screen.findByRole('button', { name: 'Подтвердить версию' });
    expect(screen.queryByRole('button', { name: 'Проверить на примере' })).not.toBeInTheDocument();
    fireEvent.click(approve);
    await waitFor(() => expect(newAuth.makeRequest).toHaveBeenCalledWith('/agent-blueprints/bp-1/compiled-script/approve', { method: 'POST', body: JSON.stringify({ version_id: 'v-ready', approval_digest: 'artifact-hash', fixture_digest: 'fixture-evidence' }) }));
  });

  it('shows failed preview row discrepancies and withholds approval', async () => {
    const previewError = Object.assign(new Error('Проверка на примере не прошла.'), { details: { preview: { status: 'failed', result: { report: { received: 1, accepted: 0, duplicates: 0, invalid: 1, errors: [{ row: 3, code: 'required', columns: ['email'] }] } }, fixture_results: [{ passed: false }] } } });
    vi.mocked(newAuth.makeRequest)
      .mockResolvedValueOnce({ success: true, candidate_version: { id: 'v-1' }, artifact: { source: 'def process(input_payload): pass' } })
      .mockRejectedValueOnce(previewError);
    render(<CompiledScriptBuilder blueprintId="bp-1" />);
    fireEvent.change(screen.getByLabelText(/Вставьте пример таблицы/), { target: { value: 'email\na@example.com' } });
    fireEvent.click(screen.getAllByRole('checkbox')[1]);
    fireEvent.click(screen.getByRole('button', { name: 'Подготовить версию' }));
    await screen.findByRole('button', { name: 'Проверить на примере' });
    fireEvent.click(screen.getByRole('button', { name: 'Проверить на примере' }));
    expect(await screen.findByText('Проверка не пройдена')).toBeInTheDocument();
    expect(screen.getByText('Не заполнены: email')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Подтвердить версию' })).not.toBeInTheDocument();
  });

  it('shows the completed run report rather than only the preview count', async () => {
    const artifact = { source: 'def process(input_payload): pass', manifest: { table_contract: { columns: ['email'], required_columns: [], dedupe_columns: ['email'], version_name: 'Проверка' } }, fixtures: [{ source: 'user', input: { rows: [] }, expected: {} }] };
    render(<CompiledScriptBuilder blueprintId="bp-1" activeRun={{ id: 'run-1', blueprint_id: 'bp-1', status: 'completed', output_json: { report: { received: 2, accepted: 1, duplicates: 0, invalid: 1, errors: [{ row: 3, code: 'required', columns: ['email'] }] } } }} blueprintDetails={{ versions: [], runs: [], active_version: { id: 'v-active', compiled_state: 'approved', compiled_artifact_json: artifact } }} />);
    expect(await screen.findByText('Фактический отчёт запуска')).toBeInTheDocument();
    expect(screen.getByText('Строк: 2 · принято: 1 · дубли: 0 · ошибки: 1')).toBeInTheDocument();
    expect(screen.getByText('Не заполнены: email')).toBeInTheDocument();
  });

  it('keeps a legacy approved version on its compatible scenario path without calling the model', async () => {
    render(<CompiledScriptBuilder blueprintId="bp-1" blueprintDetails={{ versions: [], runs: [], active_version: { id: 'v-active', compiled_state: 'approved', compiled_artifact_json: { source: 'def process(input_payload): pass' } } }} />);
    expect(await screen.findByText('Эта утверждённая версия использует прежний общий формат. Откройте сценарий агента для запуска; таблица не будет подменена новым форматом.')).toBeInTheDocument();
    expect(newAuth.makeRequest).not.toHaveBeenCalled();
  });
});
