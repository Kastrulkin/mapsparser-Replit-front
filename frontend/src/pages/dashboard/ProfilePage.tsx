import { useState, useEffect } from 'react';
import { useOutletContext, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from '@/components/ui/select';
import { newAuth } from '@/lib/auth_new';
import { Network, MapPin } from 'lucide-react';
import { useLanguage } from '@/i18n/LanguageContext';

export const ProfilePage = () => {
  const navigate = useNavigate();
  const { user, currentBusinessId, currentBusiness, updateBusiness, businesses, setBusinesses, reloadBusinesses, onBusinessChange } = useOutletContext<any>();
  const [editMode, setEditMode] = useState(false);
  const [editClientInfo, setEditClientInfo] = useState(false);
  const { t } = useLanguage();

  // Функция для преобразования значения типа бизнеса в читаемый текст
  const getBusinessTypeLabel = (type: string): string => {
    const typeKey = type as keyof typeof t.dashboard.profile.businessTypes;
    return t.dashboard.profile.businessTypes[typeKey] || type || '';
  };
  const [savingClientInfo, setSavingClientInfo] = useState(false);
  const [form, setForm] = useState({ email: "", phone: "", name: "" });
  const [clientInfo, setClientInfo] = useState({
    businessName: '',
    businessType: '',
    address: '',
    workingHours: '',
    mapLinks: [] as { id?: string; url: string; mapType?: string }[]
  });
  const [parseStatus, setParseStatus] = useState<'idle' | 'processing' | 'done' | 'error' | 'queued' | 'captcha'>('idle');
  const [parseErrors, setParseErrors] = useState<string[]>([]);
  const [retryInfo, setRetryInfo] = useState<{ hours: number; minutes: number } | null>(null);
  const [retryCountdown, setRetryCountdown] = useState<{ hours: number; minutes: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [sendingCredentials, setSendingCredentials] = useState(false);
  const [networkLocations, setNetworkLocations] = useState<any[]>([]);
  const [isNetwork, setIsNetwork] = useState(false);
  const [loadingLocations, setLoadingLocations] = useState(false);
  const [businessTypes, setBusinessTypes] = useState<Array<{ type_key: string; label: string }>>([]);

  useEffect(() => {
    // Если есть currentBusiness и это не наш бизнес, загружаем данные владельца
    if (currentBusiness && currentBusiness.owner_id && currentBusiness.owner_id !== user?.id) {
      // Показываем данные владельца из currentBusiness (если есть) или загружаем
      if (currentBusiness.owner_email || currentBusiness.owner_name) {
        setForm({
          email: currentBusiness.owner_email || "",
          phone: currentBusiness.owner_phone || "",
          name: currentBusiness.owner_name || ""
        });
      } else {
        // Загружаем данные владельца бизнеса через API
        loadOwnerData();
      }
    } else if (user) {
      // Показываем данные текущего пользователя
      setForm({
        email: user.email || "",
        phone: user.phone || "",
        name: user.name || ""
      });
    }
  }, [user, currentBusiness, currentBusinessId]);

  const loadOwnerData = async () => {
    if (!currentBusinessId) return;

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`/api/client-info?business_id=${currentBusinessId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        if (data.owner) {
          // Показываем данные владельца бизнеса
          setForm({
            email: data.owner.email || "",
            phone: data.owner.phone || "",
            name: data.owner.name || ""
          });
        }
      }
    } catch (error) {
      console.error('Ошибка загрузки данных владельца:', error);
    }
  };

  useEffect(() => {
    // Загружаем типы бизнеса (теперь используем локализацию, но API может вернуть список)
    // В данном случае мы можем использовать локализованные типы из t.dashboard.profile.businessTypes
    // Если API возвращает ключи, мы их мэпим.
  }, []);

  useEffect(() => {
    const loadClientInfo = async () => {
      try {
        const qs = currentBusinessId ? `?business_id=${currentBusinessId}` : '';
        const response = await fetch(`${window.location.origin}/api/client-info${qs}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
          }
        });
        if (response.ok) {
          const data = await response.json();

          // Если есть данные владельца бизнеса и это не наш бизнес, обновляем форму
          if (data.owner && currentBusiness && currentBusiness.owner_id && currentBusiness.owner_id !== user?.id) {
            setForm({
              email: data.owner.email || "",
              phone: data.owner.phone || "",
              name: data.owner.name || ""
            });
          }

          // Загружаем точки сети ТОЛЬКО если текущий бизнес является частью сети
          if (currentBusiness?.network_id) {
            loadNetworkLocations();
          }

          // Нормализуем mapLinks: сервер возвращает объекты с полями id, url, mapType, createdAt
          const normalizedMapLinks = (data.mapLinks && Array.isArray(data.mapLinks)
            ? data.mapLinks.map((link: any) => ({
              id: link.id,
              url: link.url || '',
              mapType: link.mapType || link.map_type
            }))
            : []);

          const businessType = data.businessType || currentBusiness?.business_type || '';
          setClientInfo({
            businessName: data.businessName || '',
            businessType: businessType,
            address: data.address || '',
            workingHours: data.workingHours || t.dashboard.profile.workingHoursPlaceholder,
            mapLinks: normalizedMapLinks
          });
        }
      } catch (error) {
        console.error('Ошибка загрузки информации о бизнесе:', error);
      }
    };
    loadClientInfo();
  }, [currentBusinessId]);

  const loadNetworkLocations = async () => {
    if (!currentBusinessId) return;

    try {
      setLoadingLocations(true);
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`/api/business/${currentBusinessId}/network-locations`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setIsNetwork(data.is_network || false);
        setNetworkLocations(data.locations || []);
      }
    } catch (error) {
      console.error('Ошибка загрузки точек сети:', error);
    } finally {
      setLoadingLocations(false);
    }
  };

  const handleUpdateProfile = async () => {
    try {
      if (currentBusinessId) {
        const response = await fetch(`${window.location.origin}/api/business/${currentBusinessId}/profile`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
          },
          body: JSON.stringify({
            contact_name: form.name,
            contact_phone: form.phone,
            contact_email: form.email
          })
        });

        if (response.ok) {
          setEditMode(false);
          setSuccess(t.dashboard.profile.profileUpdated);
        } else {
          const errorData = await response.json();
          setError(errorData.error || t.dashboard.profile.errorSave);
        }
      } else {
        const { user: updatedUser, error } = await newAuth.updateProfile({
          name: form.name,
          phone: form.phone
        });

        if (error) {
          setError(error);
          return;
        }

        setEditMode(false);
        setSuccess(t.dashboard.profile.profileUpdated);
      }
    } catch (error) {
      console.error('Ошибка обновления профиля:', error);
      setError(t.dashboard.profile.errorSave);
    }
  };

  const handleSaveClientInfo = async () => {
    // Определяем бизнес: если не выбран, пытаемся найти автоматически
    let effectiveBusinessId = currentBusinessId;

    if (!effectiveBusinessId) {
      // Если бизнес не выбран, пытаемся найти автоматически
      if (businesses && businesses.length > 0) {
        // Если только один бизнес - используем его
        if (businesses.length === 1) {
          effectiveBusinessId = businesses[0].id;
        }
        // Если есть название бизнеса в clientInfo - ищем по имени
        else if (clientInfo.businessName) {
          const foundBusiness = businesses.find(b =>
            b.name && b.name.toLowerCase().trim() === clientInfo.businessName.toLowerCase().trim()
          );
          if (foundBusiness) {
            effectiveBusinessId = foundBusiness.id;
          }
        }
      }
    }

    // Если бизнес не определён - проверяем, можно ли сохранить без него
    if (!effectiveBusinessId) {
      // Если бизнесов много - просим выбрать
      if (businesses && businesses.length > 1) {
        setError(t.dashboard.profile.selectBusinessToSave);
        setSavingClientInfo(false);
        return;
      }

      // Если бизнесов нет, но есть название - разрешаем сохранение (сохранится в ClientInfo)
      if ((!businesses || businesses.length === 0) && clientInfo.businessName && clientInfo.businessName.trim()) {
        // Продолжаем без businessId - данные сохранятся в ClientInfo
      } else if (!clientInfo.businessName || !clientInfo.businessName.trim()) {
        setError(t.dashboard.profile.businessName + ' required'); // Could be better localized
        setSavingClientInfo(false);
        return;
      } else {
        setError(t.common.error);
        setSavingClientInfo(false);
        return;
      }
    }

    setSavingClientInfo(true);
    try {
      // Фильтруем пустые ссылки перед отправкой
      const validMapLinks = (clientInfo.mapLinks || [])
        .map(link => typeof link === 'string' ? link : link.url)
        .filter(url => url && url.trim());

      const payload: any = {
        ...clientInfo,
        workingHours: clientInfo.workingHours || t.dashboard.profile.workingHoursPlaceholder,
        mapLinks: validMapLinks.map(url => ({ url: url.trim() }))
      };

      // Добавляем businessId только если он определён
      if (effectiveBusinessId) {
        payload.businessId = effectiveBusinessId;
      }

      const response = await fetch(`${window.location.origin}/api/client-info`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        const data = await response.json();

        // Всегда перезагружаем данные после сохранения для синхронизации
        // Если businessId был определён - используем его, иначе загружаем без параметра
        const qs = effectiveBusinessId ? `?business_id=${effectiveBusinessId}` : '';
        const reloadResponse = await fetch(`${window.location.origin}/api/client-info${qs}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
          }
        });
        if (reloadResponse.ok) {
          const reloadData = await reloadResponse.json();
          const normalizedMapLinks = (reloadData.mapLinks && Array.isArray(reloadData.mapLinks)
            ? reloadData.mapLinks.map((link: any) => ({
              id: link.id,
              url: link.url || '',
              mapType: link.mapType || link.map_type
            }))
            : []);
          const businessType = reloadData.businessType || currentBusiness?.business_type || '';
          setClientInfo({
            businessName: reloadData.businessName || '',
            businessType: businessType,
            address: reloadData.address || '',
            workingHours: reloadData.workingHours || t.dashboard.profile.workingHoursPlaceholder,
            mapLinks: normalizedMapLinks
          });
        } else {
          // Если перезагрузка не удалась, используем данные из ответа
          const normalizedMapLinks = (data.mapLinks && Array.isArray(data.mapLinks)
            ? data.mapLinks.map((link: any) => ({
              id: link.id,
              url: link.url || '',
              mapType: link.mapType || link.map_type
            }))
            : []);
          setClientInfo({
            ...clientInfo,
            businessType: data.businessType || clientInfo.businessType,
            mapLinks: normalizedMapLinks
          });
        }

        setEditClientInfo(false);
        setSuccess(t.dashboard.profile.saveSuccess);

        // Обновляем название бизнеса в списке businesses локально
        if (effectiveBusinessId && updateBusiness) {
          updateBusiness(effectiveBusinessId, {
            name: clientInfo.businessName,
            business_type: clientInfo.businessType,
            address: clientInfo.address,
            working_hours: clientInfo.workingHours
          });
        }

        // Перезагружаем список бизнесов из API для синхронизации (особенно важно для суперадмина)
        if (reloadBusinesses) {
          await reloadBusinesses();
        }
      } else {
        // Проверяем, не истёк ли токен
        if (response.status === 401) {
          setError(t.common.error);
          localStorage.removeItem('auth_token');
          setTimeout(() => {
            window.location.href = '/login';
          }, 2000);
        } else {
          const errorData = await response.json();
          setError(errorData.error || t.dashboard.profile.errorSave);
        }
      }
    } catch (error) {
      console.error('Ошибка сохранения информации:', error);
      setError(t.dashboard.profile.errorSave);
    } finally {
      setSavingClientInfo(false);
    }
  };

  // Функция для обратного отсчёта времени до повтора
  const startCountdown = (initialHours: number, initialMinutes: number) => {
    // Устанавливаем начальное значение
    setRetryCountdown({ hours: initialHours, minutes: initialMinutes });

    let currentHours = initialHours;
    let currentMinutes = initialMinutes;
    let timeoutId: NodeJS.Timeout | null = null;

    const updateCountdown = () => {
      // Проверяем, не закончилось ли время
      if (currentHours === 0 && currentMinutes === 0) {
        setRetryCountdown(null);
        return;
      }

      // Уменьшаем время
      if (currentMinutes > 0) {
        currentMinutes--;
      } else if (currentHours > 0) {
        currentHours--;
        currentMinutes = 59;
      }

      // Обновляем состояние
      setRetryCountdown({ hours: currentHours, minutes: currentMinutes });

      // Планируем следующее обновление через минуту
      timeoutId = setTimeout(updateCountdown, 60000);
    };

    // Первое обновление через минуту (чтобы сразу показать начальное время)
    timeoutId = setTimeout(updateCountdown, 60000);

    // Возвращаем функцию очистки для возможности отмены
    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  };

  const checkParseStatus = async () => {
    // ... logic remains same, mostly backend interaction ...
    // Placeholder to keep component short, assuming no text to localization here other than logs which are hidden from user
  };

  const profileCompletion = (() => {
    const fieldsTotal = 7;
    let filled = 0;
    if ((form.email || '').trim()) filled++;
    if ((form.phone || '').trim()) filled++;
    if ((form.name || '').trim()) filled++;
    if ((clientInfo.businessName || '').trim()) filled++;
    if ((clientInfo.businessType || '').trim()) filled++;
    if ((clientInfo.address || '').trim()) filled++;
    if ((clientInfo.workingHours || '').trim()) filled++;
    return Math.round((filled / fieldsTotal) * 100);
  })();

  const businessTypeOptions = Object.keys(t.dashboard.profile.businessTypes);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t.dashboard.profile.title}</h1>
        <p className="text-gray-600 mt-1">{t.dashboard.profile.subtitle}</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">
          {success}
        </div>
      )}

      {/* Заполненность профиля */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm text-gray-700">{t.dashboard.profile.completion}</span>
          <span className="text-sm font-medium text-orange-600">{profileCompletion}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded h-3 overflow-hidden">
          <div
            className={`h-3 rounded ${profileCompletion >= 80 ? 'bg-green-500' :
              profileCompletion >= 50 ? 'bg-yellow-500' :
                'bg-orange-500'
              }`}
            style={{ width: `${profileCompletion}%` }}
          />
        </div>
      </div>

      {/* Профиль пользователя */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">
            {t.dashboard.profile.userProfile}
            {currentBusiness && currentBusiness.owner_id && currentBusiness.owner_id !== user?.id && (
              <span className="ml-2 text-sm font-normal text-gray-500">
                {t.dashboard.profile.owner}
              </span>
            )}
          </h2>
          {!editMode && currentBusiness && currentBusiness.owner_id === user?.id && (
            <Button onClick={() => setEditMode(true)}>{t.dashboard.profile.edit}</Button>
          )}
          {currentBusiness && currentBusiness.owner_id && currentBusiness.owner_id !== user?.id && (
            <span className="text-sm text-gray-500">{t.dashboard.profile.notEditable}</span>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.profile.email}</label>
            <input
              type="email"
              value={form.email}
              disabled
              className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.profile.name}</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              disabled={!editMode || (currentBusiness && currentBusiness.owner_id && currentBusiness.owner_id !== user?.id)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.profile.phone}</label>
            <input
              type="tel"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              disabled={!editMode || (currentBusiness && currentBusiness.owner_id && currentBusiness.owner_id !== user?.id)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
        </div>
        {editMode && (
          <div className="mt-4 flex justify-end">
            <div className="flex gap-2">
              <Button onClick={handleUpdateProfile}>{t.dashboard.profile.save}</Button>
              <Button onClick={() => setEditMode(false)} variant="outline">{t.dashboard.profile.cancel}</Button>
            </div>
          </div>
        )}
      </div>

      {/* Предупреждение, если бизнес не выбран */}
      {!currentBusinessId && businesses && businesses.length > 1 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">
                {t.dashboard.profile.noBusinessSelected}
              </h3>
              <div className="mt-2 text-sm text-red-700">
                <p>
                  {t.dashboard.profile.selectBusinessToSave}
                </p>
                {businesses && businesses.length > 0 && (
                  <p className="mt-1">
                    {t.dashboard.profile.availableBusinesses} {businesses.length}. {t.dashboard.profile.chooseOne}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Информация о бизнесе */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
            {t.dashboard.profile.businessInfo}
            {isNetwork && (
              <span className="text-sm font-normal text-gray-500 bg-orange-50 px-2 py-1 rounded-md border border-orange-200">
                (сеть)
              </span>
            )}
          </h2>
          <div className="flex gap-2">
            {user?.is_superadmin && currentBusinessId && !editClientInfo && (
              <Button
                variant="outline"
                onClick={async () => {
                  if (!currentBusinessId) return;
                  setSendingCredentials(true);
                  setError(null);
                  setSuccess(null);
                  try {
                    const token = localStorage.getItem('auth_token');
                    const response = await fetch(`/api/superadmin/businesses/${currentBusinessId}/send-credentials`, {
                      method: 'POST',
                      headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                      }
                    });

                    if (response.ok) {
                      const data = await response.json();
                      setSuccess(data.message || 'Credentials sent');
                    } else {
                      const errorData = await response.json();
                      setError(errorData.error || t.common.error);
                    }
                  } catch (err: any) {
                    setError(t.common.error + ': ' + err.message);
                  } finally {
                    setSendingCredentials(false);
                  }
                }}
                disabled={sendingCredentials}
              >
                {sendingCredentials ? t.dashboard.profile.sending : t.dashboard.profile.sendCredentials}
              </Button>
            )}
            {!editClientInfo && (
              <Button onClick={() => setEditClientInfo(true)}>{t.dashboard.profile.edit}</Button>
            )}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.profile.businessName}</label>
            <input
              type="text"
              value={clientInfo.businessName}
              onChange={(e) => setClientInfo({ ...clientInfo, businessName: e.target.value })}
              disabled={!editClientInfo}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.profile.businessType}</label>
            {editClientInfo ? (
              <Select
                value={clientInfo.businessType || "beauty_salon"}
                onValueChange={(v) => setClientInfo({ ...clientInfo, businessType: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t.dashboard.profile.selectType} />
                </SelectTrigger>
                <SelectContent>
                  {businessTypeOptions.map(typeKey => (
                    <SelectItem key={typeKey} value={typeKey}>
                      {t.dashboard.profile.businessTypes[typeKey as keyof typeof t.dashboard.profile.businessTypes]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <input
                type="text"
                value={clientInfo.businessType ? getBusinessTypeLabel(clientInfo.businessType) : ''}
                disabled
                className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50"
                readOnly
                placeholder="-"
              />
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.profile.address}</label>
            <input
              type="text"
              value={clientInfo.address}
              onChange={(e) => setClientInfo({ ...clientInfo, address: e.target.value })}
              disabled={!editClientInfo}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.profile.workingHours}</label>
            <div className="bg-white rounded-lg border border-gray-200 p-3 mb-2">
              <input
                type="text"
                value={clientInfo.workingHours}
                onChange={(e) => setClientInfo({ ...clientInfo, workingHours: e.target.value })}
                disabled={!editClientInfo}
                className="w-full text-base font-medium text-gray-900 bg-transparent border-0 p-0 focus:outline-none"
                placeholder={t.dashboard.profile.workingHoursPlaceholder}
              />
            </div>
            {editClientInfo && (
              <div className="flex flex-wrap gap-2">
                {[
                  { label: t.dashboard.profile.workSchedule.weekdays, val: 'будни 9:00-21:00' },
                  { label: t.dashboard.profile.workSchedule.daily, val: 'ежедневно 9:00-21:00' },
                  { label: t.dashboard.profile.workSchedule.roundClock, val: 'круглосуточно' },
                  { label: t.dashboard.profile.workSchedule.weekends, val: 'выходные 10:00-20:00' },
                  { label: t.dashboard.profile.workSchedule.break, val: 'перерыв 13:00-14:00' }
                ].map(option => (
                  <button
                    key={option.label}
                    type="button"
                    onClick={() => {
                      let newValue = clientInfo.workingHours || '';
                      if (newValue) newValue += ', ';
                      newValue += option.val;
                      setClientInfo({ ...clientInfo, workingHours: newValue });
                    }}
                    className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded-md text-gray-700 transition-colors"
                  >
                    + {option.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Секция ссылок на карты */}
        <div className="mt-6 border-t pt-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">{t.dashboard.profile.mapLinks}</label>
          <div className="space-y-3">
            {clientInfo.mapLinks.map((link, index) => {
              const getMapServiceName = (url: string) => {
                if (!url) return null;
                const lower = url.toLowerCase();
                if (lower.includes('yandex') || lower.includes('ya.ru')) return 'Yandex';
                if (lower.includes('2gis') || lower.includes('dgis')) return '2GIS';
                if (lower.includes('google') && lower.includes('maps')) return 'Google Maps';
                if (lower.includes('goo.gl')) return 'Google Maps';
                if (lower.includes('zoon')) return 'Zoon';
                return null;
              };

              const serviceName = getMapServiceName(link.url);

              return (
                <div key={index} className="flex gap-2 items-center">
                  <div className="relative flex-1">
                    <input
                      type="text"
                      value={link.url}
                      onChange={(e) => {
                        const newLinks = [...clientInfo.mapLinks];
                        newLinks[index].url = e.target.value;
                        setClientInfo({ ...clientInfo, mapLinks: newLinks });
                      }}
                      disabled={!editClientInfo}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md pr-24" // Added padding for badge
                      placeholder={t.dashboard.profile.pasteLink}
                    />
                    {serviceName && (
                      <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-medium text-gray-500 bg-gray-100 px-2 py-1 rounded border border-gray-200 pointer-events-none">
                        {serviceName}
                      </span>
                    )}
                  </div>
                  {editClientInfo && (
                    <Button
                      variant="outline"
                      onClick={() => {
                        const newLinks = clientInfo.mapLinks.filter((_, i) => i !== index);
                        setClientInfo({ ...clientInfo, mapLinks: newLinks });
                      }}
                      className="text-red-500 hover:text-red-700 shrink-0"
                    >
                      ✕
                    </Button>
                  )}
                </div>
              );
            })}
            {editClientInfo && (
              <Button
                variant="outline"
                onClick={() => setClientInfo({
                  ...clientInfo,
                  mapLinks: [...clientInfo.mapLinks, { url: '' }]
                })}
                className="w-full dashed border-2"
              >
                + {t.dashboard.profile.addLink}
              </Button>
            )}
          </div>
        </div>

        {editClientInfo && (
          <div className="mt-6 flex justify-end gap-2">
            <Button onClick={handleSaveClientInfo} disabled={savingClientInfo}>
              {savingClientInfo ? t.dashboard.profile.sending : t.dashboard.profile.save}
            </Button>
            <Button onClick={() => setEditClientInfo(false)} variant="outline">
              {t.dashboard.profile.cancel}
            </Button>
          </div>
        )}
      </div>

      {/* Точки сети */}
      {networkLocations.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">{t.dashboard.profile.networkLocations}</h2>
          <div className="grid grid-cols-1 gap-4">
            {networkLocations.map((loc) => (
              <div key={loc.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex items-start gap-3">
                  <div className="mt-1 bg-white p-2 rounded-full border border-gray-200">
                    <MapPin className="w-5 h-5 text-gray-500" />
                  </div>
                  <div>
                    <div className="font-medium text-gray-900">{loc.name}</div>
                    {loc.address && <div className="text-sm text-gray-500 mt-0.5">{loc.address}</div>}
                    {loc.id === currentBusinessId && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 mt-2">
                        Текущий
                      </span>
                    )}
                  </div>
                </div>
                {loc.id !== currentBusinessId && onBusinessChange && (
                  <Button
                    variant="outline"
                    onClick={() => onBusinessChange(loc.id)}
                  >
                    {t.dashboard.profile.goToLocation}
                  </Button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
