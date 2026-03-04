import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';

import { BusinessHealthWidget } from '@/components/business/BusinessHealthWidget';
import CardAuditPanel from '@/components/CardAuditPanel';
import MapParseTable from '@/components/MapParseTable';
import NetworkHealthDashboard from '@/components/NetworkHealthDashboard';
import { useLanguage } from '@/i18n/LanguageContext';
import { NetworkDashboardPage } from './network/NetworkDashboardPage';

export const ProgressPage = () => {
  const { currentBusinessId } = useOutletContext<any>();
  const [isNetworkMaster, setIsNetworkMaster] = useState(false);
  const [isNetworkMember, setIsNetworkMember] = useState(false);
  const [resolvedNetworkId, setResolvedNetworkId] = useState<string | null>(null);
  const [networkStatusLoading, setNetworkStatusLoading] = useState(true);
  const { t } = useLanguage();

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
            'Content-Type': 'application/json',
          },
        });

        if (!response.ok) {
          setIsNetworkMaster(false);
          setIsNetworkMember(false);
          setResolvedNetworkId(null);
          return;
        }

        const data = await response.json();
        setIsNetworkMaster(Boolean(data.is_network_master ?? data.is_network));
        setIsNetworkMember(Boolean(data.is_network_member));
        setResolvedNetworkId(data.network_id || null);
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

  if (isNetworkMaster) {
    return (
      <div className="space-y-6">
        <div className="rounded-xl border bg-white p-4 md:p-6">
          <NetworkDashboardPage embedded businessId={currentBusinessId} />
        </div>

        <div className="rounded-xl border bg-white p-4 md:p-6">
          <h2 className="text-3xl font-bold tracking-tight">
            📊 {t.networkHealth?.title || 'Состояние сети'}
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {t.networkHealth?.subtitle || 'Мониторинг ключевых метрик по всем точкам сети.'}
          </p>
        </div>

        <NetworkHealthDashboard
          networkId={resolvedNetworkId || currentBusinessId}
          businessId={null}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border bg-white p-4 md:p-6">
        <NetworkDashboardPage embedded businessId={currentBusinessId} />
      </div>

      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {t.dashboard?.progress?.title || 'Прогресс'}
          </h1>
          <p className="mt-1 text-gray-600">
            {t.dashboard?.progress?.subtitle || 'Общая картина бизнеса, текущее состояние карточки и история парсинга.'}
          </p>
        </div>
      </div>

      <BusinessHealthWidget businessId={currentBusinessId} className="mb-6" />

      {isNetworkMember && (
        <NetworkHealthDashboard
          networkId={resolvedNetworkId}
          businessId={null}
        />
      )}

      <CardAuditPanel businessId={currentBusinessId} />

      <MapParseTable businessId={currentBusinessId} />
    </div>
  );
};
