export interface LeadMapLinkCandidate {
  url?: string;
  source_type?: string;
  provider?: string;
}

export interface LeadMapLink {
  url: string;
  label: string;
}

const safeHttpUrl = (value?: string) => {
  try {
    const url = new URL(String(value || ''));
    return ['http:', 'https:'].includes(url.protocol) ? url : null;
  } catch {
    return null;
  }
};

const normalizedHint = (candidate: LeadMapLinkCandidate) => [candidate.source_type, candidate.provider]
  .map((item) => String(item || '').trim().toLowerCase())
  .filter(Boolean)
  .join(' ');

export const leadMapLink = (candidates: LeadMapLinkCandidate[]): LeadMapLink | null => {
  for (const candidate of candidates) {
    const url = safeHttpUrl(candidate.url);
    if (!url) continue;

    const host = url.hostname.replace(/^www\./, '').toLowerCase();
    const hint = normalizedHint(candidate);
    if (
      host === 'yandex.ru'
      || host.endsWith('.yandex.ru')
      || host === 'yandex.com'
      || host.endsWith('.yandex.com')
      || hint.includes('yandex')
    ) {
      return { url: url.toString(), label: 'Открыть на Яндекс Картах' };
    }
    if (host === '2gis.ru' || host.endsWith('.2gis.ru') || hint.includes('2gis')) {
      return { url: url.toString(), label: 'Открыть в 2ГИС' };
    }
    if (
      host === 'maps.app.goo.gl'
      || (host.includes('google.') && url.pathname.toLowerCase().includes('/maps'))
      || hint.includes('google_maps')
    ) {
      return { url: url.toString(), label: 'Открыть на Google Картах' };
    }
    if (hint.includes('map_card') || hint.includes('public_map') || hint.includes('business_card')) {
      return { url: url.toString(), label: 'Открыть карточку на картах' };
    }
  }
  return null;
};
