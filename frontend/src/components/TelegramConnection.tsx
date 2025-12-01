import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Alert, AlertDescription } from './ui/alert';
import { Copy, Check, Loader2, Bot } from 'lucide-react';

const TelegramConnection: React.FC = () => {
  const [bindToken, setBindToken] = useState<string | null>(null);
  const [tokenExpiresAt, setTokenExpiresAt] = useState<string | null>(null);
  const [isLinked, setIsLinked] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${window.location.origin}/api/telegram/bind/status`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setIsLinked(data.is_linked || false);
      }
    } catch (e) {
      console.error('Ошибка проверки статуса:', e);
    }
  };

  const generateToken = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${window.location.origin}/api/telegram/bind`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setBindToken(data.token);
        setTokenExpiresAt(data.expires_at);
        setSuccess('Токен создан! Используйте его для привязки бота.');
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Ошибка создания токена');
      }
    } catch (e: any) {
      setError('Ошибка подключения к серверу: ' + e.message);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      setError('Не удалось скопировать в буфер обмена');
    }
  };

  const getBotLink = () => {
    if (!bindToken) return '';
    const botUsername = 'BeautyBotPro_bot'; // Имя бота в Telegram
    return `https://t.me/${botUsername}?start=${bindToken}`;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bot className="w-5 h-5" />
          Подключение Telegram-бота
        </CardTitle>
        <CardDescription>
          Подключите Telegram-бота для управления аккаунтом прямо из мессенджера
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLinked ? (
          <Alert>
            <AlertDescription>
              ✅ Telegram-бот успешно подключен! Вы можете использовать все функции бота.
            </AlertDescription>
          </Alert>
        ) : (
          <>
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {success && (
              <Alert>
                <AlertDescription>{success}</AlertDescription>
              </Alert>
            )}

            {!bindToken ? (
              <div className="space-y-4">
                <p className="text-sm text-gray-600">
                  Для подключения Telegram-бота:
                </p>
                <ol className="list-decimal list-inside space-y-2 text-sm text-gray-600">
                  <li>Нажмите кнопку ниже для генерации кода привязки</li>
                  <li>Откройте Telegram и найдите нашего бота</li>
                  <li>Отправьте боту команду: <code className="bg-gray-100 px-1 rounded">/start &lt;код&gt;</code></li>
                  <li>Готово! Бот будет подключен к вашему аккаунту</li>
                </ol>
                <Button onClick={generateToken} disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Генерирую токен...
                    </>
                  ) : (
                    'Сгенерировать код привязки'
                  )}
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                <Alert>
                  <AlertDescription>
                    ⏰ Токен действителен до: {new Date(tokenExpiresAt || '').toLocaleString('ru-RU')}
                  </AlertDescription>
                </Alert>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Код привязки:</label>
                  <div className="flex gap-2">
                    <Input
                      value={bindToken}
                      readOnly
                      className="font-mono"
                    />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => copyToClipboard(bindToken)}
                    >
                      {copied ? (
                        <Check className="w-4 h-4 text-green-600" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Или используйте прямую ссылку:</label>
                  <div className="flex gap-2">
                    <Input
                      value={getBotLink()}
                      readOnly
                      className="font-mono text-xs"
                    />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => copyToClipboard(getBotLink())}
                    >
                      {copied ? (
                        <Check className="w-4 h-4 text-green-600" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </Button>
                  </div>
                </div>

                <div className="p-4 bg-blue-50 rounded-lg">
                  <p className="text-sm font-medium mb-2">📱 Инструкция:</p>
                  <ol className="list-decimal list-inside space-y-1 text-sm text-gray-700">
                    <li>Откройте Telegram</li>
                    <li>Найдите бота (имя бота будет указано после создания)</li>
                    <li>Отправьте команду: <code className="bg-white px-1 rounded">/start {bindToken}</code></li>
                    <li>Или просто перейдите по ссылке выше</li>
                  </ol>
                </div>

                <Button variant="outline" onClick={() => {
                  setBindToken(null);
                  setTokenExpiresAt(null);
                  setSuccess(null);
                  setError(null);
                }}>
                  Сгенерировать новый код
                </Button>
              </div>
            )}
          </>
        )}

        <div className="pt-4 border-t">
          <h4 className="text-sm font-medium mb-2">Возможности бота:</h4>
          <ul className="list-disc list-inside space-y-1 text-sm text-gray-600">
            <li>💰 Добавление транзакций (фото чека или текстом)</li>
            <li>📊 Оптимизация услуг для SEO</li>
            <li>⚙️ Изменение данных компании (название, адрес, карты)</li>
            <li>📈 Просмотр статистики (в разработке)</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  );
};

export default TelegramConnection;

