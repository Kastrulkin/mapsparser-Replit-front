import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/services/api';
import type { ServiceProposal } from './ServiceProposals';

type Keyword = { text: string; views: number | null; source: string; dated: string };
export type PhotoReport =
  | { status: 'queued' | 'running' | 'unavailable'; note?: string }
  | { status: 'ready'; checked_at: string; library_categories: string[]; library_count: number;
      missing: { label: string; tip: string }[];
      shortlist: { key: string; label: string; source_url: string; image_url: string }[];
      review: { key: string; image_url: string; card_url: string; provider: string }[];
      sources: { url: string; provider: string; status: 'sample' | 'unavailable'; count: number }[];
      cover?: string | null; rejected: number; note?: string };
export type WebsiteAudit =
  | { status: 'queued' | 'running' | 'unavailable'; note?: string }
  | { status: 'ready'; checked_at: string; pages: {
      url: string;
      findings: { rule: string; priority: 'fix' | 'review'; title: string; fix: string }[];
    }[] };
export type Source = {
  key: string;
  url: string;
  kind: 'website' | 'map' | 'social';
  provider: string;
  status: string;
  note?: string;
  found_on?: string;
  competitor: boolean;
  service_count: number;
  photo_candidate_count?: number;
  website_audit?: WebsiteAudit;
};
type Finding = { key: string; text: string; url: string; accepted?: boolean; observed_at?: string };
export type Comparison = {
  url: string;
  name: string;
  platform: string;
  checked_at: string;
  our_checked_at: string;
  ours?: { rating?: string; reviews?: string };
  theirs?: { rating?: string; reviews?: string };
  our_services: string[];
  their_services: string[];
};
export type Setup = {
  business_id: string;
  revision: number;
  can_edit: boolean;
  origin: string;
  provisional: boolean;
  viewer_is_owner?: boolean;
  profile: Record<string, string | null>;
  sources: Source[];
  services: ServiceProposal[];
  seo_dirty: boolean;
  seo_prepared: boolean;
  saved: boolean;
  started: boolean;
  activity_type?: string;
  category_keywords: Keyword[];
  photo_report?: PhotoReport | null;
  draft_status?: 'queued' | 'running' | 'failed' | 'needs_source' | null;
  draft_ready?: boolean;
  report_ready?: boolean;
  facts: Finding[];
  profile_choices: (Finding & { field: string })[];
  comparisons: Comparison[];
  activity: { message: string; reply: string; at: string }[];
};
type SetupResponse = { available: boolean; can_edit?: boolean; setup?: Setup | null; message?: string };
export type Action = { action: string; key?: string; message?: string; name?: string; description?: string; text?: string; category?: string; auto?: boolean };
export type Invite = { email: string; invite_url?: string; login_path?: string; existing_account: boolean; already_signed_in?: boolean };

export const setupUrl = (id: string) => '/operator/initial-setup/' + encodeURIComponent(id);
const SAVE_TIMEOUT_MS = 15_000;
const VERIFY_SAVE_TIMEOUT_MS = 5_000;

function requestDeadline(duration: number) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), duration);
  return { signal: controller.signal, clear: () => window.clearTimeout(timer) };
}

export function visibleError(error: unknown) {
  if (error instanceof Error && error.message) return error.message;
  if (error && typeof error === 'object' && 'response' in error) {
    const response = error.response;
    if (response && typeof response === 'object' && 'data' in response) {
      const data = response.data;
      if (data && typeof data === 'object' && 'error' in data && typeof data.error === 'string') return data.error;
    }
  }
  return 'Не удалось загрузить или сохранить настройку. Попробуйте ещё раз.';
}

export function useInitialBusinessSetup(businessId: string | null, active: boolean) {
  const [data, setData] = useState<SetupResponse | null>(null);
  const [error, setError] = useState('');
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [saveError, setSaveError] = useState('');
  const busy = pendingAction !== null;
  const [pendingSources, setPendingSources] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState('');
  const context = active ? businessId : null;
  const generation = useRef(0);
  const mutation = useRef(0);
  const scope = useRef<string | null>(null);
  const inFlight = useRef(false);
  scope.current = context;
  const refresh = useCallback(async (signal?: AbortSignal) => {
    if (!context) return;
    const issued = ++generation.current;
    try {
      const response = await api.get(setupUrl(context), { signal });
      if (scope.current === context && generation.current === issued && !signal?.aborted) {
        setData(response.data);
        setError('');
        return response.data;
      }
    } catch (err) {
      if (scope.current === context && generation.current === issued && !signal?.aborted) setError(visibleError(err));
    }
  }, [context]);
  useEffect(() => {
    mutation.current += 1;
    setData(null);
    setNotice('');
    setError('');
    setPendingAction(null);
    setSaveError('');
    setPendingSources(false);
    inFlight.current = false;
    if (!context) return;
    const controller = new AbortController();
    setLoading(true);
    void refresh(controller.signal).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [context, refresh]);

  const state = context && data?.setup?.business_id === context ? data.setup : null;
  const reading = state?.sources.some(source => source.status === 'queued' || source.status === 'running') ?? false;
  const polling = reading || state?.draft_status === 'queued' || state?.draft_status === 'running' || state?.photo_report?.status === 'queued' || state?.photo_report?.status === 'running'
    || state?.sources.some(source => source.website_audit?.status === 'queued' || source.website_audit?.status === 'running');
  useEffect(() => {
    if (!context || !polling || busy) return;
    const controller = new AbortController();
    const interval = window.setInterval(() => {
      if (!inFlight.current) void refresh(controller.signal);
    }, 2500);
    return () => { window.clearInterval(interval); controller.abort(); };
  }, [context, polling, busy, refresh]);

  const send = async (action: Action) => {
    if (!context || inFlight.current) return false;
    inFlight.current = true;
    generation.current += 1;
    const issued = ++mutation.current;
    const isCurrent = () => scope.current === context && mutation.current === issued;
    setPendingAction(action.action);
    setPendingSources(action.action === 'read' || action.action === 'retry'
      || Boolean((action.action === 'start' || action.action === 'message') && action.message?.includes('://')));
    setError('');
    setNotice('');
    setSaveError('');
    const deadline = action.action === 'save' ? requestDeadline(SAVE_TIMEOUT_MS) : null;
    try {
      const payload = { ...action, revision: state?.revision };
      const result = deadline
        ? await api.post(setupUrl(context), payload, { signal: deadline.signal })
        : await api.post(setupUrl(context), payload);
      if (!isCurrent()) return false;
      setData(result.data);
      if (!deadline) setNotice(result.data.message || '');
      return result.data.available;
    } catch (err) {
      if (!isCurrent()) return false;
      if (deadline) {
        const timedOut = deadline.signal.aborted;
        deadline.clear();
        const verification = requestDeadline(VERIFY_SAVE_TIMEOUT_MS);
        const observed: SetupResponse | undefined = await refresh(verification.signal).finally(verification.clear);
        if (!isCurrent()) return false;
        setError('');
        // A missing response does not tell us whether the server committed the save.
        if (observed?.setup?.business_id === context && observed.setup.saved) return true;
        setSaveError(timedOut
          ? 'Сервер не подтвердил сохранение. Попробуйте ещё раз.'
          : visibleError(err));
        return false;
      }
      await refresh();
      if (isCurrent()) setError(visibleError(err));
      return false;
    } finally {
      deadline?.clear();
      if (isCurrent()) {
        inFlight.current = false;
        setPendingAction(null);
        setPendingSources(false);
      }
    }
  };
  return { state, available: data?.available, canEdit: state?.can_edit ?? data?.can_edit ?? false, error, busy,
    saving: pendingAction === 'save', saveError, loading, notice, reading, pendingSources, send, refresh };
}
