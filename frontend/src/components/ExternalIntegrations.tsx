import { ReactNode, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { newAuth } from "@/lib/auth_new";
import { useToast } from "@/components/ui/use-toast";
import { useLanguage } from "@/i18n/LanguageContext";
import OpenClawOutboxMetrics from "@/components/OpenClawOutboxMetrics";
import { ChannelControlCenter } from "@/components/ChannelControlCenter";
import { Building2, Database, ImageIcon, KeyRound, Send, Sparkles } from "lucide-react";

interface ExternalAccount {
  id: string;
  source: string;
  external_id?: string | null;
  display_name?: string | null;
  is_active: number;
  last_sync_at?: string | null;
  last_error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

interface GoogleLocation {
  name: string;
  title?: string | null;
  address?: string | null;
  primary_category?: string | null;
}

interface GoogleLocationsError extends Error {
  activationUrl?: string;
}

interface SocialChannelReadiness {
  platform: string;
  platform_label?: string | null;
  publish_mode?: string | null;
  ready?: boolean;
  status?: string | null;
  message_ru?: string | null;
  message_en?: string | null;
  next_action_ru?: string | null;
  next_action_en?: string | null;
  setup_summary_ru?: string | null;
  setup_summary_en?: string | null;
  setup_steps_ru?: string[];
  setup_steps_en?: string[];
  missing_fields?: string[];
  target_setup?: {
    telegram_transport?: string | null;
    required_fields?: string[];
  } | null;
  settings_path?: string | null;
}

interface SocialOpenClawReadiness {
  ready?: boolean;
  handoff_ready?: boolean;
  status?: string | null;
  provider_status?: string | null;
  reason?: string | null;
  action_ref?: string | null;
  capability?: string | null;
  stop_before_final_publish?: boolean;
  browser_final_click_allowed?: boolean;
  delivery_readiness?: {
    ready?: boolean;
    status?: string | null;
    callback_configured?: boolean;
  } | null;
  diagnostics_ru?: string[];
  diagnostics_en?: string[];
}

interface SocialTelegramTransport {
  schema?: string;
  ready?: boolean;
  status?: string | null;
  proxy_configured?: boolean;
  proxy_mode?: string | null;
  bot_token_present?: boolean;
  read_only_probe_enabled?: boolean;
  read_only_probe_performed?: boolean;
  summary_ru?: string | null;
  summary_en?: string | null;
  next_action_ru?: string | null;
  next_action_en?: string | null;
}

interface ExternalIntegrationsProps {
  currentBusinessId: string | null;
  readinessRefreshKey?: number;
  focusedPlatform?: string | null;
}

type AccessCardTone = "ready" | "attention" | "neutral";

type AccessCardProps = {
  title: string;
  description: string;
  status: string;
  detail?: string;
  actionLabel: string;
  icon: ReactNode;
  tone: AccessCardTone;
  focused?: boolean;
  disabled?: boolean;
  onAction: () => void;
};

const accessToneClass = (tone: AccessCardTone, focused?: boolean) => {
  if (focused) return "border-sky-300 bg-sky-50 ring-2 ring-sky-100";
  if (tone === "ready") return "border-emerald-200 bg-emerald-50/70";
  if (tone === "attention") return "border-amber-200 bg-amber-50/70";
  return "border-slate-200 bg-white";
};

const accessBadgeClass = (tone: AccessCardTone) => {
  if (tone === "ready") return "bg-emerald-100 text-emerald-800";
  if (tone === "attention") return "bg-amber-100 text-amber-800";
  return "bg-slate-100 text-slate-700";
};

const AccessCard = ({
  title,
  description,
  status,
  detail,
  actionLabel,
  icon,
  tone,
  focused = false,
  disabled = false,
  onAction,
}: AccessCardProps) => (
  <div className={["flex min-h-[190px] flex-col rounded-2xl border p-4 shadow-sm", accessToneClass(tone, focused)].join(" ")}>
    <div className="flex items-start justify-between gap-3">
      <div className="flex min-w-0 items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-slate-800 shadow-sm ring-1 ring-black/5">
          {icon}
        </div>
        <div className="min-w-0">
          <h3 className="text-base font-semibold leading-6 text-slate-950 [text-wrap:balance]">{title}</h3>
          <p className="mt-1 text-sm leading-6 text-slate-600 [text-wrap:pretty]">{description}</p>
        </div>
      </div>
      <span className={["shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold", accessBadgeClass(tone)].join(" ")}>
        {status}
      </span>
    </div>
    {detail ? (
      <p className="mt-3 text-xs leading-5 text-slate-500">{detail}</p>
    ) : null}
    <div className="mt-auto pt-4">
      <Button
        type="button"
        variant={tone === "ready" ? "outline" : "default"}
        onClick={onAction}
        disabled={disabled}
        className="min-h-10 w-full justify-center transition-transform active:scale-[0.96] sm:w-auto"
      >
        {actionLabel}
      </Button>
    </div>
  </div>
);

export const ExternalIntegrations: React.FC<ExternalIntegrationsProps> = ({
  currentBusinessId,
  readinessRefreshKey = 0,
  focusedPlatform = null,
}) => {
  const [accounts, setAccounts] = useState<ExternalAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [matonApiKey, setMatonApiKey] = useState('');
  const [googleLocations, setGoogleLocations] = useState<GoogleLocation[]>([]);
  const [selectedGoogleLocation, setSelectedGoogleLocation] = useState('');
  const [googleLocationsMessage, setGoogleLocationsMessage] = useState<string | null>(null);
  const [googleLocationsActionUrl, setGoogleLocationsActionUrl] = useState<string | null>(null);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [vkAccessToken, setVkAccessToken] = useState('');
  const [vkOwnerId, setVkOwnerId] = useState('');
  const [vkScope, setVkScope] = useState('wall');
  const [vkBusy, setVkBusy] = useState(false);
  const [photoIntelligenceEnabled, setPhotoIntelligenceEnabled] = useState(false);
  const [photoIntelligenceLoading, setPhotoIntelligenceLoading] = useState(false);
  const [photoIntelligenceSaving, setPhotoIntelligenceSaving] = useState(false);
  const [socialReadiness, setSocialReadiness] = useState<SocialChannelReadiness[]>([]);
  const [socialReadinessSummary, setSocialReadinessSummary] = useState<Record<string, number>>({});
  const [socialOpenClawReadiness, setSocialOpenClawReadiness] = useState<SocialOpenClawReadiness | null>(null);
  const [socialTelegramTransport, setSocialTelegramTransport] = useState<SocialTelegramTransport | null>(null);
  const [socialReadinessLoading, setSocialReadinessLoading] = useState(false);
  const [expandedDetails, setExpandedDetails] = useState<string | null>(null);
  const socialReadinessRef = useRef<HTMLDivElement | null>(null);
  const googleCardRef = useRef<HTMLDivElement | null>(null);
  const vkCardRef = useRef<HTMLDivElement | null>(null);
  const { toast } = useToast();
  const { t, language } = useLanguage();
  const matonAccount = accounts.find((acc) => acc.source === 'maton');
  const googleAccount = accounts.find((acc) => acc.source === 'google_business');
  const vkAccount = accounts.find((acc) => acc.source === 'vk' || acc.source === 'vk_group' || acc.source === 'vk_business');
  const normalizedFocusedPlatform = String(focusedPlatform || '').trim();
  const isGoogleSheetsFocused = normalizedFocusedPlatform === 'google_sheets';
  const isGoogleFocused = normalizedFocusedPlatform === 'google_business';
  const isVkFocused = normalizedFocusedPlatform === 'vk';
  const isMetaFocused = normalizedFocusedPlatform === 'meta' || normalizedFocusedPlatform === 'instagram' || normalizedFocusedPlatform === 'facebook';
  const isCrmFocused = normalizedFocusedPlatform === 'crm' || normalizedFocusedPlatform === 'maton';
  const googleSheetsReady = Boolean(googleAccount);
  const googleBusinessReady = Boolean(googleAccount?.external_id);
  const apiReadyCount = Number(socialReadinessSummary.api_ready || 0);
  const channelAttentionCount = Number(socialReadinessSummary.api_needs_attention || 0);
  const manualChannelCount = Number(socialReadinessSummary.controlled_or_manual || 0);
  const channelStatus = socialReadinessLoading
    ? 'Проверяем'
    : apiReadyCount > 0
      ? `${apiReadyCount} готовы`
      : channelAttentionCount > 0 || manualChannelCount > 0
        ? 'Нужно внимание'
        : 'Проверить';
  const crmKeysReady = Boolean(matonAccount);
  const focusedCardClass = 'border-sky-300 bg-sky-50/80 ring-2 ring-sky-100';
  const openClawOperational = Boolean(
    socialOpenClawReadiness?.ready
    && (
      typeof socialOpenClawReadiness.handoff_ready === 'boolean'
        ? socialOpenClawReadiness.handoff_ready
        : (
          socialOpenClawReadiness.delivery_readiness
            ? Boolean(socialOpenClawReadiness.delivery_readiness.ready)
            : true
        )
    ),
  );
  const openClawStatusLabel = openClawOperational
    ? 'OpenClaw готов'
    : socialOpenClawReadiness?.ready
      ? 'Нужна настройка handoff'
      : 'Ручной режим';
  const openClawStatusDetail = openClawOperational
    ? 'Яндекс/2ГИС можно вести как контролируемое размещение: LocalOS готовит задачу, предпросмотр и останавливается перед финальной публикацией.'
    : socialOpenClawReadiness?.ready
      ? 'Browser-use найден, но delivery/handoff ещё не подтверждён. Для карт используйте ручной режим или завершите настройку OpenClaw.'
      : 'Browser-use не подтверждён. LocalOS подготовит текст, чеклист и ручную отметку публикации, без скрытой автопубликации.';
  const openClawDiagnostics = language === 'ru'
    ? socialOpenClawReadiness?.diagnostics_ru
    : socialOpenClawReadiness?.diagnostics_en;
  const telegramReadiness = socialReadiness.find((channel) => channel.platform === 'telegram') || null;
  const telegramTargetSetup = telegramReadiness?.target_setup;
  const telegramRequiredFields = Array.isArray(telegramTargetSetup?.required_fields)
    ? telegramTargetSetup.required_fields
    : telegramReadiness?.missing_fields;
  const telegramUsesGlobalBot = telegramTargetSetup?.telegram_transport === 'global_owner_bot'
    || (
      Array.isArray(telegramRequiredFields)
      && telegramRequiredFields.length === 1
      && telegramRequiredFields[0] === 'telegram_chat_id'
    );
  const telegramChecklistHint = telegramUsesGlobalBot
    ? 'глобальный бот LocalOS + telegram_chat_id цели'
    : 'telegram_bot_token бизнеса или глобальный бот + telegram_chat_id';
  const telegramTransportSummary = language === 'ru'
    ? socialTelegramTransport?.summary_ru
    : socialTelegramTransport?.summary_en;
  const telegramTransportNextAction = language === 'ru'
    ? socialTelegramTransport?.next_action_ru
    : socialTelegramTransport?.next_action_en;

  useEffect(() => {
    let target: HTMLDivElement | null = null;
    if (isVkFocused) target = vkCardRef.current;
    else if (isGoogleFocused) target = googleCardRef.current;
    else if (isMetaFocused) target = socialReadinessRef.current;

    if (!target) return;
    const timeoutId = window.setTimeout(() => {
      target?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 140);
    return () => window.clearTimeout(timeoutId);
  }, [isGoogleFocused, isMetaFocused, isVkFocused, socialReadinessLoading]);

  useEffect(() => {
    if (isGoogleFocused || isGoogleSheetsFocused) {
      setExpandedDetails('google');
      return;
    }
    if (isVkFocused || isMetaFocused) {
      setExpandedDetails('channels');
      return;
    }
    if (isCrmFocused) {
      setExpandedDetails('crm');
    }
  }, [isCrmFocused, isGoogleFocused, isGoogleSheetsFocused, isMetaFocused, isVkFocused]);

  const loadAccounts = async () => {
    if (!currentBusinessId) return;
    setLoading(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;

      const res = await fetch(`/api/business/${currentBusinessId}/external-accounts`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.status === 404) {
        setAccounts([]);
        return;
      }

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || t.dashboard.settings.external.error);
      }
      setAccounts(data.accounts || []);
    } catch (e: any) {
      toast({
        title: t.error,
        description: e.message || t.dashboard.settings.external.error,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadSocialReadiness = async () => {
    if (!currentBusinessId) {
      setSocialReadiness([]);
      setSocialReadinessSummary({});
      setSocialOpenClawReadiness(null);
      setSocialTelegramTransport(null);
      return;
    }
    setSocialReadinessLoading(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;

      const res = await fetch(`/api/business/${currentBusinessId}/social-posts/channel-readiness`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Не удалось получить готовность каналов публикации');
      }
      setSocialReadiness(Array.isArray(data.channel_readiness) ? data.channel_readiness : []);
      setSocialReadinessSummary(data.summary || {});
      setSocialOpenClawReadiness(
        data.openclaw_browser_readiness && typeof data.openclaw_browser_readiness === 'object'
          ? data.openclaw_browser_readiness
          : null,
      );
      try {
        const runtimeRes = await fetch('/api/social-posts/runtime-status', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        const runtimeData = await runtimeRes.json();
        setSocialTelegramTransport(
          runtimeRes.ok && runtimeData.success && runtimeData.telegram_transport && typeof runtimeData.telegram_transport === 'object'
            ? runtimeData.telegram_transport
            : null,
        );
      } catch {
        setSocialTelegramTransport(null);
      }
    } catch (e: any) {
      setSocialReadiness([]);
      setSocialReadinessSummary({});
      setSocialOpenClawReadiness(null);
      setSocialTelegramTransport(null);
      toast({
        title: t.error,
        description: e.message || 'Не удалось получить готовность каналов публикации',
        variant: "destructive",
      });
    } finally {
      setSocialReadinessLoading(false);
    }
  };

  const handleGoogleConnect = async () => {
    if (!currentBusinessId) {
      toast({
        title: t.error,
        description: t.dashboard.settings.external.selectBusiness,
        variant: "destructive",
      });
      return;
    }
    setGoogleBusy(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const oauthParams = new URLSearchParams({ business_id: currentBusinessId });
      const returnTo = `${window.location.pathname}${window.location.search || ''}`;
      if (returnTo.startsWith('/dashboard/')) {
        oauthParams.set('return_to', returnTo);
      }
      const res = await fetch(`/api/google/oauth/authorize?${oauthParams.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok || !data.success || !data.auth_url) {
        throw new Error(data.error || "Не удалось начать подключение Google");
      }
      window.location.href = data.auth_url;
    } catch (e: any) {
      toast({
        title: t.error,
        description: e.message || "Ошибка подключения Google",
        variant: "destructive",
      });
      setGoogleBusy(false);
    }
  };

  const handleLoadGoogleLocations = async () => {
    if (!currentBusinessId) return;
    setGoogleBusy(true);
    setGoogleLocationsMessage(null);
    setGoogleLocationsActionUrl(null);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const res = await fetch(`/api/business/${currentBusinessId}/google/locations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        const error = new Error(data.error || "Не удалось получить карточки Google") as GoogleLocationsError;
        if (data.activation_url) {
          error.activationUrl = String(data.activation_url);
        }
        throw error;
      }
      const locations = data.locations || [];
      setGoogleLocations(locations);
      if (locations.length === 1) setSelectedGoogleLocation(locations[0].name);
      if (!locations.length) {
        setGoogleLocationsMessage(
          'Google подключён, но Business Profile API не вернул карточки. Проверьте, что этот Google аккаунт видит компании в business.google.com и имеет роль владельца или менеджера.'
        );
      }
      toast({
        title: t.success,
        description: locations.length ? `Найдено карточек: ${locations.length}` : "Google подключён, но карточки не вернулись",
      });
    } catch (e: any) {
      setGoogleLocations([]);
      setGoogleLocationsMessage(e.message || 'Не удалось получить карточки Google Business Profile');
      setGoogleLocationsActionUrl(e.activationUrl || null);
      toast({
        title: t.error,
        description: e.message || "Ошибка загрузки карточек Google",
        variant: "destructive",
      });
    } finally {
      setGoogleBusy(false);
    }
  };

  const handleBindGoogleLocation = async () => {
    if (!currentBusinessId || !selectedGoogleLocation) return;
    const location = googleLocations.find((item) => item.name === selectedGoogleLocation);
    setGoogleBusy(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const res = await fetch(`/api/business/${currentBusinessId}/google/bind-location`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          account_id: googleAccount?.id,
          location_name: selectedGoogleLocation,
          display_name: location?.title || "Google Business Profile",
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Не удалось привязать карточку Google");
      }
      toast({ title: t.success, description: "Карточка Google привязана к бизнесу" });
      await loadAccounts();
      await loadSocialReadiness();
    } catch (e: any) {
      toast({
        title: t.error,
        description: e.message || "Ошибка привязки карточки Google",
        variant: "destructive",
      });
    } finally {
      setGoogleBusy(false);
    }
  };

  const loadPhotoIntelligenceSettings = async () => {
    if (!currentBusinessId) {
      setPhotoIntelligenceEnabled(false);
      return;
    }
    setPhotoIntelligenceLoading(true);
    try {
      const data = await newAuth.makeRequest(`/media-intelligence/settings?business_id=${encodeURIComponent(currentBusinessId)}`, {
        method: "GET",
      });
      setPhotoIntelligenceEnabled(Boolean(data?.photo_intelligence?.enabled));
    } catch {
      setPhotoIntelligenceEnabled(false);
    } finally {
      setPhotoIntelligenceLoading(false);
    }
  };

  const handleTogglePhotoIntelligence = async (checked: boolean) => {
    if (!currentBusinessId) {
      toast({
        title: t.error,
        description: t.dashboard.settings.external.selectBusiness,
        variant: "destructive",
      });
      return;
    }
    const previousValue = photoIntelligenceEnabled;
    setPhotoIntelligenceEnabled(checked);
    setPhotoIntelligenceSaving(true);
    try {
      await newAuth.makeRequest('/media-intelligence/settings', {
        method: 'POST',
        body: JSON.stringify({
          business_id: currentBusinessId,
          vision_enabled: checked,
        }),
      });
      toast({
        title: t.success,
        description: checked ? 'Обработка фото включена' : 'Обработка фото выключена',
      });
    } catch (e: any) {
      setPhotoIntelligenceEnabled(previousValue);
      toast({
        title: t.error,
        description: e.message || 'Не удалось обновить обработку фото',
        variant: "destructive",
      });
    } finally {
      setPhotoIntelligenceSaving(false);
    }
  };

  const handleSyncGoogle = async () => {
    if (!currentBusinessId) return;
    setGoogleBusy(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const res = await fetch(`/api/business/${currentBusinessId}/google/sync`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ account_id: googleAccount?.id }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Не удалось синхронизировать Google");
      }
      toast({ title: t.success, description: "Отзывы и статистика Google синхронизированы" });
      await loadAccounts();
      await loadSocialReadiness();
    } catch (e: any) {
      toast({
        title: t.error,
        description: e.message || "Ошибка синхронизации Google",
        variant: "destructive",
      });
    } finally {
      setGoogleBusy(false);
    }
  };

  useEffect(() => {
    loadAccounts();
    loadSocialReadiness();
    loadPhotoIntelligenceSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentBusinessId, readinessRefreshKey]);


  const handleDisconnect = async (accountId: string) => {
    if (!accountId) return;
    setSaving(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;

      const res = await fetch(`/api/external-accounts/${accountId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || t.error);
      }
      toast({
        title: t.success,
        description: t.dashboard.settings.external.successDisconnect,
      });
      await loadAccounts();
      await loadSocialReadiness();
    } catch (e: any) {
      toast({
        title: t.error,
        description: e.message || t.error,
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveMaton = async () => {
    if (!currentBusinessId) {
      toast({
        title: t.error,
        description: t.dashboard.settings.external.selectBusiness,
        variant: "destructive",
      });
      return;
    }
    if (!matonApiKey.trim()) {
      toast({
        title: t.error,
        description: "Введите API-ключ Maton.ai",
        variant: "destructive",
      });
      return;
    }

    setSaving(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;

      const res = await fetch(`/api/business/${currentBusinessId}/external-accounts`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          source: "maton",
          external_id: "maton",
          display_name: "Maton.ai",
          auth_data: { api_key: matonApiKey.trim() },
          is_active: true,
        }),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Не удалось сохранить ключ Maton.ai");
      }

      setMatonApiKey('');
      toast({
        title: t.success,
        description: "Ключ Maton.ai сохранён",
      });
      await loadAccounts();
      await loadSocialReadiness();
    } catch (e: any) {
      toast({
        title: t.error,
        description: e.message || "Ошибка сохранения ключа Maton.ai",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveVk = async () => {
    if (!currentBusinessId) {
      toast({
        title: t.error,
        description: t.dashboard.settings.external.selectBusiness,
        variant: "destructive",
      });
      return;
    }
    const tokenValue = vkAccessToken.trim();
    const ownerValue = vkOwnerId.trim();
    if (!tokenValue || !ownerValue) {
      toast({
        title: t.error,
        description: "Для VK нужны access_token и group_id/owner_id.",
        variant: "destructive",
      });
      return;
    }

    setVkBusy(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;
      const res = await fetch(`/api/business/${currentBusinessId}/external-accounts`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          source: "vk",
          external_id: ownerValue,
          display_name: "VK публикации",
          auth_data: {
            access_token: tokenValue,
            owner_id: ownerValue,
            group_id: ownerValue.replace(/^-/, ''),
            scope: vkScope.trim() || "wall",
          },
          is_active: true,
        }),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Не удалось сохранить VK подключение");
      }

      setVkAccessToken('');
      toast({
        title: t.success,
        description: "VK подключение сохранено. Готовность каналов обновлена.",
      });
      await loadAccounts();
      await loadSocialReadiness();
    } catch (e: any) {
      toast({
        title: t.error,
        description: e.message || "Ошибка сохранения VK подключения",
        variant: "destructive",
      });
    } finally {
      setVkBusy(false);
    }
  };

  const openDetails = (section: string) => {
    setExpandedDetails(section);
  };

  return (
    <Card className="overflow-hidden rounded-3xl border-slate-200/80 bg-white shadow-sm">
      <CardHeader className="pb-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle className="text-slate-950">Подключения</CardTitle>
            <CardDescription className="mt-2 leading-6">Подключите доступы, которые нужны агентам и публикациям.</CardDescription>
          </div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 ring-1 ring-slate-200">
            {accounts.length} подключено
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <div
          data-testid="settings-integrations-scenario"
          className="rounded-3xl bg-slate-50 px-4 py-4 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]"
        >
          <div className="max-w-3xl text-sm leading-6 text-slate-700">
            Сначала подключите Google-доступ для агентов. Если агент читает таблицу, ему нужен именно доступ к Google Таблицам, а не выбор карточки Google Business.
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <AccessCard
            title="Google Таблицы"
            description="Этот доступ нужен агентам для чтения Google Таблиц. Он не публикует ничего наружу."
            status={googleSheetsReady ? 'Доступ есть' : 'Нужно подключить'}
            detail="Google Документы: позже, когда появится отдельный Drive/Docs scope."
            actionLabel={googleSheetsReady ? 'Переподключить' : 'Подключить Google-доступ'}
            icon={<Database className="h-5 w-5" />}
            tone={googleSheetsReady ? 'ready' : 'attention'}
            focused={isGoogleSheetsFocused}
            disabled={googleBusy || !currentBusinessId}
            onAction={handleGoogleConnect}
          />
          <AccessCard
            title="Google Business"
            description="Карточка компании, отзывы и посты Google. Это отдельный шаг после Google-доступа."
            status={googleBusinessReady ? 'Карточка выбрана' : googleSheetsReady ? 'Выберите карточку' : 'Нужно подключить'}
            detail={googleSheetsReady ? 'Google-доступ уже есть: можно выбрать карточку или синхронизировать данные.' : 'Сначала войдите в Google аккаунт владельца или менеджера.'}
            actionLabel={!googleSheetsReady ? 'Подключить Google' : googleBusinessReady ? 'Синхронизировать' : 'Выбрать карточку'}
            icon={<Building2 className="h-5 w-5" />}
            tone={googleBusinessReady ? 'ready' : 'attention'}
            focused={isGoogleFocused}
            disabled={googleBusy || !currentBusinessId}
            onAction={() => {
              if (!googleSheetsReady) {
                handleGoogleConnect();
                return;
              }
              if (googleBusinessReady) {
                handleSyncGoogle();
                return;
              }
              openDetails('google');
              handleLoadGoogleLocations();
            }}
          />
          <AccessCard
            title="Каналы публикаций"
            description="Telegram, VK и Meta для согласованных постов. Детали и ключи открываются только когда нужны."
            status={channelStatus}
            detail="Публикации наружу остаются через предпросмотр и подтверждение человека."
            actionLabel="Открыть каналы"
            icon={<Send className="h-5 w-5" />}
            tone={apiReadyCount > 0 ? 'ready' : 'neutral'}
            focused={isVkFocused || isMetaFocused}
            onAction={() => openDetails('channels')}
          />
          <AccessCard
            title="CRM и ключи"
            description="YCLIENTS, Altegio и Maton для записей, финансов и внешних сервисов."
            status={crmKeysReady ? 'Ключ есть' : 'Настроить'}
            detail="Формы и технические ключи спрятаны ниже, чтобы не мешать основному подключению."
            actionLabel="Открыть CRM и ключи"
            icon={<KeyRound className="h-5 w-5" />}
            tone={crmKeysReady ? 'ready' : 'neutral'}
            focused={isCrmFocused}
            onAction={() => openDetails('crm')}
          />
        </div>

        <details
          open={expandedDetails !== null}
          onToggle={(event) => {
            if (!event.currentTarget.open) {
              setExpandedDetails(null);
            }
          }}
          className="rounded-3xl border border-slate-200 bg-white px-4 py-4 shadow-sm"
        >
          <summary className="cursor-pointer select-none text-sm font-semibold text-slate-950">
            {expandedDetails === 'google'
              ? 'Google: таблицы и карточка'
              : expandedDetails === 'channels'
                ? 'Каналы публикаций'
                : expandedDetails === 'crm'
                  ? 'CRM и ключи'
                  : 'Дополнительные параметры подключения'}
          </summary>
          <div className="mt-4 space-y-6">
        <div className="rounded-3xl border border-slate-200 bg-white p-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h3 className="text-base font-semibold text-slate-950">Публикации из контент-плана</h3>
              <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
                Перед постановкой постов в расписание проверьте, какие каналы готовы к API-публикации, а где нужен ручной или контролируемый шаг. Внешняя публикация всё равно пойдёт только после предпросмотра и вашего подтверждения.
              </p>
            </div>
            <div className="grid min-w-full gap-2 text-xs sm:grid-cols-3 lg:min-w-[360px]">
              <div className="rounded-2xl bg-emerald-50 px-3 py-2 text-emerald-800">
                <div className="font-semibold text-emerald-950">{Number(socialReadinessSummary.api_ready || 0)}</div>
                <div>API готовы</div>
              </div>
              <div className="rounded-2xl bg-amber-50 px-3 py-2 text-amber-800">
                <div className="font-semibold text-amber-950">{Number(socialReadinessSummary.api_needs_attention || 0)}</div>
                <div>нужны ключи/права</div>
              </div>
              <div className="rounded-2xl bg-sky-50 px-3 py-2 text-sky-800">
                <div className="font-semibold text-sky-950">{Number(socialReadinessSummary.controlled_or_manual || 0)}</div>
                <div>контроль/вручную</div>
              </div>
            </div>
          </div>

          {socialReadinessLoading ? (
            <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
              Проверяем готовность каналов...
            </div>
          ) : socialReadiness.length ? (
            <>
              <div
                ref={socialReadinessRef}
                data-testid="social-settings-channel-readiness"
                className={[
                  'mt-4 rounded-2xl border px-4 py-4',
                  isMetaFocused ? focusedCardClass : 'border-slate-200 bg-slate-50',
                ].join(' ')}
              >
                <div className="text-sm font-semibold text-slate-950">Чеклист публикаций</div>
                <div className="mt-1 text-xs leading-5 text-slate-600">
                  Сначала подключите API-каналы для автопубликации по расписанию. Яндекс/2ГИС остаются ручными или контролируемыми: LocalOS готовит текст и задачу, финальный клик делает человек.
                </div>
                {isMetaFocused ? (
                  <div className="mt-3 rounded-xl border border-sky-200 bg-white px-3 py-2 text-xs leading-5 text-sky-900">
                    Вы пришли из контент-плана по Instagram/Facebook. Meta publish включается только после Page/IG business binding и нужных permissions; до этого LocalOS покажет ручной режим, а не fake success.
                  </div>
                ) : null}
                <div className="mt-3 grid gap-2 text-xs md:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-xl bg-white px-3 py-2 text-slate-700 ring-1 ring-slate-200">
                    <span className="font-semibold text-slate-950">Telegram:</span> {telegramChecklistHint}
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2 text-slate-700 ring-1 ring-slate-200">
                    <span className="font-semibold text-slate-950">VK:</span> access_token + group_id/owner_id + wall.post
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2 text-slate-700 ring-1 ring-slate-200">
                    <span className="font-semibold text-slate-950">Google:</span> Business Profile + локация
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2 text-slate-700 ring-1 ring-slate-200">
                    <span className="font-semibold text-slate-950">Meta:</span> Page/IG business + права
                  </div>
                </div>
                {socialTelegramTransport ? (
                  <div
                    data-testid="social-settings-telegram-transport"
                    data-schema={String(socialTelegramTransport.schema || 'localos_telegram_transport_status_v1')}
                    className={[
                      'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
                      socialTelegramTransport.ready
                        ? 'border-emerald-100 bg-emerald-50 text-emerald-900'
                        : 'border-amber-100 bg-amber-50 text-amber-900',
                    ].join(' ')}
                  >
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="font-semibold text-slate-950">Telegram transport</div>
                        <div className="mt-1">
                          {telegramTransportSummary || 'Read-only проверка Telegram transport не дала результата.'}
                        </div>
                      </div>
                      <span
                        className={[
                          'inline-flex w-max rounded-full px-2.5 py-1 text-[11px] font-semibold',
                          socialTelegramTransport.ready
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-amber-100 text-amber-800',
                        ].join(' ')}
                      >
                        {socialTelegramTransport.ready ? 'готов к API-proof' : 'проверить до API-proof'}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-[11px] font-medium text-slate-600">
                      <span>{socialTelegramTransport.proxy_configured ? 'proxy задан' : 'proxy не задан'}</span>
                      <span>{socialTelegramTransport.bot_token_present ? 'bot token есть' : 'bot token не найден'}</span>
                      <span>{socialTelegramTransport.read_only_probe_performed ? 'read-only probe выполнен' : 'probe не выполнялся'}</span>
                    </div>
                    {telegramTransportNextAction ? (
                      <div className="mt-2 font-medium text-slate-700">
                        {telegramTransportNextAction}
                      </div>
                    ) : null}
                  </div>
                ) : null}
                <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-sky-100 bg-white px-3 py-2 text-xs leading-5 text-sky-900">
                  <span className="font-semibold text-sky-950">После подключения:</span>
                  <span>Вернуться в контент-план, нажмите “Проверить готовность”, затем пройдите предпросмотр → подтверждение → расписание.</span>
                  <Button type="button" size="sm" variant="outline" className="h-7 bg-white px-2 text-[11px]" asChild>
                    <Link to="/dashboard/card?tab=news&mode=plan">Открыть контент-план</Link>
                  </Button>
                </div>
                <div
                  className={[
                    'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
                    openClawOperational
                      ? 'border-emerald-100 bg-emerald-50 text-emerald-900'
                      : socialOpenClawReadiness?.ready
                        ? 'border-amber-100 bg-amber-50 text-amber-900'
                        : 'border-slate-200 bg-white text-slate-700',
                  ].join(' ')}
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="font-semibold text-slate-950">Яндекс/2ГИС через browser-use</div>
                      <div className="mt-1">{openClawStatusDetail}</div>
                    </div>
                    <span
                      className={[
                        'inline-flex w-max rounded-full px-2.5 py-1 text-[11px] font-semibold',
                        openClawOperational
                          ? 'bg-emerald-100 text-emerald-800'
                          : socialOpenClawReadiness?.ready
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-slate-100 text-slate-700',
                      ].join(' ')}
                    >
                      {openClawStatusLabel}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-[11px] font-medium text-slate-600">
                    <span>Финальный клик: человек</span>
                    <span>Предпросмотр: обязателен</span>
                    <span>Автопубликация карт: нет</span>
                    {socialOpenClawReadiness?.action_ref ? <span>action: {socialOpenClawReadiness.action_ref}</span> : null}
                  </div>
                  {Array.isArray(openClawDiagnostics) && openClawDiagnostics.length > 0 ? (
                    <div className="mt-2 text-[11px] text-slate-600">
                      {openClawDiagnostics.slice(0, 2).join(' · ')}
                    </div>
                  ) : null}
                </div>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {socialReadiness.map((channel) => {
                  const ready = Boolean(channel.ready);
                  const isApi = channel.publish_mode === 'api';
                  const message = language === 'ru' ? channel.message_ru : channel.message_en;
                  const nextAction = language === 'ru' ? channel.next_action_ru : channel.next_action_en;
                  const setupSummary = language === 'ru' ? channel.setup_summary_ru : channel.setup_summary_en;
                  const setupSteps = language === 'ru' ? channel.setup_steps_ru : channel.setup_steps_en;
                  return (
                    <div
                      key={channel.platform}
                      className={[
                        'rounded-2xl border px-4 py-3',
                        ready
                          ? 'border-emerald-200 bg-emerald-50/80'
                          : isApi
                            ? 'border-amber-200 bg-amber-50/80'
                            : 'border-sky-200 bg-sky-50/80',
                      ].join(' ')}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-sm font-semibold text-slate-950">
                            {channel.platform_label || channel.platform}
                          </div>
                          <div className="mt-1 text-xs leading-5 text-slate-600">
                            {message || 'Проверьте настройки канала.'}
                          </div>
                        </div>
                        <span
                          className={[
                            'shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold',
                            ready
                              ? 'bg-emerald-100 text-emerald-800'
                              : isApi
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-sky-100 text-sky-800',
                          ].join(' ')}
                        >
                          {ready ? 'готов' : isApi ? 'настроить' : 'под контролем'}
                        </span>
                      </div>
                      <div className="mt-3 text-[11px] font-medium uppercase tracking-wide text-slate-500">
                        {isApi ? 'API-публикация после подтверждения' : 'Ручное или контролируемое размещение'}
                      </div>
                      {setupSummary ? (
                        <div className="mt-2 rounded-xl bg-white/70 px-3 py-2 text-xs leading-5 text-slate-700 ring-1 ring-slate-200">
                          <span className="font-semibold text-slate-950">Сейчас: </span>
                          {setupSummary}
                        </div>
                      ) : null}
                      {nextAction ? (
                        <div className="mt-2 rounded-xl bg-white/70 px-3 py-2 text-xs leading-5 text-slate-700 ring-1 ring-slate-200">
                          <span className="font-semibold text-slate-950">Что сделать: </span>
                          {nextAction}
                        </div>
                      ) : null}
                      {Array.isArray(setupSteps) && setupSteps.length > 0 ? (
                        <div className="mt-2 rounded-xl bg-white/70 px-3 py-2 text-xs leading-5 text-slate-700 ring-1 ring-slate-200">
                          <div className="font-semibold text-slate-950">Шаги подключения</div>
                          <ul className="mt-1 space-y-1">
                            {setupSteps.slice(0, 3).map((step) => (
                              <li key={`${channel.platform}-setup-${step}`} className="flex gap-2">
                                <span className="text-slate-400">-</span>
                                <span>{step}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <div className="mt-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
              Выберите бизнес, чтобы увидеть готовность каналов публикации.
            </div>
          )}
        </div>

        {/* Google Business Profile */}
        <div
          ref={googleCardRef}
          data-testid="social-settings-google-card"
          className={[
            'flex flex-col gap-4 rounded-3xl border p-5',
            isGoogleFocused ? focusedCardClass : 'border-slate-200 bg-slate-50/70',
          ].join(' ')}
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 className="text-base font-semibold text-slate-950">Google Business Profile</h3>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
                Подключите именно Google Business Profile: карточки компаний, отзывы и новости. Это не подключение Google Таблиц или Google Документов.
              </p>
              {isGoogleFocused ? (
                <p className="mt-2 rounded-xl border border-sky-200 bg-white px-3 py-2 text-xs leading-5 text-sky-900">
                  Вы пришли из контент-плана: этот канал нужен для API-публикации Google после предпросмотра, подтверждения и расписания.
                </p>
              ) : null}
            </div>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${googleAccount ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200' : 'bg-slate-100 text-slate-600 ring-1 ring-slate-200'}`}>
              {googleAccount ? (googleAccount.external_id ? 'Карточка выбрана' : 'Требуется выбор карточки') : 'Не подключён'}
            </span>
          </div>

          {!googleAccount ? (
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-slate-600">Войдите в Google аккаунт владельца или менеджера карточки.</p>
              <Button
                onClick={handleGoogleConnect}
                disabled={googleBusy || !currentBusinessId}
                className="bg-slate-900 text-white hover:bg-slate-800 sm:min-w-[190px]"
              >
                {googleBusy ? t.dashboard.subscription.processing : "Подключить Google"}
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
                <div>
                  <label className="text-xs font-semibold uppercase text-slate-500">Карточка Google</label>
                  {googleAccount.external_id ? (
                    <div className="mt-1 rounded-xl border border-emerald-100 bg-white px-3 py-2 text-sm text-slate-800">
                      <div className="font-medium">{googleAccount.display_name || "Google Business Profile"}</div>
                      <div className="mt-0.5 break-all text-xs text-slate-500">{googleAccount.external_id}</div>
                    </div>
                  ) : (
                    <>
                      <select
                        value={selectedGoogleLocation}
                        onChange={(event) => setSelectedGoogleLocation(event.target.value)}
                        className="mt-1 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900"
                        disabled={googleBusy || googleLocations.length === 0}
                      >
                        <option value="">Выберите карточку компании</option>
                        {googleLocations.map((location) => (
                          <option key={location.name} value={location.name}>
                            {[location.title, location.address || location.primary_category].filter(Boolean).join(' · ')}
                          </option>
                        ))}
                      </select>
                      {googleLocationsMessage ? (
                        <div className="mt-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
                          <div>{googleLocationsMessage}</div>
                          {googleLocationsActionUrl ? (
                            <a
                              href={googleLocationsActionUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="mt-2 inline-flex min-h-10 items-center rounded-lg bg-white px-3 py-2 font-semibold text-amber-950 shadow-sm ring-1 ring-amber-200 transition-colors hover:bg-amber-100"
                            >
                              Включить API в Google Cloud
                            </a>
                          ) : null}
                        </div>
                      ) : null}
                    </>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {!googleAccount.external_id && (
                    <>
                      <Button type="button" variant="outline" onClick={handleLoadGoogleLocations} disabled={googleBusy}>
                        Найти карточки
                      </Button>
                      <Button type="button" onClick={handleBindGoogleLocation} disabled={googleBusy || !selectedGoogleLocation}>
                        Выбрать
                      </Button>
                    </>
                  )}
                  {googleAccount.external_id && (
                    <Button type="button" variant="outline" onClick={handleSyncGoogle} disabled={googleBusy}>
                      {googleBusy ? t.dashboard.subscription.processing : "Синхронизировать"}
                    </Button>
                  )}
                </div>
              </div>
              <p className="text-xs leading-5 text-slate-500">
                Google API работает в тестовом режиме до согласования. Для внешних действий LocalOS будет показывать черновик и ждать вашего подтверждения.
              </p>
            </div>
          )}
        </div>

        {/* Photo intelligence */}
        <div className="flex flex-col gap-4 rounded-3xl border border-slate-200 bg-slate-50/70 p-5">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="flex items-start gap-4">
              <div className="rounded-2xl bg-white p-3 text-slate-900 shadow-sm ring-1 ring-slate-200">
                <ImageIcon className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-slate-950">Обработка фото</h3>
                <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
                  LocalOS сможет выбирать лучшие фото для публикаций, подсказывать чего не хватает и готовить визуал под каналы.
                </p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-3 md:justify-end">
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${photoIntelligenceEnabled ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200' : 'bg-slate-100 text-slate-600 ring-1 ring-slate-200'}`}>
                {photoIntelligenceEnabled ? 'Включено' : 'Выключено'}
              </span>
              <Switch
                checked={photoIntelligenceEnabled}
                onCheckedChange={handleTogglePhotoIntelligence}
                disabled={!currentBusinessId || photoIntelligenceLoading || photoIntelligenceSaving}
                aria-label="Включить обработку фото"
                className="data-[state=checked]:bg-emerald-600"
              />
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-[1fr_220px]">
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
              <div className="flex items-start gap-3">
                <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
                <p className="text-sm leading-6 text-slate-600">
                  Анализ запускается только после вашего действия. Результат сохраняется, поэтому повторная работа с тем же фото не списывает кредиты ещё раз.
                </p>
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
              <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Стоимость</div>
              <div className="mt-1 text-2xl font-semibold text-slate-950">2</div>
              <div className="text-sm text-slate-600">кредита за новое фото</div>
            </div>
          </div>
        </div>

        {/* VK */}
        <div
          ref={vkCardRef}
          data-testid="social-settings-vk-card"
          className={[
            'flex flex-col gap-4 rounded-3xl border p-5',
            isVkFocused ? focusedCardClass : 'border-slate-200 bg-slate-50/70',
          ].join(' ')}
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 className="text-base font-semibold text-slate-950">VK публикации</h3>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
                Подключите токен сообщества с правом wall.post, чтобы утверждённые посты выходили во VK по расписанию.
              </p>
              {isVkFocused ? (
                <p className="mt-2 rounded-xl border border-sky-200 bg-white px-3 py-2 text-xs leading-5 text-sky-900">
                  Вы пришли из контент-плана: VK обычно самый быстрый путь ко второму API-proof после Telegram. Публикация всё равно начнётся только после подтверждения и расписания.
                </p>
              ) : null}
            </div>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${vkAccount ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200' : 'bg-slate-100 text-slate-600 ring-1 ring-slate-200'}`}>
              {vkAccount ? 'Подключён' : 'Не подключён'}
            </span>
          </div>

          <div className="grid gap-3 lg:grid-cols-[1fr_220px_160px]">
            <Input
              type="password"
              placeholder="VK access_token с правом wall.post"
              value={vkAccessToken}
              onChange={(event) => setVkAccessToken(event.target.value)}
              disabled={vkBusy || !currentBusinessId}
            />
            <Input
              placeholder="group_id или owner_id"
              value={vkOwnerId}
              onChange={(event) => setVkOwnerId(event.target.value)}
              disabled={vkBusy || !currentBusinessId}
            />
            <Input
              placeholder="scope"
              value={vkScope}
              onChange={(event) => setVkScope(event.target.value)}
              disabled={vkBusy || !currentBusinessId}
            />
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs leading-5 text-slate-500">
              Токен хранится зашифрованно и после сохранения не отображается. Для группы обычно нужен owner_id вида -123456 или group_id без минуса.
              {vkAccount ? ` Сейчас подключено: ${vkAccount.display_name || vkAccount.external_id || 'VK'}.` : ''}
            </p>
            <Button
              type="button"
              onClick={handleSaveVk}
              disabled={vkBusy || !currentBusinessId || !vkAccessToken.trim() || !vkOwnerId.trim()}
              className="bg-slate-900 text-white hover:bg-slate-800 sm:min-w-[180px]"
            >
              {vkBusy ? t.dashboard.subscription.processing : "Сохранить VK"}
            </Button>
          </div>
        </div>

        {/* Maton.ai */}
        <div className="flex flex-col gap-4 rounded-3xl border border-slate-200 bg-slate-50/70 p-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 className="text-base font-semibold text-slate-950">Maton.ai</h3>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
              Maton позволяет подключить множество сторонних сервисов через один API-ключ.
              {' '}
              <a
                href="https://www.maton.ai/"
                target="_blank"
                rel="noreferrer"
                className="font-medium text-slate-900 underline underline-offset-4 hover:text-slate-700"
              >
                https://www.maton.ai/
              </a>
              </p>
            </div>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${matonAccount ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200' : 'bg-slate-100 text-slate-600 ring-1 ring-slate-200'}`}>
              {matonAccount ? 'Подключён' : 'Не подключён'}
            </span>
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            <Input
              type="password"
              placeholder="Введите API-ключ Maton.ai"
              value={matonApiKey}
              onChange={(e) => setMatonApiKey(e.target.value)}
              disabled={saving || !currentBusinessId}
            />
            <Button
              onClick={handleSaveMaton}
              disabled={saving || !currentBusinessId || !matonApiKey.trim()}
              className="bg-slate-900 text-white hover:bg-slate-800 sm:min-w-[180px]"
            >
              {saving ? t.dashboard.subscription.processing : "Сохранить ключ"}
            </Button>
          </div>

          <p className="text-xs leading-5 text-slate-500">
            Ключ хранится в зашифрованном виде. После сохранения в интерфейсе не отображается.
          </p>
        </div>

        <div className="grid gap-5 xl:grid-cols-2">
          <div className="rounded-3xl border border-slate-200 bg-slate-50/70 p-4">
            <OpenClawOutboxMetrics businessId={currentBusinessId || undefined} />
          </div>
          <div className="rounded-3xl border border-slate-200 bg-slate-50/70 p-4">
            <ChannelControlCenter businessId={currentBusinessId} />
          </div>
        </div>

        {/* Список подключённых аккаунтов */}
        <div className="space-y-3 border-t border-slate-100 pt-5">
          <div>
            <h3 className="text-sm font-semibold text-slate-950">{t.dashboard.settings.external.connectedAccounts}</h3>
            <p className="mt-1 text-xs leading-5 text-slate-500">Здесь видны реальные подключённые источники данных и их последний статус.</p>
          </div>
          {loading ? (
            <p className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">{t.dashboard.subscription.processing}</p>
          ) : accounts.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-500">{t.dashboard.settings.external.noIntegrations}</p>
          ) : (
            <div className="space-y-2">
              {accounts.map((acc) => (
                <div
                  key={acc.id}
                  className="flex flex-col rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm md:flex-row md:items-center md:justify-between"
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-1">
                      {acc.source === "google_business" ? (
                        <svg className="w-5 h-5" viewBox="0 0 24 24">
                          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                        </svg>
                      ) : (
                        <div className="w-5 h-5 rounded-full bg-slate-200" />
                      )}
                    </div>
                    <div className="space-y-0.5">
                      <div className="font-medium text-sm">
                        {acc.source === "yandex_business"
                          ? "Яндекс.Бизнес"
                          : acc.source === "google_business"
                            ? "Google-доступ"
                            : acc.source === "2gis"
                              ? "2ГИС"
                              : acc.source === "maton"
                                ? "Maton.ai"
                              : acc.source}
                      </div>
                      {acc.source === "google_business" ? (
                        <div className="flex flex-wrap gap-1 pt-1">
                          <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 ring-1 ring-emerald-100">
                            Таблицы
                          </span>
                          <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${acc.external_id ? 'bg-emerald-50 text-emerald-700 ring-emerald-100' : 'bg-slate-50 text-slate-600 ring-slate-200'}`}>
                            Карточка
                          </span>
                        </div>
                      ) : null}
                      {acc.display_name && (
                        <div className="text-sm text-slate-700">{acc.display_name}</div>
                      )}
                      {acc.external_id && (
                        <div className="text-xs text-slate-400">ID: {acc.external_id}</div>
                      )}

                      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1">
                        {acc.last_sync_at && (
                          <div className="flex items-center gap-1 text-xs text-slate-500">
                            <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                            {t.dashboard.settings.external.sync} {new Date(acc.last_sync_at).toLocaleString(language === 'ru' ? 'ru-RU' : 'en-US')}
                          </div>
                        )}
                        {acc.last_error && (
                          <div className="text-xs text-red-600 flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span>
                            {t.dashboard.settings.external.error} {acc.last_error}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 md:mt-0 flex gap-2 justify-end items-center">
                    <div className={`rounded-full px-3 py-1 text-xs font-semibold ${acc.is_active ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200' : 'bg-slate-100 text-slate-600 ring-1 ring-slate-200'}`}>
                      {acc.is_active ? t.dashboard.settings.external.active : t.dashboard.settings.external.disabled}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={saving}
                      onClick={() => handleDisconnect(acc.id)}
                      className="text-red-500 hover:text-red-600 hover:bg-red-50 border-red-100 h-8"
                    >
                      {t.dashboard.settings.external.disconnect}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
          </div>
        </details>
      </CardContent>
    </Card>
  );
};
