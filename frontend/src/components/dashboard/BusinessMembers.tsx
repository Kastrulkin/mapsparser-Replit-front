import { useEffect, useState } from 'react';
import { DashboardSection } from './DashboardPrimitives';
import { Button } from '@/components/ui/button';
import { browserBearerToken } from '@/lib/browserSessionFetch';
import { newAuth } from '@/lib/auth_new';
import { BusinessChangeForm, type BusinessManagementSchema } from './BusinessChangeForm';

type Member = {
  id: string; name: string; email: string; is_active: boolean;
  access: { role: string; scope: string }[];
};
type Directory = { businessId: string; members: Member[]; error: boolean };

export function BusinessMembers({ businessId, isRu }: { businessId: string | null; isRu: boolean }) {
  const [directory, setDirectory] = useState<Directory | null>(null);
  const [reload, setReload] = useState(0);
  const [schema, setSchema] = useState<{ businessId: string; data: BusinessManagementSchema } | null>(null);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Member | null>(null);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{businessId:string;message:string} | null>(null);
  useEffect(() => {
    setAdding(false); setEditing(null); setSchema(null); setSchemaError(null);
    if (!businessId) return;
    let active = true;
    newAuth.makeRequest(`/operator/business-management?business_id=${encodeURIComponent(businessId)}`)
      .then((data: BusinessManagementSchema) => { if (active) setSchema({businessId,data}); })
      .catch(() => { if(active)setSchemaError(businessId); });
    return () => { active = false; };
  }, [businessId,reload]);
  useEffect(() => {
    if (!businessId) return;
    const controller = new AbortController();
    setDirectory(null);
    const token = browserBearerToken();
    fetch(`/api/operator/business-members?business_id=${encodeURIComponent(businessId)}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}, signal: controller.signal,
    }).then(async response => {
      if (!response.ok) throw new Error('directory_unavailable');
      const data: { members: Member[] } = await response.json();
      if (!controller.signal.aborted) setDirectory({ businessId, members: data.members, error: false });
    }).catch(() => {
      if (!controller.signal.aborted) setDirectory({ businessId, members: [], error: true });
    });
    return () => controller.abort();
  }, [businessId, reload]);
  const current = directory?.businessId === businessId ? directory : null;
  const roleLabel = (role: string) => {
    switch (role) {
      case 'owner': return isRu ? 'Владелец' : 'Owner';
      case 'manager': return isRu ? 'Управляющий' : 'Manager';
      case 'admin': return isRu ? 'Администратор' : 'Administrator';
      case 'master': return isRu ? 'Мастер' : 'Practitioner';
      case 'member': return isRu ? 'Сотрудник' : 'Staff';
      case 'viewer': return isRu ? 'Наблюдатель' : 'Viewer';
      default: return isRu ? 'Участник' : 'Member';
    }
  };
  return <DashboardSection title={isRu ? 'Пользователи бизнеса' : 'Business users'}
    description={isRu ? 'Владелец и сотрудники выбранного бизнеса, включая доступ через сеть.' : 'The owner and staff of the selected business, including network access.'}>
    {businessId && schema?.businessId === businessId && schema.data.can_manage_team && <div className="mb-4">
      <Button type="button" variant={adding ? 'outline' : 'default'} aria-expanded={adding} onClick={() => {setEditing(null);setAdding(value => !value);}}>{adding ? (isRu ? 'Закрыть форму' : 'Close form') : (isRu ? 'Добавить сотрудника' : 'Add staff member')}</Button>
      {adding && <div className="mt-4"><BusinessChangeForm key={`${businessId}:${editing?.id || 'new'}`} businessId={businessId} kind="team" schema={schema.data} isRu={isRu}
        member={editing ? {name:editing.name,email:editing.email,role:(editing.access.find(grant=>grant.scope==='business') || editing.access[0])?.role || '',scope:(editing.access.find(grant=>grant.scope==='business') || editing.access[0])?.scope || 'business'} : undefined}
        onSaved={message => { setNotice({businessId,message}); setAdding(false); setEditing(null); setReload(value => value + 1); }} /></div>}
    </div>}
    {notice?.businessId === businessId && <p role="status" className="mb-4 text-sm">{notice.message}</p>}
    {schemaError === businessId && <div className="mb-4 space-y-2"><p className="text-sm text-muted-foreground">{isRu ? 'Управление сотрудниками временно недоступно.' : 'Staff management is temporarily unavailable.'}</p><Button type="button" variant="outline" onClick={() => setReload(value=>value+1)}>{isRu ? 'Повторить проверку доступа' : 'Retry access check'}</Button></div>}
    {!businessId ? <p className="text-sm text-muted-foreground">{isRu ? 'Выберите бизнес, чтобы увидеть его пользователей.' : 'Select a business to see its users.'}</p>
      : !current ? <p role="status">{isRu ? 'Загружаем пользователей…' : 'Loading users…'}</p>
      : current.error ? <div className="space-y-3">
        <p role="alert">{isRu ? 'Не удалось загрузить пользователей. Проверьте доступ к бизнесу и повторите попытку.' : 'Unable to load users. Check your business access and try again.'}</p>
        <Button variant="outline" onClick={() => setReload(value => value + 1)}>{isRu ? 'Повторить загрузку' : 'Retry'}</Button>
      </div>
      : current.members.length === 0 ? <p>{isRu ? 'Пользователи не найдены.' : 'No users found.'}</p>
      : <ul className="divide-y divide-border">
        {current.members.map(member => <li key={member.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="break-words font-medium">{member.name || member.email || (isRu ? 'Без имени' : 'Unnamed user')}</p>
            {member.email && <p className="break-all text-sm text-muted-foreground">{member.email}</p>}
            <p className="text-sm text-muted-foreground">{member.is_active ? (isRu ? 'Аккаунт активен' : 'Account active') : (isRu ? 'Аккаунт отключён' : 'Account disabled')}</p>
          </div>
          <div className="space-y-2 sm:text-right"><ul className="space-y-1 text-sm">
            {member.access.map(grant => <li key={`${grant.scope}:${grant.role}`}>
              {roleLabel(grant.role)} · {grant.scope === 'network' ? (isRu ? 'Через сеть' : 'Via network') : (isRu ? 'Этот бизнес' : 'This business')}
            </li>)}
          </ul>
          {schema?.businessId === businessId && schema.data.can_manage_team && member.email && !member.access.some(grant=>grant.role==='owner') && <Button type="button" variant="outline" aria-label={`${isRu ? 'Изменить роль' : 'Change role'}: ${member.name || member.email}`} onClick={() => {setEditing(member);setAdding(true);}}>{isRu ? 'Изменить роль' : 'Change role'}</Button>}
          </div>
        </li>)}
      </ul>}
  </DashboardSection>;
}
