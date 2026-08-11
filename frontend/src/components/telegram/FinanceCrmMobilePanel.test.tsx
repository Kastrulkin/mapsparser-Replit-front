import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import FinanceCrmMobilePanel from './FinanceCrmMobilePanel';

describe('FinanceCrmMobilePanel', () => {
  it('explains the generic CRM file flow without assuming a provider', async () => {
    const { container } = render(<FinanceCrmMobilePanel onOpenFileImport={vi.fn()} onRequestCrm={vi.fn().mockResolvedValue(undefined)} />);

    expect(screen.getByText('Загрузить данные из CRM')).toBeVisible();
    expect(screen.getByText('Через файл')).toBeVisible();
    expect(screen.queryByText(/partner token/i)).not.toBeInTheDocument();
    expect(container).not.toHaveTextContent('YCLIENTS');

    await userEvent.click(screen.getByRole('button', { name: /Как выгрузить файл/ }));

    expect(screen.getByText(/раздел с продажами/)).toBeInTheDocument();
    expect(screen.getByText(/Выберите CSV или Excel/)).toBeInTheDocument();
    expect(screen.getByText(/сопоставьте их вручную/)).toBeInTheDocument();
  });

  it('opens file import and creates a structured CRM request', async () => {
    const onOpenFileImport = vi.fn();
    const onRequestCrm = vi.fn().mockResolvedValue(undefined);
    render(<FinanceCrmMobilePanel onOpenFileImport={onOpenFileImport} onRequestCrm={onRequestCrm} />);

    await userEvent.click(screen.getByRole('button', { name: 'Загрузить файл из CRM' }));
    expect(onOpenFileImport).toHaveBeenCalledOnce();

    await userEvent.click(screen.getByRole('button', { name: 'Заказать подключение' }));
    await userEvent.type(screen.getByLabelText('Название CRM'), 'Bitrix24');
    await userEvent.type(screen.getByLabelText(/Что хотите загружать/), 'Продажи за месяц');
    await userEvent.click(screen.getByRole('button', { name: 'Отправить запрос' }));

    expect(onRequestCrm).toHaveBeenCalledWith({ crmName: 'Bitrix24', crmUrl: '', contact: '', comment: 'Продажи за месяц' });
    expect(await screen.findByRole('status')).toHaveTextContent('Запрос отправлен');
  });

  it('shows an honest error and keeps the form available', async () => {
    const onRequestCrm = vi.fn().mockRejectedValue(new Error('Сервис временно недоступен'));
    render(<FinanceCrmMobilePanel onOpenFileImport={vi.fn()} onRequestCrm={onRequestCrm} />);

    await userEvent.click(screen.getByRole('button', { name: 'Заказать подключение' }));
    await userEvent.type(screen.getByLabelText('Название CRM'), 'amoCRM');
    await userEvent.click(screen.getByRole('button', { name: 'Отправить запрос' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Сервис временно недоступен');
    expect(screen.getByLabelText('Название CRM')).toHaveValue('amoCRM');
  });
});
