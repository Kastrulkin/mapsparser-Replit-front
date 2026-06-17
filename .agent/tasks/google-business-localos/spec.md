# Task Spec: google-business-localos

## Metadata
- Task ID: google-business-localos
- Created: 2026-06-17T08:28:38+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Создать Google Business Profile приложение для LocalOS, подготовить отправку на согласование, авторизацию пользователя и доделать сторону LocalOS для отзывов, ответов, новостей, услуг и цен

## Acceptance criteria
- AC1: Google Cloud OAuth app for LocalOS is created or documented as blocked.
- AC2: LocalOS can start Google OAuth and store encrypted credentials in the current `externalbusinessaccounts` schema.
- AC3: LocalOS can list and bind Google Business Profile locations after OAuth.
- AC4: LocalOS can manually sync Google reviews/statistics for a bound location.
- AC5: Google review replies and posts keep a hard manual approval boundary.
- AC6: Frontend gives the user a task-oriented Google connection flow.
- AC7: Setup/approval runbook documents env, project, and Google approval steps without committing secrets.

## Constraints
- Do not commit Google client secret.
- Do not modify production data without explicit approval.
- External publishing requires explicit user approval.
- Basic GBP API access may require Google review and CAPTCHA/manual form completion.

## Non-goals
- Full production deployment.
- Bypassing Google CAPTCHA or verification.
- Fully autonomous publishing to Google.
- A full service/price schema migration beyond the current transitional LocalOS data model.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: targeted Python compile for changed Google modules
- Integration tests: OAuth/browser flow in Google Cloud Console; runtime API test after server env is configured
- Lint: existing project lint not configured for this task
- Manual checks: Google Cloud OAuth app/client/test user setup; Basic API Access form attempt
