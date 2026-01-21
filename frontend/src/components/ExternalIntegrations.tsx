import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { newAuth } from "@/lib/auth_new";
import { useToast } from "@/components/ui/use-toast";
import { useLanguage } from "@/i18n/LanguageContext";

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
  const { toast } = useToast();
  const { t, language } = useLanguage();

  const loadAccounts = async () => {
    if (!currentBusinessId) return;
    setLoading(true);
    try {
      const token = newAuth.getToken();
      if (!token) return;

      const res = await fetch(`/api/business/${currentBusinessId}/external-accounts`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.status === 404) {
        setAccounts([]);
        return;
      }

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || t.dashboard.settings.external.error);
      }
      setAccounts(data.accounts || []);
    } catch (e: any) {
      toast({
        title: t.error,
        description: e.message || t.dashboard.settings.external.error,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAccounts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentBusinessId]);

  // Проверка статуса авторизации через URL параметры (после редиректа)
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const authStatus = urlParams.get('google_auth');

    if (authStatus === 'success') {
      toast({
        title: t.success,
        description: t.dashboard.settings.external.successAuth,
      });
      loadAccounts();
      // Убираем параметр из URL
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (authStatus === 'error') {
      toast({
        title: t.error,
        description: t.dashboard.settings.external.errorAuth,
        variant: "destructive",
      });
      window.history.replaceState({}, document.title, window.location.pathname);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleGoogleAuth = async () => {
    if (!currentBusinessId) {
      toast({
        title: t.error,
        description: t.dashboard.settings.external.selectBusiness,
        variant: "destructive",
      });
      return;
    }

    try {
      const token = newAuth.getToken();
      if (!token) {
        toast({
          title: t.error,
          description: t.error,
          variant: "destructive"
        });
        return;
      }

      // Получаем URL для авторизации
      const res = await fetch(
        `/api/google/oauth/authorize?business_id=${currentBusinessId}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.error || t.error);
      }

      // Открываем popup для авторизации
      const width = 600;
      const height = 700;
      const left = (window.screen.width - width) / 2;
      const top = (window.screen.height - height) / 2;

      const popup = window.open(
        data.auth_url,
        'Google Auth',
        `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no,scrollbars=yes,resizable=yes`
      );

      if (!popup) {
        toast({
          title: t.error,
          description: "Pop-up blocked. Please allow pop-ups.",
          variant: "destructive",
        });
        return;
      }

      const checkPopup = setInterval(() => {
        try {
          if (popup.closed) {
            clearInterval(checkPopup);
            // После закрытия окна пробуем обновить список, возможно авторизация прошла успешно
            loadAccounts();
          }
        } catch (e) {
          // Игнорируем ошибки доступа
        }
      }, 1000);

      const messageHandler = (event: MessageEvent) => {
        if (event.origin !== window.location.origin) return;

        if (event.data.type === 'GOOGLE_AUTH_SUCCESS') {
          clearInterval(checkPopup);
          window.removeEventListener('message', messageHandler);
          popup.close();

          toast({
            title: t.success,
            description: t.dashboard.settings.external.successAuth,
          });
          loadAccounts();
        } else if (event.data.type === 'GOOGLE_AUTH_ERROR') {
          clearInterval(checkPopup);
          window.removeEventListener('message', messageHandler);
          popup.close();

          toast({
            title: t.error,
            description: event.data.error || t.dashboard.settings.external.errorAuth,
            variant: "destructive"
          });
        }
      };

      window.addEventListener('message', messageHandler);

      // Таймаут 5 минут
      setTimeout(() => {
        clearInterval(checkPopup);
        window.removeEventListener('message', messageHandler);
      }, 5 * 60 * 1000);

    } catch (e: any) {
      toast({
        title: t.error,
        description: e.message || t.dashboard.settings.external.errorAuth,
        variant: "destructive",
      });
    }
  };

  const handleDisconnect = async (accountId: string) => {
    if (!accountId) return;
    setSaving(true);
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
        throw new Error(data.error || t.error);
      }
      toast({
        title: t.success,
        description: t.dashboard.settings.external.successDisconnect,
      });
      await loadAccounts();
    } catch (e: any) {
      toast({
        title: t.error,
        description: e.message || t.error,
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t.dashboard.settings.external.title}</CardTitle>
        <CardDescription>{t.dashboard.settings.external.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">

        {/* Кнопка подключения Google */}
        <div className="border rounded-lg p-6 bg-gray-50 flex flex-col items-center text-center space-y-4">
          <div className="bg-white p-3 rounded-full shadow-sm">
            <svg className="w-8 h-8" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
          </div>
          <div>
            <h3 className="font-medium text-lg">{t.dashboard.settings.external.googleTitle}</h3>
            <p className="text-sm text-gray-500 max-w-md mx-auto mt-1">
              {t.dashboard.settings.external.googleDesc}
            </p>
          </div>
          <Button
            onClick={handleGoogleAuth}
            className="w-full sm:w-auto min-w-[200px] btn-iridescent"
            disabled={!currentBusinessId}
          >
            {t.dashboard.settings.external.connectGoogle}
          </Button>
          {!currentBusinessId && (
            <p className="text-xs text-red-500">{t.dashboard.settings.external.selectBusiness}</p>
          )}
        </div>

        {/* Список подключённых аккаунтов */}
        <div className="space-y-3 pt-4 border-t">
          <h3 className="text-sm font-semibold text-gray-800">{t.dashboard.settings.external.connectedAccounts}</h3>
          {loading ? (
            <p className="text-sm text-gray-500">{t.dashboard.subscription.processing}</p>
          ) : accounts.length === 0 ? (
            <p className="text-sm text-gray-500">{t.dashboard.settings.external.noIntegrations}</p>
          ) : (
            <div className="space-y-2">
              {accounts.map((acc) => (
                <div
                  key={acc.id}
                  className="flex flex-col md:flex-row md:items-center md:justify-between border rounded-md px-4 py-3 bg-white shadow-sm"
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-1">
                      {acc.source === "google_business" ? (
                        <svg className="w-5 h-5" viewBox="0 0 24 24">
                          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                        </svg>
                      ) : (
                        <div className="w-5 h-5 bg-gray-200 rounded-full" />
                      )}
                    </div>
                    <div className="space-y-0.5">
                      <div className="font-medium text-sm">
                        {acc.source === "yandex_business"
                          ? "Яндекс.Бизнес"
                          : acc.source === "google_business"
                            ? "Google Business Profile"
                            : acc.source === "2gis"
                              ? "2ГИС"
                              : acc.source}
                      </div>
                      {acc.display_name && (
                        <div className="text-sm text-gray-700">{acc.display_name}</div>
                      )}
                      {acc.external_id && (
                        <div className="text-xs text-gray-400">ID: {acc.external_id}</div>
                      )}

                      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1">
                        {acc.last_sync_at && (
                          <div className="text-xs text-gray-500 flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                            {t.dashboard.settings.external.sync} {new Date(acc.last_sync_at).toLocaleString(language === 'ru' ? 'ru-RU' : 'en-US')}
                          </div>
                        )}
                        {acc.last_error && (
                          <div className="text-xs text-red-600 flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span>
                            {t.dashboard.settings.external.error} {acc.last_error}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 md:mt-0 flex gap-2 justify-end items-center">
                    <div className={`px-2 py-1 rounded text-xs font-medium ${acc.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                      {acc.is_active ? t.dashboard.settings.external.active : t.dashboard.settings.external.disabled}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={saving}
                      onClick={() => handleDisconnect(acc.id)}
                      className="text-red-500 hover:text-red-600 hover:bg-red-50 border-red-100 h-8"
                    >
                      {t.dashboard.settings.external.disconnect}
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
