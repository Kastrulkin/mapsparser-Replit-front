
INSERT OR REPLACE INTO Users (id, email, password_hash, name, phone, telegram_id, created_at, updated_at, is_active, is_verified, verification_token, reset_token, reset_token_expires, is_superadmin)
VALUES ('6e5a9f16-2ef0-45f9-8f9d-58532a2b4958', 'demyanovap@yandex.ru', '8b05c07331ad756f4505ba0cd3722d7f:3d332e04400e566564cfdf6c1d69bef8fea6265651a044f5d7348d0098dc0105', 'Александр', '9214224843', 'None', '2025-10-16T13:17:34.944985', '2025-10-17 21:06:49', 1, 0, 'v5oP8cD_O-8Jswse79HgWxqMtrUuAHrXrthafycPpbE', 'None', 'None', 1);

INSERT OR REPLACE INTO Users (id, email, password_hash, name, phone, telegram_id, created_at, updated_at, is_active, is_verified, verification_token, reset_token, reset_token_expires, is_superadmin)
VALUES ('0f3f0ef6-f483-44a4-934e-007945bd1aff', 'test@example.com', '44892873fd63337d488c9dd263b96c25:779b64e9ff2b162ba365ba8fe621f0d3d1461e92c914850a0b41135eef040795', 'Test User', '', 'None', '2025-10-17T19:19:28.228698', '2025-10-17 16:19:28', 1, 0, 'oValot3m9u2Z0oOnUVR2COqNVTM0JBJKRc18x_ZDk7U', 'None', 'None', 0);

INSERT OR REPLACE INTO Businesses (id, name, description, industry, owner_id, is_active, created_at, updated_at)
VALUES ('eae57c62-7f56-46b2-aba1-8e82b3b2dcf3', 'Салон красоты 'Элегант'', 'Премиальный салон красоты в центре города', 'Красота и здоровье', '6e5a9f16-2ef0-45f9-8f9d-58532a2b4958', 1, '2025-10-17 20:30:55', '2025-10-17 20:30:55');

INSERT OR REPLACE INTO Businesses (id, name, description, industry, owner_id, is_active, created_at, updated_at)
VALUES ('3bf3666b-1ad9-48d2-ab6c-8ee67f9b3296', 'Барбершоп 'Мужской стиль'', 'Современный барбершоп для мужчин', 'Красота и здоровье', '6e5a9f16-2ef0-45f9-8f9d-58532a2b4958', 1, '2025-10-17 20:30:55', '2025-10-17 20:30:55');

INSERT OR REPLACE INTO Businesses (id, name, description, industry, owner_id, is_active, created_at, updated_at)
VALUES ('04c85466-e5b5-4edd-aa1b-1e8ae2036d1c', 'Ногтевая студия 'Маникюр Плюс'', 'Студия маникюра и педикюра', 'Красота и здоровье', '6e5a9f16-2ef0-45f9-8f9d-58532a2b4958', 1, '2025-10-17 20:30:55', '2025-10-17 20:30:55');

INSERT OR REPLACE INTO Businesses (id, name, description, industry, owner_id, is_active, created_at, updated_at)
VALUES ('47ac1b4e-ab57-43ec-923c-87986ce4fa1b', 'Салон красоты 'Элегант'', 'Премиальный салон красоты в центре города', 'Красота и здоровье', '6e5a9f16-2ef0-45f9-8f9d-58532a2b4958', 1, '2025-10-17 20:54:54', '2025-10-17 20:54:54');

INSERT OR REPLACE INTO Businesses (id, name, description, industry, owner_id, is_active, created_at, updated_at)
VALUES ('d4a4fc48-65f4-4e5c-93ca-e25bd7311c6f', 'Барбершоп 'Мужской стиль'', 'Современный барбершоп для мужчин', 'Красота и здоровье', '6e5a9f16-2ef0-45f9-8f9d-58532a2b4958', 1, '2025-10-17 20:54:54', '2025-10-17 20:54:54');

INSERT OR REPLACE INTO Businesses (id, name, description, industry, owner_id, is_active, created_at, updated_at)
VALUES ('a8651164-61c1-44a7-8709-9b12e9425c09', 'Ногтевая студия 'Маникюр Плюс'', 'Студия маникюра и педикюра', 'Красота и здоровье', '6e5a9f16-2ef0-45f9-8f9d-58532a2b4958', 1, '2025-10-17 20:54:54', '2025-10-17 20:54:54');

INSERT OR REPLACE INTO Businesses (id, name, description, industry, owner_id, is_active, created_at, updated_at)
VALUES ('1713e237-6253-4c7a-8a6a-01c7fad12b03', 'Салон красоты 'Элегант'', 'Премиальный салон красоты в центре города', 'Красота и здоровье', '6e5a9f16-2ef0-45f9-8f9d-58532a2b4958', 1, '2025-10-17 20:57:53', '2025-10-17 20:57:53');

INSERT OR REPLACE INTO Businesses (id, name, description, industry, owner_id, is_active, created_at, updated_at)
VALUES ('d8856aee-6c45-4d4f-ab1a-341f75a52ad6', 'Барбершоп 'Мужской стиль'', 'Современный барбершоп для мужчин', 'Красота и здоровье', '6e5a9f16-2ef0-45f9-8f9d-58532a2b4958', 1, '2025-10-17 20:57:53', '2025-10-17 20:57:53');

INSERT OR REPLACE INTO Businesses (id, name, description, industry, owner_id, is_active, created_at, updated_at)
VALUES ('7542afec-93be-4976-a55c-f64edd298a11', 'Ногтевая студия 'Маникюр Плюс'', 'Студия маникюра и педикюра', 'Красота и здоровье', '6e5a9f16-2ef0-45f9-8f9d-58532a2b4958', 1, '2025-10-17 20:57:53', '2025-10-17 20:57:53');

INSERT OR REPLACE INTO Businesses (id, name, description, industry, owner_id, is_active, created_at, updated_at)
VALUES ('54306f6c-ffde-458d-a19b-4ec65d8b7529', 'Салон красоты 'Элегант'', 'Премиальный салон красоты в центре города', 'Красота и здоровье', '6e5a9f16-2ef0-45f9-8f9d-58532a2b4958', 1, '2025-10-17 21:03:14', '2025-10-17 21:03:14');

INSERT OR REPLACE INTO Businesses (id, name, description, industry, owner_id, is_active, created_at, updated_at)
VALUES ('e0423cda-45bc-4730-8992-be7168fb44ce', 'Барбершоп 'Мужской стиль'', 'Современный барбершоп для мужчин', 'Красота и здоровье', '6e5a9f16-2ef0-45f9-8f9d-58532a2b4958', 1, '2025-10-17 21:03:14', '2025-10-17 21:03:14');

INSERT OR REPLACE INTO Businesses (id, name, description, industry, owner_id, is_active, created_at, updated_at)
VALUES ('69fd038e-0d27-487b-ab0c-38431824f1cb', 'Ногтевая студия 'Маникюр Плюс'', 'Студия маникюра и педикюра', 'Красота и здоровье', '6e5a9f16-2ef0-45f9-8f9d-58532a2b4958', 1, '2025-10-17 21:03:14', '2025-10-17 21:03:14');

INSERT OR REPLACE INTO Businesses (id, name, description, industry, owner_id, is_active, created_at, updated_at)
VALUES ('c6471e8b-47e9-4ac1-97bd-822189831585', 'Салон красоты 'Элегант'', 'Премиальный салон красоты в центре города', 'Красота и здоровье', '6e5a9f16-2ef0-45f9-8f9d-58532a2b4958', 1, '2025-10-17 21:04:04', '2025-10-17 21:04:04');

INSERT OR REPLACE INTO Businesses (id, name, description, industry, owner_id, is_active, created_at, updated_at)
VALUES ('6d0be647-f5b3-4575-bbca-d7c08b179c50', 'Барбершоп 'Мужской стиль'', 'Современный барбершоп для мужчин', 'Красота и здоровье', '6e5a9f16-2ef0-45f9-8f9d-58532a2b4958', 1, '2025-10-17 21:04:04', '2025-10-17 21:04:04');

INSERT OR REPLACE INTO Businesses (id, name, description, industry, owner_id, is_active, created_at, updated_at)
VALUES ('2a0aeb1f-5045-4236-ba01-5f5f435a9adc', 'Ногтевая студия 'Маникюр Плюс'', 'Студия маникюра и педикюра', 'Красота и здоровье', '6e5a9f16-2ef0-45f9-8f9d-58532a2b4958', 1, '2025-10-17 21:04:04', '2025-10-17 21:04:04');