import { useEffect, useId, useState, type FormEvent } from 'react';
import { newAuth } from '@/lib/auth_new';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export type FieldSpec = { key: string; label: string; max_length: number; required: boolean };
export type BusinessManagementSchema = {
  fields: FieldSpec[]; roles: { key: string; label: string; permissions: string[] }[];
  businesses: { id: string; name: string; network_id: string | null }[];
  can_manage_team: boolean; can_edit: boolean; can_manage_network?: boolean;
  profile: { values: Record<string, string> };
};
type Result = { status: string; chat_response?: string; approval?: { action_id: string } };

export function BusinessChangeForm({ businessId, kind, schema, isRu, onSaved, fields, member }: {
  businessId: string; kind: 'team' | 'settings'; schema: BusinessManagementSchema; isRu: boolean;
  onSaved: (message: string) => void; fields?: FieldSpec[];
  member?: {name:string;email:string;role:string;scope:string};
}) {
  const id = useId();
  const [name, setName] = useState(member?.name || '');
  const [email, setEmail] = useState(member?.email || '');
  const [role, setRole] = useState(member?.role || '');
  const [scope, setScope] = useState(member?.scope === 'network' && schema.can_manage_network ? 'network' : 'business');
  const [selected, setSelected] = useState<string[]>([businessId]);
  const [sendInvitation, setSendInvitation] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { setPreview(null); setError(''); }, [name,email,role,scope,selected,sendInvitation,values]);
  const prepare = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setPreview(null);
    try {
      const patch = Object.fromEntries(Object.entries(values).filter(([key, value]) => schema.profile.values[key] !== value));
      const argumentsValue = kind === 'team'
        ? { name,email,role,scope,businesses:selected,send_invitation:sendInvitation }
        : { changes: [{ business:businessId,patch }] };
      const response: { operator_result: Result } = await newAuth.makeRequest('/operator/business-management', {
        method: 'POST', body: JSON.stringify({ business_id:businessId,kind,arguments:argumentsValue,request_id:crypto.randomUUID() }),
      });
      if (response.operator_result.status !== 'approval_required') throw new Error(response.operator_result.chat_response || 'Не удалось подготовить изменение');
      setPreview(response.operator_result);
    } catch (reason) { setError(reason instanceof Error ? reason.message : (isRu ? 'Не удалось подготовить изменение' : 'Unable to prepare changes')); }
    finally { setBusy(false); }
  };
  const confirm = async () => {
    if (!preview?.approval?.action_id) return;
    setBusy(true); setError('');
    try {
      const response: { operator_result: Result } = await newAuth.makeRequest(`/operator/actions/${encodeURIComponent(preview.approval.action_id)}/confirm`, {
        method: 'POST', body: JSON.stringify({ business_id:businessId }),
      });
      if (response.operator_result.status !== 'completed') throw new Error(response.operator_result.chat_response || 'Изменение не сохранено');
      setPreview(null); onSaved(response.operator_result.chat_response || (isRu ? 'Изменения сохранены.' : 'Changes saved.'));
    } catch (reason) { setPreview(null); setError(reason instanceof Error ? reason.message : (isRu ? 'Изменение не сохранено' : 'Changes were not saved')); }
    finally { setBusy(false); }
  };
  return <form onSubmit={event => void prepare(event)} className="space-y-4">
    <fieldset disabled={busy} className="space-y-4">
      {kind === 'team' ? <>
        <label htmlFor={`${id}-name`} className="block text-sm">{isRu ? 'Имя сотрудника' : 'Staff name'}<Input id={`${id}-name`} value={name} readOnly={Boolean(member)} maxLength={200} onChange={event => setName(event.target.value)} /></label>
        <label htmlFor={`${id}-email`} className="block text-sm">Email<Input id={`${id}-email`} type="email" required value={email} readOnly={Boolean(member)} maxLength={254} onChange={event => setEmail(event.target.value)} /></label>
        <label htmlFor={`${id}-role`} className="block text-sm">{isRu ? 'Роль' : 'Role'}
          <select id={`${id}-role`} aria-label={isRu ? 'Роль' : 'Role'} required value={role} onChange={event => setRole(event.target.value)} className="flex h-11 w-full rounded-md border border-input bg-background px-3 text-sm">
            <option value="">{isRu ? 'Выберите роль' : 'Select role'}</option>
            {schema.roles.map(option => <option key={option.key} value={option.key}>{isRu ? option.label : option.key}</option>)}
          </select>
        </label>
        {role && <p className="text-sm text-muted-foreground">{schema.roles.find(option => option.key === role)?.permissions.join(', ')}</p>}
        <label htmlFor={`${id}-scope`} className="block text-sm">{isRu ? 'Область доступа' : 'Access scope'}
          <select id={`${id}-scope`} aria-label={isRu ? 'Область доступа' : 'Access scope'} value={scope} onChange={event => setScope(event.target.value)} className="flex h-11 w-full rounded-md border border-input bg-background px-3 text-sm">
            <option value="business">{isRu ? 'Выбранные бизнесы' : 'Selected businesses'}</option>
            {schema.can_manage_network && <option value="network">{isRu ? 'Вся сеть текущего бизнеса' : 'The current business network'}</option>}
          </select>
        </label>
        {scope === 'business' && <fieldset className="space-y-2"><legend className="mb-2 text-sm">{isRu ? 'Бизнесы' : 'Businesses'}</legend>
          {schema.businesses.map(business => <label key={business.id} className="flex min-h-10 items-center gap-2 text-sm">
            <input type="checkbox" checked={selected.includes(business.id)} onChange={event => setSelected(current => event.target.checked ? [...current,business.id] : current.filter(value => value !== business.id))} />{business.name}
          </label>)}
        </fieldset>}
        <label className="flex min-h-10 items-center gap-2 text-sm"><input type="checkbox" checked={sendInvitation} onChange={event => setSendInvitation(event.target.checked)} />{isRu ? 'Отправить приглашение по email после подтверждения' : 'Send an email invitation after confirmation'}</label>
      </> : fields?.map(field => <label key={field.key} htmlFor={`${id}-${field.key}`} className="block text-sm">
        {field.label}<Input id={`${id}-${field.key}`} value={values[field.key] ?? schema.profile.values[field.key] ?? ''} maxLength={field.max_length} required={field.required}
          type={field.key === 'contact_email' ? 'email' : 'text'} onChange={event => setValues(current => ({ ...current,[field.key]:event.target.value }))} />
      </label>)}
      <Button type="submit" disabled={kind === 'team' && scope === 'business' && selected.length === 0}>{busy ? (isRu ? 'Подготавливаем…' : 'Preparing…') : (isRu ? 'Проверить изменения' : 'Review changes')}</Button>
    </fieldset>
    {preview && <div className="space-y-3 border-t border-border pt-4">
      <p role="status" className="whitespace-pre-wrap break-words text-sm">{preview.chat_response}</p>
      <div className="flex flex-wrap gap-2"><Button type="button" disabled={busy} onClick={() => void confirm()}>{busy ? (isRu ? 'Сохраняем…' : 'Saving…') : (isRu ? 'Подтвердить' : 'Confirm')}</Button>
        <Button type="button" variant="outline" disabled={busy} onClick={() => setPreview(null)}>{isRu ? 'Отмена' : 'Cancel'}</Button></div>
    </div>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
  </form>;
}
