import { promotionContent, promotionKeys, promotionTrust, promotionCreatorExamples, promotionExamples, promotionFaqGroups, promotionWorkSteps } from './promotionContent';
import { publicPlanPrice } from './publicSubscriptionPrices';
import { ruSections, ruAgentQuickstart } from "./publicDocsContent";
import { leadJourneyDirections } from "./growthDirections";
import { publicGrowthCopy } from "./publicGrowthCopy";
import { publicContentSchema } from "./publicContentSchema";
import { publishedArticles } from "./articles";
import { publishedDocuments } from "./documents";
import { solutions } from "./solutions";
import { aboutStoryCopy } from "./aboutStoryCopy";
import { publishedCases } from "./cases";
import { collectionCopy } from "./collectionCopy";
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
      intro: [plans.subtitle],
      sections: [
        { heading: `${plans.starter.name} — ${publicPlanPrice("starter")} в месяц`, paragraphs: [plans.starter.lead], items: plans.starter.features },
        { heading: `${plans.professional.name} — ${publicPlanPrice("professional")} в месяц`, paragraphs: [plans.professional.lead], items: plans.professional.features },
        { heading: `${plans.concierge.name} — ${publicPlanPrice("concierge")} в месяц`, paragraphs: [plans.concierge.lead], items: plans.concierge.features },
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
  routes["/growth"] = { title: publicGrowthCopy.seoTitle, description: publicGrowthCopy.seoDescription, heading: publicGrowthCopy.title, intro: [publicGrowthCopy.intro], sections: leadJourneyDirections.map((item) => ({ heading: item.title, paragraphs: [item.preview], links: [{ href: `/growth?direction=${item.key}`, label: item.choiceCta || publicGrowthCopy.defaultChoice }] })) };
  for (const item of leadJourneyDirections) {
    routes[`/growth?direction=${item.key}`] = { title: `${item.detailTitle} — LocalOS`, description: item.detail, heading: item.detailTitle, intro: [item.detail], sections: [
      ...(item.detailSections ? item.detailSections.map((section) => ({ heading: section.title, items: section.items })) : item.steps.map((step) => ({ heading: step.title, paragraphs: [step.description] }))),
      ...(item.detailSections ? [] : [{ heading: publicGrowthCopy.businessRoleTitle, paragraphs: [item.businessRole] }, { heading: publicGrowthCopy.localosRoleTitle, paragraphs: [item.localosRole] }]),
      { heading: item.continueTitle || publicGrowthCopy.continueTitle, paragraphs: [item.continueText || publicGrowthCopy.continueText], links: [{ href: `/login?tab=register&source=lead_journey&journey=${item.key}`, label: publicGrowthCopy.continueButton }, { href: "/growth", label: publicGrowthCopy.allDirections }] },
    ] };
  }
  for (const section of ruSections) {
    const route = section.slug === "overview" ? "/docs" : `/docs/${section.slug}`;
    routes[route] = { title: `${section.title} - Документация LocalOS`, description: section.summary, heading: section.title, intro: [section.summary], sections: [...section.items.map((item) => ({ heading: item.title, paragraphs: [item.text, ...(item.status ? [item.status] : [])] })), { heading: "Как подключить агента", paragraphs: [ruAgentQuickstart], links: [{ href: "/api/agent-api/openapi.json", label: "Контракт Agent API" }, { href: "/localos-agents-ru.txt", label: "Инструкция для агентов" }] }, { heading: "Разделы документации", links: ruSections.map((item) => ({ href: item.slug === "overview" ? "/docs" : `/docs/${item.slug}`, label: item.title })) }] };
  }
  const promotion = promotionContent();
  for (const key of promotionKeys) {
    const page = promotion[key];
    const home = key === 'home';
    const routeCases = home ? publishedCases.slice(0, 1) : key === 'maps' ? publishedCases : [];
    routes[page.path] = {
      title: page.seoTitle, description: page.description, heading: page.title,
      intro: [page.description],
      sections: [
        ...(promotionTrust ? [{ heading: 'LocalOS', paragraphs: [promotionTrust.text] }] : []),
        ...(!home ? [{ heading: 'Направление', links: [{ href: '/', label: 'Главная' }], paragraphs: [page.label] }] : []),
        { heading: home ? 'С чего хотите начать?' : 'Работа по направлению', paragraphs: [page.reason], links: home ? promotionKeys.filter((direction) => direction !== 'home').map((direction) => ({ href: promotion[direction].path, label: promotion[direction].label })) : [] },
        ...page.sections.map((section) => ({ heading: section.title, paragraphs: [section.text], items: section.items || [] })),
        ...(!home ? [{ heading: 'Пример работы', paragraphs: ['Тексты для вашей компании подготовим с учётом её услуг и цен.'] }] : []),
        ...(key === 'maps' ? promotionExamples().map((item) => ({ heading: item.title, paragraphs: [item.text] })) : []),
        ...(key === 'bloggers' ? promotionCreatorExamples().map((item) => ({ heading: item.title, paragraphs: [item.text] })) : []),
        { heading: 'Как начнём работу', items: promotionWorkSteps(false, key).map((step) => `${step.title}. ${step.text}`) },
        ...routeCases.map((item) => ({ heading: item.title, paragraphs: [item.excerpt, 'Кейс по продвижению на Картах.'], items: item.metrics.map((metric) => `${metric.label}: ${metric.value}`), links: [{ href: `/cases/${item.slug}`, label: 'Читать кейс' }] })),
        { heading: home ? 'Тарифы и ответы на вопросы' : 'Условия и стоимость', paragraphs: ['Тарифы подписки собраны на отдельной странице. Работу команды и расходы на размещения обсудим до начала.'], links: [{ href: `/pricing?direction=${key}`, label: 'Посмотреть тарифы' }, { href: `/faq?direction=${key}`, label: 'Вопросы и ответы' }] },
        { heading: home ? 'Поможем выбрать способ продвижения' : `Обсудим направление «${page.label}»`, paragraphs: ['Оставьте имя и телефон. Менеджер обсудит задачу, состав работ и стоимость.'], links: [{ href: '/contact', label: 'Контакты' }, ...(home ? promotionKeys.filter((direction) => direction !== 'home').map((direction) => ({ href: promotion[direction].path, label: promotion[direction].label })) : [])] },
      ],
    };
  }
  routes['/faq'] = {
    title: 'Вопросы и ответы о продвижении — LocalOS',
    description: 'Как начать работу с LocalOS, предоставить доступы и согласовать материалы. Ответы о Картах, блогерах, партнёрах и стоимости.',
    heading: 'Вопросы и ответы', intro: ['Как начинаем работу, какие доступы нужны и что входит в продвижение.'],
    sections: [
      ...promotionFaqGroups().flatMap((group) => [
        { heading: group.title, paragraphs: [] },
        ...group.questions.map((item) => ({ heading: item.question, paragraphs: [item.answer] })),
      ]),
      { heading: 'Не нашли ответ?', paragraphs: ['Оставьте заявку. Менеджер свяжется с вами и ответит на вопросы.'], links: [{ href: '/contact', label: 'Контакты' }, { href: '/pricing', label: 'Посмотреть тарифы' }] },
    ],
  };
  return { version: 1, publicShell: "public-seo-index.html", routes };
};
