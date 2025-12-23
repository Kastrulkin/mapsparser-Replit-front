import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { newAuth } from '@/lib/auth_new';
import { Settings } from 'lucide-react';

interface ExternalAccount {
  id: string;
  source: string;
  external_id?: string;
  display_name?: string;
  is_active: boolean;
  last_sync_at?: string;
  last_error?: string;
}

interface AdminExternalCabinetSettingsProps {
  businessId: string;
  businessName: string;
}

export const AdminExternalCabinetSettings = ({ businessId, businessName }: AdminExternalCabinetSettingsProps) => {
  const [yandexAccount, setYandexAccount] = useState<ExternalAccount | null>(null);
  const [twoGisAccount, setTwoGisAccount] = useState<ExternalAccount | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  // Формы для Яндекс.Бизнес
  const [yandexForm, setYandexForm] = useState({
    external_id: '',
    display_name: '',
    auth_data: '',
  });

  // Формы для 2ГИС
  const [twoGisForm, setTwoGisForm] = useState({
    external_id: '',
    display_name: '',
    auth_data: '',
  });

  useEffect(() => {
    loadAccounts();
  }, [businessId]);

  const loadAccounts = async () => {
    try {
      const token = await newAuth.getToken();
      const response = await fetch(`/api/business/${businessId}/external-accounts`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        const accounts = data.accounts || [];
        
        const yandex = accounts.find((a: ExternalAccount) => a.source === 'yandex_business');
        const twoGis = accounts.find((a: ExternalAccount) => a.source === '2gis');
        
        setYandexAccount(yandex || null);
        setTwoGisAccount(twoGis || null);
        
        if (yandex) {
          setYandexForm({
            external_id: yandex.external_id || '',
            display_name: yandex.display_name || '',
            auth_data: '', // Не показываем зашифрованные данные
          });
        }
        
        if (twoGis) {
          setTwoGisForm({
            external_id: twoGis.external_id || '',
            display_name: twoGis.display_name || '',
            auth_data: '', // Не показываем зашифрованные данные
          });
        }
      }
    } catch (error: any) {
      console.error('Ошибка загрузки аккаунтов:', error);
    } finally {
      setLoading(false);
    }
  };

  const saveAccount = async (source: 'yandex_business' | '2gis', formData: typeof yandexForm) => {
    setSaving(true);
    try {
      const token = await newAuth.getToken();
      
      // Формируем JSON для auth_data (cookies или токен)
      const authDataJson = JSON.stringify({
        cookies: formData.auth_data,
        headers: {},
      });

      const response = await fetch(`/api/business/${businessId}/external-accounts`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          source,
          external_id: formData.external_id || undefined,
          display_name: formData.display_name || undefined,
          auth_data: authDataJson,
          is_active: true,
        }),
      });

      if (response.ok) {
        toast({
          title: 'Успешно',
          description: `Аккаунт ${source === 'yandex_business' ? 'Яндекс.Бизнес' : '2ГИС'} сохранён`,
        });
        await loadAccounts();
      } else {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Ошибка сохранения');
      }
    } catch (error: any) {
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось сохранить аккаунт',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="text-center py-4">Загрузка...</div>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings className="h-5 w-5" />
          Настройки внешних кабинетов для бизнеса: {businessName}
        </CardTitle>
        <CardDescription>
          Подключите личные кабинеты Яндекс.Бизнес и 2ГИС для автоматической синхронизации данных
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Яндекс.Бизнес */}
        <div className="border rounded-lg p-4">
          <h3 className="text-lg font-semibold mb-4">Яндекс.Бизнес</h3>
          <div className="space-y-4">
            <div>
              <Label htmlFor="yandex-external-id">ID организации (рекомендуется)</Label>
              <Input
                id="yandex-external-id"
                value={yandexForm.external_id}
                onChange={(e) => setYandexForm({ ...yandexForm, external_id: e.target.value })}
                placeholder="Например: 1234567890"
              />
              <p className="text-xs text-gray-500 mt-1">
                Найти ID: откройте организацию в кабинете → посмотрите URL (https://business.yandex.ru/organizations/<strong>1234567890</strong>/...)
                <br />
                Если у вас несколько организаций, укажите ID нужной организации
              </p>
            </div>
            <div>
              <Label htmlFor="yandex-display-name">Название (опционально)</Label>
              <Input
                id="yandex-display-name"
                value={yandexForm.display_name}
                onChange={(e) => setYandexForm({ ...yandexForm, display_name: e.target.value })}
                placeholder="Название организации"
              />
            </div>
            <div>
              <Label htmlFor="yandex-auth-data">Cookies (обязательно) *</Label>
              <Textarea
                id="yandex-auth-data"
                value={yandexForm.auth_data}
                onChange={(e) => setYandexForm({ ...yandexForm, auth_data: e.target.value })}
                placeholder="Вставьте cookies из браузера (например: yandexuid=123...; Session_id=abc...; yandex_login=user@example.com; ...)"
                rows={6}
                required
              />
              <p className="text-xs text-gray-500 mt-1">
                <strong>Как скопировать cookies:</strong>
                <br />
                1. Откройте DevTools (F12) → вкладка "Application" (Chrome) или "Storage" (Firefox)
                <br />
                2. Слева: Cookies → выберите домен <code className="bg-gray-100 px-1 rounded">business.yandex.ru</code> или <code className="bg-gray-100 px-1 rounded">yandex.ru</code>
                <br />
                3. Скопируйте все cookies в одну строку через точку с запятой
                <br />
                <strong>Важно:</strong> Cookies должны быть скопированы после входа в личный кабинет Яндекс.Бизнес
              </p>
            </div>
            {yandexAccount && (
              <div className="text-sm text-gray-600">
                <p>Статус: {yandexAccount.is_active ? 'Активен' : 'Неактивен'}</p>
                {yandexAccount.last_sync_at && (
                  <p>Последняя синхронизация: {new Date(yandexAccount.last_sync_at).toLocaleString('ru-RU')}</p>
                )}
                {yandexAccount.last_error && (
                  <p className="text-red-600">Ошибка: {yandexAccount.last_error}</p>
                )}
              </div>
            )}
            <Button
              onClick={() => saveAccount('yandex_business', yandexForm)}
              disabled={saving || !yandexForm.auth_data}
            >
              {saving ? 'Сохранение...' : yandexAccount ? 'Обновить' : 'Сохранить'}
            </Button>
          </div>
        </div>

        {/* 2ГИС */}
        <div className="border rounded-lg p-4">
          <h3 className="text-lg font-semibold mb-4">2ГИС</h3>
          <div className="space-y-4">
            <div>
              <Label htmlFor="2gis-external-id">ID организации (опционально)</Label>
              <Input
                id="2gis-external-id"
                value={twoGisForm.external_id}
                onChange={(e) => setTwoGisForm({ ...twoGisForm, external_id: e.target.value })}
                placeholder="ID организации в 2ГИС"
              />
            </div>
            <div>
              <Label htmlFor="2gis-display-name">Название (опционально)</Label>
              <Input
                id="2gis-display-name"
                value={twoGisForm.display_name}
                onChange={(e) => setTwoGisForm({ ...twoGisForm, display_name: e.target.value })}
                placeholder="Название организации"
              />
            </div>
            <div>
              <Label htmlFor="2gis-auth-data">Cookies / Токен сессии *</Label>
              <Textarea
                id="2gis-auth-data"
                value={twoGisForm.auth_data}
                onChange={(e) => setTwoGisForm({ ...twoGisForm, auth_data: e.target.value })}
                placeholder="Вставьте cookies из браузера или токен сессии 2ГИС"
                rows={4}
                required
              />
              <p className="text-xs text-gray-500 mt-1">
                Скопируйте cookies из браузера после входа в личный кабинет 2ГИС
              </p>
            </div>
            {twoGisAccount && (
              <div className="text-sm text-gray-600">
                <p>Статус: {twoGisAccount.is_active ? 'Активен' : 'Неактивен'}</p>
                {twoGisAccount.last_sync_at && (
                  <p>Последняя синхронизация: {new Date(twoGisAccount.last_sync_at).toLocaleString('ru-RU')}</p>
                )}
                {twoGisAccount.last_error && (
                  <p className="text-red-600">Ошибка: {twoGisAccount.last_error}</p>
                )}
              </div>
            )}
            <Button
              onClick={() => saveAccount('2gis', twoGisForm)}
              disabled={saving || !twoGisForm.auth_data}
            >
              {saving ? 'Сохранение...' : twoGisAccount ? 'Обновить' : 'Сохранить'}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

