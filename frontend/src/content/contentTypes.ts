export type RelatedLink = {
  title: string;
  href: string;
  label: string;
};

export type ContentSection = {
  title: string;
  body?: string;
  items?: string[];
};

export type ArticleContent = {
  title: string;
  slug: string;
  excerpt: string;
  category: "Карты" | "Отзывы" | "Клиенты" | "Кафе";
  tags: string[];
  publishedAt: string;
  updatedAt: string;
  coverImage?: string;
  seoTitle: string;
  seoDescription: string;
  draft: boolean;
  body: ContentSection[];
  related: RelatedLink[];
};

export type DocumentContent = {
  title: string;
  slug: string;
  excerpt: string;
  documentType: "Чек-листы" | "Шаблоны" | "Таблицы";
  tags: string[];
  publishedAt: string;
  updatedAt: string;
  coverImage?: string;
  seoTitle: string;
  seoDescription: string;
  fileUrl?: string;
  downloadUrl?: string;
  draft: boolean;
  inside: string[];
  body: ContentSection[];
  related: RelatedLink[];
};

export type CaseMetric = {
  label: string;
  value: string;
};

export type CaseContent = {
  title: string;
  slug: string;
  excerpt: string;
  industry: "Салоны" | "Кафе" | "Локальный бизнес";
  tags: string[];
  publishedAt: string;
  updatedAt: string;
  coverImage?: string;
  seoTitle: string;
  seoDescription: string;
  metrics: CaseMetric[];
  draft: boolean;
  situation: string;
  actions: string[];
  result: string;
  body: ContentSection[];
  related: RelatedLink[];
};
