export function businessResultHref(href: string, businessId?: string | null): string {
  if (!businessId || !href.startsWith('/dashboard/')) return href;
  const url = new URL(href, 'https://localos.pro');
  if (!url.searchParams.get('business_id')) url.searchParams.set('business_id', businessId);
  return `${url.pathname}${url.search}${url.hash}`;
}
