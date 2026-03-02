import React, { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Badge } from "./ui/badge";
import { Loader2, MapPin, Phone, Globe, Star, Mail, MessageCircle, Save } from "lucide-react";
import { api } from "@/services/api";

type Lead = {
    id?: string;
    name: string;
    address?: string;
    city?: string;
    phone?: string;
    website?: string;
    email?: string;
    telegram_url?: string;
    whatsapp_url?: string;
    messenger_links_json?: string[] | string;
    rating?: number;
    reviews_count?: number;
    source_url?: string;
    source_external_id?: string;
    google_id?: string;
    category?: string;
    location?: any;
    status: string;
    created_at?: string;
};

type SearchJob = {
    id: string;
    status: 'queued' | 'running' | 'completed' | 'failed';
    result_count: number;
    error_text?: string | null;
    results: Lead[];
};

type LeadFilters = {
    category: string;
    city: string;
    minRating: string;
    maxRating: string;
    minReviews: string;
    maxReviews: string;
    hasWebsite: string;
    hasPhone: string;
    hasEmail: string;
    hasMessengers: string;
};

const emptyFilters: LeadFilters = {
    category: '',
    city: '',
    minRating: '',
    maxRating: '',
    minReviews: '',
    maxReviews: '',
    hasWebsite: '',
    hasPhone: '',
    hasEmail: '',
    hasMessengers: '',
};

const shortlistApproved = 'shortlist_approved';
const shortlistRejected = 'shortlist_rejected';

const badgeVariantForStatus = (status: string) => {
    if (status === shortlistApproved) {
        return 'default';
    }
    if (status === shortlistRejected) {
        return 'destructive';
    }
    return 'secondary';
};

const statusLabel = (status: string) => {
    switch (status) {
        case shortlistApproved:
            return 'В shortlist';
        case shortlistRejected:
            return 'Отклонён';
        case 'new':
            return 'Новый';
        case 'contacted':
            return 'Контакт';
        case 'qualified':
            return 'Квалифицирован';
        case 'converted':
            return 'Конвертирован';
        case 'rejected':
            return 'Отклонён';
        default:
            return status || 'Без статуса';
    }
};

const normalizeBooleanFilter = (value: string) => {
    if (value === '') {
        return undefined;
    }
    return value === 'yes';
};

const extractHasMessengers = (lead: Lead) => {
    const rawLinks = lead.messenger_links_json;
    const parsedLinks = Array.isArray(rawLinks)
        ? rawLinks
        : typeof rawLinks === 'string' && rawLinks.trim()
            ? (() => {
                try {
                    return JSON.parse(rawLinks);
                } catch {
                    return [];
                }
            })()
            : [];
    return Boolean(lead.telegram_url || lead.whatsapp_url || (Array.isArray(parsedLinks) && parsedLinks.length > 0));
};

const ContactStack: React.FC<{ lead: Lead }> = ({ lead }) => (
    <div className="flex flex-col gap-1 text-sm">
        {lead.phone && <span className="flex items-center gap-1"><Phone className="h-3 w-3" /> {lead.phone}</span>}
        {lead.email && <span className="flex items-center gap-1"><Mail className="h-3 w-3" /> {lead.email}</span>}
        {lead.website && (
            <span className="flex items-center gap-1">
                <Globe className="h-3 w-3" />
                <a href={lead.website} target="_blank" rel="noreferrer" className="underline truncate max-w-[180px]">{lead.website}</a>
            </span>
        )}
        {extractHasMessengers(lead) && (
            <span className="flex items-center gap-1 text-emerald-700">
                <MessageCircle className="h-3 w-3" />
                Мессенджеры найдены
            </span>
        )}
    </div>
);

export const ProspectingManagement: React.FC = () => {
    const [query, setQuery] = useState('');
    const [location, setLocation] = useState('');
    const [limit, setLimit] = useState(20);
    const [results, setResults] = useState<Lead[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState<Record<string, boolean>>({});
    const [savedLeads, setSavedLeads] = useState<Lead[]>([]);
    const [loadingLeads, setLoadingLeads] = useState(false);
    const [searchJobId, setSearchJobId] = useState<string | null>(null);
    const [searchJob, setSearchJob] = useState<SearchJob | null>(null);
    const [filters, setFilters] = useState<LeadFilters>(emptyFilters);
    const [leadTab, setLeadTab] = useState<'candidates' | 'shortlist' | 'rejected'>('candidates');
    const [shortlistLoading, setShortlistLoading] = useState<Record<string, string>>({});

    const activeFilters = useMemo(() => {
        const params: Record<string, string> = {};
        if (filters.category.trim()) params.category = filters.category.trim();
        if (filters.city.trim()) params.city = filters.city.trim();
        if (filters.minRating.trim()) params.min_rating = filters.minRating.trim();
        if (filters.maxRating.trim()) params.max_rating = filters.maxRating.trim();
        if (filters.minReviews.trim()) params.min_reviews = filters.minReviews.trim();
        if (filters.maxReviews.trim()) params.max_reviews = filters.maxReviews.trim();

        const hasWebsite = normalizeBooleanFilter(filters.hasWebsite);
        if (hasWebsite !== undefined) params.has_website = String(hasWebsite);
        const hasPhone = normalizeBooleanFilter(filters.hasPhone);
        if (hasPhone !== undefined) params.has_phone = String(hasPhone);
        const hasEmail = normalizeBooleanFilter(filters.hasEmail);
        if (hasEmail !== undefined) params.has_email = String(hasEmail);
        const hasMessengers = normalizeBooleanFilter(filters.hasMessengers);
        if (hasMessengers !== undefined) params.has_messengers = String(hasMessengers);

        return params;
    }, [filters]);

    useEffect(() => {
        fetchSavedLeads();
    }, [activeFilters]);

    useEffect(() => {
        if (!searchJobId) {
            return;
        }

        let cancelled = false;
        const poll = async () => {
            try {
                const response = await api.get(`/admin/prospecting/search-job/${searchJobId}`);
                const job = response.data?.job as SearchJob;
                if (cancelled || !job) {
                    return;
                }
                setSearchJob(job);
                if (job.status === 'completed') {
                    const newResults = (job.results || []).map((r: any) => ({ ...r, status: r.status || 'new' }));
                    setResults(newResults);
                    setLoading(false);
                    return;
                }
                if (job.status === 'failed') {
                    setLoading(false);
                    return;
                }
                window.setTimeout(poll, 2000);
            } catch (error) {
                console.error('Error polling prospecting job:', error);
                if (!cancelled) {
                    setLoading(false);
                }
            }
        };

        poll();

        return () => {
            cancelled = true;
        };
    }, [searchJobId]);

    const fetchSavedLeads = async () => {
        setLoadingLeads(true);
        try {
            const response = await api.get('/admin/prospecting/leads', { params: activeFilters });
            setSavedLeads(response.data.leads || []);
        } catch (error) {
            console.error('Error fetching leads:', error);
        } finally {
            setLoadingLeads(false);
        }
    };

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query || !location) return;

        setLoading(true);
        setSearchJob(null);
        setSearchJobId(null);
        try {
            const response = await api.post('/admin/prospecting/search', {
                query,
                location,
                limit: Number(limit)
            });
            setResults([]);
            setSearchJobId(response.data.job_id);
        } catch (error) {
            console.error('Error searching:', error);
            alert('Ошибка поиска. Проверьте консоль.');
            setLoading(false);
        }
    };

    const saveLead = async (lead: Lead) => {
        const key = lead.source_external_id || lead.google_id || lead.name;
        setSaving(prev => ({ ...prev, [key]: true }));
        try {
            await api.post('/admin/prospecting/save', { lead });
            await fetchSavedLeads();
        } catch (error) {
            console.error('Error saving lead:', error);
        } finally {
            setSaving(prev => ({ ...prev, [key]: false }));
        }
    };

    const reviewShortlist = async (leadId: string, decision: 'approved' | 'rejected') => {
        setShortlistLoading(prev => ({ ...prev, [leadId]: decision }));
        try {
            await api.post(`/admin/prospecting/lead/${leadId}/shortlist`, { decision });
            await fetchSavedLeads();
        } catch (error) {
            console.error('Error updating shortlist:', error);
        } finally {
            setShortlistLoading(prev => {
                const next = { ...prev };
                delete next[leadId];
                return next;
            });
        }
    };

    const resetFilters = () => setFilters(emptyFilters);

    const shortlistLeads = useMemo(
        () => savedLeads.filter((lead) => lead.status === shortlistApproved),
        [savedLeads]
    );
    const rejectedLeads = useMemo(
        () => savedLeads.filter((lead) => lead.status === shortlistRejected),
        [savedLeads]
    );
    const candidateLeads = useMemo(
        () => savedLeads.filter((lead) => lead.status !== shortlistApproved && lead.status !== shortlistRejected),
        [savedLeads]
    );

    const visibleLeads = leadTab === 'shortlist'
        ? shortlistLeads
        : leadTab === 'rejected'
            ? rejectedLeads
            : candidateLeads;

    const renderLeadRow = (lead: Lead) => {
        const isBusy = Boolean(lead.id && shortlistLoading[lead.id]);
        const busyDecision = lead.id ? shortlistLoading[lead.id] : '';

        return (
            <TableRow key={lead.id}>
                <TableCell className="font-medium min-w-[260px]">
                    <div>{lead.name}</div>
                    <div className="text-xs text-muted-foreground">{lead.category || 'Без категории'}</div>
                    {lead.source_url && (
                        <a href={lead.source_url} target="_blank" rel="noreferrer" className="text-xs text-blue-500 underline">
                            Открыть в Яндекс Картах
                        </a>
                    )}
                </TableCell>
                <TableCell className="min-w-[220px]">
                    <div className="flex items-center gap-1 text-sm">
                        <MapPin className="h-3 w-3" />
                        <span className="truncate" title={lead.address}>{lead.address || lead.city || '-'}</span>
                    </div>
                </TableCell>
                <TableCell className="min-w-[220px]">
                    <ContactStack lead={lead} />
                </TableCell>
                <TableCell className="min-w-[120px]">
                    <div className="space-y-1 text-sm">
                        <div className="flex items-center gap-1">
                            <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                            <span>{lead.rating ?? '-'}</span>
                        </div>
                        <div className="text-muted-foreground">Отзывы: {lead.reviews_count ?? 0}</div>
                    </div>
                </TableCell>
                <TableCell className="min-w-[120px]">
                    <Badge variant={badgeVariantForStatus(lead.status)}>{statusLabel(lead.status)}</Badge>
                </TableCell>
                <TableCell className="min-w-[220px]">
                    <div className="flex flex-wrap gap-2">
                        {leadTab !== 'shortlist' && leadTab !== 'rejected' && lead.id && (
                            <>
                                <Button
                                    size="sm"
                                    onClick={() => reviewShortlist(lead.id!, 'approved')}
                                    disabled={isBusy}
                                >
                                    {busyDecision === 'approved' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                    В shortlist
                                </Button>
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => reviewShortlist(lead.id!, 'rejected')}
                                    disabled={isBusy}
                                >
                                    {busyDecision === 'rejected' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                    Отклонить
                                </Button>
                            </>
                        )}
                        {leadTab === 'shortlist' && lead.id && (
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => reviewShortlist(lead.id!, 'rejected')}
                                disabled={isBusy}
                            >
                                {busyDecision === 'rejected' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                Убрать
                            </Button>
                        )}
                        {leadTab === 'rejected' && lead.id && (
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => reviewShortlist(lead.id!, 'approved')}
                                disabled={isBusy}
                            >
                                {busyDecision === 'approved' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                Вернуть
                            </Button>
                        )}
                    </div>
                </TableCell>
            </TableRow>
        );
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Поиск клиентов</h2>
                    <p className="text-muted-foreground">
                        Yandex-first поиск потенциальных клиентов через Apify с ручным shortlist-отбором.
                    </p>
                </div>
            </div>

            <Tabs defaultValue="search" className="w-full">
                <TabsList>
                    <TabsTrigger value="search">Поиск</TabsTrigger>
                    <TabsTrigger value="leads">Кандидаты и shortlist ({savedLeads.length})</TabsTrigger>
                </TabsList>

                <TabsContent value="search" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>Источники и сбор</CardTitle>
                            <CardDescription>Поиск компаний в Яндекс Картах через Apify actor и сохранение в лиды.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <form onSubmit={handleSearch} className="flex flex-wrap gap-4 items-end">
                                <div className="grid w-full max-w-sm items-center gap-1.5">
                                    <label htmlFor="query">Категория / запрос</label>
                                    <Input
                                        type="text"
                                        id="query"
                                        placeholder="например: салон красоты"
                                        value={query}
                                        onChange={(e) => setQuery(e.target.value)}
                                        required
                                    />
                                </div>
                                <div className="grid w-full max-w-sm items-center gap-1.5">
                                    <label htmlFor="location">Город</label>
                                    <Input
                                        type="text"
                                        id="location"
                                        placeholder="например: Санкт-Петербург"
                                        value={location}
                                        onChange={(e) => setLocation(e.target.value)}
                                        required
                                    />
                                </div>
                                <div className="grid w-24 items-center gap-1.5">
                                    <label htmlFor="limit">Лимит</label>
                                    <Input
                                        type="number"
                                        id="limit"
                                        value={limit}
                                        onChange={(e) => setLimit(Number(e.target.value))}
                                        min={1}
                                        max={200}
                                    />
                                </div>
                                <Button type="submit" disabled={loading}>
                                    {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                    Запустить поиск
                                </Button>
                            </form>
                            {searchJob && (
                                <div className="mt-4 rounded-lg border border-border bg-muted/30 p-3 text-sm">
                                    <div className="font-medium">
                                        Поиск: {searchJob.status === 'queued' ? 'в очереди' :
                                            searchJob.status === 'running' ? 'выполняется' :
                                            searchJob.status === 'completed' ? 'завершён' : 'ошибка'}
                                    </div>
                                    <div className="text-muted-foreground">Найдено: {searchJob.result_count || 0}</div>
                                    {searchJob.error_text && <div className="mt-2 text-red-600">{searchJob.error_text}</div>}
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {results.length > 0 && (
                        <Card>
                            <CardHeader>
                                <CardTitle>Найденные компании ({results.length})</CardTitle>
                                <CardDescription>На этом шаге вы сохраняете только релевантные компании в базу кандидатов.</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Компания</TableHead>
                                            <TableHead>Адрес</TableHead>
                                            <TableHead>Контакты</TableHead>
                                            <TableHead>Рейтинг</TableHead>
                                            <TableHead>Действие</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {results.map((lead, index) => {
                                            const isSaved = savedLeads.some((saved) =>
                                                (saved.source_external_id && saved.source_external_id === lead.source_external_id) ||
                                                (saved.google_id && saved.google_id === lead.google_id)
                                            );
                                            const key = lead.source_external_id || lead.google_id || `${lead.name}-${index}`;
                                            return (
                                                <TableRow key={key}>
                                                    <TableCell className="font-medium min-w-[260px]">
                                                        <div>{lead.name}</div>
                                                        <div className="text-xs text-muted-foreground">{lead.category || 'Без категории'}</div>
                                                    </TableCell>
                                                    <TableCell className="min-w-[220px]">
                                                        <div className="flex items-center gap-1 text-sm">
                                                            <MapPin className="h-3 w-3" />
                                                            <span className="truncate" title={lead.address}>{lead.address || lead.city || '-'}</span>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell className="min-w-[220px]">
                                                        <ContactStack lead={lead} />
                                                    </TableCell>
                                                    <TableCell className="min-w-[120px]">
                                                        <div className="flex items-center gap-1">
                                                            <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                                                            {lead.rating ?? '-'}
                                                            <span className="text-muted-foreground">({lead.reviews_count ?? 0})</span>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell className="min-w-[140px]">
                                                        <Button
                                                            size="sm"
                                                            variant={isSaved ? "secondary" : "default"}
                                                            onClick={() => saveLead(lead)}
                                                            disabled={isSaved || saving[key]}
                                                        >
                                                            {saving[key] ? <Loader2 className="mr-2 h-3 w-3 animate-spin" /> : <Save className="mr-2 h-3 w-3" />}
                                                            {isSaved ? "Сохранён" : "Сохранить"}
                                                        </Button>
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })}
                                    </TableBody>
                                </Table>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>

                <TabsContent value="leads" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>Фильтры кандидатов</CardTitle>
                            <CardDescription>Подготовьте shortlist: отберите релевантные компании и отсекайте лишние.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
                                <Input placeholder="Категория" value={filters.category} onChange={(e) => setFilters(prev => ({ ...prev, category: e.target.value }))} />
                                <Input placeholder="Город" value={filters.city} onChange={(e) => setFilters(prev => ({ ...prev, city: e.target.value }))} />
                                <Input placeholder="Мин. рейтинг" type="number" min="0" max="5" step="0.1" value={filters.minRating} onChange={(e) => setFilters(prev => ({ ...prev, minRating: e.target.value }))} />
                                <Input placeholder="Макс. рейтинг" type="number" min="0" max="5" step="0.1" value={filters.maxRating} onChange={(e) => setFilters(prev => ({ ...prev, maxRating: e.target.value }))} />
                                <Input placeholder="Мин. отзывов" type="number" min="0" value={filters.minReviews} onChange={(e) => setFilters(prev => ({ ...prev, minReviews: e.target.value }))} />
                                <Input placeholder="Макс. отзывов" type="number" min="0" value={filters.maxReviews} onChange={(e) => setFilters(prev => ({ ...prev, maxReviews: e.target.value }))} />
                                <select className="border rounded-md px-3 py-2 bg-background text-sm" value={filters.hasWebsite} onChange={(e) => setFilters(prev => ({ ...prev, hasWebsite: e.target.value }))}>
                                    <option value="">Сайт: любой</option>
                                    <option value="yes">Есть сайт</option>
                                    <option value="no">Нет сайта</option>
                                </select>
                                <select className="border rounded-md px-3 py-2 bg-background text-sm" value={filters.hasPhone} onChange={(e) => setFilters(prev => ({ ...prev, hasPhone: e.target.value }))}>
                                    <option value="">Телефон: любой</option>
                                    <option value="yes">Есть телефон</option>
                                    <option value="no">Нет телефона</option>
                                </select>
                                <select className="border rounded-md px-3 py-2 bg-background text-sm" value={filters.hasEmail} onChange={(e) => setFilters(prev => ({ ...prev, hasEmail: e.target.value }))}>
                                    <option value="">Email: любой</option>
                                    <option value="yes">Есть email</option>
                                    <option value="no">Нет email</option>
                                </select>
                                <select className="border rounded-md px-3 py-2 bg-background text-sm" value={filters.hasMessengers} onChange={(e) => setFilters(prev => ({ ...prev, hasMessengers: e.target.value }))}>
                                    <option value="">Мессенджеры: любые</option>
                                    <option value="yes">Есть мессенджеры</option>
                                    <option value="no">Нет мессенджеров</option>
                                </select>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <Button variant="outline" onClick={resetFilters}>Сбросить фильтры</Button>
                                <Badge variant="secondary">Кандидаты: {candidateLeads.length}</Badge>
                                <Badge variant="default">Shortlist: {shortlistLeads.length}</Badge>
                                <Badge variant="destructive">Отклонено: {rejectedLeads.length}</Badge>
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Ручной shortlist</CardTitle>
                            <CardDescription>Первый ручной этап: подтверждайте только подходящие компании.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <Tabs value={leadTab} onValueChange={(value) => setLeadTab(value as 'candidates' | 'shortlist' | 'rejected')}>
                                <TabsList>
                                    <TabsTrigger value="candidates">Кандидаты ({candidateLeads.length})</TabsTrigger>
                                    <TabsTrigger value="shortlist">Shortlist ({shortlistLeads.length})</TabsTrigger>
                                    <TabsTrigger value="rejected">Отклонённые ({rejectedLeads.length})</TabsTrigger>
                                </TabsList>
                                <TabsContent value={leadTab} className="mt-4">
                                    {loadingLeads ? (
                                        <div className="flex justify-center p-8"><Loader2 className="h-8 w-8 animate-spin" /></div>
                                    ) : (
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Компания</TableHead>
                                                    <TableHead>Адрес</TableHead>
                                                    <TableHead>Контакты</TableHead>
                                                    <TableHead>Рейтинг</TableHead>
                                                    <TableHead>Статус</TableHead>
                                                    <TableHead>Действие</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {visibleLeads.map(renderLeadRow)}
                                                {visibleLeads.length === 0 && (
                                                    <TableRow>
                                                        <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                                                            Для текущего набора фильтров здесь пока нет лидов.
                                                        </TableCell>
                                                    </TableRow>
                                                )}
                                            </TableBody>
                                        </Table>
                                    )}
                                </TabsContent>
                            </Tabs>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
};

export default ProspectingManagement;
