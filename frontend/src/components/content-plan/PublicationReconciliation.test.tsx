import { act, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { PublicationReconciliation } from './PublicationReconciliation';

describe('Publication reconciliation', () => {
  it('requires a receipt and explicit confirmation without offering another send', () => {
    const onConfirm = vi.fn(async () => undefined);
    render(<PublicationReconciliation busy={false} onConfirm={onConfirm} />);
    const button = screen.getByRole('button', { name: 'Подтвердить существующую публикацию' });
    const checkbox = screen.getByRole('checkbox');
    expect(button).toBeDisabled();
    expect(screen.getByText(/Не отправляйте пост повторно/)).toBeVisible();
    expect(screen.queryByRole('button', { name: /Разместить вручную|Повторить|Скопировать текст/ })).not.toBeInTheDocument();
    fireEvent.click(checkbox);
    expect(button).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Ссылка или ID уже опубликованного поста'), { target: { value: '  12345  ' } });
    expect(checkbox).not.toBeChecked();
    expect(button).toBeDisabled();
    fireEvent.click(checkbox);
    fireEvent.click(button);
    expect(onConfirm).toHaveBeenCalledExactlyOnceWith('12345');
  });

  it('disables every input and confirmation while the result is being saved', () => {
    const onConfirm = vi.fn(async () => undefined);
    render(<PublicationReconciliation busy onConfirm={onConfirm} />);
    expect(screen.getByRole('textbox')).toBeDisabled();
    expect(screen.getByRole('checkbox')).toBeDisabled();
    fireEvent.click(screen.getByRole('button'));
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('blocks a second submission until the pending confirmation settles', async () => {
    let finishConfirmation: () => void = () => undefined;
    const pending = new Promise<void>((resolve) => {
      finishConfirmation = resolve;
    });
    const onConfirm = vi.fn(() => pending);
    render(<PublicationReconciliation busy={false} onConfirm={onConfirm} />);
    const receipt = screen.getByRole('textbox');
    const checkbox = screen.getByRole('checkbox');
    const button = screen.getByRole('button');
    fireEvent.change(receipt, { target: { value: '12345' } });
    fireEvent.click(checkbox);
    fireEvent.click(button);
    fireEvent.click(button);
    expect(onConfirm).toHaveBeenCalledExactlyOnceWith('12345');
    expect(receipt).toBeDisabled();
    expect(checkbox).toBeDisabled();
    expect(button).toBeDisabled();

    await act(async () => {
      finishConfirmation();
      await pending;
    });
    expect(receipt).toBeEnabled();
    expect(checkbox).toBeEnabled();
    expect(button).toBeEnabled();
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
