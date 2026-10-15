import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { HumanResultView } from './runs';
import { extractBusinessResultPayload } from './results';
import { MapCardReport } from './map-card-report';

vi.mock('@/services/api', () => ({ api: { get: vi.fn().mockResolvedValue({ data: { progress: { revision: 0, platforms: {} } } }) } }));

const cards = [{ provider: 'google', label: 'Google', fields: [{ field: 'name', title: 'Название', proposed: 'Мелиора' }], checks: [{ field: 'address', rule_id: 'google.address', title: 'Адрес', state: 'unknown', official_url: 'https://support.google.com/business/answer/3038177' }] }, { provider: 'yandex', label: 'Яндекс', checks: [] }];
const report = { schema: 'map_card_report_v1', kind: 'preparation', summary: 'Пакет подготовлен', cards };

describe('Readable saved map results', () => {
  it('preserves the report contract when the input is a direct saved result', () => {
    const value = extractBusinessResultPayload(report);
    expect(value?.schema).toBe('map_card_report_v1');
    expect(value?.cards).toEqual(cards);
    expect(extractBusinessResultPayload(JSON.stringify(report))?.cards).toEqual(cards);
    expect(extractBusinessResultPayload({ artifact: { result: report } })?.schema).toBe('map_card_report_v1');
  });
  it('routes legacy map results to the map view instead of flattening cards and field names', () => {
    render(<HumanResultView result={{ summary: 'Пакет подготовлен', kind: 'preparation', cards }} runId="legacy-run" />);
    expect(screen.getByRole('region', { name: 'Результат работы с карточками' })).toBeVisible();
    expect(screen.queryByText(/official_url:|cards:|proposed:/)).not.toBeInTheDocument();
  });
  it('opens the wizard from a wrapped canonical history result instead of the generic renderer', async () => {
    render(<HumanResultView result={{ result: report }} runId="meliora-run" />);
    expect(await screen.findByRole('heading', { name: 'Оформить карточки по шагам' })).toBeVisible();
    expect(screen.queryByText(/official_url:|cards:|proposed:/)).not.toBeInTheDocument();
  });
  it('shows one platform at a time and keeps source details out of the default view', () => {
    render(<MapCardReport result={report} />);
    expect(screen.getByRole('button', { name: 'Google' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('heading', { name: 'Google' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Яндекс' }));
    expect(screen.getByRole('heading', { name: 'Яндекс' })).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Google' })).not.toBeInTheDocument();
  });
  it('never prints arbitrary nested editorial objects or photo tokens as a paragraph', () => {
    render(<MapCardReport result={{ ...report, editorial: { summary: 'Предложения', items: [{ platform: 'Google', fields: { description: 'Текст для проверки', photos: ['https://localos.pro/photo?token=secret'], internal_key: { field: 'name', official_url: 'https://example.org' } } }] } }} />);
    expect(screen.queryByText(/token=secret|internal_key|official_url/)).not.toBeInTheDocument();
  });
});
