export const featureFlags = {
  settingsHubV2: import.meta.env.VITE_SETTINGS_HUB_V2 !== 'false',
  webTracking: import.meta.env.VITE_WEB_TRACKING_ENABLED === 'true',
  promotionHub: import.meta.env.VITE_PROMOTION_HUB_ENABLED === 'true',
  contentJourney: import.meta.env.VITE_CONTENT_JOURNEY_ENABLED === 'true',
  journeyAdminBuilder: import.meta.env.VITE_JOURNEY_ADMIN_BUILDER_ENABLED === 'true',
  journeyPostAuthRedirect: import.meta.env.VITE_JOURNEY_POST_AUTH_REDIRECT_ENABLED === 'true',
  // Keep the guided dashboard navigation as the default even if an old deploy
  // still carries VITE_GROWTH_PATHS_NAVIGATION_ENABLED=false. The legacy menu
  // is intentionally retained only as a compatibility branch during rollout.
  growthPathsNavigation: true,
  blockAccessV2: import.meta.env.VITE_BLOCK_ACCESS_V2_ENABLED === 'true',
  compiledScriptPreview: import.meta.env.VITE_COMPILED_SCRIPT_PREVIEW_ENABLED === 'true',
};
