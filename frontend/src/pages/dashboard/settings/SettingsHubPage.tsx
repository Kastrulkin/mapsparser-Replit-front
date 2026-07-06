import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useOutletContext } from 'react-router-dom';
import { Cable, ClipboardCheck, Settings } from 'lucide-react';

import FinanceCrmPanel from '@/components/FinanceCrmPanel';
import { ExternalIntegrations } from '@/components/ExternalIntegrations';
import TelegramConnection from '@/components/TelegramConnection';
import { TelegramBotCredentials } from '@/components/TelegramBotCredentials';
import { TelegramOpportunityRadar } from '@/components/TelegramOpportunityRadar';
import WhatsAppConnection from '@/components/WhatsAppConnection';
import { WABACredentials } from '@/components/WABACredentials';
import { Button } from '@/components/ui/button';
import { DashboardPageHeader, DashboardSection } from '@/components/dashboard/DashboardPrimitives';
import { useLanguage } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';

import IntegrationsPageV3 from './IntegrationsPageV3';
import {
  NextStepBanner,
  ReadinessSummary,
  SecondaryLinks,
  SettingsDetailSheet,
  SettingsModuleCard,
} from './SettingsHubComponents';
import { getSettingsHubCopy, SettingsHubCopy } from './settingsHubCopy';
import {
  SettingsHubBusiness,
  SettingsHubCrmProvider,
  SettingsHubExternalAccount,
  SettingsHubRawState,
  SettingsHubSocialReadiness,
  mapSettingsState,
} from './settingsHubState';

type SettingsHubOutletContext = {
  currentBusinessId?: string | null;
  currentBusiness?: SettingsHubBusiness | null;
};

type HubLoadState = {
  telegramOwnerLinked?: boolean | null;
  telegramPublishStatus?: SettingsHubRawState['telegramPublishStatus'];
  socialReadiness: SettingsHubSocialReadiness[];
  externalAccounts: SettingsHubExternalAccount[];
  crmProviders: SettingsHubCrmProvider[];
};

const emptyLoadState: HubLoadState = {
  telegramOwnerLinked: null,
  telegramPublishStatus: null,
  socialReadiness: [],
  externalAccounts: [],
  crmProviders: [],
};

const authHeaders = () => {
  const token = newAuth.getToken() || localStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const fetchJson = async (url: string, options?: RequestInit) => {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  return { response, data };
};

const firstArray = (value: unknown) => Array.isArray(value) ? value : [];

const detailCopy = (detail: string | null, copy: SettingsHubCopy) => {
  if (detail === 'telegram') return copy.details.telegram;
  if (detail === 'whatsapp') return copy.details.whatsapp;
  if (detail === 'crm') return copy.details.crm;
  if (detail === 'publications') return copy.details.publications;
  return copy.details.integrations;
};

export const SettingsHubPage = () => {
  const location = useLocation();
  const { language } = useLanguage();
  const { currentBusinessId, currentBusiness } = useOutletContext<SettingsHubOutletContext>();
  const [loadState, setLoadState] = useState<HubLoadState>(emptyLoadState);
  const [loading, setLoading] = useState(false);
  const [activeDetail, setActiveDetail] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const copy = useMemo(() => getSettingsHubCopy(language), [language]);

  const focusTarget = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get('focus') || location.hash.replace(/^#/, '');
  }, [location.hash, location.search]);

  useEffect(() => {
    if (!focusTarget) return;
    if (focusTarget === 'channels') {
      setActiveDetail('publications');
      return;
    }
    if (focusTarget === 'integrations') {
      setActiveDetail('integrations');
      return;
    }
    setActiveDetail(focusTarget);
  }, [focusTarget]);

  useEffect(() => {
    let cancelled = false;

    const loadHubState = async () => {
      if (!currentBusinessId) {
        setLoadState(emptyLoadState);
        return;
      }

      setLoading(true);
      const headers = authHeaders();

      try {
        const [
          ownerStatus,
          telegramStatus,
          readiness,
          accounts,
          crmProviders,
        ] = await Promise.all([
          fetchJson(`/api/telegram/bind/status?business_id=${encodeURIComponent(currentBusinessId)}`, { headers }),
          fetchJson(`/api/business/telegram-bot/status?business_id=${encodeURIComponent(currentBusinessId)}`, { headers }),
          fetchJson(`/api/business/${encodeURIComponent(currentBusinessId)}/social-posts/channel-readiness`, { headers }),
          fetchJson(`/api/business/${encodeURIComponent(currentBusinessId)}/external-accounts`, { headers }),
          fetchJson(`/api/finance/crm/providers?business_id=${encodeURIComponent(currentBusinessId)}`, { headers }),
        ]);

        if (cancelled) return;

        setLoadState({
          telegramOwnerLinked: ownerStatus.response.ok ? Boolean(ownerStatus.data.is_linked) : false,
          telegramPublishStatus: telegramStatus.response.ok && telegramStatus.data.success ? {
            configured: Boolean(telegramStatus.data.configured),
            global_bot_configured: Boolean(telegramStatus.data.global_bot_configured),
            telegram_chat_id: telegramStatus.data.telegram_chat_id || null,
          } : null,
          socialReadiness: readiness.response.ok && readiness.data.success
            ? firstArray(readiness.data.channel_readiness)
            : [],
          externalAccounts: accounts.response.ok && accounts.data.success
            ? firstArray(accounts.data.accounts)
            : [],
          crmProviders: crmProviders.response.ok && crmProviders.data.success
            ? firstArray(crmProviders.data.providers)
            : [],
        });
      } catch {
        if (!cancelled) setLoadState(emptyLoadState);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadHubState();
    return () => {
      cancelled = true;
    };
  }, [currentBusinessId, refreshKey]);

  const hubState = useMemo(() => mapSettingsState({
    business: currentBusiness || null,
    telegramOwnerLinked: loadState.telegramOwnerLinked,
    telegramPublishStatus: loadState.telegramPublishStatus,
    socialReadiness: loadState.socialReadiness,
    externalAccounts: loadState.externalAccounts,
    crmProviders: loadState.crmProviders,
  }), [currentBusiness, loadState]);

  const moduleList = [
    hubState.modules.telegram,
    hubState.modules.whatsapp,
    hubState.modules.google_sheets,
    hubState.modules.google,
    hubState.modules.vk,
    hubState.modules.meta,
    hubState.modules.crm,
    hubState.modules.maton,
  ];

  const integrationFocus = activeDetail && !['telegram', 'whatsapp', 'crm', 'publications'].includes(activeDetail)
    ? activeDetail
    : focusTarget;

  const handleSaved = () => {
    setRefreshKey((value) => value + 1);
  };
  const activeDetailCopy = detailCopy(activeDetail, copy);

  return (
    <div className="mx-auto max-w-6xl space-y-7 pb-10" data-settings-hub-version="v2">
      <DashboardPageHeader
        eyebrow={copy.page.eyebrow}
        title={copy.page.title}
        description={copy.page.description}
        icon={Settings}
        actions={(
          <Button type="button" variant="outline" asChild>
            <Link to="/dashboard/settings/integrations">{copy.page.openDetails}</Link>
          </Button>
        )}
      />

      {loading ? (
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
          {copy.page.loading}
        </div>
      ) : null}

      <ReadinessSummary summary={hubState.summary} copy={copy} />
      <NextStepBanner nextStep={hubState.nextStep} onOpenDetail={setActiveDetail} copy={copy} />

      <section data-settings-hub-first-layer="module-grid" className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {moduleList.map((module) => (
          <SettingsModuleCard key={module.key} module={module} onOpenDetail={setActiveDetail} copy={copy} />
        ))}
      </section>

      <SecondaryLinks copy={copy} />

      <SettingsDetailSheet
        open={Boolean(activeDetail)}
        title={activeDetailCopy.title}
        description={activeDetailCopy.description}
        onOpenChange={(open) => {
          if (!open) setActiveDetail(null);
        }}
      >
        {activeDetail === 'telegram' ? (
          <>
            <TelegramConnection currentBusinessId={currentBusinessId} />
            <TelegramBotCredentials businessId={currentBusinessId || null} business={currentBusiness} onSaved={handleSaved} />
            <TelegramOpportunityRadar businessId={currentBusinessId || null} />
          </>
        ) : activeDetail === 'whatsapp' ? (
          <>
            <WhatsAppConnection currentBusinessId={currentBusinessId} business={currentBusiness} />
            <WABACredentials businessId={currentBusinessId || null} business={currentBusiness} />
          </>
        ) : activeDetail === 'crm' ? (
          <FinanceCrmPanel currentBusinessId={currentBusinessId} surface="embedded" />
        ) : (
          <ExternalIntegrations
            currentBusinessId={currentBusinessId || null}
            readinessRefreshKey={refreshKey}
            focusedPlatform={integrationFocus}
          />
        )}
      </SettingsDetailSheet>
    </div>
  );
};

export const SettingsDiagnosticsPage = () => {
  const { language } = useLanguage();
  const copy = useMemo(() => getSettingsHubCopy(language), [language]);
  const { currentBusinessId } = useOutletContext<SettingsHubOutletContext>();

  return (
    <div className="mx-auto max-w-6xl space-y-7 pb-10">
      <DashboardPageHeader
        eyebrow={copy.routes.advancedEyebrow}
        title={copy.routes.diagnosticsTitle}
        description={copy.routes.diagnosticsDescription}
        icon={ClipboardCheck}
        actions={<Button type="button" variant="outline" asChild><Link to="/dashboard/settings">{copy.routes.backToHub}</Link></Button>}
      />
      <DashboardSection title={copy.routes.diagnosticsSectionTitle} description={copy.routes.diagnosticsSectionDescription}>
        <ExternalIntegrations currentBusinessId={currentBusinessId || null} />
      </DashboardSection>
    </div>
  );
};

export const SettingsPublicationsPage = () => {
  const location = useLocation();
  const { language } = useLanguage();
  const copy = useMemo(() => getSettingsHubCopy(language), [language]);
  const { currentBusinessId, currentBusiness } = useOutletContext<SettingsHubOutletContext>();
  const params = new URLSearchParams(location.search);
  const focus = params.get('focus') || 'telegram';

  return (
    <div className="mx-auto max-w-6xl space-y-7 pb-10">
      <DashboardPageHeader
        eyebrow={copy.routes.settingsEyebrow}
        title={copy.routes.publicationsTitle}
        description={copy.routes.publicationsDescription}
        icon={ClipboardCheck}
        actions={<Button type="button" variant="outline" asChild><Link to="/dashboard/settings">{copy.routes.backToHub}</Link></Button>}
      />
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <TelegramBotCredentials businessId={currentBusinessId || null} business={currentBusiness} />
        <ExternalIntegrations currentBusinessId={currentBusinessId || null} focusedPlatform={focus} />
      </div>
    </div>
  );
};

export const SettingsIntegrationsPage = () => {
  const location = useLocation();
  const { language } = useLanguage();
  const copy = useMemo(() => getSettingsHubCopy(language), [language]);
  const { currentBusinessId, currentBusiness } = useOutletContext<SettingsHubOutletContext>();
  const params = new URLSearchParams(location.search);
  const focus = params.get('focus') || 'integrations';
  const integrationsV3Enabled = import.meta.env.VITE_SETTINGS_INTEGRATIONS_V3 !== 'false';

  if (integrationsV3Enabled) {
    return (
      <IntegrationsPageV3
        currentBusinessId={currentBusinessId || null}
        currentBusiness={currentBusiness || null}
        focus={focus}
      />
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-7 pb-10">
      <DashboardPageHeader
        eyebrow={copy.routes.settingsEyebrow}
        title={copy.routes.integrationsTitle}
        description={copy.routes.integrationsDescription}
        icon={Cable}
        actions={<Button type="button" variant="outline" asChild><Link to="/dashboard/settings">{copy.routes.backToHub}</Link></Button>}
      />
      <ExternalIntegrations currentBusinessId={currentBusinessId || null} focusedPlatform={focus} />
      <details
        open={focus === 'crm'}
        className="rounded-3xl border border-slate-200 bg-white px-4 py-4 shadow-sm"
      >
        <summary className="cursor-pointer select-none text-sm font-semibold text-slate-950">
          CRM: YCLIENTS и Altegio
        </summary>
        <div className="mt-4">
          <FinanceCrmPanel currentBusinessId={currentBusinessId} surface="embedded" />
        </div>
      </details>
    </div>
  );
};
