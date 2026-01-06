import { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { useToast } from '../hooks/use-toast';
import { newAuth } from '../lib/auth_new';
import { Plus, Trash2, Network, CheckCircle2, XCircle, Power, AlertCircle } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';

interface Proxy {
  id: string;
  type: string;
  host: string;
  port: number;
  is_active: boolean;
  is_working: boolean;
  success_count: number;
  failure_count: number;
  last_used_at: string | null;
  last_checked_at: string | null;
}

export const ProxyManagement = () => {
  const [proxies, setProxies] = useState<Proxy[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const { toast } = useToast();

  // Форма добавления прокси
  const [formData, setFormData] = useState({
    type: 'http',
    host: '',
    port: '',
    username: '',
    password: '',
  });

  useEffect(() => {
    loadProxies();
  }, []);

  const loadProxies = async () => {
    setLoading(true);
    try {
      const token = await newAuth.getToken();
      const response = await fetch('/api/admin/proxies', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setProxies(data.proxies || []);
      } else {
        const error = await response.json();
        toast({
          title: 'Ошибка загрузки',
          description: error.error || 'Не удалось загрузить список прокси',
          variant: 'destructive',
        });
      }
    } catch (error) {
      console.error('Ошибка загрузки прокси:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось загрузить список прокси',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAddProxy = async () => {
    if (!formData.host || !formData.port) {
      toast({
        title: 'Ошибка валидации',
        description: 'Заполните обязательные поля: Host и Port',
        variant: 'destructive',
      });
      return;
    }

    try {
      const token = await newAuth.getToken();
      const response = await fetch('/api/admin/proxies', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          type: formData.type,
          host: formData.host,
          port: parseInt(formData.port),
          username: formData.username || undefined,
          password: formData.password || undefined,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        toast({
          title: 'Ошибка',
          description: error.error || 'Не удалось добавить прокси',
          variant: 'destructive',
        });
        return;
      }

      toast({
        title: 'Успешно',
        description: 'Прокси добавлен',
      });
      setShowAddDialog(false);
      setFormData({
        type: 'http',
        host: '',
        port: '',
        username: '',
        password: '',
      });
      loadProxies();
    } catch (error) {
      console.error('Ошибка добавления прокси:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось добавить прокси',
        variant: 'destructive',
      });
    }
  };

  const handleDeleteProxy = async (proxyId: string) => {
    if (!confirm('Вы уверены, что хотите удалить этот прокси?')) {
      return;
    }

    setDeletingId(proxyId);
    try {
      const token = await newAuth.getToken();
      const response = await fetch(`/api/admin/proxies/${proxyId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const error = await response.json();
        toast({
          title: 'Ошибка',
          description: error.error || 'Не удалось удалить прокси',
          variant: 'destructive',
        });
        return;
      }

      toast({
        title: 'Успешно',
        description: 'Прокси удален',
      });
      loadProxies();
    } catch (error) {
      console.error('Ошибка удаления прокси:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось удалить прокси',
        variant: 'destructive',
      });
    } finally {
      setDeletingId(null);
    }
  };

  const handleToggleProxy = async (proxyId: string) => {
    try {
      const token = await newAuth.getToken();
      const response = await fetch(`/api/admin/proxies/${proxyId}/toggle`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const error = await response.json();
        toast({
          title: 'Ошибка',
          description: error.error || 'Не удалось изменить статус прокси',
          variant: 'destructive',
        });
        return;
      }

      const data = await response.json();
      toast({
        title: 'Успешно',
        description: data.is_active ? 'Прокси включен' : 'Прокси выключен',
      });
      loadProxies();
    } catch (error) {
      console.error('Ошибка переключения прокси:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось изменить статус прокси',
        variant: 'destructive',
      });
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Никогда';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    return new Intl.DateTimeFormat('ru-RU', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-16">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
            <p className="text-muted-foreground">Загрузка прокси...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Add Button */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Управление прокси</h2>
          <p className="text-muted-foreground mt-1">
            Ротация IP-адресов для обхода блокировок Яндекс
          </p>
        </div>
        <Button onClick={() => setShowAddDialog(true)} className="shadow-md hover:shadow-lg transition-shadow">
          <Plus className="w-4 h-4 mr-2" />
          Добавить прокси
        </Button>
      </div>

      {/* Empty State */}
      {proxies.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <div className="p-4 rounded-full bg-muted mb-4">
              <Network className="w-8 h-8 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Прокси не настроены</h3>
            <p className="text-muted-foreground text-center max-w-md mb-4">
              Добавьте хотя бы один прокси, чтобы включить ротацию IP-адресов.
              Это поможет обойти блокировки и капчу от Яндекс.
            </p>
            <div className="bg-muted/50 rounded-lg p-4 max-w-md text-sm text-muted-foreground space-y-2">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div>
                  <strong>Для тестирования:</strong> можно использовать бесплатные прокси-листы
                </div>
              </div>
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div>
                  <strong>Для продакшена:</strong> рекомендуется использовать резидентные прокси
                  (Smartproxy, IPRoyal, Bright Data)
                </div>
              </div>
            </div>
            <Button onClick={() => setShowAddDialog(true)} variant="outline" className="mt-6">
              <Plus className="w-4 h-4 mr-2" />
              Добавить первый прокси
            </Button>
          </CardContent>
        </Card>
      ) : (
        /* Proxies List */
        <div className="grid gap-4">
          {proxies.map((proxy) => {
            let statusColor: string;
            let StatusIcon: typeof CheckCircle2 | typeof XCircle | typeof Power;
            
            if (!proxy.is_active) {
              statusColor = 'bg-muted text-muted-foreground border-border';
              StatusIcon = Power;
            } else if (proxy.is_working) {
              statusColor = 'bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/20';
              StatusIcon = CheckCircle2;
            } else {
              statusColor = 'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/20';
              StatusIcon = XCircle;
            }

            return (
              <Card key={proxy.id} className="hover:shadow-md transition-shadow">
                <CardContent className="p-6">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 space-y-3">
                      {/* Header */}
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg border ${statusColor}`}>
                          <StatusIcon className="w-5 h-5" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="font-semibold text-lg">
                              {proxy.host}:{proxy.port}
                            </h3>
                            <Badge variant="outline" className="text-xs">
                              {proxy.type.toUpperCase()}
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground mt-1">
                            ID: {proxy.id.slice(0, 8)}...
                          </p>
                        </div>
                      </div>

                      {/* Stats */}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-2">
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">Успешных запросов</p>
                          <p className="text-lg font-semibold text-green-600 dark:text-green-400">
                            {proxy.success_count}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">Ошибок</p>
                          <p className="text-lg font-semibold text-red-600 dark:text-red-400">
                            {proxy.failure_count}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">Последнее использование</p>
                          <p className="text-sm font-medium">
                            {formatDate(proxy.last_used_at)}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">Статус</p>
                          <div className="flex items-center gap-2">
                            <Badge
                              variant={proxy.is_active ? 'default' : 'secondary'}
                              className="text-xs"
                            >
                              {proxy.is_active ? 'Активен' : 'Неактивен'}
                            </Badge>
                            {proxy.is_working && proxy.is_active && (
                              <Badge variant="outline" className="text-xs border-green-500 text-green-700 dark:text-green-400">
                                Работает
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex flex-col gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleToggleProxy(proxy.id)}
                        disabled={deletingId === proxy.id}
                      >
                        <Power className="w-4 h-4 mr-2" />
                        {proxy.is_active ? 'Выключить' : 'Включить'}
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleDeleteProxy(proxy.id)}
                        disabled={deletingId === proxy.id}
                      >
                        {deletingId === proxy.id ? (
                          <>
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                            Удаление...
                          </>
                        ) : (
                          <>
                            <Trash2 className="w-4 h-4 mr-2" />
                            Удалить
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Add Proxy Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Добавить прокси</DialogTitle>
            <DialogDescription>
              Введите данные прокси-сервера. Пароль будет зашифрован при сохранении.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="type">Тип прокси *</Label>
              <Select
                value={formData.type}
                onValueChange={(value) => setFormData({ ...formData, type: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Выберите тип" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="http">HTTP</SelectItem>
                  <SelectItem value="socks5">SOCKS5</SelectItem>
                  <SelectItem value="socks4">SOCKS4</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="host">Host *</Label>
              <Input
                id="host"
                placeholder="proxy.example.com"
                value={formData.host}
                onChange={(e) => setFormData({ ...formData, host: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="port">Port *</Label>
              <Input
                id="port"
                type="number"
                placeholder="8080"
                value={formData.port}
                onChange={(e) => setFormData({ ...formData, port: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="username">Username (опционально)</Label>
              <Input
                id="username"
                placeholder="username"
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password (опционально)</Label>
              <Input
                id="password"
                type="password"
                placeholder="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddDialog(false)}>
              Отмена
            </Button>
            <Button onClick={handleAddProxy}>
              <Plus className="w-4 h-4 mr-2" />
              Добавить
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

