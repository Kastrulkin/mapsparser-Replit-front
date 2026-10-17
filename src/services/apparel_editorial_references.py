"""Garment-making guidance, not a source of competitors' production promises."""
import re

APPAREL_REFERENCE_QUERY = r'пошив|швейн|брендированн.{0,20}одежд|худи|свитшот|футболк|\mлекал|\mgarment\M|\mapparel\M'


def is_apparel_editorial_reference(text):
    value = str(text or '').casefold()
    if re.search(r'#стартап|венчур|инвестор|ремонт.{0,20}швейн|подарочн.{0,12}сертификат|букет|конфет|ежедневник|подарочн.{0,12}набор', value):
        return False
    return bool(re.search(APPAREL_REFERENCE_QUERY.replace(r'\m',r'\b').replace(r'\M',r'\b'), value))


def apparel_editorial_guidance():
    return [
        {'id':'apparel_guidance_garment_v1','source_type':'editorial_guidance',
         'techniques':['начинать с конкретной вещи и видимой детали: силуэт, капюшон, манжета, расположение изображения',
                       'разделять то, что видно на фото, и подтверждённую технологию; не угадывать состав, плотность и способ нанесения'],
         'strength':'редакционный ориентир, не чужая спецификация изделия',
         'source_url':'https://kodmerch.ru/hoodie'},
        {'id':'apparel_guidance_sample_v1','source_type':'editorial_guidance',
         'techniques':['показывать связь дизайна с самой одеждой, посадкой и использованием',
                       'образцы и этапы производства описывать как услуги этого бизнеса только при подтверждении'],
         'strength':'редакционный ориентир; чужие мощности, минимальные партии и сроки не переносятся',
         'source_url':'https://bomonti.pro/production'},
        {'id':'apparel_guidance_brand_v1','source_type':'editorial_guidance',
         'techniques':['чередовать вещь целиком, деталь, визуальную идею, одежду команды и подтверждённую работу производства',
                       'не превращать пошив одежды в каталог подарков, упаковки и сувениров; не строить весь месяц из инструкций по брифу'],
         'strength':'редакционный ориентир, не обещание методов печати или тканей этого клиента',
         'source_url':'https://instyle.zone/sewing-industry/catalog/hudi-na-zakaz'},
    ] + [
        {'id': reference_id, 'source_type': 'editorial_guidance',
         'source_name': name, 'source_url': url, 'techniques': [technique],
         'strength': 'редакционный ориентир; чужие технологии, материалы, сроки, тиражи и заказчики не являются фактами этого бизнеса'}
        for reference_id, name, url, technique in [
            ('apparel_guidance_red_fabrik_v1', 'RED FABRIK', 'https://redfabrik.ru/',
             'чередовать готовую одежду и подтверждённые этапы её производства'),
            ('apparel_guidance_ceh8_v1', 'Цех №8', 'https://ceh-8.ru/',
             'показывать одежду под конкретную задачу: команда, мероприятие или собственный бренд'),
            ('apparel_guidance_doronin_v1', 'Мануфактура Доронина', 'https://merch-hub.ru/poshiv-hudi',
             'посвящать пост одной видимой детали: рисунку на рукаве, элементу у манжеты или размещению графики'),
            ('apparel_guidance_texnikum_v1', 'Техникум', 'https://texnikum.ru/models/hoodies',
             'объяснять варианты одной вещи через модель, посадку и оформление, без неподтверждённых характеристик'),
            ('apparel_guidance_odnm_v1', 'ODNM', 'https://odnm.ru/poshiv-hudi',
             'рассказывать, для кого создаётся одежда и как её используют; реальные заказы называть только при подтверждении'),
            ('apparel_guidance_oneplanet_v1', 'ONEPLANET.FACTORY', 'https://shiemvspb.ru/poshiv-mercha',
             'чередовать разные модели из подтверждённого ассортимента вместо повторения одной вещи весь месяц'),
            ('apparel_guidance_unifashion_v1', 'Unifashion', 'https://unifashion.ru/hudi-na-zakaz/',
             'связывать видимые особенности кроя и размещение графики с подтверждённой задачей изделия'),
            ('apparel_guidance_fashion_atlas_v1', 'Fashion Atlas Group', 'https://fashionatlasgroup.com/cases/from-visual-references-to-100-custom-hoodies/',
             'строить подтверждённый кейс по этапам: идея, первый образец, изменения и готовая вещь; не выдумывать историю заказа'),
            ('apparel_guidance_promofect_v1', 'Promofect', 'https://promofect.com/case-studies/hubspot/',
             'показывать сдержанное брендирование: небольшой знак как часть вещи вместо обязательного большого рисунка'),
            ('apparel_guidance_times_v1', 'Times Clothing', 'https://timesclothing.com/our-work/',
             'строить рассказ вокруг назначения конкретного подтверждённого заказа, а не общих обещаний качества'),
            ('apparel_guidance_vices_v1', 'ViCES Studio', 'https://vices.studio/work/kaf-custom-hoodie',
             'раскрывать одну вещь через несколько деталей оформления, называя технологии только по подтверждённым данным'),
            ('apparel_guidance_sharknits_v1', 'Sharknits', 'https://sharknits.com/work',
             'чередовать общий вид изделия и крупные планы отделки; опираться на собственные фотографии бизнеса'),
        ]
    ]
