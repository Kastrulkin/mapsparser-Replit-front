# Виджет авторизации Google Business Profile

**Дата:** 2025-01-06  
**Приоритет:** Высокий  
**Исполнитель:** Frontend кодер

---

## Цель

Добавить виджет/кнопку для авторизации Google Business Profile через OAuth 2.0. Пользователь нажимает кнопку, авторизуется в Google, и мы получаем доступ к его Google Business Profile.

---

## Архитектура

**Подход:**
- Пользователь нажимает кнопку "Подключить Google" в `ExternalIntegrations.tsx`
- Фронтенд вызывает `/api/google/oauth/authorize?business_id=...`
- Получает `auth_url` и открывает его в новом окне/popup
- Пользователь авторизуется в Google
- Google редиректит на `/api/google/oauth/callback`
- Backend обрабатывает callback и редиректит на фронтенд с параметром `google_auth=success/error`
- Фронтенд закрывает popup и обновляет список аккаунтов

---

## Реализация

### 1. Обновление ExternalIntegrations.tsx

**Файл:** `frontend/src/components/ExternalIntegrations.tsx`

**Добавить функцию для авторизации Google:**

```tsx
const handleGoogleAuth = async () => {
  if (!currentBusinessId) {
    setError("Сначала выберите бизнес");
    return;
  }
  
  try {
    const token = localStorage.getItem('auth_token');
    
    // Получаем URL для авторизации
    const res = await fetch(
      `${window.location.origin}/api/google/oauth/authorize?business_id=${currentBusinessId}`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );
    
    const data = await res.json();
    
    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Ошибка получения URL авторизации');
    }
    
    // Открываем popup для авторизации
    const width = 600;
    const height = 700;
    const left = (window.screen.width - width) / 2;
    const top = (window.screen.height - height) / 2;
    
    const popup = window.open(
      data.auth_url,
      'Google Auth',
      `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no,scrollbars=yes,resizable=yes`
    );
    
    if (!popup) {
      setError('Не удалось открыть окно авторизации. Разрешите всплывающие окна.');
      return;
    }
    
    // Слушаем сообщения от popup (если используем postMessage)
    // Или проверяем URL через polling
    const checkPopup = setInterval(() => {
      try {
        // Проверяем, закрыт ли popup
        if (popup.closed) {
          clearInterval(checkPopup);
          
          // Проверяем статус подключения через URL параметры
          const urlParams = new URLSearchParams(window.location.search);
          const authStatus = urlParams.get('google_auth');
          
          if (authStatus === 'success') {
            setSuccess('Google Business Profile успешно подключен');
            loadAccounts();
            // Убираем параметр из URL
            window.history.replaceState({}, document.title, window.location.pathname);
          } else if (authStatus === 'error') {
            setError('Ошибка подключения Google Business Profile');
            window.history.replaceState({}, document.title, window.location.pathname);
          }
        }
      } catch (e) {
        // Игнорируем ошибки cross-origin
      }
    }, 500);
    
    // Альтернативный подход: слушать postMessage от popup
    const messageHandler = (event: MessageEvent) => {
      // Проверяем origin для безопасности
      if (event.origin !== window.location.origin) {
        return;
      }
      
      if (event.data.type === 'GOOGLE_AUTH_SUCCESS') {
        clearInterval(checkPopup);
        window.removeEventListener('message', messageHandler);
        popup.close();
        
        setSuccess('Google Business Profile успешно подключен');
        loadAccounts();
      } else if (event.data.type === 'GOOGLE_AUTH_ERROR') {
        clearInterval(checkPopup);
        window.removeEventListener('message', messageHandler);
        popup.close();
        
        setError(event.data.error || 'Ошибка подключения Google Business Profile');
      }
    };
    
    window.addEventListener('message', messageHandler);
    
    // Очищаем обработчик через 5 минут (таймаут)
    setTimeout(() => {
      clearInterval(checkPopup);
      window.removeEventListener('message', messageHandler);
      if (!popup.closed) {
        popup.close();
        setError('Время ожидания авторизации истекло');
      }
    }, 5 * 60 * 1000);
    
  } catch (e: any) {
    setError(e.message || 'Ошибка подключения Google');
  }
};
```

**Добавить кнопку в UI:**

```tsx
{/* В секции добавления новой интеграции */}
<div className="mb-4">
  <label className="block text-sm font-medium text-gray-700 mb-2">
    Подключить Google Business Profile
  </label>
  <Button
    onClick={handleGoogleAuth}
    disabled={!currentBusinessId}
    className="w-full"
  >
    <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
      {/* Иконка Google */}
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
    </svg>
    Подключить Google
  </Button>
  <p className="text-xs text-gray-500 mt-2">
    Авторизуйтесь через Google, чтобы мы могли получать и публиковать данные в Google Business Profile
  </p>
</div>
```

**Показывать статус подключенного Google:**

```tsx
{/* В списке аккаунтов */}
{accounts
  .filter(acc => acc.source === 'google_business')
  .map(account => (
    <div key={account.id} className="flex items-center justify-between p-3 bg-white border rounded">
      <div className="flex items-center gap-3">
        <svg className="w-6 h-6" viewBox="0 0 24 24">
          {/* Иконка Google */}
        </svg>
        <div>
          <div className="font-medium">Google Business Profile</div>
          <div className="text-sm text-gray-500">
            {account.display_name || account.external_id || 'Подключен'}
          </div>
          {account.last_sync_at && (
            <div className="text-xs text-gray-400">
              Последняя синхронизация: {new Date(account.last_sync_at).toLocaleString('ru-RU')}
            </div>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {account.is_active ? (
          <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs">Активен</span>
        ) : (
          <span className="px-2 py-1 bg-gray-100 text-gray-800 rounded text-xs">Неактивен</span>
        )}
        <Button
          size="sm"
          variant="outline"
          onClick={() => handleDisconnect(account.id)}
          className="text-red-600 hover:text-red-700"
        >
          Отключить
        </Button>
      </div>
    </div>
  ))}
```

---

## Альтернативный подход: использование iframe

Если popup блокируется браузером, можно использовать iframe:

```tsx
const [showGoogleAuth, setShowGoogleAuth] = useState(false);
const [authUrl, setAuthUrl] = useState<string | null>(null);

const handleGoogleAuth = async () => {
  // ... получение auth_url ...
  setAuthUrl(data.auth_url);
  setShowGoogleAuth(true);
};

{/* Модальное окно с iframe */}
{showGoogleAuth && authUrl && (
  <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div className="bg-white rounded-lg p-6 max-w-2xl w-full">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold">Авторизация Google</h2>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setShowGoogleAuth(false);
            setAuthUrl(null);
          }}
        >
          ✕
        </Button>
      </div>
      <iframe
        src={authUrl}
        className="w-full h-96 border rounded"
        title="Google Auth"
      />
    </div>
  </div>
)}
```

---

## Обработка callback на фронтенде

**Вариант 1: Через URL параметры (рекомендуется)**

Backend редиректит на фронтенд с параметром:
```
https://beautybot.pro/dashboard/profile?google_auth=success
```

Фронтенд проверяет параметр при загрузке:

```tsx
useEffect(() => {
  const urlParams = new URLSearchParams(window.location.search);
  const authStatus = urlParams.get('google_auth');
  
  if (authStatus === 'success') {
    setSuccess('Google Business Profile успешно подключен');
    loadAccounts();
    // Убираем параметр из URL
    window.history.replaceState({}, document.title, window.location.pathname);
  } else if (authStatus === 'error') {
    setError('Ошибка подключения Google Business Profile');
    window.history.replaceState({}, document.title, window.location.pathname);
  }
}, []);
```

**Вариант 2: Через postMessage**

Backend возвращает HTML страницу, которая отправляет postMessage:

```html
<!DOCTYPE html>
<html>
<head>
  <title>Авторизация завершена</title>
</head>
<body>
  <script>
    window.opener.postMessage({
      type: 'GOOGLE_AUTH_SUCCESS'
    }, window.location.origin);
    window.close();
  </script>
</body>
</html>
```

---

## Чеклист для кодера

- [ ] Добавить функцию `handleGoogleAuth()` в `ExternalIntegrations.tsx`
- [ ] Добавить кнопку "Подключить Google" с иконкой Google
- [ ] Реализовать открытие popup для авторизации
- [ ] Реализовать обработку callback (через URL параметры или postMessage)
- [ ] Показывать статус подключенного Google аккаунта
- [ ] Добавить индикатор последней синхронизации
- [ ] Протестировать OAuth flow
- [ ] Обработать ошибки (пользователь отменил, popup заблокирован и т.д.)

---

## Важные замечания

1. **Popup блокировка:**
   - Некоторые браузеры блокируют popup
   - Нужно обрабатывать случай, когда `window.open()` возвращает `null`
   - Показывать сообщение пользователю о необходимости разрешить popup

2. **Безопасность:**
   - Проверять `event.origin` при использовании postMessage
   - Валидировать state в callback для предотвращения CSRF

3. **UX:**
   - Показывать индикатор загрузки во время авторизации
   - Закрывать popup автоматически после успешной авторизации
   - Показывать понятные сообщения об ошибках

