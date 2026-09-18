import { useId, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

type PublicationReconciliationProps = {
  busy: boolean;
  onConfirm: (receipt: string) => Promise<void>;
};

export function PublicationReconciliation({ busy, onConfirm }: PublicationReconciliationProps) {
  const receiptId = useId();
  const descriptionId = useId();
  const [receipt, setReceipt] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const submittingRef = useRef(false);
  const [submitting, setSubmitting] = useState(false);
  const disabled = busy || submitting;

  const confirmReceipt = async () => {
    if (disabled || submittingRef.current || !confirmed || !receipt.trim()) return;
    submittingRef.current = true;
    setSubmitting(true);
    try {
      await onConfirm(receipt.trim());
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  return (
    <div className="mt-3 space-y-3 rounded-xl bg-white p-3 ring-1 ring-slate-200">
      <p id={descriptionId} className="text-xs leading-5 text-slate-700">
        Результат отправки ещё не подтверждён. Обновите данные и проверьте площадку.
        Не отправляйте пост повторно: он уже мог быть опубликован.
        Если пост не найден, обратитесь к администратору для проверки попытки.
      </p>
      <label htmlFor={receiptId} className="block text-xs font-medium text-slate-700">
        Ссылка или ID уже опубликованного поста
      </label>
      <Input
        id={receiptId}
        aria-describedby={descriptionId}
        value={receipt}
        onChange={(event) => {
          setReceipt(event.target.value);
          setConfirmed(false);
        }}
        disabled={disabled}
        className="min-h-10 bg-white"
      />
      <label className="flex min-h-10 cursor-pointer items-start gap-2 rounded-xl bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-700">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(event) => setConfirmed(event.target.checked)}
          disabled={disabled}
          className="mt-0.5 h-4 w-4 shrink-0"
        />
        <span>Проверил на площадке: это тот же пост, его текст и медиа отображаются правильно.</span>
      </label>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled || !confirmed || !receipt.trim()}
        onClick={() => { void confirmReceipt(); }}
        className="min-h-10 rounded-xl px-3 text-xs"
      >
        Подтвердить существующую публикацию
      </Button>
    </div>
  );
}
