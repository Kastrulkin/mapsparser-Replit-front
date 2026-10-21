/** Bounded requests for team work. Mutations are never retried automatically. */
export async function teamWorkJson(url: string, options: RequestInit = {}) {
  const controller = new AbortController();
  const source = options.signal;
  const abort = () => controller.abort();
  let timedOut = false;
  if (source?.aborted) controller.abort();
  source?.addEventListener('abort', abort, { once: true });
  const timer = window.setTimeout(() => { timedOut = true; controller.abort(); }, 20000);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    let body;
    try { body = await response.json(); }
    catch (reason) {
      if (controller.signal.aborted) throw reason;
      if ([401, 403].includes(response.status)) body = {};
      else throw new Error('Сервер вернул неполный ответ. Данные остались в форме; повторите попытку.');
    }
    if (response.status >= 500) throw new Error('Не удалось выполнить действие на сервере. Данные остались в форме; проверьте результат перед повтором.');
    return { response, body };
  } catch (reason) {
    if (!source?.aborted && timedOut) throw new Error('Сервер не ответил за 20 секунд. Данные остались в форме; проверьте результат перед повтором.');
    if (!source?.aborted && reason instanceof TypeError) throw new Error('Не удалось связаться с сервером. Проверьте соединение; данные остались в форме.');
    throw reason;
  } finally {
    window.clearTimeout(timer);
    source?.removeEventListener('abort', abort);
  }
}
