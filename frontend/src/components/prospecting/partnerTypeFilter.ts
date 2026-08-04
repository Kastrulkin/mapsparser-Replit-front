export interface PartnerTypeOption {
  id: string;
  label: string;
}

export const partnerTypeOptions: PartnerTypeOption[] = [
  { id: 'residential', label: 'ЖК и апарт-комплексы' },
  { id: 'dentistry', label: 'Стоматологии' },
  { id: 'medicine', label: 'Медицина и клиники' },
  { id: 'sport', label: 'Фитнес и спорт' },
  { id: 'food', label: 'Кафе и рестораны' },
  { id: 'photo_events', label: 'Фото и мероприятия' },
  { id: 'pets', label: 'Ветеринария и зоотовары' },
  { id: 'beauty', label: 'Красота и уход' },
  { id: 'children_retail', label: 'Детские товары и одежда' },
  { id: 'children_education', label: 'Детские сады и обучение' },
  { id: 'children_leisure', label: 'Детский досуг и культура' },
  { id: 'commercial_centers', label: 'Бизнес- и торговые центры' },
  { id: 'retail', label: 'Другие магазины' },
  { id: 'other', label: 'Прочие партнёры' },
];

const includesAny = (category: string, keywords: string[]) => (
  keywords.some((keyword) => category.includes(keyword))
);

export const partnerTypeForCategory = (value?: string | null) => {
  const category = String(value || '').trim().toLowerCase().replaceAll('ё', 'е');
  if (!category) return 'other';

  if (includesAny(category, ['жилой комплекс', 'жилые комплексы', 'апарт-отель', 'апартаменты', 'жк'])) {
    return 'residential';
  }
  if (includesAny(category, ['стоматолог', 'зуботех', 'dental'])) {
    return 'dentistry';
  }
  if (includesAny(category, ['медицин', 'медцентр', 'клиник', 'диагност', 'коррекция зрения', 'поликлиник'])) {
    return 'medicine';
  }
  if (includesAny(category, ['фитнес', 'спорт', 'секци', 'бассейн', 'единоборств', 'танц', 'йог', 'каток', 'скалолаз'])) {
    return 'sport';
  }
  if (includesAny(category, ['ресторан', 'кафе', 'бар', 'кофе', 'столов', 'быстрое питание', 'доставка еды'])) {
    return 'food';
  }
  if (includesAny(category, ['фотостуд', 'фотоуслуг', 'видеосъем', 'мероприят', 'праздник', 'свадеб'])) {
    return 'photo_events';
  }
  if (includesAny(category, ['ветерин', 'ветклиник', 'зоомагазин', 'кинолог', 'питом', 'амуници'])) {
    return 'pets';
  }
  if (includesAny(category, ['beauty', 'бьюти', 'красот', 'космет', 'парфюм', 'spa', 'wellness', 'массаж', 'ногт'])) {
    return 'beauty';
  }
  if (
    includesAny(category, ['детск', 'ребен', 'ребенок'])
    && includesAny(category, ['магазин', 'одеж', 'обув', 'товар', 'игруш', 'питание', 'коляск', 'мебель', 'бутик'])
  ) {
    return 'children_retail';
  }
  if (includesAny(category, [
    'детский сад', 'ясли', 'центр развития', 'школа', 'обучен', 'образован',
    'логопед', 'дефектолог', 'репетитор', 'курсы', 'музыкаль',
  ])) {
    return 'children_education';
  }
  if (includesAny(category, [
    'детск', 'семейн', 'досуг', 'развлекатель', 'игров', 'аттракцион',
    'театр', 'музей', 'зоопарк', 'экскурси', 'мастерская', 'город профессий',
  ])) {
    return 'children_leisure';
  }
  if (includesAny(category, ['бизнес-центр', 'торговый комплекс', 'торговый центр'])) {
    return 'commercial_centers';
  }
  if (includesAny(category, ['магазин', 'бутик', 'торгов'])) {
    return 'retail';
  }
  return 'other';
};
