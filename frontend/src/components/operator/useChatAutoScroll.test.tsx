import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useChatAutoScroll } from './useChatAutoScroll';
function Chat({ business, count }: { business: string; count: number }) {
  const scroll = useChatAutoScroll(business, count);
  return <><div data-testid="history" ref={scroll.ref} /><span>{scroll.readingHistory ? 'reading' : 'following'}</span><span>{scroll.hasNewMessages ? 'new' : 'none'}</span><button onClick={scroll.scrollToLatest}>latest</button></>;
}
describe('chat following', () => {
  it('preserves reading position, signals new messages and resets for a different business', () => {
    const view = render(<Chat business="one" count={1} />);
    const history = screen.getByTestId('history');
    Object.defineProperty(history, 'scrollHeight', { configurable: true, value: 1000 });
    Object.defineProperty(history, 'clientHeight', { configurable: true, value: 300 });
    history.scrollTop = 200;
    fireEvent.scroll(history);
    view.rerender(<Chat business="one" count={2} />);
    expect(history.scrollTop).toBe(200);
    expect(screen.getByText('new')).toBeInTheDocument();
    fireEvent.click(screen.getByText('latest'));
    expect(history.scrollTop).toBe(1000);
    expect(screen.getByText('following')).toBeInTheDocument();
    history.scrollTop = 100;
    fireEvent.scroll(history);
    act(() => view.rerender(<Chat business="two" count={2} />));
    expect(screen.getByText('following')).toBeInTheDocument();
    expect(screen.getByText('none')).toBeInTheDocument();
  });
});
