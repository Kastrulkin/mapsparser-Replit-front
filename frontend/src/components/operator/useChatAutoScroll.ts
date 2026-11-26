import { useCallback, useLayoutEffect, useRef, useState } from 'react';

/** Keep following replies unless the reader deliberately leaves the bottom. */
export function useChatAutoScroll(conversationKey: string | null | undefined, messageCount = 0, progressKey?: string) {
  const element = useRef<HTMLDivElement | null>(null);
  const following = useRef(true);
  const cleanup = useRef<(() => void) | undefined>();
  const [readingHistory, setReadingHistory] = useState(false);
  const [hasNewMessages, setHasNewMessages] = useState(false);
  const previousCount = useRef(messageCount);
  const previousProgress = useRef(progressKey);
  const previousConversation = useRef(conversationKey);
  const observesContent = progressKey === undefined;
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
    // Setup results contain disclosures. Opening one should keep the reader on that row.
    const onToggle = (event: Event) => {
      if (event.target instanceof HTMLDetailsElement && event.target.open) onScroll();
    };
    const mutations = observesContent ? new MutationObserver(follow) : undefined;
    mutations?.observe(node, { childList: true, subtree: true, characterData: true });
    if (!mutations) node.addEventListener('toggle', onToggle, true);
    const resize = typeof ResizeObserver === "undefined" ? undefined : new ResizeObserver(follow);
    resize?.observe(node);
    cleanup.current = () => {
      node.removeEventListener('scroll', onScroll);
      node.removeEventListener('load', follow, true);
      mutations?.disconnect();
      node.removeEventListener('toggle', onToggle, true);
      resize?.disconnect();
    };
    follow();
  }, [follow, observesContent]);
  useLayoutEffect(() => {
    if (previousConversation.current !== conversationKey) {
      previousConversation.current = conversationKey;
      scrollToLatest();
    } else if ((messageCount > previousCount.current || progressKey !== previousProgress.current) && !following.current) {
      setHasNewMessages(true);
    }
    previousCount.current = messageCount;
    previousProgress.current = progressKey;
    follow();
  }, [conversationKey, messageCount, progressKey, follow, scrollToLatest]);
  useLayoutEffect(() => () => cleanup.current?.(), []);
  return { ref, readingHistory, hasNewMessages, scrollToLatest };
}
