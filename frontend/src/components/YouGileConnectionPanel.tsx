import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { newAuth } from '@/lib/auth_new';
import { browserBearerToken } from '@/lib/browserSessionFetch';

type Option = { id: string; title: string };
type Status = { enabled: boolean; connected: boolean; configured: boolean; can_configure: boolean; can_write: boolean;
  selection: { project_id?: string; board_id?: string; column_id?: string; board_name?: string; column_name?: string } };
type Task = { id: string; title: string; completed: boolean; assigned?: string[]; deadline?: { deadline: number }; columnId: string };
type Data = { items: Task[]; users: { id: string; name: string }[]; columns: Option[] };
type Preview = { status: string; chat_response: string; approval?: { action_id: string } };

export function YouGileConnectionPanel(props: { businessId: string; onChanged: () => void }) {
  return <YouGilePanel key={props.businessId} {...props} />;
}

function YouGilePanel({ businessId, onChanged }: { businessId: string; onChanged: () => void }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [apiKey, setApiKey] = useState('');
  const [projects, setProjects] = useState<Option[]>([]);
  const [boards, setBoards] = useState<Option[]>([]);
  const [columns, setColumns] = useState<Option[]>([]);
  const [project, setProject] = useState('');
  const [board, setBoard] = useState('');
  const [column, setColumn] = useState('');
  const [data, setData] = useState<Data | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [assigned, setAssigned] = useState('');
  const [deadline, setDeadline] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const generation = useRef(0);
  const catalogVersion = useRef(0);
  const previewRegion = useRef<HTMLDivElement>(null);
  const base = `/api/business/${encodeURIComponent(businessId)}/yougile`;

  const api = async (path: string, method = 'GET', body?: object, absolute = false) => {
    const started = generation.current;
    const token = newAuth.getToken() || browserBearerToken();
    const response = await fetch(absolute ? path : base + path, { method,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}) });
    const result = await response.json();
    if (generation.current !== started) throw new DOMException('Cancelled', 'AbortError');
    if (!response.ok || result.success === false) {
      if ([401, 403].includes(response.status) || result.code === 'not_connected') {
        setData(null); setPreview(null); setProjects([]); setBoards([]); setColumns([]);
      }
      throw new Error(result.error || 'Не удалось загрузить YouGile. Повторите позже.');
    }
    return result;
  };
  const loadTasks = async () => { setData(null); setData(await api('/tasks')); };
  const load = async () => {
    const next: Status = await api('/status');
    setStatus(next);
    if (next.connected && next.can_configure) setProjects((await api('/catalog')).items);
    if (next.configured) await loadTasks();
  };
  const run = async (operation: () => Promise<void>) => {
    if (busy) return;
    const started = generation.current;
    setBusy(true); setError(''); setMessage('');
    try { await operation(); }
    catch (reason) { if (generation.current === started && !(reason instanceof DOMException && reason.name === 'AbortError')) setError(reason instanceof Error ? reason.message : 'Не удалось выполнить действие.'); }
    finally { if (generation.current === started) setBusy(false); }
  };
  useEffect(() => {
    generation.current += 1;
    void run(load);
    return () => { generation.current += 1; };
  }, []);
  useEffect(() => { setPreview(null); }, [title, description, assigned, deadline]);
  useEffect(() => {
    if (preview?.approval) {
      previewRegion.current?.focus();
      previewRegion.current?.scrollIntoView?.({ block: 'center', behavior: 'smooth' });
    }
  }, [preview]);

  const chooseProject = async (id: string) => {
    const version = ++catalogVersion.current;
    setProject(id); setBoard(''); setColumn(''); setBoards([]); setColumns([]); setPreview(null); setError('');
    if (!id) return;
    try { const result = await api(`/catalog?project_id=${encodeURIComponent(id)}`); if (catalogVersion.current === version) setBoards(result.items); }
    catch (reason) { if (catalogVersion.current === version && reason instanceof Error && reason.name !== 'AbortError') setError(reason.message); }
  };
  const chooseBoard = async (id: string) => {
    const version = ++catalogVersion.current;
    setBoard(id); setColumn(''); setColumns([]); setPreview(null); setError('');
    if (!id) return;
    try { const result = await api(`/catalog?project_id=${encodeURIComponent(project)}&board_id=${encodeURIComponent(id)}`); if (catalogVersion.current === version) setColumns(result.items); }
    catch (reason) { if (catalogVersion.current === version && reason instanceof Error && reason.name !== 'AbortError') setError(reason.message); }
  };
  const prepare = async (args: object) => {
    setPreview(null);
    const result: { operator_result: Preview } = await api('/tasks/preview', 'POST', args);
    if (result.operator_result.status !== 'approval_required') throw new Error(result.operator_result.chat_response);
    setPreview(result.operator_result);
  };
  const selectClass = 'flex min-h-11 w-full rounded-md border border-input bg-background px-3 py-2 text-sm';
  return <section className="space-y-5" aria-label="Подключение YouGile">
    <div><h3 className="font-semibold">Задачи команды в YouGile</h3><p className="text-sm text-muted-foreground">Выберите рабочую доску, чтобы видеть задачи и готовить поручения из LocalOS. Создание и завершение требуют проверки.</p></div>
    {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    {message ? <p role="status" className="text-sm">{message}</p> : null}
    {!status ? <p role="status">{busy ? 'Загружаем подключение…' : 'Подключение не загружено.'}</p> : !status.enabled ? <p>Подключение YouGile пока выключено администратором.</p> : <>
      {!status.connected ? status.can_configure ? <form className="grid gap-3" onSubmit={event => { event.preventDefault(); void run(async () => {
        await api('/connection', 'POST', { api_key: apiKey }); setApiKey(''); await load(); onChanged();
      }); }}>
        <Label htmlFor="yougile-key">API-ключ вашей команды YouGile</Label>
        <Input id="yougile-key" type="password" autoComplete="off" value={apiKey} onChange={event => setApiKey(event.target.value)} disabled={busy} />
        <p className="text-sm text-muted-foreground">Ключ хранится зашифрованно. Подключение проверит доступ и не создаст задач.</p>
        <a href="https://yougile.com/api/" target="_blank" rel="noopener noreferrer" className="text-sm text-primary underline">Как получить ключ: документация YouGile</a>
        <Button type="submit" disabled={busy || !apiKey.trim()}>Подключить YouGile</Button>
      </form> : <p>Попросите владельца бизнеса подключить YouGile.</p> : <>
        <p className="text-sm">{status.configured ? `Рабочая доска: ${status.selection.board_name}. Новые задачи: ${status.selection.column_name}.` : 'Подключено. Выберите, куда сохранять новые задачи.'}</p>
        {status.can_configure ? <details open={!status.configured}><summary className="cursor-pointer text-sm font-medium">Выбрать рабочую доску</summary><div className="grid gap-3 pt-3">
          <Label htmlFor="yougile-project">Проект</Label><select id="yougile-project" className={selectClass} value={project} disabled={busy} onChange={event => void chooseProject(event.target.value)}><option value="">Выберите проект</option>{projects.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select>
          <Label htmlFor="yougile-board">Доска</Label><select id="yougile-board" className={selectClass} value={board} disabled={busy || !project} onChange={event => void chooseBoard(event.target.value)}><option value="">Выберите доску</option>{boards.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select>
          <Label htmlFor="yougile-column">Колонка для новых задач</Label><select id="yougile-column" className={selectClass} value={column} disabled={busy || !board} onChange={event => { setColumn(event.target.value); setPreview(null); }}><option value="">Выберите колонку</option>{columns.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select>
          <Button disabled={busy || !column} onClick={() => void run(async () => { await api('/selection', 'PUT', { project_id: project, board_id: board, column_id: column }); setPreview(null); await load(); onChanged(); })}>Использовать эту доску</Button>
        </div></details> : null}
        {status.configured ? <>
          <div className="flex items-center justify-between gap-3"><h4 className="font-medium">Задачи</h4><Button variant="outline" disabled={busy} onClick={() => void run(loadTasks)}>Обновить задачи</Button></div>
          {!data ? <p>Задачи не загружены.</p> : !data.items.length ? <p className="text-sm text-muted-foreground">На доске пока нет задач. Подготовьте первое поручение, например «Собрать фото работ до пятницы».</p> : <ul className="space-y-2">{data.items.slice(0, 100).map(task => <li key={task.id} className="rounded-md border p-3 text-sm"><div className="font-medium">{task.title}</div><div>{task.completed ? 'Выполнена' : 'В работе'} · {data.columns.find(c => c.id === task.columnId)?.title}</div>{task.deadline?.deadline ? <div>Срок: {new Date(task.deadline.deadline).toLocaleString()}</div> : null}{task.assigned?.length ? <div>Исполнители: {task.assigned.map(id => data.users.find(u => u.id === id)?.name || id).join(', ')}</div> : null}{status.can_write && !task.completed ? <Button variant="outline" size="sm" disabled={busy} onClick={() => void run(() => prepare({ operation: 'complete', task_id: task.id }))}>Подготовить завершение</Button> : null}</li>)}</ul>}
          {data && data.items.length > 100 ? <p className="text-sm">Показаны первые 100 из {data.items.length} задач.</p> : null}
          {status.can_write && data ? <details><summary className="cursor-pointer font-medium">Новое поручение</summary><form className="grid gap-3 pt-3" onSubmit={event => { event.preventDefault(); void run(() => prepare({ operation: 'create', title, description, assigned: assigned ? [assigned] : [], ...(deadline ? { deadline: new Date(deadline).toISOString() } : {}) })); }}>
            <Label htmlFor="yougile-title">Что нужно сделать</Label><Input id="yougile-title" value={title} maxLength={300} required disabled={busy} onChange={event => setTitle(event.target.value)} />
            <Label htmlFor="yougile-description">Подробности</Label><Textarea id="yougile-description" value={description} maxLength={5000} disabled={busy} onChange={event => setDescription(event.target.value)} />
            <Label htmlFor="yougile-assignee">Ответственный</Label><select id="yougile-assignee" className={selectClass} value={assigned} disabled={busy} onChange={event => setAssigned(event.target.value)}><option value="">Без исполнителя</option>{data.users.map(user => <option key={user.id} value={user.id}>{user.name}</option>)}</select>
            <Label htmlFor="yougile-deadline">Срок по времени этого устройства</Label><Input id="yougile-deadline" type="datetime-local" value={deadline} disabled={busy} onChange={event => setDeadline(event.target.value)} />
            <Button type="submit" disabled={busy || !title.trim()}>Проверить поручение</Button>
          </form></details> : null}
        </> : null}
        {preview?.approval ? <div ref={previewRegion} tabIndex={-1} className="space-y-3 rounded-md border p-4" role="region" aria-label="Проверка поручения"><p className="whitespace-pre-wrap text-sm">{preview.chat_response}</p><div className="flex flex-wrap gap-2"><Button disabled={busy} onClick={() => void run(async () => {
          const result = await api(`/api/operator/actions/${encodeURIComponent(preview.approval?.action_id || '')}/confirm`, 'POST', { business_id: businessId }, true);
          if (result.operator_result?.status !== 'completed') throw new Error(result.operator_result?.chat_response || 'Изменение не подтверждено.');
          setPreview(null); setTitle(''); setDescription(''); setAssigned(''); setDeadline(''); setMessage(result.operator_result.chat_response); await loadTasks();
        })}>Подтвердить в YouGile</Button><Button variant="outline" disabled={busy} onClick={() => void run(async () => {
          await api(`/api/operator/actions/${encodeURIComponent(preview.approval?.action_id || '')}/reject`, 'POST', { business_id: businessId }, true); setPreview(null);
        })}>Отмена</Button></div></div> : null}
        {status.can_configure ? <details><summary className="cursor-pointer text-sm">Отключение</summary><p className="py-2 text-sm text-muted-foreground">Ключ будет удалён из LocalOS. Задачи в YouGile сохранятся.</p><Button variant="outline" disabled={busy} onClick={() => void run(async () => { await api('/connection', 'DELETE'); setData(null); setPreview(null); setProjects([]); setBoards([]); setColumns([]); setProject(''); setBoard(''); setColumn(''); await load(); onChanged(); })}>Отключить YouGile</Button></details> : null}
      </>}
    </>}
    {!status && !busy ? <Button variant="outline" onClick={() => void run(load)}>Повторить загрузку</Button> : null}
  </section>;
}
