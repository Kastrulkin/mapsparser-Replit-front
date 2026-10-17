"""Salon editorial techniques; never evidence of this business's services."""
import re

BEAUTY_REFERENCE_QUERY = r'стрижк|окрашиван|тонирован|маникюр|педикюр|укладк|салон.{0,12}красоты|haircut|hairstyl|nail art'

def is_beauty_editorial_reference(text):
    value = str(text or '').casefold()
    if re.search(r'ваканси|требуется.{0,20}мастер|обучение.{0,20}мастер|курс.{0,20}маникюр|франшиз|оптов|#стартап|лечит|гарантированн.{0,20}результат', value):
        return False
    return bool(re.search(BEAUTY_REFERENCE_QUERY, value))

def beauty_editorial_guidance():
    return [
        {'id':'beauty_guidance_result_v1','source_type':'editorial_guidance',
         'techniques':['начинать с видимой детали собственной работы: форма стрижки, оттенок, линия ногтей; затем объяснять услугу',
                       'фото не доказывает технику окрашивания, состав, биозавивку или срок носки; не угадывать их'],
         'strength':'редакционный ориентир, не подтверждение фактов салона',
         'source_url':'https://burobeauty.ru/point_peter.html'},
        {'id':'beauty_guidance_mix_v1','source_type':'editorial_guidance',
         'techniques':['чередовать собственную работу, конкретную услугу, деталь образа, ответ на вопрос и подтверждённую новость',
                       'не строить месяц из одинаковых памяток «обсудите с мастером»; проверять смысловые повторы, начала и призывы'],
         'strength':'редакционный ориентир; чужие события и достижения не переносятся',
         'source_url':'https://aldocoppola.ru/news/'},
        {'id':'beauty_guidance_facts_v1','source_type':'editorial_guidance',
         'techniques':['различать задачи услуг и писать живо без обещаний идеального или лечебного результата',
                       'цены, материалы, акции и специалисты — только из актуальных данных бизнеса; один понятный призыв вместо длинного списка оговорок'],
         'strength':'редакционная проверка, не доказательство эффективности чужих постов',
         'source_url':'https://burobeauty.ru/point_peter.html'},
    ]
