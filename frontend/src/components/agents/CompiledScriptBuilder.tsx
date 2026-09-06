import { useEffect, useMemo, useRef, useState } from 'react';
import { CheckCircle2, Download, Play, RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { newAuth } from '@/lib/auth_new';
import { useLanguage } from '@/i18n/LanguageContext';
import type { AgentBlueprintDetails, AgentRun } from '@/pages/dashboard/agents/types';

import { mapTableColumns, parsePastedTable, reportCsv, tableInputError, tableInputPayload, tableTextFromRows, type TableInput } from './compiledTable';

type Artifact = { source?: string; manifest?: Record<string, unknown>; fixtures?: unknown; artifact_hash?: string };
type Candidate = { id?: string; compiled_state?: string };
type CompileResponse = { success?: boolean; candidate_version?: Candidate; artifact?: Artifact; code?: string };
type Preview = { result?: unknown; output?: unknown; status?: string; fixture_digest?: string; fixture_results?: Array<{ source?: string; passed?: boolean; expected?: unknown; actual?: unknown }> };
type PreviewResponse = { success?: boolean; version_id?: string; preview?: Preview; approval_digest?: string; code?: string };
type ApproveResponse = { success?: boolean; version_id?: string; state?: string; code?: string };
type Snapshot = { id?: string; hash?: string; input?: { rows?: Array<Record<string, string>> }; row_count?: number; expires_at?: string };
type SnapshotResponse = { success?: boolean; snapshot?: Snapshot; code?: string };
type RunResponse = { success?: boolean; run?: { id?: string }; status?: string; code?: string };
type Disposition = 'accepted' | 'duplicate' | 'missing';

type RunView = Pick<AgentRun, 'id' | 'status' | 'error_text' | 'blueprint_id'> & { output_json?: unknown };
type SavedApproval = { versionId: string; artifact: Artifact | null; approvalDigest: string; preview: Preview | null; fixtureText: string; mapping: Record<string, string>; requiredColumns: string[]; dedupeColumns: string[]; dispositions: Disposition[]; versionName: string };
type Props = { blueprintId?: string | null; blueprintDetails?: AgentBlueprintDetails | null; activeRun?: RunView | null; canPreview?: boolean; canExecute?: boolean; onRunQueued?: (runId: string) => void };

const parseObject = (value: string) => {
  try { const parsed: unknown = JSON.parse(value || '{}'); return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null; } catch { return null; }
};

const artifactFromVersion = (version: Record<string, unknown> | null | undefined): Artifact | null => {
  const raw = version?.compiled_artifact_json;
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) return raw;
  return typeof raw === 'string' ? parseObject(raw) : null;
};

const errorMessage = (error: unknown, fallback: string) => error instanceof Error && error.message ? error.message : fallback;
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);

const expectedFor = (table: TableInput, requiredColumns: string[], dispositions: Disposition[]) => {
  const rows: Array<Record<string, string>> = [];
  const errors: Array<{ row: number; code: string; columns?: string[] }> = [];
  let duplicates = 0;
  table.rows.forEach((row, index) => {
    const disposition = dispositions[index] || 'accepted';
    if (disposition === 'accepted') rows.push(row);
    if (disposition === 'duplicate') {
      duplicates += 1;
      errors.push({ row: index + 1, code: 'duplicate' });
    }
    if (disposition === 'missing') {
      const columns = requiredColumns.filter((column) => !String(row[column] || '').trim());
      errors.push({ row: index + 1, code: 'required', columns: columns.length ? columns : requiredColumns });
    }
  });
  return { schema: 'localos_compiled_script_result_v1', rows, report: { received: table.rows.length, accepted: rows.length, duplicates, invalid: errors.filter((error) => error.code !== 'duplicate').length, errors } };
};

const reportFromValue = (value: unknown) => isRecord(value) && isRecord(value.report) ? value.report : null;
const resultReport = (preview: Preview | null) => reportFromValue(preview?.result || preview?.output);

const makeIdempotencyKey = () => globalThis.crypto?.randomUUID?.() || `compiled-${Date.now()}-${Math.random().toString(16).slice(2)}`;
const readStrings = (value: unknown) => Array.isArray(value) ? value.filter((item) => typeof item === 'string') : [];
const tableContractFrom = (artifact: Artifact | null, defaultVersionName = 'Проверка таблицы') => {
  const manifest = artifact?.manifest;
  const contract = isRecord(manifest?.table_contract) ? manifest.table_contract : null;
  if (!contract) return null;
  const columns = readStrings(contract.columns);
  return columns.length ? { columns, requiredColumns: readStrings(contract.required_columns), dedupeColumns: readStrings(contract.dedupe_columns), versionName: typeof contract.version_name === 'string' ? contract.version_name : defaultVersionName } : null;
};
const previewFromVersion = (version: Record<string, unknown>) => {
  const raw = version.compiled_preview_json;
  return isRecord(raw) ? raw : typeof raw === 'string' ? parseObject(raw) : null;
};
const savedApprovalFromVersion = (version: Record<string, unknown>, defaultVersionName: string): SavedApproval | null => {
  const versionId = typeof version.id === 'string' ? version.id : '';
  const artifact = artifactFromVersion(version);
  if (!versionId || !artifact) return null;
  const contract = tableContractFrom(artifact, defaultVersionName);
  const fixtures = Array.isArray(artifact.fixtures) ? artifact.fixtures : [];
  const userFixture = fixtures.find((fixture) => isRecord(fixture) && fixture.source === 'user');
  const input = isRecord(userFixture) && isRecord(userFixture.input) ? userFixture.input : {};
  const rows = Array.isArray(input.rows) ? input.rows : [];
  return {
    versionId,
    artifact,
    approvalDigest: 'approved',
    preview: previewFromVersion(version),
    fixtureText: contract ? tableTextFromRows(contract.columns, rows) : '',
    mapping: contract ? Object.fromEntries(contract.columns.map((column) => [column, column])) : {},
    requiredColumns: contract?.requiredColumns || [],
    dedupeColumns: contract?.dedupeColumns || [],
    dispositions: rows.map(() => 'accepted'),
    versionName: contract?.versionName || '',
  };
};
const outputFromRun = (run: RunView | null | undefined) => isRecord(run?.output_json) ? run.output_json : null;
const reasonForRowError = (value: unknown, copy: BuilderCopy) => {
  const error = isRecord(value) ? value : {};
  const code = String(error.code || 'unknown');
  const columns = readStrings(error.columns);
  if (code === 'required') return copy.missingColumns(columns.join(', '));
  if (code === 'duplicate') return copy.duplicateRow;
  if (code === 'row_not_object') return copy.nonRecordRow;
  return copy.invalidRow;
};
type BuilderCopy = {
  eyebrow: string; title: string; description: string; fixture: string; fixtureHint: string; fictional: string; sample: string; ready: string; edit: string; rules: (required: string, dedupe: string) => string; next: string; inputPinned: string; retention: string; runInput: string; runPlaceholder: string; run: string; runUnavailable: string; queued: (id: string, state: string) => string; reportTitle: string; reportSummary: (report: Record<string, unknown>) => string; download: string; rowErrors: string; rowNumber: string; reason: string; missingColumns: (columns: string) => string; duplicateRow: string; nonRecordRow: string; invalidRow: string; mapRules: string; mapRulesHint: string; required: string; dedupe: string; expected: string; expectedHint: string; accepted: string; duplicate: string; fieldError: string; emptyRow: string; versionName: string; versionHint: string; compile: string; preview: string; approve: string; approved: string; returnApproved: string; passed: string; failed: string; rows: string; acceptedCount: string; duplicates: string; invalid: string; fixtureResult: (index: number, passed: boolean) => string; legacy: string; technical: string; extraRules: string; extraRulesPlaceholder: string; sourceUnavailable: string; sourceHint: string; compileInvalid: string; defaultDescription: (required: string, dedupe: string) => string; compileFailed: string; previewFailed: string; previewUnavailable: string; approveFailed: string; approveRetry: string; snapshotName: string; snapshotFailed: string; runInputMissing: string; queueFailed: string; queueRetry: string; defaultVersionName: string;
};
const RowErrors = ({ report, copy }: { report: Record<string, unknown>; copy: BuilderCopy }) => {
  const errors = Array.isArray(report.errors) ? report.errors : [];
  if (!errors.length) return null;
  return <div className="mt-3 max-w-full overflow-x-auto rounded-xl bg-white p-3 text-slate-800"><table className="w-full table-fixed text-left text-xs"><caption className="mb-2 text-left font-medium">{copy.rowErrors}</caption><thead><tr className="border-b border-slate-200 text-slate-500"><th className="w-1/3 break-words pb-2 pr-3 align-top">{copy.rowNumber}</th><th className="pb-2">{copy.reason}</th></tr></thead><tbody>{errors.map((error, index) => <tr key={`${String(isRecord(error) ? error.row : '')}-${index}`} className="border-b border-slate-100 last:border-0"><td className="py-2 pr-3 align-top tabular-nums">{String(isRecord(error) ? error.row || '—' : '—')}</td><td className="py-2 break-words">{reasonForRowError(error, copy)}</td></tr>)}</tbody></table></div>;
};

export const CompiledScriptBuilder = ({ blueprintId, blueprintDetails, activeRun, canPreview = true, canExecute = true, onRunQueued }: Props) => {
  const { language } = useLanguage();
  const locale = language === 'ru' ? 'ru' : 'en';
  const copy: BuilderCopy = locale === 'ru' ? {
    eyebrow: 'Повторяемая проверка таблиц', title: 'Проверьте таблицу без повторного обращения к ИИ', description: 'Один раз задайте поля и пример результата. После подтверждения программа запускается на новых таблицах в защищённой среде и возвращает отчёт по строкам.',
    fixture: '1. Вставьте пример таблицы', fixtureHint: 'CSV, TSV или строки из Excel; первая строка — названия столбцов.', fictional: 'Используйте вымышленные данные: пример сохраняется вместе с версией программы. Рабочую таблицу загрузите после утверждения.', sample: 'Заполнить пример',
    ready: 'Утверждённая версия готова', edit: 'Изменить правила', rules: (required, dedupe) => `Правила: обязательные — ${required || 'нет'}; поиск дублей — ${dedupe || 'нет'}.`, next: 'Следующий шаг: проверьте новую таблицу', inputPinned: 'Входные данные закрепляются вместе с запуском: изменение источника не подменит уже поставленную задачу.', retention: 'Данные запуска хранятся 7 дней. После этого остаётся отчёт без содержимого строк.', runInput: 'Новая таблица для запуска', runPlaceholder: 'Вставьте новую CSV или TSV таблицу', run: 'Запустить проверку', runUnavailable: 'Проверка версии доступна; рабочие запуски пока выключены.', queued: (id, state) => `Запуск ${id}: ${state}.`, reportTitle: 'Фактический отчёт запуска', reportSummary: (report) => `Строк: ${String(report.received || 0)} · принято: ${String(report.accepted || 0)} · дубли: ${String(report.duplicates || 0)} · ошибки: ${String(report.invalid || 0)}`, download: 'Скачать ошибки CSV', rowErrors: 'Ошибки по строкам', rowNumber: 'Номер строки данных (без заголовка)', reason: 'Причина', missingColumns: (columns) => `Не заполнены: ${columns || 'обязательные поля'}`, duplicateRow: 'Дубликат строки', nonRecordRow: 'Строка не распознана как запись таблицы', invalidRow: 'Строка не прошла проверку', mapRules: '2. Сопоставьте столбцы и правила', mapRulesHint: 'Переименование нужно, если в разных таблицах одно поле называется по-разному. Каждое имя используется только один раз.', required: 'Обязательные поля', dedupe: 'Искать дубли по', expected: '3. Подтвердите ожидаемый результат', expectedHint: 'Отметьте, как должна обработаться каждая строка. Это ваш независимый пример для проверки версии, а не догадка LocalOS.', accepted: 'принять', duplicate: 'дубликат', fieldError: 'ошибка поля', emptyRow: 'пустая строка', versionName: 'Название версии', versionHint: 'Например, «Проверка прайса — сентябрь».', compile: 'Подготовить версию', preview: 'Проверить на примере', approve: 'Подтвердить версию', approved: 'Версия подтверждена', returnApproved: 'Вернуться к утверждённой версии', passed: 'Проверка пройдена', failed: 'Проверка не пройдена', rows: 'Строк', acceptedCount: 'Принято', duplicates: 'Дубли', invalid: 'Ошибки', fixtureResult: (index, passed) => `Пример ${index}: ${passed ? 'совпадает с подтверждённым результатом' : 'не совпадает'}`, legacy: 'Эта утверждённая версия использует прежний общий формат. Откройте сценарий агента для запуска; таблица не будет подменена новым форматом.', technical: 'Технические детали', extraRules: 'Дополнительные правила для генератора', extraRulesPlaceholder: 'Необязательно: уточните правило проверки', sourceUnavailable: 'Исходный текст недоступен', sourceHint: 'Исходный текст появится после подготовки версии. Он выполняется только в защищённой среде.', compileInvalid: 'Вставьте таблицу, назовите столбцы без повторов и выберите поле для поиска дублей.', defaultDescription: (required, dedupe) => `Проверить таблицу: обязательные поля — ${required || 'нет'}; искать дубли по — ${dedupe}. Вернуть строки без ошибок и отчёт по строкам.`, compileFailed: 'Не удалось подготовить программу.', previewFailed: 'Проверка на примере не прошла.', previewUnavailable: 'Защищённый runtime недоступен или пример не прошёл проверку.', approveFailed: 'Подтверждение не выполнено.', approveRetry: 'Не удалось подтвердить эту версию. Выполните проверку ещё раз.', snapshotName: 'Таблица для запуска', snapshotFailed: 'Не удалось закрепить входные данные запуска.', runInputMissing: 'Вставьте новую таблицу для запуска.', queueFailed: 'Не удалось поставить запуск в очередь.', queueRetry: 'Не удалось поставить запуск в очередь. Повторите попытку: LocalOS не создаст второй запуск.', defaultVersionName: 'Проверка таблицы',
  } : {
    eyebrow: 'Repeatable table checks', title: 'Check a table without asking AI again', description: 'Set the fields and expected result once. After approval, the program runs on new tables in a protected environment and returns a row-level report.',
    fixture: '1. Paste an example table', fixtureHint: 'CSV, TSV, or rows from Excel; the first row contains column names.', fictional: 'Use fictional data: the example is saved with the program version. Upload the working table after approval.', sample: 'Use an example',
    ready: 'Approved version is ready', edit: 'Edit rules', rules: (required, dedupe) => `Rules: required — ${required || 'none'}; duplicate check — ${dedupe || 'none'}.`, next: 'Next step: check a new table', inputPinned: 'Input data is stored with the run, so a source change cannot replace a task that is already queued.', retention: 'Run data is stored for 7 days. After that, the report remains without row contents.', runInput: 'New table for this run', runPlaceholder: 'Paste a new CSV or TSV table', run: 'Run check', runUnavailable: 'Version checking is available; live runs are currently disabled.', queued: (id, state) => `Run ${id}: ${state}.`, reportTitle: 'Actual run report', reportSummary: (report) => `Rows: ${String(report.received || 0)} · accepted: ${String(report.accepted || 0)} · duplicates: ${String(report.duplicates || 0)} · errors: ${String(report.invalid || 0)}`, download: 'Download errors CSV', rowErrors: 'Row errors', rowNumber: 'Data row number (excluding header)', reason: 'Reason', missingColumns: (columns) => `Missing: ${columns || 'required fields'}`, duplicateRow: 'Duplicate row', nonRecordRow: 'The row was not recognized as a table record', invalidRow: 'The row did not pass validation', mapRules: '2. Map columns and rules', mapRulesHint: 'Rename a field when it has a different name in another table. Each name can be used only once.', required: 'Required fields', dedupe: 'Find duplicates by', expected: '3. Confirm the expected result', expectedHint: 'Mark how each row should be processed. This is your independent example for checking the version, not a LocalOS guess.', accepted: 'accept', duplicate: 'duplicate', fieldError: 'field error', emptyRow: 'empty row', versionName: 'Version name', versionHint: 'For example, “Price check — September”.', compile: 'Prepare version', preview: 'Check with the example', approve: 'Approve version', approved: 'Version approved', returnApproved: 'Return to approved version', passed: 'Check passed', failed: 'Check failed', rows: 'Rows', acceptedCount: 'Accepted', duplicates: 'Duplicates', invalid: 'Errors', fixtureResult: (index, passed) => `Example ${index}: ${passed ? 'matches the approved result' : 'does not match'}`, legacy: 'This approved version uses the previous general format. Open the agent scenario to run it; the table will not be replaced with a new format.', technical: 'Technical details', extraRules: 'Additional generator rules', extraRulesPlaceholder: 'Optional: clarify the validation rule', sourceUnavailable: 'Source text is unavailable', sourceHint: 'The source text appears after a version is prepared. It runs only in a protected environment.', compileInvalid: 'Paste a table, give columns unique names, and select a field for duplicate checks.', defaultDescription: (required, dedupe) => `Check a table: required fields — ${required || 'none'}; find duplicates by — ${dedupe}. Return valid rows and a row-level report.`, compileFailed: 'Could not prepare the program.', previewFailed: 'The example check did not pass.', previewUnavailable: 'The protected runtime is unavailable or the example did not pass validation.', approveFailed: 'Approval was not completed.', approveRetry: 'Could not approve this version. Run the check again.', snapshotName: 'Table for this run', snapshotFailed: 'Could not store the run input.', runInputMissing: 'Paste a new table for this run.', queueFailed: 'Could not queue the run.', queueRetry: 'Could not queue the run. Try again: LocalOS will not create a duplicate run.', defaultVersionName: 'Table check',
  };
  const [fixtureText, setFixtureText] = useState('');
  const [runText, setRunText] = useState('');
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [requiredColumns, setRequiredColumns] = useState<string[]>([]);
  const [dedupeColumns, setDedupeColumns] = useState<string[]>([]);
  const [dispositions, setDispositions] = useState<Disposition[]>([]);
  const [versionName, setVersionName] = useState('');
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [versionId, setVersionId] = useState('');
  const [approvalDigest, setApprovalDigest] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [busy, setBusy] = useState<'compile' | 'preview' | 'approve' | 'snapshot' | 'run' | ''>('');
  const [error, setError] = useState('');
  const [advancedDescription, setAdvancedDescription] = useState('');
  const [draftMode, setDraftMode] = useState(true);
  const [queuedRunId, setQueuedRunId] = useState('');
  const idempotencyKey = useRef('');
  const compileIdempotencyKey = useRef('');
  const requestRevision = useRef(0);
  const hydratedVersion = useRef('');
  const manuallyInvalidated = useRef(false);
  const approvedRef = useRef<SavedApproval | null>(null);
  const fixtureParsed = useMemo(() => parsePastedTable(fixtureText, locale), [fixtureText, locale]);
  const runParsed = useMemo(() => parsePastedTable(runText, locale), [runText, locale]);
  const fixtureTable = fixtureParsed.table ? mapTableColumns(fixtureParsed.table, mapping) : null;
  const runTable = runParsed.table ? mapTableColumns(runParsed.table, mapping) : null;

  const reset = () => {
    requestRevision.current += 1;
    manuallyInvalidated.current = false;
    setFixtureText(''); setRunText(''); setMapping({}); setRequiredColumns([]); setDedupeColumns([]); setDispositions([]); setVersionName(''); setArtifact(null); setVersionId(''); setApprovalDigest(''); setPreview(null); setSnapshot(null); setError(''); setBusy(''); setAdvancedDescription(''); setDraftMode(true); setQueuedRunId(''); approvedRef.current = null; idempotencyKey.current = ''; compileIdempotencyKey.current = ''; hydratedVersion.current = '';
  };

  useEffect(() => { reset(); }, [blueprintId]);
  useEffect(() => {
    const candidate = blueprintDetails?.candidate_version;
    const active = blueprintDetails?.active_version;
    const compiledApproved = blueprintDetails?.compiled_approved_version;
    const candidateState = typeof candidate?.compiled_state === 'string' ? candidate.compiled_state : '';
    const approvedState = typeof compiledApproved?.compiled_state === 'string' ? compiledApproved.compiled_state : '';
    const activeState = typeof active?.compiled_state === 'string' ? active.compiled_state : '';
    const approvedVersion = ['approved', 'active'].includes(approvedState)
      ? compiledApproved
      : ['approved', 'active'].includes(activeState)
        ? active
        : null;
    const savedApproved = approvedVersion ? savedApprovalFromVersion(approvedVersion, copy.defaultVersionName) : null;
    if (savedApproved && approvedRef.current?.versionId !== savedApproved.versionId) approvedRef.current = savedApproved;
    const version = ['checking', 'needs_fix', 'ready_approval', 'approved', 'active'].includes(candidateState)
      ? candidate
      : approvedVersion;
    const candidateId = typeof version?.id === 'string' ? version.id : '';
    const state = typeof version?.compiled_state === 'string' ? version.compiled_state : '';
    const unresolvedCandidate = version === candidate && ['checking', 'needs_fix'].includes(state);
    if (manuallyInvalidated.current || !candidateId || !['checking', 'needs_fix', 'ready_approval', 'approved', 'active'].includes(state) || hydratedVersion.current === candidateId || versionId) return;
    const nextArtifact = artifactFromVersion(version);
    if (!nextArtifact) return;
    hydratedVersion.current = candidateId;
    const contract = tableContractFrom(nextArtifact, copy.defaultVersionName);
    const fixtures = Array.isArray(nextArtifact.fixtures) ? nextArtifact.fixtures : [];
    const userFixture = fixtures.find((fixture) => isRecord(fixture) && fixture.source === 'user');
    const input = isRecord(userFixture) && isRecord(userFixture.input) ? userFixture.input : {};
    const rows = Array.isArray(input.rows) ? input.rows : [];
    const sourceText = contract ? tableTextFromRows(contract.columns, rows) : '';
    const nextPreview = previewFromVersion(version) || null;
    const nextDigest = state === 'ready_approval' ? String(nextArtifact.artifact_hash || '') : ['approved', 'active'].includes(state) ? 'approved' : '';
    setVersionId(candidateId); setArtifact(nextArtifact); setPreview(nextPreview); setApprovalDigest(nextDigest); setDraftMode(unresolvedCandidate);
    if (contract) {
      setFixtureText(sourceText); setMapping(Object.fromEntries(contract.columns.map((column) => [column, column]))); setRequiredColumns(contract.requiredColumns); setDedupeColumns(contract.dedupeColumns); setDispositions(rows.map(() => 'accepted')); setVersionName(contract.versionName);
    }
    if ((state === 'approved' || state === 'active') && !approvedRef.current) approvedRef.current = { versionId: candidateId, artifact: nextArtifact, approvalDigest: 'approved', preview: nextPreview, fixtureText: sourceText, mapping: contract ? Object.fromEntries(contract.columns.map((column) => [column, column])) : {}, requiredColumns: contract?.requiredColumns || [], dedupeColumns: contract?.dedupeColumns || [], dispositions: rows.map(() => 'accepted'), versionName: contract?.versionName || '' };
  }, [blueprintId, blueprintDetails?.candidate_version, blueprintDetails?.compiled_approved_version, blueprintDetails?.active_version, copy.defaultVersionName, versionId]);
  useEffect(() => {
    if (!fixtureParsed.table) return;
    const columns = fixtureParsed.table.columns;
    setMapping((current) => Object.fromEntries(columns.map((column) => [column, current[column] || column])));
    setDispositions((current) => fixtureParsed.table ? fixtureParsed.table.rows.map((_, index) => current[index] || 'accepted') : current);
  }, [fixtureParsed.table]);

  const invalidateCandidate = () => { requestRevision.current += 1; manuallyInvalidated.current = true; setArtifact(null); setVersionId(''); setApprovalDigest(''); setPreview(null); setBusy(''); setSnapshot(null); idempotencyKey.current = ''; compileIdempotencyKey.current = ''; hydratedVersion.current = ''; };
  const beginDraft = () => { setDraftMode(true); invalidateCandidate(); setError(''); };
  const returnToApproved = () => {
    const saved = approvedRef.current;
    if (!saved) return;
    requestRevision.current += 1; manuallyInvalidated.current = false; hydratedVersion.current = saved.versionId;
    setVersionId(saved.versionId); setArtifact(saved.artifact); setApprovalDigest(saved.approvalDigest); setPreview(saved.preview); setFixtureText(saved.fixtureText); setMapping(saved.mapping); setRequiredColumns(saved.requiredColumns); setDedupeColumns(saved.dedupeColumns); setDispositions(saved.dispositions); setVersionName(saved.versionName); setDraftMode(false); setBusy(''); setError(''); setSnapshot(null); idempotencyKey.current = '';
  };
  const changeFixture = (value: string) => { setFixtureText(value); invalidateCandidate(); };
  const loadSample = () => changeFixture('email\tamount\nanna@example.test\t1500\nanna@example.test\t1500\n\t900');
  const toggleColumn = (column: string, selected: string[], setSelected: (next: string[]) => void) => { setSelected(selected.includes(column) ? selected.filter((item) => item !== column) : [...selected, column]); invalidateCandidate(); };
  const renameColumn = (sourceColumn: string, nextName: string) => {
    const previousName = (mapping[sourceColumn] || sourceColumn).trim();
    const cleanName = nextName.trim();
    setMapping((current) => ({ ...current, [sourceColumn]: nextName }));
    setRequiredColumns((current) => current.map((column) => column === previousName ? cleanName : column));
    setDedupeColumns((current) => current.map((column) => column === previousName ? cleanName : column));
    invalidateCandidate();
  };
  const mappingError = fixtureTable ? tableInputError(fixtureTable, locale) : '';
  const validMapping = fixtureTable && !mappingError;

  const compile = async () => {
    if (!blueprintId || !fixtureTable || !validMapping || !dedupeColumns.length) { setError(copy.compileInvalid); return; }
    if (!compileIdempotencyKey.current) compileIdempotencyKey.current = makeIdempotencyKey();
    const compileKey = compileIdempotencyKey.current;
    const expected = expectedFor(fixtureTable, requiredColumns, dispositions);
    const description = advancedDescription.trim() || copy.defaultDescription(requiredColumns.join(', '), dedupeColumns.join(', '));
    setBusy('compile'); setError(''); setPreview(null); setApprovalDigest('');
    const revision = requestRevision.current + 1; requestRevision.current = revision;
    try {
      const response: CompileResponse = await newAuth.makeRequest(`/agent-blueprints/${encodeURIComponent(blueprintId)}/compiled-script/compile`, { method: 'POST', body: JSON.stringify({ idempotency_key: compileKey, description, fixtures: [{ input: tableInputPayload(fixtureTable), expected, source: 'user' }], table_contract: { version: 2, columns: fixtureTable.columns, required_columns: requiredColumns, dedupe_columns: dedupeColumns, version_name: versionName.trim() } }) });
      if (requestRevision.current !== revision) return;
      if (!response.success || !response.candidate_version?.id) throw new Error(response.code || copy.compileFailed);
      setVersionId(response.candidate_version.id); setArtifact(response.artifact || null);
    } catch (requestError) { if (requestRevision.current === revision) setError(errorMessage(requestError, copy.compileFailed)); } finally { if (requestRevision.current === revision) setBusy(''); }
  };

  const previewScript = async () => {
    if (!canPreview) return;
    if (!blueprintId || !versionId || !fixtureTable) return;
    setBusy('preview'); setError(''); setPreview(null); setApprovalDigest('');
    const revision = requestRevision.current + 1; requestRevision.current = revision;
    try {
      const response: PreviewResponse = await newAuth.makeRequest(`/agent-blueprints/${encodeURIComponent(blueprintId)}/compiled-script/preview`, { method: 'POST', body: JSON.stringify({ version_id: versionId, input: tableInputPayload(fixtureTable) }) });
      if (requestRevision.current !== revision) return;
      if (!response.success || !response.approval_digest) throw new Error(response.code || copy.previewFailed);
      setPreview(response.preview || null); setApprovalDigest(response.approval_digest);
    } catch (requestError) {
      if (requestRevision.current === revision) {
        const details = isRecord(requestError) && isRecord(requestError.details) ? requestError.details : null;
        const failedPreview = details && isRecord(details.preview) ? details.preview : null;
        if (failedPreview) setPreview(failedPreview);
        setError(errorMessage(requestError, copy.previewUnavailable));
      }
    } finally { if (requestRevision.current === revision) setBusy(''); }
  };

  const approve = async () => {
    if (!blueprintId || !versionId || !approvalDigest || !preview) return;
    setBusy('approve'); setError(''); const revision = requestRevision.current;
    try {
      const response: ApproveResponse = await newAuth.makeRequest(`/agent-blueprints/${encodeURIComponent(blueprintId)}/compiled-script/approve`, { method: 'POST', body: JSON.stringify({ version_id: versionId, approval_digest: approvalDigest, fixture_digest: preview.fixture_digest }) });
      if (requestRevision.current !== revision) return;
      if (!response.success) throw new Error(response.code || copy.approveFailed);
      setApprovalDigest('approved'); setRunText(fixtureText); setDraftMode(false);
      approvedRef.current = { versionId, artifact, approvalDigest: 'approved', preview, fixtureText, mapping, requiredColumns, dedupeColumns, dispositions, versionName };
    } catch (requestError) { if (requestRevision.current === revision) setError(errorMessage(requestError, copy.approveRetry)); } finally { if (requestRevision.current === revision) setBusy(''); }
  };

  const createSnapshot = async (input: TableInput) => {
    if (!blueprintId) return null;
    const response: SnapshotResponse = await newAuth.makeRequest(`/agent-blueprints/${encodeURIComponent(blueprintId)}/compiled-script/snapshots`, { method: 'POST', body: JSON.stringify({ input: tableInputPayload(input), name: copy.snapshotName }) });
    if (!response.success || !response.snapshot?.id) throw new Error(response.code || copy.snapshotFailed);
    return response.snapshot;
  };
  const changeRunText = (value: string) => {
    if (busy) return;
    requestRevision.current += 1; setRunText(value); setSnapshot(null); idempotencyKey.current = ''; setQueuedRunId('');
  };
  const run = async () => {
    if (!canExecute) return;
    if (!blueprintId || !versionId || approvalDigest !== 'approved' || !runTable || busy) { if (!runTable) setError(copy.runInputMissing); return; }
    if (!idempotencyKey.current) idempotencyKey.current = makeIdempotencyKey();
    const runKey = idempotencyKey.current;
    const runVersionId = versionId;
    const runBlueprintId = blueprintId;
    const revision = requestRevision.current;
    setBusy('snapshot'); setError('');
    try {
      const currentSnapshot = snapshot || await createSnapshot(runTable);
      if (!currentSnapshot?.id || requestRevision.current !== revision || blueprintId !== runBlueprintId || versionId !== runVersionId || idempotencyKey.current !== runKey) return;
      if (!snapshot) setSnapshot(currentSnapshot);
      setBusy('run');
      const response: RunResponse = await newAuth.makeRequest(`/agent-blueprints/${encodeURIComponent(runBlueprintId)}/compiled-script/run`, { method: 'POST', body: JSON.stringify({ version_id: runVersionId, snapshot_id: currentSnapshot.id, idempotency_key: runKey }) });
      if (requestRevision.current !== revision || blueprintId !== runBlueprintId || versionId !== runVersionId || idempotencyKey.current !== runKey) return;
      if (!response.success || !response.run?.id) throw new Error(response.code || copy.queueFailed);
      setQueuedRunId(response.run.id); onRunQueued?.(response.run.id); idempotencyKey.current = ''; setSnapshot(null);
    } catch (requestError) { if (requestRevision.current === revision) setError(errorMessage(requestError, copy.queueRetry)); } finally { if (requestRevision.current === revision) setBusy(''); }
  };
  const downloadReport = (report: Record<string, unknown>) => {
    if (!report || typeof document === 'undefined') return;
    const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([reportCsv(report, locale)], { type: 'text/csv;charset=utf-8' })); link.download = 'localos-table-errors.csv'; link.click(); URL.revokeObjectURL(link.href);
  };

  if (!blueprintId) return null;
  const isApproved = approvalDigest === 'approved';
  const previewPassed = preview?.status === 'passed';
  const report = resultReport(preview);
  const activeOutput = outputFromRun(activeRun && activeRun.blueprint_id === blueprintId ? activeRun : null);
  const runReport = reportFromValue(activeOutput);
  const tableContract = tableContractFrom(artifact, copy.defaultVersionName);
  return <section className="w-full min-w-0 max-w-full overflow-hidden rounded-3xl border border-slate-200 bg-white p-5 shadow-sm" aria-label={copy.title}>
    <div className="min-w-0 max-w-2xl"><p className="text-sm font-medium text-emerald-700">{copy.eyebrow}</p><h2 className="mt-1 text-balance text-xl font-semibold text-slate-950">{copy.title}</h2><p className="mt-2 text-sm leading-6 text-slate-600">{copy.description}</p></div>
    <div className="mt-5 grid min-w-0 grid-cols-1 gap-5 [&>*]:min-w-0">
      {draftMode ? <div className="grid gap-2"><label className="grid gap-2 text-sm font-medium text-slate-800">{copy.fixture} <span className="font-normal text-slate-500">{copy.fixtureHint}</span><Textarea aria-label={copy.fixture} value={fixtureText} onChange={(event) => changeFixture(event.target.value)} placeholder={'email\tamount\nanna@example.test\t1500'} className="min-h-32 font-mono text-xs" /></label><p className="text-sm leading-6 text-slate-600">{copy.fictional}</p><Button variant="outline" className="w-fit" onClick={loadSample}>{copy.sample}</Button></div> : <div className="rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-950"><p className="font-medium">{copy.ready}</p><p className="mt-1">{copy.rules(requiredColumns.join(', '), dedupeColumns.join(', '))}</p><Button variant="outline" className="mt-3 active:scale-[0.96] transition-transform" onClick={beginDraft}>{copy.edit}</Button></div>}
      {draftMode && (fixtureParsed.error || mappingError) ? <p role="alert" className="text-sm text-rose-700">{fixtureParsed.error || mappingError}</p> : null}
      {draftMode && fixtureParsed.table ? <><div className="min-w-0 rounded-2xl bg-slate-50 p-4"><h3 className="font-medium text-slate-950">{copy.mapRules}</h3><p className="mt-1 text-sm text-slate-600">{copy.mapRulesHint}</p><div className="mt-3 grid min-w-0 gap-3 sm:grid-cols-2">{fixtureParsed.table.columns.map((column) => <label key={column} className="grid min-w-0 gap-1 text-sm text-slate-700">{column}<Input aria-label={`${copy.mapRules}: ${column}`} value={mapping[column] || column} onChange={(event) => renameColumn(column, event.target.value)} /></label>)}</div><div className="mt-4 grid min-w-0 gap-3 sm:grid-cols-2"><fieldset className="min-w-0"><legend className="text-sm font-medium text-slate-800">{copy.required}</legend>{fixtureTable?.columns.map((column) => <label key={column} className="mt-2 flex min-h-10 min-w-0 items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={requiredColumns.includes(column)} onChange={() => toggleColumn(column, requiredColumns, setRequiredColumns)} /><span className="break-words">{column}</span></label>)}</fieldset><fieldset className="min-w-0"><legend className="text-sm font-medium text-slate-800">{copy.dedupe}</legend>{fixtureTable?.columns.map((column) => <label key={column} className="mt-2 flex min-h-10 min-w-0 items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={dedupeColumns.includes(column)} onChange={() => toggleColumn(column, dedupeColumns, setDedupeColumns)} /><span className="break-words">{column}</span></label>)}</fieldset></div></div>
      <div className="min-w-0 rounded-2xl bg-amber-50 p-4"><h3 className="font-medium text-amber-950">{copy.expected}</h3><p className="mt-1 text-sm text-amber-900">{copy.expectedHint}</p><div className="mt-3 max-h-60 max-w-full overflow-auto rounded-xl bg-white p-2">{fixtureTable?.rows.map((row, index) => <label key={index} className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] items-center gap-x-3 border-b border-amber-100 py-2 text-sm last:border-0"><select aria-label={`${copy.expected}: ${index + 1}`} value={dispositions[index] || 'accepted'} onChange={(event) => { const next = [...dispositions]; const selected = event.target.value; next[index] = selected === 'duplicate' || selected === 'missing' ? selected : 'accepted'; setDispositions(next); invalidateCandidate(); }} className="h-10 rounded-md border border-amber-200 bg-white px-2"><option value="accepted">{copy.accepted}</option><option value="duplicate">{copy.duplicate}</option><option value="missing">{copy.fieldError}</option></select><span className="min-w-0 truncate text-slate-700">{Object.values(row).join(' · ') || copy.emptyRow}</span></label>)}</div></div>
      <label className="grid gap-1 text-sm font-medium text-slate-800">{copy.versionName} <span className="font-normal text-slate-500">{copy.versionHint}</span><Input aria-label={copy.versionName} value={versionName} maxLength={80} onChange={(event) => { setVersionName(event.target.value); invalidateCandidate(); }} /></label>
      </> : null}
      {draftMode && fixtureParsed.table ? <>{!versionId ? <Button className="w-fit max-w-full whitespace-normal active:scale-[0.96] transition-transform" onClick={() => void compile()} disabled={busy !== '' || !dedupeColumns.length || !canPreview}><RefreshCw className="mr-2 h-4 w-4" />{copy.compile}</Button> : <div className="flex flex-wrap gap-3 border-t border-slate-100 pt-4"><Button variant="outline" className="max-w-full whitespace-normal active:scale-[0.96] transition-transform" onClick={() => void previewScript()} disabled={busy !== '' || isApproved || !canPreview}>{copy.preview}</Button>{previewPassed ? <Button className="max-w-full whitespace-normal active:scale-[0.96] transition-transform" onClick={() => void approve()} disabled={busy !== '' || isApproved || !canPreview}>{isApproved ? copy.approved : copy.approve}</Button> : null}</div>}{approvedRef.current ? <Button variant="ghost" className="w-fit max-w-full whitespace-normal" onClick={returnToApproved}>{copy.returnApproved}</Button> : null}</> : null}
      {!draftMode && !isApproved && previewPassed ? <Button className="w-fit max-w-full whitespace-normal active:scale-[0.96] transition-transform" onClick={() => void approve()} disabled={busy !== ''}>{copy.approve}</Button> : null}
      {!draftMode && !isApproved && approvedRef.current ? <Button variant="ghost" className="w-fit max-w-full whitespace-normal" onClick={returnToApproved}>{copy.returnApproved}</Button> : null}
      {preview ? <div className={`rounded-2xl p-4 text-sm ${previewPassed ? 'bg-emerald-50 text-emerald-950' : 'bg-rose-50 text-rose-950'}`}><div className="flex items-center gap-2 font-medium"><CheckCircle2 className="h-5 w-5" />{previewPassed ? copy.passed : copy.failed}</div>{report ? <div className="mt-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4"><span>{copy.rows}: {String(report.received || 0)}</span><span>{copy.acceptedCount}: {String(report.accepted || 0)}</span><span>{copy.duplicates}: {String(report.duplicates || 0)}</span><span>{copy.invalid}: {String(report.invalid || 0)}</span></div> : null}{report ? <RowErrors report={report} copy={copy} /> : null}{preview.fixture_results?.map((fixture, index) => <p key={index} className="mt-2 text-xs">{copy.fixtureResult(index + 1, Boolean(fixture.passed))}</p>)}{report ? <Button variant="outline" className="mt-3 active:scale-[0.96] transition-transform" onClick={() => downloadReport(report)}><Download className="mr-2 h-4 w-4" />{copy.download}</Button> : null}</div> : null}
      {isApproved && tableContract ? <div className="rounded-2xl border border-slate-200 p-4"><h3 className="font-medium text-slate-950">{copy.next}</h3><p className="mt-1 text-sm text-slate-600">{copy.inputPinned}</p><p className="mt-1 text-sm text-slate-600">{copy.retention}</p><Textarea aria-label={copy.runInput} value={runText} disabled={busy !== '' || !canExecute} onChange={(event) => changeRunText(event.target.value)} placeholder={copy.runPlaceholder} className="mt-3 min-h-32 font-mono text-xs" />{runParsed.error ? <p role="alert" className="mt-2 text-sm text-rose-700">{runParsed.error}</p> : null}<Button className="mt-3 active:scale-[0.96] transition-transform" onClick={() => void run()} disabled={busy !== '' || !canExecute}><Play className="mr-2 h-4 w-4" />{copy.run}</Button>{!canExecute ? <p className="mt-3 text-sm text-slate-600">{copy.runUnavailable}</p> : null}{queuedRunId ? <p className="mt-3 text-sm text-slate-600">{copy.queued(queuedRunId, activeRun?.id === queuedRunId ? activeRun.status : 'queued')}</p> : null}{runReport ? <div className="mt-3 rounded-xl bg-slate-50 p-3 text-sm"><p className="font-medium">{copy.reportTitle}</p><p className="mt-1">{copy.reportSummary(runReport)}</p><RowErrors report={runReport} copy={copy} /><Button variant="outline" className="mt-3 max-w-full whitespace-normal" onClick={() => downloadReport(runReport)}><Download className="mr-2 h-4 w-4" />{copy.download}</Button></div> : null}</div> : null}
      {isApproved && !tableContract ? <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">{copy.legacy}</div> : null}
      <details className="rounded-2xl bg-slate-50 p-4"><summary className="cursor-pointer text-sm font-medium text-slate-700">{copy.technical}</summary><div className="mt-3 grid gap-3"><label className="grid gap-1 text-sm text-slate-700">{copy.extraRules}<Textarea aria-label={copy.extraRules} value={advancedDescription} disabled={!draftMode} onChange={(event) => { setAdvancedDescription(event.target.value); invalidateCandidate(); }} placeholder={copy.extraRulesPlaceholder} /></label>{artifact ? <pre className="max-h-56 overflow-auto rounded-xl bg-white p-3 text-xs text-slate-700">{artifact.source || copy.sourceUnavailable}</pre> : <p className="text-xs text-slate-500">{copy.sourceHint}</p>}</div></details>
      {error ? <p role="alert" className="text-sm text-rose-700">{error}</p> : null}
    </div>
  </section>;
};
