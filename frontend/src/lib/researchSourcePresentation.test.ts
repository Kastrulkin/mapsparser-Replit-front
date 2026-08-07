import { describe, expect, it } from 'vitest';
import { researchSourcePresentation } from './researchSourcePresentation';

describe('researchSourcePresentation', () => {
  it('names a map destination instead of repeating only the company name', () => {
    expect(researchSourcePresentation({
      title: 'Персона Lab',
      url: 'https://yandex.ru/maps/org/persona_lab/123',
      source_type: 'map_service_catalog',
    })).toEqual({
      destination: 'Услуги и цены в карточке на картах',
      context: 'Персона Lab · yandex.ru',
    });
  });

  it('recognizes Telegram by URL when the backend type is generic', () => {
    expect(researchSourcePresentation({
      title: 'Персона Lab',
      url: 'https://t.me/persona_lab',
      source_type: 'public_web',
    }).destination).toBe('Публичный Telegram-канал');
  });

  it('distinguishes a Telegram post from the channel itself', () => {
    expect(researchSourcePresentation({
      title: 'Персона Lab',
      url: 'https://t.me/personaklimentinikitskaya/1969',
      source_type: 'telegram_public',
    }).destination).toBe('Публикация в Telegram');
  });

  it('uses the domain for an unknown public page', () => {
    expect(researchSourcePresentation({
      title: 'Персона Lab',
      url: 'https://persona-lab.ru/prices',
    })).toEqual({
      destination: 'Веб-страница на persona-lab.ru',
      context: 'Персона Lab · persona-lab.ru',
    });
  });
});
