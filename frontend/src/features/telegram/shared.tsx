import {
AlertCircle,
Star
} from 'lucide-react';

export const MetricMini = ({ label, value, accent = false }: { label: string; value?: string | number | null; accent?: boolean }) => <div className="min-w-0 px-1 py-1"><b className={`block truncate text-xl tabular-nums ${accent ? 'text-primary' : 'text-zinc-200'}`}>{value ?? '—'}</b><small className="block truncate text-[10px] text-zinc-600">{label}</small></div>;

export const FilterSelect = ({ label, value, setValue, options }: { label: string; value: string; setValue: (value: string) => void; options: string[][] }) => <label className="block text-[11px] text-zinc-600"><span className="mb-1 block px-1">{label}</span><select value={value} onChange={(event) => setValue(event.target.value)} className="min-h-11 w-full rounded-[14px] bg-zinc-900 px-3 text-xs text-zinc-300 outline-none ring-1 ring-inset ring-white/[0.07]"><option value="">Все</option>{options.map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></label>;

export const StatusPill = ({ value }: { value?: string }) => <span className="shrink-0 rounded-full bg-white/[0.05] px-2.5 py-1 text-[10px] text-zinc-500 ring-1 ring-inset ring-white/[0.06]">{value === 'active' ? 'Активна' : value === 'archived' ? 'Архив' : value === 'approved' || value === 'completed' ? 'Готово' : value === 'draft' || value === 'draft_generated' || value === 'edited' ? 'Черновик' : value === 'planned' ? 'Запланировано' : value === 'fresh' ? 'Актуально' : value === 'running' || value === 'processing' ? 'В работе' : value === 'failed' || value === 'error' ? 'Ошибка' : value || 'Данные'}</span>;

export const Segments = ({ value, setValue, options }: { value: string; setValue: (value: string) => void; options: string[][] }) => <div className="mb-4 flex gap-1 overflow-x-auto rounded-[18px] bg-white/[0.035] p-1 ring-1 ring-inset ring-white/[0.06]">{options.map(([key, label]) => <button key={key} onClick={() => setValue(key)} className={`min-h-11 flex-1 whitespace-nowrap rounded-[14px] px-3 text-xs font-semibold transition-[background-color,color,transform] active:scale-[0.96] ${value === key ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-600'}`}>{label}</button>)}</div>;

export const Empty = ({ icon: Icon, title, text }: { icon: typeof Star; title: string; text: string }) => <div className="mt-4 rounded-[24px] bg-white/[0.025] px-6 py-10 text-center ring-1 ring-inset ring-white/[0.06]"><Icon className="mx-auto h-7 w-7 text-zinc-700" /><h3 className="mt-3 font-semibold">{title}</h3><p className="mx-auto mt-2 max-w-xs text-pretty text-sm leading-6 text-zinc-600">{text}</p></div>;

export const InlineError = ({ text }: { text: string }) => <div className="mb-3 flex gap-2 rounded-[16px] bg-rose-500/10 p-3 text-xs leading-5 text-rose-100 ring-1 ring-inset ring-rose-400/20"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{text}</div>;

export const ReviewSkeleton = () => <div className="space-y-3">{[1, 2, 3].map((item) => <div key={item} className="h-44 animate-pulse rounded-[24px] bg-white/[0.04] motion-reduce:animate-none" />)}</div>;

export const Screen = ({ title, subtitle, children, action }: { title: string; subtitle: string; children: React.ReactNode; action?: React.ReactNode }) => <section className="px-4"><div className="mb-5 flex items-start gap-3"><div className="min-w-0 flex-1"><h1 className="text-balance text-2xl font-semibold tracking-[-0.04em]">{title}</h1><p className="mt-1 text-pretty text-sm leading-6 text-zinc-500">{subtitle}</p></div>{action}</div>{children}</section>;
