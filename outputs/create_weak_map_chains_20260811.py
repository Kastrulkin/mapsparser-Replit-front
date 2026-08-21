#!/usr/bin/env python3
"""Create current-evidence weak-map LocalOS draft chains; never approve, queue, or send."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for path in (str(REPO_ROOT), str(SRC_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from services.contact_intelligence_service import upsert_contact_points  # noqa: E402
from services.outreach_campaign_service import _quality_gate, persist_preview  # noqa: E402
from services.outreach_human_language import review_human_language  # noqa: E402
from services.outreach_safety_service import research_source_fact_fingerprint, strategy_fingerprint  # noqa: E402


RULES_VERSION = "weak_map_owner_rules_v6_20260811"


def msg(observation: str, pain: str, solution: str, cta: str) -> str:
    return "\n\n".join([
        "Здравствуйте! Я Александр Демьянов, основатель LocalOS.",
        observation,
        pain,
        solution,
        cta,
    ])


def beauty_low_rating_first_touch(name: str, rating: str) -> str:
    return "\n\n".join([
        "Здравствуйте! Я Александр Демьянов, основатель LocalOS.",
        f"У {name} сейчас рейтинг {rating} на Яндекс Картах. "
        "С таким рейтингом карточка может терять клиентов из карт.",
        "LocalOS помогает исправить ситуацию: отслеживает отзывы, готовит ответы и подсказывает, что изменить в карточке. "
        "Для одного салона красоты мы с нуля привлекли 10 клиентов с карт.",
        "Стоимость - от 1200 рублей в месяц.",
        "Вам может быть это интересно?",
    ])


def contact(contact_type: str, value: str, source_url: str, *, status: str = "confirmed_source") -> dict[str, Any]:
    return {
        "contact_type": contact_type,
        "value": value,
        "owner_type": "company",
        "source_url": source_url,
        "source_type": "official_map_or_site",
        "provider": "public",
        "confidence": 0.98,
        "verification_status": status,
        "metadata_json": {"recipient_eligible": True, "messageability": "manual_review"},
    }


def touch(channel: str, contact_type: str, contact_value: str, day: int, angle: str, source: str,
          observation: str, pain: str, solution: str, cta: str, subject: str | None = None,
          text_override: str | None = None) -> dict[str, Any]:
    return {
        "channel": channel,
        "contact_type": contact_type,
        "contact_value": contact_value,
        "day": day,
        "angle": angle,
        "source": source,
        "observation": observation,
        "pain": pain,
        "solution": solution,
        "cta": cta,
        "subject": subject,
        "text": text_override or msg(observation, pain, solution, cta),
    }


def low_rating_touch(channel: str, contact_type: str, contact_value: str, day: int,
                     source: str, name: str, rating: str,
                     subject: str | None = None) -> dict[str, Any]:
    return touch(
        channel, contact_type, contact_value, day, "content_operations", source,
        f"У {name} сейчас рейтинг {rating} на Яндекс Картах.",
        "С таким рейтингом карточка может терять клиентов из карт.",
        "LocalOS помогает исправить ситуацию: отслеживает отзывы, готовит ответы и подсказывает, что изменить в карточке. "
        "Для одного салона красоты мы с нуля привлекли 10 клиентов с карт. "
        "Стоимость - от 1200 рублей в месяц.",
        "Вам может быть это интересно?",
        subject=subject,
        text_override=beauty_low_rating_first_touch(name, rating),
    )


def average_ticket_owner_touch(channel: str, contact_type: str, contact_value: str,
                               day: int, source: str, observation: str) -> dict[str, Any]:
    pain = "Вам знакома проблема: услуг много, а средний чек всё равно маленький."
    solution = (
        "LocalOS по вашему прайсу соберёт матрицу услуг и допродаж, "
        "подготовит подсказки для администратора и поможет довести до реальной продажи."
    )
    cta = "Вам было бы интересно увеличить средний чек?"
    return touch(
        channel, contact_type, contact_value, day, "average_ticket", source,
        observation, pain, solution, cta,
        text_override="\n\n".join([
            "Здравствуйте! Я Александр Демьянов, основатель LocalOS.",
            pain,
            solution,
            cta,
        ]),
    )


MAP = {
    "padrina": "https://yandex.com/maps/org/padrina_studio/68716502058/",
    "avicenna": "https://yandex.com/maps/org/avitsenna/1047796383/",
    "dvor": "https://yandex.com/maps/org/kosmetolog_dvorovikova_galina/13215951535/",
    "safonov": "https://yandex.com/maps/org/plasticheskiy_khirurg_safonov_m_s_/189363309405/",
    "olgat": "https://yandex.com/maps/org/dr_olgat/157529796636/",
    "beauty": "https://yandex.com/maps/org/beauty_lab/226635037573/",
    "line": "https://yandex.com/maps/org/liniya_krasoty/169125099398/",
    "oval": "https://yandex.com/maps/org/idealny_oval/143679379669/",
    "magic": "https://yandex.com/maps/org/magic_of_beauty/123757010808/",
    "life": "https://yandex.com/maps/org/life_balance_healthcare/239285984818/",
}


COHORT: dict[str, dict[str, Any]] = {}


def add(workstream_id: str, lead_id: str, name: str, rating: float, ratings: int, reviews: int,
        why_now: str, contacts: list[dict[str, Any]], touches: list[dict[str, Any]]) -> None:
    COHORT[workstream_id] = {
        "lead_id": lead_id,
        "name": name,
        "rating": rating,
        "ratings": ratings,
        "reviews": reviews,
        "why_now": why_now,
        "contacts": contacts,
        "touches": touches,
    }


add(
    "d4333121-071e-40be-a9e4-10604f43f58f", "9aa271b1-ca9b-4f41-a13f-c11bf6c14d9e", "Padrina_studio", 2.5, 6, 3,
    "11 августа 2026: рейтинг 2,5, 6 оценок, 3 отзыва, новостей нет; запись ведёт в DIKIDI.",
    [contact("telegram", "https://t.me/+79602701918", MAP["padrina"]), contact("vk", "https://vk.com/padrina_studio", MAP["padrina"]), contact("phone", "+7 (960) 270-19-18", MAP["padrina"])],
    [
        touch("telegram", "telegram", "https://t.me/+79602701918", 0, "content_operations", MAP["padrina"],
              "У Padrina_studio сейчас рейтинг 2,5 на Яндекс Картах.",
              "С таким рейтингом карточка может терять клиентов из карт.",
              "LocalOS помогает исправить ситуацию: отслеживает отзывы, готовит ответы и подсказывает, что изменить в карточке. Для одного салона красоты мы с нуля привлекли 10 клиентов с карт. Стоимость - от 1200 рублей в месяц.",
              "Вам может быть это интересно?",
              text_override=(
                  "Здравствуйте! Я Александр Демьянов, основатель LocalOS.\n\n"
                  "У Padrina_studio сейчас рейтинг 2,5 на Яндекс Картах. С таким рейтингом карточка может терять клиентов из карт.\n\n"
                  "LocalOS помогает исправить ситуацию: отслеживает отзывы, готовит ответы и подсказывает, что изменить в карточке. Для одного салона красоты мы с нуля привлекли 10 клиентов с карт.\n\n"
                  "Стоимость - от 1200 рублей в месяц.\n\n"
                  "Вам может быть это интересно?"
              )),
        touch("vk_manual", "vk", "https://vk.com/padrina_studio", 7, "content_operations", MAP["padrina"],
              "Вижу, вы пользуетесь DIKIDI.",
              "Подготовка постов для нескольких площадок вручную отнимает время.",
              "На основе выгрузки из DIKIDI LocalOS автоматически подготовит черновики постов о выполненных услугах для Телеграм, VK, Яндекс Карт и прочих.",
              "Вам было бы интересно сэкономить время на ведении соцсетей?",
              text_override=(
                  "Здравствуйте! Я Александр Демьянов, основатель LocalOS.\n\n"
                  "Вижу, вы пользуетесь DIKIDI.\n\n"
                  "На основе выгрузки из DIKIDI LocalOS автоматически подготовит черновики постов о выполненных услугах для Телеграм, VK, Яндекс Карт и прочих.\n\n"
                  "Вам было бы интересно сэкономить время на ведении соцсетей?"
              )),
        touch("phone", "phone", "+7 (960) 270-19-18", 16, "average_ticket", MAP["padrina"],
              "В карточке Padrina_studio опубликованы услуги с ценами - от бровей и ресниц до косметологии.",
              "Вам знакома проблема: услуг много, а средний чек всё равно маленький.",
              "LocalOS по вашему прайсу соберёт матрицу услуг и допродаж, подготовит подсказки для администратора и поможет довести до реальной продажи.",
              "Вам было бы интересно увеличить средний чек?",
              text_override=(
                  "Здравствуйте! Я Александр Демьянов, основатель LocalOS.\n\n"
                  "Вам знакома проблема: услуг много, а средний чек всё равно маленький.\n\n"
                  "LocalOS по вашему прайсу соберёт матрицу услуг и допродаж, подготовит подсказки для администратора и поможет довести до реальной продажи.\n\n"
                  "Вам было бы интересно увеличить средний чек?"
              )),
    ],
)

add(
    "71d18fdb-2823-4b60-b320-262532e75aee", "492caf0b-f633-4fbb-ab05-f1943c61d0f7", "Авиценна", 3.2, 3, 0,
    "11 августа 2026: рейтинг 3,2 при 3 оценках, текстовых отзывов и новостей нет, отметка владельца не видна.",
    [contact("email", "info@avitsenna.ru", "https://avitsenna.ru/"), contact("vk", "https://vk.com/club32016616", MAP["avicenna"]), contact("whatsapp", "https://wa.me/79219544224", "https://avitsenna.ru/"), contact("phone", "+7 (812) 954-42-24", MAP["avicenna"])],
    [
        low_rating_touch("email", "email", "info@avitsenna.ru", 0, MAP["avicenna"],
                         "Авиценны", "3,2", "Авиценна | ЛокалОС | Сотрудничество"),
        touch("vk_manual", "vk", "https://vk.com/club32016616", 5, "content_operations", MAP["avicenna"],
              "В карточке Авиценны на Яндекс Картах сейчас нет раздела с новостями.",
              "Если материалы готовить для сайта, VK и карт отдельно, на одну тему уходит больше времени команды.",
              "LocalOS подготовит из одной согласованной темы отдельные черновики для сайта, VK и Яндекс Карт. Публикация в Картах останется ручной.",
              "Вы бы хотели сэкономить время на подготовке публикаций?"),
        touch("whatsapp", "whatsapp", "https://wa.me/79219544224", 11, "content_operations", MAP["avicenna"],
              "В карточке Авиценны не видна отметка подтверждения владельцем, а услуги и цены в открытом блоке не показаны.",
              "Такие пробелы легко пропустить, когда карточку проверяют вручную от случая к случаю.",
              "LocalOS подготовит короткий чек-лист: какие данные, услуги и ссылки проверить в карточке. Изменения внесёт сотрудник после проверки.",
              "Показать пример такого чек-листа?"),
        touch("phone", "phone", "+7 (812) 954-42-24", 18, "integrated_system", MAP["avicenna"],
              "Авиценна работает в нескольких городах, а в карточке петербургского филиала пока только три оценки.",
              "Для локального филиала дополнительным источником обращений могут стать партнёры рядом с клиникой.",
              "LocalOS подготовит список местных бизнесов со смежной аудиторией и черновик предложения о партнёрстве. Вы сами решите, кому его отправить.",
              "Вам было бы интересно находить новых клиентов через партнёрства?"),
        touch("email", "email", "info@avitsenna.ru", 25, "content_operations", MAP["avicenna"],
              "В карточке Авиценны одновременно видны низкий рейтинг, отсутствие текстовых отзывов и отсутствие новостей.",
              "Когда несколько элементов карточки требуют внимания, полезнее видеть их одним списком, а не проверять по отдельности.",
              "LocalOS соберёт короткую сводку по рейтингу, отзывам, новостям и данным карточки и передаст её сотруднику для ручных изменений.",
              "Показать такую сводку по Авиценне?", "Авиценна | ЛокалОС | Сотрудничество"),
    ],
)

add(
    "664f1753-c6f7-4e17-81f6-4414dcf1ce05", "1658f6ce-c613-46e6-8384-bbe444261f10", "Косметолог Дворовикова Галина", 3.6, 12, 5,
    "11 августа 2026: рейтинг 3,6 при 12 оценках и 5 отзывах; новостей, услуг и отметки владельца не видно.",
    [contact("vk", "https://vk.com/g.dvorovikova", MAP["dvor"]), contact("whatsapp", "https://wa.me/79213267562", MAP["dvor"]), contact("phone", "+7 (921) 326-75-62", MAP["dvor"])],
    [
        touch("vk_manual", "vk", "https://vk.com/g.dvorovikova", 0, "content_operations", MAP["dvor"],
              "У карточки косметолога Галины Дворовиковой сейчас рейтинг 3,6 на Яндекс Картах.",
              "С таким рейтингом карточка может терять клиентов из карт.",
              "LocalOS помогает исправить ситуацию: отслеживает отзывы, готовит ответы и подсказывает, что изменить в карточке. Для одного салона красоты мы с нуля привлекли 10 клиентов с карт. Стоимость - от 1200 рублей в месяц.",
              "Вам может быть это интересно?",
              text_override=beauty_low_rating_first_touch("карточки косметолога Галины Дворовиковой", "3,6")),
        touch("whatsapp", "whatsapp", "https://wa.me/79213267562", 8, "content_operations", MAP["dvor"],
              "В карточке на Яндекс Картах сейчас нет новостей, хотя указаны прямые ссылки на VK и WhatsApp.",
              "Посты для нескольких площадок приходится писать и редактировать несколько раз, а это отнимает время.",
              "LocalOS подготовит из одной согласованной темы отдельные черновики для VK и Яндекс Карт. Публикация в Картах останется ручной.",
              "Вы бы хотели сэкономить время на постах?"),
        touch("phone", "phone", "+7 (921) 326-75-62", 18, "content_operations", MAP["dvor"],
              "В карточке косметолога Галины Дворовиковой не видны услуги с ценами и отметка подтверждения владельцем.",
              "Клиенту сложнее заранее понять, с какими процедурами можно обратиться и сколько они стоят.",
              "LocalOS подготовит чек-лист данных и услуг для карточки и черновики коротких описаний. Изменения останутся ручными.",
              "Показать пример такого чек-листа?"),
    ],
)

add(
    "0eaf5900-651c-4753-a662-580043777786", "cfb84d6c-bfd4-49dc-8521-0183cb471575", "Пластический хирург Сафонов М. С.", 3.7, 19, 4,
    "11 августа 2026: рейтинг 3,7 при 19 оценках и 4 отзывах; услуг и отметки владельца не видно.",
    [contact("vk", "https://vk.com/doctor_safonov", MAP["safonov"]), contact("whatsapp", "https://wa.me/79119902685", "http://doctorsafonov.ru/"), contact("phone", "+7 (911) 924-82-61", MAP["safonov"])],
    [
        low_rating_touch("vk_manual", "vk", "https://vk.com/doctor_safonov", 0, MAP["safonov"],
                         "карточки пластического хирурга Максима Сафонова", "3,7"),
        touch("whatsapp", "whatsapp", "https://wa.me/79119902685", 9, "content_operations", MAP["safonov"],
              "В карточке на Яндекс Картах опубликованы две новости, а на сайте и в VK материалов о работе больше.",
              "Переносить одну тему на разные площадки вручную - дополнительная работа для команды.",
              "LocalOS подготовит отдельные черновики для сайта, VK и Яндекс Карт из одной согласованной темы. Публикация в Картах останется ручной.",
              "Вы бы хотели сэкономить время на подготовке публикаций?"),
        touch("phone", "phone", "+7 (911) 924-82-61", 19, "content_operations", MAP["safonov"],
              "В карточке Максима Сафонова сейчас не видны услуги с ценами и отметка подтверждения владельцем.",
              "Пациенту сложнее заранее понять направления работы и следующий шаг для обращения.",
              "LocalOS подготовит чек-лист карточки и черновики кратких описаний только из подтверждённых данных. Медицинские формулировки останутся на проверке врача.",
              "Показать пример такого чек-листа?"),
    ],
)

add(
    "8cfc1174-4c69-41e5-982b-6a94171ee267", "1e8aea4f-b94e-4307-9895-14df8719f7c2", "Dr. OlgaT", 4.2, 3, 3,
    "11 августа 2026: рейтинг 4,2 при 3 оценках и 3 отзывах; одна новость, услуг и отметки владельца не видно.",
    [contact("telegram", "https://t.me/Dr_OlgaT", "https://t.me/Dr_OlgaT"), contact("phone", "+7 (995) 221-40-52", MAP["olgat"])],
    [
        low_rating_touch("telegram", "telegram", "https://t.me/Dr_OlgaT", 0, MAP["olgat"],
                         "Dr. OlgaT", "4,2"),
        touch("phone", "phone", "+7 (995) 221-40-52", 12, "content_operations", MAP["olgat"],
              "В карточке Dr. OlgaT опубликована одна новость и больше двухсот фотографий, но услуги с ценами не показаны.",
              "Когда фотографии, услуги и новости обновляются отдельно, карточку приходится проверять вручную.",
              "LocalOS подготовит короткую сводку по контенту карточки и черновики описаний услуг. Изменения внесёт сотрудник после проверки.",
              "Показать пример такой сводки?"),
    ],
)

add(
    "bbe5c670-644d-488e-9b91-f30046e3c47b", "e21da65b-6553-4646-add4-00d28c3dd7c5", "Beauty Lab", 4.4, 7, 7,
    "11 августа 2026: рейтинг 4,4 при 7 оценках и 7 отзывах; новостей нет, видны две услуги.",
    [contact("vk", "https://vk.com/bbeauty_lab_spb", MAP["beauty"]), contact("whatsapp", "https://wa.me/79921722196", MAP["beauty"]), contact("phone", "+7 (992) 172-21-96", MAP["beauty"])],
    [
        touch("vk_manual", "vk", "https://vk.com/bbeauty_lab_spb", 0, "content_operations", MAP["beauty"],
              "У Beauty Lab сейчас рейтинг 4,4 на Яндекс Картах.",
              "С таким рейтингом карточка может терять клиентов из карт.",
              "LocalOS помогает исправить ситуацию: отслеживает отзывы, готовит ответы и подсказывает, что изменить в карточке. Для одного салона красоты мы с нуля привлекли 10 клиентов с карт. Стоимость - от 1200 рублей в месяц.",
              "Вам может быть это интересно?",
              text_override=beauty_low_rating_first_touch("Beauty Lab", "4,4")),
        touch("whatsapp", "whatsapp", "https://wa.me/79921722196", 8, "content_operations", MAP["beauty"],
              "В карточке Beauty Lab сейчас нет новостей, хотя указаны Telegram, VK и услуги студии.",
              "Посты для нескольких площадок приходится писать и редактировать несколько раз, а это отнимает время.",
              "LocalOS подготовит из одной согласованной темы отдельные черновики для Telegram, VK и Яндекс Карт. Публикация в Картах останется ручной.",
              "Вы бы хотели сэкономить время на постах?"),
        touch("phone", "phone", "+7 (992) 172-21-96", 18, "content_operations", MAP["beauty"],
              "В карточке Beauty Lab сейчас видны только две услуги, а у одной указана цена 1 рубль.",
              "Неполный или технический прайс может мешать клиенту понять реальные услуги и стоимость.",
              "LocalOS подготовит чек-лист прайса и черновики коротких описаний для ручного обновления карточки.",
              "Показать пример такого чек-листа?"),
    ],
)

add(
    "e4ef90f7-20a1-420e-ac4f-66640cc7c40c", "510f8e0c-8f2f-485b-ba9a-4924918d2b36", "Линия красоты", 4.4, 9, 7,
    "11 августа 2026: рейтинг 4,4 при 9 оценках и 7 отзывах; Telegram обновлялся 23 июля, новостей на карте нет.",
    [contact("vk", "https://vk.com/thebeautyline_01", MAP["line"]), contact("phone", "+7 (904) 334-00-10", MAP["line"]), contact("phone", "+7 (812) 988-32-02", MAP["line"])],
    [
        low_rating_touch("vk_manual", "vk", "https://vk.com/thebeautyline_01", 0, MAP["line"],
                         "Линии красоты", "4,4"),
        touch("phone", "phone", "+7 (904) 334-00-10", 9, "content_operations", "https://t.me/ShusharubeautyLinee/22",
              "23 июля в Telegram Линии красоты вышел пост со свободными окнами, а в карточке Яндекс Карт новостей сейчас нет.",
              "Посты для нескольких площадок приходится писать и редактировать несколько раз, а это отнимает время.",
              "LocalOS подготовит из одной согласованной темы отдельные черновики для Telegram, VK и Яндекс Карт. Публикация в Картах останется ручной.",
              "Вы бы хотели сэкономить время на постах?"),
        average_ticket_owner_touch(
            "phone", "phone", "+7 (812) 988-32-02", 19, MAP["line"],
            "В карточке Линии красоты опубликованы услуги косметолога с ценами."
        ),
    ],
)

add(
    "4bdcced4-2edf-4bfe-91e0-eb03e06c46f8", "359271c0-b6ea-4f8a-9b87-95cab5486a05", "Идеальный овал", 4.4, 9, 9,
    "11 августа 2026: рейтинг 4,4 при 9 оценках и 9 отзывах; Telegram обновлялся 24 июня, новостей на карте нет.",
    [contact("phone", "+7 (905) 200-88-81", MAP["oval"])],
    [
        low_rating_touch("phone", "phone", "+7 (905) 200-88-81", 0, MAP["oval"],
                         "Идеального овала", "4,4"),
    ],
)

add(
    "fc457fdb-20d6-4484-b5aa-6a925d89588c", "ac14050a-6072-4426-ab66-afaf8bc97081", "Magic of beauty", 4.3, 6, 5,
    "11 августа 2026: рейтинг 4,3 при 6 оценках и 5 отзывах; новости и услуги на карте не видны, отзывы в основном об обучении.",
    [contact("telegram", "https://t.me/Manoshina_3003", "https://magicofbeauty.ru/kosmetik-estetist"), contact("vk", "https://vk.com/cosmetology_yulya", MAP["magic"]), contact("whatsapp", "https://wa.me/79312635121", MAP["magic"]), contact("phone", "+7 (931) 263-51-21", MAP["magic"])],
    [
        touch("telegram", "telegram", "https://t.me/Manoshina_3003", 0, "content_operations", MAP["magic"],
              "У Magic of beauty сейчас рейтинг 4,3 на Яндекс Картах.",
              "С таким рейтингом карточка может терять клиентов из карт.",
              "LocalOS помогает исправить ситуацию: отслеживает отзывы, готовит ответы и подсказывает, что изменить в карточке. Для одного салона красоты мы с нуля привлекли 10 клиентов с карт. Стоимость - от 1200 рублей в месяц.",
              "Вам может быть это интересно?",
              text_override=beauty_low_rating_first_touch("Magic of beauty", "4,3")),
        touch("vk_manual", "vk", "https://vk.com/cosmetology_yulya", 6, "content_operations", MAP["magic"],
              "В отзывах карточки Magic of beauty сейчас много материалов об обучении, а услуги для клиентов отдельным списком не показаны.",
              "Из карточки может быть не сразу понятно, где обучение, а где запись на процедуры.",
              "LocalOS подготовит чек-лист разделения направлений и черновики коротких описаний для ручного обновления карточки.",
              "Показать пример такого чек-листа?"),
        touch("whatsapp", "whatsapp", "https://wa.me/79312635121", 13, "content_operations", MAP["magic"],
              "В карточке Magic of beauty сейчас нет новостей, хотя на сайте и в соцсетях представлены косметология и обучение.",
              "Посты для нескольких площадок приходится писать и редактировать несколько раз, а это отнимает время.",
              "LocalOS подготовит из одной согласованной темы отдельные черновики для соцсетей и Яндекс Карт. Публикация в Картах останется ручной.",
              "Вы бы хотели сэкономить время на постах?"),
        touch("phone", "phone", "+7 (931) 263-51-21", 22, "integrated_system", MAP["magic"],
              "Magic of beauty работает и с клиентами, и с начинающими косметологами.",
              "Для двух направлений могут подойти разные местные партнёры и разные предложения.",
              "LocalOS подготовит список местных бизнесов со смежной аудиторией и черновик предложения о партнёрстве. Вы сами решите, кому его отправить.",
              "Вам было бы интересно находить новых клиентов через партнёрства?"),
    ],
)

add(
    "d17b96c1-18cb-4a66-ba93-88ff64e23ac7", "7999e5da-11e7-4d8d-8f51-050508e924b9", "Life Balance healthcare", 4.3, 7, 6,
    "11 августа 2026: рейтинг 4,3 при 7 оценках и 6 отзывах; одна новость, отметка владельца не видна.",
    [contact("telegram", "https://t.me/WhiteTeethSmile", MAP["life"]), contact("whatsapp", "https://wa.me/79312259882", MAP["life"]), contact("phone", "+7 (931) 225-98-82", MAP["life"])],
    [
        low_rating_touch("telegram", "telegram", "https://t.me/WhiteTeethSmile", 0, MAP["life"],
                         "Life Balance healthcare", "4,3"),
        average_ticket_owner_touch(
            "whatsapp", "whatsapp", "https://wa.me/79312259882", 8, MAP["life"],
            "В карточке Life Balance представлены разные услуги с ценами."
        ),
        touch("phone", "phone", "+7 (931) 225-98-82", 18, "integrated_system", MAP["life"],
              "Отзывы Life Balance охватывают массаж, SPA, ресницы и другие направления.",
              "Для разных услуг могут подойти разные местные партнёры со смежной аудиторией.",
              "LocalOS подготовит список местных бизнесов и черновик предложения о партнёрстве. Вы сами решите, кому его отправить.",
              "Вам было бы интересно находить новых клиентов через партнёрства?"),
    ],
)


REJECTED = {
    "427535ec-b536-49cd-a5b1-3f5a3715c6c6": "CURRENT_LOCATION_IDENTITY_CONFLICT",
    "8a0bdc6a-a6fc-4d23-b83c-2a378d111f0f": "CURRENT_RECIPIENT_IDENTITY_CONFLICT",
}
REVISE = {"17832397-bb39-49e8-889f-4a5dfb3a65b4": "NO_VERIFIED_MESSAGEABLE_ROUTE"}


def connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def actor_id(cur: Any) -> str:
    cur.execute("SELECT id FROM users WHERE COALESCE(is_superadmin,FALSE)=TRUE AND is_active=TRUE ORDER BY updated_at DESC NULLS LAST LIMIT 1")
    row = cur.fetchone()
    if not row:
        raise RuntimeError("active_superadmin_not_found")
    return str(row["id"])


def sender_id(cur: Any) -> str:
    cur.execute("SELECT id FROM outreach_sender_accounts WHERE sender_identity='localosgo@gmail.com' AND channel='email' AND status='connected' AND outreach_enabled=TRUE ORDER BY updated_at DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        raise RuntimeError("localosgo_sender_missing")
    return str(row["id"])


def cp_id(cur: Any, lead_id: str, contact_type: str, value: str) -> str:
    cur.execute("""SELECT id FROM lead_contact_points WHERE lead_id=%s AND contact_type=%s AND value=%s
                   ORDER BY CASE verification_status WHEN 'verified' THEN 0 WHEN 'confirmed_source' THEN 1 WHEN 'found' THEN 2 ELSE 3 END, updated_at DESC LIMIT 1""", (lead_id, contact_type, value))
    row = cur.fetchone()
    if not row:
        raise LookupError(f"contact_missing:{lead_id}:{contact_type}:{value}")
    return str(row["id"])


def update_research(cur: Any, workstream_id: str, item: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cur.execute("SELECT * FROM lead_workstream_research WHERE workstream_id=%s ORDER BY researched_at DESC NULLS LAST LIMIT 1", (workstream_id,))
    research = dict(cur.fetchone() or {})
    if not research:
        raise RuntimeError(f"research_missing:{item['name']}")
    evidence = [{
        "evidence_id": f"weak-map:{item['lead_id']}:20260811",
        "kind": "map_issue",
        "observation": item["why_now"],
        "source_url": item["touches"][0]["source"],
        "source_title": f"{item['name']} — Яндекс Карты",
        "source_type": "yandex_maps_exact_place",
        "source_date": "date unavailable",
        "researched_at": datetime.now(timezone.utc).isoformat(),
        "confidence": "high",
        "usable_for_outreach": True,
    }]
    report_hash = canonical_hash({"why_now": item["why_now"], "evidence": evidence, "rules": RULES_VERSION})
    cur.execute("""UPDATE lead_workstream_research SET score=%s, qualification_stage='problem_aware', signal_label='reason_to_check', why_now=%s,
                   signals_json=%s, sources_json=%s, evidence_json=%s, researched_at=NOW(), report_hash=%s
                   WHERE id=%s""", (90, item["why_now"], Json(evidence), Json([{"url": ev["source_url"], "title": ev["source_title"], "observed_at": ev["researched_at"], "source_type": ev["source_type"]} for ev in evidence]), Json(evidence), report_hash, research["id"]))
    cur.execute("UPDATE prospectingleads SET rating=%s, reviews_count=%s, updated_at=NOW() WHERE id=%s", (item["rating"], item["reviews"], item["lead_id"]))
    research.update({"why_now": item["why_now"], "signals_json": evidence, "sources_json": evidence, "evidence_json": evidence, "report_hash": report_hash})
    return research, evidence


def build_touch(item: dict[str, Any], t: dict[str, Any], index: int, contact_point_id: str, email_sender: str, fingerprint: str) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence_id = f"weak-map:{item['lead_id']}:{index}:20260811"
    candidate = {
        "id": evidence_id,
        "evidence_id": evidence_id,
        "evidence_ids": [evidence_id],
        "evidence_kind": "map_issue",
        "evidence_status": "observed",
        "supporting_evidence": [{"evidence_id": evidence_id, "source_url": t["source"]}],
        "recipient": item["name"],
        "recipient_segment": "beauty_team",
        "sender_mode": "localos",
        "observation": t["observation"],
        "observed_fact": t["observation"],
        "source_url": t["source"],
        "problem_hypothesis": t["pain"],
        "pain_hypothesis": t["pain"],
        "bridge": t["pain"],
        "relevance_bridge": t["pain"],
        "solution": t["solution"],
        "localos_action": t["solution"],
        "offer": t["solution"],
        "cta": t["cta"],
        "next_step": t["cta"],
        "freshness": "fresh",
        "confidence": 0.98,
    }
    human = review_human_language(t["text"], pain_hypothesis=t["pain"], require_signal_flow=t["angle"] == "signal")
    channel_status = "ready" if t["channel"] == "email" else "manual"
    gate = _quality_gate(t["text"], candidate, {"proof": "manual_review", "forbidden_claims": []}, channel=t["channel"], channel_status=channel_status, suppressed=False, angle=t["angle"])
    if not human["passed"] or not gate["passed"]:
        raise ValueError(f"quality_failed:{item['name']}:{index}:{human.get('reason_codes')}:{gate.get('reason_codes')}")
    strategy = {"human_edited": True, "content_source": "weak_map_current_audit_20260811", "rules_version": RULES_VERSION}
    record = {
        "sequence_index": index,
        "channel": t["channel"],
        "day_offset": t["day"],
        "scheduled_at": datetime.now(timezone.utc) + timedelta(days=t["day"]),
        "angle": t["angle"],
        "subject": t["subject"],
        "text": t["text"],
        "quality_gate": gate,
        "channel_status": channel_status,
        "contact_point_id": contact_point_id,
        "sender_account_id": email_sender if t["channel"] == "email" else None,
        "evidence_id": evidence_id,
        "evidence_kind": "map_issue",
        "source_url": t["source"],
        "observation": t["observation"],
        "problem_hypothesis": t["pain"],
        "pain_hypothesis": t["pain"],
        "solution": t["solution"],
        "relevance_bridge": t["pain"],
        "source_fact_fingerprint": fingerprint,
        "strategy": strategy,
        "strategy_fingerprint": strategy_fingerprint(strategy),
        "generation_source": "manual_product_correction",
        "human_edited": True,
    }
    return record, candidate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--workstream-id", action="append", default=[])
    args = parser.parse_args()
    os.environ["OUTREACH_ROOM_SYNC_ENABLED"] = "false"
    conn = connect()
    conn.set_session(readonly=False, autocommit=False)
    result: dict[str, Any] = {"dry_run": not args.apply, "rules_version": RULES_VERSION, "ready": [], "revise": REVISE, "reject": REJECTED}
    try:
        cur = conn.cursor()
        actor = actor_id(cur)
        email_sender = sender_id(cur)
        selected_workstreams = set(args.workstream_id)
        unknown_workstreams = selected_workstreams.difference(COHORT)
        if unknown_workstreams:
            raise RuntimeError(f"unknown_workstream_ids:{sorted(unknown_workstreams)}")
        cohort = {
            workstream_id: item
            for workstream_id, item in COHORT.items()
            if not selected_workstreams or workstream_id in selected_workstreams
        }
        for workstream_id, item in cohort.items():
            cur.execute("SELECT * FROM lead_workstreams WHERE id=%s FOR UPDATE", (workstream_id,))
            ws = cur.fetchone()
            if not ws or ws["workstream_type"] != "localos_sales":
                raise RuntimeError(f"workstream_invalid:{workstream_id}")
            cur.execute("SELECT COUNT(*) n FROM outreach_suppressions WHERE lead_id=%s AND (expires_at IS NULL OR expires_at>NOW())", (item["lead_id"],))
            if int(cur.fetchone()["n"]):
                raise RuntimeError(f"suppressed:{item['name']}")
            cur.execute("SELECT COUNT(*) n FROM outreach_inbound_events WHERE lead_id=%s AND is_human=TRUE", (item["lead_id"],))
            if int(cur.fetchone()["n"]):
                raise RuntimeError(f"human_inbound:{item['name']}")
            upsert_contact_points(cur, item["lead_id"], item["contacts"])
            research, evidence = update_research(cur, workstream_id, item)
            fingerprint = research_source_fact_fingerprint(research)
            cur.execute("SELECT sender_profile_id, selected_offer_json, trust_strategy FROM outreach_campaigns WHERE workstream_id=%s ORDER BY version DESC LIMIT 1", (workstream_id,))
            previous = cur.fetchone()
            if not previous:
                raise RuntimeError(f"campaign_context_missing:{item['name']}")
            records, candidates = [], []
            for index, t in enumerate(item["touches"]):
                point_id = cp_id(cur, item["lead_id"], t["contact_type"], t["contact_value"])
                record, candidate = build_touch(item, t, index, point_id, email_sender, fingerprint)
                records.append(record)
                candidates.append(candidate)
            preview = {
                "status": "ready",
                "workstream_id": workstream_id,
                "lead_id": item["lead_id"],
                "lead": {"name": item["name"]},
                "scope_type": "platform",
                "business_id": None,
                "sender_profile_id": str(previous["sender_profile_id"]),
                "sender_mode": "localos",
                "sender_scope_type": "platform",
                "selected_offer": dict(previous.get("selected_offer_json") or {}),
                "selected_trust": {"strategy": previous.get("trust_strategy")},
                "decision": {"action": "draft_only", "reason": "user_requested_weak_map_chain"},
                "evidence": evidence,
                "personalization_candidates": candidates,
                "touches": records,
            }
            saved = persist_preview(cur, preview, user_id=actor)
            cur.execute("""UPDATE outreach_campaigns SET status='cancelled', stop_reason=%s, updated_at=NOW()
                           WHERE workstream_id=%s AND status='draft' AND id<>%s""", (f"superseded_by_{RULES_VERSION}", workstream_id, saved["id"]))
            result["ready"].append({
                "lead": item["name"],
                "lead_id": item["lead_id"],
                "workstream_id": workstream_id,
                "saved": saved,
                "touches": [{"channel": rec["channel"], "score": rec["quality_gate"].get("total_score"), "passed": rec["quality_gate"]["passed"], "subject": rec.get("subject"), "text": rec["text"]} for rec in records],
            })
        for workstream_id, reason in REJECTED.items():
            if selected_workstreams and workstream_id not in selected_workstreams:
                continue
            cur.execute("UPDATE outreach_campaigns SET status='cancelled', stop_reason=%s, updated_at=NOW() WHERE workstream_id=%s AND status='draft'", (reason, workstream_id))
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    result["canonical_sha256"] = canonical_hash(result["ready"])
    result["approved"] = 0
    result["queued"] = 0
    result["sent"] = 0
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
