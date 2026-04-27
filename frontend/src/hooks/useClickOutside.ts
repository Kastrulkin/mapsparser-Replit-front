import { useEffect, RefObject } from 'react';

type UseClickOutsideOptions = {
  enabled?: boolean;
};

export const useClickOutside = (
  ref: RefObject<HTMLElement | null>,
  onOutsideClick: () => void,
  options: UseClickOutsideOptions = {},
) => {
  const enabled = options.enabled ?? true;

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      const element = ref.current;
      if (!element || !(event.target instanceof Node)) {
        return;
      }
      if (!element.contains(event.target)) {
        onOutsideClick();
      }
    };

    document.addEventListener('pointerdown', handlePointerDown, true);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown, true);
    };
  }, [enabled, onOutsideClick, ref]);
};
