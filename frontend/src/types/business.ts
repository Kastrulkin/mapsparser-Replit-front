import type { Dispatch, SetStateAction } from 'react';
import type { ControlScope } from '@/components/DashboardLayout';
import type { User } from '@/lib/auth_new';
import type { SubscriptionAccessPayload } from '@/lib/subscriptionAccess';

export type BusinessRecord = {
  id: string;
  name: string;
  description?: string;
  address?: string;
  city?: string;
  business_type?: string;
  site?: string;
  website?: string;
  working_hours?: string;
  owner_id?: string;
  owner_name?: string;
  owner_email?: string;
  owner_phone?: string;
  moderation_status?: string;
  entity_group?: string;
  is_lead_business?: boolean;
  network_id?: string | null;
  network_name?: string | null;
  subscription_id?: string;
  subscription_tier?: string | null;
  subscription_status?: string | null;
  subscription_ends_at?: string | null;
  trial_ends_at?: string | null;
  subscription_access?: SubscriptionAccessPayload;
  web_tracking_available?: boolean;
  creator_promotion_available?: boolean;
  ai_agents_config?: string | Record<string, AgentConfiguration>;
  ai_agent_enabled?: boolean;
  ai_agent_type?: string;
  ai_agent_restrictions?: string;
  ai_agent_id?: string;
  ai_agent_tone?: string;
  ai_agent_language?: string;
  telegram_bot_token_configured?: boolean;
  telegram_bot_token_masked?: string;
  telegram_chat_id?: string;
  waba_phone_id?: string;
  waba_access_token?: string;
  whatsapp_phone?: string;
  whatsapp_verified?: number | boolean;
};

export type AgentConfiguration = {
  enabled: boolean;
  agent_id: string | null;
  tone: string;
  language: string;
  variables: Record<string, string>;
};

export type DashboardOutletContext = {
  user: User;
  demoMode: boolean;
  currentBusinessId: string | null;
  currentBusiness: BusinessRecord | null;
  businesses: BusinessRecord[];
  controlScope: ControlScope | null;
  onControlScopeChange: (scope: ControlScope) => void;
  onBusinessChange: (businessId: string) => void;
  updateBusiness: (businessId: string, updates: Partial<BusinessRecord>) => void;
  reloadBusinesses: () => Promise<void>;
  setBusinesses: Dispatch<SetStateAction<BusinessRecord[]>>;
};
