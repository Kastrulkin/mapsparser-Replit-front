import type { ProgressPayload } from '@/components/telegram/ProgressMobileModule';
import type { MobileScope } from '@/components/telegram/ScopeProvider.logic';
import type { MobileJob } from '@/lib/mobileDataClient';

export type AttentionItem = {
  id?: string;
  title?: string;
  description?: string;
  count?: number;
  status?: string;
  severity?: string;
  progress?: number | null;
  action_unavailable_reason?: string;
  category?: string;
  screen?: string;
  cta?: { href?: string };
  target_scope?: { kind?: string; id?: string };
};

export type Metric = {
  key?: string;
  label?: string;
  value?: string | number | null;
  source?: string;
  source_label?: string;
  updated_at?: string;
};

export type Summary = {
  scope?: MobileScope;
  attention_items?: AttentionItem[];
  metrics?: Metric[];
  data_warnings?: string[];
};

export type Catalog = {
  platform?: MobileScope | null;
  networks?: NetworkCatalogItem[];
  businesses?: BusinessCatalogItem[];
  total_choices?: number;
  business_cursor?: string;
  next_business_cursor?: string | null;
  has_more_businesses?: boolean;
};

export type NetworkCatalogItem = { id?: string; name?: string; locations_count?: number };

export type BusinessCatalogItem = { id?: string; name?: string; address?: string; network_id?: string | null; network_name?: string | null };

export type NetworkLocationsResult = {
  items?: BusinessCatalogItem[];
  counts?: { total?: number };
  cursor?: string | null;
};

export type Bootstrap = {
  success?: boolean;
  error?: string;
  user?: { id?: string; name?: string; is_superadmin?: boolean };
  selected_scope?: MobileScope;
  summary?: Summary;
  catalog?: Catalog;
  web_session_token?: string;
  navigation?: NavigationItem[];
  today_v2_enabled?: boolean;
  resolved_deep_link?: { screen?: string; item_type?: string | null; item_id?: string | null; filters?: Record<string, string>; fallback_applied?: boolean };
  active_job?: MobileJob | null;
};

export type NavigationItem = {
  key: string;
  label: string;
  group: 'primary' | 'more';
  status: 'available' | 'read_only' | 'hidden';
  reason?: string;
  capability?: string;
  required_tier?: string;
  required_tier_name?: string;
  billing_url?: string;
  preview_available?: boolean;
  available_actions?: string[];
  supported_scopes?: string[];
  deep_link_targets?: string[];
  version?: number;
};

export type Workspace = {
  items?: AttentionItem[];
  counts?: { attention?: number; total?: number };
  summary?: Summary;
  data_warnings?: string[];
};

export type Review = {
  id: string;
  business_id?: string;
  location_name?: string;
  source?: string;
  rating?: number;
  author_name?: string;
  text?: string;
  response_text?: string;
  published_at?: string;
  loaded_at?: string;
  updated_at?: string;
  reply_draft_id?: string;
  reply_draft_text?: string;
  reply_draft_status?: string;
};

export type ReviewResult = {
  items?: Review[];
  counts?: { total?: number; unanswered?: number; drafts?: number };
  cursor?: string | null;
  filters?: { sources?: string[]; ratings?: number[]; locations?: Array<{ id: string; name: string }> };
};

export type OperatorMessage = {
  input_type?: string;
  id?: string;
  role: 'user' | 'operator';
  text: string;
  status?: string;
  capability?: string;
  created_at?: string;
  screen?: string;
  action_id?: string;
  action_error?: string;
};

export type OperatorActionDecision = 'confirm' | 'reject';

export type ModuleItem = { id?: string; business_id?: string; kind?: string; title?: string; subtitle?: string; business_name?: string; status?: string; rating?: number; reviews_count?: number; seo_score?: number; price?: string; category?: string; source?: string; updated_at?: string; amount?: string | number; previous_amount?: string | number; unit?: string; metric_key?: string; period_label?: string; day?: string; orders_count?: number; transaction_type?: string; selected_channel?: string; run_id?: string; run_status?: string; error_text?: string; provider_sources?: string[]; parse_status?: string; parse_source?: string; parse_updated_at?: string; refresh_cost_credits?: number; scheduled_refresh_cost_credits?: number; review_sync_enabled?: boolean; review_sync_interval_hours?: number; review_sync_schedule_mode?: string; review_sync_schedule_days?: number[]; review_sync_schedule_time?: string; review_sync_next_run_at?: string; review_sync_last_run_at?: string; review_sync_last_status?: string; plan_id?: string; plan_title?: string; plan_period_days?: number; scheduled_for?: string; content_type?: string; draft_text?: string };

export type NotificationPreferences = { daily_digest?: boolean; reviews?: boolean; tasks?: boolean; errors?: boolean; agent_results?: boolean; finance_rhythm?: boolean; content_publications?: boolean };

export type FinanceValue = string | number | boolean | null | undefined;

export type FinanceRecommendation = { code?: string; title?: string; text?: string; severity?: string; target_metric?: string | null; data_needed?: string[] };

export type FinanceDashboardMobile = {
  period?: { start_date?: string; end_date?: string };
  kpis?: Record<string, FinanceValue>;
  explanations?: Record<string, string>;
  statuses?: Record<string, string>;
  data_quality?: { score?: number; missing?: string[]; approximate?: string[]; precise?: string[] };
  recommendations?: FinanceRecommendation[];
  action_logs?: Array<{ action_key?: string; status?: string; completed_at?: string | null }>;
  action_impact?: { completed_actions_count?: number; deltas?: Array<{ metric?: string; current?: FinanceValue; previous?: FinanceValue; delta?: FinanceValue; direction?: string }> };
  period_history?: Array<{ label?: string; period_start?: string; period_end?: string; revenue?: FinanceValue; operating_margin?: FinanceValue; no_show_rate?: FinanceValue; rebooking_rate?: FinanceValue; workplace_occupancy?: FinanceValue }>;
  services?: Array<Record<string, FinanceValue>>;
  staff?: Array<Record<string, FinanceValue>>;
  workplaces?: Array<Record<string, FinanceValue>>;
};

export type ModuleData = { items?: ModuleItem[]; counts?: { total?: number }; as_of?: string; data_warnings?: string[]; status?: string; access?: NavigationItem; preview?: { title?: string; summary?: string; skeleton_count?: number }; preferences?: NotificationPreferences; available_actions?: Array<{ key?: string; label?: string }>; filters?: { period_days?: number[]; density?: string[] }; finance_dashboard?: FinanceDashboardMobile };

export type Tab = 'today' | 'tasks' | 'feed' | 'reviews' | 'progress' | 'operator' | 'more' | 'menu';

export type TelegramWebApp = {
  downloadFile?: (params: { url: string; file_name: string }) => void;
  isVersionAtLeast?: (version: string) => boolean;
  initData?: string;
  initDataUnsafe?: { start_param?: string };
  ready?: () => void;
  expand?: () => void;
  openTelegramLink?: (url: string) => void;
  BackButton?: { show: () => void; hide: () => void; onClick: (callback: () => void) => void; offClick: (callback: () => void) => void };
};

export type ReviewsProps = {
  result: ReviewResult; summary?: Summary; status: string; setStatus: (value: string) => void;
  source: string; setSource: (value: string) => void; rating: string; setRating: (value: string) => void;
  location: string; setLocation: (value: string) => void; selected: string[]; setSelected: (value: string[]) => void;
  loading: boolean; actionBusy: string; generate: (review: Review, confirmed: boolean) => Promise<void>;
  updateDraft: (review: Review, text: string) => Promise<void>; markPublished: (review: Review) => Promise<void>;
  prepareSelected: () => void; loadMore: () => void;
};

export type ModuleScreenProps = {
  module: string; focusItemId?: string; scope?: MobileScope; access?: NavigationItem; data: ModuleData; loading: boolean; progressData?: ProgressPayload | null; progressLoading: boolean; saving: boolean; actionBusy: string;
  saveNotifications: (preferences: NotificationPreferences) => Promise<void>;
  updateService: (item: ModuleItem, values: { name: string; description: string; price: string; category: string }) => Promise<void>;
  generateContentDraft: (item: ModuleItem) => Promise<void>;
  updateContentItem: (item: ModuleItem, values: { theme: string; draft_text: string; scheduled_for: string }) => Promise<void>;
  reload: () => Promise<void>;
  openTarget: (screen?: string, targetScope?: { kind?: string; id?: string }) => void;
  track: (eventName: string, target?: string) => void;
  trackProduct: (eventName: 'mission_open' | 'statistics_flow_opened' | 'statistics_preview_created' | 'statistics_preview_confirmed' | 'crm_request_created', objectId?: string) => void;
  openTasks: () => void;
  requestCrm: (values: { crmName: string; crmUrl: string; contact: string; comment: string }) => Promise<void>;
  back: () => void;
};

export type RecognizedSale = { id?: string; transaction_date?: string; amount?: number; title?: string; sale_type?: 'service' | 'upsell' | 'cross_sell'; notes?: string };

export type FinanceManualMode = 'entry' | 'service' | 'staff' | 'workplace';

export type FinanceImportPreview = { file_name?: string; rows_total?: number; valid_rows?: number; failed_rows?: number; rows_imported?: number; rows_skipped?: number; rows_failed?: number; mapping?: Record<string, string>; preview?: Array<Record<string, FinanceValue>>; errors?: Array<{ row?: number; errors?: string[] }> };

export type FinanceThreshold = { metric_key?: string; label?: string; unit?: string; source?: string; green_min?: FinanceValue; green_max?: FinanceValue; yellow_min?: FinanceValue; yellow_max?: FinanceValue; red_rule?: string };

export type FinanceTransaction = { id?: string; transaction_date?: string | null; amount?: number; services?: string[] | null; notes?: string | null; client_type?: string | null };
