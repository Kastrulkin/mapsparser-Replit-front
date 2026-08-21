#!/usr/bin/env python3
"""Run full current-evidence review for candidate group two."""

from pathlib import Path

import prepare_localos_followup_batch_01_20260820


prepare_localos_followup_batch_01_20260820.FIRST_TOUCH_IDS = [
    "d40dbba7-4623-47a3-b0fb-e6222704bf2d",  # АМД Лаборатории
    "a8b9c709-8df7-41a6-b68e-79ba7b90faa9",  # Монрепо
    "3ab0a45b-8271-4a22-ae6b-1c0c38319644",  # Микшель
    "f3bf5d1b-77e6-4074-ab4a-4a24db392cae",  # Be Beauty
    "3fa9f4b9-11ab-4002-9555-c64cb0b183db",  # D. O. M. Beauty bar
    "3e24c1ba-468c-44fd-bec1-8c36fc25710e",  # Dk Clinic
    "c67ba40c-6273-4bf8-b891-159ebc85db96",  # GinkgoLab
    "f3975041-9d05-4f06-82c7-3329105c9c1d",  # La Clinique
    "05cfe9c8-b4e2-43a3-9754-0665eeaddcde",  # LuA. Clinic
    "9f0faad6-a50c-4546-9929-17c3827506c7",  # Myrtille
    "7b726354-11ee-43f7-8d9f-fea972bfaab4",  # PF&Beauty
    "c97069ab-7360-45c7-a292-d2474e14ae8b",  # Zenmodeca
    "2d94915d-4ac3-4f2c-9e1d-68d982715c06",  # Ава-мед
    "315bc903-1744-4194-875a-0e56bb26aa2e",  # АрсВита
    "987b5cf2-d776-4a58-8be4-480e30badec7",  # Ботаника
    "9ea3668c-ec37-4d60-8fa6-bf4d79919276",  # Бьютиплан
    "4d5b2fa5-cd1d-4719-8ecf-7e7aa65a07ba",  # Гормедцентр
    "49fbef40-f114-4c0e-adff-460cac6fa5f3",  # ДМКлиника
    "0141b861-b186-4c62-b1fa-b6d0772695db",  # Инскин
    "632be992-484c-4862-9c32-5b319c227d44",  # Лека-Фарм
    "cad911a5-2680-4b3a-b8a5-da37657c1acc",  # Лица
    "7fd30122-fd7e-43af-a8fa-76389e94e406",  # Медикор
    "404c1efa-9b10-4fe9-9b54-6a76821e1871",  # МедСервис
    "2fd24aee-833a-4832-9dba-ccbba7f0e04c",  # Милано
    "a1126fb8-3b6f-4894-a905-5127d128ba51",  # Мисс Магнет
    "954f0910-8532-4659-af1d-600575d332b9",  # Модифик
    "3be83f0b-4e85-4bfe-a29b-e5d0422aa015",  # Первая семейная клиника
    "9aeda130-1a2e-4c22-a09e-26c6d9d2f767",  # Петергоф-Мед
    "4ad88050-81e1-4817-ad68-c9428fce3505",  # Привилегия Здоровья
    "8f673401-936f-4eb4-bed4-347eb2526dd8",  # Путь к здоровью
    "c8ff6063-d6eb-400b-93bb-d6943aa84dfe",  # Расчеши
    "cc4630ef-6ee3-4ceb-96a9-9127ac27bba6",  # СЗ центр лазерной медицины
    "c01c983e-a758-4c26-b91e-35e6765aed3f",  # Сирин
    "10124aca-3b17-4258-9aae-0020145abd16",  # Стоматолог Пушкин
    "80b1bd09-c8bd-4eab-8300-dc9df1ff111f",  # Стоматология Александрова
]
prepare_localos_followup_batch_01_20260820.OUTPUT_PATH = Path(
    "/app/debug_data/localos-followup-batch-02-candidates-review-20260820.json"
)


if __name__ == "__main__":
    prepare_localos_followup_batch_01_20260820.main()
