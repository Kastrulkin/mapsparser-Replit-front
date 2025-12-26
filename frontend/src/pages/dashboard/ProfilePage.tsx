import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from '@/components/ui/select';
import { newAuth } from '@/lib/auth_new';
import { Network, MapPin } from 'lucide-react';

export const ProfilePage = () => {
  const { user, currentBusinessId, currentBusiness, updateBusiness, businesses } = useOutletContext<any>();
  const [editMode, setEditMode] = useState(false);
  const [editClientInfo, setEditClientInfo] = useState(false);

  // Функция для преобразования значения типа бизнеса в читаемый текст
  const getBusinessTypeLabel = (type: string): string => {
    const typeMap: { [key: string]: string } = {
      'beauty_salon': 'Салон красоты',
      'barbershop': 'Барбершоп',
      'spa': 'SPA/Wellness',
      'nail_studio': 'Ногтевая студия',
      'cosmetology': 'Косметология',
      'massage': 'Массаж',
      'brows_lashes': 'Брови и ресницы',
      'makeup': 'Макияж',
      'tanning': 'Солярий',
      'other': 'Другое'
    };
    return typeMap[type] || type || '';
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
  const [businessTypes, setBusinessTypes] = useState<Array<{type_key: string; label: string}>>([]);

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
    // Загружаем типы бизнеса
    const loadBusinessTypes = async () => {
      try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(`${window.location.origin}/api/business-types`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        if (response.ok) {
          const data = await response.json();
          setBusinessTypes(data.types || []);
        }
      } catch (error) {
        console.error('Ошибка загрузки типов бизнеса:', error);
      }
    };
    loadBusinessTypes();
  }, []);

  useEffect(() => {
    const loadClientInfo = async () => {
      try {
        const qs = currentBusinessId ? `?business_id=${currentBusinessId}` : '';
        console.log('🔄 Загружаю client-info для business_id:', currentBusinessId);
        const response = await fetch(`${window.location.origin}/api/client-info${qs}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
          }
        });
        if (response.ok) {
          const data = await response.json();
          console.log('📥 Получены данные с сервера:', data);
          
          // Если есть данные владельца бизнеса и это не наш бизнес, обновляем форму
          if (data.owner && currentBusiness && currentBusiness.owner_id && currentBusiness.owner_id !== user?.id) {
            setForm({
              email: data.owner.email || "",
              phone: data.owner.phone || "",
              name: data.owner.name || ""
            });
          }
          
          // Загружаем точки сети, если бизнес является сетью
          if (currentBusinessId) {
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
          console.log('📋 Нормализованные mapLinks:', normalizedMapLinks);
          console.log('📋 businessType из API:', data.businessType);
          console.log('📋 Все данные из API:', data);
          // Если businessType не пришел из API, проверяем currentBusiness
          const businessType = data.businessType || currentBusiness?.business_type || '';
          console.log('📋 Используемый businessType:', businessType);
          setClientInfo({
            businessName: data.businessName || '',
            businessType: businessType,
            address: data.address || '',
            workingHours: data.workingHours || 'ежедневно 9:00-21:00',
            mapLinks: normalizedMapLinks
          });
        } else {
          console.error('❌ Ошибка загрузки client-info:', response.status, await response.text());
        }
      } catch (error) {
        console.error('❌ Ошибка загрузки информации о бизнесе:', error);
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
          setSuccess('Профиль бизнеса обновлен');
        } else {
          const errorData = await response.json();
          setError(errorData.error || 'Ошибка обновления профиля бизнеса');
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
        setSuccess('Профиль обновлен');
      }
    } catch (error) {
      console.error('Ошибка обновления профиля:', error);
      setError('Ошибка обновления профиля');
    }
  };

  const handleSaveClientInfo = async () => {
    console.log('🔵 handleSaveClientInfo вызван, currentBusinessId:', currentBusinessId);
    
    // Определяем бизнес: если не выбран, пытаемся найти автоматически
    let effectiveBusinessId = currentBusinessId;
    
    if (!effectiveBusinessId) {
      // Если бизнес не выбран, пытаемся найти автоматически
      if (businesses && businesses.length > 0) {
        // Если только один бизнес - используем его
        if (businesses.length === 1) {
          effectiveBusinessId = businesses[0].id;
          console.log('✅ Автоматически выбран единственный бизнес:', effectiveBusinessId);
        } 
        // Если есть название бизнеса в clientInfo - ищем по имени
        else if (clientInfo.businessName) {
          const foundBusiness = businesses.find(b => 
            b.name && b.name.toLowerCase().trim() === clientInfo.businessName.toLowerCase().trim()
          );
          if (foundBusiness) {
            effectiveBusinessId = foundBusiness.id;
            console.log('✅ Бизнес найден по имени:', effectiveBusinessId, clientInfo.businessName);
          }
        }
      }
    }
    
    // Если бизнес всё ещё не определён - показываем ошибку
    if (!effectiveBusinessId) {
      console.error('❌ Бизнес не выбран и не может быть определён автоматически!');
      if (businesses && businesses.length > 1) {
        setError('Пожалуйста, выберите бизнес из выпадающего списка в правом верхнем углу страницы перед сохранением');
      } else {
        setError('Не удалось определить бизнес. Пожалуйста, обратитесь в поддержку.');
      }
      setSavingClientInfo(false);
      return;
    }

    console.log('✅ Бизнес выбран, начинаю сохранение...');
    setSavingClientInfo(true);
    try {
      // Фильтруем пустые ссылки перед отправкой
      const validMapLinks = (clientInfo.mapLinks || [])
        .map(link => typeof link === 'string' ? link : link.url)
        .filter(url => url && url.trim());
      
      const payload = {
        ...clientInfo,
        businessId: effectiveBusinessId,
        workingHours: clientInfo.workingHours || 'ежедневно 9:00-21:00',
        mapLinks: validMapLinks.map(url => ({ url: url.trim() }))
      };
      
      console.log('📤 Отправляю данные:', payload);
      console.log('📤 businessType в payload:', payload.businessType);
      console.log('📤 clientInfo.businessType:', clientInfo.businessType);

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
        console.log('Ответ сервера:', data);
        
        // Всегда перезагружаем данные после сохранения для синхронизации
        const qs = effectiveBusinessId ? `?business_id=${effectiveBusinessId}` : '';
        const reloadResponse = await fetch(`${window.location.origin}/api/client-info${qs}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
          }
        });
        if (reloadResponse.ok) {
          const reloadData = await reloadResponse.json();
          console.log('🔄 Перезагруженные данные:', reloadData);
          console.log('🔄 businessType из перезагруженных данных:', reloadData.businessType);
          // Нормализуем mapLinks
          const normalizedMapLinks = (reloadData.mapLinks && Array.isArray(reloadData.mapLinks) 
            ? reloadData.mapLinks.map((link: any) => ({
                id: link.id,
                url: link.url || '',
                mapType: link.mapType || link.map_type
              }))
            : []);
          // Используем businessType из перезагруженных данных или из currentBusiness
          const businessType = reloadData.businessType || currentBusiness?.business_type || '';
          console.log('🔄 Устанавливаем businessType:', businessType);
          setClientInfo({
            businessName: reloadData.businessName || '',
            businessType: businessType,
            address: reloadData.address || '',
            workingHours: reloadData.workingHours || 'ежедневно 9:00-21:00',
            mapLinks: normalizedMapLinks
          });
        } else {
          // Если перезагрузка не удалась, используем данные из ответа
          console.log('⚠️ Перезагрузка не удалась, использую данные из ответа');
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
        setSuccess('Информация о бизнесе сохранена');
        
        // Обновляем название бизнеса в списке businesses
        if (effectiveBusinessId && updateBusiness) {
          updateBusiness(effectiveBusinessId, {
            name: clientInfo.businessName,
            business_type: clientInfo.businessType,
            address: clientInfo.address,
            working_hours: clientInfo.workingHours
          });
        }
      } else {
        // Проверяем, не истёк ли токен
        if (response.status === 401) {
          setError('Сессия истекла. Пожалуйста, войдите заново.');
          // Очищаем токен и перенаправляем на страницу входа
          localStorage.removeItem('auth_token');
          setTimeout(() => {
            window.location.href = '/login';
          }, 2000);
        } else {
          const errorData = await response.json();
          setError(errorData.error || 'Ошибка сохранения информации');
        }
      }
    } catch (error) {
      console.error('Ошибка сохранения информации:', error);
      setError('Ошибка сохранения информации');
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
    if (!currentBusinessId) return;
    
    try {
      const response = await fetch(`${window.location.origin}/api/business/${currentBusinessId}/parse-status`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        const status = data.status;
        
        // Сохраняем информацию о времени повтора для captcha
        if (data.retry_info) {
          const retryInfoData = {
            hours: data.retry_info.hours || 0,
            minutes: data.retry_info.minutes || 0
          };
          console.log('📊 Получен retry_info:', retryInfoData);
          setRetryInfo(retryInfoData);
          // Устанавливаем начальное значение для отсчёта
          setRetryCountdown(retryInfoData);
        } else {
          console.log('⚠️ retry_info не получен');
          setRetryInfo(null);
          setRetryCountdown(null);
        }
        
        if (status === 'done' || status === 'error' || status === 'captcha') {
          setParseStatus(status);
          // Для captcha запускаем обратный отсчёт
          if (status === 'captcha' && data.retry_info) {
            const hours = data.retry_info.hours || 0;
            const minutes = data.retry_info.minutes || 0;
            console.log('⏰ Запускаю обратный отсчёт:', hours, 'ч', minutes, 'мин');
            // Запускаем обратный отсчёт только если есть время
            if (hours > 0 || minutes > 0) {
              startCountdown(hours, minutes);
            }
          }
          // Останавливаем проверку статуса (кроме captcha, для которой нужен отсчёт)
          if (status !== 'captcha') {
            return;
          }
        } else if (status === 'processing' || status === 'queued') {
          setParseStatus(status);
          // Продолжаем проверку через 3 секунды
          setTimeout(checkParseStatus, 3000);
        }
      }
    } catch (error) {
      console.error('Ошибка проверки статуса парсинга:', error);
    }
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Профиль и бизнес</h1>
        <p className="text-gray-600 mt-1">Управляйте личными данными и информацией о вашем бизнесе</p>
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
          <span className="text-sm text-gray-700">Заполненность профиля</span>
          <span className="text-sm font-medium text-orange-600">{profileCompletion}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded h-3 overflow-hidden">
          <div 
            className={`h-3 rounded ${
              profileCompletion >= 80 ? 'bg-green-500' : 
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
            Профиль
            {currentBusiness && currentBusiness.owner_id && currentBusiness.owner_id !== user?.id && (
              <span className="ml-2 text-sm font-normal text-gray-500">
                (владелец бизнеса)
              </span>
            )}
          </h2>
          {!editMode && currentBusiness && currentBusiness.owner_id === user?.id && (
            <Button onClick={() => setEditMode(true)}>Редактировать</Button>
          )}
          {currentBusiness && currentBusiness.owner_id && currentBusiness.owner_id !== user?.id && (
            <span className="text-sm text-gray-500">Редактирование недоступно (чужой бизнес)</span>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input 
              type="email" 
              value={form.email} 
              disabled
              className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Имя</label>
            <input 
              type="text" 
              value={form.name} 
              onChange={(e) => setForm({...form, name: e.target.value})}
              disabled={!editMode || (currentBusiness && currentBusiness.owner_id && currentBusiness.owner_id !== user?.id)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Телефон</label>
            <input 
              type="tel"
              value={form.phone}
              onChange={(e) => setForm({...form, phone: e.target.value})}
              disabled={!editMode || (currentBusiness && currentBusiness.owner_id && currentBusiness.owner_id !== user?.id)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
        </div>
        {editMode && (
          <div className="mt-4 flex justify-end">
            <div className="flex gap-2">
              <Button onClick={handleUpdateProfile}>Сохранить</Button>
              <Button onClick={() => setEditMode(false)} variant="outline">Отмена</Button>
            </div>
          </div>
        )}
      </div>

      {/* Предупреждение, если бизнес не выбран и не может быть определён автоматически */}
      {/* Не показываем предупреждение если: бизнесов 0 или 1 (для владельцев одной точки) */}
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
                Бизнес не выбран
              </h3>
              <div className="mt-2 text-sm text-red-700">
                <p>
                  Для сохранения ссылок на карты необходимо выбрать бизнес из выпадающего списка в правом верхнем углу страницы.
                </p>
                {businesses && businesses.length > 0 && (
                  <p className="mt-1">
                    Доступно бизнесов: {businesses.length}. Выберите один из них, чтобы продолжить.
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
          <h2 className="text-xl font-semibold text-gray-900">Информация о бизнесе</h2>
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
                      setSuccess(data.message || 'Данные для входа отправлены владельцу бизнеса');
                    } else {
                      const errorData = await response.json();
                      setError(errorData.error || 'Ошибка отправки данных для входа');
                    }
                  } catch (err: any) {
                    setError('Ошибка отправки данных для входа: ' + err.message);
                  } finally {
                    setSendingCredentials(false);
                  }
                }}
                disabled={sendingCredentials}
              >
                {sendingCredentials ? 'Отправка...' : 'Send credentials'}
              </Button>
            )}
            {!editClientInfo && (
              <Button onClick={() => setEditClientInfo(true)}>Редактировать</Button>
            )}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Название бизнеса</label>
            <input 
              type="text" 
              value={clientInfo.businessName} 
              onChange={(e) => setClientInfo({...clientInfo, businessName: e.target.value})}
              disabled={!editClientInfo}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Тип бизнеса</label>
            {editClientInfo ? (
              <Select
                value={clientInfo.businessType || "beauty_salon"}
                onValueChange={(v) => setClientInfo({ ...clientInfo, businessType: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Выберите тип" />
                </SelectTrigger>
                <SelectContent>
                  {businessTypes.map(type => (
                    <SelectItem key={type.type_key} value={type.type_key}>
                      {type.label}
                    </SelectItem>
                  ))}
                  {businessTypes.length === 0 && (
                    <>
                      <SelectItem value="beauty_salon">Салон красоты</SelectItem>
                      <SelectItem value="barbershop">Барбершоп</SelectItem>
                      <SelectItem value="spa">SPA/Wellness</SelectItem>
                      <SelectItem value="nail_studio">Ногтевая студия</SelectItem>
                      <SelectItem value="cosmetology">Косметология</SelectItem>
                      <SelectItem value="massage">Массаж</SelectItem>
                      <SelectItem value="brows_lashes">Брови и ресницы</SelectItem>
                      <SelectItem value="makeup">Макияж</SelectItem>
                      <SelectItem value="tanning">Солярий</SelectItem>
                      <SelectItem value="other">Другое</SelectItem>
                    </>
                  )}
                </SelectContent>
              </Select>
            ) : (
              <input
                type="text"
                value={clientInfo.businessType ? getBusinessTypeLabel(clientInfo.businessType) : ''}
                disabled
                className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50"
                readOnly
                placeholder="Не указан"
              />
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Адрес</label>
            <input 
              type="text" 
              value={clientInfo.address} 
              onChange={(e) => setClientInfo({...clientInfo, address: e.target.value})}
              disabled={!editClientInfo}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Режим работы</label>
            <div className="bg-white rounded-lg border border-gray-200 p-3 mb-2">
              <div className="text-xs text-gray-500 mb-1">Время работы</div>
              <input 
                type="text" 
                value={clientInfo.workingHours} 
                onChange={(e) => setClientInfo({...clientInfo, workingHours: e.target.value})}
                disabled={!editClientInfo}
                className="w-full text-base font-medium text-gray-900 bg-transparent border-0 p-0 focus:outline-none"
                placeholder="ежедневно 9:00-21:00"
              />
            </div>
            {editClientInfo && (
              <div className="flex flex-wrap gap-2">
                {['Будни', 'Ежедневно', 'Круглосуточно', 'Выходные', 'Перерыв'].map(option => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => {
                      let newValue = clientInfo.workingHours || '';
                      
                      if (option === 'Ежедневно') {
                        newValue = 'ежедневно 9:00-21:00';
                      } else if (option === 'Будни') {
                        newValue = 'будни 9:00-21:00';
                      } else if (option === 'Круглосуточно') {
                        newValue = 'круглосуточно';
                      } else if (option === 'Выходные') {
                        // Добавляем через запятую, если уже есть время работы
                        if (newValue && !newValue.includes('выходные')) {
                          newValue = newValue + ', выходные 10:00-18:00';
                        } else if (!newValue) {
                          newValue = 'выходные 10:00-18:00';
                        } else {
                          // Если уже есть, заменяем
                          newValue = newValue.replace(/выходные\s+\d{1,2}:\d{2}-\d{1,2}:\d{2}/g, 'выходные 10:00-18:00');
                        }
                      } else if (option === 'Перерыв') {
                        // Добавляем через запятую, если уже есть время работы
                        if (newValue && !newValue.includes('перерыв')) {
                          newValue = newValue + ', перерыв 12:00-13:00';
                        } else if (!newValue) {
                          newValue = 'перерыв 12:00-13:00';
                        } else {
                          // Если уже есть, заменяем
                          newValue = newValue.replace(/перерыв\s+\d{1,2}:\d{2}-\d{1,2}:\d{2}/g, 'перерыв 12:00-13:00');
                        }
                      }
                      
                      setClientInfo({...clientInfo, workingHours: newValue});
                    }}
                    className="px-4 py-2 rounded-full text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
                  >
                    {option}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="md:col-span-2">
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">Ссылки на карты</label>
              {editClientInfo && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    setClientInfo({
                      ...clientInfo,
                      mapLinks: [...clientInfo.mapLinks, { url: '' }]
                    })
                  }
                >
                  + Добавить ссылку
                </Button>
              )}
            </div>
            <div className="space-y-2">
              {(clientInfo.mapLinks && clientInfo.mapLinks.length ? clientInfo.mapLinks : [{ url: '' }]).map((link, idx) => (
                <div key={idx} className="flex gap-2 items-center">
                  <input
                    type="url"
                    value={link.url}
                    onChange={(e) => {
                      const updated = [...clientInfo.mapLinks];
                      updated[idx] = { ...updated[idx], url: e.target.value };
                      setClientInfo({ ...clientInfo, mapLinks: updated });
                    }}
                    disabled={!editClientInfo}
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-md"
                    placeholder="Система сама определит, какими картами вы пользуетесь"
                  />
                  {link.mapType && (
                    <span className="text-xs text-gray-500 w-16 text-center">
                      {link.mapType}
                    </span>
                  )}
                  {editClientInfo && (
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => {
                        const updated = [...clientInfo.mapLinks];
                        updated.splice(idx, 1);
                        setClientInfo({ ...clientInfo, mapLinks: updated });
                      }}
                    >
                      Удалить
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
        {editClientInfo && (
          <div className="mt-4 flex justify-end">
            <div className="flex gap-2">
              <Button 
                onClick={() => {
                  console.log('🟢 Кнопка "Сохранить" нажата, savingClientInfo:', savingClientInfo, 'editClientInfo:', editClientInfo);
                  handleSaveClientInfo();
                }} 
                disabled={savingClientInfo}
              >
                {savingClientInfo ? 'Сохранение...' : 'Сохранить'}
              </Button>
              <Button onClick={() => setEditClientInfo(false)} variant="outline">Отмена</Button>
            </div>
          </div>
        )}
      </div>

      {/* Точки сети */}
      {isNetwork && networkLocations.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900 flex items-center">
              <Network className="h-5 w-5 mr-2 text-blue-600" />
              Точки сети
            </h2>
            <span className="text-sm text-gray-500">
              {networkLocations.length} {networkLocations.length === 1 ? 'точка' : networkLocations.length < 5 ? 'точки' : 'точек'}
            </span>
          </div>
          {loadingLocations ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
              <p className="text-sm text-gray-500">Загрузка точек сети...</p>
            </div>
          ) : (
            <div className="space-y-3">
              {networkLocations.map((location) => (
                <div
                  key={location.id}
                  className="p-4 border border-gray-200 rounded-lg hover:bg-blue-50 hover:border-blue-300 cursor-pointer transition-colors"
                  onClick={() => {
                    if (onBusinessChange) {
                      onBusinessChange(location.id);
                    }
                  }}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <p className="font-medium text-gray-900">{location.name}</p>
                      {location.description && (
                        <p className="text-sm text-gray-500 mt-1">{location.description}</p>
                      )}
                      {location.address && (
                        <p className="text-xs text-gray-400 mt-1 flex items-center">
                          <MapPin className="h-3 w-3 mr-1" />
                          {location.address}
                        </p>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (onBusinessChange) {
                          onBusinessChange(location.id);
                        }
                      }}
                    >
                      Открыть
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

