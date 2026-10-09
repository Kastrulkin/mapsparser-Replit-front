import { useCallback, useLayoutEffect, useRef, useState } from 'react';

/** Keep following replies unless the reader deliberately leaves the bottom. */
export function useChatAutoScroll(conversationKey: string | null | undefined, messageCount = 0) {
  const element = useRef<HTMLDivElement | null>(null);
  const following = useRef(true);
  const cleanup = useRef<(() => void) | undefined>();
  const [readingHistory, setReadingHistory] = useState(false);
  const [hasNewMessages, setHasNewMessages] = useState(false);
  const previousCount = useRef(messageCount);
  const follow = useCallback(() => {
    const node = element.current;
    if (node && following.current) node.scrollTop = node.scrollHeight;
  }, []);
  const scrollToLatest = useCallback(() => {
    following.current = true;
    setReadingHistory(false);
    setHasNewMessages(false);
    follow();
  }, [follow]);
  const ref = useCallback((node: HTMLDivElement | null) => {
    cleanup.current?.();
    element.current = node;
    if (!node) return;
    const onScroll = () => {
      following.current = node.scrollHeight - node.clientHeight - node.scrollTop <= 48;
      setReadingHistory(!following.current);
      if (following.current) setHasNewMessages(false);
    };
    node.addEventListener('scroll', onScroll, { passive: true });
    node.addEventListener('load', follow, true);
    const mutations = new MutationObserver(follow);
    mutations.observe(node, { childList: true, subtree: true, characterData: true });
    const resize = typeof ResizeObserver === "undefined" ? undefined : new ResizeObserver(follow);
    resize?.observe(node);
    cleanup.current = () => {
      node.removeEventListener('scroll', onScroll);
      node.removeEventListener('load', follow, true);
      mutations.disconnect();
      resize?.disconnect();
    };
    follow();
  }, [follow]);
  useLayoutEffect(() => {
    scrollToLatest();
    previousCount.current = messageCount;
  }, [conversationKey, scrollToLatest]);
  useLayoutEffect(() => {
    if (messageCount > previousCount.current && !following.current) setHasNewMessages(true);
    previousCount.current = messageCount;
    follow();
  }, [messageCount, follow]);
  useLayoutEffect(() => () => cleanup.current?.(), []);
  return { ref, readingHistory, hasNewMessages, scrollToLatest };
}

