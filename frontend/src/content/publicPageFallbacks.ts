import { aboutStoryCopy } from "./aboutStoryCopy";
import { publishedArticles } from "./articles";
import { publishedCases } from "./cases";
import { collectionCopy } from "./collectionCopy";
import { contentCopy } from "./contentCopy";
import { publicHomeContent } from "./publicHomeContent";
import { subscriptionPlanCopy } from "./subscriptionPlanCopy";

export type PublicPageSection = {
  heading: string;
  paragraphs?: string[];
  items?: string[];
  links?: Array<{ href: string; label: string }>;
};

export type PublicPageFallback = {
  title: string;
  description: string;
  heading: string;
  intro: string[];
  sections: PublicPageSection[];
  kind?: "article" | "collection" | "page";
  image?: string;
  publishedAt?: string;
  updatedAt?: string;
  video?: { youtubeId: string; title: string };
};

export type PublicPageFallbackManifest = {
  version: 1;
  routes: Record<string, PublicPageFallback>;
};

const paragraphs = (text: string) => text.split("\n\n").filter(Boolean);

export const buildPublicPageFallbacks = (): PublicPageFallbackManifest => {
  const about = aboutStoryCopy.ru;
  const plans = subscriptionPlanCopy("ru");
  const caseCollection = collectionCopy.ru.cases;
  const articleCollection = contentCopy.ru.articles;
  const routes: Record<string, PublicPageFallback> = {
    "/": {
      title: publicHomeContent.title,
      description: publicHomeContent.description,
      heading: publicHomeContent.heading,
      intro: [...publicHomeContent.intro],
      sections: [
        { heading: "Что помогает делать LocalOS", items: ["Проверять карточки в Яндекс Картах и 2ГИС: услуги, отзывы, фото и обновления.", "Готовить черновики ответов на отзывы, новости для карт и другие материалы для контента.", "Помогать с местными авторами и партнёрствами: отбором, предложениями и подготовкой сообщений.", "Подготавливать регулярные задачи для ИИ-сотрудников и автоматизации, сохраняя контроль владельца."] },
        { heading: "Тарифы", paragraphs: ["«Карты» — 1 200 ₽ в месяц, «Привлечение» — 5 000 ₽ в месяц, «Управление» — 25 000 ₽ в месяц."], links: [{ href: "/pricing", label: "Посмотреть тарифы" }] },
        ...publishedCases.map((caseItem) => ({
          heading: caseItem.title,
          items: caseItem.metrics.map((metric) => `${metric.label}: ${metric.value}`),
          links: [{ href: `/cases/${caseItem.slug}`, label: "Читать кейс" }],
        })),
        { heading: "Контроль остаётся у владельца", paragraphs: ["Публикации, внешние отправки, платежи и массовые изменения выполняются только после явного подтверждения человека."], links: [{ href: "/pricing", label: "Посмотреть тарифы" }, { href: "/cases", label: "Посмотреть кейсы" }] },
      ],
    },
    "/about": {
      title: about.metaTitle,
      description: about.metaDescription,
      heading: about.title,
      intro: [about.intro],
      sections: [
        { heading: about.storyTitle, paragraphs: [about.storyIntro], items: about.industries },
        { heading: about.chapterOneTitle, paragraphs: paragraphs(about.chapterOneText) },
        { heading: about.chapterTwoTitle, paragraphs: paragraphs(about.chapterTwoText) },
        { heading: about.chapterThreeTitle, paragraphs: paragraphs(about.chapterThreeText) },
        { heading: about.channelTitle, paragraphs: [about.channelText] },
        { heading: "Тарифы LocalOS", paragraphs: ["«Карты» — 1 200 ₽ в месяц, «Привлечение» — 5 000 ₽ в месяц, «Управление» — 25 000 ₽ в месяц. Публикации и отправки выполняются после подтверждения."], links: [{ href: "/pricing", label: "Посмотреть тарифы" }, { href: "/contact", label: "Обсудить задачу" }] },
      ],
    },
    "/pricing": {
      title: "Тарифы LocalOS для локального бизнеса",
      description: "Тарифы LocalOS: Карты — 1 200 ₽, Привлечение — 5 000 ₽, Управление — 25 000 ₽ в месяц. Публикации и отправки выполняются после подтверждения.",
      heading: "Тарифы LocalOS",
      intro: [plans.subtitle, plans.approval],
      sections: [
        { heading: `${plans.starter.name} — 1 200 ₽ в месяц`, paragraphs: [plans.starter.lead], items: plans.starter.features },
        { heading: `${plans.professional.name} — 5 000 ₽ в месяц`, paragraphs: [plans.professional.lead], items: plans.professional.features },
        { heading: `${plans.concierge.name} — 25 000 ₽ в месяц`, paragraphs: [plans.concierge.lead], items: plans.concierge.features },
        { heading: "Подтверждение действий", paragraphs: [plans.approval], links: [{ href: "/contact", label: "Обсудить задачу" }] },
      ],
    },
    "/cases": {
      title: caseCollection.seoTitle,
      description: caseCollection.seoDescription,
      heading: caseCollection.title,
      intro: [caseCollection.description, caseCollection.libraryDescription],
      sections: publishedCases.map((caseItem) => ({ heading: caseItem.title, paragraphs: [caseItem.excerpt], items: caseItem.metrics.map((metric) => `${metric.label}: ${metric.value}`), links: [{ href: `/cases/${caseItem.slug}`, label: "Читать кейс" }] })),
    },
    "/articles": {
      title: articleCollection.seoTitle,
      description: articleCollection.seoDescription,
      heading: articleCollection.title,
      intro: [articleCollection.description, articleCollection.chooseTopic],
      kind: "collection",
      sections: publishedArticles.map((article) => ({
        heading: article.title,
        paragraphs: [article.excerpt],
        items: article.tags,
        links: [{ href: `/articles/${article.slug}`, label: "Читать статью" }],
      })),
    },
  };

  for (const caseItem of publishedCases) {
    routes[`/cases/${caseItem.slug}`] = {
      title: caseItem.seoTitle,
      description: caseItem.seoDescription,
      heading: caseItem.title,
      intro: [caseItem.excerpt],
      sections: [
        { heading: "Исходная ситуация", paragraphs: [caseItem.situation] },
        { heading: "Показатели опубликованного кейса", items: caseItem.metrics.map((metric) => `${metric.label}: ${metric.value}`) },
        { heading: "Что сделали", items: caseItem.actions },
        { heading: "Результат", paragraphs: [caseItem.result] },
        ...caseItem.body.map((section) => ({ heading: section.title, ...(section.body ? { paragraphs: [section.body] } : {}), ...(section.items ? { items: section.items } : {}) })),
        ...(caseItem.related.length ? [{ heading: "Материалы по теме", links: caseItem.related.map((link) => ({ href: link.href, label: link.title })) }] : []),
      ],
    };
  }

  for (const article of publishedArticles) {
    routes[`/articles/${article.slug}`] = {
      title: article.seoTitle,
      description: article.seoDescription,
      heading: article.title,
      intro: [article.excerpt],
      kind: "article",
      image: article.coverImage
        ? `https://localos.pro${article.coverImage}`
        : article.video
          ? `https://i.ytimg.com/vi/${article.video.youtubeId}/hqdefault.jpg`
          : undefined,
      publishedAt: article.publishedAt,
      updatedAt: article.updatedAt,
      video: article.video,
      sections: [
        ...article.body.map((section) => ({
          heading: section.title,
          ...(section.body ? { paragraphs: [section.body] } : {}),
          ...(section.items ? { items: section.items } : {}),
        })),
        ...(article.related.length
          ? [{
              heading: "Материалы по теме",
              links: article.related.map((link) => ({ href: link.href, label: link.title })),
            }]
          : []),
      ],
    };
  }

  return { version: 1, routes };
};
