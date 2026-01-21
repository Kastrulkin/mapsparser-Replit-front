    def fetch_products(self, account_row: dict) -> List[Dict[str, Any]]:
        """
        Получить товары/услуги из кабинета Яндекс.Бизнес.
        
        Args:
            account_row: Строка из ExternalBusinessAccounts
        
        Returns:
            Список словарей с данными о товарах/услугах (категории и товары)
        """
        business_id = account_row["business_id"]
        external_id = account_row.get("external_id")
        
        if not external_id:
            return []
            
        print(f"🔍 Пробуем получить товары/услуги для {business_id}...")
        
        # Endpoints для товаров/услуг (Goods / Price Lists)
        # https://yandex.ru/sprav/api/{external_id}/goods
        possible_urls = [
            f"https://yandex.ru/sprav/api/{external_id}/goods",
            f"https://yandex.ru/sprav/api/company/{external_id}/goods",
            f"https://yandex.ru/sprav/api/{external_id}/price-lists",
            f"https://business.yandex.ru/api/organizations/{external_id}/goods",
        ]
        
        data = None
        for url in possible_urls:
            result = self._make_request(url)
            if result:
                data = result
                print(f"✅ Успешно получены данные товаров с {url}")
                break
                
        if not data:
            print(f"⚠️ Не удалось получить товары через API endpoints. Пробуем HTML...")
            # TODO: Можно добавить парсинг HTML страницы товаров
            # https://yandex.ru/sprav/{external_id}/p/edit/goods
            return []
            
        # Парсим ответ
        # Ожидаемая структура: {"categories": [...]} или список категорий
        categories = []
        
        if isinstance(data, list):
            categories = data
        elif isinstance(data, dict):
            categories = data.get("categories") or data.get("groups") or data.get("goods") or []
            
        parsed_products = []
        
        for category in categories:
            cat_name = category.get("name", "Разное")
            items = category.get("items") or category.get("goods") or []
            
            parsed_items = []
            for item in items:
                parsed_items.append({
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "price": item.get("price", {}).get("value") if isinstance(item.get("price"), dict) else item.get("price"),
                    "photo_url": item.get("photos", [{}])[0].get("url") if item.get("photos") else None
                })
                
            if parsed_items:
                parsed_products.append({
                    "category": cat_name,
                    "items": parsed_items
                })
                
        print(f"✅ Получено {len(parsed_products)} категорий товаров")
        return parsed_products
