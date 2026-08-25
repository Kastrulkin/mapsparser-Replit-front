COPY (
    SELECT business.name AS business,
           lead.name AS partner,
           workstream.lifecycle_status,
           workstream.status,
           workstream.status_reason,
           workstream.next_step
    FROM lead_workstreams workstream
    JOIN prospectingleads lead ON lead.id = workstream.lead_id
    JOIN businesses business ON business.id = workstream.client_business_id
    WHERE workstream.workstream_type = 'client_partnership'
      AND workstream.client_business_id IN (
          'cb674174-8b3d-41a3-8277-525c849935f2',
          '360b90ef-cf2b-4eb4-acd4-a8524e4600ae'
      )
      AND workstream.lifecycle_status <> 'needs_review'
    ORDER BY business.name, workstream.lifecycle_status, lead.name
) TO STDOUT WITH (FORMAT CSV, HEADER TRUE);
