import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { TodayMobileV2 } from './TodayMobileV2';

describe('TodayMobileV2', () => {
  it('keeps the ЛокалОС assignment field visible in Russian', () => {
    render(
      <TodayMobileV2
        data={{ scope: { kind: 'business', id: 'business-1', name: 'Тестовый бизнес' } }}
        loading={false}
        slowLoading={false}
        command=""
        setCommand={vi.fn()}
        ask={vi.fn()}
        openTarget={vi.fn()}
        openProgress={vi.fn()}
        track={vi.fn()}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Поручить ЛокалОС' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Например: подготовь ответы')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Поручить ЛокалОС' })).not.toBeInTheDocument();
  });
});
