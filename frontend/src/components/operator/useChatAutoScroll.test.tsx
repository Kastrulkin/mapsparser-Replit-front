import { fireEvent, render, act, cleanup } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { useChatAutoScroll } from './useChatAutoScroll';
function Chat({ business = 'riderra', text = 'History' }) {
  const ref = useChatAutoScroll(business);
  return <div ref={ref} data-testid="chat"><p>{text}</p></div>;
}
afterEach(cleanup);
it('follows history and new replies without interrupting manual reading', async () => {
  const view = render(<Chat />);
  const node = view.getByTestId('chat');
  Object.defineProperties(node, { scrollHeight: { configurable: true, value: 1000 }, clientHeight: { value: 200 } });
  view.rerender(<Chat text="Loaded history" />);
  expect(node.scrollTop).toBe(1000);
  node.scrollTop = 800; fireEvent.scroll(node);
  Object.defineProperty(node, 'scrollHeight', { value: 1200 });
  view.rerender(<Chat text="New reply" />);
  expect(node.scrollTop).toBe(1200);
  node.scrollTop = 100; fireEvent.scroll(node);
  view.rerender(<Chat text="More reply text" />);
  await act(async () => {});
  expect(node.scrollTop).toBe(100);
  node.scrollTop = 1000; fireEvent.scroll(node);
  Object.defineProperty(node, 'scrollHeight', { value: 1500 });
  await act(async () => { node.firstChild!.textContent = 'Streaming reply'; });
  expect(node.scrollTop).toBe(1500);
});
it('resets following when switching businesses', () => {
  const view = render(<Chat />);
  const node = view.getByTestId('chat');
  Object.defineProperties(node, { scrollHeight: { value: 1000 }, clientHeight: { value: 200 } });
  node.scrollTop = 100; fireEvent.scroll(node);
  view.rerender(<Chat business="organica" />);
  expect(node.scrollTop).toBe(1000);
  view.unmount();
});
