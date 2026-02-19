import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Check, RefreshCw, Search, Trash2, TrendingUp, X } from 'lucide-react';
import { DESIGN_TOKENS, cn } from '@/lib/design-tokens';
import { useLanguage } from '@/i18n/LanguageContext';

interface Keyword {
    keyword: string;
    views: number;
    category: string;
    updated_at: string;
}

interface GroupedKeywords {
    [key: string]: Keyword[];
}

interface SEOKeywordsTabProps {
    businessId?: string | null;
}

export default function SEOKeywordsTab({ businessId }: SEOKeywordsTabProps) {
    const { t } = useLanguage();
    const [loading, setLoading] = useState(false);
    const [updating, setUpdating] = useState(false);
    const [keywords, setKeywords] = useState<Keyword[]>([]);
    const [grouped, setGrouped] = useState<GroupedKeywords>({});
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [activeCategory, setActiveCategory] = useState<string>('all');
    const [searchQuery, setSearchQuery] = useState('');
    const [searching, setSearching] = useState(false);
    const [suggestions, setSuggestions] = useState<Keyword[]>([]);
    const [rejectedSuggestions, setRejectedSuggestions] = useState<Set<string>>(new Set());

    const loadKeywords = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('auth_token');
            const qs = businessId ? `?business_id=${encodeURIComponent(businessId)}&use_city=1` : '';
            const response = await fetch(`${window.location.origin}/api/wordstat/keywords${qs}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await response.json();

            if (data.success) {
                setKeywords(data.items);
                setGrouped(data.grouped);
            } else {
                setError(data.error);
            }
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    const updateData = async () => {
        setUpdating(true);
        setError(null);
        setSuccess(null);
        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${window.location.origin}/api/wordstat/update`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ business_id: businessId }),
            });
            const data = await response.json();

            if (data.success) {
                setSuccess(data.message || (t.common.success || 'Update started.'));
                // Reload after a delay to show new data if possible, or user can refresh manually
                setTimeout(loadKeywords, 3000);
            } else {
                setError(data.error);
            }
        } catch (e: any) {
            setError(e.message);
        } finally {
            setUpdating(false);
        }
    };

    const removeKeyword = async (keyword: string) => {
        if (!businessId) {
            setError('Выберите бизнес, чтобы удалить ключевой запрос');
            return;
        }

        try {
            setError(null);
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${window.location.origin}/api/wordstat/keywords`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ business_id: businessId, keyword }),
            });
            const data = await response.json();
            if (!data.success) {
                setError(data.error || 'Ошибка удаления ключевого запроса');
                return;
            }

            setSuccess('Запрос удалён и не будет использоваться при оптимизации');
            setKeywords(prev => prev.filter(k => k.keyword !== keyword));
            setGrouped(prev => {
                const next: GroupedKeywords = {};
                for (const [cat, items] of Object.entries(prev)) {
                    next[cat] = items.filter(item => item.keyword !== keyword);
                }
                return next;
            });
        } catch (e: any) {
            setError(e.message);
        }
    };

    const searchWordstat = async () => {
        if (!businessId) {
            setError('Выберите бизнес для поиска ключевых запросов');
            return;
        }
        const q = searchQuery.trim();
        if (q.length < 2) {
            setSuggestions([]);
            return;
        }
        setSearching(true);
        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(
                `${window.location.origin}/api/wordstat/search?business_id=${encodeURIComponent(businessId)}&q=${encodeURIComponent(q)}&limit=10`,
                { headers: { 'Authorization': `Bearer ${token}` } },
            );
            const data = await response.json();
            if (!data.success) {
                setError(data.error || 'Ошибка поиска по Wordstat');
                return;
            }
            setSuggestions((data.items || []).filter((item: Keyword) => !rejectedSuggestions.has(item.keyword)));
        } catch (e: any) {
            setError(e.message);
        } finally {
            setSearching(false);
        }
    };

    const addKeyword = async (item: Keyword) => {
        if (!businessId) return;
        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${window.location.origin}/api/wordstat/keywords/custom`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    business_id: businessId,
                    keyword: item.keyword,
                    views: item.views || 0,
                    category: item.category || 'custom',
                }),
            });
            const data = await response.json();
            if (!data.success) {
                setError(data.error || 'Ошибка добавления ключевого запроса');
                return;
            }
            setSuccess('Ключевой запрос добавлен в ваш список');
            setSuggestions(prev => prev.filter(s => s.keyword !== item.keyword));
            await loadKeywords();
        } catch (e: any) {
            setError(e.message);
        }
    };

    const rejectKeyword = (keyword: string) => {
        setRejectedSuggestions(prev => new Set(prev).add(keyword));
        setSuggestions(prev => prev.filter(s => s.keyword !== keyword));
    };

    useEffect(() => {
        loadKeywords();
    }, [businessId]);

    const categories = ['all', ...Object.keys(grouped)];
    const displayedKeywords = activeCategory === 'all'
        ? keywords
        : (grouped[activeCategory] || []);

    return (
        <div className={cn(DESIGN_TOKENS.glass.default, "rounded-2xl p-6")}>
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        <TrendingUp className="w-6 h-6 text-indigo-600" />
                        {t.dashboard.card.seoKeywords?.title || 'SEO Keywords'}
                    </h2>
                    <p className="text-gray-500 mt-1">
                        {t.dashboard.card.seoKeywords?.subtitle || 'Top search queries from Yandex.Wordstat used for AI optimization.'}
                    </p>
                </div>
                <Button
                    onClick={updateData}
                    disabled={updating}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white shadow-md"
                >
                    <RefreshCw className={cn("w-4 h-4 mr-2", updating && "animate-spin")} />
                    {updating ? (t.dashboard.card.seoKeywords?.updating || "Updating...") : (t.dashboard.card.seoKeywords?.update || "Update Data")}
                </Button>
            </div>

            {error && (
                <div className="mb-6 bg-red-50 text-red-700 p-4 rounded-lg border border-red-200">
                    {error}
                </div>
            )}

            {success && (
                <div className="mb-6 bg-green-50 text-green-700 p-4 rounded-lg border border-green-200">
                    {success}
                </div>
            )}

            {/* Categories Filter */}
            <div className="flex gap-2 overflow-x-auto pb-4 mb-4">
                {categories.map(cat => (
                    <button
                        key={cat}
                        onClick={() => setActiveCategory(cat)}
                        className={cn(
                            "px-4 py-2 rounded-full text-sm font-medium transition-colors whitespace-nowrap",
                            activeCategory === cat
                                ? "bg-indigo-100 text-indigo-700 border border-indigo-200"
                                : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
                        )}
                    >
                        {cat === 'all' ? (t.dashboard.card.seoKeywords?.all || 'All Keywords') : cat.charAt(0).toUpperCase() + cat.slice(1)}
                        {cat !== 'all' && <span className="ml-2 text-xs opacity-60">({grouped[cat]?.length || 0})</span>}
                    </button>
                ))}
            </div>

            <div className="mb-6 rounded-xl border border-gray-200 bg-white p-4">
                <div className="flex flex-col md:flex-row gap-2">
                    <input
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Поиск запросов Wordstat, например: EMS массаж"
                        className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm"
                    />
                    <Button onClick={searchWordstat} disabled={searching || !businessId || searchQuery.trim().length < 2} variant="outline">
                        <Search className="w-4 h-4 mr-2" />
                        {searching ? 'Поиск...' : 'Найти запросы'}
                    </Button>
                </div>
                {suggestions.length > 0 && (
                    <div className="mt-3 space-y-2">
                        {suggestions.map((s) => (
                            <div key={s.keyword} className="flex items-center justify-between rounded-lg border border-gray-100 px-3 py-2">
                                <div className="text-sm text-gray-800">
                                    {s.keyword}
                                    <span className="ml-2 text-xs text-gray-500">({(s.views || 0).toLocaleString()})</span>
                                </div>
                                <div className="flex gap-2">
                                    <Button size="sm" variant="outline" onClick={() => addKeyword(s)}>
                                        <Check className="w-4 h-4 mr-1" />
                                        Добавить
                                    </Button>
                                    <Button size="sm" variant="ghost" onClick={() => rejectKeyword(s.keyword)}>
                                        <X className="w-4 h-4 mr-1" />
                                        Отклонить
                                    </Button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Keywords Table */}
            <div className="overflow-hidden rounded-xl border border-gray-100 bg-white">
                <table className="min-w-full divide-y divide-gray-100">
                    <thead className="bg-gray-50/50">
                        <tr>
                            <th className="px-6 py-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{t.dashboard.card.seoKeywords?.columns?.keyword || 'Keyword'}</th>
                            <th className="px-6 py-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{t.dashboard.card.seoKeywords?.columns?.category || 'Category'}</th>
                            <th className="px-6 py-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{t.dashboard.card.seoKeywords?.columns?.views || 'Monthly Views'}</th>
                            <th className="px-6 py-4 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">{t.dashboard.card.seoKeywords?.columns?.updated || 'Last Updated'}</th>
                            <th className="px-6 py-4 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Действия</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                        {loading ? (
                            <tr>
                                <td colSpan={5} className="px-6 py-8 text-center">
                                    <div className="flex justify-center items-center gap-2 text-gray-500">
                                        <div className="animate-spin rounded-full h-5 w-5 border-2 border-indigo-600 border-t-transparent"></div>
                                        <span>{t.dashboard.card.seoKeywords?.loading || "Loading keywords..."}</span>
                                    </div>
                                </td>
                            </tr>
                        ) : displayedKeywords.length === 0 ? (
                            <tr>
                                <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                                    <div className="flex flex-col items-center justify-center gap-3">
                                        <div className="p-3 bg-gray-50 rounded-full">
                                            <Search className="w-8 h-8 text-gray-300" />
                                        </div>
                                        <p>{t.dashboard.card.seoKeywords?.empty || 'No keywords found. Click "Update Data" to fetch from Wordstat.'}</p>
                                    </div>
                                </td>
                            </tr>
                        ) : (
                            displayedKeywords.map((k) => (
                                <tr key={k.keyword} className="hover:bg-gray-50 transition-colors">
                                    <td className="px-6 py-4 text-sm font-medium text-gray-900">{(k as any).keyword_with_city || k.keyword}</td>
                                    <td className="px-6 py-4 text-sm text-gray-500">
                                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                                            {k.category}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 text-sm text-gray-900 font-semibold">{k.views.toLocaleString()}</td>
                                    <td className="px-6 py-4 text-right text-sm text-gray-500">
                                        {new Date(k.updated_at).toLocaleDateString()}
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="text-red-600 hover:text-red-700 hover:bg-red-50"
                                            onClick={() => removeKeyword(k.keyword)}
                                            disabled={!businessId}
                                        >
                                            <Trash2 className="w-4 h-4 mr-1" />
                                            Удалить
                                        </Button>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
