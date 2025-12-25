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
  const [testingCookies, setTestingCookies] = useState(false);
  const [showInstructions, setShowInstructions] = useState(false);
  const { toast } = useToast();

  // Ключи для sessionStorage
  const yandexCookiesKey = `yandex_cookies_${businessId}`;
  const twoGisCookiesKey = `2gis_cookies_${businessId}`;

  // Формы для Яндекс.Бизнес (загружаем cookies из sessionStorage при инициализации)
  const [yandexForm, setYandexForm] = useState({
    external_id: '',
    display_name: '',
    auth_data: typeof window !== 'undefined' ? (sessionStorage.getItem(yandexCookiesKey) || '') : '',
  });

  // Формы для 2ГИС (загружаем cookies из sessionStorage при инициализации)
  const [twoGisForm, setTwoGisForm] = useState({
    external_id: '',
    display_name: '',
    auth_data: typeof window !== 'undefined' ? (sessionStorage.getItem(twoGisCookiesKey) || '') : '',
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
          setYandexForm(prev => {
            // Загружаем cookies из sessionStorage, если они там есть
            const savedCookies = typeof window !== 'undefined' ? (sessionStorage.getItem(yandexCookiesKey) || '') : '';
            return {
              external_id: yandex.external_id || '',
              display_name: yandex.display_name || '',
              // Используем сохраненные cookies из sessionStorage или текущие из формы
              auth_data: savedCookies || prev.auth_data || '', // Не показываем зашифрованные данные (из соображений безопасности)
            };
          });
        } else {
          // Если аккаунта нет, очищаем форму, но сохраняем cookies если они были введены
          setYandexForm(prev => {
            const savedCookies = typeof window !== 'undefined' ? (sessionStorage.getItem(yandexCookiesKey) || '') : '';
            return {
              external_id: '',
              display_name: '',
              auth_data: savedCookies || prev.auth_data || '', // Сохраняем введенные cookies
            };
          });
        }
        
        if (twoGis) {
          setTwoGisForm(prev => {
            // Загружаем cookies из sessionStorage, если они там есть
            const savedCookies = typeof window !== 'undefined' ? (sessionStorage.getItem(twoGisCookiesKey) || '') : '';
            return {
              external_id: twoGis.external_id || '',
              display_name: twoGis.display_name || '',
              // Используем сохраненные cookies из sessionStorage или текущие из формы
              auth_data: savedCookies || prev.auth_data || '', // Не показываем зашифрованные данные (из соображений безопасности)
            };
          });
        } else {
          // Если аккаунта нет, очищаем форму, но сохраняем cookies если они были введены
          setTwoGisForm(prev => {
            const savedCookies = typeof window !== 'undefined' ? (sessionStorage.getItem(twoGisCookiesKey) || '') : '';
            return {
              external_id: '',
              display_name: '',
              auth_data: savedCookies || prev.auth_data || '', // Сохраняем введенные cookies
            };
          });
        }
      }
    } catch (error: any) {
      console.error('Ошибка загрузки аккаунтов:', error);
    } finally {
      setLoading(false);
    }
  };

  const testCookies = async (source: 'yandex_business' | '2gis', formData: typeof yandexForm) => {
    if (!formData.auth_data || !formData.auth_data.trim()) {
      toast({
        title: 'Ошибка',
        description: 'Введите cookies для тестирования',
        variant: 'destructive',
      });
      return;
    }

    if (source === 'yandex_business' && !formData.external_id) {
      toast({
        title: 'Ошибка',
        description: 'Укажите ID организации для тестирования',
        variant: 'destructive',
      });
      return;
    }

    setTestingCookies(true);
    try {
      const token = await newAuth.getToken();
      const authDataJson = JSON.stringify({
        cookies: formData.auth_data.trim(),
        headers: {},
      });

      const response = await fetch(`/api/business/${businessId}/external-accounts/test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          source,
          auth_data: authDataJson,
          external_id: formData.external_id || undefined,
        }),
      });

      // Проверяем статус ответа
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Ошибка ответа сервера:', response.status, errorText);
        toast({
          title: '❌ Ошибка сервера',
          description: `Статус ${response.status}: ${errorText.substring(0, 200)}`,
          variant: 'destructive',
        });
        return;
      }

      // Парсим JSON ответ
      let result;
      try {
        result = await response.json();
      } catch (e) {
        console.error('Ошибка парсинга JSON:', e);
        const text = await response.text();
        toast({
          title: '❌ Ошибка',
          description: `Сервер вернул не JSON ответ: ${text.substring(0, 200)}`,
          variant: 'destructive',
        });
        return;
      }

      // Обрабатываем результат
      if (result.success) {
        toast({
          title: '✅ Успешно',
          description: result.message || 'Cookies работают корректно!',
        });
      } else {
        toast({
          title: '❌ Ошибка',
          description: result.message || result.error || 'Cookies не работают',
          variant: 'destructive',
        });
      }
    } catch (error: any) {
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось протестировать cookies',
        variant: 'destructive',
      });
    } finally {
      setTestingCookies(false);
    }
  };

  const saveAccount = async (source: 'yandex_business' | '2gis', formData: typeof yandexForm) => {
    setSaving(true);
    try {
      const token = await newAuth.getToken();
      
      const account = source === 'yandex_business' ? yandexAccount : twoGisAccount;
      
      // Сохраняем введенные cookies перед сохранением (чтобы не потерять их после перезагрузки)
      const hasNewCookies = formData.auth_data && formData.auth_data.trim().length > 0;
      const savedCookies = hasNewCookies ? formData.auth_data.trim() : null;
      
      // Если cookies пустые, но аккаунт уже существует - не отправляем auth_data (чтобы не перезаписать существующие)
      let authDataJson = undefined;
      if (hasNewCookies) {
        // Формируем JSON для auth_data (cookies или токен)
        authDataJson = JSON.stringify({
          cookies: savedCookies,
          headers: {},
        });
      } else if (!account) {
        // Если аккаунта нет и cookies пустые - ошибка
        toast({
          title: 'Ошибка',
          description: 'Cookies обязательны для нового аккаунта',
          variant: 'destructive',
        });
        setSaving(false);
        return;
      }
      // Если аккаунт есть и cookies пустые - просто обновляем другие поля, не трогая cookies

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
          ...(authDataJson ? { auth_data: authDataJson } : {}), // Отправляем auth_data только если указаны новые cookies
          is_active: true,
        }),
      });

      if (response.ok) {
        toast({
          title: 'Успешно',
          description: `Аккаунт ${source === 'yandex_business' ? 'Яндекс.Бизнес' : '2ГИС'} сохранён`,
        });
        
        // Перезагружаем аккаунты
        await loadAccounts();
        
        // Если были введены новые cookies, сохраняем их в форме и sessionStorage (чтобы они не пропали)
        if (savedCookies) {
          if (source === 'yandex_business') {
            setYandexForm(prev => ({ ...prev, auth_data: savedCookies }));
            if (typeof window !== 'undefined') {
              sessionStorage.setItem(yandexCookiesKey, savedCookies);
            }
          } else if (source === '2gis') {
            setTwoGisForm(prev => ({ ...prev, auth_data: savedCookies }));
            if (typeof window !== 'undefined') {
              sessionStorage.setItem(twoGisCookiesKey, savedCookies);
            }
          }
        }
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
              {yandexAccount && yandexAccount.last_sync_at && (() => {
                const lastSync = new Date(yandexAccount.last_sync_at);
                const daysSinceSync = Math.floor((Date.now() - lastSync.getTime()) / (1000 * 60 * 60 * 24));
                const isOld = daysSinceSync > 14;
                
                return (
                  <div className={`mb-2 p-2 border rounded text-sm ${
                    isOld 
                      ? 'bg-yellow-50 border-yellow-200 text-yellow-800' 
                      : 'bg-green-50 border-green-200 text-green-800'
                  }`}>
                    {isOld ? (
                      <>
                        ⚠️ Cookies сохранены {daysSinceSync} дней назад (последняя синхронизация: {lastSync.toLocaleString('ru-RU')})
                        <br />
                        <span className="text-xs">Рекомендуется обновить cookies, если прошло больше 2 недель</span>
                      </>
                    ) : (
                      <>
                        ✅ Cookies сохранены (последняя синхронизация: {lastSync.toLocaleString('ru-RU')})
                        <br />
                        <span className="text-xs text-green-600">Чтобы обновить cookies, вставьте новые данные ниже и нажмите "Обновить"</span>
                      </>
                    )}
                  </div>
                );
              })()}
              <Textarea
                id="yandex-auth-data"
                value={yandexForm.auth_data}
                onChange={(e) => {
                  const value = e.target.value;
                  setYandexForm({ ...yandexForm, auth_data: value });
                  // Сохраняем cookies в sessionStorage при вводе
                  if (typeof window !== 'undefined') {
                    if (value.trim()) {
                      sessionStorage.setItem(yandexCookiesKey, value);
                    } else {
                      sessionStorage.removeItem(yandexCookiesKey);
                    }
                  }
                }}
                placeholder={yandexAccount && yandexAccount.last_sync_at 
                  ? "Вставьте новые cookies для обновления (или оставьте пустым, чтобы не менять)"
                  : "Вставьте cookies из браузера (например: yandexuid=123...; Session_id=abc...; yandex_login=user@example.com; ...)"}
                rows={6}
                required={!yandexAccount || !yandexAccount.last_sync_at}
              />
              <div className="mt-2">
                <button
                  type="button"
                  onClick={() => setShowInstructions(!showInstructions)}
                  className="text-sm text-blue-600 hover:text-blue-800 underline"
                >
                  {showInstructions ? '▼ Скрыть инструкцию' : '▶ Показать инструкцию по копированию cookies'}
                </button>
                {showInstructions && (
                  <div className="mt-2 p-3 bg-blue-50 border border-blue-200 rounded text-xs text-gray-700">
                    <strong className="block mb-2">📋 Пошаговая инструкция:</strong>
                    <ol className="list-decimal list-inside space-y-1 ml-2">
                      <li>Откройте личный кабинет Яндекс.Бизнес в браузере: <code className="bg-gray-100 px-1 rounded">https://yandex.ru/sprav/</code></li>
                      <li>Убедитесь, что вы авторизованы (вошли в аккаунт)</li>
                      <li>Откройте DevTools: нажмите <kbd className="bg-gray-200 px-1 rounded">F12</kbd> или <kbd className="bg-gray-200 px-1 rounded">Cmd+Option+I</kbd> (Mac)</li>
                      <li>Перейдите на вкладку <strong>"Application"</strong> (Chrome) или <strong>"Storage"</strong> (Firefox)</li>
                      <li>В левом меню найдите <strong>"Cookies"</strong> → выберите домен <code className="bg-gray-100 px-1 rounded">yandex.ru</code></li>
                      <li>Скопируйте все cookies в формате: <code className="bg-gray-100 px-1 rounded">key1=value1; key2=value2; ...</code></li>
                      <li>Вставьте скопированную строку в поле выше</li>
                      <li>Нажмите <strong>"Проверить cookies"</strong> для тестирования перед сохранением</li>
                    </ol>
                    <div className="mt-2 p-2 bg-yellow-50 border border-yellow-200 rounded">
                      <strong>⚠️ Важно:</strong>
                      <ul className="list-disc list-inside ml-2 mt-1 space-y-1">
                        <li>Cookies должны быть скопированы <strong>после входа</strong> в личный кабинет</li>
                        <li>Обязательные cookies: <code className="bg-gray-100 px-1 rounded">Session_id</code>, <code className="bg-gray-100 px-1 rounded">yandexuid</code>, <code className="bg-gray-100 px-1 rounded">sessionid2</code></li>
                        <li>Обновляйте cookies раз в 1-2 недели или при ошибках 401/302</li>
                      </ul>
                    </div>
                  </div>
                )}
              </div>
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
            <div className="flex gap-2">
              <Button
                onClick={() => testCookies('yandex_business', yandexForm)}
                disabled={testingCookies || saving || !yandexForm.auth_data || !yandexForm.external_id}
                variant="outline"
              >
                {testingCookies ? 'Проверка...' : 'Проверить cookies'}
              </Button>
              <Button
                onClick={() => saveAccount('yandex_business', yandexForm)}
                disabled={saving || testingCookies || (!yandexAccount && !yandexForm.auth_data)}
              >
                {saving ? 'Сохранение...' : yandexAccount ? 'Обновить' : 'Сохранить'}
              </Button>
            </div>
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
                onChange={(e) => {
                  const value = e.target.value;
                  setTwoGisForm({ ...twoGisForm, auth_data: value });
                  // Сохраняем cookies в sessionStorage при вводе
                  if (typeof window !== 'undefined') {
                    if (value.trim()) {
                      sessionStorage.setItem(twoGisCookiesKey, value);
                    } else {
                      sessionStorage.removeItem(twoGisCookiesKey);
                    }
                  }
                }}
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

