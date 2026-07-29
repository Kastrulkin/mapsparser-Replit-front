import { act, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import MobileShell from './MobileShell';

describe('MobileShell', () => {
  it('shows a recoverable offline state without hiding loaded content', () => {
    render(<MobileShell header={<div>ЛокалОС</div>}><div>Загруженные задачи</div></MobileShell>);

    act(() => window.dispatchEvent(new Event('offline')));

    expect(screen.getByRole('status')).toHaveTextContent('Нет сети');
    expect(screen.getByText('Загруженные задачи')).toBeInTheDocument();
  });

  it('announces request errors', () => {
    render(<MobileShell header={<div>ЛокалОС</div>} error="Не удалось обновить данные"><div>Экран</div></MobileShell>);
    expect(screen.getByRole('alert')).toHaveTextContent('Не удалось обновить данные');
  });
});
