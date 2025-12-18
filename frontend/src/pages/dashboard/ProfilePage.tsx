import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from '@/components/ui/select';
import { newAuth } from '@/lib/auth_new';

export const ProfilePage = () => {
  const { user, currentBusinessId, currentBusiness, updateBusiness, businesses } = useOutletContext<any>();
  const [editMode, setEditMode] = useState(false);
  const [editClientInfo, setEditClientInfo] = useState(false);
  const [savingClientInfo, setSavingClientInfo] = useState(false);
  const [form, setForm] = useState({ email: "", phone: "", name: "" });
  const [clientInfo, setClientInfo] = useState({
    businessName: '',
    businessType: '',
    address: '',
    workingHours: '',
    mapLinks: [] as { id?: string; url: string; mapType?: string }[]
  });
  const [parseStatus, setParseStatus] = useState<'idle' | 'processing' | 'done' | 'error'>('idle');
  const [parseErrors, setParseErrors] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setForm({
        email: user.email || "",
        phone: user.phone || "",
        name: user.name || ""
      });
    }
  }, [user]);

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
          // Нормализуем mapLinks: сервер возвращает объекты с полями id, url, mapType, createdAt
          const normalizedMapLinks = (data.mapLinks && Array.isArray(data.mapLinks) 
            ? data.mapLinks.map((link: any) => ({
                id: link.id,
                url: link.url || '',
                mapType: link.mapType || link.map_type
              }))
            : []);
          console.log('📋 Нормализованные mapLinks:', normalizedMapLinks);
          setClientInfo({
            ...data,
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
    setParseStatus('processing');
    setParseErrors([]);
    setSavingClientInfo(true);
    try {
      // Фильтруем пустые ссылки перед отправкой
      const validMapLinks = (clientInfo.mapLinks || [])
        .map(link => typeof link === 'string' ? link : link.url)
        .filter(url => url && url.trim());
      
      const payload = {
        ...clientInfo,
        businessId: effectiveBusinessId,
        mapLinks: validMapLinks.map(url => ({ url: url.trim() }))
      };
      
      console.log('Отправляю данные:', payload);

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
          // Нормализуем mapLinks
          const normalizedMapLinks = (reloadData.mapLinks && Array.isArray(reloadData.mapLinks) 
            ? reloadData.mapLinks.map((link: any) => ({
                id: link.id,
                url: link.url || '',
                mapType: link.mapType || link.map_type
              }))
            : []);
          console.log('📋 Нормализованные mapLinks после перезагрузки:', normalizedMapLinks);
          setClientInfo({
            ...reloadData,
            mapLinks: normalizedMapLinks
          });
        } else {
          // Если перезагрузка не удалась, используем данные из ответа
          console.log('⚠️ Перезагрузка не удалась, использую данные из ответа');
          if (Array.isArray(data.mapLinks)) {
            const normalizedMapLinks = data.mapLinks.map((link: any) => ({
              id: link.id,
              url: link.url || '',
              mapType: link.mapType || link.map_type
            }));
            setClientInfo({ ...clientInfo, mapLinks: normalizedMapLinks });
          }
        }
        
        setEditClientInfo(false);
        setSuccess('Информация о бизнесе сохранена');
        
        // Обновляем название бизнеса в списке businesses
        if (effectiveBusinessId && updateBusiness) {
          updateBusiness(effectiveBusinessId, {
            name: clientInfo.businessName,
            address: clientInfo.address,
            working_hours: clientInfo.workingHours
          });
        }

        // Проверяем статус парсинга
        if (data.parseStatus === 'queued') {
          setParseStatus('queued');
          // Начинаем периодическую проверку статуса
          checkParseStatus();
        } else if (data.parseStatus === 'error') {
          setParseStatus('error');
          setParseErrors(data.parseErrors || []);
          setError('Парсер завершился с ошибкой');
        } else {
          setParseStatus('done');
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
        setParseStatus('error');
      }
    } catch (error) {
      console.error('Ошибка сохранения информации:', error);
      setError('Ошибка сохранения информации');
      setParseStatus('error');
    } finally {
      setSavingClientInfo(false);
    }
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
        
        if (status === 'done' || status === 'error' || status === 'captcha') {
          setParseStatus(status);
          // Останавливаем проверку
          return;
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
          <h2 className="text-xl font-semibold text-gray-900">Профиль</h2>
          {!editMode && (
            <Button onClick={() => setEditMode(true)}>Редактировать</Button>
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
              disabled={!editMode}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Телефон</label>
            <input 
              type="tel"
              value={form.phone}
              onChange={(e) => setForm({...form, phone: e.target.value})}
              disabled={!editMode}
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
          {!editClientInfo && (
            <Button onClick={() => setEditClientInfo(true)}>Редактировать</Button>
          )}
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
                </SelectContent>
              </Select>
            ) : (
              <input
                type="text"
                value={clientInfo.businessType}
                disabled
                className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50"
                readOnly
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
            <input 
              type="text" 
              value={clientInfo.workingHours} 
              onChange={(e) => setClientInfo({...clientInfo, workingHours: e.target.value})}
              disabled={!editClientInfo}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
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
            <p className="text-xs text-gray-500 mb-2">
              Добавьте ссылку на ваш бизнес на картах — раз в неделю мы будем получать данные, чтобы отслеживать прогресс и давать советы по оптимизации.
              {' '}
              Данные с карт будут сохраняться на вкладке{' '}
              <a href="/dashboard/progress" className="text-blue-600 underline" target="_blank" rel="noreferrer">
                Прогресс
              </a>.
            </p>
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
              <div className="flex justify-end">
                <Button
                  size="sm"
                  className="bg-blue-600 hover:bg-blue-700"
                  disabled={savingClientInfo}
                  onClick={() => {
                    console.log('🔵 Кнопка "Запустить парсер данных" нажата, savingClientInfo:', savingClientInfo);
                    // Парсер запускается вместе с сохранением ссылок
                    handleSaveClientInfo();
                  }}
                >
                  Запустить парсер данных
                </Button>
              </div>
              <div className="text-xs text-gray-600">
                Статус парсинга:{' '}
                {parseStatus === 'queued' && <span className="text-yellow-600">в очереди...</span>}
                {parseStatus === 'processing' && <span className="text-blue-600">в процессе...</span>}
                {parseStatus === 'done' && <span className="text-green-600">завершён</span>}
                {parseStatus === 'error' && <span className="text-red-600">ошибка</span>}
                {parseStatus === 'captcha' && <span className="text-orange-600">требуется капча</span>}
                {parseStatus === 'idle' && <span className="text-gray-500">ожидает запуска</span>}
              </div>
              {parseErrors.length > 0 && (
                <div className="text-xs text-red-600">
                  Ошибки: {parseErrors.join('; ')}
                </div>
              )}
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
    </div>
  );
};

