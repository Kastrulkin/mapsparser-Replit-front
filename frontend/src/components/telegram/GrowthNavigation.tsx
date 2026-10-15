import { ChevronRight } from 'lucide-react';
import { workCoherenceCopy } from '@/i18n/workCoherenceCopy';
import type { Language } from '@/i18n/LanguageContext.logic';
export type GrowthNavigationEntry = { key: string; label: string; status: 'available' | 'read_only' | 'hidden'; reason?: string; preview_available?: boolean };
type Props = { navigation: GrowthNavigationEntry[]; onOpen: (key: string) => void; onOpenProgress: () => void; onLocked: (item: GrowthNavigationEntry) => void; onRestartTour: () => void; language?: Language; scope?: { kind?: string; id?: string } | null };
export default function GrowthNavigation({ navigation, onOpen, onLocked, onRestartTour, language = 'ru', scope }: Props) {
 const copy = workCoherenceCopy(language);
 const keys = ['work_journal','chats','community_sources','web_analytics'];
 const params = new URLSearchParams(); if(scope?.id) {params.set('business_id',scope.id);params.set('scope_type',scope.kind || 'business');}
 const items = keys.flatMap((key, index) => { const item = navigation.find(entry => entry.key === key && entry.status !== 'hidden'); return item ? [{ ...item, label: copy.utilities[index+1] }] : []; });
 const style = 'flex min-h-14 w-full items-center justify-between gap-3 rounded-xl bg-white/[0.04] p-4 text-left focus-visible:ring-2 focus-visible:ring-white';
 return <div><h2 className="text-xl font-semibold">{copy.moreIntro}</h2><div className="mt-4 space-y-2"><a className={style} href={'/dashboard/growth-paths' + (params.size ? '?' + params : '')}><span>{copy.utilities[0]}<small className="mt-1 block text-zinc-400">{copy.openWeb}</small></span><ChevronRight className="h-4 w-4 shrink-0" /></a>{items.map(item => <button key={item.key} type="button" onClick={() => { if (item.status === 'read_only' && !item.preview_available) onLocked(item); else onOpen(item.key); }} className={style}><span>{item.label}{item.reason ? <small className="mt-1 block text-zinc-400">{item.reason}</small> : null}</span><ChevronRight className="h-4 w-4 shrink-0" /></button>)}</div><button className="mt-5 min-h-11 text-sm" onClick={onRestartTour}>{copy.howTo}</button></div>;
}
