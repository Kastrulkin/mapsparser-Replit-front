import { readFileSync } from 'node:fs';
import { getRuleById } from '@seomator/seo-audit';
import { load } from 'cheerio';

// These SEOmator rules inspect the supplied HTML without fetching anything.
const checks = [
  { id: 'core-robots-meta', title: 'В HTML есть ограничения для поисковых роботов',
    fix: 'Уточните, должны ли роботы индексировать эту страницу и показывать её в поиске. Если ограничения случайны, исправьте настройки страницы.' },
  { id: 'core-title-present', title: 'Отсутствует заголовок страницы (title)',
    fix: 'Добавьте уникальный title, который точно описывает содержание страницы.' },
  { id: 'core-description-present', title: 'Отсутствует описание страницы (meta description)',
    fix: 'Напишите краткое уникальное описание с главной пользой для посетителя.' },
  { id: 'core-h1-present', title: 'Отсутствует главный заголовок (H1)',
    fix: 'Добавьте главный заголовок, по которому посетитель сразу поймёт тему страницы.' },
  { id: 'core-viewport-present', title: 'Отсутствует настройка мобильного масштаба (viewport)',
    fix: 'Настройте ширину страницы под экран устройства и проверьте страницу на телефоне.' },
  { id: 'core-canonical-present', title: 'Не указан предпочтительный URL (canonical)',
    fix: 'Если содержимое доступно по нескольким адресам, укажите предпочтительный адрес в canonical.', review: true },
  { id: 'core-canonical-valid', requires: 'core-canonical-present', title: 'В canonical нет полного корректного URL',
    fix: 'Проверьте canonical и укажите полный предпочтительный URL этой страницы.' },
  { id: 'core-h1-single', requires: 'core-h1-present', title: 'На странице несколько главных заголовков (H1)',
    fix: 'Проверьте структуру. Если у страницы одна главная тема, используйте один H1, а подзаголовки оформите как H2 и H3.', review: true },
  { id: 'core-title-length', requires: 'core-title-present', title: 'Стоит проверить длину заголовка (title)',
    fix: 'Поставьте основной смысл в начало. При необходимости уточните или сократите заголовок.', review: true },
  { id: 'core-description-length', requires: 'core-description-present', title: 'Стоит проверить длину описания (meta description)',
    fix: 'Сформулируйте главное в одном-двух предложениях и проверьте, что описание сохраняет смысл при сокращении.', review: true },
];

async function inspectPage({ url, html }) {
  const context = { url, $: load(html), html, headers: {} };
  const results = new Map();
  const findings = [];
  for (const check of checks) {
    if (check.requires && results.get(check.requires) !== 'pass') continue;
    const result = await getRuleById(check.id).run(context);
    results.set(check.id, result.status);
    if (result.status === 'pass' || result.status === 'skip') continue;
    findings.push({
      rule: check.id,
      priority: check.review ? 'review' : 'fix',
      title: check.title,
      fix: check.fix,
    });
  }
  return { url, findings };
}

const pages = JSON.parse(readFileSync(0, 'utf8'));
const results = [];
for (const page of pages) results.push(await inspectPage(page));
process.stdout.write(JSON.stringify(results));
