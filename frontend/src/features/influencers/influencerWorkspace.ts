export type InfluencerAccess = {
  status: 'available' | 'registration_required' | 'payment_required' | 'setup_required' | 'approval_required' | 'unavailable';
  reason: string;
  cta_label: string;
  cta_target: { screen?: string; action_id?: string | null };
};

export type InfluencerCreator = {
  id: string;
  result_id: string;
  display_name: string;
  description?: string;
  profile_type?: string;
  platform?: string;
  public_url?: string;
  city?: string;
  area?: string;
  audience_count?: number | null;
  audience_size_band?: string;
  primary_topic?: string;
  topics?: string[];
  content_styles?: string[];
  formats?: string[];
  accepts_barter?: boolean | null;
  contactability?: string;
  verification_status?: string;
  score?: number;
  fit_reasons?: string[];
  shortlist_status?: 'suggested' | 'shortlisted' | 'rejected';
  disposition?: 'available' | 'shortlisted' | 'excluded';
  disposition_reason?: string;
  account_status?: string;
  evidence?: Array<{ type?: string; summary?: string; source_url?: string; observed_at?: string; confidence?: number }>;
};

export type InfluencerWorkspaceData = {
  feature_state?: Record<string, unknown>;
  next_action?: string;
  offer?: Record<string, unknown>;
  latest_search?: {
    id?: string;
    status?: string;
    brief?: Record<string, unknown>;
    results_count?: number;
    shortlisted_count?: number;
  } | null;
  creators?: InfluencerCreator[];
  counts?: { total?: number; returned?: number; shortlisted?: number };
  cursor?: string | null;
  preview?: { limited?: boolean; visible_limit?: number; hidden_count?: number; required_tier?: string; required_tier_name?: string };
  filters?: { platforms?: string[]; cities?: string[]; topics?: string[]; formats?: string[]; audience_size_bands?: string[] };
  access?: {
    discovery?: InfluencerAccess;
    offer?: InfluencerAccess;
    message_generation?: InfluencerAccess;
    sender_setup?: InfluencerAccess;
    send?: InfluencerAccess;
  };
};

export type InfluencerWorkspaceFilters = {
  query?: string;
  platform?: string;
  city?: string;
  district?: string;
  metro?: string;
  audience_geography?: string;
  topic?: string;
  format?: string;
  audience_size_band?: string;
  shortlisted?: boolean;
  barter?: boolean;
  contactable?: boolean;
  disposition?: 'available' | 'shortlisted' | 'excluded';
};

export const influencerWorkspaceQuery = (businessId: string, filters: InfluencerWorkspaceFilters = {}, cursor = '') => {
  const params = new URLSearchParams({ business_id: businessId, limit: '30' });
  if (filters.platform) params.set('platform', filters.platform);
  if (filters.query) params.set('query', filters.query);
  if (filters.city) params.set('city', filters.city);
  if (filters.district) params.set('district', filters.district);
  if (filters.metro) params.set('metro', filters.metro);
  if (filters.audience_geography) params.set('audience_geography', filters.audience_geography);
  if (filters.topic) params.set('topic', filters.topic);
  if (filters.format) params.set('format', filters.format);
  if (filters.audience_size_band) params.set('audience_size_band', filters.audience_size_band);
  if (filters.shortlisted) params.set('shortlisted', 'true');
  if (filters.barter) params.set('barter', 'true');
  if (filters.contactable) params.set('contactable', 'true');
  if (filters.disposition) params.set('disposition', filters.disposition);
  if (cursor) params.set('cursor', cursor);
  return params;
};

export const influencerAudienceLabel = (creator: InfluencerCreator) => {
  if (creator.audience_count) return new Intl.NumberFormat('ru-RU').format(creator.audience_count);
  const labels: Record<string, string> = {
    nano: 'до 10 тыс.',
    micro: '10–100 тыс.',
    mid: '100–500 тыс.',
    macro: 'от 500 тыс.',
  };
  return labels[creator.audience_size_band || ''] || 'не подтверждена';
};

const influencerPlatformLabels: Record<string, string> = {
  telegram: 'Telegram',
  vk: 'VK',
  instagram: 'Instagram',
  threads: 'Threads',
  tiktok: 'TikTok',
  youtube: 'YouTube',
  website: 'Сайт',
};

export const influencerPlatformLabel = (platform?: string) => influencerPlatformLabels[platform || ''] || platform || 'Площадка';
