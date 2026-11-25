import { useEffect, useId, useRef, useState, type ReactNode, type RefObject } from 'react';
import { CardServiceDetail, CardServiceDraft, CardServiceList, CardServiceRow, CardServiceWorkspace } from '@/components/dashboard/CardServiceList';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export type ServiceProposal = {
  key: string;
  service_id?: string | null;
  has_original?: boolean;
  original: string;
  description: string;
  proposed: string;
  proposed_description: string;
  keywords: { text: string; views: number | null; source: string; dated: string }[];
  source_url?: string;
  category?: string;
  accepted?: boolean;
};

export type SaveServiceProposal = (action: { action: 'service'; key: string; name: string; description: string }) => Promise<boolean>;

const savedStatus = { label: 'Сохранено', className: 'border-emerald-200 bg-emerald-50 text-emerald-700' };
const updateStatus = { label: 'На проверке', className: 'border-amber-200 bg-amber-50 text-amber-800' };
const newStatus = { label: 'Новая услуга', className: 'border-slate-200 bg-slate-100 text-slate-700' };

const serviceTitle = (item: ServiceProposal) => item.has_original ? item.original : item.proposed;
export const serviceProposalStatus = (item: ServiceProposal) => item.accepted ? savedStatus : item.has_original ? updateStatus : newStatus;

export function ServiceProposals({ items, send, disabled = false, error = '' }: {
  items: ServiceProposal[];
  send?: SaveServiceProposal;
  disabled?: boolean;
  error?: string;
}) {
  const [query, setQuery] = useState('');
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const detail = useRef<HTMLElement | null>(null);
  const active = useRef<string | null>(null);
  const detailId = useId();
  const selected = items.find(item => item.key === selectedKey);
  const search = query.trim().toLowerCase();
  const visible = items.filter(item => item.proposed.toLowerCase().includes(search)
    || (item.has_original && item.original.toLowerCase().includes(search)));

  useEffect(() => {
    if (selectedKey) detail.current?.focus();
  }, [selectedKey]);

  const close = (key: string) => {
    if (active.current !== key) return;
    active.current = null;
    setSelectedKey(null);
    trigger.current?.focus();
  };

  return <div className="w-full overflow-hidden rounded-3xl border border-slate-200/80 bg-white/90 shadow-sm"
    onKeyDown={event => {
      if (event.key === 'Escape' && selected) {
        event.stopPropagation();
        close(selected.key);
      }
    }}>
    <CardServiceWorkspace
      queue={<>
        {items.length > 8 && <div className="px-3 pt-3">
          <Input type="search" aria-label="Поиск по услугам" placeholder="Поиск по услугам" value={query} onChange={event => setQuery(event.target.value)} />
        </div>}
        <div className="max-h-96 overflow-y-auto">
          <CardServiceList heading="Очередь услуг" count={visible.length}>
            {visible.map(item => <CardServiceRow key={item.key} title={serviceTitle(item)}
              status={serviceProposalStatus(item)} selected={selectedKey === item.key}
              dimmed={Boolean(selected && selectedKey !== item.key)}
              controls={selectedKey === item.key ? detailId : undefined} onClick={event => {
                trigger.current = event.currentTarget;
                if (selectedKey === item.key) detail.current?.focus();
                else {
                  active.current = item.key;
                  setSelectedKey(item.key);
                }
              }} />)}
            {!visible.length && <p className="px-2 py-3 text-sm text-muted-foreground">Услуги не найдены.</p>}
          </CardServiceList>
        </div>
      </>}
      detail={selected && <ServiceProposalDetail key={JSON.stringify([selected.key, selected.proposed, selected.proposed_description])}
        id={detailId} focusRef={detail} item={selected} send={send} disabled={disabled} error={error} onClose={() => close(selected.key)} />}
    />
  </div>;
}

export function ServiceProposalDetail({ id, focusRef, item, send, disabled, error, onClose, backAction }: {
  id: string;
  focusRef: RefObject<HTMLElement | null>;
  item: ServiceProposal;
  send?: SaveServiceProposal;
  disabled: boolean;
  error: string;
  onClose: () => void;
  backAction?: ReactNode;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(item.proposed);
  const [description, setDescription] = useState(item.proposed_description);
  const [saveFailed, setSaveFailed] = useState(false);
  const canSave = Boolean(send && !item.accepted);
  const saveLabel = item.service_id ? 'Сохранить вариант' : 'Добавить в услуги';
  const save = async (nextName: string, nextDescription: string) => {
    if (!send || disabled) return;
    setSaveFailed(false);
    if (await send({ action: 'service', key: item.key, name: nextName, description: nextDescription })) onClose();
    else setSaveFailed(true);
  };
  const changedName = item.has_original && item.original !== item.proposed;
  const changedDescription = item.has_original && item.description !== item.proposed_description;

  return <CardServiceDetail id={id} focusRef={focusRef} title={serviceTitle(item)} status={serviceProposalStatus(item)}
    description={item.has_original ? item.description : editing ? undefined : item.proposed_description}
    descriptionLabel={item.has_original ? 'Текущее описание' : 'Описание'}
    keywords={item.keywords.length ? item.keywords.map(keyword => keyword.text) : undefined}
    onClose={onClose}
    actions={!editing && (canSave || backAction) ? <>
      {canSave && <>
        <Button size="sm" disabled={disabled} onClick={() => void save(item.proposed, item.proposed_description)}>{saveLabel}</Button>
        <Button size="sm" variant="outline" disabled={disabled} onClick={() => setEditing(true)}>Изменить</Button>
        {item.has_original && <Button size="sm" variant="ghost" disabled={disabled}
          onClick={() => void save(item.original, item.description)}>Оставить исходную</Button>}
      </>}
      {backAction}
    </> : undefined}
  >
    {editing ? <CardServiceDraft title="Редактирование предложения">
      <form className="mt-2 space-y-3" onSubmit={event => {
        event.preventDefault();
        void save(name, description);
      }}>
        <label className="block space-y-1 text-sm">Название<Input value={name} maxLength={240} onChange={event => setName(event.target.value)} required /></label>
        <label className="block space-y-1 text-sm">Описание<textarea className="block min-h-24 w-full rounded-xl border bg-background px-3 py-2" value={description} maxLength={1200} onChange={event => setDescription(event.target.value)} /></label>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" type="submit" disabled={!canSave || disabled || !name.trim()}>{saveLabel}</Button>
          <Button size="sm" type="button" variant="ghost" onClick={() => {
            setName(item.proposed);
            setDescription(item.proposed_description);
            setEditing(false);
          }}>Отменить правки</Button>
        </div>
      </form>
    </CardServiceDraft> : <>
      {changedName && <CardServiceDraft title="Предложенное название">
        <p className="mt-2 break-words text-sm text-slate-900">{item.proposed}</p>
      </CardServiceDraft>}
      {changedDescription && <CardServiceDraft title="Предложенное описание">
        <p className="mt-2 whitespace-pre-line break-words text-sm leading-6 text-slate-700">{item.proposed_description || 'Без описания'}</p>
      </CardServiceDraft>}
    </>}
    {item.source_url && <a className="block w-fit text-sm underline" href={item.source_url} rel="noreferrer" target="_blank">Источник услуги</a>}
    {saveFailed && <p role="alert" className="text-sm text-destructive">{error || 'Не удалось сохранить услугу. Попробуйте ещё раз.'}</p>}
  </CardServiceDetail>;
}
