import { promotionContent } from './promotionContent';
const home = promotionContent().home;
export const publicHomeContent = {
  title: home.seoTitle,
  description: home.description,
  heading: home.title,
  intro: [home.description],
};
