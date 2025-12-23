import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { newAuth } from "@/lib/auth_new";

interface ExternalAccount {
  id: string;
  source: string;
  external_id?: string | null;
  display_name?: string | null;
  is_active: number;
  last_sync_at?: string | null;
  last_error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

interface ExternalIntegrationsProps {
  currentBusinessId: string | null;
}

export const ExternalIntegrations: React.FC<ExternalIntegrationsProps> = ({ currentBusinessId }) => {
  const [accounts, setAccounts] = useState<ExternalAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  // В пользовательском кабинете всегда работаем только с Google Business
  const formSource: "google_business" = "google_business";
  const [formExternalId, setFormExternalId] = useState("");
  const [formDisplayName, setFormDisplayName] = useState("");
  const [formAuthData, setFormAuthData] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadAccounts = async () => {
    if (!currentBusinessId) return;
    setLoading(true);
    setError(null);
    try {
      const token = newAuth.getToken();
      if (!token) return;

      const res = await fetch(`/api/business/${currentBusinessId}/external-accounts`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.status === 404) {
        // Если бэкенд не знает про этот эндпоинт или бизнес, просто считаем, что интеграций нет
        setAccounts([]);
        setError(null);
        return;
      }

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Не удалось загрузить интеграции");
      }
      setAccounts(data.accounts || []);
    } catch (e: any) {
      setError(e.message || "Ошибка загрузки интеграций");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAccounts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentBusinessId]);

  const handleSave = async () => {
    if (!currentBusinessId) {
      setError("Сначала выберите бизнес");
      return;
    }
    if (!formSource) {
      setError("Выберите источник");
      return;
    }
    if (formSource === "google_business" && !formExternalId) {
      // Для Google лучше иметь явный идентификатор локации
      setError("Укажите Google location ID (или оставьте временный маркер)");
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const token = newAuth.getToken();
      if (!token) return;

      const res = await fetch(`/api/business/${currentBusinessId}/external-accounts`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          source: formSource,
          external_id: formExternalId || null,
          display_name: formDisplayName || null,
          auth_data: formAuthData || null,
          is_active: true,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Не удалось сохранить интеграцию");
      }
      setSuccess("Интеграция сохранена");
      setFormAuthData("");
      await loadAccounts();
    } catch (e: any) {
      setError(e.message || "Ошибка сохранения интеграции");
    } finally {
      setSaving(false);
    }
  };

  const handleDisconnect = async (accountId: string) => {
    if (!accountId) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const token = newAuth.getToken();
      if (!token) return;

      const res = await fetch(`/api/external-accounts/${accountId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Не удалось отключить интеграцию");
      }
      setSuccess("Интеграция отключена");
      await loadAccounts();
    } catch (e: any) {
      setError(e.message || "Ошибка отключения интеграции");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Интеграции с внешними источниками</CardTitle>
        <CardDescription>Подключите Google Business Profile для вашего бизнеса.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {error && <div className="text-sm text-red-600">{error}</div>}
        {success && <div className="text-sm text-green-600">{success}</div>}

        {/* Форма создания/обновления аккаунта */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border rounded-lg p-4 bg-gray-50">
          <div className="space-y-2">
            <label className="text-sm font-medium">Источник</label>
            <div className="text-sm font-semibold text-gray-800">Google Business</div>
            <p className="text-xs text-gray-500">
              Напишите нам, какие другие источники вы хотели бы подключить.
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">
              Внешний ID (опционально, для Google — location ID)
            </label>
            <Input
              value={formExternalId}
              onChange={(e) => setFormExternalId(e.target.value)}
              placeholder="Например, Google location ID или ID организации"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Отображаемое имя</label>
            <Input
              value={formDisplayName}
              onChange={(e) => setFormDisplayName(e.target.value)}
              placeholder="Как аккаунт называется в кабинете"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">
              Данные доступа Google (временно: refresh token / JSON OAuth)
            </label>
            <textarea
              className="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={formAuthData}
              onChange={(e) => setFormAuthData(e.target.value)}
              placeholder={
                "В дальнейшем здесь будет храниться refresh token / JSON из OAuth Google. Сейчас можно указать тестовые данные."
              }
            />
          </div>

          <div className="md:col-span-2 flex justify-end">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Сохранение..." : "Сохранить интеграцию"}
            </Button>
          </div>
        </div>

        {/* Список подключённых аккаунтов */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-800">Подключённые аккаунты</h3>
          {loading ? (
            <p className="text-sm text-gray-500">Загрузка...</p>
          ) : accounts.length === 0 ? (
            <p className="text-sm text-gray-500">Интеграции ещё не настроены.</p>
          ) : (
            <div className="space-y-2">
              {accounts.map((acc) => (
                <div
                  key={acc.id}
                  className="flex flex-col md:flex-row md:items-center md:justify-between border rounded-md px-3 py-2 text-sm"
                >
                  <div className="space-y-1">
                    <div className="font-medium">
                      {acc.source === "yandex_business"
                        ? "Яндекс.Бизнес"
                        : acc.source === "google_business"
                        ? "Google Business"
                        : acc.source === "2gis"
                        ? "2ГИС"
                        : acc.source}
                    </div>
                    {acc.display_name && (
                      <div className="text-gray-700">{acc.display_name}</div>
                    )}
                    {acc.external_id && (
                      <div className="text-gray-500">ID: {acc.external_id}</div>
                    )}
                    {acc.last_sync_at && (
                      <div className="text-xs text-gray-500">
                        Последний синк: {new Date(acc.last_sync_at).toLocaleString("ru-RU")}
                      </div>
                    )}
                    {acc.last_error && (
                      <div className="text-xs text-red-600">
                        Ошибка последнего синка: {acc.last_error}
                      </div>
                    )}
                  </div>
                  <div className="mt-2 md:mt-0 flex gap-2 justify-end">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={saving}
                      onClick={() => handleDisconnect(acc.id)}
                    >
                      Отключить
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};


