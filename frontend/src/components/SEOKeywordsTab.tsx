import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Check, RefreshCw, Search, Trash2, TrendingUp, X } from 'lucide-react';
import { DESIGN_TOKENS, cn } from '@/lib/design-tokens';
import { useLanguage } from '@/i18n/LanguageContext';
import { useOutletContext } from 'react-router-dom';
import { getDemoShowcaseData } from '@/i18n/demoShowcaseData';

interface Keyword {
    keyword: string;
    views: number;
    category: string;
    updated_at: string;
    negative_blocked?: boolean;
    negative_reason?: string;
}

interface NegativeKeyword {
    id: string;
    phrase: string;
    scope: 'global' | 'category';
    category: string;
    created_at: string;
}

interface GroupedKeywords {
    [key: string]: Keyword[];
}

interface SEOKeywordsTabProps {
    businessId?: string | null;
}

const negativeBulkCopy: Record<string, { placeholder: string; button: string }> = {
    ru: {
        placeholder: 'Массовое добавление: одно минус-слово на строку',
        button: 'Добавить списком',
    },
    en: {
        placeholder: 'Bulk add: one negative keyword per line',
        button: 'Add in bulk',
    },
    fr: {
        placeholder: 'Ajout groupé : un mot-clé négatif par ligne',
        button: 'Ajouter en lot',
    },
    es: {
        placeholder: 'Añadir en bloque: una palabra clave negativa por línea',
        button: 'Añadir en bloque',
    },
    el: {
        placeholder: 'Μαζική προσθήκη: μία αρνητική λέξη-κλειδί ανά γραμμή',
        button: 'Μαζική προσθήκη',
    },
    de: {
        placeholder: 'Massenhinzufügen: ein negatives Keyword pro Zeile',
        button: 'Massenhaft hinzufügen',
    },
    th: {
        placeholder: 'เพิ่มจำนวนมาก: คีย์เวิร์ดเชิงลบหนึ่งรายการต่อบรรทัด',
        button: 'เพิ่มจำนวนมาก',
    },
    ar: {
        placeholder: 'إضافة جماعية: كلمة مفتاحية سلبية واحدة في كل سطر',
        button: 'إضافة جماعية',
    },
    ha: {
        placeholder: 'Ƙara da yawa: kalmar kullewa mara kyau ɗaya a kowane layi',
        button: 'Ƙara da yawa',
    },
    tr: {
        placeholder: 'Toplu ekleme: her satıra bir negatif anahtar kelime',
        button: 'Toplu ekle',
    },
};

const seoOperationalCopy: Record<string, Record<string, string>> = {
    ru: {
        negativeTitle: 'Минус-слова SEO', negativePlaceholder: 'Добавить минус-слово', globalScope: 'Глобально', categoryScope: 'По категории', categoryPlaceholder: 'Категория (если выбрано)', showBlocked: 'Показать исключённые минус-словами', loading: 'Загрузка…', negativeEmpty: 'Минус-слов пока нет', searchPlaceholder: 'Поиск запросов Wordstat, например: EMS массаж', searching: 'Поиск...', findQueries: 'Найти запросы', add: 'Добавить', reject: 'Отклонить', noSuggestions: 'По запросу ничего не найдено. Проверьте опечатки или попробуйте более широкую формулировку.', currentSearch: 'Поиск по текущим SEO-запросам', allFrequency: 'Все запросы по частотности', highFrequency: 'Высокочастотные (от 10 000)', midFrequency: 'Среднечастотные (1 000 - 9 999)', lowFrequency: 'Низкочастотные (до 999)', actions: 'Действия', remove: 'Удалить', categoryRequired: 'Укажите категорию', loadNegativeError: 'Ошибка загрузки минус-слов', addNegativeError: 'Ошибка добавления минус-слова', negativeAdded: 'Минус-слово добавлено', bulkError: 'Ошибка массового добавления', bulkAdded: 'Минус-слова добавлены', removeNegativeError: 'Ошибка удаления минус-слова', updateError: 'Не удалось обновить SEO-ключи', chooseBusiness: 'Выберите бизнес', keywordRemoveError: 'Ошибка удаления запроса', keywordRemoved: 'Запрос удалён', searchError: 'Ошибка поиска Wordstat', keywordAddError: 'Ошибка добавления запроса', keywordAdded: 'Запрос добавлен',
    },
    en: {
        negativeTitle: 'SEO negative keywords', negativePlaceholder: 'Add a negative keyword', globalScope: 'Global', categoryScope: 'By category', categoryPlaceholder: 'Category (when selected)', showBlocked: 'Show queries excluded by negative keywords', loading: 'Loading…', negativeEmpty: 'No negative keywords yet', searchPlaceholder: 'Search Wordstat queries, for example: EMS massage', searching: 'Searching...', findQueries: 'Find queries', add: 'Add', reject: 'Reject', noSuggestions: 'Nothing was found. Check the spelling or try a broader phrase.', currentSearch: 'Search current SEO queries', allFrequency: 'All query frequencies', highFrequency: 'High frequency (10,000+)', midFrequency: 'Medium frequency (1,000 - 9,999)', lowFrequency: 'Low frequency (up to 999)', actions: 'Actions', remove: 'Remove', categoryRequired: 'Enter a category', loadNegativeError: 'Could not load negative keywords', addNegativeError: 'Could not add the negative keyword', negativeAdded: 'Negative keyword added', bulkError: 'Could not add negative keywords in bulk', bulkAdded: 'Negative keywords added', removeNegativeError: 'Could not remove the negative keyword', updateError: 'Could not update SEO keywords', chooseBusiness: 'Select a business', keywordRemoveError: 'Could not remove the query', keywordRemoved: 'Query removed', searchError: 'Wordstat search failed', keywordAddError: 'Could not add the query', keywordAdded: 'Query added',
    },
    tr: {
        negativeTitle: 'SEO negatif anahtar kelimeleri', negativePlaceholder: 'Negatif anahtar kelime ekle', globalScope: 'Genel', categoryScope: 'Kategoriye göre', categoryPlaceholder: 'Kategori (seçildiyse)', showBlocked: 'Negatif anahtar kelimelerle hariç tutulanları göster', loading: 'Yükleniyor…', negativeEmpty: 'Henüz negatif anahtar kelime yok', searchPlaceholder: 'Wordstat sorgularında ara, örneğin: EMS masajı', searching: 'Aranıyor...', findQueries: 'Sorgu bul', add: 'Ekle', reject: 'Reddet', noSuggestions: 'Sonuç bulunamadı. Yazımı kontrol edin veya daha geniş bir ifade deneyin.', currentSearch: 'Mevcut SEO sorgularında ara', allFrequency: 'Tüm sorgu sıklıkları', highFrequency: 'Yüksek sıklık (10.000+)', midFrequency: 'Orta sıklık (1.000 - 9.999)', lowFrequency: 'Düşük sıklık (999’a kadar)', actions: 'İşlemler', remove: 'Sil', categoryRequired: 'Kategori belirtin', loadNegativeError: 'Negatif anahtar kelimeler yüklenemedi', addNegativeError: 'Negatif anahtar kelime eklenemedi', negativeAdded: 'Negatif anahtar kelime eklendi', bulkError: 'Negatif anahtar kelimeler toplu olarak eklenemedi', bulkAdded: 'Negatif anahtar kelimeler eklendi', removeNegativeError: 'Negatif anahtar kelime silinemedi', updateError: 'SEO anahtar kelimeleri güncellenemedi', chooseBusiness: 'İşletme seçin', keywordRemoveError: 'Sorgu silinemedi', keywordRemoved: 'Sorgu silindi', searchError: 'Wordstat araması başarısız oldu', keywordAddError: 'Sorgu eklenemedi', keywordAdded: 'Sorgu eklendi',
    },
};

type SeoCoreCopy = { negativeTitle: string; negativePlaceholder: string; globalScope: string; categoryScope: string; categoryPlaceholder: string; showBlocked: string; negativeEmpty: string; searchPlaceholder: string; findQueries: string; currentSearch: string; allFrequency: string; actions: string; remove: string; add: string; reject: string; loading: string; failure: string };
const buildSeoOperationalCopy = (value: SeoCoreCopy): Record<string, string> => ({
    negativeTitle: value.negativeTitle, negativePlaceholder: value.negativePlaceholder, globalScope: value.globalScope, categoryScope: value.categoryScope, categoryPlaceholder: value.categoryPlaceholder, showBlocked: value.showBlocked, loading: value.loading, negativeEmpty: value.negativeEmpty, searchPlaceholder: value.searchPlaceholder, searching: value.loading, findQueries: value.findQueries, add: value.add, reject: value.reject, noSuggestions: value.failure, currentSearch: value.currentSearch, allFrequency: value.allFrequency, highFrequency: value.allFrequency, midFrequency: value.allFrequency, lowFrequency: value.allFrequency, actions: value.actions, remove: value.remove, categoryRequired: value.categoryPlaceholder, loadNegativeError: value.failure, addNegativeError: value.failure, negativeAdded: value.add, bulkError: value.failure, bulkAdded: value.add, removeNegativeError: value.failure, updateError: value.failure, chooseBusiness: value.failure, keywordRemoveError: value.failure, keywordRemoved: value.remove, searchError: value.failure, keywordAddError: value.failure, keywordAdded: value.add,
});
const additionalSeoOperationalCopy: Record<string, Record<string, string>> = {
    fr: buildSeoOperationalCopy({ negativeTitle: 'Mots-clés négatifs SEO', negativePlaceholder: 'Ajouter un mot-clé négatif', globalScope: 'Global', categoryScope: 'Par catégorie', categoryPlaceholder: 'Catégorie', showBlocked: 'Afficher les requêtes exclues', negativeEmpty: 'Aucun mot-clé négatif', searchPlaceholder: 'Rechercher dans Wordstat', findQueries: 'Trouver des requêtes', currentSearch: 'Rechercher dans les requêtes actuelles', allFrequency: 'Toutes les fréquences', actions: 'Actions', remove: 'Supprimer', add: 'Ajouter', reject: 'Rejeter', loading: 'Chargement…', failure: 'Impossible d’effectuer cette action' }),
    es: buildSeoOperationalCopy({ negativeTitle: 'Palabras negativas SEO', negativePlaceholder: 'Añadir palabra negativa', globalScope: 'Global', categoryScope: 'Por categoría', categoryPlaceholder: 'Categoría', showBlocked: 'Mostrar consultas excluidas', negativeEmpty: 'No hay palabras negativas', searchPlaceholder: 'Buscar en Wordstat', findQueries: 'Buscar consultas', currentSearch: 'Buscar en consultas actuales', allFrequency: 'Todas las frecuencias', actions: 'Acciones', remove: 'Eliminar', add: 'Añadir', reject: 'Rechazar', loading: 'Cargando…', failure: 'No se pudo realizar la acción' }),
    el: buildSeoOperationalCopy({ negativeTitle: 'Αρνητικές λέξεις SEO', negativePlaceholder: 'Προσθήκη αρνητικής λέξης', globalScope: 'Γενικά', categoryScope: 'Ανά κατηγορία', categoryPlaceholder: 'Κατηγορία', showBlocked: 'Προβολή εξαιρούμενων αναζητήσεων', negativeEmpty: 'Δεν υπάρχουν αρνητικές λέξεις', searchPlaceholder: 'Αναζήτηση στο Wordstat', findQueries: 'Εύρεση αναζητήσεων', currentSearch: 'Αναζήτηση στις τρέχουσες λέξεις', allFrequency: 'Όλες οι συχνότητες', actions: 'Ενέργειες', remove: 'Διαγραφή', add: 'Προσθήκη', reject: 'Απόρριψη', loading: 'Φόρτωση…', failure: 'Η ενέργεια δεν ολοκληρώθηκε' }),
    de: buildSeoOperationalCopy({ negativeTitle: 'Negative SEO-Keywords', negativePlaceholder: 'Negatives Keyword hinzufügen', globalScope: 'Global', categoryScope: 'Nach Kategorie', categoryPlaceholder: 'Kategorie', showBlocked: 'Ausgeschlossene Suchanfragen anzeigen', negativeEmpty: 'Keine negativen Keywords', searchPlaceholder: 'In Wordstat suchen', findQueries: 'Suchanfragen finden', currentSearch: 'Aktuelle Suchanfragen durchsuchen', allFrequency: 'Alle Häufigkeiten', actions: 'Aktionen', remove: 'Entfernen', add: 'Hinzufügen', reject: 'Ablehnen', loading: 'Laden…', failure: 'Aktion konnte nicht ausgeführt werden' }),
    th: buildSeoOperationalCopy({ negativeTitle: 'คีย์เวิร์ดเชิงลบ SEO', negativePlaceholder: 'เพิ่มคีย์เวิร์ดเชิงลบ', globalScope: 'ทั้งหมด', categoryScope: 'ตามหมวดหมู่', categoryPlaceholder: 'หมวดหมู่', showBlocked: 'แสดงคำค้นที่ยกเว้น', negativeEmpty: 'ยังไม่มีคีย์เวิร์ดเชิงลบ', searchPlaceholder: 'ค้นหาใน Wordstat', findQueries: 'ค้นหาคำค้น', currentSearch: 'ค้นหาในคำค้นปัจจุบัน', allFrequency: 'ทุกความถี่', actions: 'การดำเนินการ', remove: 'ลบ', add: 'เพิ่ม', reject: 'ปฏิเสธ', loading: 'กำลังโหลด…', failure: 'ดำเนินการไม่สำเร็จ' }),
    ar: buildSeoOperationalCopy({ negativeTitle: 'الكلمات السلبية لـ SEO', negativePlaceholder: 'إضافة كلمة سلبية', globalScope: 'عام', categoryScope: 'حسب الفئة', categoryPlaceholder: 'الفئة', showBlocked: 'عرض الاستعلامات المستبعدة', negativeEmpty: 'لا توجد كلمات سلبية', searchPlaceholder: 'البحث في Wordstat', findQueries: 'البحث عن استعلامات', currentSearch: 'البحث في الاستعلامات الحالية', allFrequency: 'كل التكرارات', actions: 'الإجراءات', remove: 'حذف', add: 'إضافة', reject: 'رفض', loading: 'جارٍ التحميل…', failure: 'تعذر تنفيذ الإجراء' }),
    ha: buildSeoOperationalCopy({ negativeTitle: 'Kalmomin SEO da aka hana', negativePlaceholder: 'Ƙara kalmar da aka hana', globalScope: 'Gaba ɗaya', categoryScope: 'Ta rukuni', categoryPlaceholder: 'Rukuni', showBlocked: 'Nuna tambayoyin da aka cire', negativeEmpty: 'Babu kalmomin da aka hana', searchPlaceholder: 'Bincika a Wordstat', findQueries: 'Nemo tambayoyi', currentSearch: 'Bincika tambayoyin yanzu', allFrequency: 'Duk yawan nema', actions: 'Ayyuka', remove: 'Cire', add: 'Ƙara', reject: 'Ƙi', loading: 'Ana lodawa…', failure: 'Ba a iya yin aikin ba' }),
};

export default function SEOKeywordsTab({ businessId }: SEOKeywordsTabProps) {
    const { language, t } = useLanguage();
    const { user } = useOutletContext<any>();
    const demoMode = Boolean(user?.demo_mode);
    const [loading, setLoading] = useState(false);
    const [updating, setUpdating] = useState(false);
    const [keywords, setKeywords] = useState<Keyword[]>([]);
    const [grouped, setGrouped] = useState<GroupedKeywords>({});
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [activeCategory, setActiveCategory] = useState<string>('all');
    const [searchQuery, setSearchQuery] = useState('');
    const [tableQuery, setTableQuery] = useState('');
    const [viewsFilter, setViewsFilter] = useState<'all' | 'high' | 'mid' | 'low'>('all');
    const [searching, setSearching] = useState(false);
    const [suggestions, setSuggestions] = useState<Keyword[]>([]);
    const [hasSearchedSuggestions, setHasSearchedSuggestions] = useState(false);
    const [rejectedSuggestions, setRejectedSuggestions] = useState<Set<string>>(new Set());
    const [showBlocked, setShowBlocked] = useState(false);
    const [negativeKeywords, setNegativeKeywords] = useState<NegativeKeyword[]>([]);
    const [negativePhrase, setNegativePhrase] = useState('');
    const [negativeScope, setNegativeScope] = useState<'global' | 'category'>('global');
    const [negativeCategory, setNegativeCategory] = useState('');
    const [negativeBulkText, setNegativeBulkText] = useState('');
    const [negativeLoading, setNegativeLoading] = useState(false);
    const operationalCopy = seoOperationalCopy[language] || additionalSeoOperationalCopy[language] || seoOperationalCopy.en;

    const loadKeywords = async () => {
        setLoading(true);
        if (demoMode) {
            const demoKeywords = getDemoShowcaseData(language).keywords;
            setKeywords(demoKeywords);
            setGrouped({ [demoKeywords[0].category]: demoKeywords });
            setError(null);
            setLoading(false);
            return;
        }
        try {
            const token = localStorage.getItem('auth_token');
            const qs = businessId
                ? `?business_id=${encodeURIComponent(businessId)}&use_city=1&include_blocked=${showBlocked ? '1' : '0'}`
                : '';
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

    const loadNegativeKeywords = async () => {
        if (demoMode) {
            setNegativeKeywords([]);
            return;
        }
        if (!businessId) {
            setNegativeKeywords([]);
            return;
        }
        setNegativeLoading(true);
        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(
                `${window.location.origin}/api/wordstat/negative-keywords?business_id=${encodeURIComponent(businessId)}`,
                { headers: { 'Authorization': `Bearer ${token}` } },
            );
            const data = await response.json();
            if (data.success) {
                setNegativeKeywords(data.items || []);
            } else {
                setError(data.error || operationalCopy.loadNegativeError);
            }
        } catch (e: any) {
            setError(e.message);
        } finally {
            setNegativeLoading(false);
        }
    };

    const addNegativeKeyword = async () => {
        if (!businessId) return;
        const phrase = negativePhrase.trim();
        if (!phrase) return;
        if (negativeScope === 'category' && !negativeCategory.trim()) {
            setError(operationalCopy.categoryRequired);
            return;
        }
        try {
            setError(null);
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${window.location.origin}/api/wordstat/negative-keywords`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    business_id: businessId,
                    phrase,
                    scope: negativeScope,
                    category: negativeScope === 'category' ? negativeCategory.trim() : '',
                }),
            });
            const data = await response.json();
            if (!data.success) {
                setError(data.error || operationalCopy.addNegativeError);
                return;
            }
            setNegativePhrase('');
            setSuccess(operationalCopy.negativeAdded);
            await Promise.all([loadNegativeKeywords(), loadKeywords()]);
        } catch (e: any) {
            setError(e.message);
        }
    };

    const addNegativeKeywordsBulk = async () => {
        if (!businessId) return;
        if (!negativeBulkText.trim()) return;
        if (negativeScope === 'category' && !negativeCategory.trim()) {
            setError(operationalCopy.categoryRequired);
            return;
        }
        try {
            setError(null);
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${window.location.origin}/api/wordstat/negative-keywords/bulk`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    business_id: businessId,
                    scope: negativeScope,
                    category: negativeScope === 'category' ? negativeCategory.trim() : '',
                    raw_text: negativeBulkText,
                }),
            });
            const data = await response.json();
            if (!data.success) {
                setError(data.error || operationalCopy.bulkError);
                return;
            }
            setNegativeBulkText('');
            setSuccess(data.message || operationalCopy.bulkAdded);
            await Promise.all([loadNegativeKeywords(), loadKeywords()]);
        } catch (e: any) {
            setError(e.message);
        }
    };

    const removeNegativeKeyword = async (item: NegativeKeyword) => {
        if (!businessId) return;
        try {
            setError(null);
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${window.location.origin}/api/wordstat/negative-keywords`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ business_id: businessId, id: item.id }),
            });
            const data = await response.json();
            if (!data.success) {
                setError(data.error || operationalCopy.removeNegativeError);
                return;
            }
            await Promise.all([loadNegativeKeywords(), loadKeywords()]);
        } catch (e: any) {
            setError(e.message);
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
                const superadminDetails = typeof data.superadmin === 'string' && data.superadmin.trim()
                    ? `\n\nsuperadmin: ${data.superadmin.trim()}`
                    : '';
                setError(`${data.error || operationalCopy.updateError}${superadminDetails}`);
            }
        } catch (e: any) {
            setError(e.message);
        } finally {
            setUpdating(false);
        }
    };

    const removeKeyword = async (keyword: string) => {
        if (!businessId) {
            setError(operationalCopy.chooseBusiness);
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
                setError(data.error || operationalCopy.keywordRemoveError);
                return;
            }

            setSuccess(operationalCopy.keywordRemoved);
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
            setError(operationalCopy.chooseBusiness);
            return;
        }
        const q = searchQuery.trim();
        if (q.length < 2) {
            setSuggestions([]);
            setHasSearchedSuggestions(false);
            return;
        }
        setSearching(true);
        setHasSearchedSuggestions(true);
        setError(null);
        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(
                `${window.location.origin}/api/wordstat/search?business_id=${encodeURIComponent(businessId)}&q=${encodeURIComponent(q)}&limit=10`,
                { headers: { 'Authorization': `Bearer ${token}` } },
            );
            const data = await response.json();
            if (!data.success) {
                setError(data.error || operationalCopy.searchError);
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
                setError(data.error || operationalCopy.keywordAddError);
                return;
            }
            setSuccess(operationalCopy.keywordAdded);
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
        loadNegativeKeywords();
    }, [businessId, showBlocked, language, demoMode]);

    const categories = ['all', ...Object.keys(grouped)];
    const displayedKeywords = (activeCategory === 'all'
        ? keywords
        : (grouped[activeCategory] || [])
    ).filter((k) => {
        const q = tableQuery.trim().toLowerCase();
        if (q) {
            const keywordText = `${(k as any).keyword_with_city || ''} ${k.keyword} ${k.category}`.toLowerCase();
            if (!keywordText.includes(q)) return false;
        }

        if (viewsFilter === 'high') return k.views >= 10000;
        if (viewsFilter === 'mid') return k.views >= 1000 && k.views < 10000;
        if (viewsFilter === 'low') return k.views < 1000;
        return true;
    });

    const seoCopy = t.dashboard.card.seoKeywords || {};
    const fallbackSeoCopy = {
        title: language === 'ru' ? 'SEO-запросы' : language === 'tr' ? 'SEO sorguları' : `SEO · ${operationalCopy.findQueries}`,
        subtitle: operationalCopy.searchPlaceholder,
        update: operationalCopy.findQueries,
        updating: operationalCopy.loading,
        all: operationalCopy.allFrequency,
        loading: operationalCopy.loading,
        empty: operationalCopy.negativeEmpty,
        columns: { keyword: operationalCopy.findQueries, category: operationalCopy.categoryPlaceholder, views: operationalCopy.allFrequency, updated: operationalCopy.loading },
        categories: { grooming: operationalCopy.categoryScope, other: operationalCopy.globalScope, custom: operationalCopy.actions },
    };

    const getSeoText = (key: 'title' | 'subtitle' | 'update' | 'updating' | 'all' | 'loading' | 'empty') => language === 'en' ? seoCopy[key] || fallbackSeoCopy[key] : fallbackSeoCopy[key];
    const getSeoColumnText = (key: 'keyword' | 'category' | 'views' | 'updated') => language === 'en' ? seoCopy.columns?.[key] || fallbackSeoCopy.columns[key] : fallbackSeoCopy.columns[key];
    const negativeBulkLabels = negativeBulkCopy[language] || negativeBulkCopy.en;
    const formatCategory = (category: string) => {
        const normalized = String(category || 'other').trim().toLowerCase();
        const categoryLabels = language === 'en' ? seoCopy.categories || fallbackSeoCopy.categories : fallbackSeoCopy.categories;
        return categoryLabels[normalized] || (normalized ? normalized.charAt(0).toUpperCase() + normalized.slice(1) : fallbackSeoCopy.categories.other);
    };

    return (
        <div className={cn(DESIGN_TOKENS.glass.default, "rounded-2xl p-6")}>
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        <TrendingUp className="w-6 h-6 text-indigo-600" />
                        {getSeoText('title')}
                    </h2>
                    <p className="text-gray-500 mt-1">
                        {getSeoText('subtitle')}
                    </p>
                </div>
                <Button
                    onClick={updateData}
                    disabled={updating}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white shadow-md"
                >
                    <RefreshCw className={cn("w-4 h-4 mr-2", updating && "animate-spin")} />
                    {updating ? getSeoText('updating') : getSeoText('update')}
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
                        {cat === 'all' ? getSeoText('all') : formatCategory(cat)}
                        {cat !== 'all' && <span className="ml-2 text-xs opacity-60">({grouped[cat]?.length || 0})</span>}
                    </button>
                ))}
            </div>

            <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50/50 p-4">
                <h3 className="text-sm font-semibold text-amber-900 mb-3">{operationalCopy.negativeTitle}</h3>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-2">
                    <input
                        value={negativePhrase}
                        onChange={(e) => setNegativePhrase(e.target.value)}
                        placeholder={operationalCopy.negativePlaceholder}
                        className="rounded-lg border border-amber-200 px-3 py-2 text-sm md:col-span-2"
                    />
                    <select
                        value={negativeScope}
                        onChange={(e) => setNegativeScope(e.target.value as 'global' | 'category')}
                        className="rounded-lg border border-amber-200 px-3 py-2 text-sm bg-white"
                    >
                        <option value="global">{operationalCopy.globalScope}</option>
                        <option value="category">{operationalCopy.categoryScope}</option>
                    </select>
                    <input
                        value={negativeCategory}
                        onChange={(e) => setNegativeCategory(e.target.value)}
                        placeholder={operationalCopy.categoryPlaceholder}
                        disabled={negativeScope !== 'category'}
                        className="rounded-lg border border-amber-200 px-3 py-2 text-sm disabled:bg-gray-100"
                    />
                </div>
                <div className="flex flex-col md:flex-row gap-2 mb-3">
                    <Button variant="outline" onClick={addNegativeKeyword} disabled={!businessId || !negativePhrase.trim()}>
                        {operationalCopy.negativePlaceholder}
                    </Button>
                    <label className="inline-flex items-center gap-2 text-sm text-gray-700">
                        <input
                            type="checkbox"
                            checked={showBlocked}
                            onChange={(e) => setShowBlocked(e.target.checked)}
                        />
                        {operationalCopy.showBlocked}
                    </label>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-3">
                    <textarea
                        value={negativeBulkText}
                        onChange={(e) => setNegativeBulkText(e.target.value)}
                        placeholder={negativeBulkLabels.placeholder}
                        className="rounded-lg border border-amber-200 px-3 py-2 text-sm min-h-[90px]"
                    />
                    <div className="rounded-lg border border-amber-200 bg-white p-2 max-h-[140px] overflow-y-auto">
                        {negativeLoading ? (
                            <div className="text-xs text-gray-500">{operationalCopy.loading}</div>
                        ) : negativeKeywords.length === 0 ? (
                            <div className="text-xs text-gray-500">{operationalCopy.negativeEmpty}</div>
                        ) : (
                            <div className="space-y-1">
                                {negativeKeywords.map((item) => (
                                    <div key={item.id} className="flex items-center justify-between rounded border border-gray-100 px-2 py-1 text-xs">
                                        <div>
                                            <span className="font-medium text-gray-800">{item.phrase}</span>
                                            <span className="ml-2 text-gray-500">
                                                [{item.scope}{item.scope === 'category' ? `:${item.category}` : ''}]
                                            </span>
                                        </div>
                                        <Button variant="ghost" size="sm" onClick={() => removeNegativeKeyword(item)}>
                                            <Trash2 className="w-3 h-3 text-red-600" />
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
                <Button
                    variant="outline"
                    onClick={addNegativeKeywordsBulk}
                    disabled={!businessId || !negativeBulkText.trim()}
                >
                    {negativeBulkLabels.button}
                </Button>
            </div>

            <div className="mb-6 rounded-xl border border-gray-200 bg-white p-4">
                <div className="flex flex-col md:flex-row gap-2">
                    <input
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onKeyDown={(event) => {
                            if (event.key === 'Enter') {
                                event.preventDefault();
                                void searchWordstat();
                            }
                        }}
                        placeholder={operationalCopy.searchPlaceholder}
                        className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm"
                    />
                    <Button onClick={searchWordstat} disabled={searching || !businessId || searchQuery.trim().length < 2} variant="outline">
                        <Search className="w-4 h-4 mr-2" />
                        {searching ? operationalCopy.searching : operationalCopy.findQueries}
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
                                        {operationalCopy.add}
                                    </Button>
                                    <Button size="sm" variant="ghost" onClick={() => rejectKeyword(s.keyword)}>
                                        <X className="w-4 h-4 mr-1" />
                                        {operationalCopy.reject}
                                    </Button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
                {hasSearchedSuggestions && !searching && suggestions.length === 0 && searchQuery.trim().length >= 2 && (
                    <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-800">
                        {operationalCopy.noSuggestions}
                    </div>
                )}
            </div>

            <div className="mb-4 rounded-xl border border-gray-200 bg-white p-4">
                <div className="flex flex-col md:flex-row gap-3">
                    <div className="flex-1">
                        <input
                            value={tableQuery}
                            onChange={(e) => setTableQuery(e.target.value)}
                            placeholder={operationalCopy.currentSearch}
                            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
                        />
                    </div>
                    <select
                        value={viewsFilter}
                        onChange={(e) => setViewsFilter(e.target.value as 'all' | 'high' | 'mid' | 'low')}
                        className="rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white min-w-[240px]"
                    >
                        <option value="all">{operationalCopy.allFrequency}</option>
                        <option value="high">{operationalCopy.highFrequency}</option>
                        <option value="mid">{operationalCopy.midFrequency}</option>
                        <option value="low">{operationalCopy.lowFrequency}</option>
                    </select>
                </div>
            </div>

            {/* Keywords Table */}
            <div className="overflow-hidden rounded-xl border border-gray-100 bg-white">
                <table className="min-w-full divide-y divide-gray-100">
                    <thead className="bg-gray-50/50">
                        <tr>
                            <th className="px-6 py-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{getSeoColumnText('keyword')}</th>
                            <th className="px-6 py-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{getSeoColumnText('category')}</th>
                            <th className="px-6 py-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{getSeoColumnText('views')}</th>
                            <th className="px-6 py-4 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">{getSeoColumnText('updated')}</th>
                            <th className="px-6 py-4 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">{operationalCopy.actions}</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                        {loading ? (
                            <tr>
                                <td colSpan={5} className="px-6 py-8 text-center">
                                    <div className="flex justify-center items-center gap-2 text-gray-500">
                                        <div className="animate-spin rounded-full h-5 w-5 border-2 border-indigo-600 border-t-transparent"></div>
                                        <span>{getSeoText('loading')}</span>
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
                                        <p>{getSeoText('empty')}</p>
                                    </div>
                                </td>
                            </tr>
                        ) : (
                            displayedKeywords.map((k) => (
                                <tr key={k.keyword} className="hover:bg-gray-50 transition-colors">
                                    <td className="px-6 py-4 text-sm font-medium text-gray-900">{(k as any).keyword_with_city || k.keyword}</td>
                                    <td className="px-6 py-4 text-sm text-gray-500">
                                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                                            {formatCategory(k.category)}
                                        </span>
                                        {k.negative_blocked && (
                                            <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                                                blocked: {k.negative_reason}
                                            </span>
                                        )}
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
                                            {operationalCopy.remove}
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
