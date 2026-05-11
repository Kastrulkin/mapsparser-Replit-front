import json
import re
from collections import Counter, defaultdict

from psycopg2.extras import Json

from api.services_api import _load_active_services_for_business
from core.service_keyword_scoring import build_services_quality_audit
from database_manager import DatabaseManager


BUSINESS_ID = "360b90ef-cf2b-4eb4-acd4-a8524e4600ae"


def norm(value):
    text = str(value or "").lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9]+", " ", text)
    return " ".join(text.split())


def clean(value):
    text = str(value or "").strip().replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*\+\s*", " + ", text)
    text = re.sub(r"\s*/\s*", " / ", text)
    text = re.sub(r"\s*-\s*", " - ", text)
    text = text.replace(" Ml", " ml").replace(" ML", " ml")
    return text.strip(" .")


def sentence(value):
    text = clean(value)
    return text.rstrip(".") + "." if text else ""


def lower_first(value):
    value = str(value or "")
    return value[:1].lower() + value[1:] if value else value


def cap(value):
    value = str(value or "")
    return value[:1].upper() + value[1:] if value else value


def laser_zone(name):
    raw = clean(name)
    size = ""
    match = re.match(r"(?i)^зона\s+(mini|middle|maxi)\s*-\s*(.+)$", raw)
    if match:
        size = match.group(1).lower()
        raw = match.group(2).strip()
    raw = re.sub(r"(?i)^лазерная эпиляция\s*-\s*", "", raw).strip()
    raw = raw.replace("Всё", "всё")
    return raw, size


def laser_desc(category, name):
    category_norm = norm(category)
    audience = "мужчин" if "муж" in category_norm else "девушек"
    zone, size = laser_zone(name)
    zone_text = lower_first(zone)
    if norm(name).startswith("комплекс"):
        details = clean(name)
        return sentence(f"Лазерная эпиляция для {audience}: {lower_first(details)}")
    if zone_text in {"все тело", "всё тело"}:
        return sentence(f"Лазерная эпиляция всего тела для {audience}")
    if size:
        return sentence(f"Лазерная эпиляция зоны {zone_text} для {audience} в формате {size}")
    return sentence(f"Лазерная эпиляция зоны {zone_text} для {audience}")


def injection_kind(name):
    name_norm = norm(name)
    if "биоревитализация" in name_norm:
        return "биоревитализация"
    if "ботулинотерапия" in name_norm:
        return "ботулинотерапия"
    if "контурная пластика губ" in name_norm:
        return "контурная пластика губ"
    if "коллагенотерапия" in name_norm:
        return "коллагенотерапия"
    if "мезотерапия волосистой" in name_norm:
        return "мезотерапия волосистой части головы"
    if "мезотерапия" in name_norm:
        return "мезотерапия"
    if "плазмотерапия" in name_norm:
        return "плазмотерапия"
    if "заполнение мимических" in name_norm:
        return "бланширование морщин"
    if "маска после процедуры" in name_norm:
        return "маска после процедуры"
    return "инъекционная косметология"


def injection_desc(name):
    name_norm = norm(name)
    raw = clean(name)
    kind = injection_kind(name)
    if kind == "биоревитализация":
        prep = raw.split("препарат", 1)[1].strip(" ,") if "препарат" in raw.lower() else raw.replace("Биоревитализация,", "").strip()
        return sentence(f"Биоревитализация препаратом {prep}")
    if kind == "ботулинотерапия":
        detail = raw.replace("Ботулинотерапия.", "").strip() or raw
        return sentence(f"Ботулинотерапия: {lower_first(detail)}")
    if kind == "контурная пластика губ":
        detail = raw.replace("Контурная пластика губ -", "").strip()
        if "выведение филлера" in name_norm:
            return sentence("Контурная пластика губ: выведение филлера ферментом infini")
        return sentence(f"Контурная пластика губ препаратом {detail}")
    if kind == "коллагенотерапия":
        detail = raw.replace("Коллагенотерапия -", "").strip()
        return sentence(f"Коллагенотерапия препаратом {detail}")
    if kind == "мезотерапия волосистой части головы":
        detail = raw.replace("Мезотерапия волосистой части головы -", "").strip()
        return sentence(f"Мезотерапия волосистой части головы препаратом {detail}")
    if kind == "мезотерапия":
        detail = raw.replace("Мезотерапия, препарат", "").strip()
        return sentence(f"Мезотерапия препаратом {detail}")
    if kind == "плазмотерапия":
        detail = raw.replace("Плазмотерапия -", "").strip()
        return sentence(f"Плазмотерапия: {detail} для процедуры по назначению специалиста")
    if kind == "бланширование морщин":
        return sentence("Бланширование мимических морщин препаратом Belotero soft / balance 1 ml")
    if kind == "маска после процедуры":
        return sentence("Маска Revi De-Stress после косметологической процедуры")
    return sentence(raw)


def bio_desc(name):
    name_norm = norm(name)
    if "афро" in name_norm:
        if "экстра длин" in name_norm:
            return "Биозавивка афрокудри на экстра длинные волосы с учетом длины и формы завитка."
        if "средн" in name_norm:
            return "Биозавивка афрокудри на среднюю длину волос с учетом формы завитка."
        if "длин" in name_norm:
            return "Биозавивка афрокудри на длинные волосы с учетом длины и формы завитка."
        return "Биозавивка афрокудри с учетом длины волос."
    if "экстра длин" in name_norm:
        return "Биозавивка на экстра длинные волосы с учетом длины и структуры волос."
    if "средн" in name_norm:
        return "Биозавивка на среднюю длину волос с учетом длины и структуры волос."
    if "коротк" in name_norm:
        return "Биозавивка на короткие волосы с учетом длины и структуры волос."
    if "длин" in name_norm:
        return "Биозавивка на длинные волосы с учетом длины и структуры волос."
    return "Биозавивка волос с учетом длины и структуры волос."


def brow_desc(name):
    raw = clean(name)
    name_norm = norm(name)
    if "ваксинг" in name_norm or "восковая депиляция" in name_norm:
        return "Восковая депиляция (ваксинг) 1 зоны лица: щеки, лоб, верхняя губа или подбородок."
    if "комплекс брови и ресницы" in name_norm:
        return "Комплекс для бровей и ресниц: ламинирование, окрашивание, коррекция и уход для бровей."
    if "коррекция бровей окрашивание бровей и ресниц" in name_norm:
        return "Коррекция бровей с окрашиванием бровей и ресниц в одной услуге."
    if "окрашивание бровей коррекция бровей" in name_norm:
        return "Окрашивание и коррекция бровей с подбором формы и оттенка."
    if "коррекция бровей" in name_norm:
        if "муж" in name_norm:
            return "Мужская коррекция бровей с оформлением формы воском или пинцетом."
        if "фитмост" in name_norm:
            return "Коррекция бровей воском или пинцетом по записи ФИТМОСТ."
        return "Коррекция бровей воском и пинцетом с оформлением формы."
    if "ламинирование бровей" in name_norm:
        return "Ламинирование бровей с долговременной укладкой и оформлением формы."
    if "ламинирование ресниц" in name_norm:
        return "Ламинирование ресниц с окрашиванием, ботоксом и коллагеном."
    if "окрашивание бровей" in name_norm:
        if "фитмост" in name_norm:
            return "Окрашивание бровей краской или хной по записи ФИТМОСТ."
        return "Окрашивание бровей краской или хной с подбором оттенка."
    if "окрашивание ресниц" in name_norm:
        return "Окрашивание ресниц для более заметного цвета без наращивания."
    if "счастье для бровей" in name_norm:
        return "Уход для бровей с увлажнением и питанием волосков."
    return sentence(raw)


def lash_desc(name):
    raw = clean(name)
    name_norm = norm(name)
    if "led" in name_norm:
        return "Наращивание ресниц LED: дополнительная услуга к процедуре наращивания."
    if "знакомство с мастером" in name_norm:
        return "Первое наращивание ресниц у мастера с подбором эффекта и объема."
    if "консультация с отрисовкой" in name_norm:
        return "Консультация с отрисовкой эскиза перед процедурой."
    if "коррекция перманентного макияжа" in name_norm:
        return "Коррекция перманентного макияжа с обновлением формы и цвета."
    if "коррекция ресниц" in name_norm:
        return "Коррекция наращенных ресниц с восстановлением выбранного объема."
    if "макияж бровей" in name_norm and "пудров" in name_norm:
        return "Перманентный макияж бровей в технике пудрового напыления."
    if "перманентный макияж бровей" in name_norm:
        return "Перманентный макияж бровей с подбором формы и оттенка."
    if "перманентный макияж губ" in name_norm:
        return "Перманентный макияж губ с подбором оттенка."
    if ("перманент" in name_norm or "пермнент" in name_norm) and "межреснич" in name_norm:
        return "Перманентный макияж глаз в межресничной зоне."
    if "снятие" in name_norm:
        return "Снятие наращенных ресниц без новой процедуры наращивания."
    if "лучики" in name_norm:
        return "Наращивание ресниц с эффектом «лучики»."
    if "наращивание ресниц" in name_norm:
        tail = raw.replace("Наращивание ресниц", "").strip()
        return sentence(f"Наращивание ресниц {tail} с сохранением выбранного объема")
    return sentence(raw)


def nail_desc(name):
    raw = clean(name)
    name_norm = norm(name)
    if "гигиенический педикюр" in name_norm:
        return "Гигиенический педикюр с обработкой стоп, ногтей и кутикулы."
    if "детский маникюр" in name_norm:
        return sentence(raw + " с бережной обработкой ногтей и кутикулы")
    if "маникюр комбинированный" in name_norm:
        return "Комбинированный или аппаратный маникюр без покрытия с обработкой ногтей и кутикулы."
    if "маникюр мужской" in name_norm:
        return "Мужской маникюр с обработкой ногтей и кутикулы без декоративного покрытия."
    if "маникюр с покрытием гель" in name_norm:
        return "Маникюр с покрытием гель-лаком и обработкой ногтей и кутикулы."
    if "маникюр с покрытием лечебным" in name_norm:
        return "Маникюр с покрытием лечебным лаком и обработкой ногтей."
    if "мужской педикюр" in name_norm:
        return "Мужской педикюр с обработкой стоп и ногтей."
    if "парафинотерапия" in name_norm:
        return "Парафинотерапия для ухода за кожей рук или стоп."
    if "педикюр с покрытием" in name_norm:
        return "Педикюр с покрытием гель-лаком и обработкой стоп и ногтей."
    if "покрытие лаком" in name_norm and "лечеб" in name_norm:
        return "Покрытие ногтей лечебным лаком."
    if "покрытие цветным" in name_norm:
        return "Покрытие ногтей цветным лаком."
    if "ремонт ногтя" in name_norm:
        return "Ремонт ногтя с восстановлением формы ногтевой пластины."
    if "снятие гель" in name_norm:
        return "Снятие гель-лака с ногтей перед новым покрытием или уходом."
    if "укрепление ногтей" in name_norm:
        return "Укрепление ногтей твердым гелем."
    if "японский маникюр" in name_norm:
        return "Японский маникюр с уходом за ногтевой пластиной."
    return sentence(raw)


def hair_color_desc(name):
    raw = clean(name)
    name_norm = norm(name)
    suffix = " без учета материалов" if "без учета материалов" in name_norm else ""
    if "air touch" in name_norm or "эир тач" in name_norm:
        return "Окрашивание волос в технике Air Touch" + suffix + "."
    if "балаяж" in name_norm:
        return "Окрашивание волос в технике балаяж" + suffix + "."
    if "выход из темного" in name_norm:
        return sentence("Окрашивание волос: выход из темного цвета " + ("сложный" if "сложный" in name_norm else "простой") + suffix)
    if "контуринг" in name_norm:
        return sentence("Окрашивание волос: контуринг " + ("сложный" if "сложный" in name_norm else "простой") + suffix)
    if "корней" in name_norm:
        return "Окрашивание корней волос без учета материалов."
    if "сложное окрашивание" in name_norm:
        return "Сложное окрашивание волос без учета материалов."
    if "тонирование" in name_norm:
        return "Тонирование волос для обновления оттенка."
    if "тотал блонд" in name_norm:
        return sentence("Окрашивание волос тотал блонд " + ("сложный" if "сложный" in name_norm else "простой") + suffix)
    if "шатуш" in name_norm:
        return "Окрашивание волос в технике шатуш."
    return sentence("Окрашивание волос: " + raw)


def hair_care_desc(name):
    raw = clean(name)
    name_norm = norm(name)
    suffix = " без учета материалов" if "без учета материалов" in name_norm else ""
    if "биксипластия" in name_norm:
        if "длинные" in name_norm and "экстра" not in name_norm:
            length = "длинные волосы"
        elif "средние" in name_norm:
            length = "средние волосы"
        elif "короткие" in name_norm:
            length = "короткие волосы"
        else:
            length = "волосы"
        return sentence(f"Уход для волос: биксипластия на {length}{suffix}")
    if "ботокс для волос" in name_norm:
        return sentence("Уход для волос: ботокс для волос" + suffix)
    if "кератин" in name_norm:
        return sentence("Уход для волос: кератиновый уход" + suffix)
    if "коллаген mix" in name_norm:
        return sentence("Уход для волос: коллагеновый уход MIX" + suffix)
    if "пиу" in name_norm:
        return sentence("Уход для волос: протокол ПИУ" + suffix)
    if "счастье для волос" in name_norm:
        return sentence("Уход для волос «Счастье для волос»" + suffix)
    if "увлажняющий уход" in name_norm:
        return sentence("Увлажняющий уход для волос" + suffix)
    return sentence("Уход для волос: " + raw)


def aesthetic_desc(name):
    raw = clean(name)
    name_norm = norm(name)
    if "карбокситерапия поверхностный пилинг" in name_norm:
        return "Карбокситерапия и поверхностный пилинг с выбранным кислотным составом."
    if "карбокситерапия" in name_norm:
        return "Карбокситерапия для ухода за лицом по показаниям специалиста."
    if "классический массаж лица" in name_norm and "альгинатная" in name_norm:
        return "Классический массаж лица 45 минут с альгинатной маской."
    if "классический массаж лица" in name_norm:
        return "Классический массаж лица продолжительностью 45 минут."
    if "комплексная чистка лица" in name_norm:
        gender = "мужская" if "мужская" in name_norm else "женская" if "женская" in name_norm else ""
        extra = " с пилингом BioRePeelCl13" if "biorepeel" in name_norm else " с поверхностным пилингом" if "поверхностный пилинг" in name_norm else ""
        return sentence("Комплексная чистка лица " + gender + extra)
    if "консультация врача косметолога лечение акне первичный" in name_norm:
        return "Первичная консультация врача-косметолога по лечению акне."
    if "консультация врача косметолога лечение акне повторный" in name_norm:
        return "Повторная консультация врача-косметолога по лечению акне."
    if "консультация врача косметолога" in name_norm:
        return "Консультация врача-косметолога по состоянию кожи и подбору процедуры."
    if "пилинг джесснера" in name_norm:
        return "Пилинг Джесснера: 1 слой, каждый последующий слой оплачивается отдельно."
    if "biorepeel" in name_norm:
        return "Поверхностный пилинг BioRePeelCl13."
    if "азелаиновый" in name_norm:
        return "Поверхностный азелаиновый пилинг."
    if "миндальный" in name_norm:
        return "Поверхностный миндальный пилинг."
    if "салициловый" in name_norm:
        return "Поверхностный салициловый пилинг."
    if "феруловый" in name_norm:
        return "Поверхностный феруловый пилинг."
    if "анти акне" in name_norm:
        return "Уход за лицом анти-акне с противовоспалительным и себорегулирующим действием."
    if "глубокое увлажнение" in name_norm:
        return "Уход за лицом для глубокого увлажнения кожи и сияния."
    if "пигментации" in name_norm:
        return "Уход за лицом для коррекции пигментации и выравнивания тона кожи."
    if "розацеа" in name_norm:
        return "Уход за лицом при розацеа с учетом чувствительности кожи."
    return sentence(raw)


def child_desc(name):
    raw = clean(name)
    name_norm = norm(name)
    if "12 15" in name_norm:
        return "Детская стрижка для возраста 12-15 лет."
    if "до 7" in name_norm:
        return "Детская стрижка для детей до 7 лет."
    if "модельная" in name_norm:
        return "Детская модельная стрижка с оформлением формы."
    if "8 до 12" in name_norm:
        return "Детская стрижка для возраста от 8 до 12 лет."
    if "укладка" in name_norm:
        return "Детская укладка волос для аккуратной прически."
    if "плетение" in name_norm:
        return "Детская укладка с плетением волос для аккуратной прически."
    return sentence(raw)


def makeup_desc(name):
    raw = clean(name)
    name_norm = norm(name)
    if "вечерний" in name_norm:
        return "Вечерний макияж для выразительного образа."
    if "нюдовый" in name_norm:
        return "Нюдовый макияж с естественным акцентом на черты лица."
    if "обучение" in name_norm:
        return "Обучение макияжу для себя с разбором техник и оттенков."
    if "свадебный" in name_norm:
        return "Свадебный макияж для образа невесты и фотосъемки."
    if "укладка" in name_norm:
        return "Укладка волос: легкие локоны, выпрямление или мокрый эффект."
    return sentence(raw)


def podology_desc(name):
    raw = clean(name)
    name_norm = norm(name)
    if "гигиеническая обработка" in name_norm:
        return "Подология: гигиеническая обработка стоп в формате классического педикюра."
    if "забор биоматериала" in name_norm:
        return "Подология: забор биоматериала для диагностики."
    if "комплексная обработка стоп" in name_norm:
        return "Подология: комплексная обработка стоп и ногтей."
    if "консультация подолога" in name_norm:
        return "Консультация подолога по состоянию стоп и ногтей."
    if "вросшего ногтя" in name_norm:
        return "Подологическая обработка вросшего ногтя."
    if "диабетической стопы" in name_norm:
        return "Подологическая обработка диабетической стопы."
    if "протезирование ногтя" in name_norm:
        return "Протезирование ногтя с восстановлением формы ногтевой пластины."
    if "титанов" in name_norm:
        return "Установка титановой нити для коррекции формы ногтя."
    return sentence(raw)


def haircut_desc(name, category):
    name_norm = norm(name)
    category_norm = norm(category)
    if "бороды" in name_norm:
        return "Оформление бороды и усов с коррекцией формы."
    if "камуфляж" in name_norm:
        return "Камуфляж седины для мужчин без учета материалов."
    if "укладка" in name_norm:
        return "Мужская укладка волос с учетом формы стрижки."
    if "муж" in category_norm:
        return "Мужская стрижка с оформлением формы и длины волос."
    if "челк" in name_norm:
        return "Стрижка челки с оформлением длины и формы."
    return "Женская стрижка с оформлением формы и длины волос."


def massage_desc(name):
    name_norm = norm(name)
    if "расслабляющий" in name_norm:
        return "Расслабляющий массаж всего тела продолжительностью 60 минут."
    if "90" in name_norm:
        return "Спортивный массаж всего тела продолжительностью 90 минут."
    return "Спортивный массаж всего тела продолжительностью 60 минут."


def styling_desc(name):
    name_norm = norm(name)
    if "сложная" in name_norm:
        return "Сложная укладка волос с учетом длины и выбранной формы."
    return "Простая укладка волос для аккуратной формы и объема."


def description(category, name):
    category_norm = norm(category)
    if "лазерная эпиляция" in category_norm:
        return laser_desc(category, name)
    if "инъекционная" in category_norm:
        return injection_desc(name)
    if "биозавивка" in category_norm:
        return bio_desc(name)
    if "бров" in category_norm or "ресниц" in category_norm:
        return brow_desc(name)
    if "лаш" in category_norm:
        return lash_desc(name)
    if "маникюр" in category_norm or "педикюр" in category_norm:
        return nail_desc(name)
    if "окрашивание" in category_norm:
        return hair_color_desc(name)
    if "уход для волос" in category_norm:
        return hair_care_desc(name)
    if "эстетическая" in category_norm:
        return aesthetic_desc(name)
    if "дет" in category_norm:
        return child_desc(name)
    if "визаж" in category_norm:
        return makeup_desc(name)
    if "подология" in category_norm:
        return podology_desc(name)
    if "мужская стрижка" in category_norm or "женская стрижка" in category_norm:
        return haircut_desc(name, category)
    if "массаж" in category_norm:
        return massage_desc(name)
    if "укладки" in category_norm:
        return styling_desc(name)
    return sentence(name)


def keywords(category, name, desc):
    category_norm = norm(category)
    name_norm = norm(name)
    if "лазерная эпиляция" in category_norm:
        return ["лазерная эпиляция"]
    if "инъекционная" in category_norm:
        return [injection_kind(name)]
    if "биозавивка" in category_norm:
        return ["биозавивка"]
    if "бров" in category_norm or "ресниц" in category_norm:
        if "ваксинг" in name_norm or "депиляц" in name_norm:
            return ["восковая депиляция"]
        if "ламинирование ресниц" in name_norm:
            return ["ламинирование ресниц"]
        if "ламинирование бров" in name_norm:
            return ["ламинирование бровей"]
        if "окрашивание ресниц" in name_norm:
            return ["окрашивание ресниц"]
        if "окрашивание бров" in name_norm:
            return ["окрашивание бровей"]
        if "счастье" in name_norm:
            return ["уход для бровей"]
        return ["коррекция бровей"]
    if "визаж" in category_norm:
        if "вечерний" in name_norm:
            return ["вечерний макияж"]
        if "свадебный" in name_norm:
            return ["свадебный макияж"]
        if "обучение" in name_norm:
            return ["обучение макияжу"]
        if "укладка" in name_norm:
            return ["укладка волос"]
        return ["макияж"]
    if "дет" in category_norm:
        if "уклад" in name_norm or "плетен" in name_norm:
            return ["детская укладка"]
        return ["детская стрижка"]
    if "лаш" in category_norm:
        if "перманент" in name_norm or "макияж бровей" in name_norm:
            return ["перманентный макияж"]
        if "коррекция ресниц" in name_norm:
            return ["коррекция ресниц"]
        if "консультация" in name_norm:
            return ["консультация"]
        if "снятие" in name_norm:
            return ["снятие ресниц"]
        if "пермнент" in name_norm:
            return ["перманентный макияж"]
        return ["наращивание ресниц"]
    if "маникюр" in category_norm or "педикюр" in category_norm:
        if "парафинотерапия" in name_norm:
            return ["парафинотерапия"]
        if "ремонт ногтя" in name_norm:
            return ["ремонт ногтя"]
        if "укрепление ногтей" in name_norm:
            return ["укрепление ногтей"]
        if "педикюр" in name_norm:
            return ["педикюр"]
        if "гель" in name_norm or "покрытие" in name_norm:
            return ["покрытие ногтей"]
        return ["маникюр"]
    if "массаж" in category_norm:
        return ["массаж"]
    if "мужская стрижка" in category_norm:
        if "бород" in name_norm:
            return ["оформление бороды"]
        if "камуфляж" in name_norm:
            return ["камуфляж седины"]
        return ["мужская стрижка"]
    if "женская стрижка" in category_norm:
        if "челк" in name_norm:
            return ["стрижка челки"]
        return ["женская стрижка"]
    if "окрашивание" in category_norm:
        if "тонирование" in name_norm:
            return ["тонирование волос"]
        return ["окрашивание волос"]
    if "подология" in category_norm:
        if "консультация подолога" in name_norm:
            return ["консультация подолога"]
        if "вросшего ногтя" in name_norm:
            return ["обработка вросшего ногтя"]
        if "диабетической стопы" in name_norm:
            return ["обработка диабетической стопы"]
        if "протезирование ногтя" in name_norm:
            return ["протезирование ногтя"]
        if "титанов" in name_norm:
            return ["установка титановой нити"]
        return ["подология"]
    if "укладки" in category_norm:
        return ["укладка волос"]
    if "уход для волос" in category_norm:
        return ["уход для волос"]
    if "эстетическая" in category_norm:
        if "чистк" in name_norm:
            return ["чистка лица"]
        if "пилинг" in name_norm:
            return ["пилинг"]
        if "массаж лица" in name_norm:
            return ["массаж лица"]
        if "консультация" in name_norm:
            return ["консультация косметолога"]
        return ["уход за лицом"]
    return [clean(name).lower()]


def qa_issues(desc):
    issues = []
    if not desc.strip():
        issues.append("empty")
    if re.search(r"^([^:]{4,45}):\s*\1[\.\s]*$", desc, re.I):
        issues.append("duplicate_colon")
    if len(desc.strip()) < 35:
        issues.append("too_short")
    if desc.count(":") > 1:
        issues.append("many_colons")
    for bad in ["безболез", "без вреда", "стойкий результат", "мгновенн", "профессиональн"]:
        if bad in norm(desc):
            issues.append("forbidden_" + bad)
    return issues


def build_next_services(services):
    next_services = []
    for service in services:
        item = dict(service)
        desc = description(item.get("category"), item.get("name"))
        item["description"] = desc
        item["keywords"] = keywords(item.get("category"), item.get("name"), desc)
        item["optimized_name"] = ""
        item["optimized_description"] = ""
        item["fallback_used"] = False
        item["fallback_reason"] = ""
        item["guardrail_reasons"] = []
        item["pattern_version_ids"] = []
        item["regeneration_status"] = ""
        next_services.append(item)
    return next_services


def main():
    dry_run = "--apply" not in __import__("sys").argv
    db = DatabaseManager()
    cursor = db.conn.cursor()
    services = _load_active_services_for_business(cursor, BUSINESS_ID)
    next_services = build_next_services(services)
    audit_before = build_services_quality_audit(services)
    audit_after = build_services_quality_audit(next_services)
    qa = Counter()
    samples = defaultdict(list)
    for item in next_services:
        for issue in qa_issues(item.get("description")):
            qa[issue] += 1
        category = str(item.get("category") or "")
        if len(samples[category]) < 2:
            samples[category].append({
                "name": item.get("name"),
                "description": item.get("description"),
                "keywords": item.get("keywords"),
            })

    print("MODE", "dry_run" if dry_run else "apply")
    print("BEFORE", json.dumps(audit_before["summary"], ensure_ascii=False))
    print("AFTER", json.dumps(audit_after["summary"], ensure_ascii=False))
    print("QA", json.dumps(dict(qa), ensure_ascii=False))
    problem_by_id = {item["service_id"]: item for item in audit_after["items"] if item.get("needs_review") or item.get("manual_review")}
    if problem_by_id:
        print("PROBLEMS", len(problem_by_id))
        for item in next_services:
            sid = str(item.get("id") or "")
            if sid in problem_by_id:
                print(json.dumps({
                    "id": sid,
                    "category": item.get("category"),
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "keywords": item.get("keywords"),
                    "quality": problem_by_id[sid],
                }, ensure_ascii=False))
    for category in sorted(samples):
        print("SAMPLE", category, json.dumps(samples[category], ensure_ascii=False))

    if dry_run:
        db.close()
        return

    for item in next_services:
        cursor.execute(
            """
            UPDATE userservices
            SET description = %s,
                keywords = %s,
                optimized_name = '',
                optimized_description = '',
                fallback_used = FALSE,
                fallback_reason = '',
                guardrail_reasons = %s,
                pattern_version_ids = %s,
                updated_at = NOW()
            WHERE id = %s AND business_id = %s
            """,
            (
                item.get("description") or "",
                json.dumps(item.get("keywords") or [], ensure_ascii=False),
                Json([]),
                Json([]),
                item.get("id"),
                BUSINESS_ID,
            ),
        )
    db.conn.commit()
    services_final = _load_active_services_for_business(cursor, BUSINESS_ID)
    audit_final = build_services_quality_audit(services_final)
    print("UPDATED", len(next_services))
    print("FINAL", json.dumps(audit_final["summary"], ensure_ascii=False))
    db.close()


if __name__ == "__main__":
    main()
