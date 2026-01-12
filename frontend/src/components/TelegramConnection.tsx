import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Alert, AlertDescription } from './ui/alert';
import { Copy, Check, Loader2, Bot } from 'lucide-react';
import { useLanguage } from '@/i18n/LanguageContext';

interface TelegramConnectionProps {
  currentBusinessId?: string | null;
}

const TelegramConnection: React.FC<TelegramConnectionProps> = ({ currentBusinessId }) => {
  const [bindToken, setBindToken] = useState<string | null>(null);
  const [tokenExpiresAt, setTokenExpiresAt] = useState<string | null>(null);
  const [isLinked, setIsLinked] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const { t, language } = useLanguage();

  useEffect(() => {
    // Сбрасываем статус при смене бизнеса
    setIsLinked(false);

    if (currentBusinessId) {
      checkStatus();
    }
  }, [currentBusinessId]);

  const checkStatus = async () => {
    if (!currentBusinessId) {
      setIsLinked(false);
      return;
    }

    try {
      const token = localStorage.getItem('auth_token');
      const url = new URL(`${window.location.origin}/api/telegram/bind/status`);
      url.searchParams.append('business_id', currentBusinessId);

      console.log('Checking Telegram status for business:', currentBusinessId);

      const response = await fetch(url.toString(), {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        console.log('✅ Telegram status for business', currentBusinessId, ':', data);
        // Явно проверяем, что is_linked === true (не просто truthy значение)
        setIsLinked(data.is_linked === true);
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error('Status check error:', response.status, errorData);
        setIsLinked(false);
      }
    } catch (e) {
      console.error('Status check error:', e);
      setIsLinked(false);
    }
  };

  const generateToken = async () => {
    if (!currentBusinessId) {
      setError(t.dashboard.settings.telegram.selectBusiness);
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${window.location.origin}/api/telegram/bind`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ business_id: currentBusinessId })
      });

      if (response.ok) {
        const data = await response.json();
        setBindToken(data.token);
        setTokenExpiresAt(data.expires_at);
        setSuccess(t.dashboard.settings.telegram.successToken);
      } else {
        const errorData = await response.json();
        setError(errorData.error || t.dashboard.settings.telegram.errorToken);
      }
    } catch (e: any) {
      setError(t.error + ': ' + e.message);
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
      setError('Failed to copy to clipboard');
    }
  };

  const getBotLink = () => {
    if (!bindToken) return '';
    const botUsername = 'BeautyBotPro_bot'; // Имя бота в Telegram
    return `https://t.me/${botUsername}?start=${bindToken}`;
  };

  return (
    <Card key={currentBusinessId || 'no-business'}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bot className="w-5 h-5" />
          {t.dashboard.settings.telegram.title}
        </CardTitle>
        <CardDescription>
          {t.dashboard.settings.telegram.description}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLinked && currentBusinessId ? (
          <Alert>
            <AlertDescription>
              {t.dashboard.settings.telegram.connected}
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
                  {t.dashboard.settings.telegram.instruction}
                </p>
                <ol className="list-decimal list-inside space-y-2 text-sm text-gray-600">
                  <li>{t.dashboard.settings.telegram.step1}</li>
                  <li>{t.dashboard.settings.telegram.step2}</li>
                  <li>{t.dashboard.settings.telegram.step3} <code className="bg-gray-100 px-1 rounded">/start &lt;code&gt;</code></li>
                  <li>{t.dashboard.settings.telegram.step4}</li>
                </ol>
                <Button onClick={generateToken} disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      {t.dashboard.settings.telegram.generating}
                    </>
                  ) : (
                    t.dashboard.settings.telegram.generateToken
                  )}
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                <Alert>
                  <AlertDescription>
                    {t.dashboard.settings.telegram.tokenExpires} {new Date(tokenExpiresAt || '').toLocaleString(language === 'ru' ? 'ru-RU' : 'en-US')}
                  </AlertDescription>
                </Alert>

                <div className="space-y-2">
                  <label className="text-sm font-medium">{t.dashboard.settings.telegram.bindCode}</label>
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
                  <label className="text-sm font-medium">{t.dashboard.settings.telegram.directLink}</label>
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
                  <p className="text-sm font-medium mb-2">{t.dashboard.settings.telegram.instructionTitle}</p>
                  <ol className="list-decimal list-inside space-y-1 text-sm text-gray-700">
                    <li>{t.dashboard.settings.telegram.manualStep1}</li>
                    <li>{t.dashboard.settings.telegram.manualStep2}</li>
                    <li>{t.dashboard.settings.telegram.manualStep3} <code className="bg-white px-1 rounded">/start {bindToken}</code></li>
                    <li>{t.dashboard.settings.telegram.manualStep4}</li>
                  </ol>
                </div>

                <Button variant="outline" onClick={() => {
                  setBindToken(null);
                  setTokenExpiresAt(null);
                  setSuccess(null);
                  setError(null);
                }}>
                  {t.dashboard.settings.telegram.generateNew}
                </Button>
              </div>
            )}
          </>
        )}

        <div className="pt-4 border-t">
          <h4 className="text-sm font-medium mb-2">{t.dashboard.settings.telegram.featuresTitle}</h4>
          <ul className="list-disc list-inside space-y-1 text-sm text-gray-600">
            <li>{t.dashboard.settings.telegram.feature1}</li>
            <li>{t.dashboard.settings.telegram.feature2}</li>
            <li>{t.dashboard.settings.telegram.feature3}</li>
            <li>{t.dashboard.settings.telegram.feature4}</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  );
};

export default TelegramConnection;
