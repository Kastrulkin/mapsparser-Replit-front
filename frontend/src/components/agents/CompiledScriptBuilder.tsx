import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, Play, RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { newAuth } from '@/lib/auth_new';
import type { AgentBlueprintDetails } from '@/pages/dashboard/agents/types';

type Artifact = {
  source?: string;
  manifest?: Record<string, unknown>;
  fixtures?: unknown;
  artifact_hash?: string;
};

type Candidate = { id?: string; compiled_state?: string };
type CompileResponse = { success?: boolean; candidate_version?: Candidate; artifact?: Artifact; code?: string };
type PreviewResponse = { success?: boolean; version_id?: string; preview?: { result?: unknown; output?: unknown; status?: string; fixture_digest?: string; fixture_results?: Array<{ source?: string; passed?: boolean; expected?: unknown; actual?: unknown }> }; approval_digest?: string; code?: string };
type ApproveResponse = { success?: boolean; version_id?: string; state?: string; code?: string };
type RunResponse = { success?: boolean; run?: { id?: string }; status?: string; code?: string };

type Props = {
  blueprintId?: string | null;
  blueprintDetails?: AgentBlueprintDetails | null;
  onRunQueued?: (runId: string) => void;
};

const artifactFromVersion = (version: Record<string, unknown> | null | undefined): Artifact | null => {
  const raw = version?.compiled_artifact_json;
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) return raw;
  if (typeof raw === 'string') {
    const parsed = parseObject(raw);
    return parsed;
  }
  return null;
};

const parseObject = (value: string) => {
  try {
    const parsed: unknown = JSON.parse(value || '{}');
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
};

const errorMessage = (error: unknown, fallback: string) => {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === 'object' && error !== null && 'response' in error && error.response && typeof error.response === 'object' && 'data' in error.response && error.response.data && typeof error.response.data === 'object' && 'message' in error.response.data && typeof error.response.data.message === 'string') return error.response.data.message;
  return fallback;
};

export const CompiledScriptBuilder = ({ blueprintId, blueprintDetails, onRunQueued }: Props) => {
  const [description, setDescription] = useState('');
  const [rules, setRules] = useState('');
  const [fixtureInputText, setFixtureInputText] = useState('{}');
  const [expectedText, setExpectedText] = useState('{}');
  const [runInputText, setRunInputText] = useState('{}');
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [versionId, setVersionId] = useState('');
  const [approvalDigest, setApprovalDigest] = useState('');
  const [preview, setPreview] = useState<PreviewResponse['preview'] | null>(null);
  const [busy, setBusy] = useState<'compile' | 'preview' | 'approve' | 'run' | ''>('');
  const [error, setError] = useState('');
  const idempotencyKey = useRef('');
  const requestRevision = useRef(0);
  const hydratedVersion = useRef('');
  const manuallyInvalidated = useRef(false);

  useEffect(() => {
    requestRevision.current += 1;
    manuallyInvalidated.current = false;
    setArtifact(null); setVersionId(''); setApprovalDigest(''); setPreview(null); setError(''); setBusy(''); idempotencyKey.current = ''; hydratedVersion.current = '';
  }, [blueprintId]);

  useEffect(() => {
    const candidate = blueprintDetails?.candidate_version;
    const active = blueprintDetails?.active_version;
    const candidateState = typeof candidate?.compiled_state === 'string' ? candidate.compiled_state : '';
    const version = ['ready_approval', 'approved', 'active'].includes(candidateState) ? candidate : active;
    const candidateId = typeof version?.id === 'string' ? version.id : '';
    const state = typeof version?.compiled_state === 'string' ? version.compiled_state : '';
    if (manuallyInvalidated.current || !candidateId || !['ready_approval', 'approved', 'active'].includes(state) || hydratedVersion.current === candidateId || versionId) return;
    const nextArtifact = artifactFromVersion(version);
    if (!nextArtifact) return;
    hydratedVersion.current = candidateId;
    setVersionId(candidateId); setArtifact(nextArtifact);
    if (state === 'approved' || state === 'active') setApprovalDigest('approved');
  }, [blueprintId, blueprintDetails?.candidate_version, blueprintDetails?.active_version, versionId]);

  const invalidatePreview = () => {
    setPreview(null);
    setApprovalDigest('');
    idempotencyKey.current = '';
  };

  const invalidateCandidate = () => {
    requestRevision.current += 1;
    manuallyInvalidated.current = true;
    setArtifact(null); setVersionId(''); setApprovalDigest(''); setPreview(null); setBusy(''); idempotencyKey.current = ''; hydratedVersion.current = '';
  };

  const compile = async () => {
    const input = parseObject(fixtureInputText); const expected = parseObject(expectedText);
    if (!blueprintId || !description.trim() || !input || !expected) { setError('Добавьте пример входных данных и ожидаемый результат в JSON.'); return; }
    setBusy('compile'); setError(''); invalidatePreview();
    const revision = requestRevision.current + 1;
    requestRevision.current = revision;
    try {
      const response: CompileResponse = await newAuth.makeRequest(`/agent-blueprints/${encodeURIComponent(blueprintId)}/compiled-script/compile`, {
        method: 'POST', body: JSON.stringify({ description: `${description.trim()}\n\nПравила:\n${rules.trim()}`, fixtures: [{ input, expected, source: 'user' }] }),
      });
      if (requestRevision.current !== revision) return;
      if (!response.success || !response.candidate_version?.id) throw new Error(response.code || 'Не удалось подготовить скрипт.');
      setVersionId(response.candidate_version.id); setArtifact(response.artifact || null);
    } catch (requestError) { if (requestRevision.current === revision) setError(errorMessage(requestError, 'Не удалось подготовить скрипт.')); } finally { if (requestRevision.current === revision) setBusy(''); }
  };

  const previewScript = async () => {
    const input = parseObject(fixtureInputText); const expected = parseObject(expectedText);
    if (!blueprintId || !versionId || !input || !expected) { setError('Введите корректные JSON-данные для примера и ожидаемого результата.'); return; }
    setBusy('preview'); setError(''); invalidatePreview();
    const revision = requestRevision.current + 1;
    requestRevision.current = revision;
    try {
      const response: PreviewResponse = await newAuth.makeRequest(`/agent-blueprints/${encodeURIComponent(blueprintId)}/compiled-script/preview`, { method: 'POST', body: JSON.stringify({ version_id: versionId, input }) });
      if (requestRevision.current !== revision) return;
      if (!response.success || !response.approval_digest) throw new Error(response.code || 'Проверка на примере не прошла.');
      setPreview(response.preview || null); setApprovalDigest(response.approval_digest);
    } catch (requestError) { if (requestRevision.current === revision) setError(errorMessage(requestError, 'Защищённый runtime недоступен или пример не прошёл проверку.')); } finally { if (requestRevision.current === revision) setBusy(''); }
  };

  const approve = async () => {
    if (!blueprintId || !versionId || !approvalDigest || !preview) return;
    setBusy('approve'); setError('');
    const revision = requestRevision.current;
    try {
      const response: ApproveResponse = await newAuth.makeRequest(`/agent-blueprints/${encodeURIComponent(blueprintId)}/compiled-script/approve`, { method: 'POST', body: JSON.stringify({ version_id: versionId, approval_digest: approvalDigest, fixture_digest: preview.fixture_digest }) });
      if (requestRevision.current !== revision) return;
      if (!response.success) throw new Error(response.code || 'Подтверждение не выполнено.');
      setApprovalDigest('approved');
      setRunInputText(fixtureInputText);
    } catch (requestError) { if (requestRevision.current === revision) setError(errorMessage(requestError, 'Не удалось подтвердить эту версию. Выполните preview ещё раз.')); } finally { if (requestRevision.current === revision) setBusy(''); }
  };

  const run = async () => {
    const input = parseObject(runInputText);
    if (!blueprintId || !versionId || approvalDigest !== 'approved' || !input || busy) return;
    if (!idempotencyKey.current) idempotencyKey.current = globalThis.crypto?.randomUUID?.() || `compiled-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setBusy('run'); setError('');
    const revision = requestRevision.current;
    try {
      const response: RunResponse = await newAuth.makeRequest(`/agent-blueprints/${encodeURIComponent(blueprintId)}/compiled-script/run`, { method: 'POST', body: JSON.stringify({ version_id: versionId, input, idempotency_key: idempotencyKey.current }) });
      if (requestRevision.current !== revision) return;
      if (!response.success || !response.run?.id) throw new Error(response.code || 'Не удалось поставить запуск в очередь.');
      onRunQueued?.(response.run.id);
    } catch (requestError) { if (requestRevision.current === revision) setError(errorMessage(requestError, 'Не удалось поставить запуск в очередь.')); } finally { if (requestRevision.current === revision) setBusy(''); }
  };

  if (!blueprintId) return null;
  const isApproved = approvalDigest === 'approved';
  return <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm" aria-label="Compiled script">
    <h2 className="text-lg font-semibold text-slate-950">Скрипт для повторяемой задачи</h2>
    <p className="mt-1 text-sm leading-6 text-slate-600">Опишите работу один раз. LocalOS подготовит версию, вы проверите её на примере и подтвердите. Затем выполняется сохранённый скрипт; модель не вызывается при каждом запуске.</p>
    <details className="mt-4 group"><summary className="cursor-pointer text-sm font-medium text-slate-700">Настроить повторяемую задачу</summary><div className="mt-3 grid gap-3"><label className="text-sm font-medium text-slate-800">Что должен делать сотрудник?<Textarea value={description} onChange={(event) => { setDescription(event.target.value); invalidateCandidate(); }} placeholder="Например: проверить строки таблицы и подготовить список ошибок" /></label><label className="text-sm font-medium text-slate-800">Правила и ограничения<Textarea value={rules} onChange={(event) => { setRules(event.target.value); invalidateCandidate(); }} placeholder="Что разрешено, что нельзя менять, как выглядит результат" /></label><label className="text-sm font-medium text-slate-800">Пример входных данных (JSON)<Textarea value={fixtureInputText} onChange={(event) => { setFixtureInputText(event.target.value); invalidateCandidate(); }} /></label><label className="text-sm font-medium text-slate-800">Ожидаемый результат для проверки (JSON)<Textarea value={expectedText} onChange={(event) => { setExpectedText(event.target.value); invalidateCandidate(); }} /></label><Button onClick={() => void compile()} disabled={busy !== '' || !description.trim()}><RefreshCw className="mr-2 h-4 w-4" />Подготовить скрипт</Button></div></details>
    {artifact ? <details className="mt-4 rounded-2xl bg-slate-50 p-3"><summary className="cursor-pointer text-sm font-medium text-slate-700">Техническая версия скрипта</summary><pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap text-xs text-slate-700">{artifact.source || 'Исходный текст недоступен'}</pre></details> : null}
    {versionId ? <div className="mt-4 border-t border-slate-100 pt-4"><Button variant="outline" onClick={() => void previewScript()} disabled={busy !== ''}>Проверить на примере</Button></div> : null}
    {preview ? <div className="mt-4 rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-950"><div className="flex gap-2 font-medium"><CheckCircle2 className="h-5 w-5" />Проверка пройдена</div><pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(preview.result || preview.output || preview, null, 2)}</pre>{preview.fixture_results?.map((fixture, index) => <p key={index} className="mt-1 text-xs">Пример {index + 1}: {fixture.passed ? 'совпадает с ожидаемым результатом' : 'не совпадает'}</p>)}<Button className="mt-3" onClick={() => void approve()} disabled={busy !== '' || isApproved}>{isApproved ? 'Версия подтверждена' : 'Подтвердить эту версию'}</Button></div> : null}
    {isApproved ? <div className="mt-4 border-t border-slate-100 pt-4"><label className="text-sm font-medium text-slate-800">Данные для запуска (JSON)<Textarea value={runInputText} onChange={(event) => { setRunInputText(event.target.value); idempotencyKey.current = ''; }} /></label><Button className="mt-3" onClick={() => void run()} disabled={busy !== ''}><Play className="mr-2 h-4 w-4" />Запустить скрипт</Button></div> : null}
    {error ? <p role="alert" className="mt-3 text-sm text-rose-700">{error}</p> : null}
  </section>;
};
