import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Button } from '@/components/ui/button';

import MapParseTable from '@/components/MapParseTable';
import MapRecommendations from '@/components/MapRecommendations';
import { BusinessGrowthPlan } from '@/components/BusinessGrowthPlan';
import { MetricsHistoryCharts } from '@/components/MetricsHistoryCharts';
import { useLanguage } from '@/i18n/LanguageContext';

export const ProgressPage = () => {
  const { user, currentBusinessId } = useOutletContext<any>();
  const [showWizard, setShowWizard] = useState(false);
  const [wizardLocation, setWizardLocation] = useState<string>('');
  const [wizardExperience, setWizardExperience] = useState<string>('');
  const [wizardClients, setWizardClients] = useState<string>('');
  const [wizardCRM, setWizardCRM] = useState<string>('');
  const [wizardAverageCheck, setWizardAverageCheck] = useState<string>('');
  const [wizardRevenue, setWizardRevenue] = useState<string>('');
  const [savingWizard, setSavingWizard] = useState(false);
  const [loadingWizard, setLoadingWizard] = useState(false);
  const { t } = useLanguage();

  const experienceKeys = [
    'zeroToSix',
    'sixToTwelve',
    'oneToThree',
    'threePlus'
  ] as const;

  const locationKeys = [
    'home',
    'mall',
    'yard',
    'highway',
    'center',
    'suburbs',
    'metro'
  ] as const;

  // Загружаем сохраненные данные мастера при открытии
  useEffect(() => {
    const loadWizardData = async () => {
      if (!showWizard || !currentBusinessId) return;

      setLoadingWizard(true);
      try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(`/api/business/${currentBusinessId}/optimization-wizard`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
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
        console.error('Ошибка загрузки данных мастера:', err);
      } finally {
        setLoadingWizard(false);
      }
    };

    loadWizardData();
  }, [showWizard, currentBusinessId]);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t.dashboard.progress.title}</h1>
          <p className="text-gray-600 mt-1">{t.dashboard.progress.subtitle}</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setShowWizard(true)}>{t.dashboard.progress.wizard.button}</Button>
        </div>
      </div>

      {/* Gamified Business Growth Plan */}
      <BusinessGrowthPlan businessId={currentBusinessId} />

      {/* Metrics History Graphs */}
      <MetricsHistoryCharts businessId={currentBusinessId} />


      <MapRecommendations businessId={currentBusinessId} />
      <MapParseTable businessId={currentBusinessId} />

      {showWizard && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-[100]" onClick={() => setShowWizard(false)}>
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center p-6 border-b border-gray-200">
              <h2 className="text-2xl font-bold text-gray-900">{t.dashboard.progress.wizard.title}</h2>
              <Button onClick={() => setShowWizard(false)} variant="outline" size="sm">✕</Button>
            </div>
            <div className="p-6 overflow-auto max-h-[calc(90vh-120px)] bg-gradient-to-br from-white to-gray-50/50">
              <div className="space-y-4">
                <p className="text-gray-600 mb-4">{t.dashboard.progress.wizard.intro}</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.progress.wizard.experience}</label>
                    <div className="flex flex-wrap gap-2">
                      {experienceKeys.map(key => {
                        const label = t.dashboard.progress.wizard.options.experience[key];
                        // We use the key as the value regardless of language for consistency, 
                        // or should we use the label? 
                        // Existing code used label. To avoid breaking backend validation (if any), 
                        // we should perhaps use the label string if the backend expects Russian strings?
                        // Assuming backend stores arbitrary strings, using keys is safer for multilingual support.
                        // However, legacy data might be Russian strings.
                        // Let's use the KEY as value.
                        // Wait, if I use key 'zeroToSix', backend stores 'zeroToSix'.
                        // Display will work.
                        return (
                          <span
                            key={key}
                            onClick={() => setWizardExperience(wizardExperience === key ? '' : key)}
                            className={`px-3 py-1 rounded-md text-gray-700 text-sm cursor-pointer transition-colors ${wizardExperience === key
                              ? 'bg-primary text-white hover:bg-primary/90'
                              : 'bg-gray-100 hover:bg-gray-200'
                              }`}
                          >
                            {label}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.progress.wizard.clients}</label>
                    <input
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      placeholder={t.dashboard.progress.wizard.clientsPlaceholder}
                      value={wizardClients}
                      onChange={(e) => setWizardClients(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.progress.wizard.crm}</label>
                    <input
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      placeholder={t.dashboard.progress.wizard.crmPlaceholder}
                      value={wizardCRM}
                      onChange={(e) => setWizardCRM(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.progress.wizard.location}</label>
                    <div className="flex flex-wrap gap-2">
                      {locationKeys.map(key => {
                        const label = t.dashboard.progress.wizard.options.location[key];
                        return (
                          <span
                            key={key}
                            onClick={() => setWizardLocation(wizardLocation === key ? '' : key)}
                            className={`px-3 py-1 rounded-md text-gray-700 text-sm cursor-pointer transition-colors ${wizardLocation === key
                              ? 'bg-primary text-white hover:bg-primary/90'
                              : 'bg-gray-100 hover:bg-gray-200'
                              }`}
                          >
                            {label}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.progress.wizard.avgCheck}</label>
                    <input
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      placeholder={t.dashboard.progress.wizard.avgCheckPlaceholder}
                      value={wizardAverageCheck}
                      onChange={(e) => setWizardAverageCheck(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{t.dashboard.progress.wizard.revenue}</label>
                    <input
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      placeholder={t.dashboard.progress.wizard.revenuePlaceholder}
                      value={wizardRevenue}
                      onChange={(e) => setWizardRevenue(e.target.value)}
                    />
                  </div>
                </div>
              </div>
              <div className="mt-6 flex justify-end pt-4 border-t border-gray-200">
                <Button
                  onClick={async () => {
                    if (!currentBusinessId) {
                      alert(t.dashboard.progress.wizard.errors.noBusiness);
                      return;
                    }
                    setSavingWizard(true);
                    try {
                      const token = localStorage.getItem('auth_token');
                      const response = await fetch(`/api/business/${currentBusinessId}/optimization-wizard`, {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'application/json',
                          'Authorization': `Bearer ${token}`
                        },
                        body: JSON.stringify({
                          experience: wizardExperience,
                          clients: wizardClients,
                          crm: wizardCRM,
                          location: wizardLocation,
                          average_check: wizardAverageCheck,
                          revenue: wizardRevenue
                        })
                      });
                      const data = await response.json();
                      if (data.success) {
                        setShowWizard(false);
                        window.location.href = `/sprint?business_id=${currentBusinessId}`;
                      } else {
                        alert(t.dashboard.progress.wizard.errors.save + (data.error || t.dashboard.progress.wizard.errors.unknown));
                      }
                    } catch (error: any) {
                      alert(t.dashboard.progress.wizard.errors.save + error.message);
                    } finally {
                      setSavingWizard(false);
                    }
                  }}
                  disabled={savingWizard}
                >
                  {savingWizard ? t.dashboard.progress.wizard.saving : t.dashboard.progress.wizard.submit}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
