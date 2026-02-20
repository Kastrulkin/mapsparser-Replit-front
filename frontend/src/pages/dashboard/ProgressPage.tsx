import { useState, useEffect } from 'react';
import { useOutletContext, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';

import { BusinessHealthWidget } from '@/components/business/BusinessHealthWidget';
import MapParseTable from '@/components/MapParseTable';
import MapRecommendations from '@/components/MapRecommendations';
import { BusinessGrowthPlan } from '@/components/BusinessGrowthPlan';
import { MetricsHistoryCharts } from '@/components/MetricsHistoryCharts';
import NetworkHealthDashboard from '@/components/NetworkHealthDashboard';
import FinancialMetrics from '@/components/FinancialMetrics';
import { useLanguage } from '@/i18n/LanguageContext';

export const ProgressPage = () => {
  const { currentBusinessId } = useOutletContext<any>();
  const [showWizard, setShowWizard] = useState(false);
  // Wizard state
  const [wizardLocation, setWizardLocation] = useState<string>('');
  const [wizardExperience, setWizardExperience] = useState<string>('');
  const [wizardClients, setWizardClients] = useState<string>('');
  const [wizardCRM, setWizardCRM] = useState<string>('');
  const [wizardAverageCheck, setWizardAverageCheck] = useState<string>('');
  const [wizardRevenue, setWizardRevenue] = useState<string>('');
  const [savingWizard, setSavingWizard] = useState(false);
  const [loadingWizard, setLoadingWizard] = useState(false);

  const [isNetworkMaster, setIsNetworkMaster] = useState(false);
  const [isNetworkMember, setIsNetworkMember] = useState(false);
  const [resolvedNetworkId, setResolvedNetworkId] = useState<string | null>(null);
  const [networkStatusLoading, setNetworkStatusLoading] = useState(true);
  const { t } = useLanguage();
  const navigate = useNavigate();

  // Wizard constants
  const experienceKeys = ['zeroToSix', 'sixToTwelve', 'oneToThree', 'threePlus'] as const;
  const locationKeys = ['home', 'mall', 'yard', 'highway', 'center', 'suburbs', 'metro'] as const;

  // Check if current business is network master
  useEffect(() => {
    const checkNetwork = async () => {
      if (!currentBusinessId) {
        setIsNetworkMaster(false);
        setIsNetworkMember(false);
        setResolvedNetworkId(null);
        setNetworkStatusLoading(false);
        return;
      }

      try {
        setNetworkStatusLoading(true);
        const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
        const response = await fetch(`/api/business/${currentBusinessId}/network-locations`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (response.ok) {
          const data = await response.json();
          setIsNetworkMaster(Boolean(data.is_network_master ?? data.is_network));
          setIsNetworkMember(Boolean(data.is_network_member));
          setResolvedNetworkId(data.network_id || null);
        } else {
          setIsNetworkMaster(false);
          setIsNetworkMember(false);
          setResolvedNetworkId(null);
        }
      } catch (error) {
        console.error('Error checking network status:', error);
        setIsNetworkMaster(false);
        setIsNetworkMember(false);
        setResolvedNetworkId(null);
      } finally {
        setNetworkStatusLoading(false);
      }
    };

    checkNetwork();
  }, [currentBusinessId]);

  if (networkStatusLoading && currentBusinessId) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-56 bg-gray-100 animate-pulse rounded-md" />
        <div className="h-40 w-full bg-gray-100 animate-pulse rounded-xl" />
      </div>
    );
  }

  // Load wizard data
  useEffect(() => {
    const loadWizardData = async () => {
      if (!showWizard || !currentBusinessId) return;
      setLoadingWizard(true);
      try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(`/api/business/${currentBusinessId}/optimization-wizard`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.ok) {
          const data = await response.json();
          if (data.success && data.data) {
            setWizardExperience(data.data.experience || '');
            setWizardClients(data.data.clients || '');
            setWizardCRM(data.data.crm || '');
            setWizardLocation(data.data.location || '');
            setWizardAverageCheck(data.data.average_check || '');
            setWizardRevenue(data.data.revenue || '');
          }
        }
      } catch (err) {
        console.error('Error loading wizard data:', err);
      } finally {
        setLoadingWizard(false);
      }
    };
    loadWizardData();
  }, [showWizard, currentBusinessId]);

  // NETWORK VIEW
  if (isNetworkMaster) {
    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h2 className="text-3xl font-bold tracking-tight">📊 {t.networkHealth?.title || "Состояние сети"}</h2>
        </div>
        <NetworkHealthDashboard
          networkId={resolvedNetworkId || currentBusinessId}
          businessId={null}
        />
        <FinancialMetrics />
      </div>
    );
  }

  // STANDARD VIEW (Single Location)
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t.dashboard?.progress?.title || "Прогресс"}</h1>
          <p className="text-gray-600 mt-1">{t.dashboard?.progress?.subtitle || "Отслеживайте развитие вашего бизнеса"}</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setShowWizard(true)}>{t.dashboard?.progress?.wizard?.button || "Мастер оптимизации"}</Button>
        </div>
      </div>

      <BusinessHealthWidget businessId={currentBusinessId} className="mb-6" />
      {isNetworkMember && (
        <NetworkHealthDashboard
          networkId={resolvedNetworkId}
          businessId={null}
        />
      )}
      <BusinessGrowthPlan businessId={currentBusinessId} />

      <div className="mt-8 mb-4">
        <h2 className="text-2xl font-bold tracking-tight">{t.dashboard?.progress?.charts?.title || "Метрики Бизнеса"}</h2>
        <p className="text-muted-foreground">{t.dashboard?.progress?.charts?.subtitle || "История изменений показателей"}</p>
      </div>

      <MetricsHistoryCharts businessId={currentBusinessId} />
      <MapRecommendations businessId={currentBusinessId} />
      <MapParseTable businessId={currentBusinessId} />

      {/* WIZARD MODAL */}
      {showWizard && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-[100]" onClick={() => setShowWizard(false)}>
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center p-6 border-b border-gray-200">
              <h2 className="text-2xl font-bold text-gray-900">{t.dashboard?.progress?.wizard?.title || "Мастер оптимизации"}</h2>
              <Button onClick={() => setShowWizard(false)} variant="outline" size="sm">✕</Button>
            </div>
            <div className="p-6 overflow-auto max-h-[calc(90vh-120px)] bg-gradient-to-br from-white to-gray-50/50">
              <div className="space-y-4">
                <p className="text-gray-600 mb-4">{t.dashboard?.progress?.wizard?.intro || "Заполните данные"}</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard?.progress?.wizard?.experience || "Опыт работы"}</label>
                    <div className="flex flex-wrap gap-2">
                      {experienceKeys.map(key => (
                        <span key={key} onClick={() => setWizardExperience(key)}
                          className={`px-3 py-1 rounded-md text-sm cursor-pointer ${wizardExperience === key ? 'bg-primary text-white' : 'bg-gray-100'}`}>
                          {t.dashboard?.progress?.wizard?.options?.experience?.[key] || key}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard?.progress?.wizard?.clients || "Клиентов в базе"}</label>
                    <input className="w-full px-3 py-2 border border-gray-300 rounded-md" value={wizardClients} onChange={(e) => setWizardClients(e.target.value)} />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard?.progress?.wizard?.crm || "Используемая CRM"}</label>
                    <input className="w-full px-3 py-2 border border-gray-300 rounded-md" value={wizardCRM} onChange={(e) => setWizardCRM(e.target.value)} />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard?.progress?.wizard?.location || "Расположение"}</label>
                    <div className="flex flex-wrap gap-2">
                      {locationKeys.map(key => (
                        <span key={key} onClick={() => setWizardLocation(key)}
                          className={`px-3 py-1 rounded-md text-sm cursor-pointer ${wizardLocation === key ? 'bg-primary text-white' : 'bg-gray-100'}`}>
                          {t.dashboard?.progress?.wizard?.options?.location?.[key] || key}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard?.progress?.wizard?.avgCheck || "Средний чек"}</label>
                    <input className="w-full px-3 py-2 border border-gray-300 rounded-md" value={wizardAverageCheck} onChange={(e) => setWizardAverageCheck(e.target.value)} />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard?.progress?.wizard?.revenue || "Выручка"}</label>
                    <input className="w-full px-3 py-2 border border-gray-300 rounded-md" value={wizardRevenue} onChange={(e) => setWizardRevenue(e.target.value)} />
                  </div>
                </div>
              </div>

              <div className="mt-6 flex justify-end pt-4 border-t border-gray-200">
                <Button onClick={async () => {
                  setSavingWizard(true);
                  try {
                    const token = localStorage.getItem('auth_token');
                    await fetch(`/api/business/${currentBusinessId}/optimization-wizard`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                      body: JSON.stringify({ experience: wizardExperience, clients: wizardClients, crm: wizardCRM, location: wizardLocation, average_check: wizardAverageCheck, revenue: wizardRevenue })
                    });
                    setShowWizard(false);
                    navigate(`/sprint?business_id=${currentBusinessId}`);
                  } catch (e) { console.error(e); } finally { setSavingWizard(false); }
                }} disabled={savingWizard}>
                  {savingWizard ? (t.dashboard?.progress?.wizard?.saving || "Сохранение...") : (t.dashboard?.progress?.wizard?.submit || "Сохранить")}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
