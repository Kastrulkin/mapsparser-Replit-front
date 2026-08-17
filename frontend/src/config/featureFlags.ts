export const featureFlags = {
  settingsHubV2: import.meta.env.VITE_SETTINGS_HUB_V2 !== 'false',
  webTracking: import.meta.env.VITE_WEB_TRACKING_ENABLED === 'true',
};
