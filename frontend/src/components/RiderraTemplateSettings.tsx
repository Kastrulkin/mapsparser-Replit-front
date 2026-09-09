import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { CheckCircle2, FileCheck2, RefreshCw, ShieldCheck } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { newAuth } from '@/lib/auth_new';

import {
  RIDERRA_AUTHORIZATION_REFERENCE,
  RIDERRA_BUSINESS_ID,
  RIDERRA_DAILY_LIMIT,
  RIDERRA_SENDER_ACCOUNT_ID,
  RIDERRA_SENDER_IDENTITY,
  activeAuthorizationSummary,
  challengeManifest,
  cloneRiderraRecords,
  isJsonRecord,
  parseRiderraRecords,
  previewRiderraRecord,
  validateRiderraSnapshot,
  verifyRiderraManifest,
  type RiderraRecord,
} from './riderraTemplateContract';

type RiderraTemplateSettingsProps = {
  businessId?: string | null;
  scopeType?: 'business' | 'platform';
  senderAccountId?: string | null;
  senderIdentity?: string | null;
};

type AuthorizationSummary = {
  active: boolean;
  count: number;
};

const AUTHORIZATION_ENDPOINT = `/outreach/sender-accounts/${encodeURIComponent(RIDERRA_SENDER_ACCOUNT_ID)}/riderra-template-authorization`;
const ATTESTATION_ENDPOINT = `/outreach/sender-accounts/${encodeURIComponent(RIDERRA_SENDER_ACCOUNT_ID)}/riderra-pricebook-attestations`;

const errorCopy = (error: unknown, fallback: string) => {
  if (error instanceof Error && error.message) return error.message;
  return fallback;
};

const fileText = (file: File) => new Promise<string>((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : '');
  reader.onerror = () => reject(new Error('Не удалось прочитать JSON-файл.'));
  reader.readAsText(file);
});

const finalAuthorization = (value: unknown, expectedHash: string, expectedState: 'active' | 'revoked') => {
  if (!isJsonRecord(value) || value.external_dispatch_performed !== false || !isJsonRecord(value.authorization)) {
    throw new Error('Сервер не подтвердил безопасное изменение разрешения.');
  }
  if (value.authorization.state !== expectedState) {
    throw new Error('Статус разрешения не совпал с выбранным действием.');
  }
  if (expectedState === 'active') {
    if (!isJsonRecord(value.authorization.manifest) || value.authorization.manifest.records_sha256 !== expectedHash) {
      throw new Error('Сервер подтвердил другой состав группы.');
    }
  }
};

export const RiderraTemplateSettings = ({
  businessId = null,
  scopeType = 'business',
  senderAccountId = null,
  senderIdentity = null,
}: RiderraTemplateSettingsProps) => {
  const [accessState, setAccessState] = useState<'checking' | 'hidden' | 'ready' | 'error'>('checking');
  const [authorization, setAuthorization] = useState<AuthorizationSummary>({ active: false, count: 0 });
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [snapshotText, setSnapshotText] = useState('');
  const [snapshotName, setSnapshotName] = useState('');
  const [records, setRecords] = useState<RiderraRecord[]>([]);
  const [recordsName, setRecordsName] = useState('');
  const [previewIndex, setPreviewIndex] = useState(0);
  const [confirmRevoke, setConfirmRevoke] = useState(false);
  const [fileInputVersion, setFileInputVersion] = useState(0);
  const accessEpoch = useRef(0);
  const selectionEpoch = useRef(0);
  const snapshotReadEpoch = useRef(0);
  const recordsReadEpoch = useRef(0);

  const scopeMatches = (
    scopeType === 'business'
    && businessId === RIDERRA_BUSINESS_ID
    && senderAccountId === RIDERRA_SENDER_ACCOUNT_ID
    && senderIdentity?.trim().toLowerCase() === RIDERRA_SENDER_IDENTITY
  );

  const clearSelection = useCallback(() => {
    selectionEpoch.current += 1;
    snapshotReadEpoch.current += 1;
    recordsReadEpoch.current += 1;
    setSnapshotText('');
    setSnapshotName('');
    setRecords([]);
    setRecordsName('');
    setPreviewIndex(0);
    setConfirmRevoke(false);
    setFileInputVersion((current) => current + 1);
  }, []);

  const clearPrivateState = useCallback(() => {
    clearSelection();
    setAuthorization({ active: false, count: 0 });
    setOpen(false);
    setBusy('');
    setNotice('');
    setError('');
  }, [clearSelection]);

  const refreshAuthorization = useCallback(async () => {
    const requestEpoch = accessEpoch.current + 1;
    accessEpoch.current = requestEpoch;
    clearPrivateState();
    setAccessState('checking');
    if (!scopeMatches) {
      setAccessState('hidden');
      return;
    }

    try {
      const user = await newAuth.getCurrentUser();
      if (accessEpoch.current !== requestEpoch) return;
      if (!user) {
        const hadAuthenticatedAdmin = newAuth.getCurrentUserSync()?.is_superadmin === true;
        clearPrivateState();
        setAccessState(hadAuthenticatedAdmin ? 'error' : 'hidden');
        return;
      }
      if (user.is_superadmin !== true) {
        clearPrivateState();
        setAccessState('hidden');
        return;
      }
      const response: unknown = await newAuth.makeRequest(AUTHORIZATION_ENDPOINT);
      if (accessEpoch.current !== requestEpoch) return;
      setAuthorization(activeAuthorizationSummary(response));
      setAccessState('ready');
    } catch {
      if (accessEpoch.current !== requestEpoch) return;
      clearPrivateState();
      setAccessState(newAuth.getCurrentUserSync()?.is_superadmin === true ? 'error' : 'hidden');
    }
  }, [clearPrivateState, scopeMatches]);

  useEffect(() => {
    void refreshAuthorization();
    return () => {
      accessEpoch.current += 1;
      selectionEpoch.current += 1;
    };
  }, [refreshAuthorization]);

  useEffect(() => {
    const recheckAfterAuthChange = (event: StorageEvent) => {
      if ((event.key === 'auth_token' || event.key === null) && event.newValue === null) {
        accessEpoch.current += 1;
        clearPrivateState();
        setAccessState('hidden');
        return;
      }
      void refreshAuthorization();
    };
    window.addEventListener('storage', recheckAfterAuthChange);
    return () => window.removeEventListener('storage', recheckAfterAuthChange);
  }, [clearPrivateState, refreshAuthorization]);

  const currentPreview = useMemo(() => {
    const record = records[previewIndex];
    return record ? previewRiderraRecord(record) : null;
  }, [previewIndex, records]);

  const selectSnapshot = async (file: File | null) => {
    selectionEpoch.current += 1;
    if (busy || !file) return;
    const readEpoch = snapshotReadEpoch.current + 1;
    snapshotReadEpoch.current = readEpoch;
    setError('');
    setNotice('');
    setSnapshotText('');
    setSnapshotName('');
    try {
      const text = await fileText(file);
      if (snapshotReadEpoch.current !== readEpoch) return;
      validateRiderraSnapshot(text);
      setSnapshotText(text);
      setSnapshotName(file.name);
    } catch (requestError) {
      if (snapshotReadEpoch.current !== readEpoch) return;
      setError(errorCopy(requestError, 'Не удалось проверить snapshot005.'));
    }
  };

  const selectRecords = async (file: File | null) => {
    selectionEpoch.current += 1;
    if (busy || !file) return;
    const readEpoch = recordsReadEpoch.current + 1;
    recordsReadEpoch.current = readEpoch;
    setError('');
    setNotice('');
    setRecords([]);
    setRecordsName('');
    try {
      const text = await fileText(file);
      if (recordsReadEpoch.current !== readEpoch) return;
      const nextRecords = parseRiderraRecords(text);
      setRecords(nextRecords);
      setRecordsName(file.name);
      setPreviewIndex(0);
    } catch (requestError) {
      if (recordsReadEpoch.current !== readEpoch) return;
      setError(errorCopy(requestError, 'Не удалось проверить группу.'));
    }
  };

  const enableAuthorization = async () => {
    if (accessState !== 'ready' || busy || !snapshotText || records.length < 1) return;
    const requestAccessEpoch = accessEpoch.current;
    const requestSelectionEpoch = selectionEpoch.current;
    const selectedRecords = cloneRiderraRecords(records);
    const selectedSnapshotText = snapshotText;
    setBusy('enable');
    setError('');
    setNotice('');
    try {
      const user = await newAuth.getCurrentUser();
      if (!user || user.is_superadmin !== true) {
        clearPrivateState();
        setAccessState('hidden');
        return;
      }
      if (accessEpoch.current !== requestAccessEpoch || selectionEpoch.current !== requestSelectionEpoch) {
        throw new Error('Выбор изменился. Проверьте группу и подтвердите ещё раз.');
      }

      const attestationResponse: unknown = await newAuth.makeRequest(ATTESTATION_ENDPOINT, {
        method: 'POST',
        body: JSON.stringify({
          artifact_text: selectedSnapshotText,
          evidence_reference: 'authenticated_settings:riderra-pricebook-snapshot005',
        }),
      });
      if (
        !isJsonRecord(attestationResponse)
        || attestationResponse.external_dispatch_performed !== false
        || !isJsonRecord(attestationResponse.pricebook_attestation)
        || typeof attestationResponse.pricebook_attestation.id !== 'string'
      ) {
        throw new Error('Сервер не подтвердил snapshot005.');
      }
      if (accessEpoch.current !== requestAccessEpoch || selectionEpoch.current !== requestSelectionEpoch) {
        throw new Error('Выбор изменился во время проверки. Ничего не разрешено.');
      }
      const attestationId = attestationResponse.pricebook_attestation.id;
      const decision = {
        enabled: true,
        authorization_reference: RIDERRA_AUTHORIZATION_REFERENCE,
        records: selectedRecords,
        pricebook_attestation_id: attestationId,
        approved_manifest_sha256: '',
      };

      let manifestValue: unknown = null;
      try {
        await newAuth.makeRequest(AUTHORIZATION_ENDPOINT, {
          method: 'PATCH',
          body: JSON.stringify(decision),
        });
        throw new Error('Сервер не запросил точное подтверждение состава.');
      } catch (challengeError) {
        const challenged = challengeManifest(challengeError);
        if (!challenged) throw challengeError;
        manifestValue = challenged;
      }

      const manifest = verifyRiderraManifest(manifestValue, selectedRecords);
      if (accessEpoch.current !== requestAccessEpoch || selectionEpoch.current !== requestSelectionEpoch) {
        throw new Error('Выбор изменился после проверки. Ничего не разрешено.');
      }
      const finalResponse: unknown = await newAuth.makeRequest(AUTHORIZATION_ENDPOINT, {
        method: 'PATCH',
        body: JSON.stringify({ ...decision, approved_manifest_sha256: manifest.records_sha256 }),
      });
      finalAuthorization(finalResponse, manifest.records_sha256, 'active');
      if (accessEpoch.current !== requestAccessEpoch || selectionEpoch.current !== requestSelectionEpoch) return;
      setAuthorization({ active: true, count: selectedRecords.length });
      clearSelection();
      setNotice(`Группа из ${selectedRecords.length} компаний разрешена. Очередь и отправка не создавались.`);
    } catch (requestError) {
      if (accessEpoch.current !== requestAccessEpoch) return;
      setError(errorCopy(requestError, 'Не удалось разрешить группу.'));
    } finally {
      if (accessEpoch.current === requestAccessEpoch) setBusy('');
    }
  };

  const revokeAuthorization = async () => {
    if (accessState !== 'ready' || busy || !confirmRevoke) return;
    const requestAccessEpoch = accessEpoch.current;
    setBusy('revoke');
    setError('');
    setNotice('');
    try {
      const user = await newAuth.getCurrentUser();
      if (!user || user.is_superadmin !== true) {
        clearPrivateState();
        setAccessState('hidden');
        return;
      }
      if (accessEpoch.current !== requestAccessEpoch) return;
      const response: unknown = await newAuth.makeRequest(AUTHORIZATION_ENDPOINT, {
        method: 'PATCH',
        body: JSON.stringify({
          enabled: false,
          authorization_reference: RIDERRA_AUTHORIZATION_REFERENCE,
          records: [],
          pricebook_attestation_id: '',
          approved_manifest_sha256: '',
        }),
      });
      finalAuthorization(response, '', 'revoked');
      if (accessEpoch.current !== requestAccessEpoch) return;
      setAuthorization({ active: false, count: 0 });
      clearSelection();
      setNotice('Разрешение отозвано. Новые письма по этому шаблону не будут добавлены.');
    } catch (requestError) {
      if (accessEpoch.current !== requestAccessEpoch) return;
      setError(errorCopy(requestError, 'Не удалось отозвать разрешение.'));
    } finally {
      if (accessEpoch.current === requestAccessEpoch) setBusy('');
    }
  };

  const changeOpen = (nextOpen: boolean) => {
    if (busy) return;
    setOpen(nextOpen);
    setError('');
    setNotice('');
    if (!nextOpen) clearSelection();
  };

  if (!scopeMatches || accessState === 'checking' || accessState === 'hidden') return null;

  if (accessState === 'error') {
    return (
      <div className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between" role="status">
        <div>
          <div className="text-sm font-semibold text-slate-900">Согласованный шаблон Riderra</div>
          <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">Не удалось проверить статус. Действия недоступны.</p>
        </div>
        <Button variant="outline" onClick={() => void refreshAuthorization()} className="min-h-11 shrink-0">
          <RefreshCw /> Повторить
        </Button>
      </div>
    );
  }

  return (
    <div className="py-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-slate-900">Согласованный шаблон Riderra</span>
            <Badge variant="outline" className={authorization.active
              ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
              : 'border-slate-200 bg-slate-50 text-slate-700'}>
              {authorization.active ? `Разрешён · ${authorization.count}` : 'Не включён'}
            </Badge>
          </div>
          <p className="mt-1 max-w-xl text-pretty text-sm leading-6 text-slate-600">
            До {RIDERRA_DAILY_LIMIT} подготовленных компаний в день. Разрешение само не создаёт очередь и не отправляет письма.
          </p>
        </div>
        <Button onClick={() => setOpen(true)} className="min-h-11 shrink-0 active:scale-[0.96] transition-transform">
          <ShieldCheck /> {authorization.active ? 'Проверить или добавить' : 'Проверить и включить'}
        </Button>
      </div>

      <Dialog open={open} onOpenChange={changeOpen}>
        <DialogContent className="max-h-[90vh] w-[calc(100vw-2rem)] max-w-3xl overflow-y-auto rounded-2xl p-4 sm:p-6">
          <DialogHeader>
            <DialogTitle>Включить согласованный шаблон Riderra</DialogTitle>
            <DialogDescription className="text-pretty leading-6">
              Выберите проверенную группу, прочитайте пример и только затем разрешите её. From: {RIDERRA_SENDER_IDENTITY}.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="grid gap-3 rounded-xl bg-slate-50 p-4 sm:grid-cols-3">
              <div><div className="text-xs text-slate-500">Отправитель</div><div className="mt-1 break-all text-sm font-semibold text-slate-900">{RIDERRA_SENDER_IDENTITY}</div></div>
              <div><div className="text-xs text-slate-500">В выбранной группе</div><div className="mt-1 text-sm font-semibold tabular-nums text-slate-900">{records.length || '—'} / {RIDERRA_DAILY_LIMIT}</div></div>
              <div><div className="text-xs text-slate-500">Статус</div><div className="mt-1 text-sm font-semibold text-slate-900">{authorization.active ? 'Уже включён' : 'Ждёт вашего решения'}</div></div>
            </div>

            <details className="rounded-xl border border-slate-200 bg-white px-4 py-3">
              <summary className="flex min-h-10 cursor-pointer items-center text-sm font-semibold text-slate-800">Администратору: загрузить проверенные JSON</summary>
              <div className="grid gap-4 pt-3 sm:grid-cols-2">
                <label className="block text-sm font-medium text-slate-800">
                  Тарифы · snapshot005 JSON
                  <input
                    key={`snapshot-${fileInputVersion}`}
                    type="file"
                    aria-label="Тарифы · snapshot005 JSON"
                    accept="application/json,.json"
                    disabled={Boolean(busy)}
                    onChange={(event) => void selectSnapshot(event.target.files?.[0] || null)}
                    className="mt-2 block min-h-11 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm file:font-medium"
                  />
                  <span className="mt-1 block truncate text-xs text-slate-500">{snapshotName || 'Файл не выбран'}</span>
                </label>
                <label className="block text-sm font-medium text-slate-800">
                  Проверенные компании · JSON members
                  <input
                    key={`records-${fileInputVersion}`}
                    type="file"
                    aria-label="Проверенные компании · JSON members"
                    accept="application/json,.json"
                    disabled={Boolean(busy)}
                    onChange={(event) => void selectRecords(event.target.files?.[0] || null)}
                    className="mt-2 block min-h-11 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm file:font-medium"
                  />
                  <span className="mt-1 block truncate text-xs text-slate-500">{recordsName || 'Файл не выбран'}</span>
                </label>
              </div>
            </details>

            {currentPreview ? (
              <section aria-label="Пример письма" className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-900"><FileCheck2 className="h-4 w-4" /> Пример перед разрешением</div>
                    <p className="mt-1 text-xs text-slate-500">Адресат {previewIndex + 1} из {records.length}</p>
                  </div>
                  {records.length > 1 ? (
                    <select
                      aria-label="Выбрать пример"
                      value={previewIndex}
                      disabled={Boolean(busy)}
                      onChange={(event) => setPreviewIndex(Number(event.target.value))}
                      className="h-11 rounded-md border border-slate-200 bg-white px-3 text-sm"
                    >
                      {records.map((record, index) => <option key={`${record.workstream_id}:${record.lead_id}:${record.contact_point_id}`} value={index}>{index + 1}. {record.company}</option>)}
                    </select>
                  ) : null}
                </div>
                <div>
                  <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Тема</div>
                  <p className="mt-1 break-words text-sm font-semibold text-slate-950">{currentPreview.subject}</p>
                </div>
                <div>
                  <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Текст</div>
                  <pre className="mt-1 whitespace-pre-wrap break-words font-sans text-sm leading-6 text-slate-700">{currentPreview.body}</pre>
                </div>
                <Button type="button" variant="outline" onClick={clearSelection} disabled={Boolean(busy)} className="min-h-10 w-full sm:w-auto">Очистить выбор</Button>
              </section>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-300 px-4 py-5 text-pretty text-sm leading-6 text-slate-600">
                Откройте администраторские детали и выберите два проверенных JSON-файла. До явного разрешения никаких изменений не будет.
              </div>
            )}

            {notice ? <div aria-live="polite" className="rounded-xl bg-emerald-50 px-4 py-3 text-pretty text-sm leading-6 text-emerald-900"><CheckCircle2 className="mr-2 inline h-4 w-4" />{notice}</div> : null}
            {error ? <div role="alert" className="rounded-xl bg-rose-50 px-4 py-3 text-pretty text-sm leading-6 text-rose-900">{error}</div> : null}

            {authorization.active ? (
              <div className="rounded-xl bg-slate-50 p-4">
                <p className="text-pretty text-sm leading-6 text-slate-700">Можно добавить следующую проверенную группу. Или отозвать разрешение для новых писем.</p>
                {!confirmRevoke ? (
                  <Button variant="ghost" onClick={() => setConfirmRevoke(true)} disabled={Boolean(busy)} className="mt-2 min-h-10 px-3 text-rose-700 hover:text-rose-800">Отозвать разрешение</Button>
                ) : (
                  <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <span className="text-sm font-medium text-rose-800">Новые письма будут остановлены.</span>
                    <div className="flex flex-col gap-2 sm:flex-row">
                      <Button variant="outline" onClick={() => setConfirmRevoke(false)} disabled={Boolean(busy)} className="min-h-10">Оставить</Button>
                      <Button variant="destructive" onClick={() => void revokeAuthorization()} disabled={Boolean(busy)} className="min-h-10">
                        {busy === 'revoke' ? <RefreshCw className="animate-spin" /> : null} Подтвердить отзыв
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            ) : null}
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => changeOpen(false)} disabled={Boolean(busy)} className="min-h-11 w-full sm:w-auto">Закрыть</Button>
            <Button
              onClick={() => void enableAuthorization()}
              disabled={Boolean(busy) || !snapshotText || records.length < 1}
              className="min-h-11 w-full sm:w-auto"
            >
              {busy === 'enable' ? <RefreshCw className="animate-spin" /> : <ShieldCheck />}
              Разрешить эту группу по согласованному шаблону
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default RiderraTemplateSettings;
