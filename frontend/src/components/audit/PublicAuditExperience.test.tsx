import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import {
  PublicAuditExperience,
  type PublicAuditExperienceProps,
  type PublicAuditLabels,
} from './PublicAuditExperience';

const labels: PublicAuditLabels = {
  score: 'Оценка',
  fixYourself: 'Исправить самостоятельно',
  prepareWithLocalOS: 'Подготовить исправления с LocalOS',
  fixToday: 'Что исправить сегодня',
  fixTodayHint: 'Начните с главного.',
  whyImportant: 'Почему важно',
  actions: 'Что сделать',
  details: 'Подробнее',
  hideDetails: 'Скрыть детали',
  strengths: 'Что уже хорошо',
  noStrengths: 'Нет подтверждённых сильных сторон.',
  customerUnderstanding: 'Как клиент понимает карточку',
  strongAnswers: 'Хорошо отвечает',
  weakAnswers: 'Не хватает информации',
  missingPhotos: 'Какие фото добавить',
  needPhoto: 'Нужно добавить',
  cardData: 'Что видно в карточке',
  services: 'Услуги',
  photos: 'Фото',
  reviews: 'Отзывы',
  news: 'Новости',
  showMore: 'Показать ещё',
  showLess: 'Скрыть',
  noReply: 'Ответа нет',
  hasReply: 'Есть ответ',
  showFull: 'Показать полностью',
  hideFull: 'Свернуть',
  fullPlan: 'Полный план и методика',
  fullPlanHint: 'Детали и источники.',
  hidePlan: 'Скрыть полный план',
  openMap: 'Открыть карточку',
  companyLogo: 'Логотип',
};

const baseProps: PublicAuditExperienceProps = {
  eyebrow: 'Публичный аудит',
  title: 'Детский центр',
  diagnosis: 'Карточка хорошая, но есть три точки роста.',
  score: 72,
  status: 'Есть точки роста',
  labels,
  problems: [{
    id: 'problem-1',
    title: 'Нет свежих публикаций',
    importance: 'Карточка выглядит неактивной.',
    actions: ['Подготовить тему', 'Опубликовать новость'],
    problem: 'Полное описание проблемы.',
    evidence: 'Последняя новость была давно.',
    outcome: 'Появится свежая активность.',
  }],
  strengths: ['Рейтинг: 5.0'],
  strongDemand: ['Семейные развлечения'],
  weakDemand: ['Возраст детей'],
  missingPhotos: ['Вход'],
  services: [],
  photos: [],
  reviews: [],
  news: [],
  photoAlt: (index) => `Фото ${index + 1}`,
  onPrepareWithLocalOS: vi.fn(),
  fullPlan: <div>Скрытый полный план</div>,
};

describe('PublicAuditExperience', () => {
  it('keeps full problem text and the full plan hidden until requested', async () => {
    const user = userEvent.setup();
    render(<PublicAuditExperience {...baseProps} />);

    expect(screen.getByText('72/100')).toBeInTheDocument();
    expect(screen.getAllByText('Нет свежих публикаций')).toHaveLength(1);
    expect(screen.queryByText('Полное описание проблемы.')).not.toBeInTheDocument();
    expect(screen.queryByText('Скрытый полный план')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /подробнее/i }));
    expect(screen.getByText('Полное описание проблемы.')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /полный план и методика/i }));
    expect(screen.getByText('Скрытый полный план')).toBeInTheDocument();
  });

  it('shows only four services before expansion', async () => {
    const user = userEvent.setup();
    const services = Array.from({ length: 6 }, (_, index) => ({ name: `Услуга ${index + 1}` }));
    render(<PublicAuditExperience {...baseProps} services={services} />);

    expect(screen.getByText('Услуга 4')).toBeInTheDocument();
    expect(screen.queryByText('Услуга 5')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /показать ещё/i }));
    expect(screen.getByText('Услуга 5')).toBeInTheDocument();
    expect(screen.getByText('Услуга 6')).toBeInTheDocument();
  });

  it('renders compact review statuses and expands a news item independently', async () => {
    const user = userEvent.setup();
    render(
      <PublicAuditExperience
        {...baseProps}
        reviews={[
          { author: 'Анна', rating: 5, text: 'Дети в восторге' },
          { author: 'Иван', rating: 5, text: 'Отличное место', reply: 'Спасибо' },
        ]}
        news={[{ id: 'news-1', title: 'Новый кружок', date: '1 августа', text: 'Длинный текст публикации для проверки раскрытия.' }]}
      />,
    );

    expect(screen.getByText('Ответа нет')).toBeInTheDocument();
    expect(screen.getByText('Есть ответ')).toBeInTheDocument();
    const newsText = screen.getByText(/\u0414линный текст публикации/);
    expect(newsText).toHaveClass('line-clamp-2');
    await user.click(screen.getByRole('button', { name: /показать полностью/i }));
    expect(newsText).not.toHaveClass('line-clamp-2');
  });

  it('uses a neutral empty strength state and non-interactive photo tasks', () => {
    render(<PublicAuditExperience {...baseProps} strengths={[]} />);

    expect(screen.getByText('Нет подтверждённых сильных сторон.')).toBeInTheDocument();
    const photoSection = screen.getByRole('heading', { name: 'Какие фото добавить' }).parentElement;
    if (!photoSection) throw new Error('Missing photo section');
    expect(within(photoSection).queryByRole('checkbox')).not.toBeInTheDocument();
    expect(within(photoSection).getByText('Нужно добавить')).toBeInTheDocument();
  });

  it('keeps audit and content recommendations in two accessible tabs', async () => {
    const user = userEvent.setup();
    render(
      <PublicAuditExperience
        {...baseProps}
        contentPlan={<div>Четыре публикации с визуальными заданиями</div>}
        auditTabLabel="Аудит карточки"
        contentTabLabel="Рекомендации и контент-план"
      />,
    );

    const auditTab = screen.getByRole('tab', { name: 'Аудит карточки' });
    const contentTab = screen.getByRole('tab', { name: 'Рекомендации и контент-план' });
    expect(screen.getAllByRole('tab')[0]).toBe(auditTab);
    expect(screen.getAllByRole('tab')[1]).toBe(contentTab);
    expect(auditTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('heading', { name: 'Что исправить сегодня' })).toBeInTheDocument();

    await user.click(contentTab);

    expect(contentTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText('Четыре публикации с визуальными заданиями')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Что исправить сегодня' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Исправить самостоятельно' })).not.toBeInTheDocument();
  });

  it('can open directly on the content plan', () => {
    render(
      <PublicAuditExperience
        {...baseProps}
        contentPlan={<div>Готовый контент-план</div>}
        initialView="content"
      />,
    );

    expect(screen.getByRole('tab', { name: 'Контент-план' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText('Готовый контент-план')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Что исправить сегодня' })).not.toBeInTheDocument();
  });
});
