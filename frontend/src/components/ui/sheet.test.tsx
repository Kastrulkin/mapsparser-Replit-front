import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from './sheet';

describe('Sheet close label', () => {
  it.each([
    { label: undefined, expected: 'Close' },
    { label: 'Закрыть', expected: 'Закрыть' },
  ])('preserves the default and supports the scoped label $expected', async ({ label, expected }) => {
    render(
      <Sheet>
        <SheetTrigger>Open panel</SheetTrigger>
        <SheetContent closeLabel={label}>
          <SheetTitle>Publication</SheetTitle>
          <SheetDescription>Review a draft.</SheetDescription>
        </SheetContent>
      </Sheet>,
    );
    const trigger = screen.getByRole('button', { name: 'Open panel' });
    fireEvent.click(trigger);
    const dialog = await screen.findByRole('dialog');
    expect(dialog).not.toHaveAttribute('closeLabel');
    fireEvent.click(screen.getByRole('button', { name: expected }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    await waitFor(() => expect(trigger).toHaveFocus());
  });
});
