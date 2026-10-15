import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MapCardReport } from './map-card-report';

describe('MapCardReport', () => {
  it('shows missing visual evidence and does not turn model prose into a pass', () => {
    render(<MapCardReport result={{ schema: 'map_card_report_v1', summary: 'Проверка', cards: [{
      provider: 'yandex', label: 'Яндекс', visual_note: 'Внешний вид не проверен',
      url: 'https://yandex.ru/maps/org/123', checks: [],
    }], editorial: { summary: 'Всё готово' } }} />);
    expect(screen.getByRole('status')).toHaveTextContent('Недостаточно данных');
    expect(screen.getByRole('link', { name: 'Открыть карточку' })).toHaveAttribute('href', 'https://yandex.ru/maps/org/123');
    expect(screen.getByText('Внешний вид не проверен')).toBeVisible();
  });

  it('does not render untrusted executable links and explains missing sources', () => {
    render(<MapCardReport result={{ cards: [{ provider: 'google', label: 'Google', url: 'javascript:alert(1)', checks: [] }] }} />);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.getByText(/Подтвердите ссылку/)).toBeVisible();
  });

  it('labels a preview without claiming a real external read', () => {
    render(<MapCardReport result={{ preview: true, cards: [] }} />);
    expect(screen.getByRole('status')).toHaveTextContent('Внешние страницы и AI-провайдер не вызывались');
  });
});
