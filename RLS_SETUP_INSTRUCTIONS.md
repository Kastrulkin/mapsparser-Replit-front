# Инструкция по настройке RLS политик в Supabase

## Проблема
Отчёты не отображаются в личном кабинете пользователя из-за неправильно настроенных RLS (Row Level Security) политик.

## Решение

### 1. Откройте Supabase Dashboard
Перейдите в [Supabase Dashboard](https://supabase.com/dashboard/project/bvhpvzcvcuswiozhyqlk)

### 2. Перейдите в SQL Editor
1. В левом меню выберите "SQL Editor"
2. Создайте новый запрос

### 3. Выполните следующие SQL команды

```sql
-- Включаем RLS для всех таблиц
ALTER TABLE Users ENABLE ROW LEVEL SECURITY;
ALTER TABLE Cards ENABLE ROW LEVEL SECURITY; 
ALTER TABLE ParseQueue ENABLE ROW LEVEL SECURITY;

-- Удаляем старые политики (если есть)
DROP POLICY IF EXISTS "Users can view own profile" ON Users;
DROP POLICY IF EXISTS "Users can update own profile" ON Users;
DROP POLICY IF EXISTS "Users can view own cards" ON Cards;
DROP POLICY IF EXISTS "Users can view own queue" ON ParseQueue;
DROP POLICY IF EXISTS "Users can insert to queue" ON ParseQueue;

-- Создаем новые политики для Users
CREATE POLICY "Users can view own profile" ON Users
FOR SELECT USING (
    auth.uid()::text = auth_id OR 
    auth.jwt() ->> 'email' = email
);

CREATE POLICY "Users can update own profile" ON Users
FOR UPDATE USING (
    auth.uid()::text = auth_id OR 
    auth.jwt() ->> 'email' = email
);

-- Создаем политики для Cards
CREATE POLICY "Users can view own cards" ON Cards
FOR SELECT USING (
    user_id IN (
        SELECT id FROM Users 
        WHERE auth_id = auth.uid()::text 
        OR email = auth.jwt() ->> 'email'
    )
);

-- Создаем политики для ParseQueue
CREATE POLICY "Users can view own queue" ON ParseQueue
FOR SELECT USING (
    user_id IN (
        SELECT id FROM Users 
        WHERE auth_id = auth.uid()::text 
        OR email = auth.jwt() ->> 'email'
    )
);

CREATE POLICY "Users can insert to queue" ON ParseQueue
FOR INSERT WITH CHECK (
    user_id IN (
        SELECT id FROM Users 
        WHERE auth_id = auth.uid()::text 
        OR email = auth.jwt() ->> 'email'
    )
);
```

### 4. Проверьте результат
После выполнения SQL команд:
1. Обновите страницу личного кабинета
2. Отчёты должны появиться

## Альтернативное решение (временное)
Если нужно быстро протестировать, можно временно отключить RLS:

```sql
-- ВНИМАНИЕ: Это временное решение для тестирования!
ALTER TABLE Users DISABLE ROW LEVEL SECURITY;
ALTER TABLE Cards DISABLE ROW LEVEL SECURITY;
ALTER TABLE ParseQueue DISABLE ROW LEVEL SECURITY;
```

**После тестирования обязательно включите RLS обратно и настройте политики правильно!**
