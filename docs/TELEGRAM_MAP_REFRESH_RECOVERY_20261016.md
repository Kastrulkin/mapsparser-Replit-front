# Telegram map refresh recovery — 2026-10-16

The user's refresh confirmation reached the API but returned HTTP 400. The saved Yandex `/profile/<id>` link was rejected by the organization-link validator. The error appeared underneath the confirmation overlay, leaving no visible feedback.

Changes: normalize trusted HTTP(S) Yandex profile links to canonical organization links; validate links before credit reservation; show blocked reasons inside the confirmation; preserve retry controls; clear a stale device-offline warning on an actual API response. Preview explicitly names Yandex because the existing mobile executor only refreshes Yandex. Google recommendations and provider-specific Google/2GIS refresh remain a separate integration gap; this fix does not claim to refresh those providers.

Verification: 35 focused backend tests; 8 focused UI tests; frontend TypeScript checks; main Vite production build. A broader pre-existing TelegramControlPage suite fails because its fixtures omit LanguageProvider. The optional public-audit build could not run from the isolated snapshot because its HTML entry was not included; the existing production public-audit build was preserved.

Production: source drift checked against the live snapshot before atomic entrypoint switch; original six source files and HTML backed up in `/opt/seo-app/backups/telegram-cards-refresh-20261016-145634`; old hashed assets preserved. Gunicorn reloaded gracefully. Container source hashes checked. `/telegram/control` HTTP 200. A read-only preflight against the actual Riderra link returns ready with canonical URL and no side effects. No refresh was submitted and no provider result is claimed; device acceptance and the paid provider run require a fresh user confirmation.
