import type { AgentBlueprint, AgentExecutionMode } from './types';
export type ExecutionSettingsDraft = { mode: AgentExecutionMode; time: string; timezone: string };
export type AgentSettingsDraft = { dataSources: string; extractionRules: string; processingRules: string; outputFormat: string; manualControl: string };
export const mapAgentKind = (blueprint: AgentBlueprint) => {
  const key = blueprint.metadata_json?.template_key;
  return key === 'maps_initial_setup' ? 'preparation' : key === 'maps_card_check' ? 'check' : null;
};
export const allowedExecutionModes = (blueprint: AgentBlueprint): AgentExecutionMode[] => mapAgentKind(blueprint) === 'preparation' ? ['one_off', 'manual'] : ['one_off', 'manual', 'scheduled'];
