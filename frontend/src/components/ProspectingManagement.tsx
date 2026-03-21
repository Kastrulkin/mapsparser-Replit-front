import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Badge } from "./ui/badge";
import { Loader2, MapPin, Phone, Globe, Star, Mail, MessageCircle, Save } from "lucide-react";
import { api } from "@/services/api";
import LeadCardPreviewPanel, { type LeadCardPreview } from "./LeadCardPreviewPanel";

type Lead = {
    id?: string;
    business_id?: string;
    name: string;
    source?: string;
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
    latest_outcome?: string | null;
    latest_human_outcome?: string | null;
    latest_raw_reply?: string | null;
    latest_reaction_at?: string | null;
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
    source: string;
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
    source: '',
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

const workflowStatusLabel = (status: string) => {
    switch (status) {
        case 'new':
            return '1. Новый кандидат';
        case shortlistApproved:
            return '2. В shortlist';
        case selectedForOutreach:
            return '3. Выбран для контакта';
        case channelSelected:
            return '4. Канал подтверждён';
        case 'queued_for_send':
            return '5. В очереди на отправку';
        case 'sent':
            return '6. Отправлено';
        case 'delivered':
            return '6. Доставлено';
        case 'responded':
            return '7. Есть реакция';
        case 'converted':
            return '8. Конвертирован';
        case shortlistRejected:
        case 'rejected':
            return 'Отклонён';
        default:
            return statusLabel(status);
    }
};

const sourceLabel = (source?: string) => {
    switch (source) {
        case 'external_import':
            return 'Внешний импорт';
        case 'apify_yandex':
            return 'Apify Yandex';
        case 'apify_google':
            return 'Apify Google';
        case 'manual':
            return 'Ручной ввод';
        case 'openclaw':
            return 'OpenClaw';
        default:
            return source || 'Источник не указан';
    }
};

const normalizeBooleanFilter = (value: string) => {
    if (value === '') {
        return undefined;
    }
    return value === 'yes';
};

const formatLeadSource = (source?: string) => sourceLabel(source);

const formatLeadChannel = (channel?: string) => {
    switch (channel) {
        case 'telegram':
            return 'Telegram';
        case 'whatsapp':
            return 'WhatsApp';
        case 'email':
            return 'Email';
        case 'manual':
            return 'Manual';
        default:
            return channel || 'Канал не выбран';
    }
};

const reactionOutcomeOptions: Array<'positive' | 'question' | 'no_response' | 'hard_no'> = ['positive', 'question', 'no_response', 'hard_no'];

const getReactionClassifierSource = (note?: string | null) => {
    if (!note) {
        return null;
    }
    const match = note.match(/classifier=([a-z_]+)/i);
    return match?.[1]?.toLowerCase() || null;
};

const formatReactionClassifierSource = (source?: string | null) => {
    switch ((source || '').toLowerCase()) {
        case 'ai':
            return 'AI';
        case 'heuristic':
            return 'Fallback';
        default:
            return '—';
    }
};

const PLACEHOLDER_LEAD_VALUES = new Set([
    'name',
    'company',
    'company name',
    'title',
    'address',
    'phone',
    'email',
    'website',
    'rating',
    'reviews_count',
    'reviews',
    'status',
    'source',
    'category',
]);

const isPlaceholderLike = (value?: string | number | null) => {
    const normalized = String(value ?? '').trim().toLowerCase();
    if (!normalized) {
        return false;
    }
    return PLACEHOLDER_LEAD_VALUES.has(normalized);
};

const isDisplayableLead = (lead: Lead) => {
    if (!lead || isPlaceholderLike(lead.name)) {
        return false;
    }
    const meaningful = [lead.address, lead.phone, lead.website, lead.email, lead.source_url, lead.source_external_id];
    return meaningful.some((value) => value && !isPlaceholderLike(value));
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

const LeadMetaSummary: React.FC<{ lead: Lead; showChannel?: boolean }> = ({ lead, showChannel = false }) => (
    <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="text-[11px] font-normal">
                {formatLeadSource(lead.source)}
            </Badge>
            <Badge variant="secondary" className="text-[11px] font-normal">
                {lead.category || 'Без категории'}
            </Badge>
            {showChannel && (
                <Badge variant={lead.selected_channel ? 'default' : 'outline'} className="text-[11px] font-normal">
                    {formatLeadChannel(lead.selected_channel)}
                </Badge>
            )}
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <span className="inline-flex items-center gap-1">
                <MapPin className="h-3 w-3" />
                <span className="max-w-[420px] truncate" title={lead.address || lead.city || ''}>
                    {lead.address || lead.city || 'Адрес не указан'}
                </span>
            </span>
            <span className="inline-flex items-center gap-1">
                <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                {lead.rating ?? '-'}
                <span className="text-muted-foreground">({lead.reviews_count ?? 0})</span>
            </span>
        </div>
        <ContactStack lead={lead} />
    </div>
);

export const ProspectingManagement: React.FC = () => {
    const [query, setQuery] = useState('');
    const [location, setLocation] = useState('');
    const [searchSource, setSearchSource] = useState<'apify_yandex' | 'apify_2gis'>('apify_yandex');
    const [limit, setLimit] = useState(20);
    const [manualLeadUrl, setManualLeadUrl] = useState('');
    const [manualLeadName, setManualLeadName] = useState('');
    const [manualLeadCategory, setManualLeadCategory] = useState('');
    const [manualLeadBusy, setManualLeadBusy] = useState(false);
    const [activeTab, setActiveTab] = useState<'search' | 'leads' | 'outreach' | 'drafts' | 'queue'>('search');
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
    const [bulkParseBusy, setBulkParseBusy] = useState(false);
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
    const [reactionBusy, setReactionBusy] = useState<Record<string, string>>({});
    const [searchPollError, setSearchPollError] = useState<string | null>(null);
    const [importJson, setImportJson] = useState('');
    const [importBusy, setImportBusy] = useState(false);
    const [importResult, setImportResult] = useState<string | null>(null);
    const [draftChannelFilter, setDraftChannelFilter] = useState('');
    const [draftStatusFilter, setDraftStatusFilter] = useState('');
    const [queueChannelFilter, setQueueChannelFilter] = useState('');
    const [queueViewFilter, setQueueViewFilter] = useState<'all' | 'today' | 'attention'>('all');
    const [selectedDraftIds, setSelectedDraftIds] = useState<string[]>([]);
    const [selectedSendReadyDraftIds, setSelectedSendReadyDraftIds] = useState<string[]>([]);
    const [selectedShortlistLeadIds, setSelectedShortlistLeadIds] = useState<string[]>([]);
    const [selectedOutreachLeadIds, setSelectedOutreachLeadIds] = useState<string[]>([]);
    const [selectedQueueItemIds, setSelectedQueueItemIds] = useState<string[]>([]);
    const [bulkOutreachChannel, setBulkOutreachChannel] = useState<'telegram' | 'whatsapp' | 'email' | 'manual'>('telegram');
    const [previewLead, setPreviewLead] = useState<Lead | null>(null);
    const [previewSnapshot, setPreviewSnapshot] = useState<LeadCardPreview | null>(null);
    const [previewLoadingId, setPreviewLoadingId] = useState<string | null>(null);
    const [previewError, setPreviewError] = useState<string | null>(null);
    const [previewGenerateBusy, setPreviewGenerateBusy] = useState(false);
    const [previewAuditPageBusy, setPreviewAuditPageBusy] = useState(false);
    const [previewAuditPageUrl, setPreviewAuditPageUrl] = useState<string | null>(null);
    const [previewContactsBusy, setPreviewContactsBusy] = useState(false);
    const [previewParseBusy, setPreviewParseBusy] = useState(false);
    const [previewAutoRefreshing, setPreviewAutoRefreshing] = useState(false);

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
                source: searchSource,
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

    const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        const text = await file.text();
        setImportJson(text);
        setImportResult(null);
        e.target.value = '';
    };

    const importLeads = async () => {
        const raw = importJson.trim();
        if (!raw) return;

        setImportBusy(true);
        setImportResult(null);
        try {
            const parsed = JSON.parse(raw);
            const payload = Array.isArray(parsed) ? { items: parsed } : parsed;
            const response = await api.post('/admin/prospecting/import', payload);
            const importedCount = response.data?.imported_count || 0;
            setImportResult(`Импортировано лидов: ${importedCount}`);
            setImportJson('');
            await fetchSavedLeads();
        } catch (error: any) {
            console.error('Error importing leads:', error);
            const message = error?.message || 'Не удалось импортировать лиды';
            setImportResult(`Ошибка импорта: ${message}`);
        } finally {
            setImportBusy(false);
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

    const addLeadByUrl = async () => {
        const sourceUrl = manualLeadUrl.trim();
        if (!sourceUrl) return;

        let parsedUrl: URL | null = null;
        try {
            parsedUrl = new URL(sourceUrl);
        } catch {
            alert('Укажите корректную ссылку');
            return;
        }

        const orgIdFromPath = sourceUrl.match(/\/org\/(?:[^/]+\/)?(\d+)/)?.[1];
        const orgIdFromQuery = parsedUrl.searchParams.get('oid') || undefined;
        const sourceExternalId = orgIdFromPath || orgIdFromQuery || sourceUrl;
        const autoName = parsedUrl.hostname.replace(/^www\./, '') + (orgIdFromPath ? ` #${orgIdFromPath}` : '');
        const payloadLead: Lead = {
            name: manualLeadName.trim() || autoName || 'Лид из ссылки',
            source: 'manual',
            source_url: sourceUrl,
            source_external_id: sourceExternalId,
            category: manualLeadCategory.trim() || query.trim() || 'manual',
            city: location.trim() || undefined,
            status: 'new',
        };

        setManualLeadBusy(true);
        try {
            await api.post('/admin/prospecting/save', { lead: payloadLead });
            setManualLeadUrl('');
            setManualLeadName('');
            setManualLeadCategory('');
            await fetchSavedLeads();
        } catch (error) {
            console.error('Error saving manual lead by url:', error);
            alert('Не удалось добавить компанию по ссылке');
        } finally {
            setManualLeadBusy(false);
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

    const bulkSelectForOutreach = async () => {
        const leadIds = shortlistLeads
            .filter((lead) => lead.id && selectedShortlistLeadIds.includes(lead.id))
            .map((lead) => lead.id as string);
        if (leadIds.length === 0) return;

        setSelectionLoading((prev) => ({ ...prev, bulkSelect: 'select' }));
        try {
            await Promise.all(leadIds.map((leadId) => api.post(`/admin/prospecting/lead/${leadId}/select`)));
            setSelectedShortlistLeadIds([]);
            await fetchSavedLeads();
        } catch (error) {
            console.error('Error bulk selecting leads for outreach:', error);
        } finally {
            setSelectionLoading((prev) => {
                const next = { ...prev };
                delete next.bulkSelect;
                return next;
            });
        }
    };

    const bulkAssignOutreachChannel = async () => {
        const leadIds = outreachLeads
            .filter((lead) => lead.id && selectedOutreachLeadIds.includes(lead.id))
            .map((lead) => lead.id as string);
        if (leadIds.length === 0) return;

        setSelectionLoading((prev) => ({ ...prev, bulkChannel: bulkOutreachChannel }));
        try {
            await Promise.all(
                leadIds.map((leadId) => api.post(`/admin/prospecting/lead/${leadId}/channel`, { channel: bulkOutreachChannel }))
            );
            setSelectedOutreachLeadIds([]);
            await fetchSavedLeads();
        } catch (error) {
            console.error('Error bulk assigning outreach channel:', error);
        } finally {
            setSelectionLoading((prev) => {
                const next = { ...prev };
                delete next.bulkChannel;
                return next;
            });
        }
    };

    const deleteLeadEverywhere = async (leadId: string) => {
        setSelectionLoading((prev) => ({ ...prev, [leadId]: 'delete' }));
        try {
            await api.delete(`/admin/prospecting/lead/${leadId}`);
            setSelectedShortlistLeadIds((prev) => prev.filter((id) => id !== leadId));
            setSelectedOutreachLeadIds((prev) => prev.filter((id) => id !== leadId));
            if (previewLead?.id === leadId) {
                closeLeadPreview();
            }
            await Promise.all([fetchSavedLeads(), fetchDrafts(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error deleting lead:', error);
        } finally {
            setSelectionLoading((prev) => {
                const next = { ...prev };
                delete next[leadId];
                return next;
            });
        }
    };

    const bulkDeleteShortlistLeads = async () => {
        const leadIds = shortlistLeads
            .filter((lead) => lead.id && selectedShortlistLeadIds.includes(lead.id))
            .map((lead) => lead.id as string);
        if (leadIds.length === 0) return;
        setSelectionLoading((prev) => ({ ...prev, bulkDeleteShortlist: 'delete' }));
        try {
            await Promise.all(leadIds.map((leadId) => api.delete(`/admin/prospecting/lead/${leadId}`)));
            setSelectedShortlistLeadIds([]);
            await Promise.all([fetchSavedLeads(), fetchDrafts(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error bulk deleting shortlist leads:', error);
        } finally {
            setSelectionLoading((prev) => {
                const next = { ...prev };
                delete next.bulkDeleteShortlist;
                return next;
            });
        }
    };

    const bulkDeleteOutreachLeads = async () => {
        const leadIds = outreachLeads
            .filter((lead) => lead.id && selectedOutreachLeadIds.includes(lead.id))
            .map((lead) => lead.id as string);
        if (leadIds.length === 0) return;
        setSelectionLoading((prev) => ({ ...prev, bulkDeleteOutreach: 'delete' }));
        try {
            await Promise.all(leadIds.map((leadId) => api.delete(`/admin/prospecting/lead/${leadId}`)));
            setSelectedOutreachLeadIds([]);
            await Promise.all([fetchSavedLeads(), fetchDrafts(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error bulk deleting outreach leads:', error);
        } finally {
            setSelectionLoading((prev) => {
                const next = { ...prev };
                delete next.bulkDeleteOutreach;
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

    const saveDraftEdit = async (draftId: string) => {
        const editedText = (draftEdits[draftId] || '').trim();
        if (!editedText) return;
        setDraftBusy((prev) => ({ ...prev, [draftId]: 'save' }));
        try {
            await api.post(`/admin/prospecting/drafts/${draftId}/save`, {
                edited_text: editedText,
            });
            await fetchDrafts();
        } catch (error) {
            console.error('Error saving draft edit:', error);
        } finally {
            setDraftBusy((prev) => {
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

    const deleteDraft = async (draftId: string) => {
        setDraftBusy((prev) => ({ ...prev, [draftId]: 'delete' }));
        try {
            await api.delete(`/admin/prospecting/drafts/${draftId}`);
            setSelectedDraftIds((prev) => prev.filter((id) => id !== draftId));
            await Promise.all([fetchDrafts(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error deleting draft:', error);
        } finally {
            setDraftBusy((prev) => {
                const next = { ...prev };
                delete next[draftId];
                return next;
            });
        }
    };

    const deleteSelectedDrafts = async () => {
        const draftIds = filteredDrafts.filter((draft) => selectedDraftIds.includes(draft.id)).map((draft) => draft.id);
        if (draftIds.length === 0) return;
        setDraftBusy((prev) => ({ ...prev, bulkDelete: 'delete' }));
        try {
            await Promise.all(draftIds.map((draftId) => api.delete(`/admin/prospecting/drafts/${draftId}`)));
            setSelectedDraftIds([]);
            await Promise.all([fetchDrafts(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error bulk deleting drafts:', error);
        } finally {
            setDraftBusy((prev) => {
                const next = { ...prev };
                delete next.bulkDelete;
                return next;
            });
        }
    };

    const approveSelectedDrafts = async () => {
        const draftIds = filteredDrafts
            .filter((draft) => selectedDraftIds.includes(draft.id) && (draftEdits[draft.id] || '').trim())
            .map((draft) => draft.id);
        if (draftIds.length === 0) return;

        setDraftBusy((prev) => ({ ...prev, bulkApprove: 'approve' }));
        try {
            await Promise.all(
                draftIds.map((draftId) =>
                    api.post(`/admin/prospecting/drafts/${draftId}/approve`, {
                        approved_text: (draftEdits[draftId] || '').trim(),
                    })
                )
            );
            setSelectedDraftIds([]);
            await Promise.all([fetchDrafts(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error approving selected drafts:', error);
        } finally {
            setDraftBusy((prev) => {
                const next = { ...prev };
                delete next.bulkApprove;
                return next;
            });
        }
    };

    const rejectSelectedDrafts = async () => {
        const draftIds = filteredDrafts.filter((draft) => selectedDraftIds.includes(draft.id)).map((draft) => draft.id);
        if (draftIds.length === 0) return;

        setDraftBusy((prev) => ({ ...prev, bulkReject: 'reject' }));
        try {
            await Promise.all(draftIds.map((draftId) => api.post(`/admin/prospecting/drafts/${draftId}/reject`)));
            setSelectedDraftIds([]);
            await Promise.all([fetchDrafts(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error rejecting selected drafts:', error);
        } finally {
            setDraftBusy((prev) => {
                const next = { ...prev };
                delete next.bulkReject;
                return next;
            });
        }
    };

    const createSendBatch = async (draftIds?: string[]) => {
        setSendQueueBusy(prev => ({ ...prev, create: 'create' }));
        try {
            const payload = draftIds && draftIds.length > 0 ? { draft_ids: draftIds } : {};
            await api.post('/admin/prospecting/send-batches', payload);
            setSelectedSendReadyDraftIds([]);
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

    const deleteSendBatch = async (batchId: string) => {
        setSendQueueBusy((prev) => ({ ...prev, [batchId]: 'delete' }));
        try {
            await api.delete(`/admin/prospecting/send-batches/${batchId}`);
            setSelectedQueueItemIds((prev) => prev.filter((id) => !visibleQueueItems.some((item) => item.id === id && item.batch_id === batchId)));
            await Promise.all([fetchSavedLeads(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error deleting outreach batch:', error);
        } finally {
            setSendQueueBusy((prev) => {
                const next = { ...prev };
                delete next[batchId];
                return next;
            });
        }
    };

    const cleanupTestBatches = async () => {
        setSendQueueBusy((prev) => ({ ...prev, cleanupTest: 'cleanup' }));
        try {
            await api.post('/admin/prospecting/send-batches/cleanup-test', {});
            setSelectedQueueItemIds([]);
            await Promise.all([fetchSavedLeads(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error cleaning test batches:', error);
        } finally {
            setSendQueueBusy((prev) => {
                const next = { ...prev };
                delete next.cleanupTest;
                return next;
            });
        }
    };

    const markDelivery = async (queueId: string, deliveryStatus: 'sent' | 'delivered' | 'failed') => {
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

    const deleteQueueItem = async (queueId: string) => {
        setSendQueueBusy((prev) => ({ ...prev, [queueId]: 'delete' }));
        try {
            await api.delete(`/admin/prospecting/send-queue/${queueId}`);
            setSelectedQueueItemIds((prev) => prev.filter((id) => id !== queueId));
            await Promise.all([fetchSavedLeads(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error deleting queue item:', error);
        } finally {
            setSendQueueBusy((prev) => {
                const next = { ...prev };
                delete next[queueId];
                return next;
            });
        }
    };

    const bulkDeleteQueueItems = async () => {
        const queueIds = visibleQueueItems.filter((item) => selectedQueueItemIds.includes(item.id)).map((item) => item.id);
        if (queueIds.length === 0) return;
        setSendQueueBusy((prev) => ({ ...prev, bulkDeleteQueue: 'delete' }));
        try {
            await Promise.all(queueIds.map((queueId) => api.delete(`/admin/prospecting/send-queue/${queueId}`)));
            setSelectedQueueItemIds([]);
            await Promise.all([fetchSavedLeads(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error bulk deleting queue items:', error);
        } finally {
            setSendQueueBusy((prev) => {
                const next = { ...prev };
                delete next.bulkDeleteQueue;
                return next;
            });
        }
    };

    const bulkMarkDelivery = async (deliveryStatus: 'sent' | 'delivered' | 'failed') => {
        const queueIds = visibleQueueItems.filter((item) => selectedQueueItemIds.includes(item.id)).map((item) => item.id);
        if (queueIds.length === 0) return;

        setSendQueueBusy((prev) => ({ ...prev, bulkDelivery: deliveryStatus }));
        try {
            await Promise.all(
                queueIds.map((queueId) =>
                    api.post(`/admin/prospecting/send-queue/${queueId}/delivery`, {
                        delivery_status: deliveryStatus,
                        error_text: deliveryStatus === 'failed' ? 'Manual bulk delivery failure' : undefined,
                    })
                )
            );
            setSelectedQueueItemIds([]);
            await Promise.all([fetchSavedLeads(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error bulk updating delivery status:', error);
        } finally {
            setSendQueueBusy((prev) => {
                const next = { ...prev };
                delete next.bulkDelivery;
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

    const confirmReaction = async (reactionId: string, outcome: 'positive' | 'question' | 'no_response' | 'hard_no') => {
        setReactionBusy((prev) => ({ ...prev, [reactionId]: outcome }));
        try {
            await api.post(`/admin/prospecting/reactions/${reactionId}/confirm`, { outcome });
            await Promise.all([fetchSavedLeads(), fetchSendQueue()]);
        } catch (error) {
            console.error('Error confirming reaction outcome:', error);
        } finally {
            setReactionBusy((prev) => {
                const next = { ...prev };
                delete next[reactionId];
                return next;
            });
        }
    };

    const resetFilters = () => setFilters(emptyFilters);

    const sourceFilteredLeads = useMemo(
        () => savedLeads
            .filter(isDisplayableLead)
            .filter((lead) => !filters.source || (lead.source || '') === filters.source),
        [savedLeads, filters.source]
    );
    const shortlistLeads = useMemo(
        () => sourceFilteredLeads.filter((lead) => lead.status === shortlistApproved),
        [sourceFilteredLeads]
    );
    const rejectedLeads = useMemo(
        () => sourceFilteredLeads.filter((lead) => lead.status === shortlistRejected),
        [sourceFilteredLeads]
    );
    const candidateLeads = useMemo(
        () => sourceFilteredLeads.filter((lead) => ![shortlistApproved, shortlistRejected, selectedForOutreach, channelSelected].includes(lead.status)),
        [sourceFilteredLeads]
    );
    const outreachLeads = useMemo(
        () => sourceFilteredLeads.filter((lead) => lead.status === selectedForOutreach || lead.status === channelSelected),
        [sourceFilteredLeads]
    );
    const draftReadyLeads = useMemo(
        () => sourceFilteredLeads.filter((lead) => lead.status === channelSelected),
        [sourceFilteredLeads]
    );
    const filteredDraftReadyLeads = useMemo(
        () => draftReadyLeads.filter((lead) => !draftChannelFilter || (lead.selected_channel || '') === draftChannelFilter),
        [draftReadyLeads, draftChannelFilter]
    );
    const filteredDrafts = useMemo(
        () =>
            drafts.filter(
                (draft) =>
                    (!draftChannelFilter || draft.channel === draftChannelFilter) &&
                    (!draftStatusFilter || draft.status === draftStatusFilter)
            ),
        [drafts, draftChannelFilter, draftStatusFilter]
    );
    const filteredSendReadyDrafts = useMemo(
        () => sendReadyDrafts.filter((draft) => !queueChannelFilter || draft.channel === queueChannelFilter),
        [sendReadyDrafts, queueChannelFilter]
    );
    const todayBatchDate = useMemo(() => new Date().toISOString().slice(0, 10), []);
    const queueBatchNeedsAttention = (batch: OutreachBatch) =>
        (batch.items || []).some((item) => {
            if (queueChannelFilter && item.channel !== queueChannelFilter) return false;
            if (item.delivery_status === 'failed') return true;
            return item.delivery_status === 'sent' && !item.latest_human_outcome && !item.latest_outcome;
        });
    const filteredSendBatches = useMemo(() => {
        const byChannel = sendBatches.filter(
            (batch) => !queueChannelFilter || (batch.items || []).some((item) => item.channel === queueChannelFilter)
        );
        if (queueViewFilter === 'today') {
            return byChannel.filter((batch) => batch.batch_date === todayBatchDate);
        }
        if (queueViewFilter === 'attention') {
            return byChannel.filter((batch) => queueBatchNeedsAttention(batch));
        }
        return byChannel;
    }, [sendBatches, queueChannelFilter, queueViewFilter, todayBatchDate]);
    const groupedSendBatches = useMemo(() => {
        const groups = new Map<string, { batchDate: string; draftCount: number; approvedCount: number; batches: OutreachBatch[] }>();
        for (const batch of filteredSendBatches) {
            const key = batch.batch_date || 'Без даты';
            const existing = groups.get(key) || { batchDate: key, draftCount: 0, approvedCount: 0, batches: [] };
            existing.batches.push(batch);
            if (batch.status === 'approved') {
                existing.approvedCount += 1;
            } else {
                existing.draftCount += 1;
            }
            groups.set(key, existing);
        }
        return Array.from(groups.values()).sort((a, b) => b.batchDate.localeCompare(a.batchDate));
    }, [filteredSendBatches]);
    const visibleQueueItems = useMemo(
        () =>
            filteredSendBatches.flatMap((batch) =>
                (batch.items || []).filter((item) => !queueChannelFilter || item.channel === queueChannelFilter)
            ),
        [filteredSendBatches, queueChannelFilter]
    );
    const todaySendBatches = useMemo(
        () => filteredSendBatches.filter((batch) => batch.batch_date === todayBatchDate),
        [filteredSendBatches, todayBatchDate]
    );
    const todayQueueItems = useMemo(
        () =>
            todaySendBatches.flatMap((batch) =>
                (batch.items || []).filter((item) => !queueChannelFilter || item.channel === queueChannelFilter)
            ),
        [todaySendBatches, queueChannelFilter]
    );
    const todayQueueSummary = useMemo(() => {
        let queued = 0;
        let sent = 0;
        let delivered = 0;
        let failed = 0;
        let withReaction = 0;

        for (const item of todayQueueItems) {
            if (item.delivery_status === 'sent') {
                sent += 1;
            } else if (item.delivery_status === 'delivered') {
                delivered += 1;
            } else if (item.delivery_status === 'failed') {
                failed += 1;
            } else {
                queued += 1;
            }

            if (item.latest_human_outcome || item.latest_outcome) {
                withReaction += 1;
            }
        }

        return { queued, sent, delivered, failed, withReaction };
    }, [todayQueueItems]);

    useEffect(() => {
        setSelectedDraftIds((prev) => prev.filter((id) => filteredDrafts.some((draft) => draft.id === id)));
    }, [filteredDrafts]);

    useEffect(() => {
        setSelectedSendReadyDraftIds((prev) => prev.filter((id) => filteredSendReadyDrafts.some((draft) => draft.id === id)));
    }, [filteredSendReadyDrafts]);

    useEffect(() => {
        setSelectedShortlistLeadIds((prev) => prev.filter((id) => shortlistLeads.some((lead) => lead.id === id)));
    }, [shortlistLeads]);

    useEffect(() => {
        setSelectedOutreachLeadIds((prev) => prev.filter((id) => outreachLeads.some((lead) => lead.id === id)));
    }, [outreachLeads]);

    useEffect(() => {
        setSelectedQueueItemIds((prev) => prev.filter((id) => visibleQueueItems.some((item) => item.id === id)));
    }, [visibleQueueItems]);

    const visibleLeads = leadTab === 'shortlist'
        ? shortlistLeads
        : leadTab === 'rejected'
            ? rejectedLeads
            : candidateLeads;

    const closeLeadPreview = () => {
        setPreviewLead(null);
        setPreviewSnapshot(null);
        setPreviewError(null);
        setPreviewAuditPageUrl(null);
        setPreviewLoadingId(null);
    };

    const fetchLeadPreview = useCallback(async (leadId: string, options?: { silent?: boolean }) => {
        if (!leadId) {
            return;
        }

        if (!options?.silent) {
            setPreviewError(null);
            setPreviewLoadingId(leadId);
        }
        try {
            const response = await api.get(`/admin/prospecting/lead/${leadId}/preview`);
            const payload = response.data || {};
            if (payload.lead) {
                setPreviewLead(payload.lead as Lead);
            }
            setPreviewSnapshot((payload.preview as LeadCardPreview) || null);
        } catch (error: any) {
            if (!options?.silent) {
                setPreviewError(error?.message || 'Не удалось загрузить аудит карточки лида');
            }
        } finally {
            if (!options?.silent) {
                setPreviewLoadingId(null);
            }
        }
    }, []);

    const openLeadPreview = async (lead: Lead) => {
        if (!lead.id) {
            return;
        }

        setPreviewLead(lead);
        setPreviewSnapshot(null);
        setPreviewError(null);
        setPreviewAuditPageUrl(null);
        await fetchLeadPreview(lead.id);
    };

    const generateDraftFromLeadPreview = async () => {
        if (!previewLead?.id) {
            return;
        }
        setPreviewGenerateBusy(true);
        setPreviewError(null);
        try {
            await api.post(`/admin/prospecting/lead/${previewLead.id}/draft-generate-from-audit`);
            await Promise.all([fetchSavedLeads(), fetchDrafts(), fetchSendQueue()]);
            setActiveTab('drafts');
        } catch (error: any) {
            setPreviewError(error?.message || 'Не удалось сгенерировать письмо из аудита');
        } finally {
            setPreviewGenerateBusy(false);
        }
    };

    const generateAuditPageFromLeadPreview = async () => {
        if (!previewLead?.id) {
            return;
        }
        setPreviewAuditPageBusy(true);
        setPreviewError(null);
        setPreviewAuditPageUrl(null);
        try {
            const response = await api.post(`/admin/prospecting/lead/${previewLead.id}/offer-page`);
            const url = String(response.data?.public_url || '');
            setPreviewAuditPageUrl(url || null);
            if (url) {
                window.open(url, '_blank', 'noopener,noreferrer');
            }
        } catch (error: any) {
            setPreviewError(error?.message || 'Не удалось сгенерировать страницу аудита');
        } finally {
            setPreviewAuditPageBusy(false);
        }
    };

    const saveLeadContactsFromPreview = async (payload: { telegram_url: string; whatsapp_url: string; email: string }) => {
        if (!previewLead?.id) {
            return;
        }
        setPreviewContactsBusy(true);
        setPreviewError(null);
        try {
            const response = await api.post(`/admin/prospecting/lead/${previewLead.id}/contacts`, payload);
            const updatedLead = (response.data?.lead as Lead) || null;
            if (updatedLead) {
                setPreviewLead(updatedLead);
            }
            await fetchSavedLeads();
        } catch (error: any) {
            setPreviewError(error?.message || 'Не удалось сохранить контакты лида');
        } finally {
            setPreviewContactsBusy(false);
        }
    };

    const runLiveParseFromPreview = async () => {
        if (!previewLead?.id) {
            return;
        }
        setPreviewParseBusy(true);
        setPreviewError(null);
        try {
            await api.post(`/admin/prospecting/lead/${previewLead.id}/parse`);
            await fetchLeadPreview(previewLead.id);
            await fetchSavedLeads();
        } catch (error: any) {
            setPreviewError(error?.message || 'Не удалось запустить парсинг карточки');
        } finally {
            setPreviewParseBusy(false);
        }
    };

    const refreshPreviewStatus = async () => {
        if (!previewLead?.id) {
            return;
        }
        await fetchLeadPreview(previewLead.id, { silent: true });
    };

    useEffect(() => {
        const leadId = previewLead?.id;
        const status = String(previewSnapshot?.parse_context?.last_parse_status || '').toLowerCase();
        const shouldPoll = Boolean(leadId && ['pending', 'queued', 'processing', 'running'].includes(status));

        if (!shouldPoll) {
            setPreviewAutoRefreshing(false);
            return;
        }

        setPreviewAutoRefreshing(true);
        const timerId = window.setInterval(() => {
            if (leadId) {
                fetchLeadPreview(leadId, { silent: true });
            }
        }, 4000);

        return () => {
            window.clearInterval(timerId);
            setPreviewAutoRefreshing(false);
        };
    }, [previewLead?.id, previewSnapshot?.parse_context?.last_parse_status, fetchLeadPreview]);

    const bulkParseShortlist = async () => {
        const leadIds = shortlistLeads
            .filter((lead) => lead.id && selectedShortlistLeadIds.includes(lead.id))
            .map((lead) => lead.id as string);
        if (leadIds.length === 0) {
            return;
        }
        setBulkParseBusy(true);
        try {
            await api.post('/admin/prospecting/shortlist/parse', { lead_ids: leadIds });
            await fetchSavedLeads();
        } catch (error: any) {
            setSearchError(error?.message || 'Не удалось запустить парсинг shortlist');
        } finally {
            setBulkParseBusy(false);
        }
    };

    const renderLeadRow = (lead: Lead) => {
        const isBusy = Boolean(lead.id && shortlistLoading[lead.id]);
        const busyDecision = lead.id ? shortlistLoading[lead.id] : '';

        return (
            <TableRow key={lead.id}>
                <TableCell className="font-medium min-w-[260px]">
                    <div>{lead.name}</div>
                    <div className="text-xs text-muted-foreground">{lead.category || 'Без категории'}</div>
                    <div className="mt-1">
                        <Badge variant="outline" className="text-[11px] font-normal">
                            {formatLeadSource(lead.source)}
                        </Badge>
                    </div>
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
                        {lead.id && (
                            <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => openLeadPreview(lead)}
                                disabled={previewLoadingId === lead.id}
                            >
                                {previewLoadingId === lead.id && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                Аудит карточки
                            </Button>
                        )}
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
                        {lead.id && (
                            <Button
                                size="sm"
                                variant="destructive"
                                onClick={() => deleteLeadEverywhere(lead.id!)}
                                disabled={busyDecision === 'delete'}
                            >
                                {busyDecision === 'delete' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                Удалить
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

            {previewLead && (
                <LeadCardPreviewPanel
                    lead={previewLead}
                    preview={previewSnapshot}
                    loading={previewLoadingId === previewLead.id}
                    error={previewError}
                    generateBusy={previewGenerateBusy}
                    generateAuditPageBusy={previewAuditPageBusy}
                    generatedAuditPageUrl={previewAuditPageUrl}
                    contactsBusy={previewContactsBusy}
                    parseBusy={previewParseBusy}
                    parseAutoRefreshing={previewAutoRefreshing}
                    onGenerateFromAudit={generateDraftFromLeadPreview}
                    onGenerateAuditPage={generateAuditPageFromLeadPreview}
                    onSaveContacts={saveLeadContactsFromPreview}
                    onRunLiveParse={runLiveParseFromPreview}
                    onRefreshPreview={refreshPreviewStatus}
                    onClose={closeLeadPreview}
                />
            )}

            <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as 'search' | 'leads' | 'outreach' | 'drafts' | 'queue')} className="w-full">
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
                            <CardDescription>Поиск компаний через Apify (Яндекс Карты / 2GIS) и сохранение в лиды.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <form onSubmit={handleSearch} className="flex flex-wrap gap-4 items-end">
                                <div className="grid w-56 items-center gap-1.5">
                                    <label htmlFor="search-source">Источник</label>
                                    <select
                                        id="search-source"
                                        value={searchSource}
                                        onChange={(e) => setSearchSource(e.target.value === 'apify_2gis' ? 'apify_2gis' : 'apify_yandex')}
                                        className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                                    >
                                        <option value="apify_yandex">Apify Yandex</option>
                                        <option value="apify_2gis">Apify 2GIS</option>
                                    </select>
                                </div>
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
                            <div className="mt-4 rounded-lg border border-border bg-muted/30 p-3">
                                <div className="mb-2 text-sm font-medium">Добавить компанию вручную по ссылке</div>
                                <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                                    <Input
                                        placeholder="https://yandex.ru/maps/org/..."
                                        value={manualLeadUrl}
                                        onChange={(e) => setManualLeadUrl(e.target.value)}
                                        className="md:col-span-2"
                                    />
                                    <Input
                                        placeholder="Название (необязательно)"
                                        value={manualLeadName}
                                        onChange={(e) => setManualLeadName(e.target.value)}
                                    />
                                    <Input
                                        placeholder="Категория (необязательно)"
                                        value={manualLeadCategory}
                                        onChange={(e) => setManualLeadCategory(e.target.value)}
                                    />
                                </div>
                                <div className="mt-3 flex justify-end">
                                    <Button
                                        type="button"
                                        onClick={addLeadByUrl}
                                        disabled={manualLeadBusy || !manualLeadUrl.trim()}
                                    >
                                        {manualLeadBusy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                        Добавить по ссылке
                                    </Button>
                                </div>
                            </div>
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

                    <Card>
                        <CardHeader>
                            <CardTitle>Внешний импорт лидов</CardTitle>
                            <CardDescription>
                                Используйте этот путь, если запускаете поиск в Apify вручную. Поддерживается JSON-массив items или объект с полем <code>items</code>.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex flex-wrap gap-3 items-center">
                                <Input type="file" accept=".json,application/json" onChange={handleImportFile} className="max-w-sm" />
                                <Button onClick={importLeads} disabled={importBusy || !importJson.trim()}>
                                    {importBusy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                    Импортировать JSON
                                </Button>
                            </div>
                            <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
                                <div className="font-medium">Рекомендуемый формат</div>
                                <div className="mt-1 text-muted-foreground">
                                    Лучше всего загружать экспорт Apify в формате <code>JSON</code> с <code>All fields</code>.
                                    Импорт понимает либо массив объектов, либо объект с полем <code>items</code>, <code>results</code> или <code>leads</code>.
                                </div>
                                <pre className="mt-3 overflow-x-auto rounded-md bg-background p-3 text-xs leading-5">
{`{
  "items": [
    {
      "title": "Maya",
      "categories": ["Beauty salon", "Nail salon"],
      "address": "Санкт-Петербург, ...",
      "phone": "+7 ...",
      "website": "https://...",
      "totalScore": 4.8,
      "reviewsCount": 124,
      "url": "https://yandex.ru/maps/..."
    }
  ]
}`}
                                </pre>
                                <div className="mt-2 text-xs text-muted-foreground">
                                    Если в выгрузке нет <code>email</code>, <code>telegram</code> или <code>whatsapp</code>, импорт это не выдумает.
                                    Для первого этапа достаточно названия, категории, адреса, телефона, сайта, рейтинга и отзывов.
                                </div>
                            </div>
                            <textarea
                                className="min-h-[180px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                                placeholder='Вставьте JSON из Apify export: [{"title":"...","address":"..."}]'
                                value={importJson}
                                onChange={(e) => setImportJson(e.target.value)}
                            />
                            {importResult && (
                                <div className={`text-sm ${importResult.startsWith('Ошибка') ? 'text-red-600' : 'text-emerald-700'}`}>
                                    {importResult}
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
                                                        <div className="mt-1">
                                                            <Badge variant="outline" className="text-[11px] font-normal">
                                                                {sourceLabel(lead.source)}
                                                            </Badge>
                                                        </div>
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
                                <select className="border rounded-md px-3 py-2 bg-background text-sm" value={filters.source} onChange={(e) => setFilters(prev => ({ ...prev, source: e.target.value }))}>
                                    <option value="">Источник: любой</option>
                                    <option value="external_import">Внешний импорт</option>
                                    <option value="apify_yandex">Apify Yandex</option>
                                    <option value="openclaw">OpenClaw</option>
                                    <option value="manual">Ручной ввод</option>
                                </select>
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
                                    <div className="flex items-center gap-2">
                                        <Badge variant="secondary">{shortlistLeads.length}</Badge>
                                        <Badge variant="outline">Выбрано: {selectedShortlistLeadIds.length}</Badge>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() =>
                                                setSelectedShortlistLeadIds(
                                                    selectedShortlistLeadIds.length === shortlistLeads.length
                                                        ? []
                                                        : shortlistLeads.map((lead) => lead.id).filter(Boolean) as string[]
                                                )
                                            }
                                            disabled={shortlistLeads.length === 0}
                                        >
                                            {selectedShortlistLeadIds.length === shortlistLeads.length && shortlistLeads.length > 0 ? 'Снять всё' : 'Выбрать всё'}
                                        </Button>
                                        <Button
                                            size="sm"
                                            onClick={bulkSelectForOutreach}
                                            disabled={selectedShortlistLeadIds.length === 0 || selectionLoading.bulkSelect === 'select'}
                                        >
                                            {selectionLoading.bulkSelect === 'select' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                            Выбрать отмеченные
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="secondary"
                                            onClick={bulkParseShortlist}
                                            disabled={selectedShortlistLeadIds.length === 0 || bulkParseBusy}
                                        >
                                            {bulkParseBusy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                            Парсить отмеченные
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="destructive"
                                            onClick={bulkDeleteShortlistLeads}
                                            disabled={selectedShortlistLeadIds.length === 0 || selectionLoading.bulkDeleteShortlist === 'delete'}
                                        >
                                            {selectionLoading.bulkDeleteShortlist === 'delete' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                            Удалить отмеченные
                                        </Button>
                                    </div>
                                </div>
                                <div className="space-y-3">
                                    {shortlistLeads.length === 0 && (
                                        <div className="text-sm text-muted-foreground">Нет лидов в shortlist для следующего шага.</div>
                                    )}
                                    {shortlistLeads.map((lead) => {
                                        const pending = selectionLoading[lead.id || ''];
                                        return (
                                            <div key={lead.id} className="flex flex-col gap-3 rounded-md border p-3 md:flex-row md:items-center md:justify-between">
                                                <div className="space-y-2">
                                                    <label className="flex items-center gap-2 text-xs text-muted-foreground">
                                                        <input
                                                            type="checkbox"
                                                            checked={!!lead.id && selectedShortlistLeadIds.includes(lead.id)}
                                                            onChange={(e) =>
                                                                lead.id &&
                                                                setSelectedShortlistLeadIds((prev) =>
                                                                    e.target.checked ? [...prev, lead.id as string] : prev.filter((id) => id !== lead.id)
                                                                )
                                                            }
                                                        />
                                                        Отметить для массового перевода
                                                    </label>
                                                    <div className="font-medium">{lead.name}</div>
                                                    <LeadMetaSummary lead={lead} />
                                                </div>
                                                <div className="flex flex-wrap gap-2">
                                                    {lead.id && (
                                                        <Button
                                                            variant="secondary"
                                                            onClick={() => openLeadPreview(lead)}
                                                            disabled={previewLoadingId === lead.id}
                                                        >
                                                            {previewLoadingId === lead.id && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                                            Аудит карточки
                                                        </Button>
                                                    )}
                                                    <Button onClick={() => lead.id && selectForOutreach(lead.id)} disabled={!lead.id || Boolean(pending)}>
                                                        {pending === 'select' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                                        Выбрать для контакта
                                                    </Button>
                                                    <Button
                                                        variant="destructive"
                                                        onClick={() => lead.id && deleteLeadEverywhere(lead.id)}
                                                        disabled={!lead.id || pending === 'delete'}
                                                    >
                                                        {pending === 'delete' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                                        Удалить
                                                    </Button>
                                                </div>
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
                                    <div className="flex flex-wrap items-center gap-2">
                                        <Badge variant="secondary">{outreachLeads.length}</Badge>
                                        <Badge variant="outline">Выбрано: {selectedOutreachLeadIds.length}</Badge>
                                        <select
                                            className="border rounded-md px-3 py-2 bg-background text-sm"
                                            value={bulkOutreachChannel}
                                            onChange={(e) => setBulkOutreachChannel(e.target.value as 'telegram' | 'whatsapp' | 'email' | 'manual')}
                                        >
                                            <option value="telegram">Telegram</option>
                                            <option value="whatsapp">WhatsApp</option>
                                            <option value="email">Email</option>
                                            <option value="manual">Manual</option>
                                        </select>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() =>
                                                setSelectedOutreachLeadIds(
                                                    selectedOutreachLeadIds.length === outreachLeads.length
                                                        ? []
                                                        : outreachLeads.map((lead) => lead.id).filter(Boolean) as string[]
                                                )
                                            }
                                            disabled={outreachLeads.length === 0}
                                        >
                                            {selectedOutreachLeadIds.length === outreachLeads.length && outreachLeads.length > 0 ? 'Снять всё' : 'Выбрать всё'}
                                        </Button>
                                        <Button
                                            size="sm"
                                            onClick={bulkAssignOutreachChannel}
                                            disabled={selectedOutreachLeadIds.length === 0 || selectionLoading.bulkChannel === bulkOutreachChannel}
                                        >
                                            {selectionLoading.bulkChannel === bulkOutreachChannel && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                            Назначить канал выбранным
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="destructive"
                                            onClick={bulkDeleteOutreachLeads}
                                            disabled={selectedOutreachLeadIds.length === 0 || selectionLoading.bulkDeleteOutreach === 'delete'}
                                        >
                                            {selectionLoading.bulkDeleteOutreach === 'delete' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                            Удалить выбранные
                                        </Button>
                                    </div>
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
                                                    <div className="space-y-2">
                                                        <label className="flex items-center gap-2 text-xs text-muted-foreground">
                                                            <input
                                                                type="checkbox"
                                                                checked={!!lead.id && selectedOutreachLeadIds.includes(lead.id)}
                                                                onChange={(e) =>
                                                                    lead.id &&
                                                                    setSelectedOutreachLeadIds((prev) =>
                                                                        e.target.checked ? [...prev, lead.id as string] : prev.filter((id) => id !== lead.id)
                                                                    )
                                                                }
                                                            />
                                                            Отметить для массового назначения канала
                                                        </label>
                                                        <div className="font-medium">{lead.name}</div>
                                                        <LeadMetaSummary lead={lead} showChannel />
                                                        <div className="flex items-center gap-2">
                                                            <Badge variant={badgeVariantForStatus(lead.status)}>{statusLabel(lead.status)}</Badge>
                                                            <Badge variant="outline">{workflowStatusLabel(lead.status)}</Badge>
                                                        </div>
                                                    </div>
                                                </div>
                                                <div className="flex flex-wrap gap-2">
                                                    {lead.id && (
                                                        <Button
                                                            size="sm"
                                                            variant="secondary"
                                                            onClick={() => openLeadPreview(lead)}
                                                            disabled={previewLoadingId === lead.id}
                                                        >
                                                            {previewLoadingId === lead.id && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                                            Аудит карточки
                                                        </Button>
                                                    )}
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
                                                    <Button
                                                        size="sm"
                                                        variant="destructive"
                                                        onClick={() => lead.id && deleteLeadEverywhere(lead.id)}
                                                        disabled={!lead.id || pending === 'delete'}
                                                    >
                                                        {pending === 'delete' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                                        Удалить
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

                <TabsContent value="drafts" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>Черновики первого сообщения</CardTitle>
                            <CardDescription>
                                Здесь отображаются письма, уже сгенерированные из аудита карточки лида. Можно редактировать, утверждать и отклонять.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="flex flex-wrap items-center gap-3 rounded-lg border p-4">
                                <div className="text-sm font-medium">Фильтр канала для черновиков</div>
                                <select className="border rounded-md px-3 py-2 bg-background text-sm" value={draftChannelFilter} onChange={(e) => setDraftChannelFilter(e.target.value)}>
                                    <option value="">Все каналы</option>
                                    <option value="telegram">Telegram</option>
                                    <option value="whatsapp">WhatsApp</option>
                                    <option value="email">Email</option>
                                    <option value="manual">Manual</option>
                                </select>
                                <div className="text-sm font-medium">Статус</div>
                                <select className="border rounded-md px-3 py-2 bg-background text-sm" value={draftStatusFilter} onChange={(e) => setDraftStatusFilter(e.target.value)}>
                                    <option value="">Все статусы</option>
                                    <option value="generated">generated</option>
                                    <option value="approved">approved</option>
                                    <option value="rejected">rejected</option>
                                </select>
                                <Badge variant="outline">Черновики: {filteredDrafts.length}</Badge>
                            </div>
                            <div className="rounded-lg border p-4">
                                <div className="mb-3 flex items-center justify-between gap-3">
                                    <div>
                                        <h3 className="font-semibold">Список черновиков</h3>
                                        <p className="text-sm text-muted-foreground">Ваши правки после утверждения сохраняются как learning examples.</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Badge variant="secondary">{filteredDrafts.length}</Badge>
                                        <Badge variant="outline">Выбрано: {selectedDraftIds.length}</Badge>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => setSelectedDraftIds(selectedDraftIds.length === filteredDrafts.length ? [] : filteredDrafts.map((draft) => draft.id))}
                                            disabled={filteredDrafts.length === 0}
                                        >
                                            {selectedDraftIds.length === filteredDrafts.length && filteredDrafts.length > 0 ? 'Снять всё' : 'Выбрать всё'}
                                        </Button>
                                        <Button
                                            size="sm"
                                            onClick={approveSelectedDrafts}
                                            disabled={selectedDraftIds.length === 0 || draftBusy.bulkApprove === 'approve'}
                                        >
                                            {draftBusy.bulkApprove === 'approve' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                            Утвердить выбранные
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={rejectSelectedDrafts}
                                            disabled={selectedDraftIds.length === 0 || draftBusy.bulkReject === 'reject'}
                                        >
                                            {draftBusy.bulkReject === 'reject' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                            Отклонить выбранные
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="destructive"
                                            onClick={deleteSelectedDrafts}
                                            disabled={selectedDraftIds.length === 0 || draftBusy.bulkDelete === 'delete'}
                                        >
                                            {draftBusy.bulkDelete === 'delete' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                            Удалить выбранные
                                        </Button>
                                    </div>
                                </div>
                                <div className="space-y-4">
                                    {loadingDrafts && (
                                        <div className="flex justify-center p-8"><Loader2 className="h-8 w-8 animate-spin" /></div>
                                    )}
                                    {!loadingDrafts && filteredDrafts.length === 0 && (
                                        <div className="text-sm text-muted-foreground">Черновиков пока нет.</div>
                                    )}
                                    {filteredDrafts.map((draft) => {
                                        const pending = draftBusy[draft.id];
                                        return (
                                            <div key={draft.id} className="rounded-md border p-4 space-y-3">
                                                <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                                                    <div>
                                                        <label className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                                                            <input
                                                                type="checkbox"
                                                                checked={selectedDraftIds.includes(draft.id)}
                                                                onChange={(e) =>
                                                                    setSelectedDraftIds((prev) =>
                                                                        e.target.checked ? [...prev, draft.id] : prev.filter((id) => id !== draft.id)
                                                                    )
                                                                }
                                                            />
                                                            Выбрать для массового утверждения
                                                        </label>
                                                        <div className="font-medium">{draft.lead_name || draft.lead_id}</div>
                                                        <div className="text-sm text-muted-foreground">
                                                            Канал: {formatLeadChannel(draft.channel)} · Статус: {draft.status}
                                                        </div>
                                                        <div className="mt-1">
                                                            <Badge variant="outline">{workflowStatusLabel(savedLeads.find((item) => item.id === draft.lead_id)?.status || '')}</Badge>
                                                        </div>
                                                        {(() => {
                                                            const lead = savedLeads.find((item) => item.id === draft.lead_id);
                                                            if (!lead) return null;
                                                            return (
                                                                <div className="mt-2">
                                                                    <LeadMetaSummary lead={lead} showChannel />
                                                                </div>
                                                            );
                                                        })()}
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        {(() => {
                                                            const lead = savedLeads.find((item) => item.id === draft.lead_id);
                                                            if (!lead?.id) return null;
                                                            return (
                                                                <Button
                                                                    size="sm"
                                                                    variant="secondary"
                                                                    onClick={() => openLeadPreview(lead)}
                                                                    disabled={previewLoadingId === lead.id}
                                                                >
                                                                    {previewLoadingId === lead.id && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                                                    Аудит карточки
                                                                </Button>
                                                            );
                                                        })()}
                                                        <Badge variant={draft.status === 'approved' ? 'default' : draft.status === 'rejected' ? 'destructive' : 'secondary'}>
                                                            {draft.status}
                                                        </Badge>
                                                    </div>
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
                                                    <Button variant="secondary" onClick={() => saveDraftEdit(draft.id)} disabled={Boolean(pending)}>
                                                        {pending === 'save' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                                        Сохранить черновик
                                                    </Button>
                                                    <Button onClick={() => approveDraft(draft.id)} disabled={Boolean(pending)}>
                                                        {pending === 'approve' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                                        Утвердить
                                                    </Button>
                                                    <Button variant="outline" onClick={() => rejectDraft(draft.id)} disabled={Boolean(pending)}>
                                                        {pending === 'reject' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                                        Отклонить
                                                    </Button>
                                                    <Button variant="destructive" onClick={() => deleteDraft(draft.id)} disabled={Boolean(pending)}>
                                                        {pending === 'delete' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                                        Удалить
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
                            <div className="flex flex-wrap items-center gap-3 rounded-lg border p-4">
                                <div className="text-sm font-medium">Фильтр канала для очереди</div>
                                <select className="border rounded-md px-3 py-2 bg-background text-sm" value={queueChannelFilter} onChange={(e) => setQueueChannelFilter(e.target.value)}>
                                    <option value="">Все каналы</option>
                                    <option value="telegram">Telegram</option>
                                    <option value="whatsapp">WhatsApp</option>
                                    <option value="email">Email</option>
                                    <option value="manual">Manual</option>
                                </select>
                                <div className="text-sm font-medium">Показать</div>
                                <div className="flex flex-wrap gap-2">
                                    <Button size="sm" variant={queueViewFilter === 'all' ? 'default' : 'outline'} onClick={() => setQueueViewFilter('all')}>
                                        Все
                                    </Button>
                                    <Button size="sm" variant={queueViewFilter === 'today' ? 'default' : 'outline'} onClick={() => setQueueViewFilter('today')}>
                                        Только сегодня
                                    </Button>
                                    <Button size="sm" variant={queueViewFilter === 'attention' ? 'default' : 'outline'} onClick={() => setQueueViewFilter('attention')}>
                                        Требует внимания
                                    </Button>
                                </div>
                                <Badge variant="secondary">Готовы к queue: {filteredSendReadyDrafts.length}</Badge>
                                <Badge variant="outline">Batch-групп: {groupedSendBatches.length}</Badge>
                                <Badge variant="outline">Выбрано в очереди: {selectedQueueItemIds.length}</Badge>
                            </div>
                            <div className="rounded-lg border p-4">
                                <div className="mb-3 flex items-center justify-between gap-3">
                                    <div>
                                        <h3 className="font-semibold">Готовые к постановке в очередь</h3>
                                        <p className="text-sm text-muted-foreground">Используются только утверждённые черновики, которые ещё не попали в send queue.</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Badge variant="secondary">{filteredSendReadyDrafts.length}</Badge>
                                        <Badge variant="outline">Выбрано: {selectedSendReadyDraftIds.length}</Badge>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() =>
                                                setSelectedSendReadyDraftIds(
                                                    selectedSendReadyDraftIds.length === filteredSendReadyDrafts.length
                                                        ? []
                                                        : filteredSendReadyDrafts.slice(0, sendDailyCap).map((draft) => draft.id)
                                                )
                                            }
                                            disabled={filteredSendReadyDrafts.length === 0}
                                        >
                                            {selectedSendReadyDraftIds.length > 0 ? 'Снять выбор' : `Выбрать первые ${Math.min(filteredSendReadyDrafts.length, sendDailyCap)}`}
                                        </Button>
                                        <Button onClick={() => createSendBatch()} disabled={loadingSendQueue || Boolean(sendQueueBusy.create) || filteredSendReadyDrafts.length === 0}>
                                            {(loadingSendQueue || sendQueueBusy.create === 'create') && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                            Собрать batch (до {sendDailyCap})
                                        </Button>
                                        <Button
                                            variant="outline"
                                            onClick={() => createSendBatch(selectedSendReadyDraftIds)}
                                            disabled={loadingSendQueue || Boolean(sendQueueBusy.create) || selectedSendReadyDraftIds.length === 0}
                                        >
                                            {(loadingSendQueue || sendQueueBusy.create === 'create') && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                            Собрать из выбранных
                                        </Button>
                                    </div>
                                </div>
                                <div className="space-y-3">
                                    {loadingSendQueue && (
                                        <div className="flex justify-center p-6"><Loader2 className="h-8 w-8 animate-spin" /></div>
                                    )}
                                    {!loadingSendQueue && filteredSendReadyDrafts.length === 0 && (
                                        <div className="text-sm text-muted-foreground">Нет утверждённых черновиков, готовых к постановке в очередь.</div>
                                    )}
                                    {filteredSendReadyDrafts.slice(0, sendDailyCap).map((draft) => (
                                        <div key={draft.id} className="rounded-md border p-3">
                                            <div className="mb-2 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                                                <div>
                                                    <label className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                                                        <input
                                                            type="checkbox"
                                                            checked={selectedSendReadyDraftIds.includes(draft.id)}
                                                            onChange={(e) =>
                                                                setSelectedSendReadyDraftIds((prev) =>
                                                                    e.target.checked ? [...prev, draft.id] : prev.filter((id) => id !== draft.id)
                                                                )
                                                            }
                                                        />
                                                        Включить в ручной batch
                                                    </label>
                                                    <div className="font-medium">{draft.lead_name || draft.lead_id}</div>
                                                    <div className="text-sm text-muted-foreground">
                                                        Канал: {formatLeadChannel(draft.channel)} · Черновик утверждён
                                                    </div>
                                                    {(() => {
                                                        const lead = savedLeads.find((item) => item.id === draft.lead_id);
                                                        if (!lead) return null;
                                                        return (
                                                            <div className="mt-2">
                                                                <LeadMetaSummary lead={lead} showChannel />
                                                            </div>
                                                        );
                                                    })()}
                                                </div>
                                                <Badge variant="default">Готов к queue</Badge>
                                            </div>
                                            <div className="rounded-md bg-muted/30 p-3 text-sm whitespace-pre-wrap">
                                                {draft.approved_text || draft.edited_text || draft.generated_text}
                                            </div>
                                        </div>
                                    ))}
                                    {filteredSendReadyDrafts.length > sendDailyCap && (
                                        <div className="text-xs text-muted-foreground">
                                            В batch попадут первые {sendDailyCap} черновиков по времени обновления. Остальные останутся ждать следующего дня.
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="rounded-lg border p-4">
                                <div className="mb-3 flex items-center justify-between gap-3">
                                    <div>
                                        <h3 className="font-semibold">Сегодня</h3>
                                        <p className="text-sm text-muted-foreground">Текущая рабочая пачка на дату {todayBatchDate}.</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Badge variant="secondary">Batch: {todaySendBatches.length}</Badge>
                                        <Badge variant="outline">Элементы: {todayQueueItems.length}</Badge>
                                    </div>
                                </div>
                                <div className="space-y-3">
                                    {todaySendBatches.length === 0 && (
                                        <div className="text-sm text-muted-foreground">На сегодня ещё нет batch.</div>
                                    )}
                                    {todaySendBatches.length > 0 && (
                                        <div className="flex flex-wrap gap-2">
                                            <Badge variant="outline">В очереди: {todayQueueSummary.queued}</Badge>
                                            <Badge variant="default">Sent: {todayQueueSummary.sent}</Badge>
                                            <Badge variant="secondary">Delivered: {todayQueueSummary.delivered}</Badge>
                                            <Badge variant={todayQueueSummary.failed > 0 ? 'destructive' : 'outline'}>
                                                Failed: {todayQueueSummary.failed}
                                            </Badge>
                                            <Badge variant="secondary">С реакцией: {todayQueueSummary.withReaction}</Badge>
                                        </div>
                                    )}
                                    {todaySendBatches.map((batch) => (
                                        <div key={`today-${batch.id}`} className="rounded-md border p-3">
                                            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                                                <div>
                                                    <div className="font-medium">Batch {batch.id.slice(0, 8)}</div>
                                                    <div className="text-sm text-muted-foreground">
                                                        Статус: {batch.status === 'approved' ? 'Подтверждён' : 'Черновик'} · Элементов: {(batch.items || []).filter((item) => !queueChannelFilter || item.channel === queueChannelFilter).length}
                                                    </div>
                                                </div>
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
                                    ))}
                                </div>
                            </div>

                            <div className="rounded-lg border p-4">
                                <div className="mb-3 flex items-center justify-between gap-3">
                                    <div>
                                        <h3 className="font-semibold">Сформированные batch</h3>
                                        <p className="text-sm text-muted-foreground">После ручного подтверждения batch можно вручную отмечать доставку и фиксировать входящие реакции.</p>
                                    </div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <Badge variant="secondary">{filteredSendBatches.length}</Badge>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() =>
                                                setSelectedQueueItemIds(
                                                    selectedQueueItemIds.length === visibleQueueItems.length
                                                        ? []
                                                        : visibleQueueItems.map((item) => item.id)
                                                )
                                            }
                                            disabled={visibleQueueItems.length === 0}
                                        >
                                            {selectedQueueItemIds.length === visibleQueueItems.length && visibleQueueItems.length > 0 ? 'Снять всё' : 'Выбрать всё'}
                                        </Button>
                                        <Button
                                            size="sm"
                                            onClick={() => bulkMarkDelivery('sent')}
                                            disabled={selectedQueueItemIds.length === 0 || sendQueueBusy.bulkDelivery === 'sent'}
                                        >
                                            {sendQueueBusy.bulkDelivery === 'sent' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                            Отметить выбранные sent
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => bulkMarkDelivery('delivered')}
                                            disabled={selectedQueueItemIds.length === 0 || sendQueueBusy.bulkDelivery === 'delivered'}
                                        >
                                            {sendQueueBusy.bulkDelivery === 'delivered' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                            Отметить выбранные delivered
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => bulkMarkDelivery('failed')}
                                            disabled={selectedQueueItemIds.length === 0 || sendQueueBusy.bulkDelivery === 'failed'}
                                        >
                                            {sendQueueBusy.bulkDelivery === 'failed' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                            Пометить выбранные failed
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="destructive"
                                            onClick={bulkDeleteQueueItems}
                                            disabled={selectedQueueItemIds.length === 0 || sendQueueBusy.bulkDeleteQueue === 'delete'}
                                        >
                                            {sendQueueBusy.bulkDeleteQueue === 'delete' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                            Удалить выбранные
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="destructive"
                                            onClick={cleanupTestBatches}
                                            disabled={sendQueueBusy.cleanupTest === 'cleanup'}
                                        >
                                            {sendQueueBusy.cleanupTest === 'cleanup' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                            Очистить тестовые batch
                                        </Button>
                                    </div>
                                </div>
                                <div className="space-y-4">
                                    {!loadingSendQueue && filteredSendBatches.length === 0 && (
                                        <div className="text-sm text-muted-foreground">Пока нет сформированных batch.</div>
                                    )}
                                    {groupedSendBatches.map((group) => (
                                        <div key={group.batchDate} className="rounded-lg border p-4 space-y-4">
                                            <div className="flex flex-wrap items-center justify-between gap-3">
                                                <div>
                                                    <div className="font-semibold">Группа batch за {group.batchDate}</div>
                                                    <div className="text-sm text-muted-foreground">
                                                        Batch: {group.batches.length} · Draft: {group.draftCount} · Подтверждено: {group.approvedCount}
                                                    </div>
                                                </div>
                                                <Badge variant="outline">Дата: {group.batchDate}</Badge>
                                            </div>
                                            {group.batches.map((batch) => (
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
                                                            <Button
                                                                size="sm"
                                                                variant="destructive"
                                                                onClick={() => deleteSendBatch(batch.id)}
                                                                disabled={Boolean(sendQueueBusy[batch.id])}
                                                            >
                                                                {sendQueueBusy[batch.id] === 'delete' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                                                Удалить batch
                                                            </Button>
                                                        </div>
                                                    </div>
                                                    <div className="space-y-2">
                                                        {(batch.items || [])
                                                            .filter((item) => !queueChannelFilter || item.channel === queueChannelFilter)
                                                            .map((item) => (
                                                            <div key={item.id} className="rounded-md bg-muted/20 p-3 text-sm space-y-3">
                                                                <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                                                                    <div>
                                                                        <label className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                                                                            <input
                                                                                type="checkbox"
                                                                                checked={selectedQueueItemIds.includes(item.id)}
                                                                                onChange={(e) =>
                                                                                    setSelectedQueueItemIds((prev) =>
                                                                                        e.target.checked ? [...prev, item.id] : prev.filter((id) => id !== item.id)
                                                                                    )
                                                                                }
                                                                            />
                                                                            Выбрать для массовой отметки
                                                                        </label>
                                                                        <div className="font-medium">{item.lead_name || item.lead_id}</div>
                                                                        <div className="text-muted-foreground">
                                                                            Канал: {formatLeadChannel(item.channel)} · Доставка: {item.delivery_status}
                                                                        </div>
                                                                        <div className="mt-1">
                                                                            <Badge variant="outline">
                                                                                {workflowStatusLabel(
                                                                                    item.latest_human_outcome || item.latest_outcome
                                                                                        ? 'responded'
                                                                                        : item.delivery_status === 'sent' || item.delivery_status === 'delivered'
                                                                                            ? 'sent'
                                                                                            : 'queued_for_send'
                                                                                )}
                                                                            </Badge>
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
                                                                            variant={item.delivery_status === 'sent' || item.delivery_status === 'delivered' ? 'default' : 'outline'}
                                                                            onClick={() => markDelivery(item.id, 'sent')}
                                                                            disabled={Boolean(sendQueueBusy[item.id])}
                                                                        >
                                                                            {sendQueueBusy[item.id] === 'sent' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                                                            Отмечено как sent
                                                                        </Button>
                                                                        <Button
                                                                            size="sm"
                                                                            variant={item.delivery_status === 'delivered' ? 'default' : 'outline'}
                                                                            onClick={() => markDelivery(item.id, 'delivered')}
                                                                            disabled={Boolean(sendQueueBusy[item.id])}
                                                                        >
                                                                            {sendQueueBusy[item.id] === 'delivered' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                                                            Отмечено как delivered
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
                                                                        <Button
                                                                            size="sm"
                                                                            variant="destructive"
                                                                            onClick={() => deleteQueueItem(item.id)}
                                                                            disabled={Boolean(sendQueueBusy[item.id])}
                                                                        >
                                                                            {sendQueueBusy[item.id] === 'delete' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                                                            Удалить
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
                                                <div className="flex flex-wrap items-center gap-2">
                                                    <Badge variant="outline">
                                                        {formatReactionClassifierSource(getReactionClassifierSource(reaction.note))}
                                                    </Badge>
                                                    <Badge variant={reaction.human_confirmed_outcome === 'hard_no' ? 'destructive' : 'secondary'}>
                                                        {reaction.human_confirmed_outcome || reaction.classified_outcome}
                                                    </Badge>
                                                </div>
                                            </div>
                                            <div className="text-muted-foreground">
                                                Batch: {reaction.batch_id || '—'} · Канал: {reaction.channel || '—'} · Delivery: {reaction.delivery_status || '—'}
                                            </div>
                                            {reaction.human_confirmed_outcome && reaction.human_confirmed_outcome !== reaction.classified_outcome && (
                                                <div className="mt-1 text-xs text-muted-foreground">
                                                    AI: {reaction.classified_outcome} → Подтверждено: {reaction.human_confirmed_outcome}
                                                </div>
                                            )}
                                            {reaction.raw_reply && (
                                                <div className="mt-2 whitespace-pre-wrap">
                                                    {reaction.raw_reply}
                                                </div>
                                            )}
                                            <div className="mt-3 flex flex-wrap gap-2">
                                                {reactionOutcomeOptions.map((outcome) => (
                                                    <Button
                                                        key={`${reaction.id}-${outcome}`}
                                                        type="button"
                                                        size="sm"
                                                        variant={(reaction.human_confirmed_outcome || reaction.classified_outcome) === outcome ? 'default' : 'outline'}
                                                        onClick={() => confirmReaction(reaction.id, outcome)}
                                                        disabled={Boolean(reactionBusy[reaction.id])}
                                                    >
                                                        {reactionBusy[reaction.id] === outcome && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                                        {outcome}
                                                    </Button>
                                                ))}
                                            </div>
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
