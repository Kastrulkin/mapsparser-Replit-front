import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { clearLeadJourneyIntent, clearLeadJourneyToken, journeyActionRoute, readLeadJourneyToken, resolveStoredLeadJourney, type JourneyAction } from '@/lib/leadJourney';
import { featureFlags } from '@/config/featureFlags';

const VerifyEmail: React.FC = () => {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('Подтверждаем email...');
  const navigate = useNavigate();

  useEffect(() => {
    const verify = async () => {
      const params = new URLSearchParams(window.location.search);
      const token = params.get('token') || '';

      if (!token) {
        setStatus('error');
        setMessage('Ссылка подтверждения недействительна.');
        return;
      }

      try {
        const response = await fetch('/api/auth/verify-email', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token }),
        });
        const data = await response.json();

        if (!response.ok || !data.success) {
          setStatus('error');
          setMessage(data.error || 'Не удалось подтвердить email.');
          return;
        }

        if (data.token) {
          localStorage.setItem('auth_token', data.token);
        }

        setStatus('success');
        if (data.journey_action && featureFlags.journeyPostAuthRedirect) {
          const action: JourneyAction = data.journey_action;
          clearLeadJourneyToken();
          clearLeadJourneyIntent();
          setMessage('Email подтверждён. Возвращаемся к выбранному действию...');
          setTimeout(() => navigate(journeyActionRoute(action), { replace: true }), 1200);
          return;
        }
        if (readLeadJourneyToken() && featureFlags.journeyPostAuthRedirect) {
          setMessage('Email подтверждён. Возвращаемся к выбранному действию...');
          try {
            const resolved = await resolveStoredLeadJourney();
            setTimeout(() => navigate(resolved?.route || '/dashboard/today', { replace: true }), 1200);
          } catch (journeyError) {
            setStatus('error');
            setMessage(`Email подтверждён, но персональный сценарий пока не открылся: ${journeyError instanceof Error ? journeyError.message : 'повторите попытку'}`);
          }
          return;
        }
        const selectedTier = localStorage.getItem('selectedTier') || '';
        const selectedTierSource = localStorage.getItem('selectedTierSource') || '';
        const shouldStartPricingCheckout = Boolean(selectedTier && selectedTierSource === 'pricing');
        if (shouldStartPricingCheckout) {
          setMessage('Email подтверждён. Открываем оплату выбранного тарифа...');
          localStorage.removeItem('selectedTier');
          localStorage.removeItem('selectedTierSource');
          setTimeout(() => navigate(`/dashboard/profile?payment=required&source=pricing&autostart=1&tier=${encodeURIComponent(selectedTier)}#subscription`, { replace: true }), 1200);
          return;
        }

        setMessage('Email подтверждён. Открываем кабинет без автоматической оплаты...');
        setTimeout(() => navigate('/dashboard/profile?onboarding=1', { replace: true }), 1200);
      } catch (error) {
        setStatus('error');
        setMessage('Не удалось подтвердить email. Попробуйте открыть ссылку ещё раз.');
      }
    };

    verify();
  }, [navigate]);

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm">
        <h1 className="text-2xl font-semibold text-slate-900">Подтверждение email</h1>
        <p className={`mt-3 text-sm ${status === 'error' ? 'text-red-600' : 'text-slate-600'}`}>
          {message}
        </p>
        {status === 'loading' && (
          <div className="mx-auto mt-5 h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-blue-600" />
        )}
        {status === 'error' && (
          <button
            type="button"
            className="btn-iridescent mt-5 min-h-10 rounded-md px-4 py-2 text-sm"
            onClick={() => navigate('/login')}
          >
            Вернуться ко входу
          </button>
        )}
      </div>
    </div>
  );
};

export default VerifyEmail;
