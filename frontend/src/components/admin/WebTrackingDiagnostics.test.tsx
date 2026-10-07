import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { WebTrackingDiagnostics } from './WebTrackingDiagnostics';


vi.mock('@/lib/auth_new', () => ({
  newAuth: { makeRequest: vi.fn() },
}));

describe('WebTrackingDiagnostics', () => {
  beforeEach(() => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      success: true,
      trackers: { trackers: 1, active_trackers: 1, active_last_24h: 1, never_seen: 0 },
      events: { events_1h: 12, events_24h: 84, trackers_24h: 1, latest_ingested_at: '2026-08-16T12:00:00Z' },
      storage: { events_total_bytes: 2048, events_table_bytes: 1024, events_indexes_bytes: 1024, metrics_total_bytes: 1024 },
      versions: [{ tracker_version: '1.1.0', schema_version: 2, events: 84 }],
      tracker_diagnostics: [{
        public_tracker_id: 'pub_safe_tracker_id',
        business_id: 'business-1',
        business_name: 'Тестовый бизнес',
        allowed_domains: ['example.com'],
        enabled: true,
        tracking_enabled: true,
        first_event_at: '2026-08-16T10:00:00Z',
        last_event_at: '2026-08-16T12:00:00Z',
        last_tracker_version: '1.1.0',
        last_schema_version: 2,
        last_error_code: null,
        last_error_at: null,
        events_1h: 12,
        events_24h: 84,
      }],
      maintenance: [{
        started_at: '2026-08-16T11:00:00Z',
        finished_at: '2026-08-16T11:00:01Z',
        dry_run: true,
        status: 'completed',
        aggregate_date: '2026-08-15',
        metrics_rows: 5,
        raw_events: 84,
        aggregate_events: 84,
        eligible_events: 0,
        eligible_metrics: 0,
        deleted_events: 0,
        deleted_metrics: 0,
        deleted_sessions: 0,
        deleted_visitors: 0,
        error_code: null,
      }],
      ingestion: {
        available: true,
        window_minutes: 60,
        requests: 15,
        events_received: 96,
        accepted: 84,
        duplicates: 12,
        rejected_requests: 2,
        responses_2xx: 13,
        responses_4xx: 2,
        responses_5xx: 0,
        p50_ms: 50,
        p95_ms: 100,
        p99_ms: 250,
      },
    });
  });

  it('shows operational status without exposing page or form contents', async () => {
    render(<WebTrackingDiagnostics />);

    expect(await screen.findByText('Тестовый бизнес')).toBeInTheDocument();
    expect(screen.getByText('example.com')).toBeInTheDocument();
    expect(screen.getByText('raw / aggregate:')).toBeInTheDocument();
    expect(screen.getByText('Ошибок нет')).toBeInTheDocument();
    expect(screen.getByText('100 мс')).toBeInTheDocument();
    expect(screen.getByText('84')).toBeInTheDocument();
    expect(screen.queryByText(/input|textarea|form value/i)).not.toBeInTheDocument();
    expect(newAuth.makeRequest).toHaveBeenCalledWith('/admin/web-tracking/health');
  });
});
