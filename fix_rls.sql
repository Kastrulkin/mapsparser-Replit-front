-- Исправление RLS политик для таблиц Users, Cards и ParseQueue

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
