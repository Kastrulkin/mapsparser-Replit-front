export const SITE_URL = "https://localos.pro";

import type { Language } from "@/i18n/LanguageContext";

const dateLocales: Record<Language, string> = {
  ru: "ru-RU",
  en: "en-US",
  fr: "fr-FR",
  es: "es-ES",
  el: "el-GR",
  de: "de-DE",
  th: "th-TH",
  ar: "ar",
  ha: "ha-NG",
  tr: "tr-TR",
};

export const formatContentDate = (date: string, language: Language = "ru") =>
  new Intl.DateTimeFormat(dateLocales[language], {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(date));

export const makeBreadcrumbSchema = (items: { name: string; path: string }[]) => ({
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: items.map((item, index) => ({
    "@type": "ListItem",
    position: index + 1,
    name: item.name,
    item: `${SITE_URL}${item.path}`,
  })),
});
