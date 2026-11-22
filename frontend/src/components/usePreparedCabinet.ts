import { useEffect, useState } from 'react';
import { HttpError, newAuth } from '@/lib/auth_new';

export const destinations = {
  services: { label: 'Услуги', menu: 'maps', href: '/dashboard/card?tab=services' },
  reviews: { label: 'Отзывы', menu: 'maps', href: '/dashboard/card?tab=reviews' },
  content: { label: 'Контент-план и посты', menu: 'content', href: '/dashboard/content' },
  partnerships: { label: 'Партнёрства', menu: 'partnerships', href: '/dashboard/partnerships' },
  influencers: { label: 'Инфлюенсеры', menu: 'influencers', href: '/dashboard/influencers' },
};

export type Section = {
  key: keyof typeof destinations;
  version: string;
  unread: boolean;
  items: { title: string; text: string }[];
};

export function usePreparedCabinet(businessId: string | null, pathname: string, search: string) {
  const [loaded, setLoaded] = useState<{ businessId: string; sections: Section[] } | null>(null);
  const [retry, setRetry] = useState(0);
  const [failed, setFailed] = useState<string | null>(null);
  const sections = loaded && loaded.businessId === businessId ? loaded.sections : [];
  const tab = new URLSearchParams(search).get('tab');
  const active = sections.find(section => (
    pathname === '/dashboard/card'
      ? section.key === (tab || 'services')
      : destinations[section.key].href === pathname
  ));
  const unreadKey = active?.unread ? active.key : null;
  const unreadVersion = active?.unread ? active.version : null;

  useEffect(() => {
    if (!businessId) return;
    let current = true;
    const apiPath = '/business/' + encodeURIComponent(businessId) + '/prepared-cabinet';
    newAuth.makeRequest(apiPath).then((data: { sections: Section[] }) => {
      if (current) {
        setLoaded({ businessId, sections: data.sections || [] });
        setFailed(null);
      }
    }).catch(error => {
      if (!current) return;
      if (error instanceof HttpError && (error.status === 401 || error.status === 403)) setLoaded(null);
      setFailed(businessId);
    });
    return () => { current = false; };
  }, [businessId, retry]);

  useEffect(() => {
    if (!businessId || !unreadKey || !unreadVersion) return;
    newAuth.makeRequest('/business/' + encodeURIComponent(businessId) + '/prepared-cabinet', {
      method: 'POST',
      body: JSON.stringify({ key: unreadKey, version: unreadVersion }),
    }).then((data: { sections: Section[] }) => {
      const reviewed = data.sections.find(section => section.key === unreadKey);
      setLoaded(previous => previous?.businessId === businessId ? {
        ...previous,
        sections: data.sections.length ? previous.sections.map(section => (
          section.key === unreadKey && section.version === unreadVersion && reviewed ? reviewed : section
        )) : [],
      } : previous);
    }).catch(() => {
      setFailed(businessId);
    });
  }, [businessId, unreadKey, unreadVersion, retry]);

  return {
    sections,
    active,
    unreadMenus: sections.filter(section => section.unread).map(section => destinations[section.key].menu),
    failed: failed !== null && failed === businessId,
    retry: () => setRetry(value => value + 1),
  };
}
