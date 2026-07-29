import { KeyboardEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { Check, ExternalLink, Plus, RefreshCw, Search, Tags, X } from 'lucide-react';

import { newAuth } from '@/lib/auth_new';

type TelegramSource = {
  id: string;
  title: string;
  canonical_url?: string;
  status: string;
  source_role?: string;
  documents_count?: number;
  categories?: string[];
  last_collected_at?: string;
};

const suggestedCategories = [
  'бьюти',
  'медицина',
  'образование',
  'туризм',
  'рестораны',
  'чат',
  'канал',
  'владельцы',
  'мастера',
  'для клиентов',
];

const formatNumber = (value?: number) => new Intl.NumberFormat('ru-RU').format(value || 0);

const formatDate = (value?: string) => {
  if (!value) return 'ещё не обновлялся';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'дата не указана';
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(date);
};

const cleanCategory = (value: string) => value.trim().toLocaleLowerCase('ru-RU').replace(/\s+/g, ' ');

export const TelegramSourceCatalog = () => {
  const [sources, setSources] = useState<TelegramSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [visibleCount, setVisibleCount] = useState(60);
  const [editingId, setEditingId] = useState('');
  const [draftCategories, setDraftCategories] = useState<string[]>([]);
  const [customCategory, setCustomCategory] = useState('');
  const [saving, setSaving] = useState(false);

  const loadSources = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await newAuth.makeRequest('/admin/knowledge/sources?source_type=telegram');
      setSources(Array.isArray(response.items) ? response.items : []);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить Telegram-источники');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSources();
  }, [loadSources]);

  useEffect(() => {
    setVisibleCount(60);
  }, [query, categoryFilter]);

  const availableCategories = useMemo(() => {
    const values = new Set<string>();
    sources.forEach((source) => (source.categories || []).forEach((category) => values.add(category)));
    return Array.from(values).sort((left, right) => left.localeCompare(right, 'ru'));
  }, [sources]);

  const filteredSources = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase('ru-RU');
    return sources.filter((source) => {
      const categories = source.categories || [];
      if (categoryFilter === '__empty__' && categories.length > 0) return false;
      if (categoryFilter && categoryFilter !== '__empty__' && !categories.includes(categoryFilter)) return false;
      if (!normalizedQuery) return true;
      return [source.title, source.canonical_url, ...categories]
        .filter(Boolean)
        .some((value) => String(value).toLocaleLowerCase('ru-RU').includes(normalizedQuery));
    });
  }, [categoryFilter, query, sources]);

  const withoutCategories = sources.filter((source) => !(source.categories || []).length).length;
  const visibleSources = filteredSources.slice(0, visibleCount);

  const startEditing = (source: TelegramSource) => {
    setEditingId(source.id);
    setDraftCategories([...(source.categories || [])]);
    setCustomCategory('');
  };

  const toggleCategory = (category: string) => {
    setDraftCategories((current) => (
      current.includes(category) ? current.filter((item) => item !== category) : [...current, category].slice(0, 12)
    ));
  };

  const addCustomCategory = () => {
    const category = cleanCategory(customCategory);
    if (!category || draftCategories.includes(category) || draftCategories.length >= 12) return;
    setDraftCategories((current) => [...current, category]);
    setCustomCategory('');
  };

  const handleCustomCategoryKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    addCustomCategory();
  };

  const saveCategories = async () => {
    if (!editingId) return;
    setSaving(true);
    setError('');
    try {
      const response = await newAuth.makeRequest(`/admin/knowledge/sources/${editingId}/categories`, {
        method: 'PUT',
        body: JSON.stringify({ categories: draftCategories }),
      });
      const updated = response.source;
      setSources((current) => current.map((source) => (
        source.id === editingId ? { ...source, categories: updated?.categories || draftCategories } : source
      )));
      setEditingId('');
      setDraftCategories([]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить категории');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-2xl bg-slate-50 px-4 py-3 shadow-[inset_0_0_0_1px_rgba(148,163,184,0.16)]">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Всего источников</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-950">{formatNumber(sources.length)}</p>
        </div>
        <div className="rounded-2xl bg-slate-50 px-4 py-3 shadow-[inset_0_0_0_1px_rgba(148,163,184,0.16)]">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Размечены</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-emerald-700">{formatNumber(sources.length - withoutCategories)}</p>
        </div>
        <div className="rounded-2xl bg-amber-50 px-4 py-3 shadow-[inset_0_0_0_1px_rgba(217,119,6,0.14)]">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-amber-700">Нужна разметка</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-amber-950">{formatNumber(withoutCategories)}</p>
        </div>
      </div>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <label className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Название, ссылка или категория"
            className="h-11 w-full rounded-2xl bg-white pl-11 pr-4 text-sm text-slate-900 shadow-[0_0_0_1px_rgba(148,163,184,0.28)] outline-none transition-shadow placeholder:text-slate-400 focus:shadow-[0_0_0_3px_rgba(14,165,233,0.16)]"
          />
        </label>
        <button type="button" onClick={() => void loadSources()} disabled={loading} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold text-slate-600 transition-transform hover:bg-slate-50 active:scale-[0.96] disabled:opacity-50">
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Обновить
        </button>
      </div>

      <div className="flex gap-2 overflow-x-auto pb-1">
        {[
          { value: '', label: 'Все' },
          { value: '__empty__', label: `Без категорий · ${formatNumber(withoutCategories)}` },
          ...availableCategories.map((category) => ({ value: category, label: category })),
        ].map((filter) => (
          <button
            key={filter.value || '__all__'}
            type="button"
            onClick={() => setCategoryFilter(filter.value)}
            className={`min-h-10 shrink-0 rounded-xl px-3 text-sm font-semibold transition-transform active:scale-[0.96] ${categoryFilter === filter.value ? 'bg-slate-950 text-white shadow-sm' : 'bg-slate-100 text-slate-600 hover:text-slate-950'}`}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {error ? <div className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-800 shadow-[inset_0_0_0_1px_rgba(225,29,72,0.14)]">{error}</div> : null}

      <div className="divide-y divide-slate-200 rounded-2xl bg-white shadow-[0_1px_3px_rgba(15,23,42,0.06),0_0_0_1px_rgba(148,163,184,0.16)]">
        {!loading && visibleSources.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <Tags className="mx-auto h-7 w-7 text-slate-400" />
            <p className="mt-3 font-semibold text-slate-900">Источники не найдены</p>
            <p className="mt-1 text-sm text-slate-500">Измените поиск или выберите другую категорию.</p>
          </div>
        ) : visibleSources.map((source) => {
          const editing = editingId === source.id;
          return (
            <article key={source.id} className="px-4 py-4 sm:px-5">
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="min-w-0 truncate text-balance font-semibold text-slate-950">{source.title}</h3>
                    <span className={`rounded-md px-2 py-1 text-[11px] font-semibold ${source.status === 'active' ? 'bg-emerald-50 text-emerald-700' : source.status === 'candidate' ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>
                      {source.status === 'active' ? 'Отслеживается' : source.status === 'candidate' ? 'Нужно проверить' : 'На паузе'}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-slate-500">
                    <span className="tabular-nums">{formatNumber(source.documents_count)}</span> сообщений · обновлено {formatDate(source.last_collected_at)}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {(source.categories || []).length ? (source.categories || []).map((category) => (
                      <span key={category} className="rounded-lg bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700">{category}</span>
                    )) : <span className="text-xs font-medium text-amber-700">Категории ещё не указаны</span>}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {source.canonical_url ? (
                    <a href={source.canonical_url} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center gap-2 rounded-xl px-3 text-sm font-semibold text-slate-600 transition-transform hover:bg-slate-50 active:scale-[0.96]">
                      Открыть <ExternalLink className="h-4 w-4" />
                    </a>
                  ) : null}
                  <button type="button" onClick={() => editing ? setEditingId('') : startEditing(source)} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-slate-950 px-4 text-sm font-semibold text-white transition-transform hover:bg-slate-800 active:scale-[0.96]">
                    <Tags className="h-4 w-4" /> {editing ? 'Закрыть' : 'Разметить'}
                  </button>
                </div>
              </div>

              {editing ? (
                <div className="mt-4 rounded-2xl bg-slate-50 p-4 shadow-[inset_0_0_0_1px_rgba(148,163,184,0.16)]">
                  <p className="text-sm font-semibold text-slate-900">Что это за источник?</p>
                  <p className="mt-1 text-pretty text-xs leading-5 text-slate-500">Выберите несколько категорий: отрасль, формат и аудиторию. Можно добавить собственную.</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {suggestedCategories.map((category) => {
                      const selected = draftCategories.includes(category);
                      return (
                        <button key={category} type="button" onClick={() => toggleCategory(category)} className={`inline-flex min-h-10 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold transition-transform active:scale-[0.96] ${selected ? 'bg-sky-600 text-white shadow-sm' : 'bg-white text-slate-600 shadow-[0_0_0_1px_rgba(148,163,184,0.24)] hover:text-slate-950'}`}>
                          {selected ? <Check className="h-3.5 w-3.5" /> : null}{category}
                        </button>
                      );
                    })}
                  </div>
                  {draftCategories.filter((category) => !suggestedCategories.includes(category)).length ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {draftCategories.filter((category) => !suggestedCategories.includes(category)).map((category) => (
                        <button key={category} type="button" onClick={() => toggleCategory(category)} className="inline-flex min-h-10 items-center gap-1.5 rounded-xl bg-violet-50 px-3 text-sm font-semibold text-violet-700 transition-transform active:scale-[0.96]">
                          {category}<X className="h-3.5 w-3.5" />
                        </button>
                      ))}
                    </div>
                  ) : null}
                  <div className="mt-4 flex flex-col gap-2 sm:flex-row">
                    <input value={customCategory} onChange={(event) => setCustomCategory(event.target.value)} onKeyDown={handleCustomCategoryKeyDown} placeholder="Своя категория" maxLength={40} className="h-11 min-w-0 flex-1 rounded-xl bg-white px-4 text-sm text-slate-900 shadow-[0_0_0_1px_rgba(148,163,184,0.28)] outline-none focus:shadow-[0_0_0_3px_rgba(14,165,233,0.16)]" />
                    <button type="button" onClick={addCustomCategory} disabled={!cleanCategory(customCategory)} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-white px-4 text-sm font-semibold text-slate-700 shadow-[0_0_0_1px_rgba(148,163,184,0.28)] transition-transform active:scale-[0.96] disabled:opacity-40">
                      <Plus className="h-4 w-4" /> Добавить
                    </button>
                    <button type="button" onClick={() => void saveCategories()} disabled={saving} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-sky-600 px-5 text-sm font-semibold text-white shadow-[0_6px_18px_rgba(2,132,199,0.2)] transition-transform hover:bg-sky-700 active:scale-[0.96] disabled:opacity-50">
                      <Check className="h-4 w-4" /> {saving ? 'Сохраняем…' : 'Сохранить'}
                    </button>
                  </div>
                </div>
              ) : null}
            </article>
          );
        })}
      </div>

      {visibleCount < filteredSources.length ? (
        <button type="button" onClick={() => setVisibleCount((current) => current + 60)} className="min-h-11 w-full rounded-xl bg-slate-100 px-4 text-sm font-semibold text-slate-700 transition-transform hover:bg-slate-200 active:scale-[0.96]">
          Показать ещё · осталось <span className="tabular-nums">{formatNumber(filteredSources.length - visibleCount)}</span>
        </button>
      ) : null}
    </div>
  );
};
