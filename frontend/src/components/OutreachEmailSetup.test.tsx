import '@testing-library/jest-dom/vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { readFileSync } from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { newAuth } from '@/lib/auth_new';

import { OutreachEmailSetup } from './OutreachEmailSetup';

vi.mock('@/lib/auth_new', () => ({
  newAuth: { makeRequest: vi.fn() },
}));

const makeRequest = vi.mocked(newAuth.makeRequest);
const accountList = { success: true, sender_accounts: [] };

const fillRequiredMailbox = async () => {
  await userEvent.type(await screen.findByLabelText('Email отправителя'), 'owner@example.test');
  await userEvent.type(screen.getByLabelText('Пароль приложения'), 'app-password');
  await userEvent.type(screen.getByLabelText('SMTP-сервер'), 'smtp.example.test');
  await userEvent.type(screen.getByLabelText('IMAP-сервер'), 'imap.example.test');
};

describe('OutreachEmailSetup state lifecycle', () => {
  beforeEach(() => {
    makeRequest.mockReset();
    makeRequest.mockResolvedValue(accountList);
  });

  it('keeps the in-memory form, details, permission and preflight result across tabs', async () => {
    render(
      <Tabs defaultValue="setup">
        <TabsList>
          <TabsTrigger value="setup">Настройка</TabsTrigger>
          <TabsTrigger value="support">Для поддержки</TabsTrigger>
        </TabsList>
        <TabsContent value="setup" forceMount className="data-[state=inactive]:hidden">
          <OutreachEmailSetup businessId="business-1" compact />
        </TabsContent>
        <TabsContent value="support">Диагностика</TabsContent>
      </Tabs>,
    );

    await fillRequiredMailbox();
    const details = screen.getByText('Серверы отправки и входящих писем').closest('details');
    expect(details).not.toBeNull();
    await userEvent.click(screen.getByText('Серверы отправки и входящих писем'));
    await userEvent.click(screen.getByRole('switch', { name: 'Разрешить отправку сообщений' }));
    await userEvent.click(screen.getByRole('button', { name: 'Проверить без отправки' }));
    expect(await screen.findByText('SMTP и проверка ответов работают. Письмо не отправлялось.')).toBeVisible();

    await userEvent.click(screen.getByRole('tab', { name: 'Для поддержки' }));
    const inactiveSetup = screen.getByLabelText('Пароль приложения').closest('[data-state="inactive"]');
    expect(inactiveSetup).toHaveClass('data-[state=inactive]:hidden');
    await userEvent.click(screen.getByRole('tab', { name: 'Настройка' }));

    expect(screen.getByLabelText('Email отправителя')).toHaveValue('owner@example.test');
    expect(screen.getByLabelText('Пароль приложения')).toHaveValue('app-password');
    expect(details).toHaveAttribute('open');
    expect(screen.getByRole('switch', { name: 'Разрешить отправку сообщений' })).toBeChecked();
    expect(screen.getByRole('button', { name: 'Подключить email' })).toBeEnabled();
  });

  it('clears all private setup state when the business changes', async () => {
    const view = render(<OutreachEmailSetup businessId="business-1" compact />);
    await fillRequiredMailbox();
    await userEvent.click(screen.getByText('Серверы отправки и входящих писем'));
    await userEvent.click(screen.getByRole('switch', { name: 'Разрешить отправку сообщений' }));
    await userEvent.click(screen.getByRole('button', { name: 'Проверить без отправки' }));
    await screen.findByText('SMTP и проверка ответов работают. Письмо не отправлялось.');

    view.rerender(<OutreachEmailSetup businessId="business-2" compact />);

    await waitFor(() => expect(screen.getByLabelText('Email отправителя')).toHaveValue(''));
    expect(screen.getByLabelText('Пароль приложения')).toHaveValue('');
    expect(screen.getByText('Серверы отправки и входящих писем').closest('details')).not.toHaveAttribute('open');
    expect(screen.getByRole('switch', { name: 'Разрешить отправку сообщений' })).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Подключить email' })).toBeDisabled();
  });

  it('ignores an in-flight preflight result after mailbox fields change', async () => {
    let finishPreflight: (() => void) | undefined;
    makeRequest.mockImplementation((url: string) => {
      if (url.includes('/email/preflight')) {
        return new Promise((resolve) => {
          finishPreflight = () => resolve({ success: true });
        });
      }
      return Promise.resolve(accountList);
    });
    render(<OutreachEmailSetup businessId="business-1" compact />);
    await fillRequiredMailbox();

    await userEvent.click(screen.getByRole('button', { name: 'Проверить без отправки' }));
    await userEvent.type(screen.getByLabelText('SMTP-сервер'), '.changed');
    await act(async () => finishPreflight?.());

    expect(screen.getByRole('button', { name: 'Подключить email' })).toBeDisabled();
    expect(screen.queryByText('SMTP и проверка ответов работают. Письмо не отправлялось.')).not.toBeInTheDocument();
  });

  it('locks setup edits while connect is pending, then clears and reloads after success', async () => {
    let finishConnect: (() => void) | undefined;
    let connected = false;
    const onChanged = vi.fn();
    const connectedAccount = {
      id: 'sender-1',
      channel: 'email',
      sender_identity: 'owner@example.test',
      display_name: 'Owner',
      status: 'connected',
      outreach_enabled: true,
      health_status: 'healthy',
      health_score: 100,
    };
    makeRequest.mockImplementation((url: string, options?: RequestInit) => {
      if (url.includes('/email/preflight')) return Promise.resolve({ success: true });
      if (url === '/outreach/sender-accounts/email' && options?.method === 'POST') {
        return new Promise((resolve) => {
          finishConnect = () => {
            connected = true;
            resolve({ success: true });
          };
        });
      }
      return Promise.resolve({ success: true, sender_accounts: connected ? [connectedAccount] : [] });
    });
    render(<OutreachEmailSetup businessId="business-1" compact onChanged={onChanged} />);
    await fillRequiredMailbox();
    await userEvent.click(screen.getByText('Серверы отправки и входящих писем'));
    await userEvent.click(screen.getByRole('switch', { name: 'Разрешить отправку сообщений' }));
    await userEvent.click(screen.getByRole('button', { name: 'Проверить без отправки' }));
    await screen.findByText('SMTP и проверка ответов работают. Письмо не отправлялось.');

    await userEvent.click(screen.getByRole('button', { name: 'Подключить email' }));

    expect(screen.getByLabelText('Email отправителя')).toBeDisabled();
    expect(screen.getByLabelText('SMTP-сервер')).toBeDisabled();
    expect(screen.getByLabelText('Защита', { selector: '#outreach-smtp-security' })).toBeDisabled();
    expect(screen.getByRole('switch', { name: 'Разрешить отправку сообщений' })).toBeDisabled();

    await act(async () => finishConnect?.());

    expect(await screen.findByText('Email подключён. LocalOS сможет отправлять только подтверждённые цепочки и остановит их после ответа.')).toBeVisible();
    expect(screen.getByText('owner@example.test')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Проверить без отправки' })).toBeEnabled();
    expect(onChanged).toHaveBeenCalledOnce();

    await userEvent.click(screen.getByRole('button', { name: 'Подключить другой email' }));
    expect(screen.getByLabelText('Email отправителя')).toHaveValue('');
    expect(screen.getByLabelText('Пароль приложения')).toHaveValue('');
    expect(screen.getByRole('switch', { name: 'Разрешить отправку сообщений' })).not.toBeChecked();
  });

  it('shows a named error stage after preflight failure', async () => {
    const failure = new Error('fallback');
    Reflect.set(failure, 'details', {
      error: 'IMAP недоступен',
      next_action: 'Проверьте пароль приложения.',
      stage: 'imap_auth',
      provider_status: 535,
      provider_reason: 'authentication_rejected',
    });
    makeRequest.mockImplementation((url: string) => {
      if (url.includes('/email/preflight')) return Promise.reject(failure);
      return Promise.resolve(accountList);
    });
    render(<OutreachEmailSetup businessId="business-1" compact />);
    await fillRequiredMailbox();

    await userEvent.click(screen.getByRole('button', { name: 'Проверить без отправки' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Проверка подключения не пройдена');
    expect(screen.getByRole('alert')).toHaveTextContent('IMAP недоступен');
    expect(screen.getByRole('alert')).toHaveTextContent('Что сделать: Проверьте пароль приложения.');
    expect(screen.getByRole('alert')).toHaveTextContent('Технически: вход в IMAP · код 535 · провайдер отклонил вход');
  });

  it('keeps the email setup mounted only while the integrations sheet remains open', () => {
    const source = readFileSync('src/pages/dashboard/settings/IntegrationsPageV3.tsx', 'utf8');
    const componentSource = readFileSync('src/components/OutreachEmailSetup.tsx', 'utf8');
    const tabsStart = source.indexOf('<Tabs defaultValue="setup"');
    const tabs = source.slice(tabsStart, source.indexOf('</Tabs>', tabsStart));

    expect(tabs).toContain('<TabsContent value="setup" forceMount className="space-y-4 data-[state=inactive]:hidden"');
    expect(source).toContain('if (!open) setActiveServiceId(null)');
    expect(source).toContain('{selectedService ? (\n          <Tabs defaultValue="setup"');
    expect(source).toContain('outreach_email: \'С этой почты LocalOS отправляет одобренные письма и проверяет ответы\'');
    expect(componentSource).not.toMatch(/localStorage|sessionStorage/);
  });
});
