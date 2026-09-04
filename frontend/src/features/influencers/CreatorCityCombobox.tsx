import { Check, ChevronDown, MapPin, Search } from 'lucide-react';
import { useEffect, useId, useMemo, useState } from 'react';

import { cn } from '@/lib/utils';

type CreatorCityComboboxProps = {
  label?: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
  className?: string;
};

const aliases: Record<string, string[]> = {
  'Санкт-Петербург': ['спб', 'питер', 'питере', 'петербург', 'петербурге', 'санкт петербург', 'saint petersburg', 'st petersburg'],
  'Москва': ['москва', 'москве', 'мск', 'moscow'],
  'Таллинн': ['таллин', 'таллинн', 'tallinn'],
  'Нижний Новгород': ['нижний новгород', 'нижнем новгороде', 'nizhny novgorod'],
  'Великий Новгород': ['великий новгород', 'новгород', 'veliky novgorod'],
  'Екатеринбург': ['екб', 'екатеринбург', 'yekaterinburg', 'ekaterinburg'],
  'Новосибирск': ['нск', 'новосибирск', 'novosibirsk'],
  'Казань': ['казань', 'kazan'],
  'Краснодар': ['краснодар', 'krd', 'krasnodar'],
  'Ростов-на-Дону': ['ростов на дону', 'ростове на дону', 'rostov on don'],
  'Сочи': ['сочи', 'sochi'],
  'Батуми': ['батуми', 'batumi'],
};

const normalize = (value: string) => value.toLowerCase().replace(/ё/g, 'е').replace(/[^0-9a-zа-я]+/g, ' ').trim();

const editDistance = (left: string, right: string) => {
  const previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let leftIndex = 1; leftIndex <= left.length; leftIndex += 1) {
    const current = [leftIndex];
    for (let rightIndex = 1; rightIndex <= right.length; rightIndex += 1) {
      current[rightIndex] = Math.min(
        current[rightIndex - 1] + 1,
        previous[rightIndex] + 1,
        previous[rightIndex - 1] + (left[leftIndex - 1] === right[rightIndex - 1] ? 0 : 1),
      );
    }
    previous.splice(0, previous.length, ...current);
  }
  return previous[right.length];
};

const matches = (city: string, query: string) => {
  const needle = normalize(query);
  if (!needle) return true;
  const candidates = [normalize(city), ...(aliases[city] || []).map(normalize)];
  return candidates.some((candidate) => candidate.includes(needle) || needle.includes(candidate)
    || editDistance(candidate, needle) <= Math.max(1, Math.floor(Math.max(candidate.length, needle.length) * 0.2)));
};

export const CreatorCityCombobox = ({ label = 'Город', value, options, onChange, className }: CreatorCityComboboxProps) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(value);
  const [activeIndex, setActiveIndex] = useState(0);
  const listboxId = useId();
  const filtered = useMemo(() => options.filter((city) => matches(city, query)).slice(0, 40), [options, query]);
  useEffect(() => setQuery(value), [value]);
  useEffect(() => setActiveIndex(0), [query]);
  const select = (city: string) => { setQuery(city); onChange(city); setOpen(false); };
  const settle = () => {
    if (!query.trim()) { onChange(''); return; }
    const exact = options.find((city) => normalize(city) === normalize(query));
    if (exact) select(exact);
    else if (filtered.length === 1) select(filtered[0]);
    else setQuery(value);
  };

  return <label className={cn('relative block text-xs font-semibold text-slate-600', className)}>{label}
    <span className="relative mt-2 block"><MapPin className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-slate-400" /><input role="combobox" aria-expanded={open} aria-controls={listboxId} aria-autocomplete="list" aria-activedescendant={open && filtered[activeIndex] ? `${listboxId}-${activeIndex}` : undefined} value={query} onFocus={() => setOpen(true)} onBlur={() => { window.setTimeout(() => { settle(); setOpen(false); }, 100); }} onChange={(event) => { setQuery(event.target.value); setOpen(true); }} onKeyDown={(event) => { if (event.key === 'ArrowDown') { event.preventDefault(); setOpen(true); setActiveIndex((current) => Math.min(current + 1, Math.max(filtered.length - 1, 0))); } if (event.key === 'ArrowUp') { event.preventDefault(); setActiveIndex((current) => Math.max(current - 1, 0)); } if (event.key === 'Enter' && filtered[activeIndex]) { event.preventDefault(); select(filtered[activeIndex]); } if (event.key === 'Escape') { setQuery(value); setOpen(false); } }} placeholder="Начните вводить город" className="min-h-11 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-10 text-sm font-normal text-slate-900 outline-none transition-[border-color,box-shadow] focus:border-slate-400 focus:shadow-[0_0_0_3px_rgba(148,163,184,0.15)]" /><ChevronDown className={cn('pointer-events-none absolute right-3 top-3.5 h-4 w-4 text-slate-400 transition-transform', open && 'rotate-180')} /></span>
    {open ? <span id={listboxId} role="listbox" className="absolute z-40 mt-2 block max-h-72 w-full overflow-y-auto rounded-2xl bg-white p-1.5 font-normal shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_18px_48px_-20px_rgba(15,23,42,0.35)]">{filtered.length ? filtered.map((city, index) => <button id={`${listboxId}-${index}`} key={city} type="button" role="option" aria-selected={normalize(city) === normalize(value)} onMouseEnter={() => setActiveIndex(index)} onMouseDown={(event) => event.preventDefault()} onClick={() => select(city)} className={cn('flex min-h-10 w-full items-center gap-2 rounded-xl px-3 text-left text-sm text-slate-700 transition-[background-color,transform] hover:bg-slate-50 active:scale-[0.96]', index === activeIndex && 'bg-slate-50')}><Check className={cn('h-4 w-4 text-emerald-700', normalize(city) !== normalize(value) && 'opacity-0')} />{city}</button>) : <span className="flex min-h-20 items-center justify-center gap-2 px-3 text-sm text-slate-500"><Search className="h-4 w-4" />Город не найден</span>}</span> : null}
  </label>;
};
