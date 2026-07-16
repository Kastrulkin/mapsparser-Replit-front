import { useCallback, useEffect, useState } from 'react';
import { ArrowRight, RefreshCw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import logo from '@/assets/images/logo.png';
import { Button } from '@/components/ui/button';
import { API_URL } from '@/config/api';
import { newAuth } from '@/lib/auth_new';


type DemoSessionResponse = {
  success?: boolean;
  token?: string;
  business_id?: string;
  start_path?: string;
  error?: string;
  message?: string;
};

const ensureRobotsMeta = () => {
  let element = document.querySelector<HTMLMetaElement>('meta[name="robots"]');
  if (!element) {
    element = document.createElement('meta');
    element.name = 'robots';
    document.head.appendChild(element);
  }
  return element;
};

export default function DemoEntryPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  const enterDemo = useCallback(async () => {
    setError(null);
    try {
      const storedToken = window.localStorage.getItem('demo_auth_token');
      if (storedToken) {
        newAuth.activateDemoSession(storedToken);
        const existingUser = await newAuth.getCurrentUser();
        if (existingUser?.demo_mode) {
          const scopeBusinessId = existingUser.demo_scope_business_id || existingUser.businesses?.[0]?.id;
          if (scopeBusinessId) window.localStorage.setItem('demo_selectedBusinessId', scopeBusinessId);
          navigate('/dashboard/operator', { replace: true });
          return;
        }
      }

      const response = await fetch(`${API_URL}/api/public-demo/session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      const data: DemoSessionResponse = await response.json();
      if (!response.ok || !data.token || !data.business_id) {
        throw new Error(data.message || data.error || 'Демо сейчас недоступно');
      }
      newAuth.activateDemoSession(data.token);
      window.localStorage.setItem('demo_selectedBusinessId', data.business_id);
      navigate(data.start_path || '/dashboard/operator', { replace: true });
    } catch (requestError) {
      newAuth.deactivateDemoSession(true);
      setError(requestError instanceof Error ? requestError.message : 'Не удалось открыть демо');
    }
  }, [navigate]);

  useEffect(() => {
    document.title = 'Интерактивное демо LocalOS';
    const robots = ensureRobotsMeta();
    const previousContent = robots.content;
    robots.content = 'noindex,nofollow';
    void enterDemo();
    return () => {
      robots.content = previousContent;
    };
  }, [attempt, enterDemo]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <div className="w-full max-w-md text-center">
        <div className="mx-auto h-28 w-28 overflow-hidden rounded-full border border-slate-200 bg-white shadow-sm">
          <img
            src={logo}
            alt="Робот LocalOS"
            className="h-40 w-40 -translate-x-6 -translate-y-2 scale-125 object-cover object-top"
          />
        </div>
        <h1 className="mt-6 text-2xl font-semibold text-slate-950">Открываем «Рога и копыта»</h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Готовим личную демо-сессию. Данные аккаунта не изменятся.
        </p>
        {error ? (
          <div className="mt-6 rounded-lg border border-rose-200 bg-white p-4 text-left">
            <p className="text-sm text-rose-700">{error}</p>
            <Button type="button" className="mt-4 w-full gap-2" onClick={() => setAttempt((value) => value + 1)}>
              <RefreshCw className="h-4 w-4" />
              Повторить
            </Button>
          </div>
        ) : (
          <div className="mt-6 inline-flex min-h-10 items-center gap-2 text-sm font-medium text-slate-700" aria-live="polite">
            <span className="h-2 w-2 animate-pulse rounded-full bg-orange-500 motion-reduce:animate-none" />
            Загружаем витрину
            <ArrowRight className="h-4 w-4" />
          </div>
        )}
      </div>
    </main>
  );
}
