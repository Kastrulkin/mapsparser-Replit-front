const key = 'localos_max_connect_pending';

export const rememberMaxConnection = () => {
  try { window.localStorage.setItem(key, String(Date.now())); } catch { /* URL return still works in the current login. */ }
};

export const consumeMaxConnection = () => {
  try {
    const saved = window.localStorage.getItem(key);
    if (!saved) return false;
    window.localStorage.removeItem(key);
    const issued = Number(saved);
    return Number.isFinite(issued) && Date.now() >= issued && Date.now() - issued < 30 * 60 * 1000;
  } catch { return false; }
};
