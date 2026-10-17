"""Shared cultural-space techniques; never a source of another venue's events."""
import re


CULTURE_REFERENCE_QUERY = (
    r'культурн.{0,25}(центр|пространств)|выставк|куратор|художник|'
    r'концерт|квартет|перформанс|вернисаж|стендап|\mгалерея\M|'
    r'\mexhibition\M|\mgallery\M|\mconcert\M|\mcurator\M'
)


def is_culture_editorial_reference(text):
    value = str(text or '').casefold()
    if re.search(r'#стартап|венчур|инвестор|франшиз|выставк.{0,20}(продаж.{0,10}авто|сельхоз)|'
                 r'промышленн.{0,15}выставк|кабельн.{0,15}продукц|'
                 r'казино.{0,15}(депозит|выигрыш)|букмекер', value):
        return False
    return bool(re.search(CULTURE_REFERENCE_QUERY.replace(r'\m', r'\b').replace(r'\M', r'\b'), value))


def culture_editorial_guidance():
    return [
        {'id': 'culture_guidance_detail_v1', 'source_type': 'editorial_guidance',
         'techniques': ['одна работа, произведение или деталь как вход в программу',
                        'объяснить, что посетитель увидит или услышит, без общих советов о досуге'],
         'strength': 'редакционный ориентир, не программа или факты другой площадки',
         'source_url': 'https://t.me/s/vacges2'},
        {'id': 'culture_guidance_people_v1', 'source_type': 'editorial_guidance',
         'techniques': ['показать автора, исполнителя или подготовку события через подтверждённую деталь',
                        'не выдумывать реплики, реакции гостей, аншлаги и закулисные истории'],
         'strength': 'редакционный ориентир, не доказательство результата мероприятия',
         'source_url': 'https://t.me/s/vacges2'},
        {'id': 'culture_guidance_program_v1', 'source_type': 'editorial_guidance',
         'techniques': ['чередовать актуальную афишу, коллекцию, людей, пространство и хроники',
                        'для анонса подтвердить дату, статус и билет; архив явно обозначить, не переносить старую цену и дату'],
         'strength': 'редакционный ориентир; чужие события и доступность не переносятся в этот бизнес',
         'source_url': 'https://t.me/s/sevcableport'},
    ]
