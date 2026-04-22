import React, { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Badge } from "./ui/badge";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "./ui/sheet";
import { Loader2, MapPin, Phone, Globe, Star, Mail, MessageCircle, Save, Search, SlidersHorizontal, Plus, LayoutGrid, List, ExternalLink, TriangleAlert, X, ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "@/services/api";
import { ContactPresenceBadges, StatusSummaryCard, WorkflowActionRow } from "./prospecting/LeadWorkflowBlocks";
import { AnalyticsMetricGrid, AnalyticsSection, AnalyticsSummaryGrid, AnalyticsWindowGrid } from "./prospecting/ProspectingAnalyticsBlocks";
import {
    ErrorSummary,
    LeadList,
    LeadListItem,
    StickyBulkActionBar,
} from "./prospecting/OutreachWorkspaceBlocks";
import { DraftDetailPanel, QueueDetailPanel, SentDetailPanel } from "./prospecting/OutreachDetailPanes";
import { ProspectingIntakePanel, ProspectingPipelineHeader, ProspectingWorkspaceTabs } from "./prospecting/ProspectingWorkspaceChrome";
import { getRequestErrorMessage, withBusyState } from "./prospecting/prospectingAsync";
import type { LeadCardPreview } from "./LeadCardPreviewPanel";
import { toast } from "sonner";

const LeadCardPreviewPanel = lazy(() => import("./LeadCardPreviewPanel"));

const OutreachDetailModal = ({
    title,
    description,
    onClose,
    onPrevious,
    onNext,
    previousDisabled = false,
    nextDisabled = false,
    children,
}: {
    title: string;
    description?: string;
    onClose: () => void;
    onPrevious?: () => void;
    onNext?: () => void;
    previousDisabled?: boolean;
    nextDisabled?: boolean;
    children: React.ReactNode;
}) => {
    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                onClose();
                return;
            }
            if (event.key === 'ArrowLeft' && onPrevious && !previousDisabled) {
                onPrevious();
                return;
            }
            if (event.key === 'ArrowRight' && onNext && !nextDisabled) {
                onNext();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [nextDisabled, onClose, onNext, onPrevious, previousDisabled]);

    return (
        <div
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-2 sm:p-4 animate-in fade-in duration-200"
            onClick={onClose}
        >
            <Card
                className="w-[min(1280px,calc(100vw-1rem))] sm:w-[min(1280px,calc(100vw-2rem))] max-h-[94vh] overflow-hidden shadow-2xl border-0 animate-in zoom-in-95 duration-200"
                onClick={(event) => event.stopPropagation()}
            >
                <CardHeader className="border-b border-border/50 bg-gradient-to-r from-card to-card/50 px-4 py-4 sm:px-6">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0">
                            <CardTitle className="text-xl sm:text-2xl">{title}</CardTitle>
                            {description ? <p className="text-sm text-muted-foreground mt-1">{description}</p> : null}
                            <p className="mt-2 text-xs text-muted-foreground">
                                `Esc` закрывает окно. Стрелки влево и вправо листают соседние лиды.
                            </p>
                        </div>
                        <div className="flex items-center gap-2 self-end lg:self-start">
                            {onPrevious ? (
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={onPrevious}
                                    disabled={previousDisabled}
                                    aria-label="Открыть предыдущего лида"
                                >
                                    <ChevronLeft className="mr-1 h-4 w-4" />
                                    Назад
                                </Button>
                            ) : null}
                            {onNext ? (
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={onNext}
                                    disabled={nextDisabled}
                                    aria-label="Открыть следующего лида"
                                >
                                    Вперёд
                                    <ChevronRight className="ml-1 h-4 w-4" />
                                </Button>
                            ) : null}
                            <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                onClick={onClose}
                                className="rounded-full"
                                aria-label="Закрыть детали лида"
                            >
                                <X className="h-4 w-4" />
                            </Button>
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="overflow-y-auto max-h-[calc(94vh-132px)] p-4 sm:p-6">
                    {children}
                </CardContent>
            </Card>
        </div>
    );
};

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
    pipeline_status?: string;
    disqualification_reason?: string | null;
    disqualification_comment?: string | null;
    postponed_comment?: string | null;
    next_action_at?: string | null;
    last_contact_at?: string | null;
    last_contact_channel?: string | null;
    last_contact_comment?: string | null;
    location?: Record<string, unknown> | null;
    status: string;
    created_at?: string;
    updated_at?: string;
    partnership_stage?: string;
    public_audit_slug?: string;
    public_audit_url?: string;
    public_audit_updated_at?: string;
    has_public_audit?: boolean;
    parse_status?: string | null;
    parse_updated_at?: string | null;
    parse_retry_after?: string | null;
    parse_error?: string | null;
    parse_task_id?: string | null;
    preferred_language?: string | null;
    enabled_languages?: string[] | null;
    groups?: Array<{
        id?: string;
        name?: string;
        status?: string;
        channel_hint?: string | null;
        city_hint?: string | null;
    }>;
    group_count?: number;
    timeline_preview?: {
        event_type?: string;
        comment?: string | null;
        payload?: Record<string, unknown>;
        created_at?: string;
    } | null;
};

type LeadGroup = {
    id: string;
    name: string;
    description?: string | null;
    status: string;
    channel_hint?: string | null;
    city_hint?: string | null;
    created_by?: string | null;
    created_at?: string;
    updated_at?: string;
    leads_count?: number;
    without_channel_count?: number;
    without_contact_count?: number;
    without_audit_count?: number;
    drafts_count?: number;
};

type SearchJob = {
    id: string;
    status: 'queued' | 'running' | 'completed' | 'failed';
    result_count: number;
    apify_status?: string | null;
    error_text?: string | null;
    results: Lead[];
};

type SearchDuplicateReason = {
    code: string;
    label: string;
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
    provider_name?: string | null;
    provider_account_id?: string | null;
    recipient_kind?: string | null;
    recipient_value?: string | null;
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

const ACTIVE_SEARCH_JOB_STORAGE_KEY = 'prospecting_active_search_job_id';
const LAST_SEARCH_JOB_STORAGE_KEY = 'prospecting_last_search_job';
const LAST_SEARCH_RESULTS_STORAGE_KEY = 'prospecting_last_search_results';

type OutreachBatch = {
    id: string;
    batch_date: string;
    daily_limit: number;
    status: string;
    runtime_status?: string;
    queue_summary?: {
        total?: number;
        queued?: number;
        sending?: number;
        sent?: number;
        delivered?: number;
        retry?: number;
        failed?: number;
        dlq?: number;
        with_reaction?: number;
    };
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
    provider_name?: string | null;
    provider_account_id?: string | null;
    provider_message_id?: string | null;
    reply_created_at?: string | null;
};

type TelegramAppStatus = {
    configured: boolean;
    authorized: boolean;
    phone?: string | null;
    account_id?: string | null;
    status?: string | null;
};

type TelegramReplySyncSummary = {
    picked: number;
    imported: number;
    duplicates: number;
    noops: number;
    failed: number;
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
    hasTelegram: string;
    hasWhatsApp: string;
    hasVk: string;
    hasMax: string;
};

type KanbanColumnId = 'new' | 'shortlist' | 'in_progress' | 'contacted' | 'closed';
type WorkspaceTab = 'raw' | 'pipeline' | 'groups' | 'outreach' | 'analytics';
const toOutreachContactFilter = (value: string): OutreachContactFilter => {
    if (value === 'telegram' || value === 'whatsapp' || value === 'max' || value === 'email' || value === 'vk') {
        return value;
    }
    return '';
};

const toWorkspaceTab = (value: string): WorkspaceTab => {
    if (value === 'pipeline' || value === 'groups' || value === 'outreach' || value === 'analytics') {
        return value;
    }
    return 'raw';
};

const toOutreachTab = (value: string): OutreachTab => {
    if (value === 'queue' || value === 'sent') {
        return value;
    }
    return 'drafts';
};
type OutreachTab = 'drafts' | 'queue' | 'sent';
type PipelineViewMode = 'kanban' | 'list';
type PipelineQuickFilter = 'all' | 'without_audit' | 'with_audit' | 'priority';
type PipelineBoardColumnId = 'in_progress' | 'postponed' | 'not_relevant' | 'contacted' | 'waiting_reply' | 'replied' | 'converted';

const inferLeadAuditLanguage = (lead: Lead | null): string => {
    const preferred = String(lead?.preferred_language || '').trim().toLowerCase();
    if (preferred) {
        return preferred;
    }
    const context = [
        lead?.city || '',
        lead?.address || '',
        lead?.source_url || '',
        lead?.name || '',
    ].join(' ').toLowerCase();
    if (context.includes('türkiye') || context.includes('turkey') || context.includes('istanbul') || context.includes('fethiye') || context.includes('ölüdeniz')) {
        return 'tr';
    }
    if (context.includes('cyprus') || context.includes('paphos') || context.includes('πάφος')) {
        return 'en';
    }
    return 'en';
};

const ensureAuditLanguages = (primaryLanguage: string, enabledLanguages?: string[]): string[] => {
    const normalizedPrimary = String(primaryLanguage || 'en').trim().toLowerCase() || 'en';
    const result: string[] = [];
    const source = Array.isArray(enabledLanguages) ? enabledLanguages : [];
    source.forEach((item) => {
        const value = String(item || '').trim().toLowerCase();
        if (!value) {
            return;
        }
        if (!result.includes(value)) {
            result.push(value);
        }
    });
    if (!result.includes(normalizedPrimary)) {
        result.unshift(normalizedPrimary);
    }
    return result.length > 0 ? result : [normalizedPrimary];
};

const AUDIT_LANGUAGE_OPTIONS = [
    { value: 'en', label: 'English' },
    { value: 'ru', label: 'Русский' },
    { value: 'es', label: 'Español' },
    { value: 'de', label: 'Deutsch' },
    { value: 'fr', label: 'Français' },
    { value: 'el', label: 'Ελληνικά' },
    { value: 'th', label: 'ไทย' },
    { value: 'tr', label: 'Türkçe' },
    { value: 'ar', label: 'العربية' },
    { value: 'ha', label: 'Hausa' },
];

const formatLanguageLabel = (language: string) => {
    const normalized = String(language || '').trim().toLowerCase();
    const match = AUDIT_LANGUAGE_OPTIONS.find((item) => item.value === normalized);
    return match?.label || normalized || '—';
};

const formatConversion = (current: number, previous: number) => {
    if (!previous || previous <= 0) {
        return '—';
    }
    return `${Math.round((current / previous) * 100)}%`;
};

const formatDropOff = (current: number, previous: number) => {
    if (!previous || previous <= 0) {
        return '—';
    }
    return `${Math.max(previous - current, 0)}`;
};

const normalizeLeadIdentityText = (value: unknown) =>
    String(value || '')
        .trim()
        .toLowerCase()
        .replace(/ё/g, 'е')
        .replace(/https?:\/\//g, '')
        .replace(/[^a-z0-9а-я]+/gi, ' ')
        .replace(/\s+/g, ' ')
        .trim();

const normalizeLeadIdentityUrl = (value: unknown) => {
    const raw = String(value || '').trim();
    if (!raw) {
        return '';
    }
    try {
        const url = new URL(raw);
        url.hash = '';
        const host = url.hostname.toLowerCase();
        const normalizedHost = host.replace(/^www\./, '');
        if (normalizedHost.includes('yandex.')) {
            url.hostname = 'yandex.com';
            url.search = '';
            url.pathname = url.pathname.replace(/\/+$/, '');
        } else if (normalizedHost.includes('google.')) {
            url.hostname = 'www.google.com';
            if (url.pathname.startsWith('/maps/place/')) {
                url.search = '';
            }
            url.pathname = url.pathname.replace(/\/+$/, '');
        } else {
            url.pathname = url.pathname.replace(/\/+$/, '');
        }
        return url.toString();
    } catch {
        return raw.replace(/\/+$/, '');
    }
};

const extractLeadIdentityIdsFromUrl = (value: unknown) => {
    const url = String(value || '').trim();
    if (!url) {
        return [];
    }
    const ids: string[] = [];
    const push = (prefix: string, rawId?: string | null) => {
        const normalized = String(rawId || '').trim().toLowerCase();
        if (!normalized) {
            return;
        }
        const key = `${prefix}:${normalized}`;
        if (!ids.includes(key)) {
            ids.push(key);
        }
    };
    const yandexMatch = url.match(/\/org\/(?:[^/]+\/)?(\d+)/i);
    if (yandexMatch?.[1]) {
        push('source_external_id', yandexMatch[1]);
        push('google_id', yandexMatch[1]);
    }
    const cidMatch = url.match(/[?&]cid=(\d+)/i);
    if (cidMatch?.[1]) {
        push('source_external_id', cidMatch[1]);
        push('google_id', cidMatch[1]);
    }
    const googlePlaceMatch = url.match(/!1s(0x[0-9a-f]+:0x[0-9a-f]+)/i);
    if (googlePlaceMatch?.[1]) {
        push('source_external_id', googlePlaceMatch[1]);
        push('google_id', googlePlaceMatch[1]);
    }
    return ids;
};

const buildLeadIdentityKeys = (lead: Partial<Lead>) => {
    const keys: string[] = [];
    const push = (prefix: string, value: unknown) => {
        const normalized = String(value || '').trim().toLowerCase();
        if (!normalized) {
            return;
        }
        const nextKey = `${prefix}:${normalized}`;
        if (!keys.includes(nextKey)) {
            keys.push(nextKey);
        }
    };

    push('source_external_id', lead.source_external_id);
    push('google_id', lead.google_id);
    push('source_url', lead.source_url);
    push('name', lead.name);
    const normalizedSourceUrl = normalizeLeadIdentityUrl(lead.source_url);
    if (normalizedSourceUrl) {
        push('source_url_normalized', normalizedSourceUrl);
        extractLeadIdentityIdsFromUrl(normalizedSourceUrl).forEach((key) => {
            if (!keys.includes(key)) {
                keys.push(key);
            }
        });
    }
    const cityNameKey = [normalizeLeadIdentityText(lead.name), normalizeLeadIdentityText(lead.city)]
        .filter(Boolean)
        .join(' | ');
    if (cityNameKey) {
        push('name_city', cityNameKey);
    }

    return keys;
};

const buildStrictDuplicateReasons = (lead: Partial<Lead>): Array<SearchDuplicateReason & { key: string }> => {
    const reasons: Array<SearchDuplicateReason & { key: string }> = [];
    const seen = new Set<string>();
    const push = (code: string, label: string, value: unknown) => {
        const normalized = String(value || '').trim().toLowerCase();
        if (!normalized) {
            return;
        }
        const dedupeKey = `${code}:${normalized}`;
        if (seen.has(dedupeKey)) {
            return;
        }
        seen.add(dedupeKey);
        reasons.push({ code, label, key: dedupeKey });
    };

    push('source_external_id', 'совпадает внешний ID карточки', lead.source_external_id);
    push('google_id', 'совпадает Google/Yandex ID', lead.google_id);

    const normalizedSourceUrl = normalizeLeadIdentityUrl(lead.source_url);
    if (normalizedSourceUrl) {
        push('source_url_normalized', 'совпадает ссылка на карточку', normalizedSourceUrl);
        extractLeadIdentityIdsFromUrl(normalizedSourceUrl).forEach((item) => {
            const [code, value] = item.split(':', 2);
            if (code && value) {
                push(code, code === 'google_id' ? 'совпадает Google/Yandex ID' : 'совпадает внешний ID карточки', value);
            }
        });
    }

    const normalizedName = normalizeLeadIdentityText(lead.name);
    const normalizedAddress = normalizeLeadIdentityText(lead.address);
    const normalizedCity = normalizeLeadIdentityText(lead.city);
    if (normalizedName && normalizedAddress) {
        push('name_address', 'совпадают название и адрес', `${normalizedName} | ${normalizedAddress}`);
    } else if (normalizedName && normalizedCity) {
        push('name_city', 'совпадают название и город', `${normalizedName} | ${normalizedCity}`);
    }

    return reasons;
};

const isWithinLastDays = (value?: string, days?: number) => {
    if (!value || !days) {
        return false;
    }
    const timestamp = Date.parse(value);
    if (Number.isNaN(timestamp)) {
        return false;
    }
    const now = Date.now();
    const diff = now - timestamp;
    return diff >= 0 && diff <= days * 24 * 60 * 60 * 1000;
};

const buildLeadAuditLanguageLinks = (lead: Lead) => {
    const baseUrl = String(lead.public_audit_url || '').trim();
    if (!baseUrl) {
        return [];
    }
    const enabled = Array.isArray(lead.enabled_languages) && lead.enabled_languages.length > 0
        ? lead.enabled_languages
        : [String(lead.preferred_language || inferLeadAuditLanguage(lead)).trim().toLowerCase() || 'en'];

    return enabled
        .map((item) => String(item || '').trim().toLowerCase())
        .filter(Boolean)
        .map((language) => {
            const url = new URL(baseUrl, window.location.origin);
            url.searchParams.set('lang', language);
            return {
                language,
                href: url.toString(),
                label: formatLanguageLabel(language),
            };
        });
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
    hasTelegram: '',
    hasWhatsApp: '',
    hasVk: '',
    hasMax: '',
};

const shortlistApproved = 'shortlist_approved';
const shortlistRejected = 'shortlist_rejected';
const deferredLead = 'deferred';
const selectedForOutreach = 'selected_for_outreach';
const channelSelected = 'channel_selected';
const PIPELINE_UNPROCESSED = 'unprocessed';
const PIPELINE_IN_PROGRESS = 'in_progress';
const PIPELINE_POSTPONED = 'postponed';
const PIPELINE_NOT_RELEVANT = 'not_relevant';
const PIPELINE_CONTACTED = 'contacted';
const PIPELINE_WAITING_REPLY = 'waiting_reply';
const PIPELINE_REPLIED = 'replied';
const PIPELINE_CONVERTED = 'converted';
const PIPELINE_CLOSED_LOST = 'closed_lost';

const getLeadPipelineStatus = (lead?: Partial<Lead> | null) => {
    const explicit = String(lead?.pipeline_status || '').trim().toLowerCase();
    if (explicit) {
        return explicit;
    }
    const legacy = String(lead?.status || '').trim().toLowerCase();
    if (!legacy || legacy === 'new') return PIPELINE_UNPROCESSED;
    if ([shortlistApproved, selectedForOutreach, channelSelected, 'draft_ready', 'queued_for_send', 'audited', 'matched', 'proposal_draft_ready', 'proposal_approved', 'approved_for_send'].includes(legacy)) return PIPELINE_IN_PROGRESS;
    if (legacy === 'deferred') return PIPELINE_POSTPONED;
    if ([shortlistRejected, 'rejected'].includes(legacy)) return PIPELINE_NOT_RELEVANT;
    if (legacy === 'sent') return PIPELINE_CONTACTED;
    if (legacy === 'delivered') return PIPELINE_WAITING_REPLY;
    if (legacy === 'responded') return PIPELINE_REPLIED;
    if (['qualified', 'converted'].includes(legacy)) return PIPELINE_CONVERTED;
    if (legacy === 'closed') return PIPELINE_CLOSED_LOST;
    return PIPELINE_IN_PROGRESS;
};

const pipelineStatusLabel = (status?: string | null) => {
    switch (String(status || '').trim().toLowerCase()) {
        case PIPELINE_UNPROCESSED:
            return 'Необработан';
        case PIPELINE_IN_PROGRESS:
            return 'В работе';
        case PIPELINE_POSTPONED:
            return 'Отложен';
        case PIPELINE_NOT_RELEVANT:
            return 'Неактуален';
        case PIPELINE_CONTACTED:
            return 'Отправлено';
        case PIPELINE_WAITING_REPLY:
            return 'Ждём ответ';
        case PIPELINE_REPLIED:
            return 'Ответил';
        case PIPELINE_CONVERTED:
            return 'Конвертирован';
        case PIPELINE_CLOSED_LOST:
            return 'Закрыт';
        default:
            return '—';
    }
};

const badgeVariantForStatus = (status: string) => {
    if (status === shortlistApproved) {
        return 'default';
    }
    if (status === shortlistRejected || status === 'rejected') {
        return 'destructive';
    }
    if (status === deferredLead) {
        return 'outline';
    }
    return 'secondary';
};

const statusLabel = (status: string) => {
    return pipelineStatusLabel(getLeadPipelineStatus({ status }));
};

const workflowStatusLabel = (status: string) => {
    return pipelineStatusLabel(getLeadPipelineStatus({ status }));
};

const kanbanColumnOrder: KanbanColumnId[] = ['new', 'shortlist', 'in_progress', 'contacted', 'closed'];

const kanbanColumnMeta: Record<KanbanColumnId, { label: string; description: string; statusToSet: string }> = {
    new: {
        label: 'Новые',
        description: 'Свежие лиды из поиска и ручного ввода.',
        statusToSet: 'new',
    },
    shortlist: {
        label: 'Отобранные',
        description: 'Потенциально подходят для первого контакта.',
        statusToSet: shortlistApproved,
    },
    in_progress: {
        label: 'В работе',
        description: 'Аудит и подготовка первого контакта.',
        statusToSet: selectedForOutreach,
    },
    contacted: {
        label: 'Контактированы',
        description: 'Сообщение отправлено или в процессе.',
        statusToSet: 'sent',
    },
    closed: {
        label: 'Отложенные',
        description: 'Лиды, которые вернём в работу позже или не берём сейчас.',
        statusToSet: deferredLead,
    },
};

const leadToKanbanColumn = (lead: Lead): KanbanColumnId => {
    const status = String(lead.status || '').trim().toLowerCase();
    if (!status || status === 'new') {
        return 'new';
    }
    if (status === shortlistApproved) {
        return 'shortlist';
    }
    if ([selectedForOutreach, channelSelected, 'draft_ready'].includes(status)) {
        return 'in_progress';
    }
    if (['queued_for_send', 'sent', 'delivered', 'responded', 'converted'].includes(status)) {
        return 'contacted';
    }
    if ([deferredLead, shortlistRejected, 'rejected', 'closed'].includes(status)) {
        return 'closed';
    }
    return 'new';
};

const nextKanbanColumn = (columnId: KanbanColumnId): KanbanColumnId | null => {
    const idx = kanbanColumnOrder.indexOf(columnId);
    if (idx === -1 || idx >= kanbanColumnOrder.length - 1) {
        return null;
    }
    return kanbanColumnOrder[idx + 1];
};

const pipelineBoardColumnOrder: PipelineBoardColumnId[] = ['in_progress', 'postponed', 'not_relevant', 'contacted', 'waiting_reply', 'replied', 'converted'];

const pipelineBoardColumnMeta: Record<PipelineBoardColumnId, { label: string; description: string; statusToSet: string }> = {
    in_progress: {
        label: 'В работе',
        description: 'Подходящие лиды, с которыми сейчас работаем и которых можно собирать в группы.',
        statusToSet: PIPELINE_IN_PROGRESS,
    },
    postponed: {
        label: 'Отложенные',
        description: 'Лиды, к которым нужно вернуться позже с комментарием и следующим шагом.',
        statusToSet: PIPELINE_POSTPONED,
    },
    not_relevant: {
        label: 'Неактуален',
        description: 'Лиды, которые отсеяны как неподходящие или сняты с процесса.',
        statusToSet: PIPELINE_NOT_RELEVANT,
    },
    contacted: {
        label: 'Отправлено',
        description: 'Первичный контакт уже состоялся: вручную или через отправку.',
        statusToSet: PIPELINE_CONTACTED,
    },
    waiting_reply: {
        label: 'Ждём ответ',
        description: 'Первое касание уже сделано, сейчас ждём реакцию.',
        statusToSet: PIPELINE_WAITING_REPLY,
    },
    replied: {
        label: 'Ответил',
        description: 'Лид ответил, идёт переписка или уточнение деталей.',
        statusToSet: PIPELINE_REPLIED,
    },
    converted: {
        label: 'Конвертирован',
        description: 'Лид перешёл в следующий коммерческий этап или стал клиентом.',
        statusToSet: PIPELINE_CONVERTED,
    },
};

const leadToPipelineBoardColumn = (lead: Lead): PipelineBoardColumnId => {
    const status = getLeadPipelineStatus(lead);
    if (status === PIPELINE_IN_PROGRESS || status === PIPELINE_UNPROCESSED) {
        return 'in_progress';
    }
    if (status === PIPELINE_POSTPONED) {
        return 'postponed';
    }
    if (status === PIPELINE_NOT_RELEVANT || status === PIPELINE_CLOSED_LOST) {
        return 'not_relevant';
    }
    if (status === PIPELINE_CONTACTED) {
        return 'contacted';
    }
    if (status === PIPELINE_WAITING_REPLY) {
        return 'waiting_reply';
    }
    if (status === PIPELINE_REPLIED) {
        return 'replied';
    }
    if (status === PIPELINE_CONVERTED) {
        return 'converted';
    }
    return 'in_progress';
};

const nextPipelineBoardColumn = (columnId: PipelineBoardColumnId): PipelineBoardColumnId | null => {
    const idx = pipelineBoardColumnOrder.indexOf(columnId);
    if (idx === -1 || idx >= pipelineBoardColumnOrder.length - 1) {
        return null;
    }
    return pipelineBoardColumnOrder[idx + 1];
};

const sourceLabel = (source?: string) => {
    switch (source) {
        case 'external_import':
            return 'Внешний импорт';
        case 'apify_yandex':
            return 'Apify Yandex';
        case 'apify_2gis':
            return 'Apify 2GIS';
        case 'apify_google':
            return 'Apify Google';
        case 'apify_apple':
            return 'Apify Apple';
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
        case 'max':
            return 'Max';
        case 'email':
            return 'Email';
        case 'manual':
            return 'Manual';
        default:
            return channel || 'Канал не выбран';
    }
};

const formatQueueProvider = (providerName?: string | null) => {
    const normalized = String(providerName || '').trim().toLowerCase();
    if (normalized === 'telegram_app') return 'Telegram app';
    if (normalized === 'openclaw') return 'OpenClaw';
    if (normalized === 'maton') return 'Maton';
    if (normalized === 'manual') return 'Manual';
    if (normalized === 'email') return 'Email';
    if (normalized === 'max') return 'Max';
    return normalized || '—';
};

const buildLeadFallbackFromQueueItem = (item: OutreachQueueItem): Lead => ({
    id: item.lead_id,
    name: item.lead_name || item.lead_id,
    selected_channel: item.channel,
    status:
        item.delivery_status === 'sent' || item.delivery_status === 'delivered'
            ? 'sent'
            : item.delivery_status === 'failed' || item.delivery_status === 'dlq'
                ? 'queued_for_send'
                : 'queued_for_send',
});

const buildLeadRecipientValue = (lead: Lead | null | undefined, channel?: string) => {
    const normalizedChannel = String(channel || lead?.selected_channel || '').trim().toLowerCase();
    if (!lead) {
        return null;
    }
    if (normalizedChannel === 'telegram') {
        return lead.telegram_url || null;
    }
    if (normalizedChannel === 'whatsapp') {
        return lead.whatsapp_url || lead.phone || null;
    }
    if (normalizedChannel === 'email') {
        return lead.email || null;
    }
    if (normalizedChannel === 'max') {
        return extractHasMax(lead) ? 'Контакт через Max найден' : null;
    }
    if (normalizedChannel === 'manual') {
        return 'Ручная отправка';
    }
    return lead.phone || lead.website || null;
};

const buildSyntheticSentQueueItem = (lead: Lead): OutreachQueueItem | null => {
    const leadId = String(lead.id || '').trim();
    if (!leadId) {
        return null;
    }
    const status = String(lead.status || '').trim().toLowerCase();
    if (!['sent', 'delivered', 'responded', 'qualified', 'converted'].includes(status)) {
        return null;
    }
    const channel = String(lead.selected_channel || '').trim().toLowerCase() || 'manual';
    const deliveryStatus = status === 'sent' ? 'sent' : 'delivered';
    const timestamp = lead.updated_at || lead.created_at || null;
    return {
        id: `manual-${leadId}`,
        batch_id: 'manual',
        draft_id: '',
        lead_id: leadId,
        lead_name: lead.name,
        channel,
        delivery_status: deliveryStatus,
        provider_name: 'manual',
        provider_message_id: `manual:${leadId}`,
        recipient_kind: channel,
        recipient_value: buildLeadRecipientValue(lead, channel),
        created_at: timestamp || undefined,
        updated_at: timestamp || undefined,
        sent_at: timestamp || undefined,
    };
};

const queueItemMatchesContactFilter = (
    item: OutreachQueueItem,
    lead: Lead | undefined,
    contactFilter: OutreachContactFilter
) => {
    if (!contactFilter) {
        return true;
    }
    if (lead) {
        return leadMatchesOutreachContactFilter(lead, contactFilter);
    }
    if (contactFilter === 'vk') {
        return false;
    }
    return item.channel === contactFilter;
};

const summarizeBatchFromItems = (batch: OutreachBatch) => {
    const base = batch.queue_summary || {};
    const items = Array.isArray(batch.items) ? batch.items : [];
    const fallback = {
        total: items.length,
        queued: 0,
        sending: 0,
        sent: 0,
        delivered: 0,
        retry: 0,
        failed: 0,
        dlq: 0,
        with_reaction: 0,
    };
    items.forEach((item) => {
        const status = String(item.delivery_status || '').trim().toLowerCase();
        if (status in fallback) {
            fallback[status as keyof typeof fallback] += 1;
        }
        if (item.latest_outcome || item.latest_human_outcome || item.latest_raw_reply) {
            fallback.with_reaction += 1;
        }
    });
    return {
        total: Number(base.total ?? fallback.total ?? 0),
        queued: Number(base.queued ?? fallback.queued ?? 0),
        sending: Number(base.sending ?? fallback.sending ?? 0),
        sent: Number(base.sent ?? fallback.sent ?? 0),
        delivered: Number(base.delivered ?? fallback.delivered ?? 0),
        retry: Number(base.retry ?? fallback.retry ?? 0),
        failed: Number(base.failed ?? fallback.failed ?? 0),
        dlq: Number(base.dlq ?? fallback.dlq ?? 0),
        withReaction: Number(base.with_reaction ?? fallback.with_reaction ?? 0),
    };
};

const formatBatchRuntimeStatus = (batch: OutreachBatch) => {
    const runtimeStatus = String(batch.runtime_status || batch.status || '').trim().toLowerCase();
    if (runtimeStatus === 'draft') return 'Черновик';
    if (runtimeStatus === 'sending') return 'Идёт отправка';
    if (runtimeStatus === 'completed') return 'Завершён';
    if (runtimeStatus === 'approved') return 'Подтверждён';
    return runtimeStatus || '—';
};

const hasLeadAudit = (lead: Lead) => Boolean(String(lead.public_audit_url || '').trim());

const leadAuditLanguageSummary = (lead: Lead) => {
    const enabled = Array.isArray(lead.enabled_languages)
        ? lead.enabled_languages
            .map((item) => String(item || '').trim().toLowerCase())
            .filter(Boolean)
        : [];
    const primary = String(lead.preferred_language || '').trim().toLowerCase() || enabled[0] || '';
    const uniqueLanguages: string[] = [];
    enabled.forEach((item) => {
        if (!uniqueLanguages.includes(item)) {
            uniqueLanguages.push(item);
        }
    });
    if (primary && !uniqueLanguages.includes(primary)) {
        uniqueLanguages.unshift(primary);
    }
    return {
        primary,
        total: uniqueLanguages.length,
    };
};

const formatAuditUpdatedAt = (value?: string) => {
    if (!value) {
        return 'Дата не зафиксирована';
    }
    const timestamp = Date.parse(value);
    if (Number.isNaN(timestamp)) {
        return 'Дата не зафиксирована';
    }
    return new Date(timestamp).toLocaleString('ru-RU');
};

const reactionOutcomeOptions: Array<'positive' | 'question' | 'no_response' | 'hard_no'> = ['positive', 'question', 'no_response', 'hard_no'];

const formatDraftStatusLabel = (status?: string | null) => {
    const normalized = String(status || '').trim().toLowerCase();
    if (normalized === 'approved') {
        return 'Готово к отправке';
    }
    if (normalized === 'rejected') {
        return 'Нужна проверка';
    }
    return 'Ждёт проверки';
};

const toneForDraftStatus = (status?: string | null): 'default' | 'success' | 'warning' | 'danger' => {
    const normalized = String(status || '').trim().toLowerCase();
    if (normalized === 'approved') {
        return 'success';
    }
    if (normalized === 'rejected') {
        return 'danger';
    }
    return 'warning';
};

const formatQueueStatusLabel = (status?: string | null) => {
    const normalized = String(status || '').trim().toLowerCase();
    if (normalized === 'queued') {
        return 'Готово к отправке';
    }
    if (normalized === 'sending') {
        return 'Отправляем';
    }
    if (normalized === 'sent') {
        return 'Отправлено';
    }
    if (normalized === 'delivered') {
        return 'Доставлено';
    }
    if (normalized === 'retry') {
        return 'Повторная попытка';
    }
    if (normalized === 'dlq' || normalized === 'failed') {
        return 'Нужна проверка';
    }
    return 'Ждёт действия';
};

const toneForQueueStatus = (status?: string | null): 'default' | 'success' | 'warning' | 'danger' | 'info' => {
    const normalized = String(status || '').trim().toLowerCase();
    if (normalized === 'sent' || normalized === 'delivered') {
        return 'success';
    }
    if (normalized === 'failed' || normalized === 'dlq') {
        return 'danger';
    }
    if (normalized === 'sending' || normalized === 'retry') {
        return 'warning';
    }
    if (normalized === 'queued') {
        return 'info';
    }
    return 'default';
};

const leadLanguageLabel = (lead: Lead | null | undefined) => {
    if (!lead) {
        return 'Язык не задан';
    }
    const enabled = Array.isArray(lead.enabled_languages) ? lead.enabled_languages.filter(Boolean) : [];
    const primary = String(lead.preferred_language || enabled[0] || '').trim();
    if (!primary) {
        return 'Язык не задан';
    }
    if (enabled.length > 1) {
        return `${primary.toUpperCase()} +${enabled.length - 1}`;
    }
    return primary.toUpperCase();
};

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

const isRawImportedLead = (lead: Lead) => {
    const status = String(lead.status || '').trim().toLowerCase();
    const stage = String(lead.partnership_stage || '').trim().toLowerCase();
    return status === 'imported' && (!stage || stage === 'imported');
};

const isLeadAlreadySent = (lead?: Lead) => {
    const status = String(lead?.status || '').trim().toLowerCase();
    return ['sent', 'delivered', 'responded', 'converted'].includes(status);
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

const extractHasVk = (lead: Lead) => {
    const website = String(lead.website || '').trim().toLowerCase();
    if (website.includes('vk.com')) {
        return true;
    }
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
    return Array.isArray(parsedLinks) && parsedLinks.some((item) => String(item || '').toLowerCase().includes('vk.com'));
};

const extractHasMax = (lead: Lead) => {
    const website = String(lead.website || '').trim().toLowerCase();
    if (website.includes('max.ru') || website.includes('web.max.ru')) {
        return true;
    }
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
    return Array.isArray(parsedLinks) && parsedLinks.some((item) => {
        const value = String(item || '').toLowerCase();
        return value.includes('max.ru') || value.includes('web.max.ru');
    });
};

const matchesBooleanFilter = (value: string, condition: boolean) => {
    const normalized = normalizeBooleanFilter(value);
    if (normalized === undefined) {
        return true;
    }
    return normalized === condition;
};

type OutreachChannel = 'telegram' | 'whatsapp' | 'max' | 'email' | 'manual';
type OutreachContactFilter = '' | 'telegram' | 'whatsapp' | 'max' | 'email' | 'vk';
type SentStateFilter = '' | 'problem' | 'ready' | 'history';

const toOutreachChannel = (value: string): OutreachChannel => {
    if (value === 'telegram' || value === 'whatsapp' || value === 'max' || value === 'email') {
        return value;
    }
    return 'manual';
};

const hasChannelContact = (lead: Lead | undefined, channel: string) => {
    if (!lead) {
        return false;
    }
    if (channel === 'telegram') {
        return Boolean(lead.telegram_url);
    }
    if (channel === 'whatsapp') {
        return Boolean(lead.whatsapp_url);
    }
    if (channel === 'max') {
        return extractHasMax(lead);
    }
    if (channel === 'email') {
        return Boolean(lead.email);
    }
    if (channel === 'vk') {
        return extractHasVk(lead);
    }
    if (channel === 'manual') {
        return true;
    }
    return false;
};

const leadMatchesOutreachContactFilter = (lead: Lead | undefined, filter: OutreachContactFilter) => {
    if (!filter) {
        return true;
    }
    return hasChannelContact(lead, filter);
};

const bestAvailableOutreachChannel = (lead: Lead | undefined): OutreachChannel => {
    if (hasChannelContact(lead, 'telegram')) {
        return 'telegram';
    }
    if (hasChannelContact(lead, 'whatsapp')) {
        return 'whatsapp';
    }
    if (hasChannelContact(lead, 'max')) {
        return 'max';
    }
    if (hasChannelContact(lead, 'email')) {
        return 'email';
    }
    return 'manual';
};

const bestAlternativeOutreachChannel = (lead: Lead | undefined, currentChannel?: string | null): OutreachChannel | null => {
    const normalizedCurrent = String(currentChannel || '').trim().toLowerCase();
    const orderedChannels: OutreachChannel[] = ['telegram', 'whatsapp', 'max', 'email', 'manual'];
    const alternative = orderedChannels.find((channel) => channel !== normalizedCurrent && hasChannelContact(lead, channel));
    return alternative || null;
};

const selectedChannelWarning = (lead: Lead | undefined, channel?: string | null) => {
    const normalized = String(channel || '').trim().toLowerCase();
    if (!normalized || normalized === 'manual') {
        return '';
    }
    if (hasChannelContact(lead, normalized)) {
        return '';
    }
    return `Выбран ${formatLeadChannel(normalized)}, но контакт этого типа у лида не заполнен.`;
};

const formatDateTime = (value?: string | null) => {
    const raw = String(value || '').trim();
    if (!raw) {
        return '—';
    }
    const timestamp = Date.parse(raw);
    if (Number.isNaN(timestamp)) {
        return raw;
    }
    return new Date(timestamp).toLocaleString('ru-RU');
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
        <ContactPresenceBadges
            title="Каналы связи"
            website={lead.website}
            phone={lead.phone}
            email={lead.email}
            telegramUrl={lead.telegram_url}
            whatsappUrl={lead.whatsapp_url}
            hasMessenger={extractHasMessengers(lead)}
        />
        <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge variant="outline">Лучший канал: {formatLeadChannel(bestAvailableOutreachChannel(lead))}</Badge>
            {selectedChannelWarning(lead, lead.selected_channel) ? (
                <Badge variant="destructive" className="font-normal">
                    <TriangleAlert className="mr-1 h-3 w-3" />
                    {selectedChannelWarning(lead, lead.selected_channel)}
                </Badge>
            ) : null}
        </div>
        <ContactStack lead={lead} />
        {buildLeadAuditLanguageLinks(lead).length > 0 && (
            <div className="flex flex-wrap gap-2 text-sm">
                {buildLeadAuditLanguageLinks(lead).map((item) => (
                    <a key={item.language} href={item.href} target="_blank" rel="noreferrer" className="underline text-primary">
                        Аудит {item.label}
                    </a>
                ))}
            </div>
        )}
    </div>
);

export const ProspectingManagement: React.FC = () => {
    const [query, setQuery] = useState('');
    const [location, setLocation] = useState('');
    const [searchSource, setSearchSource] = useState<'apify_yandex' | 'apify_2gis' | 'apify_google' | 'apify_apple'>('apify_yandex');
    const [limit, setLimit] = useState(20);
    const [manualLeadUrl, setManualLeadUrl] = useState('');
    const [manualLeadName, setManualLeadName] = useState('');
    const [manualLeadCategory, setManualLeadCategory] = useState('');
    const [manualLeadBusy, setManualLeadBusy] = useState(false);
    const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceTab>('raw');
    const [outreachTab, setOutreachTab] = useState<OutreachTab>('drafts');
    const [pipelineView, setPipelineView] = useState<PipelineViewMode>('kanban');
    const [quickFilter, setQuickFilter] = useState<PipelineQuickFilter>('all');
    const [pipelineSearch, setPipelineSearch] = useState('');
    const [intakeOpen, setIntakeOpen] = useState(false);
    const [filtersOpen, setFiltersOpen] = useState(false);
    const [results, setResults] = useState<Lead[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState<Record<string, boolean>>({});
    const [savedLeads, setSavedLeads] = useState<Lead[]>([]);
    const [leadGroups, setLeadGroups] = useState<LeadGroup[]>([]);
    const [loadingLeads, setLoadingLeads] = useState(false);
    const [loadingGroups, setLoadingGroups] = useState(false);
    const [searchJobId, setSearchJobId] = useState<string | null>(null);
    const [searchJob, setSearchJob] = useState<SearchJob | null>(null);
    const [filters, setFilters] = useState<LeadFilters>(emptyFilters);
    const [shortlistLoading, setShortlistLoading] = useState<Record<string, string>>({});
    const [languageLoading, setLanguageLoading] = useState<Record<string, boolean>>({});
    const [selectionLoading, setSelectionLoading] = useState<Record<string, string>>({});
    const [drafts, setDrafts] = useState<OutreachDraft[]>([]);
    const [loadingDrafts, setLoadingDrafts] = useState(false);
    const [draftBusy, setDraftBusy] = useState<Record<string, string>>({});
    const [draftEdits, setDraftEdits] = useState<Record<string, string>>({});
    const [sendReadyDrafts, setSendReadyDrafts] = useState<OutreachDraft[]>([]);
    const [sendBatches, setSendBatches] = useState<OutreachBatch[]>([]);
    const [telegramAppStatus, setTelegramAppStatus] = useState<TelegramAppStatus | null>(null);
    const [telegramReplySyncSummary, setTelegramReplySyncSummary] = useState<TelegramReplySyncSummary | null>(null);
    const [sendDailyCap, setSendDailyCap] = useState(10);
    const [loadingSendQueue, setLoadingSendQueue] = useState(false);
    const [sendQueueBusy, setSendQueueBusy] = useState<Record<string, string>>({});
    const [reactions, setReactions] = useState<OutreachReaction[]>([]);
    const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({});
    const [reactionBusy, setReactionBusy] = useState<Record<string, string>>({});
    const [followUpDrafts, setFollowUpDrafts] = useState<Record<string, string>>({});
    const [searchPollError, setSearchPollError] = useState<string | null>(null);
    const [importJson, setImportJson] = useState('');
    const [importBusy, setImportBusy] = useState(false);
    const [importResult, setImportResult] = useState<string | null>(null);
    const [draftChannelFilter, setDraftChannelFilter] = useState('');
    const [draftContactFilter, setDraftContactFilter] = useState<OutreachContactFilter>('');
    const [draftStatusFilter, setDraftStatusFilter] = useState('');
    const [queueChannelFilter, setQueueChannelFilter] = useState('');
    const [queueContactFilter, setQueueContactFilter] = useState<OutreachContactFilter>('');
    const [queueViewFilter, setQueueViewFilter] = useState<'all' | 'today' | 'attention'>('all');
    const [sentContactFilter, setSentContactFilter] = useState<OutreachContactFilter>('');
    const [sentStateFilter, setSentStateFilter] = useState<SentStateFilter>('');
    const [outreachDetailOpen, setOutreachDetailOpen] = useState(false);
    const [selectedDraftDetailId, setSelectedDraftDetailId] = useState<string | null>(null);
    const [selectedDraftIds, setSelectedDraftIds] = useState<string[]>([]);
    const [selectedSendReadyDraftIds, setSelectedSendReadyDraftIds] = useState<string[]>([]);
    const [selectedOutreachLeadIds, setSelectedOutreachLeadIds] = useState<string[]>([]);
    const [selectedPipelineLeadIds, setSelectedPipelineLeadIds] = useState<string[]>([]);
    const [selectedQueueItemIds, setSelectedQueueItemIds] = useState<string[]>([]);
    const [selectedQueueItemId, setSelectedQueueItemId] = useState<string | null>(null);
    const [selectedSentLeadId, setSelectedSentLeadId] = useState<string | null>(null);
    const [bulkOutreachChannel, setBulkOutreachChannel] = useState<'telegram' | 'whatsapp' | 'max' | 'email' | 'manual'>('telegram');
    const [previewLead, setPreviewLead] = useState<Lead | null>(null);
    const [previewSnapshot, setPreviewSnapshot] = useState<LeadCardPreview | null>(null);
    const [previewLoadingId, setPreviewLoadingId] = useState<string | null>(null);
    const [previewError, setPreviewError] = useState<string | null>(null);
    const [previewAuditPageBusy, setPreviewAuditPageBusy] = useState(false);
    const [previewAuditPageUrl, setPreviewAuditPageUrl] = useState<string | null>(null);
    const [previewAuditPageLanguage, setPreviewAuditPageLanguage] = useState('en');
    const [previewAuditPageEnabledLanguages, setPreviewAuditPageEnabledLanguages] = useState<string[]>(['en']);
    const [previewContactsBusy, setPreviewContactsBusy] = useState(false);
    const [previewParseBusy, setPreviewParseBusy] = useState(false);
    const [previewAutoRefreshing, setPreviewAutoRefreshing] = useState(false);
    const [groupModalOpen, setGroupModalOpen] = useState(false);
    const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
    const [selectedGroupDetail, setSelectedGroupDetail] = useState<LeadGroup | null>(null);
    const [selectedGroupLeads, setSelectedGroupLeads] = useState<Lead[]>([]);
    const [groupBusy, setGroupBusy] = useState<Record<string, boolean>>({});
    const [parseActionBusy, setParseActionBusy] = useState<Record<string, boolean>>({});
    const [draggingLeadId, setDraggingLeadId] = useState<string | null>(null);
    const [dropColumnId, setDropColumnId] = useState<PipelineBoardColumnId | null>(null);
    const [statusUpdateBusy, setStatusUpdateBusy] = useState<Record<string, boolean>>({});
    const [statusUpdateError, setStatusUpdateError] = useState<Record<string, string>>({});

    const displayedSearchResults = useMemo(() => {
        if (Array.isArray(results) && results.length > 0) {
            return results;
        }
        if (searchJob?.status === 'completed' && Array.isArray(searchJob.results) && searchJob.results.length > 0) {
            return searchJob.results.map((item) => ({ ...item, status: item.status || 'new' }));
        }
        return [];
    }, [results, searchJob]);

    const unprocessedLeads = useMemo(
        () =>
            savedLeads
                .filter(isDisplayableLead)
                .filter((lead) => getLeadPipelineStatus(lead) === PIPELINE_UNPROCESSED),
        [savedLeads]
    );

    const pipelineEligibleLeads = useMemo(
        () =>
            savedLeads
                .filter(isDisplayableLead)
                .filter((lead) => !isRawImportedLead(lead))
                .filter((lead) => getLeadPipelineStatus(lead) !== PIPELINE_UNPROCESSED),
        [savedLeads]
    );

    const savedLeadDuplicateReasonMap = useMemo(() => {
        const map = new Map<string, SearchDuplicateReason>();
        pipelineEligibleLeads.forEach((lead) => {
            buildStrictDuplicateReasons(lead).forEach(({ key, code, label }) => {
                if (!map.has(key)) {
                    map.set(key, { code, label });
                }
            });
        });
        return map;
    }, [pipelineEligibleLeads]);

    const searchResultDuplicateAnalysis = useMemo(
        () =>
            displayedSearchResults.map((lead) => {
                const matchedReasons = buildStrictDuplicateReasons(lead)
                    .filter(({ key }) => savedLeadDuplicateReasonMap.has(key))
                    .map(({ key }) => savedLeadDuplicateReasonMap.get(key))
                    .filter((item): item is SearchDuplicateReason => Boolean(item));
                const dedupedReasons = Array.from(new Map(matchedReasons.map((item) => [item.code, item])).values());
                return {
                    lead,
                    duplicateReasons: dedupedReasons,
                };
            }),
        [displayedSearchResults, savedLeadDuplicateReasonMap]
    );
    const duplicateSearchResults = useMemo(
        () => searchResultDuplicateAnalysis.filter((item) => item.duplicateReasons.length > 0),
        [searchResultDuplicateAnalysis]
    );
    const unresolvedSearchResults = useMemo(
        () => searchResultDuplicateAnalysis.filter((item) => item.duplicateReasons.length === 0).map((item) => item.lead),
        [searchResultDuplicateAnalysis]
    );
    const duplicateReasonSummary = useMemo(() => {
        const counts = new Map<string, { label: string; count: number }>();
        duplicateSearchResults.forEach((item) => {
            item.duplicateReasons.forEach((reason) => {
                const current = counts.get(reason.code);
                if (current) {
                    current.count += 1;
                } else {
                    counts.set(reason.code, { label: reason.label, count: 1 });
                }
            });
        });
        return Array.from(counts.values()).sort((left, right) => right.count - left.count);
    }, [duplicateSearchResults]);
    const displayedSearchResultsCount = displayedSearchResults.length;
    const unresolvedSearchResultsCount = unresolvedSearchResults.length;
    const duplicateSearchResultsCount = duplicateSearchResults.length;
    const searchJobResultCount = searchJob?.status === 'completed'
        ? Number(searchJob.result_count || displayedSearchResultsCount || 0)
        : displayedSearchResultsCount;

    const lastSearchSummary = useMemo(() => {
        if (loading && !searchJob) {
            return {
                title: 'Идёт запуск поиска',
                hint: 'Ждём постановки задачи и первого статуса от Apify.',
                tone: 'border-sky-200 bg-sky-50 text-sky-900',
            };
        }
        if (searchJob) {
            if (searchJob.status === 'failed') {
                return {
                    title: 'Последний запуск завершился с ошибкой',
                    hint: searchJob.error_text || 'Не удалось завершить поиск.',
                    tone: 'border-red-200 bg-red-50 text-red-900',
                };
            }
            if (searchJob.status === 'completed') {
                return {
                    title: 'Последний запуск завершён',
                    hint: unresolvedSearchResultsCount > 0
                        ? `Осталось разобрать ${unresolvedSearchResultsCount} компаний из ${searchJob.result_count || 0}. Дублей в этом поиске: ${duplicateSearchResultsCount}.`
                        : `Все ${searchJob.result_count || 0} компаний из последней выдачи уже разобраны или распознаны как дубли.`,
                    tone: 'border-emerald-200 bg-emerald-50 text-emerald-900',
                };
            }
            return {
                title: 'Поиск продолжается',
                hint: searchPollError || 'Apify ещё собирает выдачу. Обновление результатов произойдёт автоматически.',
                tone: 'border-sky-200 bg-sky-50 text-sky-900',
            };
        }
        return {
            title: 'Последний запуск ещё не выполнялся',
            hint: 'Сначала задайте источник, запрос и город. После запуска здесь появится статус и краткий итог.',
            tone: 'border-gray-200 bg-gray-50 text-gray-800',
        };
    }, [duplicateSearchResultsCount, loading, searchJob, searchPollError, unresolvedSearchResultsCount]);

    useEffect(() => {
        if (typeof window === 'undefined') {
            return;
        }
        if (Array.isArray(results) && results.length > 0) {
            window.localStorage.setItem(LAST_SEARCH_RESULTS_STORAGE_KEY, JSON.stringify(results));
        }
    }, [results]);

    useEffect(() => {
        if (typeof window === 'undefined') {
            return;
        }
        if (displayedSearchResultsCount === 0) {
            return;
        }
        if (unresolvedSearchResultsCount > 0) {
            return;
        }
        setResults([]);
        setSearchJob((prev) => {
            if (!prev || prev.status !== 'completed') {
                return prev;
            }
            if (!Array.isArray(prev.results) || prev.results.length === 0) {
                return prev;
            }
            return { ...prev, results: [] };
        });
        window.localStorage.removeItem(LAST_SEARCH_RESULTS_STORAGE_KEY);
    }, [displayedSearchResultsCount, unresolvedSearchResultsCount]);


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

    const fetchSavedLeads = useCallback(async () => {
        setLoadingLeads(true);
        try {
            const response = await api.get('/admin/prospecting/leads', {
                params: {
                    ...activeFilters,
                    compact: '1',
                    include_groups: '0',
                    include_timeline: '0',
                },
            });
            setSavedLeads(response.data.leads || []);
        } catch (error) {
            console.error('Error fetching leads:', error);
        } finally {
            setLoadingLeads(false);
        }
    }, [activeFilters]);

    const fetchLeadGroups = useCallback(async () => {
        setLoadingGroups(true);
        try {
            const response = await api.get('/admin/prospecting/groups');
            setLeadGroups(response.data?.groups || []);
        } catch (error) {
            console.error('Error fetching lead groups:', error);
        } finally {
            setLoadingGroups(false);
        }
    }, []);

    const fetchDrafts = useCallback(async () => {
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
    }, []);

    const fetchSendQueue = useCallback(async () => {
        setLoadingSendQueue(true);
        try {
            const queueResponse = await api.get('/admin/prospecting/send-batches');
            setSendReadyDrafts(queueResponse.data?.ready_drafts || []);
            setSendBatches(queueResponse.data?.batches || []);
            setReactions(queueResponse.data?.reactions || []);
            setSendDailyCap(queueResponse.data?.daily_cap || 10);
            try {
                const healthResponse = await api.get('/admin/prospecting/outbound/health');
                setTelegramAppStatus(healthResponse.data?.telegram_app || null);
            } catch (healthError) {
                console.error('Error fetching outbound health:', healthError);
                setTelegramAppStatus(null);
            }
        } catch (error) {
            console.error('Error fetching send queue:', error);
        } finally {
            setLoadingSendQueue(false);
        }
    }, []);

    useEffect(() => {
        void fetchSavedLeads();
    }, [fetchSavedLeads]);

    useEffect(() => {
        const availableIds = new Set(savedLeads.map((lead) => String(lead.id || '')).filter(Boolean));
        setSelectedPipelineLeadIds((prev) => prev.filter((id) => availableIds.has(id)));
    }, [savedLeads]);

    useEffect(() => {
        void fetchLeadGroups();
    }, [fetchLeadGroups]);

    useEffect(() => {
        void fetchDrafts();
    }, [fetchDrafts]);

    useEffect(() => {
        void fetchSendQueue();
    }, [fetchSendQueue]);

    useEffect(() => {
        let cancelled = false;
        const hydrateLatestSearchJob = async () => {
            try {
                const storedActiveJobId = window.localStorage.getItem(ACTIVE_SEARCH_JOB_STORAGE_KEY);
                const storedLastJobRaw = window.localStorage.getItem(LAST_SEARCH_JOB_STORAGE_KEY);
                if (storedLastJobRaw) {
                    try {
                        const storedLastJob = JSON.parse(storedLastJobRaw) as SearchJob;
                        if (!cancelled && storedLastJob?.id) {
                            setSearchJob(storedLastJob);
                            if (storedLastJob.status === 'completed') {
                                const storedResults = (storedLastJob.results || []).map((result: Lead) => ({ ...result, status: result.status || 'new' }));
                                setResults(storedResults);
                            }
                        }
                    } catch (error) {
                        console.warn('Could not parse last stored search job:', error);
                    }
                }
                const storedResultsRaw = window.localStorage.getItem(LAST_SEARCH_RESULTS_STORAGE_KEY);
                if (storedResultsRaw) {
                    try {
                        const storedResults = JSON.parse(storedResultsRaw) as Lead[];
                        if (!cancelled && Array.isArray(storedResults) && storedResults.length > 0) {
                            setResults(storedResults.map((item) => ({ ...item, status: item.status || 'new' })));
                        }
                    } catch (error) {
                        console.warn('Could not parse stored search results:', error);
                    }
                }

                const response = await api.get('/admin/prospecting/search-job/latest');
                const latestJob = (response.data?.job || null) as SearchJob | null;
                if (cancelled || !latestJob?.id) {
                    if (!cancelled && storedActiveJobId) {
                        setSearchJobId(storedActiveJobId);
                        setLoading(true);
                    }
                    return;
                }

                setSearchJob(latestJob);
                window.localStorage.setItem(LAST_SEARCH_JOB_STORAGE_KEY, JSON.stringify(latestJob));

                if (latestJob.status === 'completed') {
                    const newResults = (latestJob.results || []).map((result: Lead) => ({ ...result, status: result.status || 'new' }));
                    if (newResults.length > 0) {
                        setResults(newResults);
                    }
                    void fetchSavedLeads();
                    setLoading(false);
                    setSearchJobId(null);
                    window.localStorage.removeItem(ACTIVE_SEARCH_JOB_STORAGE_KEY);
                    return;
                }

                if (latestJob.status === 'failed') {
                    setLoading(false);
                    setSearchJobId(null);
                    window.localStorage.removeItem(ACTIVE_SEARCH_JOB_STORAGE_KEY);
                    return;
                }

                setLoading(true);
                setSearchJobId(latestJob.id);
                window.localStorage.setItem(ACTIVE_SEARCH_JOB_STORAGE_KEY, latestJob.id);
            } catch (error) {
                console.error('Error hydrating latest prospecting search job:', error);
            }
        };

        void hydrateLatestSearchJob();

        return () => {
            cancelled = true;
        };
    }, [fetchSavedLeads]);

    useEffect(() => {
        if (!searchJobId) {
            return;
        }

        let cancelled = false;
        let consecutivePollFailures = 0;
        const poll = async () => {
            try {
                const response = await api.get(`/admin/prospecting/search-job/${searchJobId}`);
                const job = response.data?.job as SearchJob;
                if (cancelled || !job) {
                    return;
                }
                consecutivePollFailures = 0;
                setSearchPollError(null);
                setSearchJob(job);
                window.localStorage.setItem(LAST_SEARCH_JOB_STORAGE_KEY, JSON.stringify(job));
                if (job.status === 'completed') {
                    const newResults = (job.results || []).map((result: Lead) => ({ ...result, status: result.status || 'new' }));
                    if (newResults.length > 0) {
                        setResults(newResults);
                    }
                    void fetchSavedLeads();
                    setLoading(false);
                    setSearchJobId(null);
                    window.localStorage.removeItem(ACTIVE_SEARCH_JOB_STORAGE_KEY);
                    return;
                }
                if (job.status === 'failed') {
                    setLoading(false);
                    setSearchJobId(null);
                    window.localStorage.removeItem(ACTIVE_SEARCH_JOB_STORAGE_KEY);
                    return;
                }
                window.setTimeout(poll, 2000);
            } catch (error) {
                console.error('Error polling prospecting job:', error);
                if (!cancelled) {
                    consecutivePollFailures += 1;
                    if (consecutivePollFailures >= 3) {
                        setSearchPollError('Есть временные проблемы со связью. Поиск продолжается, повторяем опрос...');
                    }
                    window.setTimeout(poll, 3000);
                }
            }
        };

        void poll();

        return () => {
            cancelled = true;
        };
    }, [searchJobId, fetchSavedLeads]);

    const syncTelegramReplies = async (batchId?: string) => {
        await withSendQueueBusy('telegram-reply-sync', 'sync', async () => {
            const response = await api.post('/admin/prospecting/telegram-app/replies/sync', {
                batch_id: batchId || undefined,
                limit: 50,
            });
            setTelegramReplySyncSummary({
                picked: Number(response.data?.picked || 0),
                imported: Number(response.data?.imported || 0),
                duplicates: Number(response.data?.duplicates || 0),
                noops: Number(response.data?.noops || 0),
                failed: Number(response.data?.failed || 0),
            });
            await fetchSendQueue();
        });
    };

    const refreshProspectingData = useCallback(async (scope: 'all' | 'leads' | 'drafts_queue' | 'leads_queue' = 'all') => {
        if (scope === 'leads') {
            await fetchSavedLeads();
            return;
        }
        if (scope === 'drafts_queue') {
            await Promise.all([fetchDrafts(), fetchSendQueue()]);
            return;
        }
        if (scope === 'leads_queue') {
            await Promise.all([fetchSavedLeads(), fetchSendQueue()]);
            return;
        }
        await Promise.all([fetchSavedLeads(), fetchDrafts(), fetchSendQueue()]);
    }, [fetchDrafts, fetchSavedLeads, fetchSendQueue]);

    const withDraftBusy = async (key: string, state: string, action: () => Promise<void>) => {
        setDraftBusy((prev) => ({ ...prev, [key]: state }));
        try {
            await action();
        } catch (error) {
            console.error(`Draft action failed (${state})`, error);
        } finally {
            setDraftBusy((prev) => {
                const next = { ...prev };
                delete next[key];
                return next;
            });
        }
    };

    const withSelectionBusy = async (key: string, state: string, action: () => Promise<void>) => {
        try {
            await withBusyState(setSelectionLoading, key, state, action);
        } catch (error) {
            console.error(`Selection action failed (${state})`, error);
        }
    };

    const withSendQueueBusy = async (key: string, state: string, action: () => Promise<void>) => {
        setSendQueueBusy((prev) => ({ ...prev, [key]: state }));
        try {
            await action();
        } catch (error) {
            console.error(`Send queue action failed (${state})`, error);
        } finally {
            setSendQueueBusy((prev) => {
                const next = { ...prev };
                delete next[key];
                return next;
            });
        }
    };

    const withReactionBusy = async (key: string, state: string, action: () => Promise<void>) => {
        try {
            await withBusyState(setReactionBusy, key, state, action);
        } catch (error) {
            console.error(`Reaction action failed (${state})`, error);
        }
    };

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query || !location) return;

        setLoading(true);
        setSearchJob(null);
        setSearchJobId(null);
        setSearchPollError(null);
        window.localStorage.removeItem(ACTIVE_SEARCH_JOB_STORAGE_KEY);
        window.localStorage.removeItem(LAST_SEARCH_RESULTS_STORAGE_KEY);
        try {
            const response = await api.post('/admin/prospecting/search', {
                query,
                location,
                source: searchSource,
                limit: Number(limit)
            });
            setResults([]);
            const jobId = String(response.data.job_id || '');
            setSearchJobId(jobId);
            if (jobId) {
                window.localStorage.setItem(ACTIVE_SEARCH_JOB_STORAGE_KEY, jobId);
            }
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
        } catch (error: unknown) {
            console.error('Error importing leads:', error);
            const message = getRequestErrorMessage(error, 'Не удалось импортировать лиды');
            setImportResult(`Ошибка импорта: ${message}`);
        } finally {
            setImportBusy(false);
        }
    };

    const saveLead = async (lead: Lead, targetStatus: string = 'new') => {
        const key = lead.source_external_id || lead.google_id || lead.name;
        setSaving(prev => ({ ...prev, [key]: true }));
        try {
            await api.post('/admin/prospecting/save', {
                lead: {
                    ...lead,
                    status: targetStatus,
                    pipeline_status: PIPELINE_UNPROCESSED,
                },
            });
            await Promise.all([fetchSavedLeads(), fetchLeadGroups()]);
        } catch (error) {
            console.error('Error saving lead:', error);
        } finally {
            setSaving(prev => ({ ...prev, [key]: false }));
        }
    };

    const normalizeRequestedPipelineStatus = (value: string) => {
        const normalized = String(value || '').trim().toLowerCase();
        if (!normalized) {
            return normalized;
        }
        if (normalized === 'new') {
            return PIPELINE_UNPROCESSED;
        }
        if ([shortlistApproved, selectedForOutreach, channelSelected, 'draft_ready', queuedForSend].includes(normalized)) {
            return PIPELINE_IN_PROGRESS;
        }
        if (normalized === 'deferred') {
            return PIPELINE_POSTPONED;
        }
        if ([shortlistRejected, 'rejected'].includes(normalized)) {
            return PIPELINE_NOT_RELEVANT;
        }
        if (normalized === 'sent') {
            return PIPELINE_CONTACTED;
        }
        if (normalized === 'delivered') {
            return PIPELINE_WAITING_REPLY;
        }
        if (normalized === 'responded') {
            return PIPELINE_REPLIED;
        }
        if (['qualified', 'converted'].includes(normalized)) {
            return PIPELINE_CONVERTED;
        }
        return normalized;
    };

    const updateLeadStatusOptimistic = async (leadId: string, nextStatus: string) => {
        if (!leadId) {
            return;
        }
        const normalizedPipelineStatus = normalizeRequestedPipelineStatus(nextStatus);
        if (normalizedPipelineStatus === PIPELINE_POSTPONED) {
            await moveLeadToPostponed(leadId);
            return;
        }
        if (normalizedPipelineStatus === PIPELINE_NOT_RELEVANT) {
            await moveLeadToNotRelevant(leadId);
            return;
        }
        setStatusUpdateBusy((prev) => ({ ...prev, [leadId]: true }));
        setStatusUpdateError((prev) => {
            const next = { ...prev };
            delete next[leadId];
            return next;
        });
        const previousLeads = savedLeads;
        setSavedLeads((prev) =>
            prev.map((lead) => (
                lead.id === leadId
                    ? { ...lead, status: nextStatus, pipeline_status: normalizedPipelineStatus || lead.pipeline_status }
                    : lead
            ))
        );
        setPreviewLead((prev) => (
            prev && prev.id === leadId
                ? { ...prev, status: nextStatus, pipeline_status: normalizedPipelineStatus || prev.pipeline_status }
                : prev
        ));
        try {
            await api.post(`/admin/prospecting/lead/${leadId}/status`, {
                pipeline_status: normalizedPipelineStatus || nextStatus,
                status: nextStatus,
            });
        } catch (error) {
            console.error('Error updating lead status:', error);
            setSavedLeads(previousLeads);
            const previousLead = previousLeads.find((lead) => lead.id === leadId) || null;
            setPreviewLead((prev) => (prev && prev.id === leadId ? previousLead : prev));
            setStatusUpdateError((prev) => ({ ...prev, [leadId]: 'Не удалось обновить статус. Попробуйте ещё раз.' }));
        } finally {
            setStatusUpdateBusy((prev) => {
                const next = { ...prev };
                delete next[leadId];
                return next;
            });
        }
    };

    const moveLeadToPostponed = async (leadId: string) => {
        const comment = window.prompt('Почему откладываем этого лида?');
        if (!comment || !comment.trim()) {
            return;
        }
        await api.post(`/admin/prospecting/lead/${leadId}/status`, {
            pipeline_status: PIPELINE_POSTPONED,
            postponed_comment: comment.trim(),
            comment: comment.trim(),
        });
        await Promise.all([fetchSavedLeads(), fetchLeadGroups()]);
    };

    const moveLeadToNotRelevant = async (leadId: string) => {
        const reason = window.prompt('Причина: not_icp / duplicate / closed_business / no_contacts / weak_potential / wrong_geo / other', 'other');
        if (!reason || !reason.trim()) {
            return;
        }
        const normalizedReason = reason.trim().toLowerCase();
        const comment = window.prompt('Комментарий к причине (обязательно для other):', normalizedReason === 'other' ? '' : undefined) || '';
        await api.post(`/admin/prospecting/lead/${leadId}/status`, {
            pipeline_status: PIPELINE_NOT_RELEVANT,
            disqualification_reason: normalizedReason,
            disqualification_comment: comment.trim() || undefined,
            comment: comment.trim() || undefined,
        });
        await Promise.all([fetchSavedLeads(), fetchLeadGroups()]);
    };

    const saveSearchResultAsNotRelevant = async (lead: Lead) => {
        const reason = window.prompt('Причина: not_icp / duplicate / closed_business / no_contacts / weak_potential / wrong_geo / other', 'other');
        if (!reason || !reason.trim()) {
            return;
        }
        const normalizedReason = reason.trim().toLowerCase();
        const comment = window.prompt('Комментарий к причине (обязательно для other):', normalizedReason === 'other' ? '' : undefined) || '';
        if (normalizedReason === 'other' && !comment.trim()) {
            return;
        }
        await saveLead(
            {
                ...lead,
                pipeline_status: PIPELINE_NOT_RELEVANT,
                disqualification_reason: normalizedReason,
                disqualification_comment: comment.trim() || undefined,
            },
            shortlistRejected
        );
    };

    const markLeadManualContact = async (leadId: string, channel: string = 'manual') => {
        const comment = window.prompt('Комментарий к ручной отправке (необязательно):') || '';
        await api.post(`/admin/prospecting/lead/${leadId}/manual-contact`, {
            channel,
            comment: comment.trim() || undefined,
        });
        await Promise.all([fetchSavedLeads(), fetchSendQueue()]);
    };

    const createLeadGroupFromIds = async (leadIds: string[]) => {
        const normalizedIds = Array.from(new Set(leadIds.filter(Boolean)));
        if (normalizedIds.length === 0) {
            return;
        }
        const name = window.prompt('Название группы лидов');
        if (!name || !name.trim()) {
            return;
        }
        await api.post('/admin/prospecting/groups', {
            name: name.trim(),
            lead_ids: normalizedIds,
        });
        setSelectedPipelineLeadIds([]);
        await fetchLeadGroups();
        setActiveWorkspace('groups');
    };

    const addLeadToExistingGroup = async (leadId: string) => {
        const availableGroups = leadGroups.filter((group) => group.id);
        if (availableGroups.length === 0) {
            toast.error('Сначала создайте хотя бы одну группу');
            return;
        }

        const promptText = availableGroups
            .map((group, index) => `${index + 1}. ${group.name}`)
            .join('\n');
        const rawChoice = window.prompt(`Выберите номер группы:\n${promptText}`);
        const choice = Number.parseInt(String(rawChoice || '').trim(), 10);
        if (!Number.isFinite(choice) || choice < 1 || choice > availableGroups.length) {
            return;
        }

        const targetGroup = availableGroups[choice - 1];
        if (!targetGroup?.id) {
            return;
        }

        setGroupBusy((prev) => ({ ...prev, [targetGroup.id]: true }));
        try {
            await api.post(`/admin/prospecting/groups/${targetGroup.id}/add-leads`, { lead_ids: [leadId] });
            await Promise.all([fetchSavedLeads(), fetchLeadGroups()]);
            toast.success(`Лид добавлен в группу «${targetGroup.name || 'без названия'}»`);
            if (selectedGroupId === targetGroup.id) {
                await openLeadGroup(targetGroup.id);
            }
        } catch (error) {
            console.error('Error adding single lead to existing group:', error);
            toast.error('Не удалось добавить лида в группу');
        } finally {
            setGroupBusy((prev) => {
                const next = { ...prev };
                delete next[targetGroup.id];
                return next;
            });
        }
    };

    const openLeadGroup = async (groupId: string) => {
        setSelectedGroupId(groupId);
        setGroupModalOpen(true);
        setGroupBusy((prev) => ({ ...prev, [groupId]: true }));
        try {
            const response = await api.get(`/admin/prospecting/groups/${groupId}`);
            setSelectedGroupDetail(response.data?.group || null);
            setSelectedGroupLeads(response.data?.leads || []);
        } catch (error) {
            console.error('Error loading lead group:', error);
            setSelectedGroupDetail(null);
            setSelectedGroupLeads([]);
        } finally {
            setGroupBusy((prev) => {
                const next = { ...prev };
                delete next[groupId];
                return next;
            });
        }
    };

    const removeLeadFromGroup = async (groupId: string, leadId: string) => {
        await api.post(`/admin/prospecting/groups/${groupId}/remove-leads`, { lead_ids: [leadId] });
        await Promise.all([fetchSavedLeads(), fetchLeadGroups(), openLeadGroup(groupId)]);
    };

    const addSelectedLeadsToGroup = async (groupId: string) => {
        const normalizedIds = Array.from(new Set(selectedPipelineLeadIds.filter(Boolean)));
        if (normalizedIds.length === 0) {
            return;
        }
        setGroupBusy((prev) => ({ ...prev, [groupId]: true }));
        try {
            await api.post(`/admin/prospecting/groups/${groupId}/add-leads`, { lead_ids: normalizedIds });
            setSelectedPipelineLeadIds([]);
            await Promise.all([fetchSavedLeads(), fetchLeadGroups()]);
            if (selectedGroupId === groupId) {
                await openLeadGroup(groupId);
            }
            toast.success('Выбранные лиды добавлены в группу');
        } catch (error) {
            console.error('Error adding leads to group:', error);
            toast.error('Не удалось добавить выбранные лиды в группу');
        } finally {
            setGroupBusy((prev) => {
                const next = { ...prev };
                delete next[groupId];
                return next;
            });
        }
    };

    const handleLeadDragStart = (leadId: string) => (event: React.DragEvent<HTMLDivElement>) => {
        if (!leadId) {
            return;
        }
        event.dataTransfer.setData('text/plain', leadId);
        event.dataTransfer.effectAllowed = 'move';
        setDraggingLeadId(leadId);
    };

    const handleLeadDragEnd = () => {
        setDraggingLeadId(null);
        setDropColumnId(null);
    };

    const handleColumnDragOver = (columnId: PipelineBoardColumnId) => (event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        if (dropColumnId !== columnId) {
            setDropColumnId(columnId);
        }
    };

    const handleColumnDrop = (columnId: PipelineBoardColumnId) => async (event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        const leadId = event.dataTransfer.getData('text/plain');
        setDropColumnId(null);
        setDraggingLeadId(null);
        if (!leadId) {
            return;
        }
        const lead = savedLeads.find((item) => item.id === leadId);
        if (!lead) {
            return;
        }
        const nextStatus = pipelineBoardColumnMeta[columnId].statusToSet;
        if (lead.status === nextStatus) {
            return;
        }
        await updateLeadStatusOptimistic(leadId, nextStatus);
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

    const chooseChannel = async (leadId: string, channel: 'telegram' | 'whatsapp' | 'email' | 'manual') => {
        await withSelectionBusy(leadId, channel, async () => {
            await api.post(`/admin/prospecting/lead/${leadId}/channel`, { channel });
            await fetchSavedLeads();
        });
    };

    const bulkAssignOutreachChannel = async () => {
        const leadIds = filteredContactLeads
            .filter((lead) => lead.id && selectedOutreachLeadIds.includes(lead.id))
            .map((lead) => lead.id as string);
        if (leadIds.length === 0) return;

        await withSelectionBusy('bulkChannel', bulkOutreachChannel, async () => {
            await Promise.all(
                leadIds.map((leadId) => api.post(`/admin/prospecting/lead/${leadId}/channel`, { channel: bulkOutreachChannel }))
            );
            setSelectedOutreachLeadIds([]);
            await fetchSavedLeads();
        });
    };

    const deleteLeadEverywhere = async (leadId: string) => {
        await withSelectionBusy(leadId, 'delete', async () => {
            await api.delete(`/admin/prospecting/lead/${leadId}`);
            setSelectedOutreachLeadIds((prev) => prev.filter((id) => id !== leadId));
            if (previewLead?.id === leadId) {
                closeLeadPreview();
            }
            await refreshProspectingData('all');
        });
    };

    const generateDraft = async (leadId: string) => {
        await withDraftBusy(leadId, 'generate', async () => {
            await api.post(`/admin/prospecting/lead/${leadId}/draft-generate`);
            await refreshProspectingData('all');
        });
    };

    const approveDraft = async (draftId: string) => {
        const approvedText = (draftEdits[draftId] || '').trim();
        if (!approvedText) return;
        await withDraftBusy(draftId, 'approve', async () => {
            await api.post(`/admin/prospecting/drafts/${draftId}/approve`, {
                approved_text: approvedText,
            });
            await refreshProspectingData('drafts_queue');
        });
    };

    const saveDraftEdit = async (draftId: string) => {
        const editedText = (draftEdits[draftId] || '').trim();
        if (!editedText) return;
        await withDraftBusy(draftId, 'save', async () => {
            await api.post(`/admin/prospecting/drafts/${draftId}/save`, {
                edited_text: editedText,
            });
            await fetchDrafts();
        });
    };

    const rejectDraft = async (draftId: string) => {
        await withDraftBusy(draftId, 'reject', async () => {
            await api.post(`/admin/prospecting/drafts/${draftId}/reject`);
            await refreshProspectingData('drafts_queue');
        });
    };

    const deleteDraft = async (draftId: string) => {
        await withDraftBusy(draftId, 'delete', async () => {
            await api.delete(`/admin/prospecting/drafts/${draftId}`);
            setSelectedDraftIds((prev) => prev.filter((id) => id !== draftId));
            await refreshProspectingData('drafts_queue');
        });
    };

    const deleteSelectedDrafts = async () => {
        const draftIds = filteredDrafts.filter((draft) => selectedDraftIds.includes(draft.id)).map((draft) => draft.id);
        if (draftIds.length === 0) return;
        await withDraftBusy('bulkDelete', 'delete', async () => {
            await Promise.all(draftIds.map((draftId) => api.delete(`/admin/prospecting/drafts/${draftId}`)));
            setSelectedDraftIds([]);
            await refreshProspectingData('drafts_queue');
        });
    };

    const approveSelectedDrafts = async () => {
        const draftIds = filteredDrafts
            .filter((draft) => selectedDraftIds.includes(draft.id) && (draftEdits[draft.id] || '').trim())
            .map((draft) => draft.id);
        if (draftIds.length === 0) return;

        await withDraftBusy('bulkApprove', 'approve', async () => {
            await Promise.all(
                draftIds.map((draftId) =>
                    api.post(`/admin/prospecting/drafts/${draftId}/approve`, {
                        approved_text: (draftEdits[draftId] || '').trim(),
                    })
                )
            );
            setSelectedDraftIds([]);
            await refreshProspectingData('drafts_queue');
        });
    };

    const rejectSelectedDrafts = async () => {
        const draftIds = filteredDrafts.filter((draft) => selectedDraftIds.includes(draft.id)).map((draft) => draft.id);
        if (draftIds.length === 0) return;

        await withDraftBusy('bulkReject', 'reject', async () => {
            await Promise.all(draftIds.map((draftId) => api.post(`/admin/prospecting/drafts/${draftId}/reject`)));
            setSelectedDraftIds([]);
            await refreshProspectingData('drafts_queue');
        });
    };

    const markDraftAsSentManually = async (draft: OutreachDraft) => {
        const lead = savedLeadById.get(draft.lead_id);
        if (!lead?.id) {
            toast.error('Не удалось найти лид для ручной отправки');
            return;
        }

        await withDraftBusy(draft.id, 'manual_sent', async () => {
            await api.post(`/admin/prospecting/drafts/${draft.id}/manual-sent`, {});
            await refreshProspectingData('all');
            setActiveWorkspace('outreach');
            setSelectedSentLeadId(lead.id);
            toast.success('Лид отмечен как отправленный вручную и появится в разделе "Отправлено"');
        });
    };

    const createSendBatch = async (draftIds?: string[]) => {
        await withSendQueueBusy('create', 'create', async () => {
            const payload = draftIds && draftIds.length > 0 ? { draft_ids: draftIds } : {};
            await api.post('/admin/prospecting/send-batches', payload);
            setSelectedSendReadyDraftIds([]);
            await refreshProspectingData('leads_queue');
        });
    };

    const approveSendBatch = async (batchId: string) => {
        await withSendQueueBusy(batchId, 'approve', async () => {
            const response = await api.post(`/admin/prospecting/send-batches/${batchId}/approve`, {});
            await fetchSendQueue();
            const summary = response.data?.batch?.dispatch_summary;
            if (summary) {
                const total = Number(summary.total ?? summary.queued ?? 0);
                const sent = Number(summary.sent ?? 0);
                const failed = Number(summary.failed ?? 0);
                alert(`Batch подтверждён: в очередь поставлено ${total}, sent ${sent}, failed ${failed}`);
            }
        });
    };

    const dispatchSendBatch = async (batchId: string) => {
        await withSendQueueBusy(batchId, 'dispatch', async () => {
            const response = await api.post(`/admin/prospecting/send-batches/${batchId}/dispatch`, {});
            await fetchSendQueue();
            const batch = response.data?.batch as OutreachBatch | undefined;
            const summary = batch ? summarizeBatchFromItems(batch) : null;
            if (summary) {
                alert(`Отправка запущена: queued ${summary.queued}, sending ${summary.sending}, sent ${summary.sent}, failed ${summary.failed}`);
            }
        });
    };

    const deleteSendBatch = async (batchId: string) => {
        await withSendQueueBusy(batchId, 'delete', async () => {
            await api.delete(`/admin/prospecting/send-batches/${batchId}`);
            setSelectedQueueItemIds((prev) => prev.filter((id) => !visibleQueueItems.some((item) => item.id === id && item.batch_id === batchId)));
            await refreshProspectingData('leads_queue');
        });
    };

    const cleanupTestBatches = async () => {
        await withSendQueueBusy('cleanupTest', 'cleanup', async () => {
            await api.post('/admin/prospecting/send-batches/cleanup-test', {});
            setSelectedQueueItemIds([]);
            await refreshProspectingData('leads_queue');
        });
    };

    const markDelivery = async (queueId: string, deliveryStatus: 'sent' | 'delivered' | 'failed') => {
        await withSendQueueBusy(queueId, deliveryStatus, async () => {
            await api.post(`/admin/prospecting/send-queue/${queueId}/delivery`, {
                delivery_status: deliveryStatus,
                error_text: deliveryStatus === 'failed' ? 'Manual delivery failure' : undefined,
            });
            await refreshProspectingData('leads_queue');
        });
    };

    const prepareProblemLeadResend = async (lead: Lead, currentChannel?: string | null) => {
        if (!lead.id) {
            toast.error('Не удалось найти лид для переотправки');
            return;
        }

        const alternativeChannel = bestAlternativeOutreachChannel(lead, currentChannel);
        if (!alternativeChannel) {
            toast.error('Для этого лида нет другого доступного канала. Можно отметить отправку вручную.');
            return;
        }

        await withSelectionBusy(lead.id, `resend:${alternativeChannel}`, async () => {
            await api.post(`/admin/prospecting/lead/${lead.id}/channel`, { channel: alternativeChannel });
            await api.post(`/admin/prospecting/lead/${lead.id}/draft-generate-from-audit`, { channel: alternativeChannel });
            await refreshProspectingData('all');
            setActiveWorkspace('outreach');
            setOutreachTab('drafts');
            toast.success(`Подготовили переотправку через ${formatLeadChannel(alternativeChannel)}. Лид перенесён в "Черновики".`);
        });
    };

    const deleteQueueItem = async (queueId: string) => {
        await withSendQueueBusy(queueId, 'delete', async () => {
            await api.delete(`/admin/prospecting/send-queue/${queueId}`);
            setSelectedQueueItemIds((prev) => prev.filter((id) => id !== queueId));
            await refreshProspectingData('leads_queue');
        });
    };

    const bulkDeleteQueueItems = async () => {
        const queueIds = visibleQueueItems.filter((item) => selectedQueueItemIds.includes(item.id)).map((item) => item.id);
        if (queueIds.length === 0) return;
        await withSendQueueBusy('bulkDeleteQueue', 'delete', async () => {
            await Promise.all(queueIds.map((queueId) => api.delete(`/admin/prospecting/send-queue/${queueId}`)));
            setSelectedQueueItemIds([]);
            await refreshProspectingData('leads_queue');
        });
    };

    const bulkMarkDelivery = async (deliveryStatus: 'sent' | 'delivered' | 'failed') => {
        const queueIds = visibleQueueItems.filter((item) => selectedQueueItemIds.includes(item.id)).map((item) => item.id);
        if (queueIds.length === 0) return;

        await withSendQueueBusy('bulkDelivery', deliveryStatus, async () => {
            await Promise.all(
                queueIds.map((queueId) =>
                    api.post(`/admin/prospecting/send-queue/${queueId}/delivery`, {
                        delivery_status: deliveryStatus,
                        error_text: deliveryStatus === 'failed' ? 'Manual bulk delivery failure' : undefined,
                    })
                )
            );
            setSelectedQueueItemIds([]);
            await refreshProspectingData('leads_queue');
        });
    };

    const recordReaction = async (queueId: string, outcome?: 'positive' | 'question' | 'no_response' | 'hard_no') => {
        await withSendQueueBusy(queueId, `reaction:${outcome || 'auto'}`, async () => {
            await api.post(`/admin/prospecting/send-queue/${queueId}/reaction`, {
                raw_reply: (replyDrafts[queueId] || '').trim(),
                outcome,
            });
            await refreshProspectingData('leads_queue');
        });
    };

    const confirmReaction = async (reactionId: string, outcome: 'positive' | 'question' | 'no_response' | 'hard_no') => {
        await withReactionBusy(reactionId, outcome, async () => {
            await api.post(`/admin/prospecting/reactions/${reactionId}/confirm`, { outcome });
            await refreshProspectingData('leads_queue');
        });
    };

    const resetFilters = () => setFilters(emptyFilters);

    const applyPreset = (preset: 'best' | 'messengers' | 'website' | 'no_contacts' | 'low_rating' | 'many_reviews') => {
        switch (preset) {
            case 'best':
                setFilters((prev) => ({
                    ...prev,
                    minRating: '4.5',
                    minReviews: '50',
                }));
                break;
            case 'messengers':
                setFilters((prev) => ({
                    ...prev,
                    hasMessengers: 'yes',
                }));
                break;
            case 'website':
                setFilters((prev) => ({
                    ...prev,
                    hasWebsite: 'yes',
                }));
                break;
            case 'no_contacts':
                setFilters((prev) => ({
                    ...prev,
                    hasWebsite: 'no',
                    hasPhone: 'no',
                    hasEmail: 'no',
                    hasTelegram: 'no',
                    hasWhatsApp: 'no',
                    hasVk: 'no',
                    hasMax: 'no',
                }));
                break;
            case 'low_rating':
                setFilters((prev) => ({
                    ...prev,
                    maxRating: '3.5',
                }));
                break;
            case 'many_reviews':
                setFilters((prev) => ({
                    ...prev,
                    minReviews: '100',
                }));
                break;
            default:
                break;
        }
    };

    const sourceFilteredLeads = useMemo(
        () => pipelineEligibleLeads
            .filter((lead) => !filters.source || (lead.source || '') === filters.source)
            .filter((lead) => matchesBooleanFilter(filters.hasWebsite, Boolean(lead.website)))
            .filter((lead) => matchesBooleanFilter(filters.hasPhone, Boolean(lead.phone)))
            .filter((lead) => matchesBooleanFilter(filters.hasEmail, Boolean(lead.email)))
            .filter((lead) => matchesBooleanFilter(filters.hasMessengers, extractHasMessengers(lead)))
            .filter((lead) => matchesBooleanFilter(filters.hasTelegram, Boolean(lead.telegram_url)))
            .filter((lead) => matchesBooleanFilter(filters.hasWhatsApp, Boolean(lead.whatsapp_url)))
            .filter((lead) => matchesBooleanFilter(filters.hasVk, extractHasVk(lead)))
            .filter((lead) => matchesBooleanFilter(filters.hasMax, extractHasMax(lead))),
        [
            pipelineEligibleLeads,
            filters.source,
            filters.hasWebsite,
            filters.hasPhone,
            filters.hasEmail,
            filters.hasMessengers,
            filters.hasTelegram,
            filters.hasWhatsApp,
            filters.hasVk,
            filters.hasMax,
        ]
    );
    const visiblePipelineLeads = useMemo(() => {
        const normalizedSearch = pipelineSearch.trim().toLowerCase();
        return sourceFilteredLeads.filter((lead) => {
            if (quickFilter === 'without_audit' && hasLeadAudit(lead)) {
                return false;
            }
            if (quickFilter === 'with_audit' && !hasLeadAudit(lead)) {
                return false;
            }
            if (quickFilter === 'priority' && String(lead.status || '').trim().toLowerCase() !== shortlistApproved) {
                return false;
            }
            if (!normalizedSearch) {
                return true;
            }
            const haystack = [
                lead.name,
                lead.category,
                lead.address,
                lead.city,
                lead.phone,
                lead.email,
                lead.website,
            ]
                .filter(Boolean)
                .join(' ')
                .toLowerCase();
            return haystack.includes(normalizedSearch);
        });
    }, [sourceFilteredLeads, quickFilter, pipelineSearch]);
    const contactLeads = useMemo(
        () => sourceFilteredLeads.filter((lead) => lead.status === selectedForOutreach),
        [sourceFilteredLeads]
    );
    const filteredContactLeads = useMemo(
        () =>
            contactLeads.filter(
                (lead) => leadMatchesOutreachContactFilter(lead, queueContactFilter)
            ),
        [contactLeads, queueContactFilter]
    );
    const isContactLeadFilterActive = queueContactFilter !== '';
    const activeContactLeadFilterSummary = useMemo(() => {
        const parts: string[] = [];
        if (queueContactFilter === 'telegram') parts.push('с доступным контактом Telegram');
        else if (queueContactFilter === 'whatsapp') parts.push('с доступным контактом WhatsApp');
        else if (queueContactFilter === 'max') parts.push('с доступным контактом Max');
        else if (queueContactFilter === 'email') parts.push('с доступным контактом Email');
        else if (queueContactFilter === 'vk') parts.push('с VK-кандидатом');

        if (parts.length === 0) {
            return '';
        }
        return `Сейчас видны только лиды ${parts.join(' и ')}.`;
    }, [queueContactFilter]);
    const savedLeadById = useMemo(() => {
        const next = new Map<string, Lead>();
        savedLeads.forEach((lead) => {
            if (lead.id) {
                next.set(lead.id, lead);
            }
        });
        return next;
    }, [savedLeads]);
    const filteredLeadsForKanban = useMemo(() => sourceFilteredLeads, [sourceFilteredLeads]);
    const pipelineBoardColumns = useMemo(() => {
        const buckets: Record<PipelineBoardColumnId, Lead[]> = {
            in_progress: [],
            postponed: [],
            not_relevant: [],
            contacted: [],
            waiting_reply: [],
            replied: [],
            converted: [],
        };
        for (const lead of visiblePipelineLeads) {
            const columnId = leadToPipelineBoardColumn(lead);
            buckets[columnId].push(lead);
        }
        return pipelineBoardColumnOrder.map((columnId) => ({
            id: columnId,
            ...pipelineBoardColumnMeta[columnId],
            leads: buckets[columnId],
        }));
    }, [visiblePipelineLeads]);
    const pipelineBoardTotals = useMemo(() => {
        const totals: Record<PipelineBoardColumnId, number> = {
            in_progress: 0,
            postponed: 0,
            not_relevant: 0,
            contacted: 0,
            waiting_reply: 0,
            replied: 0,
            converted: 0,
        };
        pipelineBoardColumns.forEach((column) => {
            totals[column.id] = column.leads.length;
        });
        return totals;
    }, [pipelineBoardColumns]);
    const positiveReactionCount = useMemo(
        () =>
            reactions.filter((reaction) => {
                const outcome = String(reaction.human_confirmed_outcome || reaction.classified_outcome || '').trim().toLowerCase();
                return outcome === 'positive';
            }).length,
        [reactions]
    );
    const pipelineLeadCount = filteredLeadsForKanban.length;
    const inProgressLeadCount = pipelineBoardTotals.in_progress;
    const postponedLeadCount = pipelineBoardTotals.postponed;
    const notRelevantLeadCount = pipelineBoardTotals.not_relevant;
    const contactedLeadCount = pipelineBoardTotals.contacted;
    const waitingReplyLeadCount = pipelineBoardTotals.waiting_reply;
    const repliedLeadCount = pipelineBoardTotals.replied;
    const convertedLeadCount = pipelineBoardTotals.converted;
    const pipelineHeaderSummary = useMemo(() => {
        let withoutAudit = 0;
        let withAudit = 0;
        let readyToContact = 0;
        let priority = 0;
        sourceFilteredLeads.forEach((lead) => {
            if (hasLeadAudit(lead)) {
                withAudit += 1;
            } else {
                withoutAudit += 1;
            }
            const stage = leadToPipelineBoardColumn(lead);
            if (stage === 'contacted') {
                readyToContact += 1;
            }
            if (stage === 'in_progress') {
                priority += 1;
            }
        });
        return { withoutAudit, withAudit, readyToContact, priority };
    }, [sourceFilteredLeads]);
    const pipelineStageMetrics = useMemo(() => {
        const stages = [
            {
                key: 'in_progress',
                label: 'В работе',
                hint: 'Идёт оценка и подготовка лида',
                count: inProgressLeadCount,
                conversion: formatConversion(inProgressLeadCount, pipelineLeadCount),
            },
            {
                key: 'postponed',
                label: 'Отложенные',
                hint: 'Лиды со следующим шагом на потом',
                count: postponedLeadCount,
                conversion: formatConversion(postponedLeadCount, pipelineLeadCount),
            },
            {
                key: 'not_relevant',
                label: 'Неактуален',
                hint: 'Лиды, которые не подходят или сняты с процесса',
                count: notRelevantLeadCount,
                conversion: formatConversion(notRelevantLeadCount, pipelineLeadCount),
            },
            {
                key: 'contacted',
                label: 'Отправлено',
                hint: 'Первое касание уже сделано',
                count: contactedLeadCount,
                conversion: formatConversion(contactedLeadCount, inProgressLeadCount),
            },
            {
                key: 'waiting_reply',
                label: 'Ждём ответ',
                hint: 'Сообщение ушло и ждём реакцию',
                count: waitingReplyLeadCount,
                conversion: formatConversion(waitingReplyLeadCount, contactedLeadCount),
            },
            {
                key: 'replied',
                label: 'Ответил',
                hint: 'Лид ответил и находится в переписке',
                count: repliedLeadCount,
                conversion: formatConversion(repliedLeadCount, waitingReplyLeadCount),
            },
            {
                key: 'converted',
                label: 'Конвертирован',
                hint: 'Лид доведён до следующего коммерческого шага',
                count: convertedLeadCount,
                conversion: formatConversion(convertedLeadCount, repliedLeadCount),
            },
        ];
        return stages;
    }, [
        contactedLeadCount,
        convertedLeadCount,
        inProgressLeadCount,
        notRelevantLeadCount,
        pipelineLeadCount,
        postponedLeadCount,
        repliedLeadCount,
        waitingReplyLeadCount,
    ]);
    const pipelineEfficiencySummary = useMemo(() => {
        return {
            foundCount: searchJobResultCount,
            pipelineCount: pipelineLeadCount,
            saveRate: formatConversion(pipelineLeadCount, searchJobResultCount),
            readyRate: formatConversion(contactedLeadCount, pipelineLeadCount),
            replyRate: formatConversion(repliedLeadCount, waitingReplyLeadCount),
            qualifiedRate: formatConversion(convertedLeadCount, repliedLeadCount),
        };
    }, [
        contactedLeadCount,
        convertedLeadCount,
        pipelineLeadCount,
        repliedLeadCount,
        searchJobResultCount,
        waitingReplyLeadCount,
    ]);
    const draftReadyLeads = useMemo(
        () => sourceFilteredLeads.filter((lead) => lead.status === channelSelected),
        [sourceFilteredLeads]
    );
    const filteredDraftReadyLeads = useMemo(
        () => draftReadyLeads.filter((lead) => !draftChannelFilter || (lead.selected_channel || '') === draftChannelFilter),
        [draftReadyLeads, draftChannelFilter]
    );
    const getEffectiveDraftChannel = useCallback((draft: OutreachDraft) => {
        const lead = savedLeadById.get(draft.lead_id);
        return (lead?.selected_channel || draft.channel || '') as string;
    }, [savedLeadById]);
    const filteredDrafts = useMemo(
        () =>
            drafts.filter(
                (draft) => {
                    const lead = savedLeadById.get(draft.lead_id);
                    return (
                        !isLeadAlreadySent(lead) &&
                        (!draftChannelFilter || getEffectiveDraftChannel(draft) === draftChannelFilter) &&
                        leadMatchesOutreachContactFilter(lead, draftContactFilter) &&
                        (!draftStatusFilter || draft.status === draftStatusFilter)
                    );
                }
            ),
        [drafts, draftChannelFilter, draftContactFilter, draftStatusFilter, savedLeadById, getEffectiveDraftChannel]
    );
    const filteredSendReadyDrafts = useMemo(
        () => sendReadyDrafts.filter((draft) =>
            (!queueChannelFilter || draft.channel === queueChannelFilter) &&
            leadMatchesOutreachContactFilter(savedLeadById.get(draft.lead_id), queueContactFilter)
        ),
        [sendReadyDrafts, queueChannelFilter, queueContactFilter, savedLeadById]
    );
    const todayBatchDate = useMemo(() => new Date().toISOString().slice(0, 10), []);
    const queueBatchNeedsAttention = useCallback((batch: OutreachBatch) =>
        (batch.items || []).some((item) => {
            if (queueChannelFilter && item.channel !== queueChannelFilter) return false;
            if (item.delivery_status === 'failed') return true;
            if (item.delivery_status === 'dlq') return true;
            return item.delivery_status === 'sent' && !item.latest_human_outcome && !item.latest_outcome;
        }), [queueChannelFilter]);
    const filteredSendBatches = useMemo(() => {
        const byChannel = sendBatches.filter(
            (batch) =>
                (!queueChannelFilter || (batch.items || []).some((item) => item.channel === queueChannelFilter)) &&
                (queueContactFilter === '' || (batch.items || []).some((item) => queueItemMatchesContactFilter(item, savedLeadById.get(item.lead_id), queueContactFilter)))
        );
        if (queueViewFilter === 'today') {
            return byChannel.filter((batch) => batch.batch_date === todayBatchDate);
        }
        if (queueViewFilter === 'attention') {
            return byChannel.filter((batch) => queueBatchNeedsAttention(batch));
        }
        return byChannel;
    }, [sendBatches, queueChannelFilter, queueContactFilter, queueViewFilter, todayBatchDate, savedLeadById, queueBatchNeedsAttention]);
    const visibleQueueItems = useMemo(
        () =>
            filteredSendBatches.flatMap((batch) =>
                (batch.items || []).filter((item) =>
                    (!queueChannelFilter || item.channel === queueChannelFilter) &&
                    queueItemMatchesContactFilter(item, savedLeadById.get(item.lead_id), queueContactFilter)
                )
            ),
        [filteredSendBatches, queueChannelFilter, queueContactFilter, savedLeadById]
    );
    const visibleQueueSummary = useMemo(() => {
        let queued = 0;
        let sending = 0;
        let sent = 0;
        let delivered = 0;
        let failed = 0;
        let dlq = 0;
        let withReaction = 0;

        for (const item of visibleQueueItems) {
            if (item.delivery_status === 'sent') sent += 1;
            else if (item.delivery_status === 'delivered') delivered += 1;
            else if (item.delivery_status === 'failed') failed += 1;
            else if (item.delivery_status === 'dlq') dlq += 1;
            else if (item.delivery_status === 'sending') sending += 1;
            else queued += 1;

            if (item.latest_human_outcome || item.latest_outcome || item.latest_raw_reply) {
                withReaction += 1;
            }
        }

        return { queued, sending, sent, delivered, failed, dlq, withReaction };
    }, [visibleQueueItems]);
    const queueItemById = useMemo(() => {
        const next = new Map<string, OutreachQueueItem>();
        sendBatches.forEach((batch) => {
            (batch.items || []).forEach((item) => {
                next.set(item.id, item);
            });
        });
        return next;
    }, [sendBatches]);
    const batchById = useMemo(() => {
        const next = new Map<string, OutreachBatch>();
        sendBatches.forEach((batch) => {
            next.set(batch.id, batch);
        });
        return next;
    }, [sendBatches]);
    const latestQueueItemByLeadId = useMemo(() => {
        const next = new Map<string, OutreachQueueItem>();
        const sortValue = (item: OutreachQueueItem) =>
            Date.parse(String(item.updated_at || item.sent_at || item.created_at || '')) || 0;
        sendBatches.forEach((batch) => {
            (batch.items || []).forEach((item) => {
                const leadId = String(item.lead_id || '').trim();
                if (!leadId) {
                    return;
                }
                const existing = next.get(leadId);
                if (!existing || sortValue(item) >= sortValue(existing)) {
                    next.set(leadId, item);
                }
            });
        });
        return next;
    }, [sendBatches]);
    const sentLeads = useMemo(
        () => sourceFilteredLeads.filter((lead) => {
            if (!lead.id) {
                return false;
            }
            if (latestQueueItemByLeadId.has(lead.id)) {
                return true;
            }
            return ['sent', 'delivered', 'responded', 'qualified', 'converted'].includes(String(lead.status || '').trim().toLowerCase());
        }),
        [latestQueueItemByLeadId, sourceFilteredLeads]
    );
    const filteredSentLeads = useMemo(
        () => sentLeads.filter((lead) => leadMatchesOutreachContactFilter(lead, sentContactFilter)),
        [sentContactFilter, sentLeads]
    );
    const selectedQueueItem = useMemo(
        () => (selectedQueueItemId ? queueItemById.get(selectedQueueItemId) || null : null),
        [queueItemById, selectedQueueItemId]
    );
    const selectedQueueBatch = useMemo(
        () => (selectedQueueItem ? batchById.get(selectedQueueItem.batch_id) || null : null),
        [batchById, selectedQueueItem]
    );
    const selectedQueueLead = useMemo(() => {
        if (!selectedQueueItem) {
            return null;
        }
        return savedLeadById.get(selectedQueueItem.lead_id) || buildLeadFallbackFromQueueItem(selectedQueueItem);
    }, [savedLeadById, selectedQueueItem]);
    const sentLeadSnapshots = useMemo(
        () =>
            filteredSentLeads.map((lead) => ({
                lead,
                queueItem: lead.id ? latestQueueItemByLeadId.get(lead.id) || buildSyntheticSentQueueItem(lead) : null,
            })),
        [filteredSentLeads, latestQueueItemByLeadId]
    );

    const draftDetailRows = useMemo(
        () =>
            filteredDrafts.map((draft) => {
                const lead = savedLeadById.get(draft.lead_id);
                const effectiveChannel = getEffectiveDraftChannel(draft);
                return {
                    draft,
                    lead,
                    effectiveChannel,
                    warning: selectedChannelWarning(lead, effectiveChannel),
                };
            }),
        [filteredDrafts, getEffectiveDraftChannel, savedLeadById]
    );
    const selectedDraftDetail = useMemo(
        () => draftDetailRows.find((item) => item.draft.id === selectedDraftDetailId) || draftDetailRows[0] || null,
        [draftDetailRows, selectedDraftDetailId]
    );

    const sentDetailRows = useMemo(() => {
        const rows = sentLeadSnapshots.map((item) => {
            const status = String(item.queueItem?.delivery_status || '').trim().toLowerCase();
            const hasReply = Boolean(item.queueItem?.latest_human_outcome || item.queueItem?.latest_outcome || item.queueItem?.latest_raw_reply);
            let state: 'problem' | 'ready' | 'history';
            if (['failed', 'dlq', 'retry'].includes(status)) {
                state = 'problem';
            } else if (!hasReply) {
                state = 'ready';
            } else {
                state = 'history';
            }
            return {
                ...item,
                state,
                warning: selectedChannelWarning(item.lead, item.queueItem?.channel || item.lead.selected_channel),
            };
        });

        return rows.sort((a, b) => {
            const aTime = Date.parse(String(a.queueItem?.updated_at || a.queueItem?.sent_at || a.queueItem?.created_at || a.lead.created_at || '')) || 0;
            const bTime = Date.parse(String(b.queueItem?.updated_at || b.queueItem?.sent_at || b.queueItem?.created_at || b.lead.created_at || '')) || 0;
            return bTime - aTime;
        });
    }, [sentLeadSnapshots]);
    const filteredSentDetailRows = useMemo(
        () => sentDetailRows.filter((item) => !sentStateFilter || item.state === sentStateFilter),
        [sentDetailRows, sentStateFilter]
    );
    const selectedSentDetail = useMemo(
        () => filteredSentDetailRows.find((item) => item.lead.id === selectedSentLeadId) || filteredSentDetailRows[0] || null,
        [filteredSentDetailRows, selectedSentLeadId]
    );

    useEffect(() => {
        if (visibleQueueItems.length === 0) {
            if (selectedQueueItemId) {
                setSelectedQueueItemId(null);
            }
            return;
        }
        if (!selectedQueueItemId || !visibleQueueItems.some((item) => item.id === selectedQueueItemId)) {
            setSelectedQueueItemId(visibleQueueItems[0].id);
        }
    }, [selectedQueueItemId, visibleQueueItems]);
    useEffect(() => {
        if (draftDetailRows.length === 0) {
            if (selectedDraftDetailId) {
                setSelectedDraftDetailId(null);
            }
            return;
        }
        if (!selectedDraftDetailId || !draftDetailRows.some((item) => item.draft.id === selectedDraftDetailId)) {
            setSelectedDraftDetailId(draftDetailRows[0].draft.id);
        }
    }, [draftDetailRows, selectedDraftDetailId]);
    useEffect(() => {
        if (filteredSentDetailRows.length === 0) {
            if (selectedSentLeadId) {
                setSelectedSentLeadId(null);
            }
            return;
        }
        if (!selectedSentLeadId || !filteredSentDetailRows.some((item) => item.lead.id === selectedSentLeadId)) {
            setSelectedSentLeadId(filteredSentDetailRows[0].lead.id || null);
        }
    }, [filteredSentDetailRows, selectedSentLeadId]);
    const pipelineWindowMetrics = useMemo(() => {
        const windows = [
            { key: '7d', label: '7 дней', days: 7 },
            { key: '30d', label: '30 дней', days: 30 },
        ];
        return windows.map((window) => {
            const pipelineLeads = filteredLeadsForKanban.filter((lead) => isWithinLastDays(lead.created_at, window.days));
            const shortlistLeads = pipelineLeads.filter((lead) => leadToKanbanColumn(lead) === 'shortlist');
            const inProgressLeads = pipelineLeads.filter((lead) => leadToKanbanColumn(lead) === 'in_progress');
            const contactedLeads = pipelineLeads.filter((lead) => leadToKanbanColumn(lead) === 'contacted');
            const closedLeads = pipelineLeads.filter((lead) => leadToKanbanColumn(lead) === 'closed');
            const draftsWindow = drafts.filter((draft) => isWithinLastDays(draft.created_at, window.days));
            const approvedDraftsWindow = draftsWindow.filter((draft) => String(draft.status || '').trim().toLowerCase() === 'approved');
            const queueItemsWindow = visibleQueueItems.filter((item) => isWithinLastDays(item.created_at || item.sent_at || item.updated_at, window.days));
            const deliveredWindow = queueItemsWindow.filter((item) => item.delivery_status === 'delivered');
            const failedWindow = queueItemsWindow.filter((item) => item.delivery_status === 'failed');
            const reactionsWindow = reactions.filter((reaction) => isWithinLastDays(reaction.created_at || reaction.updated_at, window.days));
            const positiveWindow = reactionsWindow.filter((reaction) => {
                const outcome = String(reaction.human_confirmed_outcome || reaction.classified_outcome || '').trim().toLowerCase();
                return outcome === 'positive';
            });
            return {
                key: window.key,
                label: window.label,
                pipelineCount: pipelineLeads.length,
                shortlistCount: shortlistLeads.length,
                inProgressCount: inProgressLeads.length,
                contactedCount: contactedLeads.length,
                closedCount: closedLeads.length,
                draftCount: draftsWindow.length,
                approvedDraftCount: approvedDraftsWindow.length,
                queueCount: queueItemsWindow.length,
                deliveredCount: deliveredWindow.length,
                failedCount: failedWindow.length,
                reactionCount: reactionsWindow.length,
                positiveCount: positiveWindow.length,
            };
        });
    }, [filteredLeadsForKanban, drafts, visibleQueueItems, reactions]);
    const outreachOperatorMetrics = useMemo(() => {
        const approvedDrafts = drafts.filter((draft) => String(draft.status || '').trim().toLowerCase() === 'approved').length;
        const deliveredQueueItems = visibleQueueItems.filter((item) => item.delivery_status === 'delivered').length;
        const failedQueueItems = visibleQueueItems.filter((item) => item.delivery_status === 'failed').length;
        const responseCount = reactions.length;
        return [
            {
                key: 'drafts',
                label: 'Черновики',
                count: drafts.length,
                conversion: formatConversion(approvedDrafts, drafts.length),
                dropOff: formatDropOff(drafts.length - approvedDrafts, drafts.length),
                hint: 'Сколько черновиков создано и какая часть дошла до approval.',
            },
            {
                key: 'queue',
                label: 'Отправка',
                count: visibleQueueItems.length,
                conversion: formatConversion(deliveredQueueItems, visibleQueueItems.length),
                dropOff: `${failedQueueItems}`,
                hint: 'Какой объём реально дошёл до delivered и сколько упало на доставке.',
            },
            {
                key: 'sent',
                label: 'Отправлено / ответ',
                count: reactions.length,
                conversion: formatConversion(positiveReactionCount, responseCount),
                dropOff: formatDropOff(positiveReactionCount, responseCount),
                hint: 'Какой объём входящих реакций закончился позитивным outcome.',
            },
        ];
    }, [drafts, visibleQueueItems, reactions, positiveReactionCount]);

    useEffect(() => {
        setSelectedDraftIds((prev) => prev.filter((id) => filteredDrafts.some((draft) => draft.id === id)));
    }, [filteredDrafts]);

    useEffect(() => {
        setSelectedSendReadyDraftIds((prev) => prev.filter((id) => filteredSendReadyDrafts.some((draft) => draft.id === id)));
    }, [filteredSendReadyDrafts]);

    useEffect(() => {
        setSelectedOutreachLeadIds((prev) => prev.filter((id) => filteredContactLeads.some((lead) => lead.id === id)));
    }, [filteredContactLeads]);

    useEffect(() => {
        setSelectedQueueItemIds((prev) => prev.filter((id) => visibleQueueItems.some((item) => item.id === id)));
    }, [visibleQueueItems]);

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
        } catch (error: unknown) {
            if (!options?.silent) {
                setPreviewError(getRequestErrorMessage(error, 'Не удалось загрузить аудит карточки лида'));
            }
        } finally {
            if (!options?.silent) {
                setPreviewLoadingId(null);
            }
        }
    }, []);

    const refreshSavedLeadsAndPreview = useCallback(async (leadId?: string, options?: { silentPreview?: boolean }) => {
        await fetchSavedLeads();
        if (leadId) {
            await fetchLeadPreview(leadId, options?.silentPreview ? { silent: true } : undefined);
        }
    }, [fetchLeadPreview, fetchSavedLeads]);

    const openLeadPreviewById = async (leadId?: string, fallbackLead?: Lead) => {
        if (!leadId) {
            return;
        }

        const lead =
            fallbackLead ||
            savedLeadById.get(leadId) || {
                id: leadId,
                name: leadId,
                status: 'new',
            };
        setPreviewLead(lead);
        const inferredLanguage = inferLeadAuditLanguage(lead);
        const storedLanguages = Array.isArray(lead.enabled_languages) ? lead.enabled_languages : [];
        const primaryLanguage = String(lead.preferred_language || inferredLanguage).trim().toLowerCase() || inferredLanguage;
        setPreviewAuditPageLanguage(primaryLanguage);
        setPreviewAuditPageEnabledLanguages(ensureAuditLanguages(primaryLanguage, storedLanguages.length ? storedLanguages : [primaryLanguage]));
        setPreviewSnapshot(null);
        setPreviewError(null);
        setPreviewAuditPageUrl(lead.public_audit_url || null);
        await fetchLeadPreview(leadId);
    };

    const openLeadPreview = async (lead: Lead) => {
        await openLeadPreviewById(lead.id, lead);
    };

    const generateAuditPageFromLeadPreview = async () => {
        if (!previewLead?.id) {
            return;
        }
        setPreviewAuditPageBusy(true);
        setPreviewError(null);
        try {
            const response = await api.post(`/admin/prospecting/lead/${previewLead.id}/offer-page`, {
                primary_language: previewAuditPageLanguage,
                enabled_languages: ensureAuditLanguages(previewAuditPageLanguage, previewAuditPageEnabledLanguages),
            });
            const url = String(response.data?.public_url || '');
            setPreviewAuditPageUrl(url || null);
            const updatedLead = (response.data?.lead as Lead) || null;
            if (updatedLead) {
                setPreviewLead(updatedLead);
            }
            await refreshSavedLeadsAndPreview(previewLead.id, { silentPreview: true });
            if (url) {
                window.open(url, '_blank', 'noopener,noreferrer');
            }
        } catch (error: unknown) {
            setPreviewError(getRequestErrorMessage(error, 'Не удалось сгенерировать страницу аудита'));
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
            await refreshSavedLeadsAndPreview();
        } catch (error: unknown) {
            setPreviewError(getRequestErrorMessage(error, 'Не удалось сохранить контакты лида'));
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
            await refreshSavedLeadsAndPreview(previewLead.id);
        } catch (error: unknown) {
            setPreviewError(getRequestErrorMessage(error, 'Не удалось запустить парсинг карточки'));
        } finally {
            setPreviewParseBusy(false);
        }
    };

    const runLeadParse = async (lead: Lead) => {
        if (!lead.id) {
            return;
        }
        setParseActionBusy((prev) => ({ ...prev, [lead.id as string]: true }));
        try {
            await api.post(`/admin/prospecting/lead/${lead.id}/parse`);
            await fetchSavedLeads();
        } catch (error: unknown) {
            toast.error(getRequestErrorMessage(error, 'Не удалось запустить парсинг карточки'));
        } finally {
            setParseActionBusy((prev) => ({ ...prev, [lead.id as string]: false }));
        }
    };

    const updateLeadLanguage = async (lead: Lead, language: string) => {
        if (!lead.id) {
            return;
        }
        const normalized = String(language || '').trim().toLowerCase();
        if (!normalized) {
            return;
        }
        setLanguageLoading((prev) => ({ ...prev, [lead.id as string]: true }));
        try {
            await api.post(`/admin/prospecting/lead/${lead.id}/language`, {
                preferred_language: normalized,
                enabled_languages: [normalized],
            });
            await fetchSavedLeads();
        } catch (error: unknown) {
            toast.error(getRequestErrorMessage(error, 'Не удалось обновить язык аудита'));
        } finally {
            setLanguageLoading((prev) => ({ ...prev, [lead.id as string]: false }));
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

    const renderKanbanCard = (lead: Lead) => {
        const leadId = lead.id || '';
        const columnId = leadToPipelineBoardColumn(lead);
        const isDragging = leadId && draggingLeadId === leadId;
        const isSelected = Boolean(leadId && selectedPipelineLeadIds.includes(leadId));

        return (
            <Card
                key={leadId || lead.name}
                draggable={Boolean(leadId)}
                onDragStart={leadId ? handleLeadDragStart(leadId) : undefined}
                onDragEnd={handleLeadDragEnd}
                onClick={() => openLeadPreview(lead)}
                className={`cursor-pointer border border-border bg-background shadow-sm transition hover:border-primary/40 hover:shadow-md ${isDragging ? 'opacity-60' : ''}`}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        openLeadPreview(lead);
                    }
                }}
            >
                <CardHeader className="space-y-2 pb-3">
                    <div className="flex items-start justify-between gap-2">
                        <div className="flex items-start gap-3">
                            {leadId ? (
                                <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onClick={(event) => event.stopPropagation()}
                                    onChange={(event) =>
                                        setSelectedPipelineLeadIds((prev) =>
                                            event.target.checked
                                                ? Array.from(new Set([...prev, leadId]))
                                                : prev.filter((id) => id !== leadId)
                                        )
                                    }
                                    className="mt-1 h-4 w-4 rounded border border-input"
                                />
                            ) : null}
                            <div>
                                <div className="text-sm font-semibold">{lead.name}</div>
                                <div className="mt-1 text-xs text-muted-foreground">
                                    {lead.category || 'Без категории'}
                                </div>
                            </div>
                        </div>
                        <Badge variant="outline" className="text-[11px] font-normal">
                            {sourceLabel(lead.source)}
                        </Badge>
                    </div>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Star className="h-3.5 w-3.5 fill-yellow-400 text-yellow-400" />
                        <span>{lead.rating ?? '-'}</span>
                        {lead.reviews_count ? <span>({lead.reviews_count})</span> : null}
                    </div>
                    <div className="text-xs leading-5 text-muted-foreground">
                        {lead.address || lead.city || 'Адрес не указан'}
                    </div>
                </CardHeader>
                <CardContent className="pt-0" />
            </Card>
        );
    };

    const renderDraftsWorkspace = () => {
        const selectedItem = selectedDraftDetail;
        const selectedDraft = selectedItem?.draft || null;
        const selectedLead = selectedItem?.lead || null;
        const selectedDraftIndex = selectedDraft ? draftDetailRows.findIndex((item) => item.draft.id === selectedDraft.id) : -1;
        const selectedChannel = selectedItem?.effectiveChannel || '';
        const selectedDraftText = selectedDraft ? (draftEdits[selectedDraft.id] || '') : '';
        const selectedDraftPending = selectedDraft ? draftBusy[selectedDraft.id] : '';
        const selectedDraftHasIssue = Boolean(selectedItem?.warning);
        const selectedDraftMissingContacts = filteredDrafts.filter((draft) => {
            const lead = savedLeadById.get(draft.lead_id);
            return Boolean(selectedChannelWarning(lead, getEffectiveDraftChannel(draft)));
        }).length;
        const detailPanel = selectedDraft ? (
            <DraftDetailPanel
                title={selectedLead?.name || selectedDraft?.lead_name}
                description={selectedLead?.address || 'Сначала проверьте канал, текст и безопасное следующее действие.'}
                statusLabel={formatDraftStatusLabel(selectedDraft.status)}
                statusTone={toneForDraftStatus(selectedDraft.status)}
                warning={selectedDraftHasIssue ? selectedItem?.warning || '' : ''}
                canOpenLeadCard={Boolean(selectedLead)}
                onOpenLeadCard={() => selectedLead && openLeadPreview(selectedLead)}
                onFixChannel={() => selectedLead?.id && chooseChannel(selectedLead.id, bestAvailableOutreachChannel(selectedLead))}
                leadContacts={selectedLead}
                hasMessenger={selectedLead ? extractHasMessengers(selectedLead) : false}
                selectedChannelLabel={formatLeadChannel(selectedChannel)}
                selectedChannelValue={selectedChannel === 'telegram' ? (selectedLead?.telegram_url || 'Нет контакта для выбранного канала') :
                    selectedChannel === 'whatsapp' ? (selectedLead?.whatsapp_url || 'Нет контакта для выбранного канала') :
                        selectedChannel === 'email' ? (selectedLead?.email || 'Нет контакта для выбранного канала') :
                            selectedChannel === 'max' ? (selectedLead && extractHasMax(selectedLead) ? 'Контакт через Max найден' : 'Нет контакта для выбранного канала') :
                                'Для ручной отправки используйте карточку лида'}
                selectedChannelTone={selectedDraftHasIssue ? 'warning' : 'success'}
                auditStatusLabel={selectedLead && hasLeadAudit(selectedLead) ? 'Доступен' : 'Пока нет'}
                auditPrimaryText={selectedLead && hasLeadAudit(selectedLead) ? 'Ссылки на аудит доступны ниже' : 'Аудит не должен мешать отправке, но помогает при проверке'}
                auditSecondaryText={selectedLead?.public_audit_updated_at ? `Обновлён ${formatAuditUpdatedAt(selectedLead.public_audit_updated_at)}` : 'Без даты обновления'}
                auditTone={selectedLead && hasLeadAudit(selectedLead) ? 'info' : 'default'}
                channelSelector={selectedLead ? (
                    <div className="flex flex-wrap items-center gap-3">
                        <select
                            className="border rounded-md px-3 py-2 bg-background text-sm"
                            value={selectedLead.selected_channel || 'manual'}
                            onChange={(e) => {
                                if (selectedLead.id) {
                                    void chooseChannel(selectedLead.id, toOutreachChannel(String(e.target.value || 'manual')));
                                }
                            }}
                        >
                            <option value="telegram">Telegram</option>
                            <option value="whatsapp">WhatsApp</option>
                            <option value="max">Max</option>
                            <option value="email">Email</option>
                            <option value="manual">Ручная отправка</option>
                        </select>
                        <div className="text-sm text-muted-foreground">
                            {selectedChannel === 'telegram' ? (selectedLead.telegram_url || 'Нет контакта для выбранного канала') :
                                selectedChannel === 'whatsapp' ? (selectedLead.whatsapp_url || 'Нет контакта для выбранного канала') :
                                    selectedChannel === 'email' ? (selectedLead.email || 'Нет контакта для выбранного канала') :
                                        selectedChannel === 'max' ? (extractHasMax(selectedLead) ? 'Контакт через Max найден' : 'Нет контакта для выбранного канала') :
                                            'Для ручной отправки используйте карточку лида'}
                        </div>
                    </div>
                ) : null}
                auditLinks={selectedLead && buildLeadAuditLanguageLinks(selectedLead).length > 0 ? buildLeadAuditLanguageLinks(selectedLead).map((item) => (
                    <a key={item.language} href={item.href} target="_blank" rel="noreferrer">
                        <Button type="button" size="sm" variant="outline">Аудит {item.label}</Button>
                    </a>
                )) : null}
                primaryAction={selectedDraft.status === 'approved'
                    ? {
                        label: 'Проверить и добавить в отправку',
                        onClick: () => createSendBatch([selectedDraft.id]),
                        disabled: Boolean(selectedDraftPending),
                    }
                    : {
                        label: 'Утвердить черновик',
                        onClick: () => approveDraft(selectedDraft.id),
                        disabled: Boolean(selectedDraftPending) || !selectedDraftText.trim(),
                    }}
                secondaryActions={[
                    {
                        label: 'Сохранить черновик',
                        onClick: () => saveDraftEdit(selectedDraft.id),
                        disabled: Boolean(selectedDraftPending) || !selectedDraftText.trim(),
                    },
                    {
                        label: 'Открыть карточку лида',
                        onClick: () => selectedLead && openLeadPreview(selectedLead),
                        disabled: !selectedLead,
                    },
                    {
                        label: 'Отклонить',
                        onClick: () => rejectDraft(selectedDraft.id),
                        disabled: Boolean(selectedDraftPending),
                        variant: 'outline',
                    },
                    {
                        label: 'Отправлено вручную',
                        onClick: () => markDraftAsSentManually(selectedDraft),
                        disabled: Boolean(selectedDraftPending),
                        variant: 'secondary',
                    },
                ]}
                editorValue={selectedDraftText}
                onEditorChange={(value) => setDraftEdits((prev) => ({ ...prev, [selectedDraft.id]: value }))}
                reviewDescription="Здесь видно итоговый текст до отправки или переноса в очередь."
                checklistItems={[
                    {
                        id: 'channel',
                        label: 'Выбранный канал можно использовать',
                        checked: !selectedDraftHasIssue,
                        hint: selectedDraftHasIssue ? 'Сначала смените канал или уточните контакт.' : 'Контакт для выбранного канала найден.',
                    },
                    {
                        id: 'text',
                        label: 'Текст сообщения готов',
                        checked: Boolean(selectedDraftText.trim()),
                        hint: selectedDraftText.trim() ? 'Можно переходить к сохранению или отправке.' : 'Сообщение пока пустое.',
                    },
                    {
                        id: 'audit',
                        label: 'Контекст лида доступен',
                        checked: Boolean(selectedLead),
                        hint: selectedLead && hasLeadAudit(selectedLead) ? 'Аудит под рукой, если нужно быстро свериться.' : 'Можно работать и без аудита, но стоит проверить карточку.',
                    },
                ]}
                historyRows={[
                    { label: 'Статус', value: formatDraftStatusLabel(selectedDraft.status) },
                    { label: 'Создан', value: selectedDraft.created_at ? formatDateTime(selectedDraft.created_at) : '—' },
                    { label: 'Последнее изменение', value: selectedDraft.updated_at ? formatDateTime(selectedDraft.updated_at) : '—' },
                ]}
            />
        ) : null;

        return (
            <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-3 rounded-xl border p-4">
                    <div className="text-sm font-medium">Канал</div>
                    <select className="border rounded-md px-3 py-2 bg-background text-sm" value={draftChannelFilter} onChange={(e) => setDraftChannelFilter(e.target.value)}>
                        <option value="">Все каналы</option>
                        <option value="telegram">Telegram</option>
                        <option value="whatsapp">WhatsApp</option>
                        <option value="max">Max</option>
                        <option value="email">Email</option>
                        <option value="manual">Ручная отправка</option>
                    </select>
                    <div className="text-sm font-medium">Контакт</div>
                    <select className="border rounded-md px-3 py-2 bg-background text-sm" value={draftContactFilter} onChange={(e) => setDraftContactFilter(toOutreachContactFilter(String(e.target.value || '')))}>
                        <option value="">Любой</option>
                        <option value="telegram">Только с Telegram</option>
                        <option value="whatsapp">Только с WhatsApp</option>
                        <option value="max">Только с Max</option>
                        <option value="email">Только с Email</option>
                        <option value="vk">Только с VK</option>
                    </select>
                    <div className="text-sm font-medium">Состояние</div>
                    <select className="border rounded-md px-3 py-2 bg-background text-sm" value={draftStatusFilter} onChange={(e) => setDraftStatusFilter(e.target.value)}>
                        <option value="">Все</option>
                        <option value="generated">Ждут проверки</option>
                        <option value="approved">Готовы к отправке</option>
                        <option value="rejected">Нужна проверка</option>
                    </select>
                    <Badge variant="outline">Показано {filteredDrafts.length} из {drafts.length}</Badge>
                </div>

                {selectedDraftMissingContacts > 0 ? (
                    <ErrorSummary
                        title="Есть черновики с неверным каналом"
                        description={`У ${selectedDraftMissingContacts} лидов выбран канал, для которого нет контакта. Сначала проверьте канал или откройте карточку лида.`}
                    />
                ) : null}

                <div className="grid gap-4">
                    <LeadList
                        title="Нужно действие"
                        description="Слева только короткий список: кому писать, через какой канал и где нужен ручной контроль."
                        count={filteredDrafts.length}
                    >
                        <div className="space-y-3">
                            {loadingDrafts ? (
                                <div className="flex justify-center py-10 text-sm text-muted-foreground">
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Загружаем черновики...
                                </div>
                            ) : filteredDrafts.length === 0 ? (
                                <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                                    По текущим фильтрам здесь пока ничего нет.
                                </div>
                            ) : (
                                draftDetailRows.map(({ draft, lead, effectiveChannel, warning }) => (
                                    <LeadListItem
                                        key={draft.id}
                                        title={lead?.name || draft.lead_name || draft.lead_id}
                                        subtitle={lead?.category || 'Без категории'}
                                        location={lead?.city || lead?.address || 'Локация не указана'}
                                        statusLabel={formatDraftStatusLabel(draft.status)}
                                        statusTone={toneForDraftStatus(draft.status)}
                                        channelLabel={`Канал: ${formatLeadChannel(effectiveChannel)}`}
                                        languageLabel={leadLanguageLabel(lead)}
                                        lastActionLabel={draft.updated_at ? `Обновлено ${formatDateTime(draft.updated_at)}` : 'Ещё не отправляли'}
                                        contactBadges={
                                            <ContactPresenceBadges
                                                website={lead?.website}
                                                phone={lead?.phone}
                                                email={lead?.email}
                                                telegramUrl={lead?.telegram_url}
                                                whatsappUrl={lead?.whatsapp_url}
                                                hasMessenger={lead ? extractHasMessengers(lead) : false}
                                            />
                                        }
                                        warning={warning || undefined}
                                        selected={selectedDraft?.id === draft.id}
                                        onSelect={() => {
                                            setSelectedDraftDetailId(draft.id);
                                            setOutreachDetailOpen(true);
                                        }}
                                        checked={selectedDraftIds.includes(draft.id)}
                                        onCheckedChange={(checked) => {
                                            setSelectedDraftIds((prev) => checked ? Array.from(new Set([...prev, draft.id])) : prev.filter((id) => id !== draft.id));
                                            setSelectedDraftDetailId(draft.id);
                                            setOutreachDetailOpen(true);
                                        }}
                                    />
                                ))
                            )}
                        </div>
                    </LeadList>
                </div>

                <StickyBulkActionBar count={selectedDraftIds.length} label="Можно массово утвердить, отклонить или удалить выбранные черновики.">
                    <Button size="sm" onClick={approveSelectedDrafts} disabled={selectedDraftIds.length === 0 || draftBusy.bulkApprove === 'approve'}>
                        {draftBusy.bulkApprove === 'approve' && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                        Утвердить
                    </Button>
                    <Button size="sm" variant="outline" onClick={rejectSelectedDrafts} disabled={selectedDraftIds.length === 0 || draftBusy.bulkReject === 'reject'}>
                        Отклонить
                    </Button>
                    <Button size="sm" variant="destructive" onClick={deleteSelectedDrafts} disabled={selectedDraftIds.length === 0 || draftBusy.bulkDelete === 'delete'}>
                        Удалить
                    </Button>
                </StickyBulkActionBar>

                {outreachDetailOpen && detailPanel ? (
                    <OutreachDetailModal
                        title="Карточка лида"
                        description="Проверьте канал, сообщение и следующее безопасное действие."
                        onClose={() => setOutreachDetailOpen(false)}
                        onPrevious={selectedDraftIndex > 0 ? () => setSelectedDraftDetailId(draftDetailRows[selectedDraftIndex - 1].draft.id) : undefined}
                        onNext={selectedDraftIndex >= 0 && selectedDraftIndex < draftDetailRows.length - 1 ? () => setSelectedDraftDetailId(draftDetailRows[selectedDraftIndex + 1].draft.id) : undefined}
                        previousDisabled={selectedDraftIndex <= 0}
                        nextDisabled={selectedDraftIndex === -1 || selectedDraftIndex >= draftDetailRows.length - 1}
                    >
                        {detailPanel}
                    </OutreachDetailModal>
                ) : null}
            </div>
        );
    };

    const renderQueueWorkspace = () => {
        const selectedLead = selectedQueueLead;
        const selectedItem = selectedQueueItem;
        const selectedQueueIndex = selectedItem ? visibleQueueItems.findIndex((item) => item.id === selectedItem.id) : -1;
        const selectedWarning = selectedLead ? selectedChannelWarning(selectedLead, selectedItem?.channel || selectedLead.selected_channel) : '';
        const selectedMessage = selectedItem?.approved_text || selectedItem?.generated_text || '';
        const selectedRecipient = selectedItem?.recipient_value
            || (selectedItem?.channel === 'telegram' ? selectedLead?.telegram_url : '')
            || (selectedItem?.channel === 'whatsapp' ? selectedLead?.whatsapp_url : '')
            || (selectedItem?.channel === 'email' ? selectedLead?.email : '');
        const selectedProblemCount = visibleQueueItems.filter((item) => {
            const lead = savedLeadById.get(item.lead_id) || buildLeadFallbackFromQueueItem(item);
            return Boolean(selectedChannelWarning(lead, item.channel) || item.error_text || ['failed', 'dlq', 'retry'].includes(String(item.delivery_status || '').toLowerCase()));
        }).length;

        return (
            <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-3 rounded-xl border p-4">
                    <div className="text-sm font-medium">Канал для списка и очереди</div>
                    <select className="border rounded-md px-3 py-2 bg-background text-sm" value={queueChannelFilter} onChange={(e) => setQueueChannelFilter(e.target.value)}>
                        <option value="">Все каналы</option>
                        <option value="telegram">Telegram</option>
                        <option value="whatsapp">WhatsApp</option>
                        <option value="max">Max</option>
                        <option value="email">Email</option>
                        <option value="manual">Ручная отправка</option>
                    </select>
                    <div className="text-sm font-medium">Контакт для списка и очереди</div>
                    <select className="border rounded-md px-3 py-2 bg-background text-sm" value={queueContactFilter} onChange={(e) => setQueueContactFilter(toOutreachContactFilter(String(e.target.value || '')))}>
                        <option value="">Любой</option>
                        <option value="telegram">Только с Telegram</option>
                        <option value="whatsapp">Только с WhatsApp</option>
                        <option value="max">Только с Max</option>
                        <option value="email">Только с Email</option>
                        <option value="vk">Только с VK</option>
                    </select>
                    <div className="text-sm font-medium">Срез</div>
                    <select className="border rounded-md px-3 py-2 bg-background text-sm" value={queueViewFilter} onChange={(e) => setQueueViewFilter(String(e.target.value || 'all') as 'all' | 'today' | 'attention')}>
                        <option value="all">Все</option>
                        <option value="today">Только сегодня</option>
                        <option value="attention">Требует внимания</option>
                    </select>
                    <Badge variant="outline">Показано {visibleQueueItems.length}</Badge>
                    <Badge variant={selectedProblemCount > 0 ? 'destructive' : 'outline'}>Нужна проверка: {selectedProblemCount}</Badge>
                </div>

                {selectedProblemCount > 0 ? (
                    <ErrorSummary
                        title="Есть лиды с проблемами отправки"
                        description="Проверьте канал, контакт и статус отправки до следующего шага. Ошибки показаны прямо в списке и в деталях справа."
                    />
                ) : null}

                <div className="grid gap-4">
                    <LeadList
                        title="Готово к отправке и требует контроля"
                        description="Сначала видно, кому можно писать сейчас, а где сначала нужно исправить канал или статус."
                        count={visibleQueueItems.length}
                    >
                        <div className="space-y-3">
                            {loadingSendQueue ? (
                                <div className="flex justify-center py-10 text-sm text-muted-foreground">
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Загружаем очередь...
                                </div>
                            ) : visibleQueueItems.length === 0 ? (
                                <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                                    По текущему срезу ничего не найдено.
                                </div>
                            ) : (
                                visibleQueueItems.map((item) => {
                                    const lead = savedLeadById.get(item.lead_id) || buildLeadFallbackFromQueueItem(item);
                                    const warning = selectedChannelWarning(lead, item.channel) || item.error_text || '';
                                    return (
                                        <LeadListItem
                                            key={item.id}
                                            title={item.lead_name || lead.name || item.lead_id}
                                            subtitle={lead.category || 'Без категории'}
                                            location={lead.city || lead.address || 'Локация не указана'}
                                            statusLabel={formatQueueStatusLabel(item.delivery_status)}
                                            statusTone={toneForQueueStatus(item.delivery_status)}
                                            channelLabel={`Канал: ${formatLeadChannel(item.channel)}`}
                                            languageLabel={leadLanguageLabel(lead)}
                                            lastActionLabel={item.updated_at ? `Обновлено ${formatDateTime(item.updated_at)}` : 'Ещё не отправляли'}
                                            contactBadges={
                                                <ContactPresenceBadges
                                                    website={lead.website}
                                                    phone={lead.phone}
                                                    email={lead.email}
                                                    telegramUrl={lead.telegram_url}
                                                    whatsappUrl={lead.whatsapp_url}
                                                    hasMessenger={extractHasMessengers(lead)}
                                                />
                                            }
                                            warning={warning || undefined}
                                            selected={selectedQueueItemId === item.id}
                                            onSelect={() => {
                                                setSelectedQueueItemId(item.id);
                                                setOutreachDetailOpen(true);
                                            }}
                                            checked={selectedQueueItemIds.includes(item.id)}
                                            onCheckedChange={(checked) => {
                                                setSelectedQueueItemIds((prev) => checked ? Array.from(new Set([...prev, item.id])) : prev.filter((id) => id !== item.id));
                                                setSelectedQueueItemId(item.id);
                                                setOutreachDetailOpen(true);
                                            }}
                                        />
                                    );
                                })
                            )}
                        </div>
                    </LeadList>

                </div>

                <StickyBulkActionBar count={selectedQueueItemIds.length} label="Выбранные лиды можно быстро отметить, удалить из очереди или вернуть на ручную проверку.">
                    <Button size="sm" onClick={() => bulkMarkDelivery('sent')} disabled={selectedQueueItemIds.length === 0 || sendQueueBusy.bulkDelivery === 'sent'}>Отметить как отправленные</Button>
                    <Button size="sm" variant="outline" onClick={() => bulkMarkDelivery('delivered')} disabled={selectedQueueItemIds.length === 0 || sendQueueBusy.bulkDelivery === 'delivered'}>Отметить как доставленные</Button>
                    <Button size="sm" variant="outline" onClick={() => bulkMarkDelivery('failed')} disabled={selectedQueueItemIds.length === 0 || sendQueueBusy.bulkDelivery === 'failed'}>Нужна проверка</Button>
                    <Button size="sm" variant="destructive" onClick={bulkDeleteQueueItems} disabled={selectedQueueItemIds.length === 0 || sendQueueBusy.bulkDeleteQueue === 'delete'}>Удалить из очереди</Button>
                </StickyBulkActionBar>

                {outreachDetailOpen && selectedItem ? (
                    <OutreachDetailModal
                        title="Карточка лида"
                        description="Проверьте текст, канал, статус доставки и следующее действие."
                        onClose={() => setOutreachDetailOpen(false)}
                        onPrevious={selectedQueueIndex > 0 ? () => setSelectedQueueItemId(visibleQueueItems[selectedQueueIndex - 1].id) : undefined}
                        onNext={selectedQueueIndex >= 0 && selectedQueueIndex < visibleQueueItems.length - 1 ? () => setSelectedQueueItemId(visibleQueueItems[selectedQueueIndex + 1].id) : undefined}
                        previousDisabled={selectedQueueIndex <= 0}
                        nextDisabled={selectedQueueIndex === -1 || selectedQueueIndex >= visibleQueueItems.length - 1}
                    >
                        <QueueDetailPanel
                            title={selectedItem.lead_name || selectedLead?.name}
                            description={selectedLead?.address || 'Здесь видно канал, контакт, текст и безопасное следующее действие.'}
                            statusLabel={formatQueueStatusLabel(selectedItem.delivery_status)}
                            statusTone={toneForQueueStatus(selectedItem.delivery_status)}
                            warning={selectedWarning}
                            canOpenLeadCard={Boolean(selectedLead)}
                            onOpenLeadCard={() => selectedLead && openLeadPreviewById(selectedItem.lead_id, selectedLead)}
                            onFixChannel={selectedLead?.id ? () => chooseChannel(selectedLead.id || '', bestAvailableOutreachChannel(selectedLead)) : undefined}
                            leadContacts={selectedLead}
                            hasMessenger={selectedLead ? extractHasMessengers(selectedLead) : false}
                            channelStatusLabel={formatLeadChannel(selectedItem.channel || selectedLead?.selected_channel)}
                            channelPrimaryText={selectedRecipient ? 'Контакт найден, можно продолжать' : 'Нет контакта для выбранного канала'}
                            channelSecondaryText={selectedRecipient || 'Откройте карточку лида или смените канал'}
                            channelTone={selectedRecipient ? 'success' : 'warning'}
                            queueStatusLabel={selectedItem.latest_human_outcome || selectedItem.latest_outcome || 'Без ответа'}
                            queuePrimaryText={selectedItem.delivery_status ? `Статус доставки: ${formatQueueStatusLabel(selectedItem.delivery_status)}` : 'Статус ещё не задан'}
                            queueSecondaryText={selectedItem.updated_at ? `Последнее изменение ${formatDateTime(selectedItem.updated_at)}` : 'Без даты'}
                            queueTone={selectedItem.latest_human_outcome || selectedItem.latest_outcome ? 'info' : 'default'}
                            topErrorSummary={selectedItem.error_text ? (
                                <ErrorSummary
                                    title="Отправка не завершилась корректно"
                                    description={selectedItem.error_text}
                                    actions={selectedLead?.id ? <Button size="sm" variant="outline" onClick={() => openLeadPreviewById(selectedItem.lead_id, selectedLead)}>Открыть карточку лида</Button> : null}
                                />
                            ) : null}
                            contextLinks={selectedLead ? (
                                <>
                                    {buildLeadAuditLanguageLinks(selectedLead).map((item) => (
                                        <a key={item.language} href={item.href} target="_blank" rel="noreferrer">
                                            <Button type="button" size="sm" variant="outline">Аудит {item.label}</Button>
                                        </a>
                                    ))}
                                    <Button type="button" size="sm" variant="outline" onClick={() => openLeadPreviewById(selectedItem.lead_id, selectedLead)}>Карточка лида</Button>
                                </>
                            ) : null}
                            primaryAction={selectedWarning
                                ? {
                                    label: 'Исправить канал',
                                    onClick: () => selectedLead?.id && chooseChannel(selectedLead.id, bestAvailableOutreachChannel(selectedLead)),
                                    disabled: !selectedLead?.id || Boolean(sendQueueBusy[selectedItem.id]),
                                }
                                : ['queued', 'retry', 'sending'].includes(String(selectedItem.delivery_status || '').toLowerCase())
                                    ? {
                                        label: 'Проверить и отметить отправку',
                                        onClick: () => markDelivery(selectedItem.id, 'sent'),
                                        disabled: Boolean(sendQueueBusy[selectedItem.id]),
                                    }
                                    : {
                                        label: 'Зафиксировать ответ',
                                        onClick: () => recordReaction(selectedItem.id),
                                        disabled: Boolean(sendQueueBusy[selectedItem.id]),
                                    }}
                            secondaryActions={[
                                {
                                    label: 'Открыть карточку лида',
                                    onClick: () => selectedLead && openLeadPreviewById(selectedItem.lead_id, selectedLead),
                                    disabled: !selectedLead,
                                },
                                {
                                    label: 'Пропустить этот лид',
                                    variant: 'outline',
                                    onClick: () => selectedLead?.id && updateLeadStatusOptimistic(selectedLead.id, pipelineBoardColumnMeta.not_relevant.statusToSet),
                                    disabled: !selectedLead?.id,
                                },
                            ]}
                            message={selectedMessage}
                            reviewDescription="Сначала проверьте текст и канал, потом отмечайте отправку или фиксируйте ответ."
                            checklistItems={[
                                { id: 'channel', label: 'Канал подтверждён контактом', checked: !selectedWarning, hint: selectedWarning || 'Контакт для выбранного канала найден.' },
                                { id: 'message', label: 'Текст сообщения готов', checked: Boolean(selectedMessage.trim()), hint: selectedMessage.trim() ? 'Текст можно использовать без дополнительного поиска по странице.' : 'В очереди нет текста сообщения.' },
                                { id: 'status', label: 'Статус отправки понятен', checked: Boolean(selectedItem.delivery_status), hint: selectedItem.delivery_status ? `Сейчас: ${formatQueueStatusLabel(selectedItem.delivery_status)}` : 'Статус ещё не выбран.' },
                            ]}
                            reviewActions={
                                <>
                                    <Button size="sm" variant={selectedItem.delivery_status === 'delivered' ? 'default' : 'outline'} onClick={() => markDelivery(selectedItem.id, 'delivered')} disabled={Boolean(sendQueueBusy[selectedItem.id])}>
                                        Отметить как доставлено
                                    </Button>
                                    <Button size="sm" variant="outline" onClick={() => markDelivery(selectedItem.id, 'failed')} disabled={Boolean(sendQueueBusy[selectedItem.id])}>
                                        Ошибка отправки
                                    </Button>
                                </>
                            }
                            noteValue={replyDrafts[selectedItem.id] ?? ''}
                            onNoteChange={(value) => setReplyDrafts((prev) => ({ ...prev, [selectedItem.id]: value }))}
                            noteHint="Если ответ уже есть, вставьте его сюда и выберите безопасную классификацию."
                            historyRows={[
                                { label: 'Batch', value: selectedQueueBatch?.batch_date || selectedItem.batch_id },
                                { label: 'Provider', value: formatQueueProvider(selectedItem.provider_name) },
                                { label: 'Recipient', value: selectedItem.recipient_value || '—' },
                                { label: 'Последний outcome', value: selectedItem.latest_human_outcome || selectedItem.latest_outcome || '—' },
                            ]}
                        />
                    </OutreachDetailModal>
                ) : null}
            </div>
        );
    };

    const renderSentWorkspace = () => {
        const selectedLead = selectedSentDetail?.lead || null;
        const selectedQueue = selectedSentDetail?.queueItem || null;
        const selectedSentIndex = selectedLead?.id ? filteredSentDetailRows.findIndex((item) => item.lead.id === selectedLead.id) : -1;
        const selectedFollowUp = selectedLead?.id ? (followUpDrafts[selectedLead.id] ?? '') : '';
        const sentProblemCount = sentDetailRows.filter((item) => item.state === 'problem').length;
        const followUpReadyCount = sentDetailRows.filter((item) => item.state === 'ready').length;
        const sentHistoryCount = sentDetailRows.filter((item) => item.state === 'history').length;
        const canPrepareAlternativeResend = Boolean(selectedLead && bestAlternativeOutreachChannel(selectedLead, selectedQueue?.channel || selectedLead.selected_channel));

        return (
            <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-3 rounded-xl border p-4">
                    <div className="text-sm font-medium">Контакт</div>
                    <select className="border rounded-md px-3 py-2 bg-background text-sm" value={sentContactFilter} onChange={(e) => setSentContactFilter(toOutreachContactFilter(String(e.target.value || '')))}>
                        <option value="">Любой</option>
                        <option value="telegram">Только с Telegram</option>
                        <option value="whatsapp">Только с WhatsApp</option>
                        <option value="max">Только с Max</option>
                        <option value="email">Только с Email</option>
                        <option value="vk">Только с VK</option>
                    </select>
                    <Badge variant="outline">Показано {filteredSentDetailRows.length}</Badge>
                    <Button
                        type="button"
                        size="sm"
                        variant={sentStateFilter === 'ready' ? 'default' : 'outline'}
                        onClick={() => setSentStateFilter((prev) => (prev === 'ready' ? '' : 'ready'))}
                    >
                        Готовы к follow-up: {followUpReadyCount}
                    </Button>
                    <Button
                        type="button"
                        size="sm"
                        variant={sentStateFilter === 'problem' ? 'destructive' : 'outline'}
                        onClick={() => setSentStateFilter((prev) => (prev === 'problem' ? '' : 'problem'))}
                    >
                        Нужна проверка: {sentProblemCount}
                    </Button>
                    <Button
                        type="button"
                        size="sm"
                        variant={sentStateFilter === 'history' ? 'secondary' : 'outline'}
                        onClick={() => setSentStateFilter((prev) => (prev === 'history' ? '' : 'history'))}
                    >
                        История: {sentHistoryCount}
                    </Button>
                </div>

                {sentProblemCount > 0 ? (
                    <ErrorSummary
                        title="Не все отправленные лиды готовы к следующему шагу"
                        description="Часть лидов ушла с ошибкой или без подходящего канала. Это видно в списке и в деталях выбранной записи."
                    />
                ) : null}

                <div className="grid gap-4">
                    <LeadList
                        title="История отправки"
                        description="Здесь в одном списке: отправлено, ждём ответ, уже ответили и лиды, которым сначала нужна проверка."
                        count={filteredSentDetailRows.length}
                    >
                        <div className="space-y-3">
                            {filteredSentDetailRows.length === 0 ? (
                                <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                                    {sentStateFilter
                                        ? 'По этому фильтру отправленных лидов пока нет.'
                                        : 'Отправленных лидов пока нет.'}
                                </div>
                            ) : (
                                filteredSentDetailRows.map(({ lead, queueItem, state, warning }) => (
                                    <LeadListItem
                                        key={`sent-${lead.id}`}
                                        title={lead.name}
                                        subtitle={lead.category || 'Без категории'}
                                        location={lead.city || lead.address || 'Локация не указана'}
                                        statusLabel={state === 'problem' ? 'Нужна проверка' : state === 'ready' ? 'Ждём ответ' : 'История'}
                                        statusTone={state === 'problem' ? 'danger' : state === 'ready' ? 'info' : 'success'}
                                        channelLabel={`Канал: ${formatLeadChannel(queueItem?.channel || lead.selected_channel)}`}
                                        languageLabel={leadLanguageLabel(lead)}
                                        lastActionLabel={(queueItem?.updated_at || queueItem?.sent_at) ? formatDateTime(queueItem?.updated_at || queueItem?.sent_at || '') : 'Не отправлено'}
                                        contactBadges={
                                            <ContactPresenceBadges
                                                website={lead.website}
                                                phone={lead.phone}
                                                email={lead.email}
                                                telegramUrl={lead.telegram_url}
                                                whatsappUrl={lead.whatsapp_url}
                                                hasMessenger={extractHasMessengers(lead)}
                                            />
                                        }
                                        warning={warning || queueItem?.error_text || undefined}
                                        selected={selectedLead?.id === lead.id}
                                        onSelect={() => {
                                            setSelectedSentLeadId(lead.id || null);
                                            setOutreachDetailOpen(true);
                                        }}
                                    />
                                ))
                            )}
                        </div>
                    </LeadList>

                </div>

                {outreachDetailOpen && selectedSentDetail ? (
                    <OutreachDetailModal
                        title="Карточка лида"
                        description="Проверьте историю, канал и follow-up перед следующим шагом."
                        onClose={() => setOutreachDetailOpen(false)}
                        onPrevious={selectedSentIndex > 0 ? () => setSelectedSentLeadId(filteredSentDetailRows[selectedSentIndex - 1].lead.id || null) : undefined}
                        onNext={selectedSentIndex >= 0 && selectedSentIndex < filteredSentDetailRows.length - 1 ? () => setSelectedSentLeadId(filteredSentDetailRows[selectedSentIndex + 1].lead.id || null) : undefined}
                        previousDisabled={selectedSentIndex <= 0}
                        nextDisabled={selectedSentIndex === -1 || selectedSentIndex >= filteredSentDetailRows.length - 1}
                    >
                        <SentDetailPanel
                            title={selectedLead?.name}
                            description={selectedLead?.address || 'Здесь собраны история, follow-up и безопасное следующее действие.'}
                            statusLabel={selectedSentDetail.state === 'problem' ? 'Нужна проверка' : selectedSentDetail.state === 'ready' ? 'Готово к follow-up' : 'История'}
                            statusTone={selectedSentDetail.state === 'problem' ? 'danger' : selectedSentDetail.state === 'ready' ? 'info' : 'success'}
                            warning={selectedSentDetail.warning || ''}
                            canOpenLeadCard={Boolean(selectedLead)}
                            onOpenLeadCard={() => selectedLead && openLeadPreview(selectedLead)}
                            onFixChannel={selectedLead?.id ? () => chooseChannel(selectedLead.id || '', bestAvailableOutreachChannel(selectedLead)) : undefined}
                            leadContacts={selectedLead}
                            hasMessenger={selectedLead ? extractHasMessengers(selectedLead) : false}
                            channelStatusLabel={formatLeadChannel(selectedQueue?.channel || selectedLead?.selected_channel)}
                            channelPrimaryText={selectedQueue?.recipient_value || 'Контакт нужно уточнить в карточке лида'}
                            channelSecondaryText={selectedQueue?.delivery_status ? `Статус: ${formatQueueStatusLabel(selectedQueue.delivery_status)}` : 'Без статуса отправки'}
                            channelTone={selectedSentDetail.state === 'problem' ? 'warning' : 'success'}
                            responseStatusLabel={selectedQueue?.latest_human_outcome || selectedQueue?.latest_outcome || 'Без ответа'}
                            responsePrimaryText={selectedQueue?.latest_raw_reply ? 'Ответ уже зафиксирован' : 'Ответ ещё не зафиксирован'}
                            responseSecondaryText={selectedQueue?.latest_raw_reply || 'Можно подготовить follow-up в одном месте'}
                            responseTone={selectedQueue?.latest_raw_reply ? 'info' : 'default'}
                            contextLinks={selectedLead ? (
                                <>
                                    {buildLeadAuditLanguageLinks(selectedLead).map((item) => (
                                        <a key={item.language} href={item.href} target="_blank" rel="noreferrer">
                                            <Button type="button" size="sm" variant="outline">Аудит {item.label}</Button>
                                        </a>
                                    ))}
                                    <Button type="button" size="sm" variant="outline" onClick={() => openLeadPreview(selectedLead)}>Карточка лида</Button>
                                </>
                            ) : null}
                            primaryAction={selectedLead ? (selectedSentDetail.state === 'problem'
                                ? {
                                    label: 'Подготовить переотправку',
                                    onClick: () => prepareProblemLeadResend(selectedLead, selectedQueue?.channel || selectedLead.selected_channel),
                                    disabled: !selectedLead.id || !canPrepareAlternativeResend,
                                }
                                : {
                                    label: 'Сохранить follow-up',
                                    onClick: () => toast.success('Follow-up сохранён локально в интерфейсе'),
                                    disabled: !selectedLead.id,
                                }) : undefined}
                            secondaryActions={selectedLead ? [
                                {
                                    label: 'Отметить как отправленное вручную',
                                    onClick: () => selectedQueue?.id && markDelivery(selectedQueue.id, 'sent'),
                                    disabled: !selectedQueue?.id,
                                    variant: 'secondary',
                                },
                                {
                                    label: 'Открыть карточку лида',
                                    onClick: () => openLeadPreview(selectedLead),
                                },
                                {
                                    label: 'Пропустить этот лид',
                                    variant: 'outline',
                                    onClick: () => selectedLead.id && updateLeadStatusOptimistic(selectedLead.id, pipelineBoardColumnMeta.not_relevant.statusToSet),
                                    disabled: !selectedLead.id,
                                },
                            ] : []}
                            editorValue={selectedFollowUp}
                            onEditorChange={(value) => selectedLead && setFollowUpDrafts((prev) => ({ ...prev, [selectedLead.id || '']: value }))}
                            reviewDescription="Перед ручной отправкой посмотрите итоговый текст и убедитесь, что выбран правильный канал."
                            checklistItems={[
                                {
                                    id: 'channel',
                                    label: 'Выбранный канал ещё доступен',
                                    checked: !selectedSentDetail.warning,
                                    hint: selectedSentDetail.warning || 'Контакт для follow-up на месте.',
                                },
                                {
                                    id: 'followup',
                                    label: 'Follow-up подготовлен',
                                    checked: Boolean(selectedFollowUp.trim()),
                                    hint: selectedFollowUp.trim() ? 'Текст готов к ручной отправке.' : 'Добавьте follow-up, чтобы не возвращаться к этому лиду позже.',
                                },
                                {
                                    id: 'history',
                                    label: 'История отправки понятна',
                                    checked: Boolean(selectedQueue),
                                    hint: selectedQueue?.delivery_status ? `Последний статус: ${formatQueueStatusLabel(selectedQueue.delivery_status)}` : 'Нет зафиксированной отправки.',
                                },
                            ]}
                            historyRows={selectedQueue ? [
                                { label: 'Отправлено', value: selectedQueue.sent_at ? formatDateTime(selectedQueue.sent_at) : '—' },
                                { label: 'Последнее изменение', value: selectedQueue.updated_at ? formatDateTime(selectedQueue.updated_at) : '—' },
                                { label: 'Delivery', value: formatQueueStatusLabel(selectedQueue.delivery_status) },
                                { label: 'Outcome', value: selectedQueue.latest_human_outcome || selectedQueue.latest_outcome || '—' },
                            ] : []}
                            rawReply={selectedQueue?.latest_raw_reply || undefined}
                        />
                    </OutreachDetailModal>
                ) : null}
            </div>
        );
    };

    const visibleMainTab = activeWorkspace === 'raw'
        ? 'raw'
        : activeWorkspace === 'pipeline'
            ? 'inbox'
            : activeWorkspace === 'groups'
                ? 'groups'
            : activeWorkspace === 'analytics'
                ? 'analytics'
                : outreachTab;

    const renderIntakeContent = () => (
        <div className="space-y-6">
            <div className={`rounded-xl border p-4 ${lastSearchSummary.tone}`}>
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                        <div className="text-xs font-semibold uppercase tracking-wide opacity-80">Результат последнего запуска</div>
                        <div className="mt-1 text-base font-semibold">{lastSearchSummary.title}</div>
                        <div className="mt-1 text-sm opacity-90">{lastSearchSummary.hint}</div>
                    </div>
                    <div className="flex flex-wrap gap-2 text-xs">
                        <span className="rounded-full border border-current/15 bg-white/60 px-3 py-1">
                            Осталось в выдаче: {unresolvedSearchResults.length}
                        </span>
                        <span className="rounded-full border border-current/15 bg-white/60 px-3 py-1">
                            Дубликаты в поиске: {duplicateSearchResultsCount}
                        </span>
                        <span className="rounded-full border border-current/15 bg-white/60 px-3 py-1">
                            Уже в pipeline: {sourceFilteredLeads.length}
                        </span>
                    </div>
                </div>
            </div>

            <div className="space-y-4">
                <div className="text-sm font-medium">Поиск через Apify</div>
                <form onSubmit={handleSearch} className="flex flex-wrap gap-4 items-end">
                    <div className="grid w-56 items-center gap-1.5">
                        <label htmlFor="search-source">Источник</label>
                        <select
                            id="search-source"
                            value={searchSource}
                            onChange={(e) => {
                                const nextValue = String(e.target.value || '').trim().toLowerCase();
                                if (nextValue === 'apify_2gis') {
                                    setSearchSource('apify_2gis');
                                    return;
                                }
                                if (nextValue === 'apify_google') {
                                    setSearchSource('apify_google');
                                    return;
                                }
                                if (nextValue === 'apify_apple') {
                                    setSearchSource('apify_apple');
                                    return;
                                }
                                setSearchSource('apify_yandex');
                            }}
                            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                        >
                            <option value="apify_yandex">Apify Yandex</option>
                            <option value="apify_2gis">Apify 2GIS</option>
                            <option value="apify_google">Apify Google</option>
                            <option value="apify_apple">Apify Apple</option>
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
                        />
                    </div>
                    <Button type="submit" disabled={loading}>
                        {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Запустить поиск
                    </Button>
                </form>

                <div className="rounded-lg border border-border bg-muted/30 p-3">
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
                    <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
                        <div className="font-medium">
                            Поиск: {searchJob.status === 'queued' ? 'в очереди' :
                                searchJob.status === 'running' ? 'выполняется' :
                                    searchJob.status === 'completed' ? 'завершён' : 'ошибка'}
                        </div>
                        <div className="text-muted-foreground">Найдено: {searchJob.result_count || 0}</div>
                        {searchJob.status === 'running' && (
                            <div className="mt-2 text-muted-foreground">
                                Поиск продолжается. Результаты подтянутся автоматически сразу после завершения.
                            </div>
                        )}
                        {searchPollError && searchJob.status === 'running' && (
                            <div className="mt-2 text-amber-600">{searchPollError}</div>
                        )}
                        {searchJob.error_text && <div className="mt-2 text-red-600">{searchJob.error_text}</div>}
                    </div>
                )}
            </div>

            <div className="rounded-lg border border-border bg-muted/30 p-4 space-y-4">
                <div className="text-sm font-medium">Импортировать свой список</div>
                <div className="flex flex-wrap gap-3 items-center">
                    <Input type="file" accept=".json,application/json" onChange={handleImportFile} className="max-w-sm" />
                    <Button onClick={importLeads} disabled={importBusy || !importJson.trim()}>
                        {importBusy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Импортировать JSON
                    </Button>
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
            </div>

            <div className="rounded-lg border border-border bg-muted/30 p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                    <div className="text-sm font-medium">Необработанные лиды ({unprocessedLeads.length})</div>
                    {unprocessedLeads.length > 0 ? (
                        <Button size="sm" variant="outline" onClick={() => createLeadGroupFromIds(unprocessedLeads.map((lead) => lead.id || '').filter(Boolean))}>
                            Собрать всех в группу
                        </Button>
                    ) : null}
                </div>
                <div className="space-y-3">
                    {unprocessedLeads.length === 0 ? (
                        <div className="rounded-lg border border-dashed border-border bg-background p-4 text-xs text-muted-foreground">
                            Сюда попадают сохранённые лиды из ручного добавления, парсинга и импорта. Сейчас очередь необработанных пуста.
                        </div>
                    ) : (
                        unprocessedLeads.map(renderKanbanCard)
                    )}
                </div>
            </div>

            {duplicateSearchResultsCount > 0 ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50/80 p-3 text-sm">
                    <div className="font-medium text-amber-900">
                        В этом поиске найдено дублей: {duplicateSearchResultsCount}
                    </div>
                    <div className="mt-1 text-amber-800">
                        Эти компании скрыты из блока «Найденные компании», потому что уже совпали с существующими лидами по более строгим признакам.
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                        {duplicateReasonSummary.slice(0, 4).map((item) => (
                            <span
                                key={item.label}
                                className="rounded-full border border-amber-300 bg-white/70 px-3 py-1 text-xs text-amber-900"
                            >
                                {item.label}: {item.count}
                            </span>
                        ))}
                    </div>
                </div>
            ) : null}

            <div className="rounded-lg border border-border bg-muted/30 p-3">
                <div className="mb-2 text-sm font-medium">
                    Найденные компании ({unresolvedSearchResults.length})
                </div>
                <Table className="table-fixed">
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-[26%]">Компания</TableHead>
                            <TableHead className="w-[24%]">Адрес</TableHead>
                            <TableHead className="w-[22%]">Контакты</TableHead>
                            <TableHead className="w-[10%]">Рейтинг</TableHead>
                            <TableHead className="w-[18%]">Действие</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {unresolvedSearchResults.map((lead, index) => {
                            const key = lead.source_external_id || lead.google_id || `${lead.name}-${index}`;
                            return (
                                <TableRow key={key}>
                                    <TableCell className="font-medium">
                                        <div className="break-words">{lead.name}</div>
                                        <div className="text-xs text-muted-foreground break-words">{lead.category || 'Без категории'}</div>
                                        <div className="mt-1">
                                            <Badge variant="outline" className="text-[11px] font-normal">
                                                {sourceLabel(lead.source)}
                                            </Badge>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex items-start gap-1 text-sm">
                                            <MapPin className="mt-0.5 h-3 w-3 shrink-0" />
                                            <span className="min-w-0 break-words whitespace-normal" title={lead.address}>
                                                {lead.address || lead.city || '-'}
                                            </span>
                                        </div>
                                    </TableCell>
                                    <TableCell className="align-top">
                                        <ContactStack lead={lead} />
                                    </TableCell>
                                    <TableCell className="align-top">
                                        <div className="flex items-center gap-1">
                                            <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                                            {lead.rating ?? '-'}
                                            <span className="text-muted-foreground">({lead.reviews_count ?? 0})</span>
                                        </div>
                                    </TableCell>
                                    <TableCell className="align-top">
                                        <div className="flex flex-wrap gap-2">
                                            <Button
                                                size="sm"
                                                variant="default"
                                                onClick={() => saveLead(lead, 'new')}
                                                disabled={saving[key]}
                                            >
                                                {saving[key] ? <Loader2 className="mr-2 h-3 w-3 animate-spin" /> : <Save className="mr-2 h-3 w-3" />}
                                                В необработанные
                                            </Button>
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => saveSearchResultAsNotRelevant(lead)}
                                            >
                                                Сразу в неактуальные
                                            </Button>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            );
                        })}
                        {unresolvedSearchResults.length === 0 && (
                            <TableRow>
                                <TableCell colSpan={5} className="text-center py-6 text-muted-foreground">
                                    Пока нет сырых результатов. Запустите поиск или импорт.
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </div>
        </div>
    );

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Поиск клиентов</h2>
                    <p className="text-muted-foreground">
                        Единый рабочий экран: сначала добавляем лиды, затем ведём их по pipeline до контакта и follow-up.
                    </p>
                </div>
            </div>

            <Sheet open={Boolean(previewLead)} onOpenChange={(open) => {
                if (!open) {
                    closeLeadPreview();
                }
            }}>
            <SheetContent side="right" className="w-[96vw] overflow-y-auto p-0 sm:max-w-3xl lg:max-w-5xl">
                    {previewLead && (
                        <div className="p-4 sm:p-6">
                            <Suspense
                                fallback={
                                    <Card className="border-dashed">
                                        <CardContent className="flex items-center justify-center py-12 text-sm text-muted-foreground">
                                            Загружаем карточку лида...
                                        </CardContent>
                                    </Card>
                                }
                            >
                                <LeadCardPreviewPanel
                                    lead={previewLead}
                                    preview={previewSnapshot}
                                    loading={previewLoadingId === previewLead.id}
                                    error={previewError}
                                    generateAuditPageBusy={previewAuditPageBusy}
                                    generatedAuditPageUrl={previewAuditPageUrl}
                                    contactsBusy={previewContactsBusy}
                                    parseBusy={previewParseBusy}
                                    parseAutoRefreshing={previewAutoRefreshing}
                                    onGenerateAuditPage={generateAuditPageFromLeadPreview}
                                    onSaveContacts={saveLeadContactsFromPreview}
                                    onRunLiveParse={runLiveParseFromPreview}
                                    onRefreshPreview={refreshPreviewStatus}
                                    onMoveToPostponed={previewLead.id ? () => moveLeadToPostponed(previewLead.id || '') : undefined}
                                    onMoveToNotRelevant={previewLead.id ? () => moveLeadToNotRelevant(previewLead.id || '') : undefined}
                                    onMarkManualContact={previewLead.id ? () => markLeadManualContact(previewLead.id || '', previewLead.selected_channel || bestAvailableOutreachChannel(previewLead)) : undefined}
                                    onCreateLeadGroup={previewLead.id ? () => createLeadGroupFromIds([previewLead.id || '']) : undefined}
                                    onAddToExistingGroup={previewLead.id ? () => addLeadToExistingGroup(previewLead.id || '') : undefined}
                                    onRemoveFromGroup={previewLead.id ? (groupId: string) => removeLeadFromGroup(groupId, previewLead.id || '') : undefined}
                                    onClose={closeLeadPreview}
                                />
                            </Suspense>
                        </div>
                    )}
                </SheetContent>
            </Sheet>

            {groupModalOpen && selectedGroupId ? (
                <OutreachDetailModal
                    title={selectedGroupDetail?.name || 'Группа лидов'}
                    description={selectedGroupDetail?.description || 'Состав группы и быстрые ручные действия по каждому лиду.'}
                    onClose={() => {
                        setGroupModalOpen(false);
                        setSelectedGroupId(null);
                        setSelectedGroupDetail(null);
                        setSelectedGroupLeads([]);
                    }}
                >
                    <div className="space-y-4">
                        {groupBusy[selectedGroupId] ? (
                            <div className="flex items-center justify-center py-10 text-sm text-muted-foreground">
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Загружаем группу...
                            </div>
                        ) : (
                            <>
                                <div className="grid gap-3 md:grid-cols-4">
                                    <StatusSummaryCard
                                        title="Лидов"
                                        statusLabel={String(selectedGroupLeads.length)}
                                        statusVariant="secondary"
                                        primaryText="Всего в группе"
                                        secondaryText="Лиды остаются в своих этапах и могут входить в несколько групп."
                                    />
                                    <StatusSummaryCard
                                        title="Без аудита"
                                        statusLabel={String(selectedGroupLeads.filter((lead) => !hasLeadAudit(lead)).length)}
                                        statusVariant="outline"
                                        primaryText="Нужно добрать аудит"
                                        secondaryText="Хорошая точка для массовой подготовки."
                                    />
                                    <StatusSummaryCard
                                        title="Без канала"
                                        statusLabel={String(selectedGroupLeads.filter((lead) => !lead.selected_channel).length)}
                                        statusVariant="outline"
                                        primaryText="Канал не выбран"
                                        secondaryText="Можно сначала сегментировать по Telegram / WhatsApp / Email / Manual."
                                    />
                                    <StatusSummaryCard
                                        title="Отправлено"
                                        statusLabel={String(selectedGroupLeads.filter((lead) => getLeadPipelineStatus(lead) === PIPELINE_CONTACTED).length)}
                                        statusVariant="secondary"
                                        primaryText="Уже контактированы"
                                        secondaryText="Проверьте, кого оставить в группе, а кого убрать."
                                    />
                                </div>
                                <div className="space-y-3">
                                    {selectedGroupLeads.length === 0 ? (
                                        <div className="rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
                                            В группе пока нет лидов.
                                        </div>
                                    ) : (
                                        selectedGroupLeads.map((lead) => (
                                            <Card key={lead.id || lead.name} className="border border-border bg-background">
                                                <CardContent className="flex flex-col gap-3 p-4">
                                                    <LeadMetaSummary lead={lead} showChannel />
                                                    <div className="flex flex-wrap gap-2">
                                                        <Badge variant="outline">{pipelineStatusLabel(getLeadPipelineStatus(lead))}</Badge>
                                                        {(lead.group_count || 0) > 1 ? <Badge variant="outline">Ещё групп: {(lead.group_count || 1) - 1}</Badge> : null}
                                                    </div>
                                                    <WorkflowActionRow
                                                        primary={{ label: 'Карточка лида', onClick: () => lead.id && openLeadPreviewById(lead.id, lead) }}
                                                        secondary={[
                                                            {
                                                                label: 'Отправлено вручную',
                                                                onClick: () => lead.id && markLeadManualContact(lead.id, lead.selected_channel || bestAvailableOutreachChannel(lead)),
                                                            },
                                                            {
                                                                label: 'Отложить',
                                                                onClick: () => lead.id && moveLeadToPostponed(lead.id),
                                                            },
                                                            {
                                                                label: 'Неактуален',
                                                                variant: 'destructive',
                                                                onClick: () => lead.id && moveLeadToNotRelevant(lead.id),
                                                            },
                                                            {
                                                                label: 'Убрать из группы',
                                                                variant: 'ghost',
                                                                onClick: () => lead.id && removeLeadFromGroup(selectedGroupId, lead.id),
                                                            },
                                                        ]}
                                                    />
                                                </CardContent>
                                            </Card>
                                        ))
                                    )}
                                </div>
                            </>
                        )}
                    </div>
                </OutreachDetailModal>
            ) : null}

            <Sheet open={intakeOpen} onOpenChange={setIntakeOpen}>
                <SheetContent side="right" className="w-[96vw] overflow-y-auto sm:max-w-5xl">
                    <SheetHeader>
                        <SheetTitle>Добавить лиды</SheetTitle>
                        <SheetDescription>
                            Сырые результаты поиска, ручной ввод и импорт. Здесь пополняем pipeline, не смешивая intake с рабочей воронкой.
                        </SheetDescription>
                    </SheetHeader>
                    <div className="mt-6">{renderIntakeContent()}</div>
                </SheetContent>
            </Sheet>

            <Sheet open={filtersOpen} onOpenChange={setFiltersOpen}>
                <SheetContent side="right" className="w-[96vw] overflow-y-auto sm:max-w-2xl">
                    <SheetHeader>
                        <SheetTitle>Все фильтры</SheetTitle>
                        <SheetDescription>
                            Расширенные фильтры для pipeline. Основной экран остаётся лёгким, а детальный отбор — здесь.
                        </SheetDescription>
                    </SheetHeader>
                    <div className="mt-6 space-y-4">
                        <div className="grid gap-3 md:grid-cols-2">
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
                            <select className="border rounded-md px-3 py-2 bg-background text-sm" value={filters.hasTelegram} onChange={(e) => setFilters(prev => ({ ...prev, hasTelegram: e.target.value }))}>
                                <option value="">Telegram: любой</option>
                                <option value="yes">Есть Telegram</option>
                                <option value="no">Нет Telegram</option>
                            </select>
                            <select className="border rounded-md px-3 py-2 bg-background text-sm" value={filters.hasWhatsApp} onChange={(e) => setFilters(prev => ({ ...prev, hasWhatsApp: e.target.value }))}>
                                <option value="">WhatsApp: любой</option>
                                <option value="yes">Есть WhatsApp</option>
                                <option value="no">Нет WhatsApp</option>
                            </select>
                            <select className="border rounded-md px-3 py-2 bg-background text-sm" value={filters.hasMax} onChange={(e) => setFilters(prev => ({ ...prev, hasMax: e.target.value }))}>
                                <option value="">Max: любой</option>
                                <option value="yes">Есть Max</option>
                                <option value="no">Нет Max</option>
                            </select>
                            <select className="border rounded-md px-3 py-2 bg-background text-sm" value={filters.hasVk} onChange={(e) => setFilters(prev => ({ ...prev, hasVk: e.target.value }))}>
                                <option value="">VK: любой</option>
                                <option value="yes">Есть VK</option>
                                <option value="no">Нет VK</option>
                            </select>
                            <select className="border rounded-md px-3 py-2 bg-background text-sm" value={filters.hasMessengers} onChange={(e) => setFilters(prev => ({ ...prev, hasMessengers: e.target.value }))}>
                                <option value="">Мессенджеры: любые</option>
                                <option value="yes">Есть мессенджеры</option>
                                <option value="no">Нет мессенджеров</option>
                            </select>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <Button variant="outline" onClick={resetFilters}>Сбросить фильтры</Button>
                            <Button variant="secondary" onClick={() => applyPreset('best')}>Лучшие лиды</Button>
                            <Button variant="secondary" onClick={() => applyPreset('many_reviews')}>Много отзывов</Button>
                            <Button variant="secondary" onClick={() => applyPreset('low_rating')}>Низкий рейтинг</Button>
                        </div>
                    </div>
                </SheetContent>
            </Sheet>

            <ProspectingWorkspaceTabs
                activeWorkspace={activeWorkspace}
                onWorkspaceChange={(value) => setActiveWorkspace(toWorkspaceTab(value))}
                workspaces={[
                    { value: 'raw', label: 'Необработанные', count: unprocessedLeads.length + unresolvedSearchResults.length },
                    { value: 'pipeline', label: 'Воронка', count: sourceFilteredLeads.length },
                    { value: 'groups', label: 'Группы лидов', count: leadGroups.length },
                    { value: 'outreach', label: 'Аутрич', count: drafts.length + visibleQueueItems.length + sentDetailRows.length },
                    { value: 'analytics', label: 'Аналитика' },
                ]}
                outreachTabs={[
                    { value: 'drafts', label: 'Черновики', count: drafts.length },
                    { value: 'queue', label: 'В очереди', count: visibleQueueItems.length },
                    { value: 'sent', label: 'Отправлено', count: sentDetailRows.length },
                ]}
                activeOutreachTab={outreachTab}
                onOutreachTabChange={(value) => setOutreachTab(toOutreachTab(value))}
            />

            <Tabs value={visibleMainTab} className="w-full">
                <TabsContent value="raw" className="space-y-6">
                    <ProspectingIntakePanel
                        title="Необработанные"
                        description="Все новые лиды сначала попадают сюда. Здесь разбираем ручной ввод, импорт и результаты поиска перед переводом в работу или в неактуальные."
                        badges={[
                            { label: 'Найдено в последнем поиске', value: searchJob?.result_count || 0 },
                            { label: 'Сохранено в необработанные', value: unprocessedLeads.length },
                            { label: 'Ещё не сохранено из выдачи', value: unresolvedSearchResults.length },
                            { label: 'Дубликаты в последнем поиске', value: duplicateSearchResultsCount },
                        ]}
                    >
                        {renderIntakeContent()}
                    </ProspectingIntakePanel>
                </TabsContent>

                <TabsContent value="inbox" className="space-y-6">
                    <ProspectingPipelineHeader
                        totalLeads={sourceFilteredLeads.length}
                        summary={pipelineHeaderSummary}
                        search={pipelineSearch}
                        onSearchChange={setPipelineSearch}
                        filters={{
                            source: filters.source,
                            hasTelegram: filters.hasTelegram,
                            hasWhatsApp: filters.hasWhatsApp,
                            hasMax: filters.hasMax,
                            hasEmail: filters.hasEmail,
                            hasWebsite: filters.hasWebsite,
                            hasVk: filters.hasVk,
                        }}
                        onSourceChange={(value) => setFilters(prev => ({ ...prev, source: value }))}
                        onHasTelegramChange={(value) => setFilters(prev => ({ ...prev, hasTelegram: value }))}
                        onHasWhatsAppChange={(value) => setFilters(prev => ({ ...prev, hasWhatsApp: value }))}
                        onHasMaxChange={(value) => setFilters(prev => ({ ...prev, hasMax: value }))}
                        onHasEmailChange={(value) => setFilters(prev => ({ ...prev, hasEmail: value }))}
                        onHasWebsiteChange={(value) => setFilters(prev => ({ ...prev, hasWebsite: value }))}
                        onHasVkChange={(value) => setFilters(prev => ({ ...prev, hasVk: value }))}
                        onOpenFilters={() => setFiltersOpen(true)}
                        onOpenIntake={() => setIntakeOpen(true)}
                        pipelineView={pipelineView}
                        onPipelineViewChange={setPipelineView}
                        quickFilter={quickFilter}
                        onQuickFilterChange={setQuickFilter}
                        onResetFilters={resetFilters}
                        onApplyBestPreset={() => applyPreset('best')}
                        onApplyManyReviewsPreset={() => applyPreset('many_reviews')}
                    />

                    {pipelineView === 'kanban' ? (
                        <div className="flex gap-4 overflow-x-auto pb-6">
                            {pipelineBoardColumns.map((column) => (
                                <div
                                    key={column.id}
                                    onDragOver={handleColumnDragOver(column.id)}
                                    onDragLeave={() => setDropColumnId(null)}
                                    onDrop={handleColumnDrop(column.id)}
                                    className={`min-w-[280px] flex-1 rounded-xl border border-border bg-muted/30 p-3 transition ${dropColumnId === column.id ? 'ring-2 ring-primary/40' : ''}`}
                                >
                                    <div className="flex items-start justify-between gap-2 border-b border-border pb-2">
                                        <div>
                                            <div className="text-sm font-semibold">{column.label}</div>
                                            <div className="text-xs text-muted-foreground">{column.description}</div>
                                        </div>
                                        <Badge variant="secondary">{column.leads.length}</Badge>
                                    </div>
                                    <div className="mt-3 space-y-3">
                                        {loadingLeads ? (
                                            <div className="flex items-center justify-center py-6 text-sm text-muted-foreground">
                                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                                Загрузка лидов...
                                            </div>
                                        ) : column.leads.length === 0 ? (
                                            <div className="rounded-lg border border-dashed border-border bg-background p-4 text-xs text-muted-foreground">
                                                Здесь пока нет лидов.
                                            </div>
                                        ) : (
                                            column.leads.map(renderKanbanCard)
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {loadingLeads ? (
                                <div className="flex items-center justify-center py-10 text-sm text-muted-foreground">
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Загрузка лидов...
                                </div>
                            ) : visiblePipelineLeads.length === 0 ? (
                                <Card className="border-dashed">
                                    <CardContent className="py-10 text-center text-sm text-muted-foreground">
                                        По текущим фильтрам и поиску здесь пока ничего нет.
                                    </CardContent>
                                </Card>
                            ) : (
                                visiblePipelineLeads.map(renderKanbanCard)
                            )}
                        </div>
                    )}

                    <StickyBulkActionBar count={selectedPipelineLeadIds.length} label="Выбранные лиды можно собрать в группу, отложить, убрать в неактуальные или отметить как отправленные вручную.">
                        <Button size="sm" onClick={() => createLeadGroupFromIds(selectedPipelineLeadIds)} disabled={selectedPipelineLeadIds.length === 0}>
                            Собрать в группу
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => Promise.all(selectedPipelineLeadIds.map((leadId) => markLeadManualContact(leadId))).catch(() => undefined)} disabled={selectedPipelineLeadIds.length === 0}>
                            Отправлено вручную
                        </Button>
                    </StickyBulkActionBar>
                </TabsContent>

                <TabsContent value="analytics" className="space-y-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Эффективность воронки</CardTitle>
                            <CardDescription>
                                Отдельный аналитический экран: объёмы, конверсия, потери между этапами и тренд за 7/30 дней.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <AnalyticsSummaryGrid
                                items={[
                                    { key: 'found', label: 'Найдено', value: pipelineEfficiencySummary.foundCount, helper: 'Последний поиск / импорт' },
                                    { key: 'pipeline', label: 'В pipeline', value: pipelineEfficiencySummary.pipelineCount, helper: `Сохранение: ${pipelineEfficiencySummary.saveRate}` },
                                    { key: 'contacted', label: 'Отправлено', value: contactedLeadCount, helper: `Из pipeline: ${pipelineEfficiencySummary.readyRate}` },
                                    { key: 'waiting', label: 'Ждём ответ', value: waitingReplyLeadCount, helper: 'Сообщение ушло, но ответа ещё нет' },
                                    { key: 'replied', label: 'Ответили', value: repliedLeadCount, helper: `От ответа: ${pipelineEfficiencySummary.replyRate}` },
                                    { key: 'converted', label: 'Конвертировано', value: convertedLeadCount, helper: `Из ответа: ${pipelineEfficiencySummary.qualifiedRate}` },
                                    { key: 'inactive', label: 'Неактуально / отложено', value: notRelevantLeadCount + postponedLeadCount, helper: 'Сняты с процесса или отложены' },
                                ]}
                            />

                            <AnalyticsMetricGrid
                                items={pipelineStageMetrics.map((stage, index) => {
                                    const previousCount = index > 0 ? pipelineStageMetrics[index - 1]?.count || 0 : 0;
                                    return {
                                        key: stage.key,
                                        label: `${index + 1}. ${stage.label}`,
                                        hint: stage.hint,
                                        count: stage.count,
                                        conversion: stage.conversion,
                                        dropOff: formatDropOff(stage.count, previousCount),
                                    };
                                })}
                            />

                            <AnalyticsWindowGrid
                                title="Тренд за 7 / 30 дней"
                                description="Сравнение свежего потока и качества прохождения по стадиям лида."
                                items={pipelineWindowMetrics.map((window) => ({
                                    key: window.key,
                                    label: window.label,
                                    badgeLabel: 'Pipeline',
                                    badgeValue: window.pipelineCount,
                                    stats: [
                                        { key: `${window.key}-progress`, label: 'В работе', value: window.inProgressCount, helper: `Conv: ${formatConversion(window.inProgressCount, window.pipelineCount)}` },
                                        { key: `${window.key}-contacted`, label: 'Отправлено', value: window.contactedCount, helper: `Conv: ${formatConversion(window.contactedCount, window.inProgressCount)}` },
                                        { key: `${window.key}-inactive`, label: 'Неактуально / отложено', value: window.closedCount, helper: `Conv: ${formatConversion(window.closedCount, window.pipelineCount)}` },
                                        { key: `${window.key}-queue`, label: 'Ждём ответ', value: window.deliveredCount, helper: `Conv: ${formatConversion(window.deliveredCount, window.contactedCount)}` },
                                        { key: `${window.key}-reply`, label: 'Ответили', value: window.reactionCount, helper: `Conv: ${formatConversion(window.reactionCount, window.deliveredCount)}` },
                                        { key: `${window.key}-positive`, label: 'Позитивный ответ', value: window.positiveCount, helper: `Conv: ${formatConversion(window.positiveCount, window.reactionCount)}` },
                                    ],
                                }))}
                            />

                            <AnalyticsSection
                                title="Операторский блок outreach"
                                description="Отдельно по черновикам, отправке и ответам, чтобы видеть узкие места уже после отбора."
                            >
                                <AnalyticsMetricGrid items={outreachOperatorMetrics} columnsClassName="md:grid-cols-3" />
                            </AnalyticsSection>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="drafts" className="space-y-4">
                    {renderDraftsWorkspace()}
                </TabsContent>

                <TabsContent value="groups" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>Группы лидов</CardTitle>
                            <CardDescription>
                                Рабочие подборки для ручной сегментации, аудитов и дальнейшей отправки. Лид остаётся в своей стадии и может входить в несколько групп.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {loadingGroups ? (
                                <div className="flex items-center justify-center py-10 text-sm text-muted-foreground">
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Загружаем группы...
                                </div>
                            ) : leadGroups.length === 0 ? (
                                <div className="rounded-lg border border-dashed border-border bg-background p-6 text-sm text-muted-foreground">
                                    Групп пока нет. Выделите лиды в этапе «В работе» или «Необработанные» и соберите первую группу.
                                </div>
                            ) : (
                                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                                    {leadGroups.map((group) => (
                                        <Card key={group.id} className="border border-border bg-background shadow-sm">
                                            <CardHeader className="pb-3">
                                                <div className="flex items-start justify-between gap-3">
                                                    <div>
                                                        <CardTitle className="text-base">{group.name}</CardTitle>
                                                        <CardDescription className="mt-1">
                                                            {group.description || 'Рабочая группа для ручной обработки и массовых действий.'}
                                                        </CardDescription>
                                                    </div>
                                                    <Badge variant="outline">{group.leads_count || 0}</Badge>
                                                </div>
                                            </CardHeader>
                                            <CardContent className="space-y-3">
                                                <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                                                    <div>Без аудита: <span className="font-medium text-foreground">{group.without_audit_count || 0}</span></div>
                                                    <div>Без канала: <span className="font-medium text-foreground">{group.without_channel_count || 0}</span></div>
                                                    <div>Без контакта: <span className="font-medium text-foreground">{group.without_contact_count || 0}</span></div>
                                                    <div>Черновиков: <span className="font-medium text-foreground">{group.drafts_count || 0}</span></div>
                                                </div>
                                                <WorkflowActionRow
                                                    primary={{ label: 'Открыть группу', onClick: () => openLeadGroup(group.id) }}
                                                    secondary={[
                                                        {
                                                            label: 'Добавить выбранные',
                                                            onClick: () => addSelectedLeadsToGroup(group.id),
                                                            disabled: selectedPipelineLeadIds.length === 0 || Boolean(groupBusy[group.id]),
                                                        },
                                                    ]}
                                                />
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="queue" className="space-y-4">
                    {renderQueueWorkspace()}
                </TabsContent>

                <TabsContent value="sent" className="space-y-4">
                    {renderSentWorkspace()}
                </TabsContent>
            </Tabs>
        </div>
    );
};

export default ProspectingManagement;
