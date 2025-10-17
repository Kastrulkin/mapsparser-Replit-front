# 🏗️ Архитектура базы данных BeautyBot

## 🎯 **Принципы проектирования:**

### 1. **Иерархия сущностей:**
```
Users (Пользователи)
  └── Businesses (Бизнесы) - один пользователь может владеть несколькими
      ├── Services (Услуги)
      ├── FinancialTransactions (Финансовые транзакции)
      ├── FinancialMetrics (Финансовые метрики)
      ├── Cards (Отчеты/Карточки)
      └── ScreenshotAnalyses (Анализ скриншотов)
```

### 2. **Ключевые принципы:**
- **Все данные привязаны к business_id** (не к user_id)
- **user_id используется только для авторизации**
- **business_id - основной ключ для изоляции данных**
- **Суперадмин видит все бизнесы, обычные пользователи - только свои**

## 📋 **Структура таблиц:**

### 👥 **Users (Пользователи)**
```sql
CREATE TABLE Users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    phone TEXT,
    password_hash TEXT,
    is_superadmin BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 🏢 **Businesses (Бизнесы)**
```sql
CREATE TABLE Businesses (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    industry TEXT,
    business_type TEXT,
    address TEXT,
    working_hours TEXT,
    phone TEXT,
    email TEXT,
    website TEXT,
    owner_id TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES Users (id) ON DELETE CASCADE
);
```

### 🛠️ **Services (Услуги)**
```sql
CREATE TABLE Services (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    keywords TEXT, -- JSON массив
    price TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
);
```

### 💰 **FinancialTransactions (Финансовые транзакции)**
```sql
CREATE TABLE FinancialTransactions (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    description TEXT,
    transaction_type TEXT CHECK (transaction_type IN ('income', 'expense')),
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
);
```

### 📊 **FinancialMetrics (Финансовые метрики)**
```sql
CREATE TABLE FinancialMetrics (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value DECIMAL(10,2) NOT NULL,
    period TEXT, -- 'daily', 'weekly', 'monthly', 'yearly'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
);
```

### 📄 **Cards (Отчеты/Карточки)**
```sql
CREATE TABLE Cards (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL,
    url TEXT,
    title TEXT,
    address TEXT,
    phone TEXT,
    site TEXT,
    rating REAL,
    reviews_count INTEGER,
    categories TEXT,
    overview TEXT,
    products TEXT,
    news TEXT,
    photos TEXT,
    features_full TEXT,
    competitors TEXT,
    hours TEXT,
    hours_full TEXT,
    report_path TEXT,
    seo_score INTEGER,
    ai_analysis TEXT,
    recommendations TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
);
```

### 📸 **ScreenshotAnalyses (Анализ скриншотов)**
```sql
CREATE TABLE ScreenshotAnalyses (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL,
    screenshot_path TEXT,
    analysis_result TEXT, -- JSON результат анализа
    analysis_type TEXT, -- 'service_optimization', 'card_analysis'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
);
```

## 🔐 **Права доступа:**

### **Обычные пользователи:**
- Видят только свои бизнесы (`WHERE owner_id = user_id`)
- Все данные фильтруются по `business_id`

### **Суперадмины:**
- Видят все бизнесы
- Могут переключаться между любыми бизнесами
- Все данные доступны без ограничений

## 🚀 **Преимущества такой архитектуры:**

1. **Изоляция данных** - каждый бизнес изолирован
2. **Масштабируемость** - легко добавлять новые бизнесы
3. **Безопасность** - четкое разделение прав доступа
4. **Производительность** - индексы по business_id
5. **Гибкость** - суперадмин может управлять всеми бизнесами

## 📈 **Индексы для производительности:**
```sql
CREATE INDEX idx_businesses_owner_id ON Businesses(owner_id);
CREATE INDEX idx_services_business_id ON Services(business_id);
CREATE INDEX idx_transactions_business_id ON FinancialTransactions(business_id);
CREATE INDEX idx_metrics_business_id ON FinancialMetrics(business_id);
CREATE INDEX idx_cards_business_id ON Cards(business_id);
CREATE INDEX idx_screenshots_business_id ON ScreenshotAnalyses(business_id);
```
