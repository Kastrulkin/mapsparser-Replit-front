import { useEffect, useState } from 'react';
import { DashboardSection } from './DashboardPrimitives';
import { newAuth } from '@/lib/auth_new';
import { Button } from '@/components/ui/button';
import { BusinessChangeForm, type BusinessManagementSchema } from './BusinessChangeForm';

// Existing profile controls cover these fields. Any new registry field appears here.
const PROFILE_FIELDS = new Set(['name','business_type','address','city','website','working_hours','currency','timezone']);
export function BusinessAdditionalSettings({businessId,isRu}: {businessId:string | null;isRu:boolean}) {
  const [saved,setSaved] = useState<{businessId:string;data:BusinessManagementSchema} | null>(null);
  const [reload,setReload] = useState(0);
  const [failed,setFailed] = useState<string | null>(null);
  useEffect(() => {
    setSaved(null); setFailed(null); if (!businessId) return;
    let active = true;
    newAuth.makeRequest(`/operator/business-management?business_id=${encodeURIComponent(businessId)}`)
      .then((data:BusinessManagementSchema) => { if(active)setSaved({businessId,data}); }).catch(() => { if(active)setFailed(businessId); });
    return () => { active=false; };
  },[businessId,reload]);
  if (!businessId) return null;
  if (failed === businessId) return <DashboardSection title={isRu ? 'Дополнительные настройки бизнеса' : 'Additional business settings'}><p role="alert" className="mb-3 text-sm">{isRu ? 'Не удалось загрузить настройки.' : 'Unable to load settings.'}</p><Button variant="outline" onClick={()=>setReload(value=>value+1)}>{isRu ? 'Повторить загрузку' : 'Retry'}</Button></DashboardSection>;
  if (saved?.businessId !== businessId) return null;
  const fields = saved.data.fields.filter(field => !PROFILE_FIELDS.has(field.key));
  if (!fields.length) return null;
  return <DashboardSection title={isRu ? 'Контакты и дополнительные настройки бизнеса' : 'Business contacts and additional settings'} description={isRu ? 'Контакты бизнеса используются отдельно от личного профиля владельца.' : 'Business contacts are separate from the owner’s personal profile.'}>
    {saved.data.can_edit ? <BusinessChangeForm key={`${businessId}:${reload}`} businessId={businessId} kind="settings" schema={saved.data} fields={fields} isRu={isRu} onSaved={() => setReload(value=>value+1)} />
      : <dl className="space-y-2">{fields.map(field=><div key={field.key}><dt className="text-sm text-muted-foreground">{field.label}</dt><dd className="break-words">{saved.data.profile.values[field.key] || '—'}</dd></div>)}</dl>}
  </DashboardSection>;
}
