# Preserve unfinished content setup

Closing content setup previously discarded unfinished company, founder, audience, tone and example fields. The same shared component serves the web workspace and both messenger routes.

A close or a transition to general business knowledge now offers Continue filling or Discard and close when fields have changed. Unchanged forms close immediately. Successful profile save updates the saved baseline; separate example input remains unsaved until its own Add action. Switching between steps or opening sources retains existing behavior. This change does not save automatically, regenerate existing plans or publish anything.

Validation: four regression cases failed before the change; all five focused cases passed afterward. The common branch passed 22 adjacent personalization/reference tests. The production-based frontend build passed. A live Telegram pass verified close protection, continue with retained founder text, protection before general knowledge navigation, and explicit discard. Temporary text was discarded without saving to the client profile. Live MAX and physical-device behavior remain separate acceptance requirements.
