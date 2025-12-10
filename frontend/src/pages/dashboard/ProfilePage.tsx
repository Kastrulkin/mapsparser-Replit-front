import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from '@/components/ui/select';
import { newAuth } from '@/lib/auth_new';

export const ProfilePage = () => {
  const { user, currentBusinessId, currentBusiness, updateBusiness } = useOutletContext<any>();
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
        const response = await fetch(`${window.location.origin}/api/client-info`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
          }
        });
        if (response.ok) {
          const data = await response.json();
          setClientInfo(data);
        }
      } catch (error) {
        console.error('Ошибка загрузки информации о бизнесе:', error);
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
    setSavingClientInfo(true);
    try {
      const response = await fetch(`${window.location.origin}/api/client-info`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({
          ...clientInfo,
          businessId: currentBusinessId
        })
      });

      if (response.ok) {
        setEditClientInfo(false);
        setSuccess('Информация о бизнесе сохранена');
        
        // Обновляем название бизнеса в списке businesses, чтобы оно отображалось в выпадающем списке
        if (currentBusinessId && updateBusiness) {
          updateBusiness(currentBusinessId, {
            name: clientInfo.businessName,
            address: clientInfo.address,
            working_hours: clientInfo.workingHours
          });
        }
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Ошибка сохранения информации');
      }
    } catch (error) {
      console.error('Ошибка сохранения информации:', error);
      setError('Ошибка сохранения информации');
    } finally {
      setSavingClientInfo(false);
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
            <div className="space-y-2">
              {(clientInfo.mapLinks || []).map((link, idx) => (
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
                    placeholder="https://yandex.ru/maps/... или https://maps.google.com/..."
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
              {!clientInfo.mapLinks?.length && (
                <div className="text-sm text-gray-500">
                  Пока нет ссылок. Добавьте ссылку на Яндекс или Google карты.
                </div>
              )}
            </div>
          </div>
        </div>
        {editClientInfo && (
          <div className="mt-4 flex justify-end">
            <div className="flex gap-2">
              <Button onClick={handleSaveClientInfo} disabled={savingClientInfo}>
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

