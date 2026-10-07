import { useCallback, useEffect, useRef } from 'react';

export const useLatestCallback = <Arguments extends unknown[], Result>(
  callback: (...arguments_: Arguments) => Result,
) => {
  const callbackRef = useRef(callback);

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  return useCallback(
    (...arguments_: Arguments) => callbackRef.current(...arguments_),
    [],
  );
};
