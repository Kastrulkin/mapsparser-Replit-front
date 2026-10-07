import { ArrowUpRight, Bookmark, Check, MapPin, Users } from 'lucide-react';

import { cn } from '@/lib/utils';
import { influencerAudienceLabel, influencerPlatformLabel, type InfluencerCreator } from './influencerWorkspace';

type InfluencerCreatorCardProps = {
  creator: InfluencerCreator;
  dark?: boolean;
  busy?: boolean;
  onToggleShortlist: (creator: InfluencerCreator) => void;
  onExclude?: (creator: InfluencerCreator) => void;
};

export const InfluencerCreatorCard = ({ creator, dark = false, busy = false, onToggleShortlist, onExclude }: InfluencerCreatorCardProps) => {
  const shortlisted = creator.disposition === 'shortlisted' || creator.shortlist_status === 'shortlisted';
  const excluded = creator.disposition === 'excluded' || creator.shortlist_status === 'rejected';
  const topics = [creator.primary_topic, ...(creator.topics || []), ...(creator.content_styles || [])]
    .filter((value): value is string => Boolean(value))
    .slice(0, 4);
  const evidence = (creator.evidence || []).find((item) => item.summary);
  return (
    <article className={cn('rounded-2xl p-4', dark ? 'bg-white/[0.04] ring-1 ring-inset ring-white/[0.07]' : 'border border-slate-200 bg-white shadow-sm')}>
      <div className="flex items-start gap-3">
        <span className={cn('grid h-11 w-11 shrink-0 place-items-center rounded-xl', dark ? 'bg-primary/15 text-primary' : 'bg-orange-50 text-orange-700')}><Users className="h-5 w-5" aria-hidden="true" /></span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className={cn('text-balance text-base font-semibold', dark ? 'text-zinc-100' : 'text-slate-950')}>{creator.display_name}</h3><p className={cn('mt-1 text-xs', dark ? 'text-zinc-500' : 'text-slate-500')}>{influencerPlatformLabel(creator.platform)}</p></div>{creator.accepts_barter === true ? <span className={cn('rounded-full px-2.5 py-1 text-[11px] font-semibold', dark ? 'bg-emerald-400/10 text-emerald-300' : 'bg-emerald-50 text-emerald-700')}>Бартер</span> : null}</div>
          <div className={cn('mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs', dark ? 'text-zinc-400' : 'text-slate-600')}><span className="inline-flex items-center gap-1.5"><MapPin className="h-3.5 w-3.5" />{[creator.city, creator.area].filter(Boolean).join(' · ') || 'География уточняется'}</span><span className="inline-flex items-center gap-1.5"><Users className="h-3.5 w-3.5" />{influencerAudienceLabel(creator)}</span></div>
        </div>
      </div>
      {creator.description ? <p className={cn('mt-4 line-clamp-3 text-pretty text-sm leading-6', dark ? 'text-zinc-400' : 'text-slate-600')}>{creator.description}</p> : null}
      {topics.length ? <div className="mt-3 flex flex-wrap gap-2">{topics.map((topic) => <span key={topic} className={cn('rounded-full px-2.5 py-1 text-[11px]', dark ? 'bg-white/[0.05] text-zinc-400' : 'bg-slate-100 text-slate-600')}>{topic}</span>)}</div> : null}
      {(creator.fit_reasons || []).length ? <div className={cn('mt-4 rounded-xl p-3 text-xs leading-5', dark ? 'bg-black/20 text-zinc-400' : 'bg-orange-50 text-orange-950')}><strong className="font-semibold">Почему подходит:</strong> {creator.fit_reasons?.[0]}</div> : null}
      {evidence ? <p className={cn('mt-3 text-xs leading-5', dark ? 'text-zinc-500' : 'text-slate-500')}><strong className={cn('font-semibold', dark ? 'text-zinc-300' : 'text-slate-700')}>Что уже публиковал:</strong> {evidence.summary}</p> : null}
      <div className="mt-4 grid grid-cols-2 gap-2">
        {creator.public_url ? <a href={creator.public_url} target="_blank" rel="noreferrer" className={cn('inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-3 text-xs font-semibold transition-transform active:scale-[0.96]', dark ? 'bg-white/[0.05] text-zinc-300 ring-1 ring-inset ring-white/[0.07]' : 'border border-slate-200 text-slate-700')}><ArrowUpRight className="h-4 w-4" />Площадка</a> : <span />}
        <button type="button" disabled={busy} onClick={() => onToggleShortlist(creator)} className={cn('inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-3 text-xs font-semibold transition-[background-color,color,transform] active:scale-[0.96] disabled:opacity-50', shortlisted ? (dark ? 'bg-emerald-400/15 text-emerald-300' : 'bg-emerald-700 text-white hover:bg-emerald-800') : (dark ? 'bg-primary text-white' : 'bg-slate-950 text-white'))}>{shortlisted ? <Check className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}{excluded ? 'Вернуть' : 'Подходит'}</button>
      </div>
      {onExclude && !excluded ? <button type="button" disabled={busy} onClick={() => onExclude(creator)} className="mt-2 min-h-10 w-full rounded-xl px-3 text-xs font-semibold text-slate-500 transition-[background-color,color,transform] hover:bg-rose-50 hover:text-rose-700 active:scale-[0.96] disabled:opacity-50">Не подходит</button> : null}
    </article>
  );
};
