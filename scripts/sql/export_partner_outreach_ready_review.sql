COPY (
    WITH latest_campaign AS (
        SELECT DISTINCT ON (campaign.workstream_id)
               campaign.id,
               campaign.workstream_id,
               campaign.business_id,
               campaign.version,
               campaign.room_id
        FROM outreach_campaigns campaign
        WHERE campaign.status = 'draft'
          AND campaign.policy_json ->> 'generation_rules_version' = 'partner_first_touch_human_v1'
        ORDER BY campaign.workstream_id, campaign.version DESC
    )
    SELECT business.name AS business,
           lead.name AS partner,
           touch.channel,
           contact.value AS recipient,
           touch.subject,
           touch.generated_text AS message,
           (touch.quality_gate_json ->> 'total_score')::integer AS quality_score,
           touch.status AS touch_status,
           'https://localos.pro/room/' || room.slug AS room_url,
           latest_campaign.id AS campaign_id
    FROM latest_campaign
    JOIN outreach_campaign_touches touch ON touch.campaign_id = latest_campaign.id
    JOIN lead_workstreams workstream ON workstream.id = latest_campaign.workstream_id
    JOIN prospectingleads lead ON lead.id = workstream.lead_id
    JOIN businesses business ON business.id = latest_campaign.business_id
    JOIN lead_contact_points contact ON contact.id = touch.contact_point_id
    LEFT JOIN sales_rooms room ON room.id = latest_campaign.room_id
    ORDER BY business.name, lead.name
) TO STDOUT WITH (FORMAT CSV, HEADER TRUE);
