import { AccessPreview, type BlockAccess } from '@/components/access/AccessBoundary';
import { Button } from '@/components/ui/button';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { growthPathsCopyFor } from '@/i18n/growthPathsCopy';
import { newAuth } from '@/lib/auth_new';
import { journeyActionRoute, type JourneyAction } from '@/lib/leadJourney';
import { workCoherenceCopy } from '@/i18n/workCoherenceCopy';
import { workStatusLabel } from '@/lib/workStatus';
import { workNavigationCopy } from '@/lib/workNavigation';
import type { TodayPreference } from './todayWorkModel';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useOutletContext, useSearchParams } from 'react-router-dom';

type Flow = 'maps' | 'content' | 'influencer' | 'partnership' | 'automation' | 'average_ticket';
type Path = { flow_type: Flow; status: string; access: BlockAccess; action?: JourneyAction | null; obstacle?: string;
 locations?: Array<{ business_id: string; business_name?: string; access: BlockAccess; action?: JourneyAction | null }> };
type Data = { paths?: Path[]; focus_action?: JourneyAction | null };
type Scope = { kind: 'business' | 'network' | 'platform'; id: string };
const route: Record<Flow, string> = { maps: '/dashboard/card', content: '/dashboard/content', influencer: '/dashboard/influencers', partnership: '/dashboard/partnerships', automation: '/dashboard/agents', average_ticket: '/dashboard/average-ticket' };
const preferenceFlow: Record<Flow, TodayPreference['primary_flow']> = { maps: 'maps', content: 'content', influencer: 'influencers', partnership: 'partnerships', automation: 'automation', average_ticket: 'upsells' };

export const GrowthPathsPage = () => {
 const { currentBusinessId, controlScope, onControlScopeChange } = useOutletContext<{ currentBusinessId?: string | null; controlScope?: Scope; onControlScopeChange?: (scope: Scope) => void }>();
 const [params] = useSearchParams();
 const clientDirections = params.get('group') === 'clients';
 const scope = controlScope?.kind === 'network' ? controlScope : { kind: 'business', id: currentBusinessId || '' };
 return <GrowthPathsWorkspace key={scope.kind + ':' + scope.id} scope={scope} selectScope={onControlScopeChange} clientDirections={clientDirections} />;
};
const GrowthPathsWorkspace = ({ scope, selectScope, clientDirections }: { clientDirections?: boolean; scope: { kind: string; id: string }; selectScope?: (scope: Scope) => void }) => {
 const { businesses = [] } = useOutletContext<{ businesses?: Array<{ id: string; address?: string | null }> }>();
 const { language } = useLanguage(); const copy = growthPathsCopyFor(language); const navigation = workNavigationCopy(language); const extra = workCoherenceCopy(language); const navigate = useNavigate();
 const [data, setData] = useState<Data | null>(null); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
 const [preference, setPreference] = useState<TodayPreference | null>(null); const [pending, setPending] = useState<Flow | null>(null); const [saving, setSaving] = useState(false);
 const sequence = useRef(0); const active = useRef(true);
 const scopeQuery = new URLSearchParams({ scope_type: scope.kind, scope_id: scope.id }).toString();
 const load = useCallback(async () => {
  if (!scope.id) { setLoading(false); return; } const generation = ++sequence.current;
  setLoading(true); setError('');
  try { const response = await newAuth.makeRequest('/growth-paths?' + (scope.kind === 'network' ? new URLSearchParams({ scope_type: 'network', scope_id: scope.id }) : new URLSearchParams({ business_id: scope.id })));
   if (active.current && generation === sequence.current) setData(response);
  } catch (failure) { if (active.current && generation === sequence.current) { if (typeof failure === 'object' && failure && 'status' in failure && [401,403,404].includes(Number(failure.status))) setData(null); setError(failure instanceof Error ? failure.message : copy.loadError); } }
  finally { if (active.current && generation === sequence.current) setLoading(false); }
 }, [scope.id, scope.kind, copy.loadError]);
 useEffect(() => { active.current = true; void load(); return () => { active.current = false; sequence.current++; }; }, [load]);
 useEffect(() => { let current = true; void newAuth.makeRequest('/operator/today/preference?' + scopeQuery).then(response => { if (current) setPreference(response.preference || null); }).catch(() => { if(current) setPreference(null); }); return () => { current = false; }; }, [scopeQuery]);
 const choose = async () => { if (!preference || !pending) return; setSaving(true); try { const response = await newAuth.makeRequest('/operator/today/preference?' + scopeQuery, { method: 'POST', body: JSON.stringify({ action: 'set', expected_revision: preference.revision, primary_flow: preferenceFlow[pending] }) }); if (active.current) { setPreference(response.preference); setPending(null); } } catch (failure) { if (active.current) setError(failure instanceof Error ? failure.message : copy.loadError); } finally { if (active.current) setSaving(false); } };
 const open = (path: Path, businessId = scope.id, action = path.action) => { if (scope.kind === 'network') { if(!selectScope) return; selectScope({ kind: 'business', id: businessId }); } const target = action ? journeyActionRoute(action) : route[path.flow_type]; const url = new URL(target, 'https://localos.pro'); url.searchParams.set('business_id', businessId); navigate(url.pathname + url.search); };
 if (!scope.id) return <p>{copy.chooseBusiness}</p>;
 const paths = (data?.paths || []).filter(path => path && Object.prototype.hasOwnProperty.call(route, path.flow_type) && (!clientDirections || ['maps','content','partnership','influencer'].includes(path.flow_type))).sort((left, right) => Number(right.flow_type === data?.focus_action?.flow_type) - Number(left.flow_type === data?.focus_action?.flow_type));
 return <div className="space-y-6 pb-10"><header><p className="text-sm text-muted-foreground">{copy.eyebrow}</p><h1 className="text-3xl font-semibold">{copy.title}</h1><p className="mt-2 max-w-2xl text-sm text-muted-foreground">{extra.focusIntro}</p></header>
 {error ? <div role="alert" className="rounded-xl border border-amber-200 p-4"><p>{error}</p><Button variant="outline" onClick={() => void load()}>{copy.retry}</Button></div> : null}
 {pending ? <section aria-label={navigation.focus} className="rounded-xl border bg-card p-4"><p>{navigation.focus}: {copy.directions[pending].title}</p><p className="my-2 text-sm text-muted-foreground">{extra.focusHint}</p><Button disabled={saving} onClick={() => void choose()}>{navigation.focus}</Button><Button variant="ghost" disabled={saving} onClick={() => setPending(null)}>{extra.cancel}</Button></section> : null}
 {loading && !data ? <p role="status">{copy.loading}</p> : paths.length ? <div className="divide-y rounded-xl border bg-card">{paths.map(path => <section key={path.flow_type} className="p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div className="max-w-2xl"><h2 className="text-xl font-semibold">{copy.directions[path.flow_type].title}</h2><p className="mt-1 text-sm text-muted-foreground">{workStatusLabel(path.status, language)}</p><p className="mt-2 text-sm text-muted-foreground">{copy.directions[path.flow_type].description}</p>{path.obstacle && language === 'ru' ? <p className="mt-2 text-sm">{copy.obstacle} {path.obstacle}</p> : null}</div>
 {preference && preference.available_flows?.includes(preferenceFlow[path.flow_type]) ? <Button variant="outline" disabled={saving || preference.primary_flow === preferenceFlow[path.flow_type]} onClick={() => setPending(path.flow_type)}>{preference.primary_flow === preferenceFlow[path.flow_type] ? extra.currentFocus : navigation.focus}</Button> : null}</div>
 {scope.kind === 'network' ? <details className="mt-4"><summary className="min-h-11 cursor-pointer py-2 font-medium">{extra.locations} · {path.locations?.length || 0}</summary><div className="divide-y">{path.locations?.map(location => {
   const address = businesses.find(business => business.id === location.business_id)?.address;
   const name = location.business_name || location.business_id;
   return <div key={location.business_id} className="flex flex-wrap items-center justify-between gap-3 py-3"><span className="min-w-0"><span className="block">{name}</span>{address ? <span className="block break-words text-sm text-muted-foreground">{address}</span> : null}</span>{location.access.status === 'available' ? <Button variant="outline" aria-label={address ? `${copy.directions[path.flow_type].cta}: ${name}, ${address}` : undefined} disabled={!selectScope} onClick={() => open(path, location.business_id, location.action)}>{copy.directions[path.flow_type].cta}</Button> : <AccessPreview access={location.access} businessId={location.business_id} />}</div>;
  })}</div></details> : path.access.status === 'available' ? <Button variant="outline" className="mt-4" asChild><Link to={(() => { const target = new URL(path.action ? journeyActionRoute(path.action) : route[path.flow_type], 'https://localos.pro'); target.searchParams.set('business_id', scope.id); return target.pathname + target.search; })()}>{path.action?.cta_label || copy.directions[path.flow_type].cta}</Link></Button> : <AccessPreview access={path.access} className="mt-4" />}</section>)}</div> : !error && !loading ? <section><h2 className="text-xl font-semibold">{copy.emptyTitle}</h2><p className="mt-2 text-sm text-muted-foreground">{copy.emptyDescription}</p></section> : null}
 </div>;
};
