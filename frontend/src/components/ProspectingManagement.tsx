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
    selected_channel?: string;
    location?: any;
    status: string;
    created_at?: string;
};

type SearchJob = {
    id: string;
    status: 'queued' | 'running' | 'completed' | 'failed';
    result_count: number;
    apify_status?: string | null;
    error_text?: string | null;
    results: Lead[];
};

type OutreachDraft = {
    id: string;
    lead_id: string;
    lead_name?: string;
    channel: string;
    status: string;
    generated_text: string;
    edited_text?: string;
    approved_text?: string;
    learning_note_json?: { note?: string } | null;
    created_at?: string;
};

type OutreachQueueItem = {
    id: string;
    batch_id: string;
    lead_id: string;
    draft_id: string;
    channel: string;
    delivery_status: string;
    provider_message_id?: string | null;
    error_text?: string | null;
    sent_at?: string | null;
    created_at?: string;
    updated_at?: string;
    lead_name?: string;
    approved_text?: string;
    generated_text?: string;
};

type OutreachBatch = {
    id: string;
    batch_date: string;
    daily_limit: number;
    status: string;
    created_by?: string | null;
    approved_by?: string | null;
    created_at?: string;
    updated_at?: string;
    items: OutreachQueueItem[];
};

type OutreachReaction = {
    id: string;
    queue_id: string;
    lead_id: string;
    raw_reply?: string | null;
    classified_outcome: string;
    confidence?: number | null;
    human_confirmed_outcome?: string | null;
    note?: string | null;
    created_at?: string;
    updated_at?: string;
    lead_name?: string;
    batch_id?: string;
    channel?: string;
    delivery_status?: string;
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
const selectedForOutreach = 'selected_for_outreach';
const channelSelected = 'channel_selected';

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
        case selectedForOutreach:
            return 'Выбран для контакта';
        case channelSelected:
            return 'Канал подтверждён';
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
    const [selectionLoading, setSelectionLoading] = useState<Record<string, string>>({});
    const [drafts, setDrafts] = useState<OutreachDraft[]>([]);
    const [loadingDrafts, setLoadingDrafts] = useState(false);
    const [draftBusy, setDraftBusy] = useState<Record<string, string>>({});
    const [draftEdits, setDraftEdits] = useState<Record<string, string>>({});
    const [sendReadyDrafts, setSendReadyDrafts] = useState<OutreachDraft[]>([]);
    const [sendBatches, setSendBatches] = useState<OutreachBatch[]>([]);
    const [sendDailyCap, setSendDailyCap] = useState(10);
    const [loadingSendQueue, setLoadingSendQueue] = useState(false);
    const [sendQueueBusy, setSendQueueBusy] = useState<Record<string, string>>({});
    const [reactions, setReactions] = useState<OutreachReaction[]>([]);
    const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({});
    const [searchPollError, setSearchPollError] = useState<string | null>(null);

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
        fetchDrafts();
    }, []);

    useEffect(() => {
        fetchSendQueue();
    }, []);

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
                setSearchPollError(null);
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
                    setSearchPollError('Связь с сервером прервалась. Повторяем опрос...');
                    window.setTimeout(poll, 3000);
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

    const fetchDrafts = async () => {
        setLoadingDrafts(true);
        try {
            const response = await api.get('/admin/prospecting/drafts');
            const items = response.data?.drafts || [];
            setDrafts(items);
            setDraftEdits((prev) => {
                const next = { ...prev };
                for (const draft of items) {
                    if (!(draft.id in next)) {
                        next[draft.id] = draft.approved_text || draft.edited_text || draft.generated_text || '';
                    }
                }
                return next;
            });
        } catch (error) {
            console.error('Error fetching drafts:', error);
        } finally {
            setLoadingDrafts(false);
        }
    };

    const fetchSendQueue = async () => {
        setLoadingSendQueue(true);
        try {
            const response = await api.get('/admin/prospecting/send-batches');
            setSendReadyDrafts(response.data?.ready_drafts || []);
            setSendBatches(response.data?.batches || []);
            setReactions(response.data?.reactions || []);
            setSendDailyCap(response.data?.daily_cap || 10);
        } catch (error) {
            console.error('Error fetching send queue:', error);
        } finally {
            setLoadingSendQueue(false);
        }
    };

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query || !location) return;

        setLoading(true);
        setSearchJob(null);
        setSearchJobId(null);
        setSearchPollError(null);
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

    const selectForOutreach = async (leadId: string) => {
        setSelectionLoading(prev => ({ ...prev, [leadId]: 'select' }));
        try {
            await api.post(`/admin/prospecting/lead/${leadId}/select`);
            await fetchSavedLeads();
        } catch (error) {
            console.error('Error selecting lead for outreach:', error);
        } finally {
            setSelectionLoading(prev => {
                const next = { ...prev };
                delete next[leadId];
                return next;
            });
        }
    };

    const chooseChannel = async (leadId: string, channel: 'telegram' | 'whatsapp' | 'email' | 'manual') => {
        setSelectionLoading(prev => ({ ...prev, [leadId]: channel }));
        try {
            await api.post(`/admin/prospecting/lead/${leadId}/channel`, { channel });
            await fetchSavedLeads();
        } catch (error) {
            console.error('Error selecting channel:', error);
        } finally {
            setSelectionLoading(prev => {
                const next = { ...prev };
                delete next[leadId];
                return next;
            });
        }
    };

    const generateDraft = async (leadId: string) => {
        setDraftBusy(prev => ({ ...prev, [leadId]: 'generate' }));
        try {
            await api.post(`/admin/prospecting/lead/${leadId}/draft-generate`);
            await Promise.all([fetchSavedLeads(), fetchDrafts(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error generating draft:', error);
        } finally {
            setDraftBusy(prev => {
                const next = { ...prev };
                delete next[leadId];
                return next;
            });
        }
    };

    const approveDraft = async (draftId: string) => {
        const approvedText = (draftEdits[draftId] || '').trim();
        if (!approvedText) return;
        setDraftBusy(prev => ({ ...prev, [draftId]: 'approve' }));
        try {
            await api.post(`/admin/prospecting/drafts/${draftId}/approve`, {
                approved_text: approvedText,
            });
            await Promise.all([fetchDrafts(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error approving draft:', error);
        } finally {
            setDraftBusy(prev => {
                const next = { ...prev };
                delete next[draftId];
                return next;
            });
        }
    };

    const rejectDraft = async (draftId: string) => {
        setDraftBusy(prev => ({ ...prev, [draftId]: 'reject' }));
        try {
            await api.post(`/admin/prospecting/drafts/${draftId}/reject`);
            await Promise.all([fetchDrafts(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error rejecting draft:', error);
        } finally {
            setDraftBusy(prev => {
                const next = { ...prev };
                delete next[draftId];
                return next;
            });
        }
    };

    const createSendBatch = async () => {
        setSendQueueBusy(prev => ({ ...prev, create: 'create' }));
        try {
            await api.post('/admin/prospecting/send-batches', {});
            await Promise.all([fetchSavedLeads(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error creating outreach batch:', error);
        } finally {
            setSendQueueBusy(prev => {
                const next = { ...prev };
                delete next.create;
                return next;
            });
        }
    };

    const approveSendBatch = async (batchId: string) => {
        setSendQueueBusy(prev => ({ ...prev, [batchId]: 'approve' }));
        try {
            const response = await api.post(`/admin/prospecting/send-batches/${batchId}/approve`, {});
            await fetchSendQueue();
            const summary = response.data?.batch?.dispatch_summary;
            if (summary) {
                alert(`Отправка batch завершена: sent ${summary.sent}/${summary.total}, failed ${summary.failed}`);
            }
        } catch (error) {
            console.error('Error approving outreach batch:', error);
        } finally {
            setSendQueueBusy(prev => {
                const next = { ...prev };
                delete next[batchId];
                return next;
            });
        }
    };

    const markDelivery = async (queueId: string, deliveryStatus: 'sent' | 'failed') => {
        setSendQueueBusy(prev => ({ ...prev, [queueId]: deliveryStatus }));
        try {
            await api.post(`/admin/prospecting/send-queue/${queueId}/delivery`, {
                delivery_status: deliveryStatus,
                error_text: deliveryStatus === 'failed' ? 'Manual delivery failure' : undefined,
            });
            await Promise.all([fetchSavedLeads(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error updating delivery status:', error);
        } finally {
            setSendQueueBusy(prev => {
                const next = { ...prev };
                delete next[queueId];
                return next;
            });
        }
    };

    const recordReaction = async (queueId: string, outcome?: 'positive' | 'question' | 'no_response' | 'hard_no') => {
        setSendQueueBusy(prev => ({ ...prev, [queueId]: `reaction:${outcome || 'auto'}` }));
        try {
            await api.post(`/admin/prospecting/send-queue/${queueId}/reaction`, {
                raw_reply: (replyDrafts[queueId] || '').trim(),
                outcome,
            });
            await Promise.all([fetchSavedLeads(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error recording reaction:', error);
        } finally {
            setSendQueueBusy(prev => {
                const next = { ...prev };
                delete next[queueId];
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
        () => savedLeads.filter((lead) => ![shortlistApproved, shortlistRejected, selectedForOutreach, channelSelected].includes(lead.status)),
        [savedLeads]
    );
    const outreachLeads = useMemo(
        () => savedLeads.filter((lead) => lead.status === selectedForOutreach || lead.status === channelSelected),
        [savedLeads]
    );
    const draftReadyLeads = useMemo(
        () => savedLeads.filter((lead) => lead.status === channelSelected),
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
                    <TabsTrigger value="outreach">Отбор для контакта ({outreachLeads.length})</TabsTrigger>
                    <TabsTrigger value="drafts">Черновики ({drafts.length})</TabsTrigger>
                    <TabsTrigger value="queue">Очередь отправки ({sendBatches.length})</TabsTrigger>
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
                                    {searchJob.status === 'running' && searchJob.apify_status === 'START_PENDING' && (
                                        <div className="mt-2 text-muted-foreground">
                                            Ожидаем подтверждение запуска от Apify. Это может занять больше обычного.
                                        </div>
                                    )}
                                    {searchJob.status === 'completed' && (searchJob.result_count || 0) === 0 && (
                                        <div className="mt-2 text-muted-foreground">
                                            Поиск завершён, но actor не вернул компаний по этому запросу. Попробуйте сузить категорию или изменить формулировку запроса.
                                        </div>
                                    )}
                                    {searchPollError && searchJob.status === 'running' && (
                                        <div className="mt-2 text-amber-600">{searchPollError}</div>
                                    )}
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

                <TabsContent value="outreach" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>Отбор для контакта</CardTitle>
                            <CardDescription>
                                Переводите лиды из shortlist в контактную работу и вручную подтверждайте первый канал касания.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="rounded-lg border p-4">
                                <div className="mb-3 flex items-center justify-between gap-3">
                                    <div>
                                        <h3 className="font-semibold">Shortlist, готовые к выбору</h3>
                                        <p className="text-sm text-muted-foreground">Следующий шаг после shortlist: пометить лид как выбранный для аутрича.</p>
                                    </div>
                                    <Badge variant="secondary">{shortlistLeads.length}</Badge>
                                </div>
                                <div className="space-y-3">
                                    {shortlistLeads.length === 0 && (
                                        <div className="text-sm text-muted-foreground">Нет лидов в shortlist для следующего шага.</div>
                                    )}
                                    {shortlistLeads.map((lead) => {
                                        const pending = selectionLoading[lead.id || ''];
                                        return (
                                            <div key={lead.id} className="flex flex-col gap-3 rounded-md border p-3 md:flex-row md:items-center md:justify-between">
                                                <div className="space-y-1">
                                                    <div className="font-medium">{lead.name}</div>
                                                    <div className="text-sm text-muted-foreground">{lead.category || 'Без категории'} · {lead.address || lead.city || 'Адрес не указан'}</div>
                                                    <ContactStack lead={lead} />
                                                </div>
                                                <Button onClick={() => lead.id && selectForOutreach(lead.id)} disabled={!lead.id || Boolean(pending)}>
                                                    {pending === 'select' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                                    Выбрать для контакта
                                                </Button>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>

                            <div className="rounded-lg border p-4">
                                <div className="mb-3 flex items-center justify-between gap-3">
                                    <div>
                                        <h3 className="font-semibold">Выбранные для аутрича</h3>
                                        <p className="text-sm text-muted-foreground">Подтвердите первый канал: Telegram, WhatsApp, Email или ручное касание.</p>
                                    </div>
                                    <Badge variant="secondary">{outreachLeads.length}</Badge>
                                </div>
                                <div className="space-y-3">
                                    {outreachLeads.length === 0 && (
                                        <div className="text-sm text-muted-foreground">Пока нет выбранных лидов для контакта.</div>
                                    )}
                                    {outreachLeads.map((lead) => {
                                        const pending = selectionLoading[lead.id || ''];
                                        return (
                                            <div key={lead.id} className="rounded-md border p-3">
                                                <div className="mb-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                                                    <div className="space-y-1">
                                                        <div className="font-medium">{lead.name}</div>
                                                        <div className="text-sm text-muted-foreground">
                                                            {lead.address || lead.city || 'Адрес не указан'}
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            <Badge variant={badgeVariantForStatus(lead.status)}>{statusLabel(lead.status)}</Badge>
                                                            {lead.selected_channel && (
                                                                <Badge variant="outline">Канал: {lead.selected_channel}</Badge>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <ContactStack lead={lead} />
                                                </div>
                                                <div className="flex flex-wrap gap-2">
                                                    {(['telegram', 'whatsapp', 'email', 'manual'] as const).map((channel) => (
                                                        <Button
                                                            key={channel}
                                                            size="sm"
                                                            variant={lead.selected_channel === channel ? 'default' : 'outline'}
                                                            onClick={() => lead.id && chooseChannel(lead.id, channel)}
                                                            disabled={!lead.id || Boolean(pending)}
                                                        >
                                                            {pending === channel && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                                            {channel === 'telegram' ? 'Telegram' : channel === 'whatsapp' ? 'WhatsApp' : channel === 'email' ? 'Email' : 'Manual'}
                                                        </Button>
                                                    ))}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="drafts" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>Черновики первого сообщения</CardTitle>
                            <CardDescription>
                                Для лидов в `channel_selected` генерируйте первый текст, редактируйте его и вручную утверждайте.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="rounded-lg border p-4">
                                <div className="mb-3 flex items-center justify-between gap-3">
                                    <div>
                                        <h3 className="font-semibold">Готовые к генерации</h3>
                                        <p className="text-sm text-muted-foreground">Только лиды с подтверждённым каналом.</p>
                                    </div>
                                    <Badge variant="secondary">{draftReadyLeads.length}</Badge>
                                </div>
                                <div className="space-y-3">
                                    {draftReadyLeads.length === 0 && (
                                        <div className="text-sm text-muted-foreground">Пока нет лидов со статусом channel_selected.</div>
                                    )}
                                    {draftReadyLeads.map((lead) => {
                                        const pending = draftBusy[lead.id || ''];
                                        return (
                                            <div key={lead.id} className="flex flex-col gap-3 rounded-md border p-3 md:flex-row md:items-center md:justify-between">
                                                <div className="space-y-1">
                                                    <div className="font-medium">{lead.name}</div>
                                                    <div className="text-sm text-muted-foreground">
                                                        Канал: {lead.selected_channel || 'не подтверждён'}
                                                    </div>
                                                </div>
                                                <Button onClick={() => lead.id && generateDraft(lead.id)} disabled={!lead.id || Boolean(pending)}>
                                                    {pending === 'generate' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                                    Сгенерировать черновик
                                                </Button>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>

                            <div className="rounded-lg border p-4">
                                <div className="mb-3 flex items-center justify-between gap-3">
                                    <div>
                                        <h3 className="font-semibold">Список черновиков</h3>
                                        <p className="text-sm text-muted-foreground">Ваши правки после утверждения сохраняются как learning examples.</p>
                                    </div>
                                    <Badge variant="secondary">{drafts.length}</Badge>
                                </div>
                                <div className="space-y-4">
                                    {loadingDrafts && (
                                        <div className="flex justify-center p-8"><Loader2 className="h-8 w-8 animate-spin" /></div>
                                    )}
                                    {!loadingDrafts && drafts.length === 0 && (
                                        <div className="text-sm text-muted-foreground">Черновиков пока нет.</div>
                                    )}
                                    {drafts.map((draft) => {
                                        const pending = draftBusy[draft.id];
                                        return (
                                            <div key={draft.id} className="rounded-md border p-4 space-y-3">
                                                <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                                                    <div>
                                                        <div className="font-medium">{draft.lead_name || draft.lead_id}</div>
                                                        <div className="text-sm text-muted-foreground">
                                                            Канал: {draft.channel} · Статус: {draft.status}
                                                        </div>
                                                    </div>
                                                    <Badge variant={draft.status === 'approved' ? 'default' : draft.status === 'rejected' ? 'destructive' : 'secondary'}>
                                                        {draft.status}
                                                    </Badge>
                                                </div>
                                                <div className="rounded-md bg-muted/30 p-3 text-sm whitespace-pre-wrap">
                                                    {draft.generated_text}
                                                </div>
                                                <textarea
                                                    className="min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                                                    value={draftEdits[draft.id] ?? ''}
                                                    onChange={(e) => setDraftEdits(prev => ({ ...prev, [draft.id]: e.target.value }))}
                                                />
                                                <div className="flex flex-wrap gap-2">
                                                    <Button onClick={() => approveDraft(draft.id)} disabled={Boolean(pending)}>
                                                        {pending === 'approve' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                                        Утвердить
                                                    </Button>
                                                    <Button variant="outline" onClick={() => rejectDraft(draft.id)} disabled={Boolean(pending)}>
                                                        {pending === 'reject' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                                        Отклонить
                                                    </Button>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="queue" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>Очередь отправки</CardTitle>
                            <CardDescription>
                                Дневная capped-пачка: не более {sendDailyCap} сообщений. Сначала собираете batch, затем вручную подтверждаете его.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="rounded-lg border p-4">
                                <div className="mb-3 flex items-center justify-between gap-3">
                                    <div>
                                        <h3 className="font-semibold">Готовые к постановке в очередь</h3>
                                        <p className="text-sm text-muted-foreground">Используются только утверждённые черновики, которые ещё не попали в send queue.</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Badge variant="secondary">{sendReadyDrafts.length}</Badge>
                                        <Button onClick={createSendBatch} disabled={loadingSendQueue || Boolean(sendQueueBusy.create) || sendReadyDrafts.length === 0}>
                                            {(loadingSendQueue || sendQueueBusy.create === 'create') && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                            Собрать batch (до {sendDailyCap})
                                        </Button>
                                    </div>
                                </div>
                                <div className="space-y-3">
                                    {loadingSendQueue && (
                                        <div className="flex justify-center p-6"><Loader2 className="h-8 w-8 animate-spin" /></div>
                                    )}
                                    {!loadingSendQueue && sendReadyDrafts.length === 0 && (
                                        <div className="text-sm text-muted-foreground">Нет утверждённых черновиков, готовых к постановке в очередь.</div>
                                    )}
                                    {sendReadyDrafts.slice(0, sendDailyCap).map((draft) => (
                                        <div key={draft.id} className="rounded-md border p-3">
                                            <div className="mb-2 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                                                <div>
                                                    <div className="font-medium">{draft.lead_name || draft.lead_id}</div>
                                                    <div className="text-sm text-muted-foreground">
                                                        Канал: {draft.channel} · Черновик утверждён
                                                    </div>
                                                </div>
                                                <Badge variant="default">Готов к queue</Badge>
                                            </div>
                                            <div className="rounded-md bg-muted/30 p-3 text-sm whitespace-pre-wrap">
                                                {draft.approved_text || draft.edited_text || draft.generated_text}
                                            </div>
                                        </div>
                                    ))}
                                    {sendReadyDrafts.length > sendDailyCap && (
                                        <div className="text-xs text-muted-foreground">
                                            В batch попадут первые {sendDailyCap} черновиков по времени обновления. Остальные останутся ждать следующего дня.
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="rounded-lg border p-4">
                                <div className="mb-3 flex items-center justify-between gap-3">
                                    <div>
                                        <h3 className="font-semibold">Сформированные batch</h3>
                                        <p className="text-sm text-muted-foreground">После ручного подтверждения batch можно вручную отмечать доставку и фиксировать входящие реакции.</p>
                                    </div>
                                    <Badge variant="secondary">{sendBatches.length}</Badge>
                                </div>
                                <div className="space-y-4">
                                    {!loadingSendQueue && sendBatches.length === 0 && (
                                        <div className="text-sm text-muted-foreground">Пока нет сформированных batch.</div>
                                    )}
                                    {sendBatches.map((batch) => (
                                        <div key={batch.id} className="rounded-md border p-4 space-y-3">
                                            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                                                <div>
                                                    <div className="font-medium">Batch от {batch.batch_date}</div>
                                                    <div className="text-sm text-muted-foreground">
                                                        Элементов: {batch.items?.length || 0} · Лимит: {batch.daily_limit}
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <Badge variant={batch.status === 'approved' ? 'default' : 'secondary'}>
                                                        {batch.status === 'approved' ? 'Подтверждён' : 'Черновик'}
                                                    </Badge>
                                                    {batch.status === 'draft' && (
                                                        <Button
                                                            size="sm"
                                                            onClick={() => approveSendBatch(batch.id)}
                                                            disabled={Boolean(sendQueueBusy[batch.id])}
                                                        >
                                                            {sendQueueBusy[batch.id] === 'approve' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                                            Подтвердить и отправить
                                                        </Button>
                                                    )}
                                                </div>
                                            </div>
                                            <div className="space-y-2">
                                                {(batch.items || []).map((item) => (
                                                    <div key={item.id} className="rounded-md bg-muted/20 p-3 text-sm space-y-3">
                                                        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                                                            <div>
                                                                <div className="font-medium">{item.lead_name || item.lead_id}</div>
                                                                <div className="text-muted-foreground">
                                                                    Канал: {item.channel} · Доставка: {item.delivery_status}
                                                                </div>
                                                                {(item.latest_human_outcome || item.latest_outcome) && (
                                                                    <div className="text-xs text-emerald-700 mt-1">
                                                                        Последний outcome: {item.latest_human_outcome || item.latest_outcome}
                                                                    </div>
                                                                )}
                                                            </div>
                                                            <div className="flex flex-wrap gap-2">
                                                                <Button
                                                                    size="sm"
                                                                    variant={item.delivery_status === 'sent' ? 'default' : 'outline'}
                                                                    onClick={() => markDelivery(item.id, 'sent')}
                                                                    disabled={Boolean(sendQueueBusy[item.id])}
                                                                >
                                                                    {sendQueueBusy[item.id] === 'sent' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                                                    Отмечено как sent
                                                                </Button>
                                                                <Button
                                                                    size="sm"
                                                                    variant="outline"
                                                                    onClick={() => markDelivery(item.id, 'failed')}
                                                                    disabled={Boolean(sendQueueBusy[item.id])}
                                                                >
                                                                    {sendQueueBusy[item.id] === 'failed' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                                                    Пометить failed
                                                                </Button>
                                                            </div>
                                                        </div>
                                                        <div className="whitespace-pre-wrap">
                                                            {item.approved_text || item.generated_text || '—'}
                                                        </div>
                                                        {item.delivery_status !== 'failed' && (
                                                            <div className="space-y-2 rounded-md border p-3">
                                                                <div className="text-xs font-medium text-muted-foreground">Входящая реакция</div>
                                                                <textarea
                                                                    className="min-h-[90px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                                                                    placeholder="Вставьте ответ клиента или оставьте пустым для no_response"
                                                                    value={replyDrafts[item.id] ?? ''}
                                                                    onChange={(e) => setReplyDrafts(prev => ({ ...prev, [item.id]: e.target.value }))}
                                                                />
                                                                <div className="flex flex-wrap gap-2">
                                                                    <Button
                                                                        size="sm"
                                                                        onClick={() => recordReaction(item.id)}
                                                                        disabled={Boolean(sendQueueBusy[item.id])}
                                                                    >
                                                                        {sendQueueBusy[item.id] === 'reaction:auto' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                                                        Автоклассифицировать
                                                                    </Button>
                                                                    {(['positive', 'question', 'no_response', 'hard_no'] as const).map((outcome) => (
                                                                        <Button
                                                                            key={outcome}
                                                                            size="sm"
                                                                            variant="outline"
                                                                            onClick={() => recordReaction(item.id, outcome)}
                                                                            disabled={Boolean(sendQueueBusy[item.id])}
                                                                        >
                                                                            {sendQueueBusy[item.id] === `reaction:${outcome}` && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                                                            {outcome}
                                                                        </Button>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div className="rounded-lg border p-4">
                                <div className="mb-3 flex items-center justify-between gap-3">
                                    <div>
                                        <h3 className="font-semibold">Последние реакции</h3>
                                        <p className="text-sm text-muted-foreground">Базовая классификация outcome для первого supervised цикла.</p>
                                    </div>
                                    <Badge variant="secondary">{reactions.length}</Badge>
                                </div>
                                <div className="space-y-2">
                                    {!loadingSendQueue && reactions.length === 0 && (
                                        <div className="text-sm text-muted-foreground">Реакций пока нет.</div>
                                    )}
                                    {reactions.map((reaction) => (
                                        <div key={reaction.id} className="rounded-md border p-3 text-sm">
                                            <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
                                                <div className="font-medium">{reaction.lead_name || reaction.lead_id}</div>
                                                <Badge variant={reaction.human_confirmed_outcome === 'hard_no' ? 'destructive' : 'secondary'}>
                                                    {reaction.human_confirmed_outcome || reaction.classified_outcome}
                                                </Badge>
                                            </div>
                                            <div className="text-muted-foreground">
                                                Batch: {reaction.batch_id || '—'} · Канал: {reaction.channel || '—'} · Delivery: {reaction.delivery_status || '—'}
                                            </div>
                                            {reaction.raw_reply && (
                                                <div className="mt-2 whitespace-pre-wrap">
                                                    {reaction.raw_reply}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
};

export default ProspectingManagement;
