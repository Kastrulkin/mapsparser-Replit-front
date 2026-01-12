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

  // Фильтруем точки сети - показываем только основные аккаунты
  // Фильтруем точки сети - показываем независимые точки ИЛИ "главную" точку сети (самую старую)
  const mainBusinesses = React.useMemo(() => {
    const independent = [];
    const networks: { [key: string]: Business[] } = {};

    // Группируем
    for (const b of businesses) {
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
    const networkHeads = Object.values(networks).map((group: any[]) => {
      // Сортируем по created_at (по возрастанию - старые первые), если поля нет, оставляем как есть
      // Предполагаем, что created_at приходит строкой ISO
      return group.sort((a, b) => {
        if (a.created_at && b.created_at) {
          return a.created_at.localeCompare(b.created_at);
        }
        return 0;
      })[0];
    });

    return [...independent, ...networkHeads];
  }, [businesses]);

  useEffect(() => {
    if (mainBusinesses.length > 0) {
      const current = mainBusinesses.find(b => b.id === currentBusinessId) || mainBusinesses[0];
      setSelectedBusiness(current);
    }
  }, [mainBusinesses, currentBusinessId]);

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
            {selectedBusiness?.name || 'Выберите бизнес'}
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
                    {business.name}
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
