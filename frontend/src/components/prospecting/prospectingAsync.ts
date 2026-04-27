export function getRequestErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

type BusyMap = Record<string, string>;

type BusyMapSetter = (updater: (prev: BusyMap) => BusyMap) => void;

type LoadingSetter = (value: boolean) => void;

type ErrorSetter = (value: string | null) => void;

export async function withBusyState(
  setBusy: BusyMapSetter,
  key: string,
  state: string,
  action: () => Promise<void>,
) {
  setBusy((prev) => ({ ...prev, [key]: state }));
  try {
    await action();
  } finally {
    setBusy((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }
}

export async function runLoadingAction(
  setLoading: LoadingSetter,
  setError: ErrorSetter,
  fallback: string,
  action: () => Promise<void>,
) {
  try {
    setLoading(true);
    setError(null);
    await action();
  } catch (error: unknown) {
    setError(getRequestErrorMessage(error, fallback));
  } finally {
    setLoading(false);
  }
}
