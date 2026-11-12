import type { OperatorMessage } from '@/features/telegram/types';

export function OperatorMessageText({ message }: { message: OperatorMessage }) {
  const pending = message.role === 'operator' && ['sending', 'running'].includes(message.status || '');
  const collapsible = message.role === 'operator' && message.status === 'completed' && message.text.length > 600;
  if (!collapsible) return <p className="whitespace-pre-wrap break-words text-pretty" role={pending ? 'status' : undefined}>{message.text}</p>;
  const paragraph = message.text.indexOf('\n\n');
  const word = message.text.lastIndexOf(' ', 400);
  const boundary = paragraph >= 40 && paragraph <= 400 ? paragraph : word >= 200 ? word : 400;
  return <>
    <p className="whitespace-pre-wrap break-words text-pretty">{message.text.slice(0, boundary)}</p>
    <details className="mt-1">
      <summary className="min-h-11 cursor-pointer py-3 text-xs font-semibold">Подробнее</summary>
      <p className="whitespace-pre-wrap break-words text-pretty">{message.text.slice(boundary).trimStart()}</p>
    </details>
  </>;
}
