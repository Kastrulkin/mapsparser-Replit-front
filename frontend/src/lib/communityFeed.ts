export type CommunityFeedTopic = {
  id: string;
  eyebrow?: string;
  title?: string;
  description?: string;
  message_count?: number | null;
  sources_count?: number | null;
  source_name?: string;
  source_url?: string | null;
  last_discussed_at?: string;
};

export type CommunityFeedItem = {
  id: string;
  platform: string;
  source_id?: string;
  source_name?: string;
  source_url?: string;
  title?: string;
  text: string;
  published_at?: string;
  url: string;
};

export type CommunityFeedInboundItem = {
  id: string;
  channel: string;
  classification: string;
  sender_name: string;
  text: string;
  received_at?: string;
  flow_type: 'influencer' | 'partnership';
  target?: { screen?: string; item_id?: string };
};

export type CommunityFeedTrend = {
  key: string;
  label: string;
  period_days: number;
  message_count: number;
  sample_size?: number;
  topics: Array<{
    key: string;
    title: string;
    message_count: number;
    percent: number;
  }>;
};

export type CommunityFeedPayload = {
  topics?: CommunityFeedTopic[];
  topic_trends?: CommunityFeedTrend[];
  items?: CommunityFeedItem[];
  inbound_items?: CommunityFeedInboundItem[];
  cursor?: string | null;
  as_of?: string;
  freshness?: { status?: string; updated_at?: string | null };
  available_actions?: string[];
};

export const communityFeedTimeLabel = (value?: string) => {
  if (!value) return 'время не указано';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'время не указано';
  const distance = Date.now() - parsed.getTime();
  if (distance >= 0 && distance < 60_000) return 'только что';
  if (distance >= 0 && distance < 3_600_000) return `${Math.max(1, Math.floor(distance / 60_000))} мин назад`;
  if (distance >= 0 && distance < 86_400_000) return `${Math.floor(distance / 3_600_000)} ч назад`;
  return parsed.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
};
