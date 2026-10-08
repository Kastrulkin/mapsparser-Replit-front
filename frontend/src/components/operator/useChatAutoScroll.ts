import { useCallback, useLayoutEffect, useRef } from 'react';

/** Follow live replies until the reader leaves the bottom to read history. */
export function useChatAutoScroll(conversationKey: string | null | undefined) {
  const element = useRef<HTMLDivElement | null>(null);
  const following = useRef(true);
  const cleanup = useRef<(() => void) | undefined>(undefined);
  const previousKey = useRef(conversationKey);
  if (previousKey.current !== conversationKey) {
    previousKey.current = conversationKey;
    following.current = true;
  }
  const follow = useCallback(() => {
    const node = element.current;
    if (node && following.current) node.scrollTop = node.scrollHeight;
  }, []);
  const ref = useCallback((node: HTMLDivElement | null) => {
    cleanup.current?.();
    element.current = node;
    if (!node) return;
    const onScroll = () => {
      following.current = node.scrollHeight - node.clientHeight - node.scrollTop <= 48;
    };
    node.addEventListener('scroll', onScroll, { passive: true });
    node.addEventListener('load', follow, true);
    const mutations = new MutationObserver(follow);
    mutations.observe(node, { childList: true, subtree: true, characterData: true, attributes: true });
    const resize = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(follow);
    resize?.observe(node);
    cleanup.current = () => {
      node.removeEventListener('scroll', onScroll);
      node.removeEventListener('load', follow, true);
      mutations.disconnect();
      resize?.disconnect();
    };
    follow();
  }, [follow]);
  useLayoutEffect(follow);
  return ref;
}
