# Evidence: fix-whatsapp-lead-audits

## Scope
- Production group: `Канал - Востапп`
- Group id: `cb88c1fa-637f-41df-bef3-05aeda192f58`
- Leads/audits processed: 224

## Backup
- Created production backup before writes:
  - `/opt/seo-app/backups/audit_repair/whatsapp_lead_audits_20260506_171702.sql.gz`

## Code changes
- `src/core/card_audit.py`
  - Added default-local guard for obvious non-beauty retail/hypermarket categories.
  - Removed user-facing `beauty-*` language from generated audit copy.
- `src/core/public_audit_editor.py`
  - Added public audit copy sanitizer for stale phrases, city grammar, internal terminology and English `social proof`.
  - Normalizes full public page JSON, including `audit_full`.
- `src/api/admin_prospecting.py`
  - Applies public audit normalizer when generating admin lead public offer pages.
  - Replaced old deterministic phrases: `реальный спрос`, `тёплый спрос`, generic competitor wording.

## Production rollout
- Rebuilt/restarted only backend services:
  - `docker compose up -d --build app worker`
- Health checked:
  - `docker compose ps`
  - `curl -I http://localhost:8000` returned `200 OK`

## Data repair
- Rebuilt and republished all 224 public lead audits for the group.
- Preserved `edited_json` path in script logic; no published manual editor overlay was present in final update run.
- Final profile distribution:
  - `beauty`: 140
  - `medical`: 39
  - `wellness`: 28
  - `default_local_business`: 12
  - `food`: 3
  - `fashion`: 2

## Quality gate
Final gate over all 224 audits:
- active public audits: 224/224
- problems: 0
- bad terms found: 0
- empty issue blocks: 0
- missing action plans: 0
- weak evidence blocks: 0

Blocked phrases checked:
- `beauty-опис`
- `сильного beauty`
- `тёплый спрос`
- `салон под реальный спрос`
- `Санкт-Петербургее`
- `в Санкт-Петербург `
- `в Ленинградская область`
- `social proof`
- `medical вертикали`

## Manual sample checked
- `12 Месяцев`: now `default_local_business`, no salon/medical mismatch.
- `Комфорт`: now `medical`, no beauty/manicure mismatch.
- `Beauty Lab`, `4you`, `Aml Clinic`: concrete evidence retained: photo count, rating, prices/services, website.
- `Культура красоты`, `КосМед`, `Евромедсервис`, `Good Med`: profile-specific copy cleaned.
