import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Plus, Trash2, Building2, MapPin, Link as LinkIcon } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { NetworkXMLImport } from './NetworkXMLImport';

interface Network {
  id: string;
  name: string;
  description?: string;
}

interface BusinessLocation {
  id?: string;
  name: string;
  address: string;
  yandex_url: string;
}

export const NetworkManagement: React.FC = () => {
  const { toast } = useToast();
  const { currentBusinessId, currentBusiness } = useOutletContext<any>();
  const [isNetwork, setIsNetwork] = useState<boolean>(false);
  const [networks, setNetworks] = useState<Network[]>([]);
  const [selectedNetworkId, setSelectedNetworkId] = useState<string>('');
  const [networkName, setNetworkName] = useState<string>('');
  const [networkDescription, setNetworkDescription] = useState<string>('');
  const [locations, setLocations] = useState<BusinessLocation[]>([
    { name: '', address: '', yandex_url: '' }
  ]);
  const [loading, setLoading] = useState(false);
  const [creatingNetwork, setCreatingNetwork] = useState(false);

  useEffect(() => {
    loadNetworks();
  }, []);

  const loadNetworks = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch('/api/networks', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      if (data.success && data.networks) {
        setNetworks(data.networks);
        if (data.networks.length > 0 && !selectedNetworkId) {
          setSelectedNetworkId(data.networks[0].id);
        }
      }
    } catch (error) {
      console.error('Ошибка загрузки сетей:', error);
    }
  };

  const handleCreateNetwork = async () => {
    if (!networkName.trim()) {
      toast({
        title: 'Ошибка',
        description: 'Введите название сети',
        variant: 'destructive'
      });
      return;
    }

    setCreatingNetwork(true);
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('Токен авторизации не найден. Пожалуйста, войдите в систему.');
      }

      const response = await fetch('/api/networks', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: networkName,
          description: networkDescription
        })
      });

      // Проверяем, что ответ не пустой
      const text = await response.text();
      if (!text) {
        throw new Error('Пустой ответ от сервера');
      }

      let data;
      try {
        data = JSON.parse(text);
      } catch (e) {
        console.error('Ошибка парсинга JSON:', text);
        throw new Error(`Ошибка ответа сервера: ${text.substring(0, 100)}`);
      }

      if (!response.ok) {
        throw new Error(data.error || `Ошибка ${response.status}: ${response.statusText}`);
      }

      if (data.success) {
        const newNetworkId = data.network_id;
        toast({
          title: 'Успешно',
          description: 'Сеть создана'
        });
        setNetworkName('');
        setNetworkDescription('');
        await loadNetworks();
        setSelectedNetworkId(newNetworkId);

        // Автоматически добавляем текущий бизнес в сеть, если он есть
        if (currentBusinessId && currentBusiness) {
          try {
            const addResponse = await fetch(`/api/networks/${newNetworkId}/businesses`, {
              method: 'POST',
              headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
              },
              body: JSON.stringify({
                business_id: currentBusinessId
              })
            });

            if (addResponse.ok) {
              toast({
                title: 'Успешно',
                description: `Бизнес "${currentBusiness.name}" добавлен в сеть`
              });
              // Перезагружаем страницу для обновления списка бизнесов
              setTimeout(() => window.location.reload(), 1000);
            }
          } catch (error) {
            console.error('Ошибка добавления бизнеса в сеть:', error);
          }
        }
      } else {
        throw new Error(data.error || 'Ошибка создания сети');
      }
    } catch (error: any) {
      console.error('Ошибка создания сети:', error);
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось создать сеть',
        variant: 'destructive'
      });
    } finally {
      setCreatingNetwork(false);
    }
  };

  const handleAddLocation = () => {
    setLocations([...locations, { name: '', address: '', yandex_url: '' }]);
  };

  const handleRemoveLocation = (index: number) => {
    if (locations.length > 1) {
      setLocations(locations.filter((_, i) => i !== index));
    }
  };

  const handleLocationChange = (index: number, field: keyof BusinessLocation, value: string) => {
    const updated = [...locations];
    updated[index] = { ...updated[index], [field]: value };
    setLocations(updated);
  };

  const handleSaveLocations = async () => {
    if (!selectedNetworkId) {
      toast({
        title: 'Ошибка',
        description: 'Выберите или создайте сеть',
        variant: 'destructive'
      });
      return;
    }

    const validLocations = locations.filter(loc => loc.name.trim());
    if (validLocations.length === 0) {
      toast({
        title: 'Ошибка',
        description: 'Добавьте хотя бы одну точку с названием',
        variant: 'destructive'
      });
      return;
    }

    setLoading(true);
    try {
      const token = localStorage.getItem('auth_token');

      for (const location of validLocations) {
        const response = await fetch(`/api/networks/${selectedNetworkId}/businesses`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            name: location.name,
            address: location.address,
            yandex_url: location.yandex_url
          })
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error || 'Ошибка добавления точки');
        }
      }

      toast({
        title: 'Успешно',
        description: `Добавлено точек: ${validLocations.length}`
      });

      // Очищаем форму
      setLocations([{ name: '', address: '', yandex_url: '' }]);

      // Перезагружаем страницу для обновления списка бизнесов
      window.location.reload();
    } catch (error: any) {
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось добавить точки',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Управление сетью</CardTitle>
        <CardDescription>
          Выберите тип организации: одна точка или сеть с несколькими точками
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Выбор типа */}
        <div className="space-y-4">
          <Label>Тип организации</Label>
          <div className="flex gap-4">
            <Button
              variant={!isNetwork ? 'default' : 'outline'}
              onClick={() => setIsNetwork(false)}
            >
              Одна точка
            </Button>
            <Button
              variant={isNetwork ? 'default' : 'outline'}
              onClick={async () => {
                setIsNetwork(true);
                // Если есть текущий бизнес и есть сеть - добавляем бизнес в сеть
                if (currentBusinessId && selectedNetworkId) {
                  try {
                    const token = localStorage.getItem('auth_token');
                    const response = await fetch(`/api/networks/${selectedNetworkId}/businesses`, {
                      method: 'POST',
                      headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                      },
                      body: JSON.stringify({
                        business_id: currentBusinessId
                      })
                    });

                    if (response.ok) {
                      toast({
                        title: 'Успешно',
                        description: `Бизнес добавлен в сеть`
                      });
                      setTimeout(() => window.location.reload(), 1000);
                    }
                  } catch (error) {
                    console.error('Ошибка добавления бизнеса в сеть:', error);
                  }
                }
              }}
            >
              Сеть
            </Button>
          </div>
        </div>

        {/* Форма создания сети */}
        {isNetwork && (
          <div className="space-y-4 border-t pt-4">
            <div>
              <Label>Создать новую сеть</Label>
              <div className="space-y-3 mt-2">
                <div>
                  <Label htmlFor="network-name">Название сети *</Label>
                  <Input
                    id="network-name"
                    value={networkName}
                    onChange={(e) => setNetworkName(e.target.value)}
                    placeholder="Например: Сеть салонов красоты"
                  />
                </div>
                <div>
                  <Label htmlFor="network-description">Описание (необязательно)</Label>
                  <Input
                    id="network-description"
                    value={networkDescription}
                    onChange={(e) => setNetworkDescription(e.target.value)}
                    placeholder="Краткое описание сети"
                  />
                </div>
                <Button
                  onClick={handleCreateNetwork}
                  disabled={creatingNetwork || !networkName.trim()}
                >
                  {creatingNetwork ? 'Создание...' : 'Создать сеть'}
                </Button>
              </div>
            </div>

            {/* Выбор существующей сети */}
            {networks.length > 0 && (
              <div>
                <Label>Или выберите существующую сеть</Label>
                <select
                  className="mt-2 w-full px-3 py-2 border border-gray-300 rounded-md"
                  value={selectedNetworkId}
                  onChange={(e) => setSelectedNetworkId(e.target.value)}
                >
                  {networks.map((network) => (
                    <option key={network.id} value={network.id}>
                      {network.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* XML Import для сети */}
            {selectedNetworkId && (
              <div className="border-t pt-4">
                <NetworkXMLImport
                  networkId={selectedNetworkId}
                  onImportComplete={() => {
                    toast({
                      title: 'Обновление',
                      description: 'Список точек обновлен'
                    });
                    setTimeout(() => window.location.reload(), 1000);
                  }}
                />
              </div>
            )}

            {/* Добавление точек сети */}
            {(selectedNetworkId || networks.length > 0) && (
              <div className="space-y-4 border-t pt-4">
                <div className="flex items-center justify-between">
                  <Label>Точки сети</Label>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleAddLocation}
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Добавить точку
                  </Button>
                </div>

                {locations.map((location, index) => (
                  <Card key={index} className="p-4">
                    <div className="flex items-start justify-between mb-3">
                      <h4 className="font-medium">Точка {index + 1}</h4>
                      {locations.length > 1 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveLocation(index)}
                        >
                          <Trash2 className="w-4 h-4 text-red-500" />
                        </Button>
                      )}
                    </div>
                    <div className="space-y-3">
                      <div>
                        <Label htmlFor={`location-name-${index}`}>
                          <Building2 className="w-4 h-4 inline mr-1" />
                          Название точки *
                        </Label>
                        <Input
                          id={`location-name-${index}`}
                          value={location.name}
                          onChange={(e) => handleLocationChange(index, 'name', e.target.value)}
                          placeholder="Например: Салон на Невском"
                        />
                      </div>
                      <div>
                        <Label htmlFor={`location-address-${index}`}>
                          <MapPin className="w-4 h-4 inline mr-1" />
                          Адрес
                        </Label>
                        <Input
                          id={`location-address-${index}`}
                          value={location.address}
                          onChange={(e) => handleLocationChange(index, 'address', e.target.value)}
                          placeholder="Например: г. Санкт-Петербург, Невский пр., 1"
                        />
                      </div>
                      <div>
                        <Label htmlFor={`location-yandex-${index}`}>
                          <LinkIcon className="w-4 h-4 inline mr-1" />
                          Ссылка на карты
                        </Label>
                        <Input
                          id={`location-yandex-${index}`}
                          type="url"
                          value={location.yandex_url}
                          onChange={(e) => handleLocationChange(index, 'yandex_url', e.target.value)}
                          placeholder="https://yandex.ru/maps/org/..."
                        />
                      </div>
                    </div>
                  </Card>
                ))}

                <Button
                  onClick={handleSaveLocations}
                  disabled={loading || !selectedNetworkId}
                  className="w-full"
                >
                  {loading ? 'Сохранение...' : 'Сохранить точки'}
                </Button>
              </div>
            )}
          </div>
        )}

        {!isNetwork && (
          <div className="text-sm text-gray-500 border-t pt-4">
            Вы работаете с одной точкой. Для управления несколькими точками выберите "Сеть".
          </div>
        )}
      </CardContent>
    </Card>
  );
};

