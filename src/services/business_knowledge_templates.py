"""Field suggestions keyed by the existing profile type, not a second type registry."""

SUGGESTIONS = {
    'beauty_salon': [('hair_chairs','Парикмахерские кресла'),('nail_places','Маникюрные места'),('rooms','Кабинеты'),('washbasins','Мойки')],
    'children_hair_salon': [('hair_chairs','Парикмахерские кресла'),('washbasins','Мойки'),('play_places','Игровые места'),('waiting_places','Места ожидания родителей')],
    'barbershop': [('hair_chairs','Рабочие кресла'),('washbasins','Мойки'),('waiting_places','Места ожидания')],
    'nail_studio': [('nail_places','Маникюрные места'),('pedicure_places','Педикюрные места')],
    'spa': [('rooms','Кабинеты'),('rest_places','Места в зоне отдыха'),('equipment','Оборудование','long_text')],
    'cosmetology': [('rooms','Кабинеты'),('couches','Кушетки'),('equipment','Оборудование','long_text')],
    'massage': [('rooms','Кабинеты'),('massage_tables','Массажные столы')],
    'brows_lashes': [('work_places','Рабочие места'),('couches','Кушетки')],
    'makeup': [('work_places','Рабочие места'),('equipment','Оборудование','long_text')],
    'tanning': [('tanning_units','Установки солярия'),('equipment','Типы установок','long_text')],
    'auto_service': [('repair_posts','Ремонтные посты'),('lifts','Подъёмники'),('diagnostic_posts','Диагностические посты'),('vehicle_limits','Ограничения по габаритам автомобилей','long_text')],
    'gas_station': [('fuel_columns','Топливораздаточные колонки'),('fuel_places','Заправочные места'),('fuel_types','Виды топлива','text')],
    'cafe': [('tables','Столики'),('hall_seats','Посадочные места в зале'),('terrace_seats','Места на террасе')],
    'shawarma': [('production_posts','Производственные посты'),('hall_seats','Посадочные места'),('equipment','Оборудование','long_text')],
    'school': [('classrooms','Аудитории'),('classroom_capacity','Вместимость аудиторий','long_text'),('group_max','Максимальный размер группы'),('equipment','Оборудование','long_text')],
    'workshop': [('work_places','Рабочие места'),('machines','Станки'),('equipment','Оборудование','long_text')],
    'shoe_repair': [('work_places','Рабочие места'),('equipment','Оборудование','long_text')],
    'gym': [('floor_area','Площадь залов','decimal'),('group_max','Вместимость группового занятия'),('machines','Тренажёры')],
    'theater': [('halls','Залы'),('hall_seats','Посадочные места'),('stage','Параметры сцены','long_text')],
    'transport': [('vehicle_types','Транспортные средства по типам','long_text'),('passenger_capacity','Пассажировместимость','long_text'),('payload_capacity','Грузоподъёмность','long_text')],
    'hotel': [('room_categories','Номера по категориям','long_text'),('beds','Спальные места')],
    'guest_house': [('room_categories','Номера по категориям','long_text'),('beds','Спальные места')],
    'other': [('floor_area','Площадь','decimal'),('equipment','Оборудование','long_text'),('service_features','Особенности обслуживания','long_text')],
}


def fields(type_key):
    result = []
    for item in SUGGESTIONS.get(type_key, SUGGESTIONS['other']):
        key, label = item[:2]
        kind = item[2] if len(item) > 2 else 'integer'
        result.append({'template_key': key, 'label': label, 'type': kind,
                       'group': 'Помещение и оборудование', 'unit': 'м²' if key == 'floor_area' else 'шт.' if kind == 'integer' else '',
                       'min': 0 if kind in {'integer','decimal'} else None, 'location_only': True})
    return result
