import React, { useCallback, useRef, useState, useEffect } from 'react';
import { ChevronDown, Building2, Users } from 'lucide-react';
import { getNetworkRepresentativeIds, pickNetworkRepresentative } from '@/lib/networkRepresentative';
import { useClickOutside } from '@/hooks/useClickOutside';

interface Business {
  id: string;
  name: string;
  description?: string;
  industry?: string;
  owner_email?: string;
  owner_name?: string;
  network_id?: string;
  created_at?: string;
  moderation_status?: string;
  entity_group?: string;
  is_lead_business?: boolean;
}

interface BusinessSwitcherProps {
  businesses: Business[];
  currentBusinessId?: string;
  onBusinessChange: (businessId: string) => void;
  isSuperadmin: boolean;
}

export const BusinessSwitcher: React.FC<BusinessSwitcherProps> = ({
  businesses,
  currentBusinessId,
  onBusinessChange,
  isSuperadmin
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedBusiness, setSelectedBusiness] = useState<Business | null>(null);
  const switcherRef = useRef<HTMLDivElement | null>(null);
  const closeSwitcher = useCallback(() => setIsOpen(false), []);
  useClickOutside(switcherRef, closeSwitcher, { enabled: isOpen });
  const isLeadBusiness = (business?: Business | null) => {
    const moderationStatus = String(business?.moderation_status || '').trim().toLowerCase();
    const entityGroup = String(business?.entity_group || '').trim().toLowerCase();
    const description = String(business?.description || '').trim().toLowerCase();
    return (
      business?.is_lead_business === true ||
      moderationStatus === 'lead_outreach' ||
      entityGroup === 'lead' ||
      description.startsWith('lead shadow business for outreach lead')
    );
  };
  const visibleBusinesses = React.useMemo(
    () => businesses.filter((business) => !isLeadBusiness(business)),
    [businesses]
  );

  const networkRepresentativeIds = React.useMemo(() => {
    return getNetworkRepresentativeIds(visibleBusinesses);
  }, [visibleBusinesses]);

  const getBusinessDisplayName = (business: Business) => {
    const baseName = String(business.name || '').trim() || 'Без названия';
    if (networkRepresentativeIds[business.id]) {
      return `👑 ${baseName}`;
    }
    return baseName;
  };

  // Фильтруем точки сети - показываем только основные аккаунты
  // Фильтруем точки сети - показываем независимые точки ИЛИ "главную" точку сети (самую старую)
  const mainBusinesses = React.useMemo(() => {
    const independent = [];
    const networks: { [key: string]: Business[] } = {};

    // Группируем
    for (const b of visibleBusinesses) {
      if (!b.network_id) {
        independent.push(b);
      } else {
        if (!networks[b.network_id]) {
          networks[b.network_id] = [];
        }
        networks[b.network_id].push(b);
      }
    }

    // Выбираем "главные" точки из сетей (сортировка по дате создания, если есть, или просто первый)
    const networkHeads = Object.entries(networks)
      .map(([networkId, group]) => pickNetworkRepresentative(group, networkId))
      .filter(Boolean) as Business[];

    return [...independent, ...networkHeads];
  }, [visibleBusinesses]);

  useEffect(() => {
    if (mainBusinesses.length > 0) {
      // 1. Пытаемся найти бизнес в списке отображаемых (для независимых или главных точек)
      let current = mainBusinesses.find(b => b.id === currentBusinessId);

      // 2. Если не нашли (значит это дочерняя точка), ищем её родителя/главную точку
      if (!current && currentBusinessId) {
        const childBusiness = businesses.find(b => b.id === currentBusinessId);
        if (childBusiness?.network_id) {
          current = mainBusinesses.find(b => b.network_id === childBusiness.network_id);
        }
      }

      // 3. Если всё равно не нашли, не меняем (или ставим первый, но лучше оставить как есть во избежание скачков)
      // Но если selectedBusiness еще нет, ставим первый
      if (current) {
        setSelectedBusiness(current);
      } else if (!selectedBusiness) {
        setSelectedBusiness(mainBusinesses[0]);
      }
    }
  }, [mainBusinesses, currentBusinessId, businesses]);

  const handleBusinessSelect = (business: Business) => {
    setSelectedBusiness(business);
    onBusinessChange(business.id);
    setIsOpen(false);
  };

  const hasBusinesses = mainBusinesses.length > 0;

  return (
    <div ref={switcherRef} className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex min-h-12 max-w-[min(26rem,calc(100vw-2rem))] items-center gap-3 rounded-xl border border-gray-300 bg-white px-3 py-2 transition-colors hover:bg-gray-50"
      >
        <Building2 className="h-5 w-5 shrink-0 text-gray-600" />
        <div className="min-w-0 text-left">
          <div className="truncate text-sm font-medium text-gray-900">
            {selectedBusiness ? getBusinessDisplayName(selectedBusiness) : 'Выберите бизнес'}
          </div>
          {isSuperadmin && selectedBusiness?.owner_name && (
            <div className="truncate text-xs text-gray-500">
              {selectedBusiness.owner_name}
            </div>
          )}
        </div>
        <ChevronDown className={`h-4 w-4 shrink-0 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute left-0 top-full z-50 mt-2 max-h-[min(70vh,34rem)] w-[min(34rem,calc(100vw-2rem))] overflow-y-auto overflow-x-hidden rounded-2xl border border-gray-200 bg-white shadow-xl ring-1 ring-black/5">
          {hasBusinesses && mainBusinesses.map((business) => (
            <button
              key={business.id}
              onClick={() => handleBusinessSelect(business)}
              className={`w-full px-4 py-3 text-left transition-colors hover:bg-gray-50 ${selectedBusiness?.id === business.id ? 'border-l-4 border-blue-500 bg-blue-50 pl-3' : ''
                }`}
            >
              <div className="flex items-start gap-3">
                <Building2 className="mt-0.5 h-5 w-5 shrink-0 text-gray-600" />
                <div className="min-w-0 flex-1">
                  <div className="break-words text-base font-medium leading-6 text-gray-900">
                    {getBusinessDisplayName(business)}
                  </div>
                  {business.description && (
                    <div className="mt-1 line-clamp-2 break-words text-sm leading-5 text-gray-500">
                      {business.description}
                    </div>
                  )}
                  {isSuperadmin && business.owner_name && (
                    <div className="mt-2 flex items-center gap-1">
                      <Users className="h-3.5 w-3.5 shrink-0 text-gray-400" />
                      <span className="min-w-0 break-words text-sm text-gray-500">
                        {business.owner_name}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
