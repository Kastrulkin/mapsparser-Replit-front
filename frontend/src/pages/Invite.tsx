import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { Button } from '../components/ui/button';

const Invite: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inviteData, setInviteData] = useState<{
    email: string;
    url: string;
    inviterEmail: string;
  } | null>(null);

  useEffect(() => {
    const email = searchParams.get('email');
    const url = searchParams.get('url');
    
    if (email && url) {
      setInviteData({
        email,
        url,
        inviterEmail: 'friend@example.com' // Будет получено из email
      });
    } else {
      setError('Неверная ссылка приглашения');
    }
  }, [searchParams]);

  const handleAcceptInvite = async () => {
    if (!inviteData) return;
    
    setLoading(true);
    setError(null);

    try {
      // Перенаправляем на главную страницу с предзаполненными данными
      navigate('/', { 
        state: { 
          invitedEmail: inviteData.email,
          invitedUrl: inviteData.url,
          fromInvite: true
        } 
      });
    } catch (error) {
      setError('Ошибка при обработке приглашения');
    } finally {
      setLoading(false);
    }
  };

  if (!inviteData) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p>Загрузка приглашения...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-primary/5 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-card rounded-3xl shadow-xl border border-primary/10 p-8">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-primary/20 rounded-2xl mx-auto mb-4 flex items-center justify-center">
            <svg className="w-8 h-8 text-primary" fill="currentColor" viewBox="0 0 20 20">
              <path d="M8 9a3 3 0 100-6 3 3 0 000 6zM8 11a6 6 0 016 6H2a6 6 0 016-6zM16 7a1 1 0 10-2 0v1h-1a1 1 0 100 2h1v1a1 1 0 102 0v-1h1a1 1 0 100-2h-1V7z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-foreground mb-2">Вас пригласили!</h1>
          <p className="text-muted-foreground">
            Друг приглашает вас получить бесплатный SEO анализ
          </p>
        </div>

        <div className="space-y-4 mb-8">
          <div className="bg-muted/10 rounded-xl p-4">
            <p className="text-sm text-muted-foreground mb-1">Приглашение от:</p>
            <p className="font-medium text-foreground">{inviteData.inviterEmail}</p>
          </div>
          
          <div className="bg-muted/10 rounded-xl p-4">
            <p className="text-sm text-muted-foreground mb-1">Ваш email:</p>
            <p className="font-medium text-foreground">{inviteData.email}</p>
          </div>
          
          <div className="bg-muted/10 rounded-xl p-4">
            <p className="text-sm text-muted-foreground mb-1">Ссылка на бизнес:</p>
            <p className="font-medium text-foreground break-all">{inviteData.url}</p>
          </div>
        </div>

        {error && (
          <div className="bg-destructive/10 border border-destructive/20 rounded-xl p-4 mb-6">
            <p className="text-destructive text-sm">{error}</p>
          </div>
        )}

        <div className="space-y-3">
          <Button 
            onClick={handleAcceptInvite}
            disabled={loading}
            className="w-full"
            size="lg"
          >
            {loading ? 'Обработка...' : 'Принять приглашение'}
          </Button>
          
          <Button 
            variant="outline" 
            onClick={() => navigate('/')}
            className="w-full"
          >
            Вернуться на главную
          </Button>
        </div>

        <div className="mt-6 text-center">
          <p className="text-xs text-muted-foreground">
            Приняв приглашение, вы получите бесплатный SEO анализ вашего бизнеса
          </p>
        </div>
      </div>
    </div>
  );
};

export default Invite; 