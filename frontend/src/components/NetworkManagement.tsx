import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Plus, Trash2, Building2, MapPin, Link as LinkIcon } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { NetworkXMLImport } from './NetworkXMLImport';
import { useLanguage } from '@/i18n/LanguageContext';

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
  const { t } = useLanguage();
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

  // Определяем, является ли текущий бизнес частью сети
  useEffect(() => {
    if (currentBusiness && currentBusiness.network_id) {
      setIsNetwork(true);
      setSelectedNetworkId(currentBusiness.network_id);
    }
  }, [currentBusiness]);

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
        title: t.common.error,
        description: t.dashboard.network.create.emptyName,
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
          title: t.common.success,
          description: t.dashboard.network.create.success
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
                title: t.common.success,
                description: `${t.dashboard.network.businessAdded}: "${currentBusiness.name}"`
              });
              // Перезагружаем страницу для обновления списка бизнесов
              setTimeout(() => window.location.reload(), 1000);
            }
          } catch (error) {
            console.error('Ошибка добавления бизнеса в сеть:', error);
          }
        }
      } else {
        throw new Error(data.error || t.dashboard.network.create.error);
      }
    } catch (error: any) {
      console.error('Ошибка создания сети:', error);
      toast({
        title: t.common.error,
        description: error.message || t.dashboard.network.create.error,
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
        title: t.common.error,
        description: t.dashboard.network.points.selectNetwork,
        variant: 'destructive'
      });
      return;
    }

    const validLocations = locations.filter(loc => loc.name.trim());
    if (validLocations.length === 0) {
      toast({
        title: t.common.error,
        description: t.dashboard.network.points.empty,
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
          throw new Error(error.error || t.dashboard.network.points.error);
        }
      }

      toast({
        title: t.common.success,
        description: `${t.dashboard.network.points.success}: ${validLocations.length}`
      });

      // Очищаем форму
      setLocations([{ name: '', address: '', yandex_url: '' }]);

      // Перезагружаем страницу для обновления списка бизнесов
      window.location.reload();
    } catch (error: any) {
      toast({
        title: t.common.error,
        description: error.message || t.dashboard.network.points.error,
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t.dashboard.network.title}</CardTitle>
        <CardDescription>
          {t.dashboard.network.subtitle}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Выбор типа */}
        <div className="space-y-4">
          <Label>{t.dashboard.network.type}</Label>
          <div className="flex gap-4">
            <Button
              variant={!isNetwork ? 'default' : 'outline'}
              onClick={() => setIsNetwork(false)}
            >
              {t.dashboard.network.singlePoint}
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
                        title: t.common.success,
                        description: t.dashboard.network.businessAdded
                      });
                      setTimeout(() => window.location.reload(), 1000);
                    }
                  } catch (error) {
                    console.error('Ошибка добавления бизнеса в сеть:', error);
                  }
                }
              }}
            >
              {t.dashboard.network.network}
            </Button>
          </div>
        </div>

        {/* Форма создания сети */}
        {isNetwork && (
          <div className="space-y-4 border-t pt-4">
            <div>
              <Label>{t.dashboard.network.create.title}</Label>
              <div className="space-y-3 mt-2">
                <div>
                  <Label htmlFor="network-name">{t.dashboard.network.create.name}</Label>
                  <Input
                    id="network-name"
                    value={networkName}
                    onChange={(e) => setNetworkName(e.target.value)}
                    placeholder={t.dashboard.network.create.namePlaceholder}
                  />
                </div>
                <div>
                  <Label htmlFor="network-description">{t.dashboard.network.create.description}</Label>
                  <Input
                    id="network-description"
                    value={networkDescription}
                    onChange={(e) => setNetworkDescription(e.target.value)}
                    placeholder={t.dashboard.network.create.descriptionPlaceholder}
                  />
                </div>
                <Button
                  onClick={handleCreateNetwork}
                  disabled={creatingNetwork || !networkName.trim()}
                >
                  {creatingNetwork ? t.dashboard.network.create.creating : t.dashboard.network.create.submit}
                </Button>
              </div>
            </div>

            {/* Выбор существующей сети */}
            {networks.length > 0 && (
              <div>
                <Label>{t.dashboard.network.select.label}</Label>
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
                      title: t.common.success,
                      description: t.dashboard.network.points.success
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
                  <Label>{t.dashboard.network.points.title}</Label>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleAddLocation}
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    {t.dashboard.network.points.add}
                  </Button>
                </div>

                {locations.map((location, index) => (
                  <Card key={index} className="p-4">
                    <div className="flex items-start justify-between mb-3">
                      <h4 className="font-medium">{t.dashboard.network.points.point} {index + 1}</h4>
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
                          {t.dashboard.network.points.name}
                        </Label>
                        <Input
                          id={`location-name-${index}`}
                          value={location.name}
                          onChange={(e) => handleLocationChange(index, 'name', e.target.value)}
                          placeholder={t.dashboard.network.points.namePlaceholder}
                        />
                      </div>
                      <div>
                        <Label htmlFor={`location-address-${index}`}>
                          <MapPin className="w-4 h-4 inline mr-1" />
                          {t.dashboard.network.points.address}
                        </Label>
                        <Input
                          id={`location-address-${index}`}
                          value={location.address}
                          onChange={(e) => handleLocationChange(index, 'address', e.target.value)}
                          placeholder={t.dashboard.network.points.addressPlaceholder}
                        />
                      </div>
                      <div>
                        <Label htmlFor={`location-yandex-${index}`}>
                          <LinkIcon className="w-4 h-4 inline mr-1" />
                          {t.dashboard.network.points.mapLink}
                        </Label>
                        <Input
                          id={`location-yandex-${index}`}
                          type="url"
                          value={location.yandex_url}
                          onChange={(e) => handleLocationChange(index, 'yandex_url', e.target.value)}
                          placeholder={t.dashboard.network.points.mapLinkPlaceholder}
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
                  {loading ? t.dashboard.network.points.saving : t.dashboard.network.points.save}
                </Button>
              </div>
            )}
          </div>
        )}

        {!isNetwork && (
          <div className="text-sm text-gray-500 border-t pt-4">
            {t.dashboard.network.singlePointMessage}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

