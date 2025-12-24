#!/usr/bin/env python3
"""
Скрипт для форматирования cookies из таблицы в строку для вставки в админскую панель.
"""

# Cookies из таблицы (имя = значение)
# Формат: имя \t значение
cookies_raw = """_yasc	BtTrBJd3OEdXO13POSglq9UeNPZmM+jEeqLq7W9bj+qxZ6Yx2o/Iszq18+3Ay18K
_yasc	PdppVjKE8jAxfXm46Stwv9EEwnW/C3x9QlvFzfYwoeXI3aRf5V0ndWWLbI8J5wSDJWgBD6GtGz0hcDQcrIYG/GYEPw==
_ym_d	1755336837
_ym_d	1760954559
_ym_d	1742889194
_ym_isad	2
_ym_uid	1742889187528829383
_ym_uid	1755336837194969178
_ym_uid	1742128615416397392
_ym_visorc	b
alice_uuid	8A53C863-815A-4C63-9430-588B5324FAAF
amcuid	1494970031742211656
bh	ElEiQ2hyb21pdW0iO3Y9IjE0MCIsICJOb3Q9QT9CcmFuZCI7dj0iMjQiLCAiWWFCcm93c2VyIjt2PSIyNS4xMCIsICJZb3dzZXIiO3Y9IjIuNSIaBSJhcm0iIg4iMjUuMTAuMi4xMTg2IioCPzAyAiIiOgcibWFjT1MiQggiMTUuMy4xIkoEIjY0IlJqIkNocm9taXVtIjt2PSIxNDAuMC43MzM5LjExODYiLCAiTm90PUE/QnJhbmQiO3Y9IjI0LjAuMC4wIiwgIllhQnJvd3NlciI7dj0iMjUuMTAuMi4xMTg2IiwgIllvd3NlciI7dj0iMi41IloCPzBg3LmvygZqI9zK0bYBu/GfqwT61obMCNLR7esD/Lmv/wff/fvzDd21zYcI
coockoos	1
Cookie_check	1
cycada	CTCHqG0naEGDwiLWwMsTd5cHrds12wRzCyRXRJl1d2Y=
font_loaded	YSv1
gdpr	0
geoadv-utm	utm_source%3Dyandex%26utm_medium%3Dcpc%26utm_campaign%3Dfmt_text%257Ccmp_brand%257Cprod_subscription%257Clp_short-xx2%26utm_term%3D%25D1%258F%25D0%25B1%25D0%25B8%25D0%25B7%25D0%25BD%25D0%25B5%25D1%2581%26utm_content%3Dcid_90405261%257Cgbid_5237707202%257Caid_14571280537%257Cadp_no%257Cpos_premium1%257Csrc_search_none%257Cdvc_desktop%257Crtg_45939877966%26yclid%3D15130383330384019455
i	60KfAFNvX+p83ozEMofml/jOuYFjc2Scld3FyVhI+DHxzWxwy04G8N/OZLlLXhLaVGsgRTuSS+Yqh+bzOjWBJzZ90OU=
is_gdpr	0
is_gdpr	0
is_gdpr_b	CK6UEBCCwgI=
is_gdpr_b	COOeNhDMygIoAg==
isa	OjQXWPfVfybYvbUqgF/fhqwqDC+FaHte+keDdOTLLx8Ex+QfLD5iXmgbAGC/GerCxUCnhojSEe/YVlVFWURMBZ8ljkg=
k50lastvisit	db546baba3acb079f91946f80b9078ffa565e36d.7c02308d46bf1c9d74a6e8152425b5fe7a46b92a.db546baba3acb079f91946f80b9078ffa565e36d.509d0bf2530c9815d5755090879a1dc919d61350.1766507643062
k50uuid	261bec41-f700-4cb3-88b8-a00ca484a1cb
L	enVGfX1jaWJ6dnFRX29+RFJ/B3YBVllCFjYvEDUGCBsUJQ==.1765271286.1475851.370753.99c2817dec6476dd37b42310e48b1221
maps_routes_travel_mode	auto"""

# Парсим и форматируем
cookies_list = []
seen_names = set()  # Для отслеживания дубликатов (берем последнее значение)

# Обрабатываем строки в обратном порядке, чтобы при дубликатах брать последнее значение
lines = cookies_raw.strip().split('\n')
for line in reversed(lines):
    parts = line.split('\t')
    if len(parts) >= 2:
        name = parts[0].strip()
        value = parts[1].strip()
        if name and value and name not in seen_names:
            cookies_list.insert(0, f"{name}={value}")  # Вставляем в начало
            seen_names.add(name)

# Формируем итоговую строку
cookies_string = "; ".join(cookies_list)

print("=" * 80)
print("🍪 СТРОКА COOKIES ДЛЯ ВСТАВКИ В АДМИНСКУЮ ПАНЕЛЬ:")
print("=" * 80)
print()
print(cookies_string)
print()
print("=" * 80)
print(f"📊 Всего уникальных cookies: {len(cookies_list)}")
print("=" * 80)

