import { describe, expect, it } from 'vitest';
import { promotionContent } from './promotionContent';

// Approved first-screen copy from LOCALOS_TZ_CODEX_IMPLEMENTATION.md.
const approved = {
  "home": {
    "title": "Привлекайте клиентов рядом, даже когда некогда заниматься продвижением",
    "description": "Карты, локальные блогеры и партнёры по соседству — три способа познакомить с вашим бизнесом людей, которым удобно к вам прийти. LocalOS помогает готовить материалы и предложения для каждого из них",
    "eyebrow": "Продвижение локального бизнеса"
  },
  "maps": {
    "title": "Увеличивайте поток клиентов с Карт — без ручной работы",
    "description": "LocalOS готовит оформление карточки, SEO-описания услуг, публикации и ответы на отзывы — чтобы повышать видимость на картах и привлекать клиентов рядом",
    "eyebrow": "Продвижение бизнеса на Яндекс Картах"
  },
  "bloggers": {
    "title": "Привлекайте внимание к бизнесу через локальных блогеров",
    "description": "LocalOS помогает найти местных авторов и подготовить предложение о сотрудничестве, чтобы познакомить с вашей точкой людей, которым удобно стать вашими клиентами",
    "eyebrow": "Реклама у локальных блогеров"
  },
  "partners": {
    "title": "Привлекайте клиентов через рекомендации бизнесов по соседству",
    "description": "Найдите локальных партнёров рядом с вашей точкой на Яндекс Картах и предложите взаимные рекомендации или общую акцию. LocalOS помогает подобрать бизнес и подготовить предложение с выгодой для обеих сторон",
    "eyebrow": "Локальные партнёры для взаимопиара и совместных акций"
  }
};

describe('approved promotion copy', () => {
  it('preserves the four approved Russian first screens verbatim', () => {
    const pages = promotionContent();
    expect(pages.home).toMatchObject(approved.home);
    expect(pages.maps).toMatchObject(approved.maps);
    expect(pages.bloggers).toMatchObject(approved.bloggers);
    expect(pages.partners).toMatchObject(approved.partners);
  });
});
