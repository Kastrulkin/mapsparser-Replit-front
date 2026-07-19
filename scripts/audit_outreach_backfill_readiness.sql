\set ON_ERROR_STOP on

-- Read-only readiness report for the controlled outreach enrichment backfill.
-- This script does not enqueue jobs, update leads, prepare drafts, or send messages.

WITH latest_research AS (
    SELECT DISTINCT ON (workstream_id)
           workstream_id,
           COALESCE(NULLIF(message_readiness_json ->> 'code', ''), 'missing_code') AS readiness_code,
           qualification_stage,
           CASE
               WHEN jsonb_typeof(COALESCE(evidence_json, '[]'::jsonb)) = 'array'
               THEN jsonb_array_length(COALESCE(evidence_json, '[]'::jsonb))
               ELSE 0
           END AS evidence_count,
           CASE
               WHEN jsonb_typeof(COALESCE(personalization_candidates_json, '[]'::jsonb)) = 'array'
               THEN jsonb_array_length(COALESCE(personalization_candidates_json, '[]'::jsonb))
               ELSE 0
           END AS personalization_count,
           selected_personalization_id
    FROM lead_workstream_research
    ORDER BY workstream_id, researched_at DESC, created_at DESC
),
latest_job AS (
    SELECT DISTINCT ON (workstream_id)
           workstream_id,
           status AS job_status,
           error_code
    FROM lead_enrichment_jobs
    ORDER BY workstream_id, created_at DESC
),
contact_rollup AS (
    SELECT lead_id,
           COUNT(*) AS contact_count,
           COUNT(*) FILTER (
               WHERE verification_status NOT IN ('invalid', 'stale')
           ) AS usable_contact_count
    FROM lead_contact_points
    GROUP BY lead_id
),
workstream_readiness AS (
    SELECT ws.id AS workstream_id,
           ws.workstream_type,
           lead.id AS lead_id,
           lr.readiness_code,
           lr.qualification_stage,
           COALESCE(lr.evidence_count, 0) AS evidence_count,
           COALESCE(lr.personalization_count, 0) AS personalization_count,
           lr.selected_personalization_id,
           lj.job_status,
           lj.error_code,
           COALESCE(cr.usable_contact_count, 0) AS usable_contact_count,
           EXISTS (
               SELECT 1
               FROM adminprospectingleadpublicoffers offer
               WHERE offer.lead_id = lead.id
                 AND offer.is_active = TRUE
           ) AS has_public_audit,
           COALESCE(
               NULLIF(BTRIM(lead.phone), ''),
               NULLIF(BTRIM(lead.email), ''),
               NULLIF(BTRIM(lead.telegram_url), ''),
               NULLIF(BTRIM(lead.whatsapp_url), '')
           ) IS NOT NULL AS has_legacy_direct_contact
    FROM lead_workstreams ws
    JOIN prospectingleads lead ON lead.id = ws.lead_id
    LEFT JOIN latest_research lr ON lr.workstream_id = ws.id
    LEFT JOIN latest_job lj ON lj.workstream_id = ws.id
    LEFT JOIN contact_rollup cr ON cr.lead_id = lead.id
)
SELECT workstream_type,
       COUNT(*) AS total_workstreams,
       COUNT(*) FILTER (WHERE readiness_code IS NULL) AS missing_research,
       COUNT(*) FILTER (WHERE readiness_code IS NOT NULL) AS with_research,
       COUNT(*) FILTER (WHERE has_public_audit) AS with_public_audit,
       COUNT(*) FILTER (WHERE usable_contact_count > 0) AS with_normalized_contact,
       COUNT(*) FILTER (WHERE has_legacy_direct_contact) AS with_legacy_direct_contact,
       COUNT(*) FILTER (
           WHERE usable_contact_count = 0
             AND NOT has_legacy_direct_contact
       ) AS without_direct_contact,
       COUNT(*) FILTER (WHERE evidence_count > 0) AS with_evidence,
       COUNT(*) FILTER (WHERE personalization_count > 0) AS with_personalization_variants,
       COUNT(*) FILTER (WHERE selected_personalization_id IS NOT NULL) AS with_selected_personalization,
       COUNT(*) FILTER (WHERE job_status IS NULL) AS without_job,
       COUNT(*) FILTER (
           WHERE job_status IN (
               'queued', 'collecting', 'verifying', 'researching',
               'drafting', 'retry_wait'
           )
       ) AS active_jobs,
       COUNT(*) FILTER (
           WHERE job_status IN ('ready', 'needs_contact', 'needs_evidence', 'suppressed')
       ) AS terminal_result,
       COUNT(*) FILTER (WHERE job_status = 'failed') AS failed_jobs
FROM workstream_readiness
GROUP BY workstream_type
ORDER BY workstream_type;

WITH latest_research AS (
    SELECT DISTINCT ON (workstream_id)
           workstream_id,
           COALESCE(NULLIF(message_readiness_json ->> 'code', ''), 'missing_code') AS readiness_code
    FROM lead_workstream_research
    ORDER BY workstream_id, researched_at DESC, created_at DESC
)
SELECT ws.workstream_type,
       latest_research.readiness_code,
       COUNT(*) AS workstreams
FROM latest_research
JOIN lead_workstreams ws ON ws.id = latest_research.workstream_id
GROUP BY ws.workstream_type, latest_research.readiness_code
ORDER BY ws.workstream_type, workstreams DESC, latest_research.readiness_code;

WITH latest_job AS (
    SELECT DISTINCT ON (workstream_id)
           workstream_id,
           status,
           NULLIF(error_code, '') AS error_code
    FROM lead_enrichment_jobs
    ORDER BY workstream_id, created_at DESC
)
SELECT ws.workstream_type,
       latest_job.status,
       latest_job.error_code,
       COUNT(*) AS workstreams
FROM latest_job
JOIN lead_workstreams ws ON ws.id = latest_job.workstream_id
GROUP BY ws.workstream_type, latest_job.status, latest_job.error_code
ORDER BY ws.workstream_type, workstreams DESC, latest_job.status, latest_job.error_code;

WITH latest_research AS (
    SELECT DISTINCT ON (workstream_id)
           workstream_id,
           message_readiness_json
    FROM lead_workstream_research
    ORDER BY workstream_id, researched_at DESC, created_at DESC
),
missing_reason AS (
    SELECT latest_research.workstream_id,
           reason.value AS reason
    FROM latest_research
    CROSS JOIN LATERAL jsonb_array_elements_text(
        CASE
            WHEN jsonb_typeof(latest_research.message_readiness_json -> 'missing') = 'array'
            THEN latest_research.message_readiness_json -> 'missing'
            ELSE '[]'::jsonb
        END
    ) AS reason(value)
)
SELECT ws.workstream_type,
       missing_reason.reason,
       COUNT(DISTINCT missing_reason.workstream_id) AS workstreams
FROM missing_reason
JOIN lead_workstreams ws ON ws.id = missing_reason.workstream_id
GROUP BY ws.workstream_type, missing_reason.reason
ORDER BY ws.workstream_type, workstreams DESC, missing_reason.reason;

SELECT ws.workstream_type,
       COUNT(DISTINCT draft.workstream_id) AS workstreams_with_draft,
       COUNT(*) AS drafts,
       COUNT(*) FILTER (WHERE NULLIF(BTRIM(draft.generated_text), '') IS NOT NULL) AS drafts_with_text,
       COUNT(*) FILTER (WHERE draft.quality_gate_json ->> 'passed' = 'true') AS quality_passed_drafts,
       COUNT(*) FILTER (WHERE draft.status = 'approved') AS approved_drafts
FROM outreachmessagedrafts draft
JOIN lead_workstreams ws ON ws.id = draft.workstream_id
WHERE draft.research_id IS NOT NULL
GROUP BY ws.workstream_type
ORDER BY ws.workstream_type;

WITH latest_research AS (
    SELECT DISTINCT ON (workstream_id)
           workstream_id,
           COALESCE(NULLIF(message_readiness_json ->> 'code', ''), 'missing_code') AS readiness_code
    FROM lead_workstream_research
    ORDER BY workstream_id, researched_at DESC, created_at DESC
),
latest_job AS (
    SELECT DISTINCT ON (workstream_id)
           workstream_id,
           status,
           NULLIF(result_json ->> 'draft_id', '') AS result_draft_id
    FROM lead_enrichment_jobs
    ORDER BY workstream_id, created_at DESC
),
draft_rollup AS (
    SELECT workstream_id,
           COUNT(*) AS draft_count,
           COUNT(*) FILTER (WHERE research_id IS NOT NULL) AS sourced_draft_count,
           COUNT(*) FILTER (WHERE quality_gate_json ->> 'passed' = 'true') AS passed_draft_count
    FROM outreachmessagedrafts
    GROUP BY workstream_id
)
SELECT ws.workstream_type,
       COUNT(*) FILTER (WHERE latest_research.readiness_code = 'ready') AS research_ready,
       COUNT(*) FILTER (
           WHERE latest_research.readiness_code = 'ready'
             AND COALESCE(draft_rollup.draft_count, 0) > 0
       ) AS research_ready_with_any_draft,
       COUNT(*) FILTER (
           WHERE latest_research.readiness_code = 'ready'
             AND COALESCE(draft_rollup.sourced_draft_count, 0) > 0
       ) AS research_ready_with_sourced_draft,
       COUNT(*) FILTER (
           WHERE latest_research.readiness_code = 'ready'
             AND COALESCE(draft_rollup.draft_count, 0) = 0
       ) AS research_ready_without_draft,
       COUNT(*) FILTER (
           WHERE latest_research.readiness_code <> 'ready'
             AND latest_job.status = 'ready'
       ) AS nonready_research_with_ready_job,
       COUNT(*) FILTER (
           WHERE latest_job.status = 'ready'
             AND latest_job.result_draft_id IS NULL
       ) AS ready_job_without_result_draft_id,
       COUNT(*) FILTER (
           WHERE latest_job.status = 'ready'
             AND COALESCE(draft_rollup.passed_draft_count, 0) = 0
       ) AS ready_job_without_passed_draft
FROM lead_workstreams ws
LEFT JOIN latest_research ON latest_research.workstream_id = ws.id
LEFT JOIN latest_job ON latest_job.workstream_id = ws.id
LEFT JOIN draft_rollup ON draft_rollup.workstream_id = ws.id
GROUP BY ws.workstream_type
ORDER BY ws.workstream_type;

WITH latest_research AS (
    SELECT DISTINCT ON (workstream_id)
           workstream_id,
           COALESCE(NULLIF(message_readiness_json ->> 'code', ''), 'missing_code') AS readiness_code,
           researched_at
    FROM lead_workstream_research
    ORDER BY workstream_id, researched_at DESC, created_at DESC
),
latest_job AS (
    SELECT DISTINCT ON (workstream_id)
           workstream_id,
           status,
           NULLIF(result_json ->> 'draft_id', '') AS result_draft_id,
           updated_at
    FROM lead_enrichment_jobs
    ORDER BY workstream_id, created_at DESC
),
draft_rollup AS (
    SELECT workstream_id,
           COUNT(*) FILTER (WHERE quality_gate_json ->> 'passed' = 'true') AS passed_draft_count
    FROM outreachmessagedrafts
    GROUP BY workstream_id
)
SELECT ws.workstream_type,
       latest_research.readiness_code,
       latest_job.status AS job_status,
       latest_research.researched_at::date AS research_date,
       latest_job.updated_at::date AS job_date,
       COUNT(*) AS workstreams
FROM lead_workstreams ws
JOIN latest_research ON latest_research.workstream_id = ws.id
JOIN latest_job ON latest_job.workstream_id = ws.id
LEFT JOIN draft_rollup ON draft_rollup.workstream_id = ws.id
WHERE latest_job.status = 'ready'
  AND (
      latest_job.result_draft_id IS NULL
      OR COALESCE(draft_rollup.passed_draft_count, 0) = 0
      OR latest_research.readiness_code <> 'ready'
  )
GROUP BY ws.workstream_type,
         latest_research.readiness_code,
         latest_job.status,
         latest_research.researched_at::date,
         latest_job.updated_at::date
ORDER BY ws.workstream_type, workstreams DESC, research_date, job_date;

SELECT workstream_type,
       CASE WHEN client_business_id IS NULL THEN 'platform' ELSE 'business' END AS scope_type,
       COUNT(*) AS active_profiles,
       COUNT(*) FILTER (WHERE confirmed_at IS NOT NULL) AS confirmed_profiles,
       COUNT(*) FILTER (WHERE NULLIF(BTRIM(competence_story), '') IS NOT NULL) AS with_story,
       COUNT(*) FILTER (
           WHERE jsonb_typeof(COALESCE(proof_points_json, '[]'::jsonb)) = 'array'
             AND jsonb_array_length(COALESCE(proof_points_json, '[]'::jsonb)) > 0
       ) AS with_proof,
       COUNT(*) FILTER (
           WHERE jsonb_typeof(COALESCE(verified_cases_json, '[]'::jsonb)) = 'array'
             AND jsonb_array_length(COALESCE(verified_cases_json, '[]'::jsonb)) > 0
       ) AS with_cases,
       COUNT(*) FILTER (
           WHERE jsonb_typeof(COALESCE(allowed_offers_json, '[]'::jsonb)) = 'array'
             AND jsonb_array_length(COALESCE(allowed_offers_json, '[]'::jsonb)) > 0
       ) AS with_offer,
       COUNT(*) FILTER (
           WHERE jsonb_typeof(COALESCE(voice_examples_json, '[]'::jsonb)) = 'array'
             AND jsonb_array_length(COALESCE(voice_examples_json, '[]'::jsonb)) > 0
       ) AS with_voice,
       COUNT(*) FILTER (
           WHERE jsonb_typeof(COALESCE(forbidden_claims_json, '[]'::jsonb)) = 'array'
             AND jsonb_array_length(COALESCE(forbidden_claims_json, '[]'::jsonb)) > 0
       ) AS with_forbidden_claims
FROM outreach_sender_profiles
WHERE is_active = TRUE
GROUP BY workstream_type, scope_type
ORDER BY workstream_type, scope_type;

SELECT scope_type,
       channel,
       status,
       outreach_enabled,
       COALESCE(capabilities_json ->> 'direct_send', 'false') AS direct_send,
       COALESCE(capabilities_json ->> 'reply_sync', 'false') AS reply_sync,
       COALESCE(health_status, 'unknown') AS health_status,
       COUNT(*) AS sender_accounts
FROM outreach_sender_accounts
GROUP BY scope_type,
         channel,
         status,
         outreach_enabled,
         direct_send,
         reply_sync,
         health_status
ORDER BY scope_type, channel, status, outreach_enabled;

SELECT account.is_active,
       COALESCE(permission.radar_enabled, TRUE) AS radar_enabled,
       COALESCE(permission.outreach_enabled, FALSE) AS outreach_enabled,
       COUNT(*) AS telegram_accounts
FROM externalbusinessaccounts account
LEFT JOIN telegram_account_permissions permission ON permission.account_id = account.id
WHERE account.source = 'telegram_app'
GROUP BY account.is_active,
         COALESCE(permission.radar_enabled, TRUE),
         COALESCE(permission.outreach_enabled, FALSE)
ORDER BY account.is_active DESC, radar_enabled DESC, outreach_enabled DESC;

SELECT scope_type,
       status,
       COUNT(*) AS campaigns
FROM outreach_campaigns
GROUP BY scope_type, status
ORDER BY scope_type, status;

SELECT channel,
       status,
       COUNT(*) AS touches
FROM outreach_campaign_touches
GROUP BY channel, status
ORDER BY channel, status;
