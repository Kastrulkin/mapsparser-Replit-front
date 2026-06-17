import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  Download,
  Loader2,
  LogIn,
  RefreshCw,
  ShieldCheck,
  Store,
} from "lucide-react";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type YclientsAccount = {
  id?: string;
  salon_id?: string;
  display_name?: string;
  is_active?: boolean;
  status?: string;
  activation_status?: string;
  activation_error?: string;
  last_import_at?: string;
  last_import_count?: number;
};

type YclientsServerStatus = {
  has_partner_token?: boolean;
  has_user_token?: boolean;
  has_activation_url?: boolean;
};

type YclientsStatusResponse = {
  success?: boolean;
  error?: string;
  accounts?: YclientsAccount[];
  server?: YclientsServerStatus;
};

type YclientsConnectResponse = YclientsStatusResponse & {
  activation?: {
    activation_status?: string;
    activation_error?: string;
  };
};

type YclientsImportedService = {
  salon_id?: string;
  external_id?: string;
  name?: string;
  price?: string;
  category?: string;
};

type YclientsImportResponse = {
  success?: boolean;
  error?: string;
  imported_count?: number;
  services?: YclientsImportedService[];
};

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const readStringArray = (params: URLSearchParams, key: string): string[] =>
  params.getAll(key).map((value) => value.trim()).filter(Boolean);

const getSalonIds = (params: URLSearchParams): string[] => {
  const values = [
    ...readStringArray(params, "salon_ids[]"),
    ...readStringArray(params, "salon_ids"),
    ...readStringArray(params, "salon_id"),
    ...readStringArray(params, "company_id"),
  ];
  return values.filter((value, index) => values.indexOf(value) === index);
};

const getAuthToken = () => localStorage.getItem("auth_token") || localStorage.getItem("token") || "";

const getSelectedBusinessId = () =>
  localStorage.getItem("selectedBusinessId") || localStorage.getItem("admin_selected_business_id") || "";

const parseStatusResponse = (payload: unknown): YclientsStatusResponse => {
  if (!isObject(payload)) {
    return {};
  }
  return {
    success: Boolean(payload.success),
    error: typeof payload.error === "string" ? payload.error : undefined,
    accounts: Array.isArray(payload.accounts) ? payload.accounts.filter(isObject) : [],
    server: isObject(payload.server) ? payload.server : undefined,
  };
};

const parseConnectResponse = (payload: unknown): YclientsConnectResponse => {
  const base = parseStatusResponse(payload);
  return {
    ...base,
    activation: isObject(payload) && isObject(payload.activation) ? payload.activation : undefined,
  };
};

const parseImportResponse = (payload: unknown): YclientsImportResponse => {
  if (!isObject(payload)) {
    return {};
  }
  return {
    success: Boolean(payload.success),
    error: typeof payload.error === "string" ? payload.error : undefined,
    imported_count: typeof payload.imported_count === "number" ? payload.imported_count : undefined,
    services: Array.isArray(payload.services) ? payload.services.filter(isObject) : [],
  };
};

const formatDate = (value?: string) => {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("ru-RU");
};

const serverReadyLabel = (server?: YclientsServerStatus) => {
  if (!server) {
    return "Проверяем настройки сервера";
  }
  if (server.has_partner_token && server.has_user_token) {
    return "API-токены YCLIENTS заданы";
  }
  return "Нужно задать YCLIENTS_PARTNER_TOKEN и YCLIENTS_USER_TOKEN на сервере";
};

const activationLabel = (account?: YclientsAccount) => {
  if (!account) {
    return "Связь ещё не сохранена";
  }
  if (account.activation_status === "activated") {
    return "Интеграция активирована в YCLIENTS";
  }
  if (account.activation_status === "pending_configuration") {
    return "Связь сохранена, активационный URL не настроен";
  }
  if (account.activation_status === "failed") {
    return "YCLIENTS вернул ошибку активации";
  }
  return account.status === "connected" ? "Связь сохранена в LocalOS" : "Связь готовится";
};

const YclientsConnect = () => {
  const [params] = useSearchParams();
  const salonIds = useMemo(() => getSalonIds(params), [params]);
  const userData = params.get("user_data") || "";
  const userDataSign = params.get("user_data_sign") || "";
  const [token, setToken] = useState("");
  const [businessId, setBusinessId] = useState("");
  const [accounts, setAccounts] = useState<YclientsAccount[]>([]);
  const [server, setServer] = useState<YclientsServerStatus | undefined>();
  const [status, setStatus] = useState("Готово к подключению");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [importedServices, setImportedServices] = useState<YclientsImportedService[]>([]);
  const [importedCount, setImportedCount] = useState<number | undefined>();

  const primaryAccount = accounts[0];
  const hasAuth = Boolean(token);
  const hasBusiness = Boolean(businessId);
  const hasSalon = salonIds.length > 0;
  const canConnect = hasAuth && hasBusiness && hasSalon && !isConnecting;
  const canImport = hasAuth && hasBusiness && accounts.length > 0 && !isImporting;

  const refreshSessionState = useCallback(() => {
    setToken(getAuthToken());
    setBusinessId(getSelectedBusinessId());
  }, []);

  const requestPayload = useCallback(() => ({
    business_id: businessId,
    salon_ids: salonIds,
    user_data: userData,
    user_data_sign: userDataSign,
  }), [businessId, salonIds, userData, userDataSign]);

  const loadStatus = useCallback(async () => {
    if (!token || !businessId) {
      return;
    }
    setIsLoading(true);
    setError("");
    const query = new URLSearchParams({ business_id: businessId });
    salonIds.forEach((salonId) => query.append("salon_ids[]", salonId));
    try {
      const response = await fetch(`/api/yclients/marketplace/status?${query.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const payload: unknown = await response.json();
      const result = parseStatusResponse(payload);
      if (!response.ok || !result.success) {
        setError(result.error || "Не удалось получить статус подключения");
        return;
      }
      setAccounts(result.accounts || []);
      setServer(result.server);
      setStatus((result.accounts || []).length > 0 ? "Связь с YCLIENTS найдена" : "Связь ещё не сохранена");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка проверки статуса");
    } finally {
      setIsLoading(false);
    }
  }, [businessId, salonIds, token]);

  const connectYclients = async () => {
    if (!canConnect) {
      return;
    }
    setIsConnecting(true);
    setError("");
    setStatus("Сохраняем связь и отправляем активацию в YCLIENTS");
    try {
      const response = await fetch("/api/yclients/marketplace/connect", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestPayload()),
      });
      const payload: unknown = await response.json();
      const result = parseConnectResponse(payload);
      if (!response.ok || !result.success) {
        setError(result.error || "Не удалось сохранить связь YCLIENTS");
        setStatus("Нужно повторить подключение");
        return;
      }
      setAccounts(result.accounts || []);
      if (result.server) {
        setServer(result.server);
      }
      setStatus(result.activation?.activation_error || "YCLIENTS подключен к LocalOS");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка подключения");
      setStatus("Нужно повторить подключение");
    } finally {
      setIsConnecting(false);
    }
  };

  const importServices = async () => {
    if (!canImport) {
      return;
    }
    setIsImporting(true);
    setError("");
    setStatus("Импортируем услуги и цены из YCLIENTS");
    try {
      const response = await fetch("/api/yclients/marketplace/import-services", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestPayload()),
      });
      const payload: unknown = await response.json();
      const result = parseImportResponse(payload);
      if (!response.ok || !result.success) {
        setError(result.error || "Не удалось импортировать услуги");
        setStatus("Импорт не выполнен");
        return;
      }
      setImportedCount(result.imported_count);
      setImportedServices(result.services || []);
      setStatus(`Импортировано услуг: ${result.imported_count || 0}`);
      await loadStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка импорта");
      setStatus("Импорт не выполнен");
    } finally {
      setIsImporting(false);
    }
  };

  useEffect(() => {
    refreshSessionState();
  }, [refreshSessionState]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  return (
    <div className="min-h-screen bg-background">
      <main className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-10 sm:px-6 lg:px-8">
        <section className="space-y-4">
          <p className="text-sm font-semibold uppercase tracking-wide text-primary">YCLIENTS + LocalOS</p>
          <h1 className="max-w-3xl text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Подключение филиала YCLIENTS к LocalOS
          </h1>
          <p className="max-w-3xl text-base leading-7 text-muted-foreground">
            Сохраните связь с филиалом, импортируйте услуги и цены, затем продолжайте работу с картами,
            отзывами, контент-планом, новостями и партнёрствами. Публикации и внешние отправки остаются
            только после вашего подтверждения.
          </p>
        </section>

        <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
          <Card>
            <CardHeader>
              <CardTitle>Подключение</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-md border p-3">
                  <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Шаг 1</div>
                  <div className="mt-1 text-sm font-semibold text-foreground">
                    {hasAuth ? "Вход выполнен" : "Войдите в LocalOS"}
                  </div>
                </div>
                <div className="rounded-md border p-3">
                  <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Шаг 2</div>
                  <div className="mt-1 text-sm font-semibold text-foreground">
                    {hasBusiness ? "Бизнес выбран" : "Выберите бизнес"}
                  </div>
                </div>
                <div className="rounded-md border p-3">
                  <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Шаг 3</div>
                  <div className="mt-1 text-sm font-semibold text-foreground">
                    {accounts.length > 0 ? "Связь сохранена" : "Сохраните связь"}
                  </div>
                </div>
              </div>

              <div className="rounded-md border bg-muted/40 p-4">
                <div className="flex items-start gap-3">
                  <Store className="mt-1 h-5 w-5 shrink-0 text-primary" />
                  <div className="min-w-0">
                    <div className="font-medium text-foreground">Филиал YCLIENTS</div>
                    <div className="break-words text-sm text-muted-foreground">
                      {hasSalon ? salonIds.join(", ") : "Не пришёл salon_id из YCLIENTS. Откройте подключение из маркетплейса ещё раз."}
                    </div>
                    {businessId && (
                      <div className="mt-1 break-words text-xs text-muted-foreground">
                        Бизнес LocalOS: {businessId}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {error && (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                  {error}
                </div>
              )}

              <div className="flex flex-wrap gap-3">
                {!hasAuth && (
                  <Button asChild>
                    <Link to="/login">
                      <LogIn className="mr-2 h-4 w-4" />
                      Войти в LocalOS
                    </Link>
                  </Button>
                )}
                {hasAuth && !hasBusiness && (
                  <Button asChild>
                    <Link to="/dashboard">
                      Выбрать бизнес
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                )}
                <Button onClick={connectYclients} disabled={!canConnect}>
                  {isConnecting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                  Сохранить связь YCLIENTS
                </Button>
                <Button variant="secondary" onClick={importServices} disabled={!canImport}>
                  {isImporting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                  Импортировать услуги и цены
                </Button>
                <Button variant="outline" onClick={loadStatus} disabled={!hasAuth || !hasBusiness || isLoading}>
                  {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                  Обновить статус
                </Button>
              </div>

              <div className="text-sm text-muted-foreground">{status}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Готовность</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-muted-foreground">
              <div className="flex gap-3 rounded-md border p-3">
                <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                <div>
                  <div className="font-medium text-foreground">{serverReadyLabel(server)}</div>
                  <div>
                    Активация marketplace: {server?.has_activation_url ? "URL задан" : "URL не задан, связь сохранится в LocalOS"}
                  </div>
                </div>
              </div>
              <div className="flex gap-3 rounded-md border p-3">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                <div>
                  <div className="font-medium text-foreground">{activationLabel(primaryAccount)}</div>
                  {primaryAccount?.activation_error && <div>{primaryAccount.activation_error}</div>}
                  {primaryAccount?.last_import_at && (
                    <div>
                      Последний импорт: {formatDate(primaryAccount.last_import_at)}, услуг: {primaryAccount.last_import_count || 0}
                    </div>
                  )}
                </div>
              </div>
              <div className="rounded-md border p-3">
                <div className="font-medium text-foreground">Что импортируем сейчас</div>
                <div>Категории услуг, названия, описания, цены, длительность и внешний ID YCLIENTS.</div>
              </div>
            </CardContent>
          </Card>
        </div>

        {(accounts.length > 0 || importedServices.length > 0) && (
          <Card>
            <CardHeader>
              <CardTitle>Результат</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {accounts.length > 0 && (
                <div className="grid gap-3 md:grid-cols-2">
                  {accounts.map((account) => (
                    <div key={account.id || account.salon_id} className="rounded-md border p-3 text-sm">
                      <div className="font-medium text-foreground">{account.display_name || `YCLIENTS ${account.salon_id}`}</div>
                      <div className="text-muted-foreground">Филиал: {account.salon_id || "не указан"}</div>
                      <div className="text-muted-foreground">{activationLabel(account)}</div>
                    </div>
                  ))}
                </div>
              )}
              {typeof importedCount === "number" && (
                <div className="text-sm font-medium text-foreground">Импортировано услуг: {importedCount}</div>
              )}
              {importedServices.length > 0 && (
                <div className="overflow-hidden rounded-md border">
                  <div className="grid grid-cols-[1fr_0.6fr_0.5fr] gap-3 border-b bg-muted/40 px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    <div>Услуга</div>
                    <div>Категория</div>
                    <div>Цена</div>
                  </div>
                  {importedServices.slice(0, 10).map((service) => (
                    <div
                      key={`${service.salon_id || ""}:${service.external_id || service.name || ""}`}
                      className="grid grid-cols-[1fr_0.6fr_0.5fr] gap-3 border-b px-3 py-2 text-sm last:border-b-0"
                    >
                      <div className="min-w-0 truncate text-foreground">{service.name || "Без названия"}</div>
                      <div className="min-w-0 truncate text-muted-foreground">{service.category || "YCLIENTS"}</div>
                      <div className="min-w-0 truncate text-muted-foreground">{service.price || "не указана"}</div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </main>
      <Footer />
    </div>
  );
};

export default YclientsConnect;
