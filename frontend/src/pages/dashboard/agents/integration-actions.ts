import { api } from '@/services/api';
import { humanizeMeta } from './model';
import { connectorLabel, getRequestErrorMessage, normalizePostCreateHandoff, normalizeSpreadsheetInput } from './normalization';
import type { AgentBlueprint, AgentIntegration, AgentIntegrationBindingStatus, AgentProviderRoute, AgentWorkspaceMode } from './types';

type IntegrationActionOptions = {
  selectedBlueprint: AgentBlueprint | null;
  agentBindingStatus: AgentIntegrationBindingStatus[];
  selectedConnectionBindingKey: string;
  agentIntegrations: AgentIntegration[];
  availableAgentIntegrations: AgentIntegration[];
  sheetSpreadsheetId: string;
  sheetName: string;
  sheetAuthRef: string;
  sheetDailyCap: string;
  browserTargetUrls: string;
  browserDailyCap: string;
  telegramBotMode: string;
  telegramDailyCap: string;
  whatsappChannelMode: string;
  whatsappDailyCap: string;
  matonAuthRef: string;
  matonChannel: string;
  matonDailyCap: string;
  setActionLoading: (value: boolean) => void;
  setError: (value: string | null) => void;
  setDecisionNotice: (value: string | null) => void;
  setSelectedConnectionBindingKey: (value: string) => void;
  setWorkspaceMode: (value: AgentWorkspaceMode) => void;
  loadAgentIntegrations: (blueprintId: string) => Promise<void>;
  loadBlueprintDetails: (blueprintId: string) => Promise<void>;
  loadBlueprintReview: (blueprintId: string) => Promise<void>;
  applyPostConnectHandoff: (value: unknown) => void;
};

// Created for each render, retaining the same captured inputs as the workspace handlers.
export const createAgentIntegrationActions = ({
  selectedBlueprint, agentBindingStatus, selectedConnectionBindingKey,
  agentIntegrations, availableAgentIntegrations,
  sheetSpreadsheetId, sheetName, sheetAuthRef, sheetDailyCap,
  browserTargetUrls, browserDailyCap, telegramBotMode, telegramDailyCap,
  whatsappChannelMode, whatsappDailyCap, matonAuthRef, matonChannel, matonDailyCap,
  setActionLoading, setError, setDecisionNotice, setSelectedConnectionBindingKey,
  setWorkspaceMode, loadAgentIntegrations, loadBlueprintDetails, loadBlueprintReview,
  applyPostConnectHandoff,
}: IntegrationActionOptions) => {
  const saveSheetIntegration = async () => {
    if (!selectedBlueprint || !sheetSpreadsheetId.trim()) {
      return;
    }
    const selectedBinding = agentBindingStatus.find((item) => item.key === selectedConnectionBindingKey && item.provider === 'google_sheets');
    const existing = [...agentIntegrations, ...availableAgentIntegrations].find((item) => item.provider === 'google_sheets');
    const needsRead = agentBindingStatus.some((item) => item.provider === 'google_sheets' && item.capability === 'google_sheets.read_rows');
    const needsAppend = agentBindingStatus.some((item) => item.provider === 'google_sheets' && item.capability === 'sheets.append_row_request');
    const selectedCapability = selectedBinding?.capability || '';
    const operation = selectedCapability === 'google_sheets.read_rows'
      ? 'read_rows'
      : selectedCapability === 'sheets.append_row_request'
        ? 'append_row'
        : needsRead && needsAppend ? 'read_write' : needsRead ? 'read_rows' : 'append_row';
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: existing?.id,
        binding_key: selectedBinding?.key || '',
        provider: 'google_sheets',
        status: 'active',
        display_name: 'Google Sheets',
        auth_ref: sheetAuthRef.trim(),
        config: {
          spreadsheet_id: normalizeSpreadsheetInput(sheetSpreadsheetId),
          sheet_name: sheetName.trim() || 'Sheet1',
          operation,
        },
        limits: {
          daily_append_cap: Number(sheetDailyCap) > 0 ? Number(sheetDailyCap) : 50,
          frequency_cap_minutes: 0,
        },
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      const handoff = normalizePostCreateHandoff(response.data?.post_connect_handoff);
      applyPostConnectHandoff(handoff);
      if (handoff?.status === 'ready_for_preview') {
        setDecisionNotice('Таблица сохранена. Теперь запустите безопасный тест.');
      } else if (handoff?.status === 'needs_connections') {
        const nextTitle = handoff.next_binding?.title || connectorLabel(handoff.next_binding?.provider);
        setDecisionNotice(`Таблица сохранена. Остался следующий доступ: ${nextTitle}.`);
      } else {
        setDecisionNotice('Таблица сохранена.');
      }
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить Google Sheets.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveBrowserUseIntegration = async () => {
    if (!selectedBlueprint || !browserTargetUrls.trim()) {
      return;
    }
    const selectedBinding = agentBindingStatus.find((item) => item.key === selectedConnectionBindingKey && item.provider === 'browser_use');
    const existing = [...agentIntegrations, ...availableAgentIntegrations].find((item) => item.provider === 'browser_use');
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: existing?.id,
        binding_key: selectedBinding?.key || '',
        provider: 'browser_use',
        status: 'active',
        display_name: 'Browser use',
        config: {
          target_urls: browserTargetUrls,
        },
        limits: {
          daily_page_check_cap: Number(browserDailyCap) > 0 ? Number(browserDailyCap) : 50,
          frequency_cap_minutes: 60,
        },
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить Browser use.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveTelegramIntegration = async () => {
    if (!selectedBlueprint) {
      return;
    }
    const selectedBinding = agentBindingStatus.find((item) => item.key === selectedConnectionBindingKey && item.provider === 'telegram');
    const existing = [...agentIntegrations, ...availableAgentIntegrations].find((item) => item.provider === 'telegram');
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: existing?.id,
        binding_key: selectedBinding?.key || '',
        provider: 'telegram',
        status: 'active',
        display_name: 'Telegram',
        config: {
          bot_mode: telegramBotMode,
        },
        limits: {
          daily_message_cap: Number(telegramDailyCap) > 0 ? Number(telegramDailyCap) : 50,
          frequency_cap_minutes: 30,
        },
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить Telegram.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveWhatsappIntegration = async () => {
    if (!selectedBlueprint) {
      return;
    }
    const selectedBinding = agentBindingStatus.find((item) => item.key === selectedConnectionBindingKey && item.provider === 'whatsapp');
    const existing = [...agentIntegrations, ...availableAgentIntegrations].find((item) => item.provider === 'whatsapp');
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: existing?.id,
        binding_key: selectedBinding?.key || '',
        provider: 'whatsapp',
        status: 'active',
        display_name: 'WhatsApp',
        config: {
          channel_mode: whatsappChannelMode,
        },
        limits: {
          daily_message_cap: Number(whatsappDailyCap) > 0 ? Number(whatsappDailyCap) : 50,
          frequency_cap_minutes: 30,
        },
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить WhatsApp.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveMatonIntegration = async () => {
    if (!selectedBlueprint) {
      return;
    }
    const selectedBinding = agentBindingStatus.find((item) => item.key === selectedConnectionBindingKey && item.provider === 'maton');
    const existing = [...agentIntegrations, ...availableAgentIntegrations].find((item) => item.provider === 'maton');
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: existing?.id,
        binding_key: selectedBinding?.key || '',
        provider: 'maton',
        status: 'active',
        display_name: 'Maton.ai',
        auth_ref: matonAuthRef.trim(),
        config: {
          channel: matonChannel.trim() || 'maton_bridge',
        },
        limits: {
          daily_message_cap: Number(matonDailyCap) > 0 ? Number(matonDailyCap) : 50,
          frequency_cap_minutes: 30,
        },
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить Maton.ai.'));
    } finally {
      setActionLoading(false);
    }
  };

  const chooseProviderRoute = async (bindingKey: string, route: AgentProviderRoute) => {
    if (!selectedBlueprint || !bindingKey || !route.provider) {
      return;
    }
    if (route.provider === 'maton' && !matonAuthRef.trim()) {
      setSelectedConnectionBindingKey(bindingKey);
      setWorkspaceMode('connections');
      setError('Выберите сохранённый Maton.ai key для этого шага.');
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/provider-routes`, {
        binding_key: bindingKey,
        route_provider: route.provider,
        external_account_id: route.provider === 'maton' ? matonAuthRef.trim() : '',
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      await loadBlueprintReview(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось выбрать способ подключения для агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  const attachExistingAgentIntegration = async (integration: AgentIntegration, bindingKey = '') => {
    if (!selectedBlueprint || !integration?.id || !integration.provider) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: integration.id,
        binding_key: bindingKey,
        provider: integration.provider,
        status: 'active',
        display_name: integration.display_name || integration.provider_label || humanizeMeta(integration.provider),
        auth_ref: integration.auth_ref || '',
        config: integration.config || {},
        limits: integration.limits || {},
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить существующий доступ к агенту.'));
    } finally {
      setActionLoading(false);
    }
  };

  return {
    saveSheetIntegration, saveBrowserUseIntegration, saveTelegramIntegration,
    saveWhatsappIntegration, saveMatonIntegration, chooseProviderRoute, attachExistingAgentIntegration,
  };
};
