import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { api } from '@/services/api';
import { API_URL } from '@/config/api';
import { newAuth } from '@/lib/auth_new';
import type { AgentBlueprintDetails } from '@/pages/dashboard/agents/types';

const record = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? Object.fromEntries(Object.entries(value)) : {};

export function HandoffPhotoPreview({ assetId }: { assetId: string }) {
  const [image, setImage] = useState('');
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl = '';
    setImage(''); setFailed(false);
    const load = async () => {
      try {
        const token = newAuth.getToken();
        const response = await fetch(`${API_URL}/api/media-intelligence/photos/${encodeURIComponent(assetId)}/file`, {
          signal: controller.signal, headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        });
        if (!response.ok) throw new Error('photo_unavailable');
        const blob = await response.blob();
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(blob); setImage(objectUrl);
      } catch {
        if (!controller.signal.aborted) setFailed(true);
      }
    };
    void load();
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [assetId]);
  if (failed) return <p role="alert" className="text-sm text-red-700">Не удалось загрузить выбранное фото. Проверьте его в публикации перед утверждением.</p>;
  return image ? <img src={image} alt="Фото для передачи через бот" className="mt-2 h-40 w-full rounded-xl bg-slate-50 object-contain" /> : <p role="status" className="text-sm text-slate-500">Загружаем выбранное фото…</p>;
}

export function hasContentHandoff(details: AgentBlueprintDetails | null | undefined) {
  const version = details?.candidate_version || details?.active_version;
  return Array.isArray(version?.steps_json) && version.steps_json.some((step: unknown) => record(step).capability === 'content.publish_handoff');
}

export function ContentHandoffProgram({ blueprintId, details, onRunQueued }: {
  blueprintId: string; details: AgentBlueprintDetails | null; onRunQueued: (id: string) => void;
}) {
  const saved = details?.compiled_approved_version || details?.candidate_version;
  const [versionId, setVersionId] = useState(String(saved?.id || ''));
  const [state, setState] = useState(String(saved?.compiled_state || 'legacy'));
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [preview, setPreview] = useState<Record<string, unknown>>({});
  const [exampleAccepted, setExampleAccepted] = useState(false);
  const inFlight = useRef(false);
  const runKey = useRef('');
  const runSnapshot = useRef('');
  const target = useRef(blueprintId);
  const artifact = record(saved?.compiled_artifact_json);
  const [artifactHash, setArtifactHash] = useState(String(artifact.artifact_hash || ''));
  useEffect(() => {
    target.current = blueprintId;
    setVersionId(String(saved?.id || '')); setState(String(saved?.compiled_state || 'legacy'));
    setArtifactHash(String(record(saved?.compiled_artifact_json).artifact_hash || ''));
    setPreview({}); setError(''); setBusy(''); setExampleAccepted(false); runKey.current = ''; runSnapshot.current = '';
  }, [blueprintId, saved?.id]);
  const perform = async (operation: string) => {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(operation); setError('');
    const selected = blueprintId;
    try {
      if (operation === 'compile') {
        const response = await api.post(`/agent-blueprints/${selected}/compiled-script/compile`, {
          content_handoff: true, description: String(details?.candidate_version?.goal || details?.active_version?.goal || 'Передавать готовые посты по сохранённым условиям'),
          idempotency_key: `content-compile:${selected}:${versionId}`,
          fixtures: [{ source: 'user', input: { posts: [{ post_id: 'пример', revision: 'версия-1', eligible: true }] }, expected: { requests: [{ post_id: 'пример', revision: 'версия-1' }] } }],
        });
        if (target.current !== selected) return;
        setVersionId(String(response.data.candidate_version?.id || '')); setState('checking');
        setArtifactHash(String(response.data.artifact?.artifact_hash || ''));
      } else if (operation === 'preview') {
        const snapshot = await api.post(`/agent-blueprints/${selected}/compiled-script/snapshots`, { source_kind: 'content_plan', version_id: versionId });
        const response = await api.post(`/agent-blueprints/${selected}/compiled-script/preview`, { version_id: versionId, snapshot_id: snapshot.data.snapshot.id });
        if (target.current !== selected) return;
        setPreview({ ...record(response.data.preview), input: snapshot.data.snapshot.input });
        setState(response.data.preview?.status === 'passed' ? 'ready_approval' : 'needs_fix');
      } else if (operation === 'approve') {
        if (preview.status !== 'passed' || !preview.fixture_digest || !record(preview.delivery_context).digest) {
          throw new Error('Сначала обновите предпросмотр материалов и получателя. Отправки при проверке нет.');
        }
        await api.post(`/agent-blueprints/${selected}/compiled-script/approve`, { version_id: versionId, approval_digest: artifactHash, fixture_digest: preview.fixture_digest,
          delivery_context_digest: record(preview.delivery_context).digest });
        if (target.current === selected) setState('approved');
      } else {
        if (!runSnapshot.current) {
          const snapshot = await api.post(`/agent-blueprints/${selected}/compiled-script/snapshots`, { source_kind: 'content_plan', version_id: versionId });
          if (target.current !== selected) return;
          runSnapshot.current = String(snapshot.data.snapshot.id);
        }
        if (!runKey.current) runKey.current = `content-test:${selected}:${Date.now()}`;
        const response = await api.post(`/agent-blueprints/${selected}/compiled-script/run`, { version_id: versionId, snapshot_id: runSnapshot.current, idempotency_key: runKey.current });
        if (target.current === selected && response.data.run?.id) onRunQueued(String(response.data.run.id));
      }
    } catch (failure) {
      if (target.current === selected) setError(failure instanceof Error ? failure.message : 'Не удалось выполнить шаг. Материалы не отправляйте повторно, пока не проверен журнал.');
    } finally {
      inFlight.current = false;
      if (target.current === selected) setBusy('');
    }
  };
  const input = record(preview.input);
  const context = record(preview.delivery_context);
  const scope = record(context.scope || record(artifact.manifest).content_handoff_contract && record(record(artifact.manifest).content_handoff_contract).scope);
  const posts = Array.isArray(input.posts) ? input.posts : [];
  return <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
    <h2 className="text-lg font-semibold">Передача готовых публикаций через бот</h2>
    <p className="text-sm text-slate-600">Сначала проверьте программу и материалы, затем утвердите условия. Передача сотруднику не означает публикацию на площадке.</p>
    {Object.keys(scope).length > 0 && <div className="rounded-xl bg-slate-50 p-3 text-sm space-y-1">
      <p className="font-medium">{String(context.business_name || 'Выбранная точка')} · {String(context.address || '')}</p>
      <p>Получатель: {String(context.recipient_name || 'Проверяется при предпросмотре')}{context.telegram_id ? ` · Telegram ID ${String(context.telegram_id)}` : ''}</p>
      <p>За {String(scope.lead_days)} дн. до публикации, в {String(scope.time)} · {String(scope.timezone)}</p>
      <p>Каналы: {Array.isArray(scope.platforms) ? scope.platforms.join(', ') : ''}. Только готовые версии с фото.</p>
    </div>}
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {busy && <p role="status" className="text-sm text-slate-600">{busy === 'compile' ? 'Создаём и сохраняем программу…' : busy === 'preview' ? 'Читаем план и проверяем выбор материалов. Отправки нет…' : busy === 'approve' ? 'Сохраняем ваше подтверждение условий…' : 'Принимаем тестовый запуск. Результат появится в журнале…'}</p>}
    {(state === 'legacy' || state === 'needs_fix') && <>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={exampleAccepted} onChange={(event) => setExampleAccepted(event.target.checked)} />Ожидаемый результат: готовый комплект с фото передаётся; неполный пост и уже переданная версия пропускаются.</label>
      <Button disabled={Boolean(busy) || !exampleAccepted} onClick={() => void perform('compile')}>Создать программу по условиям</Button>
    </>}
    {(state === 'checking' || state === 'ready_approval') && <Button variant={preview.status === 'passed' ? 'outline' : 'default'} disabled={Boolean(busy)} onClick={() => void perform('preview')}>Проверить на текущем плане без отправки</Button>}
    {posts.map((post: unknown) => { const row = record(post); return <div key={String(row.post_id)} className="border-t border-slate-100 pt-3 text-sm"><p className="font-medium">{String(row.platform || '')} · {row.eligible ? 'Готово к передаче' : String(row.blocked_reason || 'Не готово')}</p><p className="mt-1 whitespace-pre-wrap">{String(row.text || '')}</p>{row.photo_asset_id ? <HandoffPhotoPreview assetId={String(row.photo_asset_id)} /> : <p className="text-slate-500">Фото не выбрано</p>}</div>; })}
    {state === 'ready_approval' && preview.status === 'passed' && <Button disabled={Boolean(busy)} onClick={() => void perform('approve')}>Утвердить программу и условия передачи</Button>}
    {(state === 'approved' || state === 'active') && <><p className="text-sm text-slate-600">Программа утверждена. Регулярное расписание включается отдельно; сейчас можно выполнить тест на выбранного получателя.</p><Button disabled={Boolean(busy) || details?.compiled_access?.execute !== true} onClick={() => void perform('run')}>Передать готовые материалы — тест</Button></>}
  </section>;
}
