import { useClickOutside } from '@/hooks/useClickOutside';
import { Input } from '@/components/ui/input';
import { Building2, ChevronDown, Users } from 'lucide-react';
import React, { useCallback, useEffect, useId, useRef, useState } from 'react';

interface Business {
  id: string;
  name: string;
  description?: string;
  address?: string;
  industry?: string;
  owner_email?: string;
  owner_name?: string;
  network_id?: string;
  network_name?: string;
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
  const [query, setQuery] = useState('');
  const [selectedBusiness, setSelectedBusiness] = useState<Business | null>(null);
  const switcherRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);
  const listId = useId();
  const closeSwitcher = useCallback(() => {
    setIsOpen(false);
    setQuery('');
  }, []);
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
  const showSearch = visibleBusinesses.length > 5;
  const term = query.trim().toLocaleLowerCase();
  const filteredBusinesses = showSearch && term ? visibleBusinesses.filter(business => (
    [business.name, business.address, business.network_name, isSuperadmin ? business.owner_name : '']
      .some(value => value?.toLocaleLowerCase().includes(term))
  )) : visibleBusinesses;

  const getBusinessDisplayName = (business: Business) => {
    return String(business.name || '').trim() || 'Без названия';
  };

  useEffect(() => {
    const current = visibleBusinesses.find((business) => business.id === currentBusinessId);
    setSelectedBusiness(previous => current || visibleBusinesses.find(business => business.id === previous?.id) || visibleBusinesses[0] || null);
  }, [visibleBusinesses, currentBusinessId]);

  useEffect(() => {
    if (isOpen && showSearch) searchRef.current?.focus();
  }, [isOpen, showSearch]);

  const handleBusinessSelect = (business: Business) => {
    setSelectedBusiness(business);
    onBusinessChange(business.id);
    closeSwitcher();
    triggerRef.current?.focus();
  };

  return (
    <div ref={switcherRef} className="relative min-w-0 shrink-0" onKeyDown={event => {
      if (!isOpen || event.key !== 'Escape') return;
      event.preventDefault();
      closeSwitcher();
      triggerRef.current?.focus();
    }}>
      <button
        type="button"
        ref={triggerRef}
        onClick={() => isOpen ? closeSwitcher() : setIsOpen(true)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={isOpen ? listId : undefined}
        className="flex h-12 w-[clamp(11rem,18vw,16rem)] min-w-0 max-w-full items-center gap-3 rounded-xl border border-gray-300 bg-white px-3 py-2 transition-colors hover:bg-gray-50"
      >
        <Building2 className="h-5 w-5 shrink-0 text-gray-600" />
        <div className="min-w-0 flex-1 text-left">
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
        <div className="absolute left-0 top-full z-50 mt-2 flex max-h-[min(70vh,34rem)] w-[min(34rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-xl ring-1 ring-black/5">
          {showSearch && <div className="shrink-0 border-b p-2">
            <Input ref={searchRef} type="search" aria-label="Поиск бизнеса" placeholder="Название или адрес" value={query}
              onChange={event => setQuery(event.target.value)} />
          </div>}
          {filteredBusinesses.length === 0 && <p role="status" className="px-4 py-3 text-sm text-muted-foreground">
            {term ? 'Ничего не найдено' : 'Нет доступных бизнесов'}
          </p>}
          <div id={listId} role="listbox" aria-label="Бизнесы" className="min-h-0 overflow-y-auto overflow-x-hidden">
          {filteredBusinesses.map((business) => (
            <button
              key={business.id}
              type="button"
              role="option"
              aria-selected={selectedBusiness?.id === business.id}
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
                  {(business.address || business.description) && (
                    <div className="mt-1 line-clamp-2 break-words text-sm leading-5 text-gray-500">
                      {business.address || business.description}
                    </div>
                  )}
                  {business.network_name && (
                    <div className="mt-1 text-xs text-gray-500">{business.network_name}</div>
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
        </div>
      )}
    </div>
  );
};
