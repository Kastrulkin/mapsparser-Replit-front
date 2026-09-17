import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  RIDERRA_AUTHORIZATION_REFERENCE,
  RIDERRA_BUSINESS_ID,
  RIDERRA_SENDER_ACCOUNT_ID,
  RIDERRA_SENDER_IDENTITY,
  parseRiderraRecords,
  previewRiderraRecord,
} from './riderraTemplateContract';
import { RiderraTemplateSettings } from './RiderraTemplateSettings';

const auth = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  getCurrentUserSync: vi.fn(),
  makeRequest: vi.fn(),
}));

vi.mock('@/lib/auth_new', () => ({ newAuth: auth }));

const admin = { id: 'admin', email: 'admin@example.test', is_superadmin: true };
const hash = 'a'.repeat(64);

const snapshot = JSON.stringify({
  spreadsheet_id: '17YqqHe0TgDvUgXDNq0FeYe7113R2LTZza4musWLjEUo',
  sheet: 'Актуальный полный',
  evidence_kind: 'provider_observed',
  provider: 'Google Sheets via configured Google Drive connector',
  verified_at: '2026-09-09T07:00:00+00:00',
  ranges: [{ range: "'Актуальный полный'!A1:G1", values: [[]] }],
});

const member = {
  audience: 'transfer_buyer',
  lead_id: 'lead-1',
  workstream_id: 'workstream-1',
  contact_point_id: 'contact-1',
  recipient: 'buyer@example.test',
  company: 'Malaca Instituto',
  city: 'Malaga',
  opening: '',
  opening_source_url: '',
  opening_variant: 'no_opening_v1',
  source_fact_fingerprint: `facts:${'b'.repeat(64)}`,
  content_sha256: 'c'.repeat(64),
  pricebook: {
    spreadsheet_id: '17YqqHe0TgDvUgXDNq0FeYe7113R2LTZza4musWLjEUo',
    sheet: 'Актуальный полный',
    row: 1710,
    route: 'Malaga Airport (AGP) to a hotel in Malaga',
    vehicle: 'standard minivan',
    pax: 6,
    price: '€46',
    currency: 'EUR',
    source_row_sha256: 'd'.repeat(64),
    source_artifact_sha256: 'e'.repeat(64),
    source_version: 'e'.repeat(64),
  },
};

const recordsText = (record = member) => JSON.stringify({ records: [record] });

const serverManifest = (record = member) => {
  const selected = parseRiderraRecords(recordsText(record));
  const preview = previewRiderraRecord(selected[0]);
  return {
    business_id: RIDERRA_BUSINESS_ID,
    sender_account_id: RIDERRA_SENDER_ACCOUNT_ID,
    sender_identity: RIDERRA_SENDER_IDENTITY,
    daily_limit: 150,
    records_sha256: hash,
    records: [{ ...selected[0], subject: preview.subject, body: preview.body }],
  };
};

const props: {
  businessId: string;
  scopeType: 'business';
  senderAccountId: string;
  senderIdentity: string;
} = {
  businessId: RIDERRA_BUSINESS_ID,
  scopeType: 'business',
  senderAccountId: RIDERRA_SENDER_ACCOUNT_ID,
  senderIdentity: RIDERRA_SENDER_IDENTITY,
};

const requestBody = (options?: RequestInit) => (
  typeof options?.body === 'string' ? JSON.parse(options.body) : {}
);

const setupReadyStatus = (authorization = {}) => {
  auth.makeRequest.mockImplementation((endpoint: string, options?: RequestInit) => {
    if (endpoint.endsWith('/riderra-template-authorization') && !options?.method) {
      return Promise.resolve({ success: true, authorization });
    }
    return Promise.reject(new Error(`Unexpected request: ${endpoint}`));
  });
};

const openAndUpload = async (record = member) => {
  await screen.findByText('Согласованный шаблон Riderra');
  await userEvent.click(screen.getByRole('button', { name: 'Проверить и включить' }));
  await userEvent.click(screen.getByText('Администратору: загрузить проверенные JSON'));
  await userEvent.upload(
    screen.getByLabelText('Тарифы · snapshot005 JSON'),
    new File([snapshot], 'snapshot005.json', { type: 'application/json' }),
  );
  await userEvent.upload(
    screen.getByLabelText('Проверенные компании · JSON members'),
    new File([recordsText(record)], 'members.json', { type: 'application/json' }),
  );
  await screen.findByText(`${record.company} | Riderra | ${record.city} airport transfers`);
};

describe('RiderraTemplateSettings', () => {
  beforeEach(() => {
    auth.getCurrentUser.mockReset();
    auth.getCurrentUserSync.mockReset();
    auth.makeRequest.mockReset();
    auth.getCurrentUser.mockResolvedValue(admin);
    auth.getCurrentUserSync.mockReturnValue(admin);
    setupReadyStatus();
  });

  it('shows only for a freshly authenticated superadmin in the exact business and sender scope', async () => {
    const view = render(<RiderraTemplateSettings {...props} />);
    expect(await screen.findByText('До 150 подготовленных компаний в день.', { exact: false })).toBeVisible();

    view.rerender(<RiderraTemplateSettings {...props} businessId="another-business" />);
    expect(screen.queryByText('Согласованный шаблон Riderra')).not.toBeInTheDocument();

    auth.getCurrentUser.mockResolvedValue({ id: 'user', email: 'user@example.test', is_superadmin: false });
    auth.getCurrentUserSync.mockReturnValue({ id: 'user', email: 'user@example.test', is_superadmin: false });
    view.rerender(<RiderraTemplateSettings {...props} key="ordinary-user" />);
    await waitFor(() => expect(screen.queryByText('Согласованный шаблон Riderra')).not.toBeInTheDocument());
  });

  it('clears the private preview immediately when the business scope changes', async () => {
    const view = render(<RiderraTemplateSettings {...props} />);
    await openAndUpload();
    expect(screen.getByText('Malaca Instituto | Riderra | Malaga airport transfers')).toBeVisible();
    view.rerender(<RiderraTemplateSettings {...props} businessId="another-business" />);
    expect(screen.queryByText('Malaca Instituto | Riderra | Malaga airport transfers')).not.toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('clears the private preview and aborts approval when logout clears storage', async () => {
    let finishAttestation = (_value: unknown) => undefined;
    const pendingAttestation = new Promise((resolve) => {
      finishAttestation = resolve;
    });
    auth.makeRequest.mockImplementation((endpoint: string, options?: RequestInit) => {
      if (!options?.method) return Promise.resolve({ success: true, authorization: {} });
      if (endpoint.endsWith('/riderra-pricebook-attestations')) return pendingAttestation;
      return Promise.reject(new Error('Approval must stop after logout'));
    });
    render(<RiderraTemplateSettings {...props} />);
    await openAndUpload();
    await userEvent.click(screen.getByRole('button', { name: 'Разрешить эту группу по согласованному шаблону' }));
    window.dispatchEvent(new StorageEvent('storage', { key: null, oldValue: null, newValue: null }));
    finishAttestation({ success: true, pricebook_attestation: { id: 'receipt-1' }, external_dispatch_performed: false });

    await waitFor(() => expect(screen.queryByText('Malaca Instituto | Riderra | Malaga airport transfers')).not.toBeInTheDocument());
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.queryByText('Согласованный шаблон Riderra')).not.toBeInTheDocument();
    expect(auth.makeRequest.mock.calls.filter((call) => call[1]?.method === 'PATCH')).toHaveLength(0);
  });

  it('previews text safely and performs attestation, exact challenge, then one final approval', async () => {
    let patchCount = 0;
    const manifest = serverManifest();
    auth.makeRequest.mockImplementation((endpoint: string, options?: RequestInit) => {
      if (!options?.method) return Promise.resolve({ success: true, authorization: {} });
      if (endpoint.endsWith('/riderra-pricebook-attestations')) {
        return Promise.resolve({ success: true, pricebook_attestation: { id: 'receipt-1' }, external_dispatch_performed: false });
      }
      patchCount += 1;
      if (patchCount === 1) {
        return Promise.reject({ details: { error: 'exact_riderra_manifest_approval_required', manifest } });
      }
      return Promise.resolve({
        success: true,
        authorization: { state: 'active', manifest },
        external_dispatch_performed: false,
      });
    });

    render(<RiderraTemplateSettings {...props} />);
    await openAndUpload();
    expect(auth.makeRequest).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/I'm Alex from Riderra/)).toBeVisible();
    expect(document.querySelector('script')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Разрешить эту группу по согласованному шаблону' }));

    expect(await screen.findByText(/Группа из 1 компаний разрешена/)).toBeVisible();
    const mutationCalls = auth.makeRequest.mock.calls.filter((call) => call[1]?.method);
    expect(mutationCalls).toHaveLength(3);
    expect(requestBody(mutationCalls[0][1]).evidence_reference).toBe('authenticated_settings:riderra-pricebook-snapshot005');
    expect(requestBody(mutationCalls[1][1]).approved_manifest_sha256).toBe('');
    expect(requestBody(mutationCalls[2][1])).toMatchObject({
      authorization_reference: RIDERRA_AUTHORIZATION_REFERENCE,
      approved_manifest_sha256: hash,
      enabled: true,
    });
    expect(auth.makeRequest.mock.calls.some((call) => /\/queue|\/dispatch|\/send(?:\/|$)/.test(String(call[0])))).toBe(false);
  });

  it('fails closed if the selection changes while the attestation is pending', async () => {
    let finishAttestation = (_value: unknown) => undefined;
    const pendingAttestation = new Promise((resolve) => {
      finishAttestation = resolve;
    });
    auth.makeRequest.mockImplementation((endpoint: string, options?: RequestInit) => {
      if (!options?.method) return Promise.resolve({ success: true, authorization: {} });
      if (endpoint.endsWith('/riderra-pricebook-attestations')) return pendingAttestation;
      return Promise.reject(new Error('Approval challenge must not be reached'));
    });

    render(<RiderraTemplateSettings {...props} />);
    await openAndUpload();
    await userEvent.click(screen.getByRole('button', { name: 'Разрешить эту группу по согласованному шаблону' }));
    const membersInput = screen.getByLabelText('Проверенные компании · JSON members');
    fireEvent.change(membersInput, { target: { files: [new File([recordsText()], 'changed.json')] } });
    finishAttestation({ success: true, pricebook_attestation: { id: 'receipt-1' }, external_dispatch_performed: false });

    expect(await screen.findByRole('alert')).toHaveTextContent('Выбор изменился');
    expect(auth.makeRequest.mock.calls.filter((call) => call[1]?.method === 'PATCH')).toHaveLength(0);
  });

  it('rejects a server manifest with a changed recipient before final approval', async () => {
    const manifest = serverManifest();
    manifest.records[0].recipient = 'other@example.test';
    auth.makeRequest.mockImplementation((endpoint: string, options?: RequestInit) => {
      if (!options?.method) return Promise.resolve({ success: true, authorization: {} });
      if (endpoint.endsWith('/riderra-pricebook-attestations')) {
        return Promise.resolve({ success: true, pricebook_attestation: { id: 'receipt-1' }, external_dispatch_performed: false });
      }
      return Promise.reject({ details: { error: 'exact_riderra_manifest_approval_required', manifest } });
    });

    render(<RiderraTemplateSettings {...props} />);
    await openAndUpload();
    await userEvent.click(screen.getByRole('button', { name: 'Разрешить эту группу по согласованному шаблону' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Серверная запись 1 изменилась');
    expect(auth.makeRequest.mock.calls.filter((call) => call[1]?.method === 'PATCH')).toHaveLength(1);
  });

  it('keeps the mobile dialog usable and disables approval for empty or invalid input', async () => {
    render(<RiderraTemplateSettings {...props} />);
    await screen.findByText('Согласованный шаблон Riderra');
    await userEvent.click(screen.getByRole('button', { name: 'Проверить и включить' }));
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveClass('w-[calc(100vw-2rem)]', 'max-h-[90vh]', 'overflow-y-auto');
    expect(screen.getByRole('button', { name: 'Разрешить эту группу по согласованному шаблону' })).toBeDisabled();

    await userEvent.click(screen.getByText('Администратору: загрузить проверенные JSON'));
    await userEvent.upload(
      screen.getByLabelText('Проверенные компании · JSON members'),
      new File(['[]'], 'empty.json', { type: 'application/json' }),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('от 1 до 150');
  });

  it('keeps actions disabled when the protected status request fails', async () => {
    auth.makeRequest.mockRejectedValue(new Error('network unavailable'));
    render(<RiderraTemplateSettings {...props} />);

    expect(await screen.findByText('Не удалось проверить статус. Действия недоступны.')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Проверить и включить' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeEnabled();
  });

  it('requires a separate confirmation before revoking an active authorization', async () => {
    setupReadyStatus({ state: 'active', manifest: serverManifest() });
    auth.makeRequest.mockImplementation((endpoint: string, options?: RequestInit) => {
      if (!options?.method) return Promise.resolve({ success: true, authorization: { state: 'active', manifest: serverManifest() } });
      return Promise.resolve({ success: true, authorization: { state: 'revoked' }, external_dispatch_performed: false });
    });
    render(<RiderraTemplateSettings {...props} />);

    await screen.findByText('Разрешён · 1');
    await userEvent.click(screen.getByRole('button', { name: 'Проверить или добавить' }));
    await userEvent.click(screen.getByRole('button', { name: 'Отозвать разрешение' }));
    expect(auth.makeRequest.mock.calls.filter((call) => call[1]?.method === 'PATCH')).toHaveLength(0);
    await userEvent.click(screen.getByRole('button', { name: 'Подтвердить отзыв' }));

    expect(await screen.findByText(/Разрешение отозвано/)).toBeVisible();
    const patchCalls = auth.makeRequest.mock.calls.filter((call) => call[1]?.method === 'PATCH');
    expect(patchCalls).toHaveLength(1);
    expect(requestBody(patchCalls[0][1])).toMatchObject({
      enabled: false,
      authorization_reference: RIDERRA_AUTHORIZATION_REFERENCE,
      records: [],
    });
  });

  it('offers a safe retry when fresh auth temporarily fails but the cached admin session remains', async () => {
    auth.getCurrentUser.mockResolvedValue(null);
    auth.getCurrentUserSync.mockReturnValue(admin);
    render(<RiderraTemplateSettings {...props} />);

    expect(await screen.findByText('Не удалось проверить статус. Действия недоступны.')).toBeVisible();
    expect(auth.makeRequest).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeEnabled();
  });
});
