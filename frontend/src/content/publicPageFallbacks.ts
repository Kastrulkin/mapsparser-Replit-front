import { publicContentSchema } from "./publicContentSchema";
import { publishedArticles } from "./articles";
import { publishedDocuments } from "./documents";
import { solutions } from "./solutions";
import { aboutStoryCopy } from "./aboutStoryCopy";
import { publishedCases } from "./cases";
import { collectionCopy } from "./collectionCopy";
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
  schema?: unknown;
};

export type PublicPageFallbackManifest = {
  version: 1;
  publicShell?: string;
  routes: Record<string, PublicPageFallback>;
};

const paragraphs = (text: string) => text.split("\n\n").filter(Boolean);

export const buildPublicPageFallbacks = (): PublicPageFallbackManifest => {
  const about = aboutStoryCopy.ru;
  const plans = subscriptionPlanCopy("ru");
  const caseCollection = collectionCopy.ru.cases;
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

  const sections = (body: Array<{ title: string; body?: string; items?: string[]; bodyLinks?: Array<{ text: string; href: string }> }>) => body.map((section) => ({ heading: section.title, paragraphs: section.body ? [section.body] : [], items: section.items || [], links: (section.bodyLinks || []).map((link) => ({ href: link.href, label: link.text })) }));
  const related = (links: Array<{ title: string; href: string }>) => ({ heading: "Материалы по теме", links: links.map((item) => ({ href: item.href, label: item.title })) });
  const articleCopy = { seoTitle: "Статьи для владельцев локального бизнеса — LocalOS", seoDescription: "Статьи LocalOS о картах, отзывах, клиентах, финансах и автоматизации регулярной работы локального бизнеса.", title: "Статьи о бизнесе, клиентах и росте", description: "Практические разборы о картах, отзывах, клиентах, финансах и ежедневной работе владельца." };
  routes["/articles"] = { title: articleCopy.seoTitle, description: articleCopy.seoDescription, heading: articleCopy.title, intro: [articleCopy.description], sections: publishedArticles.map((item) => ({ heading: item.title, paragraphs: [item.excerpt], links: [{ href: `/articles/${item.slug}`, label: "Читать статью" }] })) };
  routes["/documents"] = { title: collectionCopy.ru.documents.seoTitle, description: collectionCopy.ru.documents.seoDescription, heading: collectionCopy.ru.documents.title, intro: [collectionCopy.ru.documents.description], sections: publishedDocuments.map((item) => ({ heading: item.title, paragraphs: [item.excerpt], links: [{ href: `/documents/${item.slug}`, label: "Открыть документ" }] })) };
  for (const item of publishedArticles) {
    routes[`/articles/${item.slug}`] = { title: item.seoTitle, description: item.seoDescription, heading: item.title, intro: [item.excerpt], sections: [{ heading: "Дата публикации", paragraphs: [item.publishedAt] }, ...sections(item.body), related(item.related)], schema: publicContentSchema(item, "articles", "Статьи") };
  }
  for (const item of publishedDocuments) {
    routes[`/documents/${item.slug}`] = { title: item.seoTitle, description: item.seoDescription, heading: item.title, intro: [item.excerpt], sections: [{ heading: "Что внутри", items: item.inside }, ...sections(item.body), related(item.related)], schema: publicContentSchema(item, "documents", "Документы") };
  }
  for (const item of solutions) {
    routes[`/solutions/${item.slug}`] = { title: item.seoTitle, description: item.seoDescription, heading: item.title, intro: [item.excerpt], sections: [...sections(item.body), related(item.related)] };
  }
  routes["/"].sections.unshift({ heading: "Задачи владельца", links: [{ href: "/solutions/yandex-maps", label: "Привлечь клиентов через карты" }, { href: "/solutions/ai-review-replies", label: "Подготовить ответы на отзывы" }, { href: "/articles/kak-uvelichit-sredniy-chek", label: "Увеличить средний чек" }, { href: "/solutions/business-automation", label: "Передать регулярные задачи" }, { href: "/articles/pochemu-salon-s-polnoi-zapisyu-mozhet-rabotat-v-minus", label: "Разобраться с прибылью" }] });
  return { version: 1, publicShell: "public-seo-index.html", routes };
};
