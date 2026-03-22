import React, { useState, useEffect } from 'react';
import { ChevronDown, Building2, Users } from 'lucide-react';

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
    const groups: Record<string, Business[]> = {};
    const ids: Record<string, boolean> = {};

    for (const business of visibleBusinesses) {
      const networkId = String(business.network_id || '').trim();
      if (!networkId) continue;
      if (!groups[networkId]) {
        groups[networkId] = [];
      }
      groups[networkId].push(business);
    }

    for (const networkId of Object.keys(groups)) {
      const group = groups[networkId] || [];
      const explicitParent = group.find((item) => String(item.id) === networkId);
      if (explicitParent) {
        ids[explicitParent.id] = true;
        continue;
      }
      const sortedGroup = [...group].sort((left, right) => {
        const leftCreated = String(left.created_at || '');
        const rightCreated = String(right.created_at || '');
        return leftCreated.localeCompare(rightCreated);
      });
      const head = sortedGroup[0];
      if (head?.id) {
        ids[head.id] = true;
      }
    }

    return ids;
  }, [visibleBusinesses]);

  const getBusinessDisplayName = (business: Business) => {
    const baseName = String(business.name || '').trim() || 'Без названия';
    if (networkRepresentativeIds[business.id]) {
      return `${baseName} (материнская)`;
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
    const networkHeads = Object.entries(networks).map(([networkId, group]) => {
      const explicitParent = group.find((business) => String(business.id) === String(networkId));
      if (explicitParent) {
        return explicitParent;
      }
      return [...group].sort((a, b) => {
        const leftCreated = String(a.created_at || '');
        const rightCreated = String(b.created_at || '');
        return leftCreated.localeCompare(rightCreated);
      })[0];
    });

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
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2 px-3 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
      >
        <Building2 className="w-4 h-4 text-gray-600" />
        <div className="text-left">
          <div className="text-sm font-medium text-gray-900">
            {selectedBusiness ? getBusinessDisplayName(selectedBusiness) : 'Выберите бизнес'}
          </div>
          {isSuperadmin && selectedBusiness?.owner_name && (
            <div className="text-xs text-gray-500">
              {selectedBusiness.owner_name}
            </div>
          )}
        </div>
        <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-60 overflow-y-auto">
          {hasBusinesses && mainBusinesses.map((business) => (
            <button
              key={business.id}
              onClick={() => handleBusinessSelect(business)}
              className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${selectedBusiness?.id === business.id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                }`}
            >
              <div className="flex items-start space-x-3">
                <Building2 className="w-4 h-4 text-gray-600 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900 truncate">
                    {getBusinessDisplayName(business)}
                  </div>
                  {business.description && (
                    <div className="text-xs text-gray-500 mt-1 line-clamp-2">
                      {business.description}
                    </div>
                  )}
                  {isSuperadmin && business.owner_name && (
                    <div className="flex items-center space-x-1 mt-1">
                      <Users className="w-3 h-3 text-gray-400" />
                      <span className="text-xs text-gray-500">
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
