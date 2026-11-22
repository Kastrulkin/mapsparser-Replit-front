import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { newAuth } from '@/lib/auth_new';
import { browserBearerToken } from '@/lib/browserSessionFetch';

type Board = { id: string; name: string; closed?: boolean };
type TrelloStatus = {
  enabled: boolean; configured: boolean; connected: boolean; needs_reauthorization?: boolean;
  boards: { board_id: string; board_name: string; last_sync_at: string | null }[];
};
type Snapshot = {
  board: Board;
  lists: { id: string; name: string; closed: boolean }[];
  cards: { id: string; name: string; idList: string; closed: boolean; due: string | null; dueComplete: boolean }[];
};

export function TrelloConnectionPanel({ businessId, onChanged }: { businessId: string; onChanged: () => void }) {
  const [status, setStatus] = useState<TrelloStatus | null>(null);
  const [boards, setBoards] = useState<Board[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [saved, setSaved] = useState<string[]>([]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const alive = useRef(true);
  const generation = useRef(0);
  const base = `/api/business/${encodeURIComponent(businessId)}/trello`;

  const api = async (path: string, method = 'GET', body?: object) => {
    const started = generation.current;
    const token = newAuth.getToken() || browserBearerToken();
    const response = await fetch(base + path, {
      method, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    const data = await response.json();
    if (!alive.current || generation.current !== started) throw new DOMException('Cancelled', 'AbortError');
    if (!response.ok || !data.success) {
      if (alive.current && ([401, 403].includes(response.status) || data.error === 'reauthorization_required' || data.error === 'not_connected')) {
        setBoards([]); setSelected([]); setSaved([]); setSnapshot(null); setStatus(null);
      }
      throw new Error(data.message || 'Не удалось загрузить Trello. Повторите попытку.');
    }
    return data;
  };

  const load = async () => {
    const data = await api('/status');
    if (!alive.current) return;
    setStatus(data);
    const ids = data.boards.map((board: { board_id: string }) => board.board_id);
    setSelected(ids); setSaved(ids);
    if (data.connected && !data.needs_reauthorization && data.configured) {
      const available = await api('/boards');
      if (alive.current) setBoards(available.boards);
    } else {
      setBoards([]); setSnapshot(null);
    }
  };

  const run = async (operation: () => Promise<void>) => {
    const started = ++generation.current;
    setBusy(true); setError(''); setMessage('');
    try { await operation(); }
    catch (failure) { if (alive.current && generation.current === started && !(failure instanceof DOMException && failure.name === 'AbortError')) setError(failure instanceof Error ? failure.message : 'Не удалось загрузить Trello.'); }
    finally { if (alive.current && generation.current === started) setBusy(false); }
  };

  useEffect(() => {
    alive.current = true;
    void run(load);
    const params = new URLSearchParams(window.location.search);
    const result = params.get('trello_result');
    if (result) {
      setMessage(result === 'connected' ? 'Trello подключён. Выберите доски для чтения.'
        : result === 'denied' ? 'Доступ Trello не предоставлен. Можно начать подключение снова.'
          : 'Подключение не завершено. Начните снова.');
      params.delete('trello_result');
      window.history.replaceState(null, '', window.location.pathname + '?' + params.toString());
    }
    return () => { alive.current = false; generation.current += 1; };
    // Parent keys this panel by business; pending responses cannot populate another business.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const connect = () => run(async () => {
    const data = await api('/authorize', 'POST');
    const url = new URL(data.authorization_url);
    if (url.origin !== 'https://auth.atlassian.com' || url.pathname !== '/authorize') throw new Error('Адрес подключения не подтверждён.');
    if (alive.current) window.location.assign(url.href);
  });

  const selectionDirty = selected.length !== saved.length || selected.some((id) => !saved.includes(id));
  return (
    <section className="space-y-4 rounded-2xl border border-border bg-background p-5" aria-busy={busy}>
      <div>
        <h3 className="text-base font-semibold">Карточки Trello в LocalOS</h3>
        <p className="mt-1 text-sm text-muted-foreground">Выберите доски, чтобы читать карточки и сроки. Обновление запускается по кнопке.</p>
        <p className="mt-2 text-sm font-medium">Только чтение · пилот для владельца бизнеса</p>
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {message && <p role="status" className="text-sm text-muted-foreground">{message}</p>}
      {!status && <Button variant="outline" disabled={busy} onClick={() => void run(load)}>{busy ? 'Проверяем подключение…' : 'Проверить подключение'}</Button>}
      {status && (!status.enabled || !status.configured) && <p className="text-sm text-muted-foreground">Подключение ещё не настроено администратором. Доски появятся после настройки пилота.</p>}
      {status?.enabled && status.configured && (!status.connected || status.needs_reauthorization) && (
        <Button disabled={busy} onClick={() => void connect()}>{status.needs_reauthorization ? 'Подключить Trello заново' : 'Подключить Trello для чтения'}</Button>
      )}
      {status?.connected && !status.needs_reauthorization && status.configured && <>
        <fieldset disabled={busy} className="space-y-3">
          <legend className="mb-3 text-sm font-medium">Выберите до 10 досок</legend>
          {boards.length === 0 && <p className="text-sm text-muted-foreground">Доступных досок пока нет. Проверьте членство в Trello и обновите список.</p>}
          {boards.map((board) => <div key={board.id} className="flex items-center gap-3">
            <Checkbox id={`trello-${board.id}`} checked={selected.includes(board.id)}
              disabled={busy || (!selected.includes(board.id) && selected.length >= 10)}
              onCheckedChange={(checked) => { setSnapshot(null); setSelected((ids) => checked === true ? [...ids, board.id] : ids.filter((id) => id !== board.id)); }} />
            <Label htmlFor={`trello-${board.id}`}>{board.name}{board.closed ? ' · архив' : ''}</Label>
          </div>)}
        </fieldset>
        <div className="flex flex-wrap gap-2">
          <Button disabled={busy || !selectionDirty} onClick={() => void run(async () => {
            await api('/selection', 'PUT', { board_ids: selected });
            if (!alive.current) return;
            setSaved([...selected]); setSnapshot(null); setMessage('Выбор сохранён. Загрузите карточки выбранной доски.'); onChanged();
          })}>Сохранить выбор</Button>
          <Button variant="outline" disabled={busy} onClick={() => void run(load)}>Обновить список досок</Button>
        </div>
        {saved.filter((id) => boards.some((board) => board.id === id)).map((id) => <div key={id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border p-3">
          <span className="text-sm">{boards.find((board) => board.id === id)?.name}</span>
          <Button variant="ghost" disabled={busy || selectionDirty} onClick={() => void run(async () => {
            const data = await api(`/boards/${id}/snapshot`);
            if (alive.current) { setSnapshot(data.snapshot); setMessage(data.snapshot ? `Сохранённый снимок: ${new Date(data.last_sync_at).toLocaleString('ru-RU')}` : 'Сначала загрузите карточки этой доски.'); }
          })}>Сохранённый снимок</Button>
          <Button variant="outline" disabled={busy || selectionDirty} onClick={() => void run(async () => {
            const data = await api(`/boards/${id}/sync`, 'POST');
            if (!alive.current) return;
            setSnapshot(data.snapshot); setMessage(`Загружено карточек: ${data.card_count}.`); onChanged();
          })}>{busy ? 'Загрузка…' : 'Загрузить карточки'}</Button>
        </div>)}
      </>}
      {snapshot && <div className="space-y-2">
        <h4 className="font-medium">{snapshot.board.name} · снимок на момент загрузки</h4>
        {snapshot.cards.length === 0 && <p className="text-sm text-muted-foreground">На доске нет карточек.</p>}
        <p className="text-sm text-muted-foreground">Карточек: {snapshot.cards.length}. Показаны первые 100.</p>
        <ul className="max-h-96 space-y-2 overflow-auto" aria-label="Карточки Trello">
          {snapshot.cards.slice(0, 100).map((card) => <li key={card.id} className="rounded-xl border border-border p-3 text-sm">
            <div className="font-medium">{card.name}{card.closed ? ' · архив' : ''}</div>
            <div className="text-muted-foreground">{snapshot.lists.find((list) => list.id === card.idList)?.name || 'Список недоступен'}
              {card.due ? ` · срок: ${new Date(card.due).toLocaleString('ru-RU')}${card.dueComplete ? ' · выполнен' : ''}` : ''}</div>
          </li>)}
        </ul>
      </div>}
      {status?.connected && <Button variant="outline" disabled={busy} onClick={() => void run(async () => {
        await api('/connection', 'DELETE');
        if (!alive.current) return;
        setBoards([]); setSelected([]); setSaved([]); setSnapshot(null);
        setStatus({ ...status, connected: false }); setMessage('Подключение и сохранённые снимки удалены из LocalOS.'); onChanged();
      })}>Отключить в LocalOS</Button>}
    </section>
  );
}
