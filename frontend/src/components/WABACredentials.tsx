import { useState, useEffect } from 'react';
import { useLanguage } from '@/i18n/LanguageContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useToast } from '@/hooks/use-toast';
import { Loader2, MessageCircle, Eye, EyeOff } from 'lucide-react';

interface WABACredentialsProps {
  businessId: string | null;
  business: any;
}

export const WABACredentials = ({ businessId, business }: WABACredentialsProps) => {
  const { t } = useLanguage();
  const [phoneId, setPhoneId] = useState('');
  const [accessToken, setAccessToken] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    if (business) {
      setPhoneId(business.waba_phone_id || '');
      setAccessToken(business.waba_access_token || '');
    }
  }, [business]);

  const handleSave = async () => {
    if (!businessId) {
      toast({
        title: t.common.error,
        description: t.dashboard.settings.whatsapp.selectBusiness,
        variant: 'destructive',
      });
      return;
    }

    if (!phoneId || !accessToken) {
      toast({
        title: t.common.error,
        description: t.common.fillAllFields,
        variant: 'destructive',
      });
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch('/api/business/profile', {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          business_id: businessId,
          waba_phone_id: phoneId,
          waba_access_token: accessToken
        })
      });

      const data = await response.json();

      if (response.ok) {
        toast({
          title: t.common.success,
          description: t.dashboard.settings.whatsapp.successSave,
        });
      } else {
        toast({
          title: t.common.error,
          description: data.error || t.dashboard.settings.whatsapp.errorSave,
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: t.common.error,
        description: t.dashboard.settings.whatsapp.errorSave,
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageCircle className="h-5 w-5" />
          {t.dashboard.settings.whatsapp.title}
        </CardTitle>
        <CardDescription>
          {t.dashboard.settings.whatsapp.description}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert>
          <AlertDescription>
            {t.dashboard.settings.whatsapp.subtitle}
            {t.dashboard.settings.whatsapp.alert}
          </AlertDescription>
        </Alert>

        <div className="space-y-2">
          <Label htmlFor="waba-phone-id">{t.dashboard.settings.whatsapp.phoneIdLabel}</Label>
          <Input
            id="waba-phone-id"
            type="text"
            placeholder={t.dashboard.settings.whatsapp.phoneIdPlaceholder}
            value={phoneId}
            onChange={(e) => setPhoneId(e.target.value)}
            disabled={saving}
          />
          <p className="text-xs text-gray-500">
            {t.dashboard.settings.whatsapp.phoneIdHelp}
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="waba-access-token">{t.dashboard.settings.whatsapp.accessTokenLabel}</Label>
          <div className="relative">
            <Input
              id="waba-access-token"
              type={showToken ? 'text' : 'password'}
              placeholder={t.dashboard.settings.whatsapp.accessTokenPlaceholder}
              value={accessToken}
              onChange={(e) => setAccessToken(e.target.value)}
              disabled={saving}
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="absolute right-0 top-0 h-full px-3"
              onClick={() => setShowToken(!showToken)}
            >
              {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </Button>
          </div>
          <p className="text-xs text-gray-500">
            {t.dashboard.settings.whatsapp.accessTokenHelp}
          </p>
        </div>

        <Button
          onClick={handleSave}
          disabled={saving || !phoneId || !accessToken}
          className="w-full"
        >
          {saving ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              {t.dashboard.settings.whatsapp.saving}
            </>
          ) : (
            t.dashboard.settings.whatsapp.saveButton
          )}
        </Button>
      </CardContent>
    </Card>
  );
};

